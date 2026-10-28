#!/usr/bin/env python3
"""Extractor for Motovario VSF (NMRV/NRV/SW/ISW worm gearmotors) catalogue.
Usage: python3 tools/extract_VSF.py [stage ...]   (stages: ratings, tables, images; default all)
Writes only into data/raw/VSF/.
PDF page index is 1-based; printed page = pdf page - 2.
"""
import csv, os, re, sys, json, collections
import pdfplumber

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "sources/catalogs/VSF_worm_NMRV.pdf")
OUT = os.path.join(ROOT, "data/raw/VSF")
os.makedirs(OUT, exist_ok=True)


def num(s):
    """catalogue number (comma decimal) -> python string with dot, '' for / or -"""
    s = s.strip()
    if s in ("", "/", "-", "–"):
        return ""
    return s.replace(",", ".")


def write_csv(name, cols, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, "") if isinstance(r, dict) else r[i] for i, c in enumerate(cols)])
    print(name, len(rows))


_pdf = None
def pdf():
    global _pdf
    if _pdf is None:
        _pdf = pdfplumber.open(PDF)
    return _pdf


def page_lines(pno, xmin=0, xmax=1e9, ymin=0, ymax=1e9, tol=2.5):
    """Words of page grouped in lines (list of list of word dicts), sorted by x."""
    pg = pdf().pages[pno - 1]
    ws = [w for w in pg.extract_words(keep_blank_chars=False, extra_attrs=["size"])
          if xmin <= w["x0"] < xmax and ymin <= w["top"] < ymax]
    ws.sort(key=lambda w: (round(w["top"]), w["x0"]))
    lines = []
    for w in ws:
        # superscripts sit ~0.6pt higher: tolerance merges them
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    for l in lines:
        l.sort(key=lambda w: w["x0"])
    return lines


# ---------------------------------------------------------------- ratings
NOMINAL_N1 = {"2": 2800, "4": 1400, "6": 900, "8": 700}


def frames_from_motor(m):
    fr = []
    for part in m.split("/"):
        mm = re.match(r"(\d+)", part)
        if mm and mm.group(1) not in fr:
            fr.append(mm.group(1))
    return ";".join(fr)


def fam(size):
    s = size
    if s.startswith("IHW"): return "IHW+NMRV-P"
    if s.startswith("HW"): return "HW+NMRV-P"
    if s.startswith("HA31+NMRV"): return "HA31+NMRV"
    if s.startswith("HA31+SW"): return "HA31+SW"
    if s.startswith("NMRV-P"): return "NMRV-P"
    if s.startswith("NMRV"): return "NMRV"
    if s.startswith("NRV-P"): return "NRV-P"
    if s.startswith("NRV"): return "NRV"
    if s.startswith("ISW"): return "ISW"
    if s.startswith("SW"): return "SW"
    return ""


def config(size):
    if size.startswith(("HA31", "HW", "IHW")): return "prestage"
    if "/" in size: return "combined"
    return "single"


RAT_COLS = ["series", "size", "stages", "n1_rpm", "p1_kw", "i", "n2_rpm", "t2_nm", "fs", "fr2_n",
            "motor_frames", "variant", "src_page",
            "family", "config", "motor_size", "poles", "n1_implied_rpm", "fr1_n", "brake_motor_only", "section"]


GM_ROW = re.compile(r"^\s*([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+(\S+)\s+(\S+(?:\s\(1\))?)\s+(\d)\s+(\d+)\s*$")


def brake_flags(p):
    """order-aligned booleans: does a '(1)' superscript (brake motor only) sit on each data row? (pdfplumber, only for few pages)"""
    flags = []
    for l in page_lines(p):
        toks = [w["text"] for w in l if w["text"] != "(1)"]
        if len(toks) == 8 and re.match(r"^[\d,.]+$", toks[0]) and toks[-2] in NOMINAL_N1:
            flags.append(any(w["text"] == "(1)" for w in l))
    return flags


def parse_gearmotor_pages(pages, rows, issues, texts):
    for p in pages:
        t = texts[p - 1]
        kw, sect = None, None
        page_rows = []
        for line in t.split("\n"):
            m = re.match(r"^\s*([\d,]+) kW\s*$", line)
            if m:
                kw = num(m.group(1)); continue
            m = re.match(r"^\s*(\d\.\d+) (NMRV/NMRV-P|SW) WORM GEARED MOTOR", line)
            if m:
                sect = m.group(1); continue
            m = GM_ROW.match(line)
            if m:
                n2, m2, fs, i, red, motor, pole, fr2 = m.groups()
                inline = "(1)" in motor
                motor = motor.replace(" (1)", "")
                if pole not in NOMINAL_N1:
                    issues.append(f"gearmotor p{p}: unknown pole count {line.strip()}"); continue
                page_rows.append(dict(series="VSF", size=red, stages="", n1_rpm=NOMINAL_N1[pole], p1_kw=kw,
                                 i=num(i), n2_rpm=num(n2), t2_nm=num(m2), fs=num(fs), fr2_n=fr2,
                                 motor_frames=frames_from_motor(motor), variant="gearmotor", src_page=p,
                                 family=fam(red), config=config(red), motor_size=motor, poles=pole,
                                 n1_implied_rpm=round(float(num(n2)) * float(num(i))),
                                 fr1_n="", brake_motor_only="1" if inline else "", section=sect))
            elif re.match(r"^\s*[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+\S", line):
                issues.append(f"gearmotor p{p}: unparsed line {line.strip()}")
        if re.search(r"^\s*\(1\)\s*$", t, re.M) or any(r["brake_motor_only"] for r in page_rows):
            fl = brake_flags(p)
            if len(fl) == len(page_rows):
                for r, f in zip(page_rows, fl):
                    r["brake_motor_only"] = "1" if f else ""
            else:
                issues.append(f"gearmotor p{p}: brake flag count mismatch {len(fl)} vs {len(page_rows)}")
        rows.extend(page_rows)


RED_ROW = re.compile(r"^\s*(\d+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+(\d+)\s+(\d+)\s*$")


def parse_reducer_pages(pages, rows, issues, texts):
    cur = None
    for p in pages:
        t = texts[p - 1]
        m = re.search(r"^\s*(\d\.\d+) .*?- (\d+) rpm", t, re.M)
        sect, n1 = (m.group(1), int(m.group(2))) if m else ("", None)
        for line in t.split("\n"):
            h = re.match(r"^\s*((?:NRV|NRV-P|ISW|IHW|HW)[A-Za-z0-9+/\-]*\d)\s*$", line)
            if h:
                cur = h.group(1); continue
            m = RED_ROW.match(line)
            if m:
                mn2, i, pn1, n2, fr1, fr2 = m.groups()
                if n1 is None or cur is None:
                    issues.append(f"reducer p{p}: no header/n1 for {line.strip()}"); continue
                rows.append(dict(series="VSF", size=cur, stages="", n1_rpm=n1, p1_kw=num(pn1), i=num(i),
                                 n2_rpm=num(n2), t2_nm=num(mn2), fs="", fr2_n=fr2, motor_frames="",
                                 variant="reducer", src_page=p, family=fam(cur), config=config(cur),
                                 motor_size="", poles="", n1_implied_rpm="", fr1_n=fr1,
                                 brake_motor_only="", section=sect))
            elif re.match(r"^\s*[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+\d", line):
                issues.append(f"reducer p{p}: unparsed line {line.strip()}")


def section_pages(texts):
    """classify pages by section title (from pdftotext)"""
    res = {"gm": [], "red": []}
    for i, t in enumerate(texts, start=1):
        if i < 80:
            continue
        if re.search(r"\n\s*(5\.1|6\.1) (NMRV/NMRV-P|SW) WORM GEARED MOTOR", t[:600]):
            res["gm"].append(i)
        elif re.search(r"\n\s*(5|6)\.\d+ (NRV|ISW|IHW)", t[:600]):
            res["red"].append(i)
    return res


def stage_ratings():
    import subprocess
    texts = subprocess.run(["pdftotext", "-layout", PDF, "-"], capture_output=True, text=True).stdout.split("\f")
    sp = section_pages(texts)
    issues = []
    rows = []
    parse_gearmotor_pages(sp["gm"], rows, issues, texts)
    parse_reducer_pages(sp["red"], rows, issues, texts)
    write_csv("ratings.csv", RAT_COLS, rows)
    json.dump({"pages": sp, "issues": issues}, open(os.path.join(OUT, "_ratings_parse_log.json"), "w"), indent=1)
    print("gearmotor pages", len(sp["gm"]), "reducer pages", len(sp["red"]), "issues", len(issues))
    for s in issues[:20]:
        print(s)
    return rows


# ---------------------------------------------------------------- motors (section 3.2)
EFF_CLASS = {"TS": "IE1", "TH": "IE2", "TP": "IE3"}   # catalogue p68 (3.2.2)


# frame -> number of printed columns, per table block of 3.2.3 (read from the page image)
MOTOR_BLOCKS = [
    [("63A", 1), ("63B", 1), ("63C", 1), ("71A", 1), ("71B", 1), ("71C", 1), ("80A", 3), ("80B", 3)],
    [("90S", 2), ("90L", 2), ("100LR", 1), ("100L", 1), ("100LA", 2), ("112MR", 1), ("112MS", 1), ("112MA", 1), ("112M", 1)],
    [("112MR", 1), ("112MS", 1), ("132S", 1), ("132SA", 1), ("132MS", 1), ("132SB", 1), ("132M", 1), ("132MA", 2), ("132MB", 2)],
    [("160M", 1), ("160MA", 1), ("160MB", 1), ("160L", 1), ("160LA", 1), ("180M", 1), ("180L", 1)],
    [("200L", 1), ("200LA", 1), ("200LB", 1), ("225S", 1), ("225M", 1), ("250M", 1), ("280S", 1), ("280M", 1)],
]


def stage_motors():
    """3.2.3 'Nominal power [kW]' (pdf p69): frame x poles x series -> power. Only printed data.
    Catalogue prints no rpm/voltage/torque/current/mass for motors -> those columns stay empty."""
    p = 69
    lines = page_lines(p)
    rows, seen = [], set()
    starts = [k for k, l in enumerate(lines) if l[0]["text"] == "Poles"]
    assert len(starts) == len(MOTOR_BLOCKS), starts
    for blk, k in zip(MOTOR_BLOCKS, starts):
        hdr = lines[k][1:]
        types = [h["text"][0::2] if h["text"][0::2] == h["text"][1::2] else h["text"] for h in hdr]
        cols = [fr for fr, n in blk for _ in range(n)]
        assert len(cols) == len(types), (blk, types)
        for dl in lines[k + 1: k + 4]:
            poles = dl[0]["text"]
            vals = [w["text"] for w in dl[1:]]
            assert len(vals) == len(cols), (poles, vals)
            for fr, ty, v in zip(cols, types, vals):
                if v == "-" or (fr, ty, poles) in seen:
                    continue
                seen.add((fr, ty, poles))
                rows.append(dict(series="VSF", motor_type=ty, frame=fr, poles=poles, power_kw=num(v),
                                 efficiency_class=EFF_CLASS[ty], src_page=p))
    cols = ["series", "motor_type", "frame", "poles", "power_kw", "rpm", "voltage_v", "efficiency_class",
            "efficiency_pct", "torque_nm", "current_a", "mass_kg", "src_page"]
    write_csv("motors.csv", cols, rows)
    return rows


MD_COLS = ["series", "size", "variant", "poles", "AC", "AD", "L", "LB", "LC", "X", "Y", "V", "D", "E", "E1", "f", "F1",
           "GA", "F", "GD", "LL", "Pg", "L_brake", "LB_brake", "LC_brake", "M", "N", "P", "LA", "S", "T", "src_page"]


def stage_motors_dimensions():
    """3.2.1 motor dimensions (pdf p66-67). *(x) values (brake/TP motors) kept in *_brake columns."""
    rows = []
    # --- p66 body table (small frames)
    lines = page_lines(66)
    tops = lambda l: l[0]["top"]
    star = [l for l in lines if l[0]["text"].startswith("*(") and len(l) == 3]
    triple = [l for l in lines if len(l) == 3 and re.match(r"^[\d,]+$", l[0]["text"]) and l[0]["x0"] < 160
              and 300 < tops(l) < 500]
    for l in lines:
        tk = [w["text"] for w in l]
        if re.match(r"^(063|071|080|90S|90L|100|112|132S|132L|160S)$", tk[0]) and len(tk) >= 14 and tops(l) < 540:
            v = tk[1:]
            r = dict(series="VSF", size=tk[0], variant="motor_body", src_page=66)
            names = ["AC", "AD", "L", "LB", "LC", "X", "Y", "V", "D", "E", "E1", "f", "F1", "GA", "F", "GD"]
            # rows whose L/LB/LC cells are two-line (value + *(brake value)) lost those three tokens in this line
            tl = [t for t in triple if abs(tops(t) - tops(l)) <= 5]
            if tl:                                       # L, LB, LC were printed on a separate line
                v = v[:2] + [w["text"] for w in tl[0]] + v[2:]
                st = [t for t in star if 0 < tops(t) - tops(tl[0]) < 12]
                if st:
                    for c, w in zip(["L_brake", "LB_brake", "LC_brake"], st[0]):
                        r[c] = num(w["text"].strip("*()"))
            if len(v) >= 10 and re.match(r"^[jk]6$", v[9]):   # D printed as "11 j6"
                v[8:10] = [v[8] + " " + v[9]]
            for c, x in zip(names, v):
                r[c] = num(x)
            rows.append(r)
    # --- p66 flange tables B5 (left) and B14 (right)
    for l in lines:
        tk = [w["text"] for w in l]
        if len(tk) == 14 and re.match(r"^\d{3}$", tk[0]) and re.match(r"^\d{3}$", tk[7]):
            for off, var in ((0, "flange_B5"), (7, "flange_B14")):
                r = dict(series="VSF", size=tk[off], variant=var, src_page=66)
                for c, x in zip(["M", "N", "P", "LA", "S", "T"], tk[off + 1: off + 7]):
                    r[c] = num(x)
                rows.append(r)
    # --- p67 large frames
    for l in page_lines(67):
        tk = [w["text"] for w in l]
        if re.match(r"^\d{3}[A-Z]$", tk[0]) and re.match(r"^[246](-[246])*$", tk[1]) and len(tk) == 16:
            r = dict(series="VSF", size=tk[0], variant="motor_body_160-280", poles=tk[1], src_page=67)
            for c, x in zip(["AC", "AD", "L", "LB", "X", "D", "E", "f", "GA", "F", "GD", "LL"], tk[2:14]):
                r[c] = num(x)
            r["Pg"] = tk[14] + " " + tk[15]
            rows.append(r)
        elif len(tk) == 7 and re.match(r"^\d{3}$", tk[0]) and tk[1].isdigit():
            r = dict(series="VSF", size=tk[0], variant="flange_B5", src_page=67)
            for c, x in zip(["M", "N", "P", "LA", "S", "T"], tk[1:]):
                r[c] = num(x)
            rows.append(r)
    write_csv("motors_dimensions.csv", MD_COLS, rows)
    return rows


# ---------------------------------------------------------------- generic table helpers
def dd(s):
    """bold header cells are printed with every glyph doubled ('GG11' -> 'G1'); undo per whitespace token"""
    if s is None:
        return ""
    out = []
    for tok in re.split(r"(\s+)", s):
        if tok.strip() and len(tok) % 2 == 0 and tok[0::2] == tok[1::2]:
            tok = tok[0::2]
        out.append(tok)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def ptext(p):
    import subprocess
    return subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), PDF, "-"],
                          capture_output=True, text=True).stdout


def tables(p):
    pg = pdf().pages[p - 1]
    ts = pg.find_tables()
    res = [(t.bbox, t.extract()) for t in ts[1:]]     # [0] is the page frame
    pg.flush_cache()
    return res


def is_size(x):
    return bool(re.match(r"^\d{3}$", x or ""))


def pivot_table(rows):
    """label x size tables: header = sizes (optionally label col 0 = group, col 1 = symbol)."""
    hdr = [dd(c) for c in rows[0]]
    sizes = [(k, h) for k, h in enumerate(hdr) if is_size(h)]
    lab = sizes[0][0] - 1                              # symbol column directly left of first size
    grp = None
    out = {h: {} for _, h in sizes}
    groups = {h: {} for _, h in sizes}
    for r in rows[1:]:
        if lab >= 1 and r[0]:
            grp = re.sub(r"\s+", "/", dd(r[0]).strip())
        sym = dd(r[lab])
        if not sym:
            continue
        for k, h in sizes:
            v = r[k]
            if v is None:
                continue
            out[h][sym] = num(v.replace("\n", " ")) if re.match(r"^[\d,.\-/ ()*A-Za-z]*$", v) else num(v)
            groups[h][sym] = grp
    return out, groups


def stage_dimensions():
    housing, shaft, mflange = [], [], []
    HC = []   # column order, filled as encountered

    def add_housing(p, fam_name, tbl, forced_variant=None):
        out, groups = pivot_table(tbl)
        for size, d in out.items():
            by_var = collections.OrderedDict()
            for sym, v in d.items():
                g = groups[size][sym]
                var = forced_variant or (f"{fam_name}[{g}]" if g else fam_name)
                by_var.setdefault(var, {})[sym] = v
                if sym not in HC: HC.append(sym)
            for var, dv in by_var.items():
                r = dict(series="VSF", size=f"{fam_name} {size}", variant=var, src_page=p)
                r.update(dv)
                housing.append(r)

    def add_shaft(p, fam_name, tbl):
        cur = None
        for r in tbl[1:]:
            if r[0]: cur = r[0]
            if cur is None or not r[1]: continue
            shaft.append(dict(series="VSF", size=f"{fam_name} {cur}", variant=fam_name, **{"D H8": num(r[1]),
                              "b": num(r[2]), "t": num(r[3]), "T": num(r[4]), "src_page": p}))

    def add_mfl(p, fam_name, tbl):
        h = [dd(c) for c in tbl[0]]
        var = "B5" if h[0].startswith("B5") else "B14"
        for r in tbl[1:]:
            mflange.append(dict(series="VSF", size=r[0], variant=f"{fam_name} {var}", Pm=num(r[1]), Dm=num(r[2]),
                                bm=num(r[3]), tm=num(r[4]), src_page=p))

    # NMRV 030-150 (p52), SW (p55), NRV (p56), ISW (p59)
    for p, fam_name, kinds in ((52, "NMRV", "pshbB"), (55, "SW", "pp" + "shbB"), (56, "NRV", "pshb"), (59, "ISW", "ppsh")):
        tb = tables(p)
        pivots = [t for _, t in tb if is_size(dd(t[0][1] if len(t[0]) > 1 else "")) or is_size(dd(t[0][2] if len(t[0]) > 2 else ""))
                  and not is_size(dd(t[1][0]))]
        # classify
        for bbox, t in tb:
            h0 = [dd(c) for c in t[0]]
            if h0[0].startswith(("B5", "B14")) or h0[0] in ("B5 Pm Dm bm tm",):
                add_mfl(p, fam_name, t)
            elif "D H8" in h0 or "D b t T" in " ".join(h0) or (len(h0) == 5 and h0[1] in ("D H8", "D\nH8")):
                add_shaft(p, fam_name, t)
            elif any(is_size(x) for x in h0[1:]):
                add_housing(p, fam_name, t)
    # HA31 + NMRV / SW (p60): G4,G5 per reducer size, by motor flange
    tb = tables(60)
    for bbox, t in tb:
        h0 = [dd(c) if c else "" for c in t[0]]
        if h0[0] == "B5":
            add_mfl(60, "HA31", t)
        elif any(x.startswith(("NMRV", "SW")) for x in h0):
            fam_name = "HA31+NMRV" if "NMRV040" in h0 else "HA31+SW"
            cols = [(k, h0[k]) for k in range(len(h0)) if h0[k]]
            sub = [dd(c) for c in t[1]]
            for r in t[2:]:
                for k, nm in cols:
                    for j in (k, k + 1):
                        pass
                    rec = dict(series="VSF", size=f"{fam_name[:-3] if False else fam_name}{nm.replace('NMRV','').replace('SW','')}",
                               variant=fam_name, src_page=60)
                for k, nm in cols:
                    rec = dict(series="VSF", size=f"HA31+{nm}", variant=f"{fam_name} (motor flange {r[0]})", src_page=60)
                    rec["G4"] = num(r[k]); rec["G5"] = num(r[k + 1])
                    rec["motor_flange"] = r[0]
                    housing.append(rec)
    for c in ("G4", "G5", "motor_flange"):
        if c not in HC: HC.append(c)
    # HW (p61) and IHW (p62)
    tb = tables(61)
    t = tb[0][1]
    hw_cols = [(k, dd(t[0][k]) ) for k in range(len(t[0])) if t[0][k]]
    # row 1 = NMRV-P size header per column (printed in 2nd header row)
    hdr2 = t[1]
    for r in t[2:]:
        sym = dd(r[0])
        if not sym: continue
        pass
    for bbox, t in tb:
        h0 = [dd(c) if c else "" for c in t[0]]
        if h0[0].startswith("NMRV-P") and "D H8" in h0:
            add_shaft(61, "NMRV-P/HW", t)
        elif h0[0] == "B5":
            add_mfl(61, "HW", t)
        elif h0[0] == "B14":
            add_mfl(61, "HW", t)
    # HW table, wide: row0 = [,HW030,None,HW040,None]; row1 = [,frames..]; row2 = [,NMRV-P 063,075,090,110]?
    t = tb[0][1]
    for ri, r in enumerate(t[:4]):
        pass
    hwt = [[(c or "") for c in r] for r in t]
    # find the row that holds the NMRV-P sizes
    hdr_rows = [i for i, r in enumerate(hwt) if any(x.startswith("NMRV") or "NMRV" in dd(x) for x in r)]
    # fall back: sizes from catalogue layout NMRV-P 063/075/090/110 in column order
    sizes_hw = ["NMRV-P063", "NMRV-P075", "NMRV-P090", "NMRV-P110"]
    hw_pre = ["HW030", "HW030", "HW040", "HW040"]
    for r in hwt[2:]:
        sym = dd(r[0])
        if not sym: continue
        vals = [x for x in r[1:] if x != ""]
        for k, (pre, sz) in enumerate(zip(hw_pre, sizes_hw)):
            if k < len(vals):
                housing_rec = dict(series="VSF", size=f"{pre}+{sz}", variant="HW+NMRV-P", src_page=61)
                housing_rec[sym] = num(vals[k])
                housing.append(("HWROW", housing_rec))
    write_housing(housing, HC)
    write_csv("dimensions_shaft_bore.csv", ["series", "size", "variant", "D H8", "b", "t", "T", "src_page"], shaft)
    write_csv("dimensions_motor_input_flange.csv", ["series", "size", "variant", "Pm", "Dm", "bm", "tm", "src_page"], mflange)


def write_housing(housing, HC):
    # merge HW rows (one dict per symbol) into one row per size
    merged, rows = {}, []
    for r in housing:
        if isinstance(r, tuple):
            d = r[1]
            m = merged.setdefault(d["size"], dict(series="VSF", size=d["size"], variant=d["variant"], src_page=61))
            for k, v in d.items():
                if k not in ("series", "size", "variant", "src_page"):
                    m[k] = v
                    if k not in HC: HC.append(k)
        else:
            rows.append(r)
    rows += list(merged.values())
    rows = [r for r in rows if any(v not in ("", None) for k, v in r.items() if k not in ("series", "size", "variant", "src_page"))]
    write_csv("dimensions_housing.csv", ["series", "size", "variant"] + HC + ["src_page"], rows)


def stage_dimensions_combined():
    """p62 IHW, p63-65 combined units (rows = size pairs, columns = symbols)"""
    rows, cols = [], []

    def addcols(c):
        for x in c:
            if x not in cols: cols.append(x)

    # IHW040 + NMRV-P 090/110 (p62): symbols down, sizes in header row 1
    for bbox, t in tables(62):
        sizes = [dd(c) for c in t[1][1:]]
        for k, sz in enumerate(sizes, start=1):
            rec = dict(series="VSF", size=f"IHW040+{sz.replace(' ', '')}", variant="IHW040+NMRV-P", src_page=62)
            for r in t[2:]:
                sym = dd(r[0])
                if sym and r[k] not in (None, ""):
                    rec[sym] = num(r[k].replace(" j6", ""))
                    if " j6" in r[k]: rec[sym + "_tol"] = "j6"
            addcols([k2 for k2 in rec if k2 not in ("series", "size", "variant", "src_page")])
            rows.append(rec)
    titles = {63: ["NMRV/NMRV-P+NMRV/NMRV-P (3.1.10)"], 64: ["NRV/NRV-P+NMRV/NMRV-P input side (3.1.11)"],
              65: ["SW+SW (3.1.12)", "ISW+SW (3.1.13) / SW+SW input side"]}
    for p in (63, 64, 65):
        tb = tables(p)
        for n, (bbox, t) in enumerate(tb):
            hdr = [dd(c) for c in t[0]]
            var = titles[p][min(n, len(titles[p]) - 1)] if p != 65 else \
                ("SW+SW / ISW+SW combined housing (3.1.12-13)" if "G" in hdr else "SW+SW / ISW+SW input side (3.1.12-13)")
            for r in t[1:]:
                if not r[0]:
                    continue
                rec = dict(series="VSF", size=r[0], variant=var, src_page=p)
                for sym, v in zip(hdr[1:], r[1:]):
                    rec[sym] = num(v or "")
                rows.append(rec)
                addcols(hdr[1:])
    write_csv("dimensions_combined.csv", ["series", "size", "variant"] + cols + ["src_page"], rows)


def stage_weights():
    rows = []
    p = 70
    for bbox, t in tables(p):
        h0 = [dd(c) if c else "" for c in t[0]]
        title = h0[0]
        if title.startswith(("NMRV - NMRV-P", "NRV - NRV-P")):
            nrv = title.startswith("NRV")
            for sz, v in zip([dd(x) for x in t[1]], t[2]):
                if nrv:
                    nm = f"NRV{sz}" if sz in ("030", "040", "050", "130", "150") else f"NRV-P{sz}"
                else:
                    nm = f"NMRV{sz}" if sz in ("025", "030", "040", "050", "130", "150") else f"NMRV-P{sz}"
                rows.append(dict(series="VSF", size=nm, variant="NRV reducer (no motor, no oil)" if nrv else
                                 "NMRV gearbox (no motor, no oil)", motor_frame="", mass_kg=num(v), src_page=p))
        elif h0[1:2] and h0[1].startswith("HA31+") and "(~ kg)" in h0[1]:
            for r in t[1:]:
                for k in range(1, len(h0)):
                    if h0[k].startswith("HA31+") and r[k]:
                        rows.append(dict(series="VSF", size=h0[k].replace(" (~ kg)", ""), variant="HA31 prestage + reducer (no motor, no oil)",
                                         motor_frame=r[0], mass_kg=num(r[k]), src_page=p))
        elif len(t) == 2 and "IHW" in dd(t[0][0]):
            for k in range(len(t[0])):
                nm = dd(t[0][k]).replace("(~ kg)", "").replace("\n", "").strip()
                rows.append(dict(series="VSF", size=nm.replace("NMRV- P", "NMRV-P").replace("/", "+").replace("NMRV-P090+IHW040", "IHW040+NMRV-P090")
                                 .replace("NMRV-P110+IHW040", "IHW040+NMRV-P110").replace("NMRV- P", "NMRV-P"),
                                 variant="IHW prestage + NMRV-P (no motor, no oil)", motor_frame="", mass_kg=num(t[1][k]), src_page=p))
        elif len(t) == 3 and "HW" in dd(t[1][0]):
            for k in range(len(t[1])):
                nm = dd(t[1][k]).replace("(~ kg)", "").strip()
                a, b = nm.split("/")
                rows.append(dict(series="VSF", size=f"{b}+{a}", variant="HW prestage + NMRV-P (no motor, no oil)",
                                 motor_frame=dd(t[0][0 if k < 2 else 2]), mass_kg=num(t[2][k]), src_page=p))
        elif title.startswith(("NMRV+NMRV", "NRV+NMRV", "SW+SW", "ISW+SW")) or title.startswith("SW (") or title.startswith("ISW ("):
            combos = [dd(x) for x in t[1]] if len(t) > 2 else [dd(x) for x in t[1]]
            if title.startswith(("SW (", "ISW (")):
                var = ("SW" if title.startswith("SW") else "ISW") + " (no motor, no oil)"
                combos = [dd(x) for x in t[1]]
                for sz, v in zip(combos, t[2]):
                    rows.append(dict(series="VSF", size=f"{'SW' if title.startswith('SW') else 'ISW'}{sz}", variant=var,
                                     motor_frame="", mass_kg=num(v), src_page=p))
                continue
            raw = "|".join(c or "" for c in t[1])
            raw = raw.replace(" 00|4400", "|004400")          # one header cell is split by the PDF text layer
            combos = [dd(x) for x in raw.split("|") if x]
            vals = [x for x in t[2] if x]
            assert len(combos) == len(vals), (title, combos, vals)
            for sz, v in zip(combos, vals):
                rows.append(dict(series="VSF", size=sz, variant=f"{title.replace(' (~ kg)', '').replace('(~ kg)', '').strip()} combined (no motor, no oil)",
                                 motor_frame="", mass_kg=num(v), src_page=p))
        elif h0[1:2] and h0[1].startswith("HA31+SW"):
            for r in t[1:]:
                for k in range(1, len(h0)):
                    if h0[k].startswith("HA31+SW") and r[k]:
                        rows.append(dict(series="VSF", size=h0[k].replace(" (~ kg)", ""), variant="HA31 prestage + reducer (no motor, no oil)",
                                         motor_frame=r[0], mass_kg=num(r[k]), src_page=p))
    write_csv("weights.csv", ["series", "size", "variant", "motor_frame", "mass_kg", "src_page"], rows)


def stage_lubrication():
    """p49 table 2.12.4 (values read from the page; merged cells mean the same quantity for B3..V6)."""
    p = 49
    oil = "synthetic ENI TELIUM VSF (ISO VG320), lubricated for life"
    rows = []
    tb = tables(p)
    pos = ["B3", "B8", "B6-B7", "V5", "V6"]
    for bbox, t in tb:
        h = [dd(c) if c else "" for c in t[0]]
        name = h[0]
        if name == "NMRV":
            sizes = h[1:]
            for k, sz in enumerate(sizes):
                for r in t[1:]:
                    v = r[k + 1]
                    if v in (None, ""):
                        v = next((x[k + 1] for x in t[1:] if x[k + 1]), "")   # merged cell: single value for all rows
                        if sz in ("130", "150"):
                            v = ""
                    rows.append(dict(series="VSF", size=f"NMRV{sz}", mounting_position=dd(r[0]), oil_l=num(v), oil_type=oil, src_page=p))
        elif name in ("NMRV-P", "SW"):
            for k, sz in enumerate(h[1:], start=1):
                val = next((x[k] for x in t[1:] if x[k]), "")
                for r in t[1:]:
                    rows.append(dict(series="VSF", size=("NMRV-P" if name == "NMRV-P" else "SW") + sz, mounting_position=dd(r[0]),
                                     oil_l=num(val), oil_type=oil, src_page=p))
        elif name == "HW":
            for k in range(1, len(t[1])):
                pass
    # HW and HA31 small tables: parse from text (single value rows)
    txt = ptext(p)
    m = re.search(r"NMRV-P063\s+NMRV-P075\s+NMRV-P090\s+NMRV-P110\s*\n\s*B3\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", txt)
    if m:
        for sz, pre, v in zip(["063", "075", "090", "110"], ["HW030", "HW030", "HW040", "HW040"], m.groups()):
            rows.append(dict(series="VSF", size=f"{pre}+NMRV-P{sz}", mounting_position="B3", oil_l=num(v), oil_type=oil + " (HW prestage module, separate oil)", src_page=p))
    m = re.search(r"B3-B5\s+([\d,]+)", txt)
    if m:
        rows.append(dict(series="VSF", size="HA31", mounting_position="B3-B5", oil_l=num(m.group(1)), oil_type=oil + " (HA31 prestage module, separate oil)", src_page=p))
    write_csv("lubrication.csv", ["series", "size", "mounting_position", "oil_l", "oil_type", "src_page"], rows)


def stage_service_factor():
    """p10: nomogram image. Curves A/B/C digitised at the printed starts/hour ticks; hours/day scales read off
    the left-hand scales (row offsets 0.7 / 0.9 / 1.1 / 1.4 at the bottom row for 2 / 8 / 16 / 24 h)."""
    import subprocess, tempfile
    from PIL import Image
    import numpy as np
    tmp = tempfile.mkdtemp()
    subprocess.run(["pdfimages", "-png", "-f", "10", "-l", "10", PDF, os.path.join(tmp, "sf")], check=True)
    im = np.array(Image.open(os.path.join(tmp, "sf-000.png")).convert("L"))
    xt = {5: 589, 10: 642, 20: 732, 30: 822, 40: 913, 50: 1004, 60: 1093, 70: 1183, 80: 1273, 90: 1365, 100: 1455}
    y_bottom, step = 485.0, 35.5      # y of 0.7 (2 h scale) and pixels per 0.1
    offs = {2: 0.0, 8: 0.2, 16: 0.4, 24: 0.7}
    rows = []
    for k, x in xt.items():
        xx = x + (6 if k == 5 else (-6 if k == 100 else 0))
        col = im[96:510, xx - 1:xx + 2].min(axis=1)
        runs, cur = [], []
        for i, v in enumerate(col):
            if v < 70: cur.append(i + 96)
            elif cur: runs.append(sum(cur) / len(cur)); cur = []
        if cur: runs.append(sum(cur) / len(cur))
        # A lowest curve (largest y) ... C highest; merge split runs of the same curve
        merged = []
        for r in runs:
            if merged and abs(r - merged[-1]) < 6: merged[-1] = (merged[-1] + r) / 2
            else: merged.append(r)
        assert len(merged) == 3, (k, runs)
        for cls, y in zip("CBA", merged):
            base = 0.7 + (y_bottom - y) / (step * 10)
            for h, o in offs.items():
                rows.append(dict(series="VSF", load_class=cls, hours_per_day=h, starts_per_hour=k, fs=round(base + o, 2), src_page=10))
    rows.sort(key=lambda r: (r["load_class"], r["hours_per_day"], r["starts_per_hour"]))
    write_csv("service_factor.csv", ["series", "load_class", "hours_per_day", "starts_per_hour", "fs", "src_page"], rows)


def across(p, idx, label_col_name=None):
    """symbols-down / sizes-across table -> (sizes, {symbol: [values]})"""
    t = tables(p)[idx][1]
    h = [dd(c) for c in t[0]]
    sizes = h[1:]
    return h[0], sizes, {dd(r[0]): [num(x or "") for x in r[1:]] for r in t[1:]}


def stage_motor_interface():
    """2.9.1 (NMRV/NMRV-P, p33) and 2.9.5 (SW, p37): IEC frame / flange / bore per reducer size + feasibility by ratio."""
    mi, mat = [], []
    for p, famname in ((33, "NMRV"), (37, "SW")):
        t = tables(p)[0][1]
        hdr_i = [dd(c) for c in t[1]]
        ratios = [num(x) for x in hdr_i[6:]]
        size, cur = None, None
        pend = []
        for r in t[2:]:
            if r[0]:
                size = r[0]
            frame = r[1]
            m = re.match(r"^([\d/]+)B(5|14)$", frame)
            cell_vals = r[6:]
            if any(v not in (None, "") for v in cell_vals):
                cur = [v for v in cell_vals]            # merged cells: value belongs to this and the following None-row
            row_size = (f"NMRV{size}" if famname == "NMRV" and size in ("025", "030", "040", "050", "130", "150")
                        else (f"NMRV-P{size}" if famname == "NMRV" else f"SW{size}"))
            mi.append(dict(series="VSF", size=row_size, iec_frame=m.group(1), flange="B" + m.group(2), bore_mm=num(r[5]),
                           src_page=p, N_mm=num(r[2]), M_mm=num(r[3]), P_mm=num(r[4])))
            for i_, v in zip(ratios, cur):
                st = {"•": "feasible", "•*": "feasible (low profile key supplied)", "**": "not feasible",
                      "+": "not to be used (out of warranty)"}.get(v, "raw:" + str(v))
                mat.append(dict(series="VSF", size=row_size, iec_frame=m.group(1), flange="B" + m.group(2), i=i_,
                                status=st, cell=v, src_page=p))
    write_csv("motor_interface.csv", ["series", "size", "iec_frame", "flange", "bore_mm", "src_page", "N_mm", "M_mm", "P_mm"], mi)
    write_csv("extra_motor_flange_ratio_matrix.csv", ["series", "size", "iec_frame", "flange", "i", "status", "cell", "src_page"], mat)


def stage_extras():
    # 2.5 mesh data (p29)
    t = tables(29)[0][1]
    hdr = [dd(c) for c in t[0]]
    ratios = [num(x) for x in hdr[2:]]
    rows, size = [], None
    recs = {}
    for r in t[1:]:
        if r[0]: size = r[0]
        sym = dd(r[1])
        for i_, v in zip(ratios, r[2:]):
            recs.setdefault((size, i_), {})[sym] = (v or "")
    for (sz, i_), d in recs.items():
        if all(v in ("", "-") for v in d.values()):
            continue
        rows.append(dict(series="VSF", size=f"NMRV {sz}", i=i_, Z1=num(d.get("Z1", "")), lead_angle=d.get("ϒ", ""),
                         Mx=num(d.get("Mx", "")), eta_dyn_1400=num(d.get("ηδ(1400)", d.get("ηδ(1400)".replace("δ", "d"), ""))),
                         eta_static=num(d.get("ηs", "")), src_page=29))
    write_csv("extra_mesh_efficiency.csv", ["series", "size", "i", "Z1", "lead_angle", "Mx", "eta_dyn_1400", "eta_static", "src_page"], rows)
    # backlash (p30)
    rows = []
    for bbox, t in tables(30):
        for h, v in zip(t[0], t[1]):
            rows.append(dict(series="VSF", size=dd(h), backlash_arcmin=v.replace("÷", "-"), src_page=30))
    write_csv("extra_backlash.csv", ["series", "size", "backlash_arcmin", "src_page"], rows)
    # output shaft bearings (p44)
    rows = []
    for r in tables(44)[0][1][1:]:
        rows.append(dict(series="VSF", size=r[1], variant=r[0], standard_bearing="ball" if r[2] == "1" else r[2],
                         on_request=("roller" if r[3] == "2" else ""), src_page=44))
    write_csv("extra_output_bearings.csv", ["series", "size", "variant", "standard_bearing", "on_request", "src_page"], rows)
    # overhung load parameters (p45 input, p46 output)
    rows = []
    for p in (45, 46):
        for idx in range(len(tables(p))):
            name, sizes, d = across(p, idx)
            for k, sz in enumerate(sizes):
                rows.append(dict(series="VSF", size=f"{name} {sz}".strip(), shaft="input" if p == 45 else "output",
                                 a_mm=d["a"][k], b_mm=d["b"][k],
                                 fr_max_n=[v for kk, v in d.items() if kk.startswith("Fr")][0][k], src_page=p))
    write_csv("radial_load_params.csv", ["series", "size", "shaft", "a_mm", "b_mm", "fr_max_n", "src_page"], rows)
    # moments of inertia (p50)
    rows = []
    for bbox, t in tables(50):
        title = dd(t[0][0])
        for r in t[1:]:
            if r[0] and r[1]:
                rows.append(dict(series="VSF", size=f"{title} {r[0]}", J1_kgm2=num(r[1]), src_page=50))
    # HA31 / A31 line printed in text
    m = re.search(r"A31\s+([\d,]+)", ptext(50))
    if m: rows.append(dict(series="VSF", size="HA31 (A31)", J1_kgm2=num(m.group(1)), src_page=50))
    write_csv("extra_inertia.csv", ["series", "size", "J1_kgm2", "src_page"], rows)
    # low speed (output) shafts p72
    t = tables(72)[0][1]
    hdr = [dd(c) for c in t[0]]
    rows = []
    for r in t[1:]:
        rec = dict(series="VSF", size=r[1], variant=re.sub(r"[​\s]+", " ", r[0] or "").strip(), src_page=72)
        for c, v in zip(hdr[2:], r[2:]):
            rec[c] = re.sub(r"\s+", " ", (v or "").replace(",", ".")).strip()
        rows.append(rec)
    write_csv("extra_low_speed_shafts.csv", ["series", "size", "variant"] + hdr[2:] + ["src_page"], rows)
    # torque arm dimensions p76
    name, sizes, d = across(76, 0)
    rows = []
    for k, sz in enumerate(sizes):
        rec = dict(series="VSF", size=sz, variant="NMRV/NMRV-P/SW torque arm", src_page=76)
        for sym, vals in d.items(): rec[sym] = vals[k]
        rows.append(rec)
    write_csv("extra_torque_arm.csv", ["series", "size", "variant"] + list(d.keys()) + ["src_page"], rows)
    # output shaft cover N2 (p77) from text
    rows = []
    for m in re.finditer(r"^\s*(\d{3})\s+([\d,]+)\s*$", ptext(77), re.M):
        rows.append(dict(series="VSF", size=m.group(1), N2=num(m.group(2)), src_page=77))
    write_csv("extra_output_shaft_cover.csv", ["series", "size", "N2", "src_page"], rows)


def stage_designation():
    seg = lambda name, desc, vals=None, page=None: {"name": name, "description": desc, "values": vals or {}, "src_page": page}
    flange = {"FA": "output flange type FA", "FB": "output flange type FB", "FC": "output flange type FC",
              "FD": "output flange type FD", "FE": "output flange type FE"}
    ex_sw = dict(flange, PA="torque arm/foot execution PA", PB="PB", PV="PV", PAS="PAS", PBS="PBS", PVS="PVS")
    pos = {k: f"mounting position {k}" for k in ("B3", "B8", "B6", "B7", "V5", "V6")}
    common_tail = [
        seg("input_dimensions", "input dimensions: motor-flange fitting (PAM + IEC size, e.g. 160x14 = flange Ø160 x bore 14) or input shaft diameter (ECE)", {"PAM": "fitted for motor coupling", "ECE": "input shaft diameter"}),
        seg("VS", "double input shaft (option, blank box in the catalogue = value to be specified)"),
        seg("output_flange_dia", "Ø output flange (mm, e.g. 125)"),
        seg("output_shaft_dia", "Ø output shaft (mm, e.g. 25)"),
    ]
    d = {
        "series": "VSF", "source_pages": [13, 14, 15, 16, 17],
        "note": "The designation is shown on pp.11-15 of the printed catalogue only as flow diagrams (images); segments are in drawing order, values are the boxes printed in the diagram.",
        "patterns": [
            {"family": "NMRV / NRV (worm gearbox, p13)", "pattern": "NMRV 050 HA31 FA 7,5 160x14 VS 125 25 BS B3 ...accessories",
             "segments": [
                 seg("gearbox_type", "gearbox type", {"NMRV": "worm geared motor / gearbox with motor flange", "NRV": "worm gear reducer with input shaft"}),
                 seg("size", "size", {k: k for k in ("025", "030", "040", "050", "063", "075", "090", "105", "110", "130", "150")}),
                 seg("prestage", "optional pre-stage helical module", {"HA31": "pre-stage helical module (NMRV 040-050)"}),
                 seg("output_flange", "output flange", flange),
                 seg("ratio", "reduction ratio (5, 7,5, 10 ... 100, then pre-stage ratios e.g. 22,08 ... 315)")] + common_tail + [
                 seg("execution", "execution", {"AS": "AS", "BS": "BS", "VS": "VS", "PS": "PS"}),
                 seg("mounting_position", "mounting position", pos),
                 seg("accessories", "accessories")]},
            {"family": "NMRV-P / NRV-P (p14)", "pattern": "NMRV-P 063 HW030 FA 30 160x14 VS 125 25 B3 ...accessories",
             "segments": [
                 seg("gearbox_type", "gearbox type", {"NMRV-P": "NMRV-P worm geared motor (power series)", "NRV-P": "NRV-P worm reducer"}),
                 seg("size", "size", {k: k for k in ("063", "075", "090", "110")}),
                 seg("prestage", "optional pre-stage helical module", {"HW030": "HW030", "HW040": "HW040", "IHW040": "IHW040"}),
                 seg("output_flange", "output flange", flange),
                 seg("ratio", "reduction ratio (5/7,5 ... 100, with pre-stage 22,08 ... 1083,3)")] + common_tail + [
                 seg("mounting_position", "mounting position", pos), seg("accessories", "accessories")]},
            {"family": "combined NMRV+NMRV etc. (p15)", "pattern": "NMRV+NMRV-P 050+110 FA 900 160x14 40 BS1 B3",
             "segments": [
                 seg("gearbox_type", "combined unit", {"NMRV+NMRV": "combined geared motor", "NMRV+NMRV-P": "combined geared motor",
                       "NMRV-P+NMRV": "combined geared motor", "NMRV-P+NMRV-P": "combined geared motor", "NRV+NMRV": "combined gear reducer",
                       "NRV+NMRV-P": "combined gear reducer", "NRV-P+NMRV": "combined gear reducer", "NRV-P+NMRV-P": "combined gear reducer"}),
                 seg("size", "size pair", {k: k for k in ("025+030", "025+040", "030+030", "030+050", "030+063", "040+050", "040+063", "040+075",
                       "040+090", "050+090", "050+110", "063+110", "063+130", "063+150")}),
                 seg("output_flange", "output flange", flange),
                 seg("ratio", "reduction ratio (e.g. 900)"),
                 seg("input_dimensions", "input dimensions: PAM (fitted for motor coupling) / ECE (input shaft diameter)", {"PAM": "motor coupling", "ECE": "input shaft"}),
                 seg("output_shaft_dia", "Ø output shaft (mm)"),
                 seg("execution", "execution", {k: k for k in ("AS1", "AS2", "BS1", "BS2", "VS1", "VS2", "PS1", "PS2")}),
                 seg("mounting_position", "mounting position")]},
            {"family": "SW / ISW (p16)", "pattern": "SW 050 HA31 FA 7,5 160x14 VS 125 25 BS B3 ...accessories",
             "segments": [
                 seg("gearbox_type", "gearbox type", {"SW": "SW worm geared motor", "ISW": "ISW worm gear reducer"}),
                 seg("size", "size", {k: k for k in ("030", "040", "050", "063", "075", "090", "105")}),
                 seg("prestage", "optional pre-stage helical module", {"HA31": "pre-stage helical module"}),
                 seg("output_flange", "output flange / execution of housing", ex_sw),
                 seg("ratio", "reduction ratio (5, 7,5 ... 100, with pre-stage 22,08 ... 315)")] + common_tail + [
                 seg("execution", "execution", {"AS": "AS", "BS": "BS", "VS": "VS", "PS": "PS"}),
                 seg("mounting_position", "mounting position", pos), seg("accessories", "accessories")]},
            {"family": "SW+SW / ISW+SW (p17)", "pattern": "SW+SW 050+110 FA 900 160x14 40 BS1 B3",
             "segments": [
                 seg("gearbox_type", "combined unit", {"SW+SW": "combined geared motor", "ISW+SW": "combined gear reducer"}),
                 seg("size", "size pair", {k: k for k in ("030+040", "030+050", "030+063", "040+050", "040+063", "040+075", "040+090", "050+090", "050+105", "063+105")}),
                 seg("output_flange", "output flange / execution", ex_sw),
                 seg("ratio", "reduction ratio (e.g. 900)"),
                 seg("input_dimensions", "input dimensions: PAM / ECE", {"PAM": "motor coupling", "ECE": "input shaft"}),
                 seg("output_shaft_dia", "Ø output shaft (mm)"),
                 seg("execution", "execution", {k: k for k in ("AS1", "AS2", "BS1", "BS2", "VS1", "VS2", "PS1", "PS2")}),
                 seg("mounting_position", "mounting position")]}],
        "gearmotor_ordering_note": "Geared motors in the selection tables (5.1 / 6.1) are given as size + motor (IEC frame, poles, kW); VSF has no separate motor-code segment in the printed designation.",
    }
    json.dump(d, open(os.path.join(OUT, "designation.json"), "w"), indent=1, ensure_ascii=False)
    print("designation.json")


IMG_PAGES = {  # pdf page: (size, kind, caption)
    10: ("general", "diagram", "service factor nomogram (load class A/B/C, hours/day, starts/hour)"),
    13: ("NMRV", "diagram", "designation NMRV/NRV"), 14: ("NMRV-P", "diagram", "designation NMRV-P/NRV-P"),
    15: ("NMRV+NMRV", "diagram", "designation combined NMRV units"), 16: ("SW", "diagram", "designation SW/ISW"),
    17: ("SW+SW", "diagram", "designation combined SW units"),
    18: ("NMRV", "render", "versions NMRV"), 19: ("NMRV-P", "render", "versions NMRV-P"), 20: ("SW", "render", "versions SW"),
    21: ("NMRV", "render", "modularity NMRV"), 22: ("NMRV-P", "render", "modularity NMRV-P"), 23: ("SW", "render", "modularity SW"),
    24: ("general", "drawing", "mounting positions NMRV/NMRV-P/NRV/HW (+SW-T)"), 25: ("SW", "drawing", "mounting positions SW"),
    26: ("general", "drawing", "executions"), 27: ("general", "drawing", "executions and terminal box position"),
    31: ("general", "drawing", "direction of rotation of high speed shaft"),
    33: ("NMRV", "drawing", "motor flange dimensions N M P D"), 34: ("NMRV", "drawing", "hybrid motor flange sketch"),
    37: ("SW", "drawing", "motor flange sketch SW"), 38: ("SW", "drawing", "hybrid motor flange sketch SW"),
    40: ("combined", "diagram", "ratios of combined units (figure)"), 43: ("combined", "diagram", "ratios of SW combined units (figure)"),
    45: ("general", "drawing", "overhung load on input shaft"), 46: ("general", "drawing", "overhung load on output shaft"),
    51: ("NMRV025", "drawing", "dimensions NMRV 025"), 52: ("NMRV", "drawing", "dimensions NMRV 030-150 views"),
    53: ("SW", "drawing", "dimensions SW views"), 54: ("SW", "drawing", "dimensions SW views (2)"),
    56: ("NRV", "drawing", "dimensions NRV views"), 57: ("ISW", "drawing", "dimensions ISW views"),
    58: ("ISW", "drawing", "dimensions ISW views (2)"), 60: ("HA31", "drawing", "dimensions HA31+NMRV / HA31+SW"),
    61: ("HW", "drawing", "dimensions NMRV-P/HW"), 62: ("IHW", "drawing", "dimensions NMRV-P/IHW"),
    63: ("combined", "drawing", "dimensions NMRV/NMRV-P + NMRV/NMRV-P"), 64: ("combined", "drawing", "dimensions NRV + NMRV"),
    65: ("combined", "drawing", "dimensions SW+SW / ISW+SW"), 66: ("motors", "drawing", "electric motor dimensions 063-160S"),
    67: ("motors", "drawing", "electric motor dimensions 160M-280M"), 71: ("general", "drawing", "end shaft key"),
    72: ("general", "drawing", "low speed shafts"), 73: ("general", "drawing", "output flange drawings"),
    74: ("general", "drawing", "torque arm mounting positions"), 75: ("general", "drawing", "torque arm mounting positions (NRV/ISW)"),
    76: ("general", "drawing", "torque arm dimensions"), 77: ("general", "drawing", "output shaft cover"),
    78: ("general", "drawing", "torque limiter dimensions"), 79: ("general", "drawing", "torque limiter operating principle"),
}


def stage_images():
    import subprocess, tempfile, shutil
    from PIL import Image
    imgdir = os.path.join(OUT, "images")
    os.makedirs(imgdir, exist_ok=True)
    rows = []
    for p, (size, kind, cap) in sorted(IMG_PAGES.items()):
        lst = subprocess.run(["pdfimages", "-list", "-f", str(p), "-l", str(p), PDF], capture_output=True, text=True).stdout.splitlines()[2:]
        types = [l.split()[2] for l in lst]
        tmp = tempfile.mkdtemp()
        subprocess.run(["pdfimages", "-png", "-f", str(p), "-l", str(p), PDF, os.path.join(tmp, "x")], check=True)
        files = sorted(os.listdir(tmp))
        n = 0
        for f, ty in zip(files, types):
            if ty != "image":
                continue
            n += 1
            im = Image.open(os.path.join(tmp, f))
            if im.width < 150 or im.height < 100:
                continue
            name = f"VSF_{size}_{kind}_p{p}_{n}.png"
            shutil.copy(os.path.join(tmp, f), os.path.join(imgdir, name))
            rows.append(dict(file=name, series="VSF", size=size, kind=kind, caption=cap, src_page=p, width_px=im.width, height_px=im.height))
        shutil.rmtree(tmp)
    write_csv("images/index.csv", ["file", "series", "size", "kind", "caption", "src_page", "width_px", "height_px"], rows)


def stage_tables():
    stage_motors()
    stage_motors_dimensions()
    stage_dimensions()
    stage_dimensions_combined()
    stage_weights()
    stage_lubrication()
    stage_service_factor()
    stage_motor_interface()
    stage_extras()
    stage_designation()


if __name__ == "__main__":
    stages = sys.argv[1:] or ["ratings", "tables", "images"]
    if "ratings" in stages: stage_ratings()
    if "tables" in stages: stage_tables()
    if "images" in stages: stage_images()
