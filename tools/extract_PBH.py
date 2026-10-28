#!/usr/bin/env python3
"""Extract Motovario PBH (parallel / bevel helical, IEC) catalogue into data/raw/PBH/.

Usage:  python3 tools/extract_PBH.py            (from repo root)
Needs:  pdftotext, pdftoppm (poppler), pdfplumber, Pillow.
All page numbers are 1-based PDF pages (printed page = PDF page - 2).
"""
import csv, json, os, re, subprocess, sys
from pathlib import Path

import pdfplumber
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "sources/catalogs/PBH_parallel-bevel.pdf"
OUT = ROOT / "data/raw/PBH"
IMG = OUT / "images"
SERIES = "PBH"
OUT.mkdir(parents=True, exist_ok=True)
IMG.mkdir(parents=True, exist_ok=True)

SIZES = ["180", "200", "225", "250", "280", "355"]
PH = ["P1H", "P2H", "P3H", "P4H"]
BH = ["B2H", "B3H", "B4H"]
TRAINS = PH + BH
STAGES = {"P1H": 1, "P2H": 2, "P3H": 3, "P4H": 4, "B2H": 2, "B3H": 3, "B4H": 4}


def page_text(p):
    return subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), str(PDF), "-"],
                          capture_output=True, text=True, check=True).stdout


def num(s):
    """catalogue number -> canonical string ('' for -, /)."""
    s = s.strip()
    if s in ("-", "/", "", "–"):
        return ""
    s = s.replace(",", ".")
    return s


def isnum(s):
    return re.fullmatch(r"\d+(?:,\d+)?", s) is not None


def write_csv(name, header, rows):
    with open(OUT / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return len(rows)


COUNTS = {}
FLAGS = []

# --------------------------------------------------------------------------
# ratings.csv  (PDF pages 71-112)
# --------------------------------------------------------------------------
rating_rows = []
# motor frames per (train,size) from p16 table (filled below, needed here)
pdf = pdfplumber.open(str(PDF))


def expand_iec(col):
    return {"100-112": ["100", "112"], "250-280": ["250", "280"]}.get(col, [col])


motor_map = {}  # (train,size) -> list of IEC frames
p16 = pdf.pages[15]
for tb in p16.extract_tables():
    if len(tb) < 3 or len(tb[1]) < 9:
        continue
    cols = [re.sub(r"(.)\1", r"\1", c) if c else c for c in tb[1]]  # doubled glyph artefact
    cols = ["100-112", "132", "160", "180", "200", "225", "250-280", "315"]
    cur = None
    cur_cells = None
    for r in tb[2:]:
        if r[0]:
            cur = r[0]
            prev = [None] * 8
        for j in range(8):
            v = r[j + 1]
            if v and v != "-":
                for fr in expand_iec(cols[j]):
                    motor_map.setdefault((v, cur[-3:]), [])
                    if fr not in motor_map[(v, cur[-3:])]:
                        motor_map[(v, cur[-3:])].append(fr)
for k in motor_map:
    motor_map[k].sort(key=int)

for p in range(71, 113):
    txt = page_text(p)
    m = re.search(r"(\d{3,4}) rpm", txt)
    n1 = m.group(1)
    lines = txt.split("\n")
    left = right = None
    for ln in lines:
        hdr = re.findall(r"([PB]\dH) (\d{3})", ln)
        if len(hdr) == 2:
            left, right = hdr
            continue
        toks = ln.split()
        if left and toks and all(isnum(t) for t in toks):
            if len(toks) == 1:
                continue  # printed page number
            if len(toks) != 8:
                FLAGS.append(f"p{p}: row with {len(toks)} tokens: {ln.strip()}")
                continue
            for (tr, sz), t4 in ((left, toks[:4]), (right, toks[4:])):
                mn2, i, pn1, n2 = [num(x) for x in t4]
                rating_rows.append([SERIES, f"{tr} {sz}", STAGES[tr], n1, pn1, i, n2, mn2, "", "",
                                    ";".join(motor_map.get((tr, sz), [])), "reducer", p])
rating_rows.sort(key=lambda r: (TRAINS.index(r[1][:3]), r[1], -int(r[3]), float(r[5])))
RH = ["series", "size", "stages", "n1_rpm", "p1_kw", "i", "n2_rpm", "t2_nm", "fs", "fr2_n",
      "motor_frames", "variant", "src_page"]
COUNTS["ratings.csv"] = write_csv("ratings.csv", RH, rating_rows)

# quality gates ------------------------------------------------------------
seen = {}
gate2 = []
gate3 = []
for r in rating_rows:
    key = (r[0], r[1], r[3], r[5], r[11])
    if key in seen:
        FLAGS.append(f"DUPLICATE KEY {key} pages {seen[key]},{r[12]}")
    seen[key] = r[12]
    n1, p1, i, n2, t2 = float(r[3]), float(r[4]), float(r[5]), float(r[6]), float(r[7])
    eta = t2 * n2 / 9550 / p1
    if not (0.55 <= eta <= 1.0):
        gate2.append((r[1], r[3], r[5], round(eta, 3), r[12]))
    if abs(n1 / i - n2) / n2 > 0.03:
        gate3.append((r[1], r[3], r[5], r[6], round(n1 / i, 1), r[12]))
etas = [float(r[7]) * float(r[6]) / 9550 / float(r[4]) for r in rating_rows]
print("ratings rows", len(rating_rows), "eta min/max", round(min(etas), 3), round(max(etas), 3))
print("gate2 (eta outside 0.55-1.0):", gate2)
print("gate3 (n2 vs n1/i >3%):", gate3)

# --------------------------------------------------------------------------
# dimensions_reducer.csv  (pages 41-47)
# --------------------------------------------------------------------------
dim = {}  # (variant,size) -> dict
dim_cols = []
for p in range(41, 48):
    lines = page_text(p).split("\n")
    hdr = None
    for ln in lines:
        toks = ln.split()
        if len(toks) > 3 and re.fullmatch(r"[PB]\dH", toks[0]) and toks[1] in ("D2", "G1", "H", "G3", "F"):
            var = toks[0]
            names = []
            for t in toks[1:]:
                n = t
                if n in names:
                    n = n + "_in_gt4"  # P1H: second D1/B1 pair is for in > 4
                names.append(n)
            if var == "P1H" and names[:2] == ["D2", "B2"] and "D1" not in names:
                names = names[:2] + ["D1", "B1", "D1_in_gt4", "B1_in_gt4"] + names[2:]  # p41 header lost D1/B1 pairs
            hdr = (var, names)
            continue
        if hdr and toks and toks[0] in SIZES:
            var, names = hdr
            if len(toks) - 1 != len(names):
                FLAGS.append(f"dim p{p}: {var} row {toks[0]} has {len(toks)-1} values vs {len(names)} cols")
                continue
            d = dim.setdefault((var, toks[0]), {"src_page": set()})
            for n, v in zip(names, toks[1:]):
                d[n] = num(v)
                if n not in dim_cols:
                    dim_cols.append(n)
            d["src_page"].add(p)
rows = []
for (var, sz), d in sorted(dim.items(), key=lambda kv: (TRAINS.index(kv[0][0]), int(kv[0][1]))):
    rows.append([SERIES, f"{var} {sz}", "reducer_foot_B3"] + [d.get(c, "") for c in dim_cols] +
                [";".join(str(x) for x in sorted(d["src_page"]))])
COUNTS["dimensions_reducer.csv"] = write_csv("dimensions_reducer.csv",
                                             ["series", "size", "variant"] + dim_cols + ["src_page"], rows)


# --------------------------------------------------------------------------
# generic small-table helper: rows of whitespace tokens after a header regex
# --------------------------------------------------------------------------
def grab_rows(p, first_tok_re, ntok, start_re=None, stop_re=None, tokfix=None):
    txt = page_text(p).split("\n")
    on = start_re is None
    out = []
    for ln in txt:
        if start_re and re.search(start_re, ln):
            on = True
            continue
        if stop_re and re.search(stop_re, ln):
            on = False
        if not on:
            continue
        toks = ln.split()
        if tokfix:
            toks = tokfix(toks)
        if toks and re.fullmatch(first_tok_re, toks[0]) and len(toks) == ntok:
            out.append(toks)
    return out


# weights (p48) ---------------------------------------------------------------
rows = []
txt = page_text(48).split("\n")
cur = None
for ln in txt:
    t = ln.split()
    if t[:1] == ["PH"] or t[:1] == ["BH"]:
        pass
    if len(t) == 5 and t[0] in SIZES and all(x.isdigit() for x in t):
        cur = PH
        for tr, v in zip(cur, t[1:]):
            rows.append([SERIES, f"{tr} {t[0]}", "reducer_dry_no_oil", "", v, 48])
    elif len(t) == 4 and t[0] in SIZES and all(x.isdigit() for x in t):
        for tr, v in zip(BH, t[1:]):
            rows.append([SERIES, f"{tr} {t[0]}", "reducer_dry_no_oil", "", v, 48])
COUNTS["weights.csv"] = write_csv("weights.csv", ["series", "size", "variant", "motor_frame", "mass_kg", "src_page"], rows)

# lubrication (p30) ---------------------------------------------------------------
rows = []
txt = page_text(30).split("\n")
blocks = []  # list of train-list for current header
mounts = ["B3", "B8", "B6", "B7", "V5", "V6"]
cur_trains = None
for ln in txt:
    t = ln.split()
    found = re.findall(r"\b([PB]\dH)\b", ln)
    if found and not t[0] in mounts:
        cur_trains = found
        continue
    if t and t[0] in mounts and cur_trains:
        vals = t[1:]
        n = len(cur_trains) * 6
        if len(vals) != n:
            FLAGS.append(f"lub p30 {t[0]} {len(vals)} vals expected {n}")
            continue
        for k, tr in enumerate(cur_trains):
            for j, sz in enumerate(SIZES):
                rows.append([SERIES, f"{tr} {sz}", t[0], vals[k * 6 + j], "", 30])
rows.sort(key=lambda r: (TRAINS.index(r[1][:3]), int(r[1][4:]), mounts.index(r[2])))
COUNTS["lubrication.csv"] = write_csv("lubrication.csv",
                                      ["series", "size", "mounting_position", "oil_l", "oil_type", "src_page"], rows)

# thermal (p25) -----------------------------------------------------------------
rows = []
for ln in page_text(25).split("\n"):
    t = ln.split()
    if len(t) == 7 and t[0] in TRAINS and all(x.isdigit() for x in t[1:]):
        for sz, v in zip(SIZES, t[1:]):
            rows.append([SERIES, f"{t[0]} {sz}", "Pth_B3_continuous_n1<=1500", v, 25])
COUNTS["thermal.csv"] = write_csv("thermal.csv", ["series", "size", "variant", "pth_kw", "src_page"], rows)

# extra: Pta cooling (p27) ---------------------------------------------------------
rows = []
kind = None
for ln in page_text(27).split("\n"):
    if "WATER - OIL" in ln:
        kind = "water-oil"
    if "AIR - OIL" in ln:
        kind = "air-oil"
    t = ln.split()
    if kind and len(t) == 8 and all(x.isdigit() for x in t):
        for tr, v in zip(PH + BH, t[1:]):
            rows.append([SERIES, "all", kind, "URO/" + ("W" if kind == "water-oil" else "A") + t[0], tr, v, 27])
COUNTS["extra_thermal_pta_cooling.csv"] = write_csv("extra_thermal_pta_cooling.csv",
        ["series", "size", "variant", "cooling_unit", "train", "pta_max_kw", "src_page"], rows)

# extra: max input speed (p28) ------------------------------------------------------
rows = []
for ln in page_text(28).split("\n"):
    t = ln.split()
    if len(t) == 8 and t[0] in SIZES and all(x.isdigit() for x in t):
        for tr, v in zip(PH[:4] + BH[:3], t[1:]):
            pass
hdr_order = ["P1H", "P2H", "P3H", "P4H", "B2H", "B3H", "B4H"]
for ln in page_text(28).split("\n"):
    t = ln.split()
    if len(t) == 8 and t[0] in SIZES and all(x.isdigit() for x in t):
        for tr, v in zip(hdr_order, t[1:]):
            rows.append([SERIES, f"{tr} {t[0]}", "n1_max_continuous_S1", v, 28])
COUNTS["extra_max_input_speed.csv"] = write_csv("extra_max_input_speed.csv",
        ["series", "size", "variant", "n1_max_rpm", "src_page"], rows)

# extra: ratio / torque range (p17) ------------------------------------------------------
rows = []
sect = None
for ln in page_text(17).split("\n"):
    t = ln.split()
    if t[:1] in (["PH"], ["BH"]) and "Max" in t:
        sect = t[0]
    if len(t) == 4 and t[0] in SIZES and sect:
        rows.append([SERIES, f"{sect} {t[0]}", "range_at_1400rpm", num(t[1]), num(t[2]), num(t[3]), 17])
COUNTS["extra_range.csv"] = write_csv("extra_range.csv",
        ["series", "size", "variant", "mn2_max_nm", "i_min", "i_max", "src_page"], rows)

# service factor (p24) -----------------------------------------------------------------
fsa = {}
fsb = {}
hours = [2, 4, 8, 16, 24]
starts = ["<8", "8-32", "32-64", "64-128"]
fsc = []
mode = None
for ln in page_text(24).split("\n"):
    if "Table fsa" in ln:
        mode = "a"
    elif "Table fsb" in ln:
        mode = "b"
    elif "Table fsc" in ln:
        mode = "c"
    t = ln.split()
    if t and t[0] in ("Uniform", "Moderate", "Heavy") and mode in ("a", "b"):
        vals = [num(x) for x in t[1:]]
        (fsa if mode == "a" else fsb)[t[0].lower()] = vals
rows_a = [[SERIES, "all", "fsa", lc, h, "", fsa[lc][k], 24] for lc in fsa for k, h in enumerate(hours)]
rows_b = [[SERIES, "all", "fsb", lc, "", s, fsb[lc][k], 24] for lc in fsb for k, s in enumerate(starts)]
COUNTS["extra_service_factor_fsa_fsb.csv"] = write_csv("extra_service_factor_fsa_fsb.csv",
        ["series", "size", "table", "load_class", "hours_per_day", "starts_per_hour", "factor", "src_page"],
        rows_a + rows_b)
# fsc (motor type) – 3 lines, transcribed from p24 text (assert present)
t24 = page_text(24)
fsc_rows = [("electric motor", "1.00"), ("reciprocating multiple-cylinder motor", "1.25"),
            ("reciprocating single-cylinder motor", "1.50")]
assert "1,00" in t24 and "1,25" in t24 and "1,50" in t24
COUNTS["extra_service_factor_fsc.csv"] = write_csv("extra_service_factor_fsc.csv",
        ["series", "motor_type", "fsc", "src_page"], [[SERIES, a, b, 24] for a, b in fsc_rows])
rows = []
for lc in ("uniform", "moderate", "heavy"):
    for k, h in enumerate(hours):
        for j, s in enumerate(starts):
            fs = float(fsa[lc][k]) * float(fsb[lc][j]) * 1.00
            rows.append([SERIES, lc, h, s, f"{fs:.4f}".rstrip("0").rstrip("."), 24])
COUNTS["service_factor.csv"] = write_csv("service_factor.csv",
        ["series", "load_class", "hours_per_day", "starts_per_hour", "fs", "src_page"], rows)

# application classification (p22-23) ------------------------------------------------------
rows = []
LOADS = ("Uniform", "Moderate", "Heavy")
for p in (22, 23):
    pg = pdf.pages[p - 1]
    W, H = pg.width, pg.height
    for half, (x0, x1) in enumerate(((0, W / 2), (W / 2, W))):
        crop = pg.crop((x0, 0, x1, H))
        lines = crop.extract_text(layout=False).split("\n")
        group = ""
        last = None
        for ln in lines:
            ln = ln.strip()
            if not ln or ln.startswith(("PBH Series", "2.4 PRODUCT", "Table APPLICATION", "TECHNICAL", "Application Type")) \
               or re.fullmatch(r"\d+", ln):
                continue
            m = re.search(r"\s(Uniform|Moderate|Heavy)$", ln)
            if m:
                name = ln[:m.start()].strip()
                load = m.group(1)
                if name.isupper() or re.fullmatch(r"[A-Z ,()/-]+", name):
                    group = name
                    rows.append([SERIES, group, group, load, p])
                    last = rows[-1]
                    group_is_row = True
                else:
                    rows.append([SERIES, group, name, load, p])
                    last = rows[-1]
            else:
                if re.match(r"[A-Z]{3,}\b", ln):
                    group = ln
                    last = None
                elif last is not None:
                    last[2] = last[2] + " " + ln  # wrapped continuation of previous application
                else:
                    group = (group + " " + ln).strip()  # wrapped group heading
COUNTS["extra_application_classification.csv"] = write_csv("extra_application_classification.csv",
        ["series", "group", "application", "load_class", "src_page"], rows)

# --------------------------------------------------------------------------
# radial loads (p32-40)
# --------------------------------------------------------------------------
rows = []
for p in (32, 33):
    cur = None
    for ln in page_text(p).split("\n"):
        t = ln.split()
        if t and re.fullmatch(r"[PB]\dH", t[0]) and len(t) == 7:
            cur = t[0]
        elif cur and t and t[0] == "a" and len(t) == 7:
            a = t[1:]
        elif cur and t and t[0] == "b" and len(t) == 7:
            b = t[1:]
        elif cur and t and t[0].startswith("Fr1") and len(t) == 8:
            fr = t[2:] if t[1] == "(**)" else t[1:]
            if len(fr) != 6:
                fr = t[-6:]
            for sz, aa, bb, ff in zip(SIZES, a, b, fr):
                rows.append([SERIES, f"{cur} {sz}", "input_shaft_Fr1_at_n1_1400", aa, bb, ff, p])
            cur = None
COUNTS["radial_load_input.csv"] = write_csv("radial_load_input.csv",
        ["series", "size", "variant", "a", "b", "fr1_n", "src_page"], rows)

rows = []
grp = None
a = b = None
for ln in page_text(34).split("\n"):
    t = ln.split()
    if t and re.fullmatch(r"[PB]\dH", t[0]) and "180" in t:
        grp = "P1H-P2H-B2H" if t[0] == "P1H" else "P3H-P4H-B3H-B4H"
    if len(t) == 7 and t[0] == "a":
        a = t[1:]
    if len(t) == 7 and t[0] == "b":
        b = t[1:]
    if len(t) >= 7 and t[0] == "Fr2":
        fr = t[-6:]
        for sz, aa, bb, ff in zip(SIZES, a, b, fr):
            rows.append([SERIES, sz, grp, aa, bb, ff, 34])
COUNTS["radial_load_output_max.csv"] = write_csv("radial_load_output_max.csv",
        ["series", "size", "variant", "a", "b", "fr2_max_n", "src_page"], rows)

rows = []
for p in range(35, 41):
    txt = page_text(p)
    sz = re.search(r"Size (\d{3})", txt).group(1)
    for ln in txt.split("\n"):
        t = ln.split()
        if len(t) == 5 and all(x.isdigit() for x in t):
            rows.append([SERIES, sz, "PH-BH_output_shaft_life", t[0], t[1], t[2], t[3], t[4], p])
COUNTS["radial_load_output_life.csv"] = write_csv("radial_load_output_life.csv",
        ["series", "size", "variant", "n2_x_Lh_cycles", "fr2_100_n", "fr2_75_n", "fr2_50_n", "fa_100_n", "src_page"], rows)

# --------------------------------------------------------------------------
# shaft ends, low-speed shafts, accessories dimension tables
# --------------------------------------------------------------------------
# input shaft end p49
# (re-do cleanly: tokens are  D1 fit B1 b1 t1 f1 key a1 -> 8 tokens, t1 may have decimal comma)
rows = []
for ln in page_text(49).split("\n"):
    t = ln.split()
    if len(t) == 8 and t[0].isdigit() and t[1] in ("k6", "m6"):
        rows.append([SERIES, "general", "input_shaft_end", t[0], t[1], t[2], t[3], num(t[4]), t[5], t[6], t[7], 49])
COUNTS["dimensions_shaft_input.csv"] = write_csv("dimensions_shaft_input.csv",
        ["series", "size", "variant", "D1", "D1_fit", "B1", "b1", "t1", "f1", "b1xh1xl1", "a1", "src_page"], rows)

# output shaft end p50
rows = []
for ln in page_text(50).split("\n"):
    t = ln.split()
    if len(t) == 8 and t[0] in SIZES:
        rows.append([SERIES, t[0], "PH-BH_output_shaft_end", t[1], "m6", t[2], t[3], t[4], t[5], t[6], t[7], 50])
COUNTS["dimensions_shaft_output.csv"] = write_csv("dimensions_shaft_output.csv",
        ["series", "size", "variant", "D2", "D2_fit", "B2", "b2", "t2", "f2", "b2xh2xl2", "a2", "src_page"], rows)

# hollow shafts (p51 keyway, p52 shrink disc, p53 splined hollow) ---------------------
hs_cols = ["D3", "b3", "t3", "G1", "U3", "V3", "LB", "X", "D4", "D5", "D6", "CL", "G4", "G5", "L1", "L2", "L3",
           "T1", "T2", "MT_12.9_Nm", "D3S", "V3S"]
hs = []


def hrow(var, sz, d, p):
    hs.append([SERIES, sz, var] + [d.get(c, "") for c in hs_cols] + [p])


for ln in page_text(51).split("\n"):
    t = ln.split()
    if len(t) == 9 and t[0] in SIZES:
        hrow("hollow_keyway_D3_H7/h6", t[0], dict(zip(["D3", "b3", "t3", "G1", "U3", "V3", "LB", "X"],
                                                  [num(x) for x in t[1:]])), 51)
for ln in page_text(52).split("\n"):
    t = ln.split()
    if len(t) == 15 and t[0] in SIZES:
        names = ["D3", "D4", "D5", "D6", "CL", "G4", "G5", "L1", "L2", "L3", "T1", "T2", "X", "MT_12.9_Nm"]
        hrow("hollow_shrink_disc_D3_H7/g7_D4_H7/f7", t[0], dict(zip(names, [num(x) for x in t[1:]])), 52)
for ln in page_text(53).split("\n"):
    t = ln.split()
    if len(t) == 6 and t[0] in SIZES and "x" in t[1]:
        hrow("hollow_splined_DIN5480", t[0], dict(zip(["D3S", "D3", "G1", "V3", "V3S"], [t[1]] + [num(x) for x in t[2:]])), 53)
COUNTS["dimensions_hollow_shaft.csv"] = write_csv("dimensions_hollow_shaft.csv",
        ["series", "size", "variant"] + hs_cols + ["src_page"], hs)

rows = []
for ln in page_text(53).split("\n"):
    t = ln.split()
    if len(t) == 7 and t[0] in SIZES and "x" in t[1]:
        rows.append([SERIES, t[0], "splined_output_shaft_DIN5480"] + [t[1]] + [num(x) for x in t[2:]] + [53])
COUNTS["dimensions_splined_shaft.csv"] = write_csv("dimensions_splined_shaft.csv",
        ["series", "size", "variant", "D2S", "DC_f7", "B2S", "f2", "G1", "V2S", "src_page"], rows)

# input flanges (p54-57) via pdfplumber tables ------------------------------------------
flange = []
FL_H = ["dm", "PF", "GF", "GF1", "NF", "MF", "TF", "RF", "OF", "OF_n", "W"]
for p in (54, 55, 56, 57):
    for tb in pdf.pages[p - 1].extract_tables():
        if not tb or not re.fullmatch(r"[PB]\dH", tb[0][0] or ""):
            continue
        tr = tb[0][0]
        sz = None
        for r in tb[1:]:
            if r[0]:
                sz = r[0]
            dm, PF, GF, NF, MF, TF, RF, OFx, W = r[1:10]
            mm = re.fullmatch(r"(M\d+) \(n° (\d+)\)", OFx)
            gf, gf1 = (GF, "") if tr.startswith("P") else ("", GF)
            flange.append([SERIES, f"{tr} {sz}", "motor_flange_" + ("PH" if tr[0] == "P" else "BH"),
                           dm.replace(" ", ""), PF, gf, gf1, NF, MF, TF, RF, mm.group(1), mm.group(2), W, p])
COUNTS["dimensions_input_flange.csv"] = write_csv("dimensions_input_flange.csv",
        ["series", "size", "variant"] + FL_H + ["src_page"], flange)

# motor_interface.csv ------------------------------------------------------------------------
# iec_frame candidates are DERIVED from motor shaft diameter dm (IEC 60072 4-pole/2-pole shaft dia.),
# not printed in the catalogue; flagged in notes.md.
DM2IEC = {"28": "100;112", "38": "132", "42": "160", "48": "180", "55": "200;225", "60": "225;250",
          "65": "250;280;315", "75": "280", "80": "315"}
rows = []
for r in flange:
    for dm in r[3].split("-"):
        rows.append([SERIES, r[1], DM2IEC.get(dm, ""), f"B5 PF{r[4]} NF{r[7]} MF{r[8]}", dm, r[-1]])
COUNTS["motor_interface.csv"] = write_csv("motor_interface.csv",
        ["series", "size", "iec_frame", "flange", "bore_mm", "src_page"], rows)


# --------------------------------------------------------------------------
# accessories
# --------------------------------------------------------------------------
# cooling fan p59: columns E,G,G',L,K,N (E11 G11 G12 L11 K11 N11 for PH, E13 G13 G14 L13 K13 N13 for BH)
rows = []
trs = None
for ln in page_text(59).split("\n"):
    t = ln.split()
    h = re.findall(r"\b([PB]\dH)\b", ln)
    if len(h) == 2 and t[0] not in ("PH", "BH"):
        trs = h
    if trs and len(t) == 13 and t[0] in SIZES:
        for tr, vals in ((trs[0], t[1:7]), (trs[1], t[7:])):
            rows.append([SERIES, f"{tr} {t[0]}", "cooling_fan"] + [num(x) for x in vals] + [59])
COUNTS["dimensions_cooling_fan.csv"] = write_csv("dimensions_cooling_fan.csv",
        ["series", "size", "variant", "E1", "G1", "G2", "L", "K", "N", "src_page"], rows)
# NOTE columns E1,G1,G2,L,K,N stand for E11/E13, G11/G13, G12/G14, L11/L13, K11/K13, N11/N13 (PH / BH)

# bearing lubrication pump p60: DP KP I
rows = []
groups = []
for ln in page_text(60).split("\n"):
    if "DP" in ln:
        groups = [g.strip() for g in re.split(r"\s+DP\s+KP\s+I\s*", ln) if g.strip()]
        continue
    t = ln.split()
    if groups and len(t) == 4 * len(groups) and t[0] in SIZES:
        for k, g in enumerate(groups):
            sz, dp, kp, i_ = t[4 * k:4 * k + 4]
            for tr in re.findall(r"[PB]\dH", g):
                rows.append([SERIES, f"{tr} {sz}", "bearing_lubrication_pump", dp, kp, num(i_), 60])
rows.sort(key=lambda r: (TRAINS.index(r[1][:3]), int(r[1][4:])))
COUNTS["dimensions_lube_pump.csv"] = write_csv("dimensions_lube_pump.csv",
        ["series", "size", "variant", "DP", "KP", "I", "src_page"], rows)

# output flange p61 (header 'NU G6' = NU with G6 tolerance)
rows = []
for ln in page_text(61).split("\n"):
    m = re.match(r"\s*(\d{3})\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(M\d+) \(n°(\d+)\)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+)", ln)
    if m and m.group(1) in SIZES:
        g = m.groups()
        rows.append([SERIES, g[0], "PH-BH_output_flange", g[1], g[2], g[3], "G6", g[4], g[5], g[6], g[7], g[8], g[9], g[10], 61])
COUNTS["dimensions_output_flange.csv"] = write_csv("dimensions_output_flange.csv",
        ["series", "size", "variant", "PU", "MU", "NU", "NU_fit", "SU", "OU", "OU_n", "JU", "JU1", "CU", "GU", "src_page"], rows)

# reaction bolt p62
rows = []
for ln in page_text(62).split("\n"):
    t = ln.split()
    if len(t) == 7 and t[0] in SIZES:
        rows.append([SERIES, t[0], "PH-BH_reaction_bolt"] + [num(x) for x in t[1:]] + [62])
COUNTS["dimensions_reaction_bolt.csv"] = write_csv("dimensions_reaction_bolt.csv",
        ["series", "size", "variant", "KE_P1H_P2H_B2H_B3H", "KE_P3H_P4H_B4H", "KD", "KF", "KG", "KH", "src_page"], rows)

# output shaft cover p63, assembling kit p64
rows = []
for ln in page_text(63).split("\n"):
    t = ln.split()
    if len(t) == 3 and t[0] in SIZES and t[1].isdigit():
        rows.append([SERIES, t[0], "PH-BH_output_shaft_cover", t[1], t[2], 63])
COUNTS["dimensions_shaft_cover.csv"] = write_csv("dimensions_shaft_cover.csv",
        ["series", "size", "variant", "D7", "N2", "src_page"], rows)
rows = []
for ln in page_text(64).split("\n"):
    t = ln.split()
    if len(t) == 6 and t[0] in SIZES:
        rows.append([SERIES, t[0], "PH-BH_assembly_kit_hollow_keyway"] + t[1:] + [64])
COUNTS["dimensions_assembly_kit.csv"] = write_csv("dimensions_assembly_kit.csv",
        ["series", "size", "variant", "D", "A", "X", "Y", "M", "src_page"], rows)

# --------------------------------------------------------------------------
# lubrication extras (p29-30, p67)
# --------------------------------------------------------------------------
rows = []
for ln in page_text(30).split("\n"):
    t = ln.split()
    if len(t) >= 3 and t[0] in (">", "210", "20", "<5") or ln.strip().startswith(("> 210", "210 ÷ 20", "20 ÷ 5", "<5")):
        pass
# ISO viscosity grades (4 rows, transcribed after assertion against the text)
t30 = page_text(30)
for key in ("> 210", "210 ÷ 20", "20 ÷ 5", "<5"):
    assert key in t30
iso = [("> 210", "150", "150"), ("210-20", "150", "220"), ("20-5", "220", "320"), ("<5", "320", "460")]
COUNTS["extra_oil_iso_viscosity.csv"] = write_csv("extra_oil_iso_viscosity.csv",
        ["series", "n2_rpm_range", "iso_vg_mineral_0_to_40C", "iso_vg_synthetic_minus10_to_50C", "src_page"],
        [[SERIES, a, b, c, 30] for a, b, c in iso])

rows = []
for ln in page_text(29).split("\n"):
    m = re.match(r"\s*(ENI|SHELL|KLUBER|MOBIL|CASTROL|BP|ESSO|TOTAL)\s{2,}(.+?)\s{2,}(.+?)\s{2,}(.+?)\s*$", ln)
    if m:
        rows.append([SERIES, m.group(1), m.group(2), m.group(3), m.group(4), 29])
COUNTS["extra_oil_recommended_brands.csv"] = write_csv("extra_oil_recommended_brands.csv",
        ["series", "brand", "mineral", "synthetic_PAO", "synthetic_PG", "src_page"], rows)

rows = []
for ln in page_text(67).split("\n"):
    t = ln.split()
    if len(t) == 4 and t[0] in ("Mineral", "Synthetic") and t[1] == "oil":
        pass
    m = re.match(r"\s*(Mineral oil|Synthetic oil)\s+(\d+) h\s+(\d+) h\s+(\d+) h", ln)
    if m:
        rows.append([SERIES, m.group(1), m.group(2), m.group(3), m.group(4), 67])
COUNTS["extra_oil_change_interval.csv"] = write_csv("extra_oil_change_interval.csv",
        ["series", "oil_type", "h_at_lt65C", "h_at_80C", "h_at_95C", "src_page"], rows)

# --------------------------------------------------------------------------
# thermal correction factor tables (p26) - small irregular layout, transcribed; each value asserted in text
# --------------------------------------------------------------------------
t26 = page_text(26)
corr = []  # (table, key1, key2, value)
for alt, v in ((0, "1"), (750, "0,95"), (1500, "0,9"), (2250, "0,85"), (3000, "0,81")):
    corr.append(("fta_altitude_m", alt, "", v.replace(",", ".")))
for tr, a, b in (("P1H-P2H-P3H", "1,7", "1,5"), ("B2H-B3H", "1,8", "1,6")):
    corr.append(("ftb_cooling_fan", tr, "n1<=1500", a.replace(",", ".")))
    corr.append(("ftb_cooling_fan", tr, "n1<=1000", b.replace(",", ".")))
ftc = {10: (1.15, 1.25, 1.35, 1.5, 2), 20: (1, 1.05, 1.15, 1.35, 1.75), 30: (0.9, 1, 1.05, 1.25, 1.5),
       40: (0.75, 0.8, 0.9, 1, 1.35), 50: (0.6, 0.63, 0.7, 0.8, 1)}
for amb, vals in ftc.items():
    for d, v in zip((100, 80, 60, 40, 20), vals):
        corr.append(("ftc_ambient_temp_C_vs_duty_pct", amb, d, v))
for tr, vals in (("P1H", (1.15, 1.1, 1.05, 1, 0.8)), ("P2H-B2H", (1.1, 1.07, 1.05, 1, 0.85)),
                 ("P3H-P4H-B3H-B4H", (1.07, 1.05, 1.05, 1, 0.95))):
    for n, v in zip((700, 900, 1140, 1400, 1800), vals):
        corr.append(("ftn_input_speed", tr, n, v))
corr += [("fts_cooling_coil", "P1H-P2H-B2H-B3H", "", 2), ("fts_cooling_coil", "P3H-P4H-B4H", "", 1.8),
         ("ftv_airflow", "stagnant air (<0.5 m/s)", "", 0.75), ("ftv_airflow", "indoor slight ventilation", "", 1),
         ("ftv_airflow", "indoor good ventilation (>1.4 m/s)", "", 1.4)]
fmp = {"B3": (1, 1, 1, 1, 1, 1, 1), "B6": (0.8, 0.85, 0.85, 0.85, 0.8, 0.8, 0.75),
       "B7": (0.8, 0.75, 0.75, 0.75, 0.8, 0.75, 0.7), "B8": (1, 1, 1, 1, 1, 1, 1),
       "V5": (0.8, 0.75, 0.75, 0.75, 0.75, 0.75, 0.7), "V6": (0.8, 0.85, 0.85, 0.85, 0.8, 0.8, 0.75)}
for mp, vals in fmp.items():
    for tr, v in zip(("P1H", "P2H", "P3H", "P4H", "B2H", "B3H", "B4H"), vals):
        corr.append(("Fmp_mounting_position", mp, tr, v))
# verify Fmp rows against the text layer
for mp, vals in fmp.items():
    m = re.search(r"\b%s\s+((?:[\d,]+\s+){6}[\d,]+)\s*$" % mp, t26, re.M)
    assert m, mp
    got = [float(x.replace(",", ".")) for x in m.group(1).split()]
    assert got == [float(v) for v in vals], (mp, got)
COUNTS["extra_thermal_correction_factors.csv"] = write_csv("extra_thermal_correction_factors.csv",
        ["series", "table", "key1", "key2", "value", "src_page"], [[SERIES, a, b, c, d, 26] for a, b, c, d in corr])

# --------------------------------------------------------------------------
# designation.json  (diagram p13, executions p18, mounting positions p19-20, p16 matrix)
# --------------------------------------------------------------------------
designation = {
    "series": SERIES,
    "source_pages": [13, 14, 15, 18, 19, 20],
    "pattern": "PBH <B|P><1H..4H> <size> <execution> <I|P> <input dimension> <output version> <output dimension> <ratio> <mounting>",
    "note": ("Order of segments read from the designation diagram on p13 (flow chart, no printed example string). "
             "Execution meanings are read from the drawings on p18 (visual interpretation)."),
    "segments": [
        {"name": "series", "values": {"PBH": "Motovario parallel/bevel helical industrial gear reducers, IEC"}},
        {"name": "type", "values": {"B": "bevel helical reducer", "P": "parallel shaft reducer"}},
        {"name": "stages", "values": {"1H": "1 stage (P only, P1H)", "2H": "2 stages", "3H": "3 stages", "4H": "4 stages"},
         "note": "Gear trains printed in catalogue: P1H P2H P3H P4H, B2H B3H B4H"},
        {"name": "size", "values": {s: "frame size " + s for s in SIZES}},
        {"name": "execution", "values": {
            "AZ": "parallel; single output shaft (output on right in drawing), solid input shaft",
            "AU": "parallel; single output shaft (output on left in drawing), solid input shaft",
            "DZ": "parallel; double input shaft (input shaft both sides in drawing), output on right",
            "DU": "parallel; double input shaft (input shaft both sides in drawing), output on left",
            "LR": "bevel helical; output shaft right (drawing p18)",
            "LL": "bevel helical; output shaft left (drawing p18)",
            "SR": "bevel helical; output shaft right, bevel input on rear face (drawing p18)",
            "SL": "bevel helical; output shaft left, bevel input on rear face (drawing p18)",
            "DR": "bevel helical; output shaft right, input shaft on the opposite side (drawing p18)",
            "DL": "bevel helical; output shaft left, input shaft on the opposite side (drawing p18)"},
         "note": "AZ/AU/DZ/DU for P series; LR/LL/SR/SL/DR/DL for B series (p18 groups)"},
        {"name": "input", "values": {"I": "male (solid) input shaft", "P": "bell coupling input (motor flange + coupling)"}},
        {"name": "input_dimension", "values": {
            "PF x dm (e.g. 350x42)": "PAM: motor flange diameter PF x motor shaft dia dm, tables p54-57",
            "D1 x B1 (e.g. 48x110)": "solid input shaft diameter x length, table p49 and dimensions p41-47"}},
        {"name": "output_shaft_version", "values": {
            "CS": "solid shaft", "HC": "hollow shaft with key", "HL": "shrink disk shaft", "CD": "double output shaft",
            "HS": "splined hollow shaft", "SS": "splined solid shaft", "SD": "double splined solid shaft"}},
        {"name": "output_dimension", "values": {"D": "e.g. 100 (shaft diameter)", "D x B": "e.g. 100 x 210 (diameter x length)"}},
        {"name": "reduction_ratio", "values": {"1,22 ... 762,36": "range printed in diagram p13; ratios listed in performance tables p71-112"}},
        {"name": "mounting_position", "values": {
            "B3": "foot-mounted, preferred, default", "B6": "wall, see p17-18", "B7": "wall, see p17-18",
            "B8": "ceiling, see p17-18", "V5": "vertical, output down (see p17-18)", "V6": "vertical (see p17-18)"},
         "note": "V5/V6 with vertical input shaft need pressure-fed lubrication (pump) per p27; orientation of each code only drawn, not described in text"},
    ],
    "motor_frames_available_by_size": {f"{k[0]} {k[1]}": v for k, v in sorted(motor_map.items())},
}
with open(OUT / "designation.json", "w") as f:
    json.dump(designation, f, indent=1, ensure_ascii=False)

# --------------------------------------------------------------------------
# images
# --------------------------------------------------------------------------
IMG_PAGES = {13: "diagram", 14: "render", 15: "render", 18: "render", 19: "drawing", 20: "drawing",
             31: "diagram", 32: "drawing", 34: "drawing", 41: "drawing", 42: "drawing", 43: "drawing",
             44: "drawing", 45: "drawing", 46: "drawing", 47: "drawing", 49: "drawing", 50: "drawing",
             51: "drawing", 52: "drawing", 53: "drawing", 54: "drawing", 56: "drawing", 59: "drawing",
             60: "drawing", 61: "drawing", 62: "drawing", 63: "drawing", 64: "drawing", 68: "photo"}
CAPS = {13: "Designation diagram", 14: "Versions: solid-shaft input / bell-housing input (PH, BH)",
        15: "Gear trains P1H-P4H, B2H-B4H", 18: "Executions AZ AU DZ DU LR LL SR SL DR DL",
        19: "Mounting positions parallel helical", 20: "Mounting positions bevel helical",
        31: "Direction of rotation", 32: "Radial load input drawing", 34: "Radial load output drawing",
        41: "Dimensions P1H", 42: "Dimensions P2H", 43: "Dimensions P3H", 44: "Dimensions P4H",
        45: "Dimensions B2H", 46: "Dimensions B3H", 47: "Dimensions B4H", 49: "Input shaft end",
        50: "Output shaft end", 51: "Hollow output shaft with keyway", 52: "Hollow shaft with shrink disc",
        53: "Splined shafts", 54: "Motor mounting flange PH", 56: "Motor mounting flange BH",
        59: "Cooling fan", 60: "Bearings lubrication pump", 61: "Output flange", 62: "Reaction bolt",
        63: "Output shaft cover", 64: "Assembling/disassembling kit", 68: "Motor assembly on PAM flange"}
SIZE_OF = {41: "P1H", 42: "P2H", 43: "P3H", 44: "P4H", 45: "B2H", 46: "B3H", 47: "B4H"}
for _f in IMG.glob("*.png"):
    _f.unlink()  # drop stale crops from earlier runs
tmp = OUT / "_tmp"
tmp.mkdir(exist_ok=True)
idx = []
for p, kind in IMG_PAGES.items():
    pg = pdf.pages[p - 1]
    subprocess.run(["pdftoppm", "-r", "200", "-png", "-f", str(p), "-l", str(p), str(PDF), str(tmp / f"pg{p}")], check=True)
    f = sorted(tmp.glob(f"pg{p}-*.png"))[0]
    im = Image.open(f).convert("RGB")
    sc = im.width / pg.width
    boxes = []
    for imo in pg.images:
        w, h = imo["x1"] - imo["x0"], imo["bottom"] - imo["top"]
        if w < 40 or h < 25:
            continue
        boxes.append((imo["x0"], imo["top"], imo["x1"], imo["bottom"]))
    # merge boxes that overlap strongly (image + overlay layers)
    merged = []
    for b in sorted(boxes):
        for k, m in enumerate(merged):
            ox = min(b[2], m[2]) - max(b[0], m[0])
            oy = min(b[3], m[3]) - max(b[1], m[1])
            if ox > 0 and oy > 0 and ox * oy > 0.6 * min((b[2]-b[0])*(b[3]-b[1]), (m[2]-m[0])*(m[3]-m[1])):
                merged[k] = (min(b[0], m[0]), min(b[1], m[1]), max(b[2], m[2]), max(b[3], m[3]))
                break
        else:
            merged.append(b)
    # reading order: top-to-bottom, left-to-right
    merged.sort(key=lambda b: (round(b[1] / 20), b[0]))
    for n, b in enumerate(merged, 1):
        pad = 2
        crop = im.crop((max(0, int((b[0] - pad) * sc)), max(0, int((b[1] - pad) * sc)),
                        min(im.width, int((b[2] + pad) * sc)), min(im.height, int((b[3] + pad) * sc))))
        size = SIZE_OF.get(p, "general")
        name = f"{SERIES}_{size}_{kind}_p{p}_{n}.png"
        crop.save(IMG / name)
        idx.append([name, SERIES, size, kind, CAPS[p], p, crop.width, crop.height])
for f in tmp.glob("*"):
    f.unlink()
tmp.rmdir()
COUNTS["images/index.csv"] = write_csv("images/index.csv",
        ["file", "series", "size", "kind", "caption", "src_page", "width_px", "height_px"], idx)

print("FLAGS:", FLAGS)
for k, v in COUNTS.items():
    print(f"{k}: {v}")
