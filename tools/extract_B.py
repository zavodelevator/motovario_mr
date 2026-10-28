#!/usr/bin/env python3
"""Extractor for Motovario B series (helical-bevel, IEC) technical catalogue.

Source : sources/catalogs/B_helical-bevel.pdf  (188 pages, 1-based PDF index; printed page = PDF page - 2)
Output : data/raw/B/*.csv, designation.json, images/  (see docs/DATA_SCHEMA.md)

Run:  python3 tools/extract_B.py [--no-images]
Needs: pdfplumber, pdftotext/pdftoppm (poppler), Pillow, numpy.
Nothing is invented: every value is read from the text layer / vector tables of the PDF,
except service_factor.csv which is measured from the raster chart on PDF p14 (see notes.md).
"""
import csv, json, os, re, subprocess, sys, collections
import pdfplumber

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, 'sources/catalogs/B_helical-bevel.pdf')
OUT = os.path.join(ROOT, 'data/raw/B')
os.makedirs(OUT, exist_ok=True)
SERIES = 'B'
pdf = pdfplumber.open(PDF)


# ----------------------------------------------------------------- helpers
def num(s):
    """'12,5' -> '12.5'; '/' '-' '' None -> ''."""
    if s is None:
        return ''
    s = str(s).strip()
    if s in ('/', '-', '–', ''):
        return ''
    if re.fullmatch(r'-?\d+,\d+', s):
        return s.replace(',', '.')
    return s


def clean(s):
    return re.sub(r'\s+', ' ', str(s)).strip() if s is not None else ''


def undouble_token(t):
    if len(t) % 2 == 0 and len(t) >= 2 and t[0::2] == t[1::2]:
        return t[0::2]
    return t


def hdr(s):
    """Header cells in this PDF have every glyph doubled (fake bold). Undo per token."""
    if s is None:
        return ''
    toks = str(s).split()
    out = ' '.join(undouble_token(t) for t in toks)
    return out.replace('--', '-')


def canon(label):
    """Printed label -> canonical size (BA42, B063).  CBA42/IBA42 -> BA42, CB063/IB063 -> B063, A42 -> BA42, 063 -> B063."""
    s = clean(label)
    m = re.fullmatch(r'(?:CB|IB|PB|B)?A?\s?(\d{2})', s)
    if re.fullmatch(r'(CBA|IBA|BA|A)\d{2}', s):
        return 'BA' + s[-2:]
    if re.fullmatch(r'(CB|IB|PB|B)?\d{3}', s):
        return 'B' + s[-3:]
    return s


def expand_sizes(label):
    """'BA52/BA53' 'A52 A53 A73' 'BA52-BA53' 'BA72/A73' -> list of canonical sizes."""
    s = clean(label)
    toks = [t for t in re.split(r'[\s/\-]+', s) if t]
    return [canon(t) for t in toks]


def table_rows(page, k):
    return pdf.pages[page - 1].find_tables()[k].extract()


def split_star(cell):
    """'223\\n*246' -> ('223','246'); '262*\\n295' (misplaced asterisk, p42) -> ('262','295'); '/' -> ('','')"""
    if cell is None:
        return '', ''
    parts = [p for p in str(cell).split('\n') if p.strip()]
    vals = [num(p.replace('*', '').strip()) for p in parts]
    base = vals[0] if vals else ''
    star = vals[1] if len(vals) > 1 else ''
    return base, star


class Writer:
    files = {}

    @classmethod
    def write(cls, name, header, rows):
        path = os.path.join(OUT, name)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(header)
            for r in rows:
                w.writerow([r.get(h, '') for h in header] if isinstance(r, dict) else r)
        cls.files[name] = len(rows)
        print('%-42s %6d rows' % (name, len(rows)))


def fwrite(name, rows, lead, cols, tail=('src_page',)):
    header = list(lead) + list(cols) + list(tail)
    Writer.write(name, header, rows)


# ----------------------------------------------------------------- 1. ratings
NUM = r'[0-9]+(?:[.,][0-9]+)?'
ROW_GM = re.compile(r'^\s*(%s)\s+(%s)\s+(%s)\s+(%s)\s+(\S+)\s+(\S+)\s+(\d)\s+(\S+)\s+(\S+)\s*$' % (NUM, NUM, NUM, NUM))
ROW_RED = re.compile(r'^\s*(%s)\s+(%s)\s+(%s)\s+(%s)\s+(%s)\s+(\S+)\s+(\S+)\s*$' % (NUM, NUM, NUM, NUM, NUM))
KW = re.compile(r'^\s*(%s)\s*kW\s*$' % NUM)
SIZE_HDR = re.compile(r'^\s+(I?BA?\d{2,3})\s*$')
POLE_N1 = {'2': 2800, '4': 1400, '6': 900}  # nominal speed by pole count (catalogue gives poles only)
STAGES = {'BA42': 2, 'BA52': 2, 'BA72': 2, 'BA53': 3, 'BA73': 3}  # p16: BA.2 / BA.3 ; B..3 stages


def stages_of(size):
    if size in STAGES:
        return STAGES[size]
    return 3 if size.startswith('B0') or size.startswith('B1') else ''


def ptext(p):
    return subprocess.run(['pdftotext', '-layout', '-f', str(p), '-l', str(p), PDF, '-'],
                          capture_output=True, text=True).stdout


def parse_ratings():
    rows = []
    unparsed = []
    # 5.1 geared motors: PDF 69..135
    kw = None
    for p in range(69, 136):
        for line in ptext(p).splitlines():
            m = KW.match(line)
            if m:
                kw = num(m.group(1))
                continue
            m = ROW_GM.match(line)
            if m:
                n2, M2, fs, i, red, mot, pole, fa, fb = m.groups()
                frames = ';'.join(dict.fromkeys(re.findall(r'\d+', mot)))
                rows.append(dict(series=SERIES, size=red, stages=stages_of(red), n1_rpm=POLE_N1[pole], p1_kw=kw,
                                 i=num(i), n2_rpm=num(n2), t2_nm=num(M2), fs=num(fs), fr2_n=num(fa),
                                 motor_frames=frames, variant='gearmotor', src_page=p,
                                 fr2_c_n=num(fb), fr1_n='', motor_size=mot, poles=pole,
                                 n1_implied_rpm=round(float(num(n2)) * float(num(i)))))
            elif re.match(r'^\s*\d', line) and len(line.split()) > 4 and 'CATALOGUE' not in line:
                unparsed.append((p, line))
    # 5.2-5.7 reducers: PDF 136..183, section n1 from title
    size = None
    for p in range(136, 184):
        txt = ptext(p)
        m = re.search(r'IB/IBA GEAR REDUCER - (\d+) rpm', txt)
        n1 = int(m.group(1))
        for line in txt.splitlines():
            ms = SIZE_HDR.match(line)
            if ms:
                size = ms.group(1)
                continue
            m = ROW_RED.match(line)
            if m:
                Mn2, i, pn1, n2, fr1, fa, fb = m.groups()
                cs = canon(size)
                rows.append(dict(series=SERIES, size=cs, stages=stages_of(cs), n1_rpm=n1, p1_kw=num(pn1),
                                 i=num(i), n2_rpm=num(n2), t2_nm=num(Mn2), fs='', fr2_n=num(fa),
                                 motor_frames='', variant='reducer', src_page=p,
                                 fr2_c_n=num(fb), fr1_n=num(fr1), motor_size='', poles='',
                                 n1_implied_rpm='', printed_size=size))
            elif re.match(r'^\s*\d', line) and len(line.split()) > 4 and 'CATALOGUE' not in line:
                unparsed.append((p, line))
    for r in rows:
        r.setdefault('printed_size', r['size'])
    return rows, unparsed


# ----------------------------------------------------------------- 2. dimension tables
def parse_main_table(rows, page, variant_of, lead_cols, merge_cols=None):
    """Generic: first col = size label (None => continuation, inherit non-empty cells)."""
    header = [hdr(c) for c in rows[0]]
    out = []
    cur = None
    prev = None
    for r in rows[1:]:
        label = r[0]
        if label:
            cur = [clean(x) for x in label.split('\n')]
            prev = None
        vals = []
        for j, c in enumerate(r):
            if j == 0:
                vals.append(None)
            else:
                vals.append(c)
        if prev is not None:
            vals = [v if (v is not None and str(v).strip() != '') else prev[j] for j, v in enumerate(vals)]
            # continuation rows only override cells that are present
        prev = vals
        for lab in cur:
            d = {'series': SERIES, 'size': canon(lab), 'variant': variant_of(lab), 'src_page': page}
            for j, c in enumerate(vals):
                if j == 0 or not header[j]:
                    continue
                d[header[j]] = num(c)
            out.append(d)
    return out, header


def main():
    skip_images = '--no-images' in sys.argv

    # ---------------- ratings
    rows, unparsed = parse_ratings()
    cols = ['series', 'size', 'stages', 'n1_rpm', 'p1_kw', 'i', 'n2_rpm', 't2_nm', 'fs', 'fr2_n', 'motor_frames',
            'variant', 'src_page', 'fr2_c_n', 'fr1_n', 'motor_size', 'poles', 'n1_implied_rpm', 'printed_size']
    Writer.write('ratings.csv', cols, rows)
    sanity = ratings_sanity(rows)
    if unparsed:
        print('UNPARSED data-like lines:', len(unparsed))
        for u in unparsed[:10]:
            print(u)

    # ---------------- motor flange availability (-> motor_interface.csv)
    build_motor_interface()

    # ---------------- dimensions
    build_dimensions()

    # ---------------- weights, lubrication, thermal, radial, service factor, extras, motors
    build_weights()
    build_lubrication()
    build_thermal_radial_extra()
    build_service_factor()
    build_motors()
    write_designation()
    if not skip_images:
        build_images()
    json.dump({'sanity': sanity, 'files': Writer.files}, open(os.path.join('/tmp', 'extract_B_summary.json'), 'w'), indent=1,
              default=str)


# ----------------------------------------------------------------- sanity
def ratings_sanity(rows):
    eff_flags, n2_flags = [], []
    dup = collections.Counter()
    for r in rows:
        p1, n2, t2, i, n1 = (float(r['p1_kw']), float(r['n2_rpm']), float(r['t2_nm']), float(r['i']), r['n1_rpm'])
        eta = t2 * n2 / (9550 * p1)
        r['_eta'] = eta
        if not (0.55 <= eta <= 1.0):
            eff_flags.append((r['variant'], r['size'], r['p1_kw'], r['i'], round(eta, 3), r['src_page']))
        dev = abs(n2 - n1 / i) / (n1 / i)
        if dev > 0.03:
            n2_flags.append((r['variant'], r['size'], n1, r['i'], r['n2_rpm'], round(dev, 3), r['src_page']))
        dup[(r['size'], r['n1_rpm'], r['i'], r['variant'])] += 1
    dups = {k: v for k, v in dup.items() if v > 1}
    dup2 = collections.Counter((r['size'], r['n1_rpm'], r['i'], r['variant'], r['p1_kw'], r['motor_size']) for r in rows)
    dups2 = {k: v for k, v in dup2.items() if v > 1}
    print('efficiency flags', len(eff_flags), 'n2 flags', len(n2_flags), 'dup keys (spec key)', len(dups),
          'dup keys incl p1_kw+motor_size', len(dups2))
    return dict(eff_flags=eff_flags, n2_flags=n2_flags, dups=len(dups), dups2=len(dups2), dup_examples=list(dups.items())[:5],
                dup2_examples=list(dups2.items())[:5])


# ----------------------------------------------------------------- motor interface
FRAME_DM = {'063': '11', '071': '14', '080': '19', '090': '24', '100': '28', '112': '28', '132': '38', '160': '42',
            '180': '48', '200': '55', '225': '60', '250': '65', '280': '75'}
FRAME_PMDM = {'063': '140x11', '071': '160x14', '080': '200x19', '090': '200x24', '100': '250x28', '112': '250x28',
              '132': '300x38', '160': '350x42', '180': '350x48', '200': '400x55', '225': '450x60', '250': '550x65',
              '280': '550x75'}


def build_motor_interface():
    out = []

    def add(size, frame, flange, i_min, i_max, page, series_var):
        fr = frame.zfill(3)
        out.append(dict(series=SERIES, size=size, iec_frame=frame, flange=flange, bore_mm=FRAME_DM.get(fr, ''),
                        src_page=page, i_min=i_min, i_max=i_max, pm_x_dm_b5=FRAME_PMDM.get(fr, ''), version=series_var))

    # p28: BA (right table) and CBA/CB compact (left table)
    for k, ver in ((0, 'CBA'), (1, 'BA')):
        rows = table_rows(28, k)
        frames = [hdr(c) for c in rows[0][2:]]
        for r in rows[1:]:
            size = canon(r[0].replace('CB ', ''))
            rng = [num(x.strip()) for x in r[1].split('÷')]
            i_min, i_max = rng[0], rng[-1]
            for fr, cell in zip(frames, r[2:]):
                cell = clean(cell).replace(' - ', '-')
                if cell:
                    add(size, fr, cell, i_min, i_max, 28, ver)
    # p29-31: B / CB / PB
    for page in (29, 30, 31):
        for k, t in enumerate(pdf.pages[page - 1].find_tables()):
            rows = t.extract()
            title = hdr(rows[0][0])  # 'CB - B - PB 063'
            size = canon(title.split()[-1])
            frames = [hdr(c).replace('*', '') for c in rows[1][1:]]
            for r in rows[2:]:
                if not r[0]:
                    continue
                i = num(r[0].strip())
                for fr, cell in zip(frames, r[1:]):
                    cell = clean(cell)
                    if not cell:
                        continue
                    for f1 in fr.split('-') if fr == '100-112' else [fr]:
                        add(size, f1, cell, i, i, page, 'B/CB/PB')
    cols = ['series', 'size', 'iec_frame', 'flange', 'bore_mm', 'src_page', 'i_min', 'i_max', 'pm_x_dm_b5', 'version']
    Writer.write('motor_interface.csv', cols, out)


# ----------------------------------------------------------------- dimensions
def build_dimensions():
    # ---- BA / CBA / IBA housing (p39-44)
    ba_rows = []
    cols_ba = None
    for page, fam in ((39, 'BA'), (40, 'BA'), (41, 'CBA'), (42, 'CBA'), (43, 'IBA'), (44, 'IBA')):
        rows = table_rows(page, 0)
        rr, header = parse_main_table(rows, page, lambda lab, fam=fam: fam, None)
        if page == 40 or page == 42 or page == 44:
            pass
        ba_rows += rr
    # p40/42/44 first table has no size label on first row for BA53 (label cell sits between rows) -> handled by cell merge
    cols = ['D H7', 'b', 't', 'U', 'V', 'E', 'E1', 'F', 'G', 'G1', 'H', 'H1', 'I', 'J', 'K', 'L', 'M', 'N', 'N1', 'O',
            'O1', 'P', 'Q', 'R', 'S', 'T', 'W']
    fwrite('dimensions_BA_housing.csv', ba_rows, ['series', 'size', 'variant'], cols)

    # ---- BA/CBA/IBA input shaft IBA (p43,p44 table1) + IB (p50 table 2)
    inp = []
    for page, k, fam in ((43, 1, 'IBA'), (44, 1, 'IBA'), (50, 2, 'IB')):
        rows = table_rows(page, k)
        header = [hdr(c) for c in rows[0]]
        for r in rows[1:]:
            d = dict(series=SERIES, size=canon(r[0]), variant=fam, src_page=page)
            for h, c in zip(header[1:], r[1:]):
                d[h] = num(c)
            inp.append(d)
    # IB table header: G3,B2,D2,b2,t2,f2 ; IBA: G3,D1,B1,b1,t1,f
    fwrite('dimensions_input_shaft.csv', inp, ['series', 'size', 'variant'],
           ['G3', 'D1', 'B1', 'b1', 't1', 'f', 'B2', 'D2', 'b2', 't2', 'f2'])

    # ---- motor T / TB (CBA p41,42 ; CB p48)
    mt = []
    for page, fam in ((41, 'CBA'), (42, 'CBA'), (48, 'CB')):
        tabs = pdf.pages[page - 1].find_tables()
        for k in range(1, len(tabs)):
            rows = tabs[k].extract()
            mtype = clean(rows[0][0] or rows[0][2]).split()[0]
            frames = [hdr(c) for c in rows[1][2:]]
            groups = None
            cur = {}
            for r in rows[2:]:
                if r[0]:
                    groups = [clean(x) for x in r[0].split('\n')]
                    cur = {}
                sym = clean(r[1])
                cur[sym] = r[2:]
                if sym == 'Z':
                    for g in groups:
                        for j, fr in enumerate(frames):
                            xb, xs = split_star(cur['X'][j])
                            if not (xb or num(cur['Y'][j]) or num(cur['Z'][j])):
                                continue
                            mt.append(dict(series=SERIES, size=canon(g), variant=fam, motor_type=mtype, motor_frame=fr,
                                           X=xb, X_star=xs, Y=num(cur['Y'][j]), Z=num(cur['Z'][j]), src_page=page))
    fwrite('dimensions_compact_motor_CB.csv', mt, ['series', 'size', 'variant'],
           ['motor_type', 'motor_frame', 'X', 'X_star', 'Y', 'Z'])

    # ---- B / CB / IB housing (identical on p46, 48, 50)
    r1 = table_rows(46, 0)
    r2 = table_rows(46, 1)
    h1 = [hdr(c) for c in r1[0]]
    h2 = [hdr(c) for c in r2[0]]
    # table 1 rows with continuation
    bd = {}
    cur = None
    prev = None
    out = []
    for r in r1[1:]:
        if r[0]:
            cur = r[0]
            prev = None
        vals = list(r)
        if prev:
            vals = [v if v not in (None, '') else prev[j] for j, v in enumerate(vals)]
        prev = vals
        d = {h: num(c) for h, c in zip(h1[1:], vals[1:])}
        d['size'] = cur
        out.append(d)
    t2 = {}
    for r in r2[1:]:
        t2[r[0]] = {h: num(c) for h, c in zip(h2[1:], r[1:])}
    rows = []
    for d in out:
        row = dict(series=SERIES, size=canon(d['size']), variant='B-CB-IB', src_page=46)
        row.update({k: v for k, v in d.items() if k != 'size'})
        row.update(t2[d['size']])
        rows.append(row)
    cols = h1[1:] + h2[1:]
    fwrite('dimensions_B_housing.csv', rows, ['series', 'size', 'variant'], cols)

    # ---- motor-flange G2 per IEC frame (p39, p40 BA ; p46 B) and Pm/Dm/bm/tm (B5, B14)
    g2 = []
    for page in (39, 40, 46):
        rows = table_rows(page, 1 if page != 46 else 2)
        # header row index with IEC
        hi = [i for i, r in enumerate(rows[:3]) if r[0] and hdr(r[0]) == 'IEC'][0]
        head = [hdr(c) for c in rows[hi]]
        sizecols = head[2:] if page == 46 else head[3 if page == 39 else 3:]
        for r in rows[hi + 1:]:
            if page == 46:
                pm_b5, pm_b14, vals, names = clean(r[1]), '', r[2:], head[2:]
            else:
                pm_b5, pm_b14, vals, names = clean(r[1]), clean(r[2]), r[3:], head[3:]
            for nm, v in zip(names, vals):
                for s in expand_sizes(nm) if not nm.startswith('BA') or '-' not in nm else expand_sizes(nm):
                    g2.append(dict(series=SERIES, size=s, variant='G2', iec_frame=clean(r[0]), pm_x_dm_b5=pm_b5,
                                   pm_x_dm_b14=pm_b14, G2=num(v), src_page=page))
    fwrite('dimensions_motor_flange_G2.csv', g2, ['series', 'size', 'variant'], ['iec_frame', 'pm_x_dm_b5', 'pm_x_dm_b14', 'G2'])

    # ---- motor flange B5/B14 (Pm, Dm, bm, tm)
    fl = {}
    for page, k, v in ((39, 2, 'B5'), (39, 3, 'B14'), (40, 2, 'B5'), (40, 3, 'B14'), (46, 3, 'B5')):
        rows = table_rows(page, k)
        head = [hdr(c) for c in rows[0]]
        for r in rows[1:]:
            key = (v, clean(r[0]))
            fl.setdefault(key, dict(series=SERIES, size='motor_flange', variant=v, iec_frame=clean(r[0]),
                                    Pm=num(r[1]), Dm=num(r[2]), bm=num(r[3]), tm=num(r[4]), src_page=page))
    fwrite('dimensions_motor_flange.csv', list(fl.values()), ['series', 'size', 'variant'], ['iec_frame', 'Pm', 'Dm', 'bm', 'tm'])

    # ---- accessories
    # low speed (double) shaft p57
    rows = table_rows(57, 0)
    head = [hdr(c) for c in rows[0]]
    out = []
    for r in rows[1:]:
        for s in expand_sizes(r[0]):
            d = dict(series=SERIES, size=s, variant='low_speed_shaft', src_page=57)
            d.update({h: num(c) for h, c in zip(head[1:], r[1:])})
            out.append(d)
    fwrite('dimensions_low_speed_shaft.csv', out, ['series', 'size', 'variant'], head[1:])

    # output flange BA p58: availability + dims
    rows = table_rows(58, 0)
    out = []
    head = [hdr(c) for c in rows[0]]
    for r in rows[1:]:
        for nm, v in zip(head[1:], r[1:]):
            for s in expand_sizes(nm):
                out.append(dict(series=SERIES, size=s, variant='flange_availability_BA', flange=clean(r[0]),
                                n_available=num(v), src_page=58))
    fwrite('extra_output_flange_availability_BA.csv', out, ['series', 'size', 'variant'], ['flange', 'n_available'])
    rows = table_rows(58, 1)
    head = [hdr(c) for c in rows[0]]
    out = []
    cur = None
    for r in rows[1:]:
        if r[0]:
            cur = r[0].split('\n')
        for s in cur:
            d = dict(series=SERIES, size=canon(s), variant='output_flange_BA', flange=clean(r[1]), src_page=58)
            d.update({h: num(c) for h, c in zip(head[2:], r[2:])})
            out.append(d)
    fwrite('dimensions_output_flange_BA.csv', out, ['series', 'size', 'variant', 'flange'], head[2:])
    # output flange B p59
    rows = table_rows(59, 0)
    head = [hdr(c) for c in rows[0]]
    out = []
    cur = None
    cc = {}
    for r in rows[1:]:
        if r[0]:
            cur = r[0]
        d = dict(series=SERIES, size=canon(cur), variant='output_flange_B(S/U)', flange=clean(r[1]), src_page=59)
        d.update({h: num(c) for h, c in zip(head[2:], r[2:])})
        if d.get('C'):
            cc[cur] = (d['C'], d['G1'])
        out.append(d)
    for d in out:  # C and G1 are printed once per size (merged cell) -> apply to all its flange rows
        for s, (c, g) in cc.items():
            if canon(s) == d['size']:
                d['C'], d['G1'] = c, g
    fwrite('dimensions_output_flange_B.csv', out, ['series', 'size', 'variant', 'flange'], head[2:])

    # torque arm positions p60/p61 + dims p60,p62
    out = []
    for page, k in ((60, 0), (61, 0)):
        rows = table_rows(page, k)
        for r in rows[2:]:
            for s in expand_sizes(r[0].replace('A53', 'BA53').replace('A73', 'BA73')) if page == 60 else [canon(r[0])]:
                for pi in range(8):
                    for jj, nm in enumerate(('J', 'K')):
                        v = r[1 + 2 * pi + jj]
                        v = clean(v)
                        out.append(dict(series=SERIES, size=s, variant='torque_arm_position', position='P%d' % (pi + 1),
                                        side=nm,
                                        status={'': 'available', '/': 'not_available', '*': 'not_available_with_shrink_disc'}.get(v, v),
                                        src_page=page))
    fwrite('extra_torque_arm_positions.csv', out, ['series', 'size', 'variant', 'position', 'side', 'status'], [])
    out = []
    for page, k in ((60, 1), (62, 0), (62, 1)):
        rows = table_rows(page, k)
        head = [hdr(c) for c in rows[0]]
        for r in rows[1:]:
            lab = clean(r[0])
            m = re.fullmatch(r'(B\d{3})([SU])', lab)
            if m:
                sizes, var = [m.group(1)], 'torque_arm_B..' + m.group(2)
            else:
                sizes, var = expand_sizes(lab), 'torque_arm'
            for s in sizes:
                d = dict(series=SERIES, size=s, variant=var, src_page=page)
                d.update({h: num(c) for h, c in zip(head[1:], r[1:])})
                out.append(d)
    fwrite('dimensions_torque_arm.csv', out, ['series', 'size', 'variant'], ['KI', 'KG', 'KH', 'G', 'R', 'KM'])

    # output shaft cover p63
    rows = table_rows(63, 0)
    out = [dict(series=SERIES, size=canon(r[0]), variant='output_shaft_cover', N2=num(r[1]), src_page=63) for r in rows[1:]]
    fwrite('dimensions_output_shaft_cover.csv', out, ['series', 'size', 'variant'], ['N2'])

    # shrink disc p65
    rows = table_rows(65, 0)
    head = [hdr(c) for c in rows[0]]
    out = []
    for r in rows[1:]:
        for s in expand_sizes(r[0]):
            d = dict(series=SERIES, size=s, variant='shrink_disc', src_page=65)
            d.update({h: num(c) for h, c in zip(head[1:], r[1:])})
            out.append(d)
    fwrite('dimensions_shrink_disc.csv', out, ['series', 'size', 'variant'], head[1:])

    # assembling kit p67 (merged D rows)
    rows = table_rows(67, 0)
    head = [hdr(c) for c in rows[0]]
    out = []
    cur = None
    for r in rows[1:]:
        if r[0]:
            cur = r[0]
        for s in expand_sizes(cur):
            d = dict(series=SERIES, size=s, variant='assembling_kit', src_page=67)
            d.update({h: num(c) for h, c in zip(head[1:], r[1:])})
            out.append(d)
    fwrite('dimensions_assembling_kit.csv', out, ['series', 'size', 'variant'], head[1:])

    # machine axis p68
    rows = table_rows(68, 0)
    head = [hdr(c) for c in rows[0]]
    out = []
    cur = None
    for r in rows[1:]:
        if r[0]:
            cur = r[0]
        d = dict(series=SERIES, size=canon(cur), variant='machine_axis', src_page=68)
        d.update({h.replace('*', ''): num(c) for h, c in zip(head[1:], r[1:])})
        out.append(d)
    fwrite('dimensions_machine_axis.csv', out, ['series', 'size', 'variant'], ['D H7/h6', 'E', 'l', 'm'])

    # shaft end keyways p52
    rows = table_rows(52, 0)
    out = []
    last = {}
    for r in rows[2:]:
        def sp(c):
            return [num(x) for x in str(c).split('\n')] if c not in (None, '') else None
        tol = r[6] if r[6] else last.get('tol', '')
        s = sp(r[9]) or last.get('s')
        t12 = sp(r[13]) or last.get('t12')
        rr = sp(r[14]) or last.get('r')
        last.update(tol=tol, s=s, t12=t12, r=rr)
        out.append(dict(series=SERIES, size='keyway', variant='UNI6604-DIN6885', d_over=num(r[1]), d_to=num(r[2]),
                        b_key=num(r[3]), h_key=num(r[5]), tol_b_h=clean(tol), L_min=num(r[7]), L_max=num(r[8]),
                        s_min=s[0], s_max=s[-1], b=num(r[10]), t1=num(r[11]), t2=num(r[12]),
                        tol_t1=t12[0], tol_t2=t12[-1], r_a=rr[0], r_b=rr[-1], src_page=52))
    fwrite('extra_shaft_end_keyway.csv', out, ['series', 'size', 'variant'],
           ['d_over', 'd_to', 'b_key', 'h_key', 'tol_b_h', 'L_min', 'L_max', 's_min', 's_max', 'b', 't1', 't2', 'tol_t1',
            'tol_t2', 'r_a', 'r_b'])


# ----------------------------------------------------------------- weights
def build_weights():
    out = []
    t = pdf.pages[50].find_tables()
    # table 0: B-PB reducer (without motor), columns = motor flange size
    rows = t[0].extract()
    head = [hdr(c) for c in rows[0]]
    for r in rows[1:]:
        for nm, v in zip(head[1:-1], r[1:-1]):
            if not num(v):
                continue
            out.append(dict(series=SERIES, size=canon(r[0]), variant='reducer B-PB (with motor flange, without motor)',
                            motor_frame=nm, mass_kg=num(v), src_page=51))
    for r in t[1].extract()[1:]:
        out.append(dict(series=SERIES, size=canon(r[0]), variant='reducer IB (input shaft)', motor_frame='',
                        mass_kg=num(r[1]), src_page=51))
    for k in (2, 3, 4, 5):
        rows = t[k].extract()
        # rows[0] = [CB, 'TH'..]; sub header row 1 = frames
        mt = hdr(rows[0][2] if len(rows[0]) > 2 and rows[0][2] else [c for c in rows[0][1:] if c][0])
        hr = rows[1]
        for r in rows[2:]:
            for j in range(1, len(r) - 1):
                if r[j] is None or not num(r[j]):
                    continue
                out.append(dict(series=SERIES, size=canon(r[0]), variant='gearmotor CB %s' % mt, motor_frame=hdr(hr[j]),
                                mass_kg=num(r[j]), src_page=51))
    fwrite('weights.csv', out, ['series', 'size', 'variant', 'motor_frame', 'mass_kg'], [])


# ----------------------------------------------------------------- lubrication
POS = ['B3', 'B8', 'B6', 'B7', 'V5', 'V6']


def build_lubrication():
    out = []
    oil_ba = 'mineral oil SAE 85W-140 (Tamb -5..+40 C)'
    oil_b = 'mineral oil ISO VG220 (Tamb -5..+40 C); ISO VG150 for -15..+25 C'
    for k, ver in ((0, 'B'), (1, 'CB')):
        rows = table_rows(37, k)
        head = rows[0][1:]
        vals = rows[1][1:]  # merged cell spans all positions B3..V6
        for s, v in zip(head, vals):
            for pos in POS:
                out.append(dict(series=SERIES, size=canon(s), mounting_position=pos, oil_l=num(v), oil_type=oil_ba,
                                src_page=37, version=ver, note='single value printed for all mounting positions (merged cell)'))
    rows = table_rows(37, 2)
    head = rows[0][1:]
    for r in rows[1:]:
        for s, v in zip(head, r[1:]):
            out.append(dict(series=SERIES, size=canon(s), mounting_position=r[0], oil_l=num(v), oil_type=oil_b,
                            src_page=37, version='B-CB', note=''))
    Writer.write('lubrication.csv', ['series', 'size', 'mounting_position', 'oil_l', 'oil_type', 'src_page', 'version', 'note'], out)
    # lubricant brands (p35) and special lubricants (p36) as raw tables
    out = []
    rows = table_rows(35, 0)
    cols = ['B063-163 (-5..+40C) ISO VG220', 'B063-163 (-15..+25C) ISO VG150', 'BA42..A72/3 (-5..+40C) SAE 85W-140']
    for r in rows[3:]:
        for c, v in zip(cols, r[1:]):
            out.append(dict(series=SERIES, size='', variant='standard_lubricants', brand=clean(r[0]), application=c,
                            product=clean(v), src_page=35))
    fwrite('extra_lubricants_standard.csv', out, ['series', 'size', 'variant'], ['brand', 'application', 'product'])
    out = []
    for k, kind in ((0, 'polyglycol synthetic'), (1, 'polyglycol synthetic food grade')):
        rows = table_rows(36, k)
        brand = ''
        for r in rows[1:]:
            brand = r[0] or brand
            out.append(dict(series=SERIES, size='', variant='special_lubricants', brand=brand, oil_kind=kind,
                            tamb_c=clean(r[1]), product=clean(r[2]), src_page=36))
    fwrite('extra_lubricants_special.csv', out, ['series', 'size', 'variant'], ['brand', 'oil_kind', 'tamb_c', 'product'])


# ----------------------------------------------------------------- thermal / radial / extras
def build_thermal_radial_extra():
    out = []
    for r in table_rows(25, 0)[2:]:
        out.append(dict(series=SERIES, size=canon(r[0]), n1_rpm=1500, pth_kw=num(r[1]), src_page=25,
                        conditions='B3, continuous, n1<=1500, Tamb 25C, sea level, air>=1 m/s, no external loads'))
    Writer.write('thermal.csv', ['series', 'size', 'n1_rpm', 'pth_kw', 'src_page', 'conditions'], out)
    out = []
    rows = table_rows(25, 1)
    duty = [hdr(c) for c in rows[1][2:]]
    for r in rows[2:]:
        for d, v in zip(duty, r[2:]):
            out.append(dict(series=SERIES, size='', variant='thermal_factor', factor='Fc', param1='ambient_temp_C=' + clean(r[1]),
                            param2='duty_%_per_hour=' + d, value=num(v), src_page=25))
    for r in table_rows(25, 2)[1:]:
        out.append(dict(series=SERIES, size='', variant='thermal_factor', factor='Fa', param1='altitude_m=' + clean(r[0]).replace('*', ''),
                        param2='', value=num(r[1]), src_page=25))
    for r in table_rows(25, 3)[1:]:
        out.append(dict(series=SERIES, size='', variant='thermal_factor', factor='Fv', param1=clean(r[0]), param2='', value=num(r[1]),
                        src_page=25))
    fwrite('extra_thermal_factors.csv', out, ['series', 'size', 'variant'], ['factor', 'param1', 'param2', 'value'])

    # radial load
    inp, outp = [], []
    for k in (0, 1):
        rows = table_rows(33, k)
        head = rows[0][1:]
        for j, hh in enumerate(head):
            for s in expand_sizes(hh):
                inp.append(dict(series=SERIES, size=s, variant='input IB', a=num(rows[1][1 + j]), b=num(rows[2][1 + j]),
                                fr1_max_n=num(rows[3][1 + j]), src_page=33))
    fwrite('radial_load_input.csv', inp, ['series', 'size', 'variant'], ['a', 'b', 'fr1_max_n'])
    for k in (0, 1):
        rows = table_rows(34, k)
        head = rows[0][1:]
        for j, hh in enumerate(head):
            for s in expand_sizes(hh):
                outp.append(dict(series=SERIES, size=s, variant='output B', a=num(rows[1][1 + j]), b=num(rows[2][1 + j]),
                                 fr2_max_dsp_n=num(rows[3][1 + j]), fr2_max_c_n=num(rows[4][1 + j]), src_page=34))
    fwrite('radial_load_output.csv', outp, ['series', 'size', 'variant'], ['a', 'b', 'fr2_max_dsp_n', 'fr2_max_c_n'])

    # bearings p32
    out = []
    rows = table_rows(32, 0)
    names = [clean(x) for x in rows[0]]
    sizes = ['BA40', 'BA50', 'BA70']
    for r in rows[2:]:
        for si, s in enumerate(sizes):
            for ji, kind in enumerate(('standard', 'on_request')):
                out.append(dict(series=SERIES, size=s, variant='BA bearings (1=ball)', housing='U', output_version=r[1],
                                kind=kind, bearing=num(r[2 + 2 * si + ji]), src_page=32))
    rows = table_rows(32, 1)
    sizes = ['B060', 'B080', 'B100/125', 'B140/150/160']
    housing = None
    ver = None
    pend = None
    for r in rows[2:]:
        housing = r[0] or housing
        if r[1]:
            ver = r[1]
        elif r[0] is None and r[1] is None and pend:
            ver = pend
        for si, s in enumerate(sizes):
            for ji, kind in enumerate(('standard', 'on_request')):
                v = r[2 + 2 * si + ji]
                if v is None:
                    continue
                out.append(dict(series=SERIES, size=s, variant='B bearings (1=ball, 2=roller)', housing=housing,
                                output_version=ver, kind=kind, bearing=num(v) if v not in ('/',) else '', src_page=32))
        pend = ver
    fwrite('extra_output_shaft_bearings.csv', out, ['series', 'size', 'variant'], ['housing', 'output_version', 'kind', 'bearing'])

    # inertia p38
    out = []
    for k in (0, 1):
        for r in table_rows(38, k)[1:]:
            for s in expand_sizes(r[0]):
                out.append(dict(series=SERIES, size=s, J1_kgm2=num(r[1]), src_page=38))
    fwrite('extra_inertia.csv', out, ['series', 'size'], ['J1_kgm2'])

    # critical applications p27
    out = []
    for k in (0, 1):
        rows = table_rows(27, k)
        for r in rows[1:]:
            for s, v in zip(rows[0][1:], r[1:]):
                out.append(dict(series=SERIES, size=('B' + s) if k == 1 else s, variant='A=not recommended;B=check/call;tick=verified',
                                condition=clean(r[0]), rating=clean(v), src_page=27))
    fwrite('extra_critical_applications.csv', out, ['series', 'size', 'variant'], ['condition', 'rating'])

    # backstop p64
    out = []
    rows = table_rows(64, 1)
    frames = [clean(c) for c in rows[0][1:]]
    flanges = [hdr(c) for c in rows[1][1:]]
    for r in rows[2:]:
        for fr, fl, v in zip(frames, flanges, r[1:]):
            if clean(v):
                out.append(dict(series=SERIES, size=canon(r[0]), variant='backstop_device', iec_frame=fr, pm_x_dm=fl,
                                flange=clean(v), src_page=64))
    fwrite('extra_backstop_availability.csv', out, ['series', 'size', 'variant'], ['iec_frame', 'pm_x_dm', 'flange'])

    # reinforced seals p66
    out = []
    for r in table_rows(66, 0)[1:]:
        out.append(dict(series=SERIES, size=canon(r[0]), variant='reinforced_seal',
                        double_oil_seal='yes' if clean(r[1]) else '', VRM_ring='yes' if clean(r[2]) else '', src_page=66))
    fwrite('extra_reinforced_seals.csv', out, ['series', 'size', 'variant'], ['double_oil_seal', 'VRM_ring'])


# ----------------------------------------------------------------- service factor (chart on p14, raster)
def build_service_factor():
    """Chart read: three straight thick lines A/B/C (load class) vs starts/h; 4 vertical scales for hours/day.
    Pixel geometry measured on the embedded 1600x624 image (pdfimages page 14)."""
    import numpy as np
    from PIL import Image
    tmp = '/tmp/_B_p14'
    os.makedirs(tmp, exist_ok=True)
    subprocess.run(['pdfimages', '-png', '-f', '14', '-l', '14', PDF, tmp + '/i'], check=True)
    im = np.array(Image.open(tmp + '/i-000.png').convert('L')).astype(int)
    # y of the labelled grid lines: label 'top' is on line y=130.5 and each 0.1 step is 35.4 px (measured grid lines)
    def f2h(y, top):
        return top - (y - 130.5) / 354.0
    tops = {2: 1.7, 8: 1.9, 16: 2.1, 24: 2.4}
    xs = {5: 621, 10: 681, 20: 769, 30: 861, 50: 1041, 60: 1131, 70: 1221, 80: 1311, 90: 1403, 100: 1493}

    def runs_at(x):
        col = im[100:520, x] < 80
        res, st = [], None
        for i, v in enumerate(col):
            if v and st is None:
                st = i
            if (not v) and st is not None:
                if i - st >= 3:
                    res.append((st + i - 1) / 2 + 100)
                st = None
        return res
    pts = {}
    for s, x in xs.items():
        r = runs_at(x)
        assert len(r) == 3, (s, r)
        pts[s] = r  # [C, B, A] top to bottom
    # straight-line fit for each class (also gives starts/h = 40 where letter boxes hide the line)
    import numpy as np
    out = []
    for ci, cls in enumerate(('C', 'B', 'A')):
        px = np.array(list(xs.values()), float)
        py = np.array([pts[s][ci] for s in xs], float)
        a, b = np.polyfit(px, py, 1)
        for s in (5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100):
            x = {**xs, 40: 951}[s]
            y = a * x + b
            for h, top in tops.items():
                fs = round(round(f2h(y, top) / 0.05) * 0.05, 2)
                out.append(dict(series=SERIES, load_class=cls, hours_per_day=h, starts_per_hour=s, fs=fs, src_page=14,
                                method='read from chart p14, rounded to 0.05'))
    out.sort(key=lambda d: (d['load_class'], d['hours_per_day'], d['starts_per_hour']))
    Writer.write('service_factor.csv', ['series', 'load_class', 'hours_per_day', 'starts_per_hour', 'fs', 'src_page', 'method'], out)


# ----------------------------------------------------------------- motors (section 3.4)
def build_motors():
    # dimensions
    out = []
    flange = []
    for page, k in ((53, 0), (54, 0)):
        rows = table_rows(page, k)
        head = [hdr(c) for c in rows[0]]
        for r in rows[1:]:
            d = dict(series=SERIES, motor_type='', frame=clean(r[0]), variant='motor_body', src_page=page)
            poles = ''
            start = 1
            if page == 54:
                poles = clean(r[1])
                start = 2
            d['poles'] = poles
            names = head[start:]
            seen = collections.Counter()
            for nm, c in zip(names, r[start:]):
                if not nm and page == 54:
                    nm = 'Pg_2'
                base, star = None, None
                if c and '\n' in str(c):
                    base, star = split_star(c)
                    d[nm] = base
                    d[nm + '_star'] = star
                else:
                    d[nm] = num(c)
            out.append(d)
    for page, k, v in ((53, 1, 'B5'), (53, 2, 'B14'), (54, 1, 'B5')):
        rows = table_rows(page, k)
        head = [hdr(c) for c in rows[0]]
        for r in rows[1:]:
            d = dict(series=SERIES, motor_type='', frame=clean(r[0]), variant='flange_' + v, poles='', src_page=page)
            for nm, c in zip(head[1:], r[1:]):
                d[nm] = num(c)
            out.append(d)
    cols = ['AC', 'AD', 'L', 'L_star', 'LB', 'LB_star', 'LC', 'LC_star', 'X', 'Y', 'V', 'D', 'E', 'E1', 'f', 'F1', 'GA', 'F', 'GD',
            'LL', 'Pg', 'Pg_2', 'M', 'N', 'P', 'LA', 'S', 'T']
    fwrite('motors_dimensions.csv', out, ['series', 'motor_type', 'frame', 'poles', 'variant'], cols)
    # nominal power p56 -> motors.csv ; efficiency classes from p55 text
    eff = {'TS': 'IE1', 'TH': 'IE2', 'TP': 'IE3'}
    out = []
    for k in range(5):
        rows = table_rows(56, k)
        names = [hdr(c) if c else '' for c in rows[0]]
        types = [hdr(c) for c in rows[1]]
        # header names are on merged cells (None = same frame as previous named column)
        cur = ''
        frames = []
        for n in names:
            cur = n or cur
            frames.append(cur)
        for r in rows[2:]:
            pole = clean(r[0])
            for j in range(1, len(r)):
                v = clean(r[j])
                if v in ('', '-'):
                    continue
                out.append(dict(series=SERIES, motor_type=types[j], frame=frames[j], poles=pole, power_kw=num(v), rpm='',
                                voltage_v='', efficiency_class=eff[types[j]], efficiency_pct='', torque_nm='', current_a='',
                                mass_kg='', src_page=56))
    Writer.write('motors.csv', ['series', 'motor_type', 'frame', 'poles', 'power_kw', 'rpm', 'voltage_v', 'efficiency_class',
                                'efficiency_pct', 'torque_nm', 'current_a', 'mass_kg', 'src_page'], out)


# ----------------------------------------------------------------- designation
def write_designation():
    d = {
        'series': 'B',
        'source_pages': {'designation_chart': 17, 'versions': [18, 19, 20, 21], 'modularity': [22, 23], 'mounting_positions': 24},
        'pattern': 'B <type> <size> <casing><output shaft> [<output flange>] <ratio> <input dims> <output dims> <mounting position> [accessories]',
        'example_from_chart': 'B 083 F C FA 91,3 160x14 250x28 B3 ...',
        'note': 'Chart on PDF p17 is an image; field order read from it. Casing letter + output-shaft letter combine, e.g. FC = foot mounting + C hollow shaft.',
        'segments': [
            {'name': 'series', 'values': {'B': 'B series helical-bevel (family code)'}},
            {'name': 'type', 'description': 'gearbox / motor-side execution', 'values': {
                'PB': 'gearmotor fitted for motor mounting with flexible coupling (PAM-type input with elastic coupling); not for size 063',
                'B': 'gearmotor fitted for motor coupling (PAM) - IEC B5/B11 motor flange',
                'CB': 'compact gearmotor (motor directly flanged; B10/B11 compact motor versions)',
                'IB': 'gear reducer with input shaft'},
             'aluminium_series_prefix': 'BA = aluminium series: CBA compact motor, BA PAM motor-coupling, IBA input shaft'},
            {'name': 'size', 'values': {'A42': 'aluminium series 2 stages', 'A52': 'aluminium 2 stages', 'A53': 'aluminium 3 stages',
                                        'A72': 'aluminium 2 stages', 'A73': 'aluminium 3 stages', '063': 'cast iron', '083': 'cast iron',
                                        '103': 'cast iron', '123': 'cast iron', '143': 'cast iron', '153': 'cast iron',
                                        '163': 'cast iron'}},
            {'name': 'casing_version', 'description': 'cast-iron series (063..163)', 'values': {
                'F': 'foot mounting', 'S': 'flange mounting', 'U': 'foot-flange mounting'}},
            {'name': 'output_shaft_version', 'values': {
                'C': 'hollow shaft', 'D': 'solid shaft', 'S': 'solid shaft', 'P': 'double output shaft',
                'L': 'shrink disc shaft', 'M': 'shrink disc shaft (opposite side)'},
             'availability': 'Sizes A42-A52-A53 are not available in versions D-S-P (p16). Aluminium series: foot mounting only (A40/A50/A70 pages 18); '
                             'cast iron 063-123: F/S/U; 143-163: F and U only per p19-21 (S flange: 063-123).'},
            {'name': 'output_flange', 'values': {'FA': 'output flange type A', 'FB': 'output flange type B', 'FC': 'output flange type C',
                                                  'FD': 'output flange type D (BA only)'},
             'availability': 'BA: A42/A52-A53: FA,FB,FC,FD; A72-A73: FA,FB (p58). B..S/U: 063,083,103,123: FA,FB,FC; 143: FB; 153: FB,FC; 163: FB (p59)'},
            {'name': 'ratio', 'description': 'reduction ratio i, 7.62 ... 442.76 (see ratings.csv)'},
            {'name': 'input_dimensions', 'description': 'PAM motor-coupling flange PmxDm (e.g. 160x14) or ECE input shaft diameter',
             'values': {'PAM': 'fitted for motor coupling (e.g. 160x14)', 'ECE': 'input shaft diameter (2B)'}},
            {'name': 'output_dimensions', 'description': 'output shaft/bore dimension, e.g. 250x28 (free field in chart)'},
            {'name': 'mounting_position', 'values': {'B3': 'horizontal, feet down', 'B8': 'horizontal, feet up', 'B6': 'horizontal, feet at side',
                                                       'B7': 'horizontal, feet at opposite side', 'V5': 'vertical, output down (motor up)',
                                                       'V6': 'vertical, output up (motor down)'},
             'note': 'p22 shows the six positions B3,B6,B7,B8,V5,V6 pictorially; meaning of V5/V6 orientation as drawn (V5 motor up, V6 motor down).'},
            {'name': 'terminal_box_position', 'values': {'1': 'default (top)', '2': 'right', '3': 'bottom', '4': 'left'},
             'note': 'p22; supplied in position 1 unless specified'},
            {'name': 'accessories', 'description': 'torque arm, output shaft cover, backstop, shrink disc, reinforced seals, mounting kit, machine axis (section 4)'},
        ],
        'direction_of_rotation': 'p24: standard rotation as in diagram; opposite rotation on request except BA42-BA52-BA53',
    }
    with open(os.path.join(OUT, 'designation.json'), 'w', encoding='utf-8') as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
    print('designation.json written')


# ----------------------------------------------------------------- images
DPI = 200
# (page, image index on page, size, kind, caption) ; None index = skip.  Logos / other-series photos are dropped.
IMG_PLAN = [
    (1, 1, 'general', 'photo', 'B series helical-bevel gearmotor (cover photo)'),
    (10, 3, 'general', 'photo', 'IEC electric motor (product range page)'),
    (14, 0, 'general', 'diagram', 'Service factor chart (load class A/B/C vs starts/h and hours/day)'),
    (15, 0, 'general', 'drawing', 'Motor assembly on PAM flange: flexible joint'),
    (15, 1, 'general', 'drawing', 'Motor assembly on PAM flange: PAM sleeve'),
    (17, 0, 'general', 'diagram', 'Designation (ordering code) chart'),
    (22, 0, 'BA', 'render', 'Modularity BA aluminium series: CBA / BA / IBA'),
    (23, 0, 'B', 'render', 'Modularity B grey cast iron series: CB / B / PB / IB and casing F / S / U'),
    (24, 0, 'general', 'render', 'Mounting positions B3 B6 B7 B8 V5 V6'),
    (24, 1, 'general', 'drawing', 'Terminal box positions 1-4'),
    (26, 0, 'general', 'drawing', 'Direction of rotation - high speed shaft'),
    (33, 0, 'B', 'drawing', 'Radial load on input shaft (a, b, x)'),
    (34, 0, 'B', 'drawing', 'Radial load on output shaft (a, b, x)'),
    (39, 0, 'BA42-BA72', 'drawing', 'BA.2 dimensions (reducer/geared motor)'),
    (40, 0, 'BA53-BA73', 'drawing', 'BA.3 dimensions'),
    (41, 0, 'CBA42-CBA72', 'drawing', 'CBA.2 dimensions'),
    (42, 0, 'CBA53-CBA73', 'drawing', 'CBA.3 dimensions'),
    (43, 0, 'IBA42-IBA72', 'drawing', 'IBA.2 dimensions'),
    (44, 0, 'IBA53-IBA73', 'drawing', 'IBA.3 dimensions'),
    (45, 0, 'B063-B163', 'drawing', 'B dimensions (PAM motor flange)'),
    (47, 0, 'B063-B163', 'drawing', 'CB dimensions (compact motor)'),
    (49, 0, 'B063-B163', 'drawing', 'IB dimensions (input shaft)'),
    (52, 0, 'general', 'drawing', 'Shaft end keyway (UNI 6604 - DIN 6885)'),
    (53, 0, 'general', 'drawing', 'Electric motor dimensions 63-160S, B5 and B14 flanges'),
    (54, 0, 'general', 'drawing', 'Electric motor dimensions 160M-280M, B5 flange'),
    (57, 0, 'BA70', 'drawing', 'Low speed shaft BA70 solid shaft'),
    (57, 1, 'B', 'drawing', 'Low speed shaft B solid shaft'),
    (58, 0, 'BA', 'drawing', 'Output flange BA (FA FB FC FD)'),
    (59, 0, 'B', 'drawing', 'Output flange B..S / B..U (FA FB FC)'),
    (60, 0, 'BA', 'drawing', 'Torque arm BA - mounting positions P1-P8, J/K sides'),
    (60, 1, 'BA', 'drawing', 'Torque arm BA - dimensions KI KG KH G R'),
    (61, 0, 'B', 'drawing', 'Torque arm B - mounting positions P1-P8'),
    (62, 0, 'B', 'drawing', 'Torque arm B063-123 dimensions'),
    (62, 1, 'B', 'drawing', 'Torque arm B143-163 dimensions'),
    (63, 0, 'B', 'drawing', 'Output shaft cover (N2)'),
    (64, 0, 'B', 'drawing', 'Backstop device - standard sense of direction'),
    (64, 1, 'B', 'drawing', 'Backstop device - opposite rotation'),
    (65, 0, 'general', 'drawing', 'Output shaft with shrink disc'),
    (66, 0, 'B', 'drawing', 'Reinforced oil seals - double oil seal'),
    (66, 1, 'B', 'drawing', 'Reinforced oil seals - VRM ring'),
    (67, 0, 'general', 'drawing', 'Assembling/disassembling kit components'),
    (67, 1, 'general', 'drawing', 'Assembling/disassembling kit dimensions'),
    (68, 0, 'general', 'drawing', 'Machine axis suggested dimensions'),
]
TILE_PAGES = {  # grid pages: image index 0 split into tiles (row-major captions)
    18: ('BA', ['C foot mounting / C hollow shaft', 'D foot mounting / D solid shaft', 'S foot mounting / S solid shaft',
                'P foot mounting / P double output shaft', 'L foot mounting / L shrink disc shaft']),
    19: ('B063-B123', ['FC foot / hollow shaft', 'FD foot / solid shaft D', 'FS foot / solid shaft S', 'FP foot / double output shaft',
                       'FL foot / shrink disc L', 'FM foot / shrink disc M']),
    20: ('B063-B123', ['SC flange / hollow shaft', 'SD flange / solid shaft D', 'SS flange / solid shaft S',
                       'SP flange / double output shaft', 'SL flange / shrink disc L', 'SM flange / shrink disc M']),
    21: ('B063-B163', ['UC foot-flange / hollow shaft', 'UD foot-flange / solid shaft D', 'US foot-flange / solid shaft S',
                       'UP foot-flange / double output shaft', 'UL foot-flange / shrink disc L', 'UM foot-flange / shrink disc M']),
}


def render_crop(page, bbox, path):
    x0, top, x1, bottom = bbox
    k = DPI / 72.0
    X, Y, W, H = int(x0 * k), int(top * k), int((x1 - x0) * k) + 1, int((bottom - top) * k) + 1
    base = path[:-4]
    subprocess.run(['pdftoppm', '-r', str(DPI), '-x', str(X), '-y', str(Y), '-W', str(W), '-H', str(H), '-png', '-singlefile',
                    '-f', str(page), '-l', str(page), PDF, base], check=True)


def find_tiles(img):
    """Split a figure sheet into tiles: bands of non-white rows, then column groups inside each band."""
    import numpy as np
    a = np.array(img.convert('L')) < 245
    def groups(mask, gap):
        idx = np.where(mask)[0]
        if len(idx) == 0:
            return []
        res, st, pv = [], idx[0], idx[0]
        for i in idx[1:]:
            if i - pv > gap:
                res.append((st, pv))
                st = i
            pv = i
        res.append((st, pv))
        return res
    tiles = []
    for (r0, r1) in groups(a.any(axis=1), 50):
        band = a[r0:r1 + 1]
        for (c0, c1) in groups(band.any(axis=0), 40):
            tiles.append((c0, r0, c1 + 1, r1 + 1))
    return tiles


def build_images():
    from PIL import Image
    d = os.path.join(OUT, 'images')
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    index = []
    cache = {}

    def page_images(p):
        if p not in cache:
            cache[p] = pdf.pages[p - 1].images
        return cache[p]

    def save(page, n, size, kind, caption, im=None, bbox=None):
        fn = '%s_%s_%s_p%d_%d.png' % (SERIES, size, kind, page, n)
        path = os.path.join(d, fn)
        if im is None:
            render_crop(page, bbox, path)
            im = Image.open(path)
        else:
            im.save(path)
        index.append(dict(file=fn, series=SERIES, size=size, kind=kind, caption=caption, src_page=page,
                          width_px=im.width, height_px=im.height))

    counters = collections.Counter()
    for page, idx, size, kind, caption in IMG_PLAN:
        im = page_images(page)[idx]
        counters[page] += 1
        save(page, counters[page], size, kind, caption, bbox=(im['x0'], im['top'], im['x1'], im['bottom']))
    for page, (size, caps) in TILE_PAGES.items():
        im = page_images(page)[0]
        tmp = os.path.join(d, '_tmp.png')
        render_crop(page, (im['x0'], im['top'], im['x1'], im['bottom']), tmp)
        sheet = Image.open(tmp).convert('RGB')
        tiles = find_tiles(sheet)
        merged = [t for t in tiles if not (t[1] < 100 and (t[3] - t[1]) < 100)]  # drop the size-range header bar
        merged.sort(key=lambda t: (round(t[1] / 150), t[0]))
        os.remove(tmp)
        if len(merged) != len(caps):
            print('WARNING tiles on p%d: found %d expected %d' % (page, len(merged), len(caps)))
        for n, (t, cap) in enumerate(zip(merged, caps), 1):
            crop = sheet.crop((max(t[0] - 8, 0), max(t[1] - 8, 0), min(t[2] + 8, sheet.width), min(t[3] + 8, sheet.height)))
            save(page, n, size, 'render', 'Version ' + cap, im=crop)
    index.sort(key=lambda r: (r['src_page'], r['file']))
    Writer.write('images/index.csv', ['file', 'series', 'size', 'kind', 'caption', 'src_page', 'width_px', 'height_px'], index)


if __name__ == '__main__':
    main()
