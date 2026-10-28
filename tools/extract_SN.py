#!/usr/bin/env python3
"""Extractor for Motovario SN (shaft mounted) catalogue -> data/raw/SN/.
Usage: python3 -I tools/extract_SN.py  (run from repo root). Needs pdftotext, pdftoppm, pdfimages, pdfplumber, Pillow.
"""
import csv, json, os, re, subprocess, sys, glob, shutil, tempfile
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')) if '__file__' in globals() else os.getcwd()
PDF = os.path.join(ROOT, 'sources/catalogs/SN_shaft-mounted.pdf')
OUT = os.path.join(ROOT, 'data/raw/SN')
os.makedirs(OUT, exist_ok=True)
S = 'SN'

def page_text(p):
    return subprocess.run(['pdftotext', '-layout', '-f', str(p), '-l', str(p), PDF, '-'],
                          capture_output=True, text=True, check=True).stdout

def num(s):
    s = s.strip()
    if s in ('', '-', '/'):
        return ''
    return s.replace(',', '.')

def write_csv(name, header, rows):
    with open(os.path.join(OUT, name), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return len(rows)

counts = {}
flags = []   # lines for notes.md

# ---------------------------------------------------------------- ratings
RH = ['series', 'size', 'stages', 'n1_rpm', 'p1_kw', 'i', 'n2_rpm', 't2_nm', 'fs', 'fr2_n', 'motor_frames',
      'variant', 'src_page', 'kind', 'motor', 'poles', 'fr1_n', 'n2_calc_rpm']
rat = []
stages = lambda size: {'2': '2', '3': '3'}.get(size[-1], '')
# --- gearmotor tables, pdf pages 45-63
pw = None
for p in range(45, 64):
    for line in page_text(p).splitlines():
        m = re.match(r'^\s*([\d,]+)\s+kW\s*$', line)
        if m:
            pw = m.group(1).replace(',', '.'); continue
        t = line.split()
        if len(t) == 8 and re.match(r'^SN1\d\d$', t[4]) and re.match(r'^\d+[A-Z]*/\d', t[5]):
            n2, m2, sf, i, red, mot, n1, fr2 = t
            frame = re.match(r'(\d+)', mot).group(1)
            poles = re.match(r'\d+[A-Z]*/(\d+)', mot).group(1)
            pk = f'{float(pw):.2f}'
            rat.append([S, red, stages(red), n1, pw, num(i), num(n2), m2, num(sf), fr2, frame,
                        f'gearmotor_{pk}kW', p, 'gearmotor', mot, poles, '', ''])
        elif line.strip() and re.match(r'^\s*\d', line) and 'kW' not in line and 'CATALOGUE' not in line and len(t) > 3 and not re.match(r'^\d+$', line.strip()):
            flags.append(f'UNPARSED gearmotor line p{p}: {line.strip()}')
# drop exact printed duplicates (same page, identical row printed twice)
seen = set(); rat2 = []
for r in rat:
    k = tuple(r[:12] + r[13:])
    if k in seen:
        flags.append(f'Duplicate printed row dropped (identical to earlier page/row): p{r[12]} {r[1]} {r[4]}kW {r[14]} i={r[5]}'); continue
    seen.add(k); rat2.append(r)
rat = rat2
ngm = len(rat)

# --- reducer (ISN) tables, pdf pages 64-87: 6 speeds x 4 pages
speed_by_page = {}
for k, n1 in enumerate([2900, 1450, 950, 725, 475, 360]):
    for p in range(64 + 4 * k, 68 + 4 * k):
        speed_by_page[p] = n1
isn_rows = []
for p in range(64, 88):
    size = None
    n1 = speed_by_page[p]
    for line in page_text(p).splitlines():
        m = re.match(r'^\s*(ISN1\d\d)\s*$', line)
        if m:
            size = m.group(1); continue
        t = line.split()
        if size and len(t) == 6 and re.match(r'^[\d,]+$', t[0]) and ',' in t[1]:
            mn2, i, pn1, n2, fr1, fr2 = t
            isn_rows.append((p, size, n1, mn2, i, pn1, n2, fr1, fr2))
        elif size and line.strip() and re.match(r'^\s*\d', line) and len(t) > 2 and 'CATALOGUE' not in line:
            flags.append(f'UNPARSED reducer line p{p}: {line.strip()}')
# ratio sets taken from the motor-flange tables (pp. 22-23) -- built below via ratio_map

# ---------------------------------------------------------------- motor flange availability (pp.22-23)
import pdfplumber
pdf = pdfplumber.open(PDF)
flange_rows = []            # (size, i, frames, page)
ratio_map = {}              # size -> {i: set(frames)}
for pn in (22, 23):
    pg = pdf.pages[pn - 1]
    ws = pg.extract_words()
    titles = [w for w in ws if re.match(r'^SN1\d\d$', w['text'])]
    for tw in titles:
        left = tw['x0'] < 300
        x_lo, x_hi = (0, 300) if left else (300, 700)
        y0 = tw['top']
        below = [t for t in titles if t['top'] > y0 + 5]
        y1 = min([t['top'] for t in below], default=pg.height) - 2
        reg = [w for w in ws if x_lo <= w['x0'] < x_hi and y0 < w['top'] < y1]
        hdr_i = [w for w in reg if w['text'] == 'i'][0]
        hdr = [w for w in reg if abs(w['top'] - hdr_i['top']) < 3 and re.match(r'^\d{3}$', w['text'])]
        cols = [((w['x0'] + w['x1']) / 2, w['text']) for w in hdr]
        for w in reg:
            if re.match(r'^\d+,\d\d$', w['text']) and w['top'] > hdr_i['top'] + 3 and w['x0'] < x_lo + 130:
                rowb = [b for b in reg if b['text'] == 'B5' and abs(b['top'] - w['top']) < 3]
                frames = []
                for b in rowb:
                    c = (b['x0'] + b['x1']) / 2
                    fx = min(cols, key=lambda cc: abs(cc[0] - c))
                    frames.append(fx[1])
                flange_rows.append((tw['text'], num(w['text']), frames, pn))
for size, i, frames, pn in flange_rows:
    ratio_map.setdefault(size, {}).setdefault(i, set()).update(frames)


# ---------------------------------------------------------------- assemble ratings
def fmt(x):
    return ('%.2f' % x).rstrip('0').rstrip('.') if x == x else ''

rejected = []
for (p, size, n1, mn2, i, pn1, n2, fr1, fr2) in isn_rows:
    sn = 'SN' + size[3:]
    iv = num(i)
    frames = ';'.join(sorted(ratio_map.get(sn, {}).get(iv, []), key=int)) if iv in ratio_map.get(sn, {}) else ''
    row = [S, size, stages(size), str(n1), num(pn1), iv, num(n2), mn2, '', fr2, frames, 'reducer', p, 'reducer', '', '',
           num(fr1), fmt(n1 / float(iv))]
    if iv not in ratio_map.get(sn, {}):
        rejected.append(row + ['ratio not in the ratio list of ' + sn + ' (motor-flange tables pp.22-23): stray/misplaced row in catalogue'])
    else:
        rat.append(row)
for r in rat:
    if r[13] == 'gearmotor':
        r[17] = fmt(float(r[3]) / float(r[5]))
        sn = r[1]
        if r[5] not in ratio_map.get(sn, {}):
            flags.append(f'Gearmotor ratio {r[5]} of {sn} p{r[12]} not in flange table ratio list')
n_red = len(rat) - ngm
counts['ratings.csv'] = write_csv('ratings.csv', RH, rat)
counts['ratings_rejected.csv'] = write_csv('ratings_rejected.csv', RH + ['reason'], rejected)

# quality gates
gate = []
dup = {}
for r in rat:
    k = (r[0], r[1], r[3], r[5], r[11])
    dup.setdefault(k, []).append(r[12])
for k, v in dup.items():
    if len(v) > 1:
        gate.append(f'DUPLICATE KEY {k} pages {v}')
for r in rat:
    try:
        n2c = float(r[3]) / float(r[5]); n2 = float(r[6])
        if abs(n2 - n2c) / n2c > 0.03:
            gate.append(f'G3 n2 mismatch p{r[12]} {r[1]} {r[13]} n1={r[3]} i={r[5]} printed n2={r[6]} n1/i={n2c:.1f}')
        if r[4]:
            eta = float(r[7]) * n2 / (9550 * float(r[4]))
            if r[13] == 'gearmotor' and not (0.55 <= eta <= 1.0):
                gate.append(f'G2 eta {eta:.3f} p{r[12]} {r[1]} {r[4]}kW i={r[5]}')
            if r[13] == 'reducer':
                eta_c = float(r[7]) * n2c / (9550 * float(r[4]))
                lo = float(r[7]) * n2c / (9550 * (float(r[4]) + 0.5)); hi = float(r[7]) * n2c / (9550 * max(float(r[4]) - 0.5, 0.01))
                if hi < 0.55 or lo > 1.0:
                    gate.append(f'G2 reducer eta(n1/i) {eta_c:.3f} (eta w/ printed n2 {eta:.3f}) p{r[12]} {r[1]} n1={r[3]} i={r[5]} Pn1={r[4]} Mn2={r[7]}')
    except ValueError as e:
        gate.append(f'ERR {r}')

# ---------------------------------------------------------------- generic word-position table reader
def tolnum(s):
    return s.replace(',', '.')

def lines_of(p):
    return [l for l in page_text(p).splitlines() if l.strip()]

def pwords(p):
    return pdf.pages[p - 1].extract_words()

def grid(p, header_names, header_y, row_re, y_max=None, tol_syms=(), row_dy=6, x_min=0):
    """Read a table by word coordinates.
    header_names: expected header tokens in left->right order, located on the line(s) with top in header_y (lo,hi).
    Rows: words matching row_re (left label), all words within +-row_dy of label top are assigned to nearest header
    centre; tokens like '+0,03/0' are stored in <col>_tol of the closest column to their left."""
    ws = pwords(p)
    hdr = [w for w in ws if header_y[0] <= w['top'] <= header_y[1] and w['x0'] >= x_min]
    hdr.sort(key=lambda w: w['x0'])
    hdr = [w for w in hdr if w['text'] in header_names]
    names = []
    for w in hdr:
        nm = w['text']
        while nm in names:
            nm += '_2'
        names.append(nm)
    cent = [(w['x0'] + w['x1']) / 2 for w in hdr]
    labels = [w for w in ws if re.match(row_re, w['text']) and w['top'] > header_y[1] and w['x0'] >= x_min and w['x0'] < hdr[0]['x0'] - 2
              and (y_max is None or w['top'] < y_max)]
    labels.sort(key=lambda w: w['top'])
    rows = []
    for lb in labels:
        row = {'label': lb['text']}
        near = [w for w in ws if abs(w['top'] - lb['top']) <= row_dy and w['x0'] > lb['x1'] + 1]
        near.sort(key=lambda w: w['x0'])
        for w in near:
            c = (w['x0'] + w['x1']) / 2
            if re.match(r'^[+-]\d', w['text']):
                # tolerance: attach to the nearest header column to the left of / at centre
                k = max([j for j in range(len(cent)) if cent[j] <= c + 4], key=lambda j: cent[j], default=0)
                row[names[k] + '_tol'] = tolnum(w['text'])
            else:
                k = min(range(len(cent)), key=lambda j: abs(cent[j] - c))
                row[names[k]] = tolnum(w['text']) if names[k] not in row else row[names[k]] + ' ' + tolnum(w['text'])
        rows.append(row)
    return names, rows


def ytop(p, text, nth=0):
    ws = [w for w in pwords(p) if w['text'] == text]
    ws.sort(key=lambda w: (w['top'], w['x0']))
    return ws[nth]['top']

def split_pair(label):
    return label.split('/')

def sizes_of(label, prefix='SN'):
    return [x if x.startswith(prefix) else prefix + x for x in label.split('/')]

# ---------------------------------------------------------------- dimensions_sn.csv (p30) and dimensions_isn.csv (p32)
H1 = ['C', 'CS', 'C1', 'E', 'E1', 'F', 'G1', 'G1S', 'H', 'H1', 'I', 'K', 'O', 'O2', 'O3', 'S', 'S']
H2 = ['D1', 'b1', 't1', 'U', 'B', 'D', 'b', 't', 'f']
H3 = ['G3', 'G3S', 'B2', 'D2', 'b2', 't2', 'f2']

def housing(p, prefix, with_isn_input):
    rows = {}
    y1 = ytop(p, 'C'); y2 = ytop(p, 'D1')
    n1, r1 = grid(p, H1, (y1 - 2, y1 + 2), r'^%s1\d\d/%s1\d\d$' % (prefix, prefix), y_max=y2 - 5)
    n2, r2 = grid(p, H2, (y2 - 2, y2 + 2), r'^%s1\d\d/%s1\d\d$' % (prefix, prefix), y_max=(ytop(p, 'G3') - 5) if with_isn_input else None)
    r3 = []
    if with_isn_input:
        y3 = ytop(p, 'G3')
        n3, r3 = grid(p, H3, (y3 - 2, y3 + 2), r'^%s1\d\d/%s1\d\d$' % (prefix, prefix))
    allr = []
    for k, a in enumerate(r1):
        d = dict(a); d.update({kk: v for kk, v in r2[k].items() if kk != 'label'})
        if with_isn_input:
            d.update({kk: v for kk, v in r3[k].items() if kk != 'label'})
        allr.append(d)
    return allr

dim_cols = ['C', 'CS', 'C1', 'E', 'E1', 'F', 'G1', 'G1S', 'H', 'H1', 'I', 'K', 'O', 'O2', 'O3', 'S', 'S_2',
            'D1', 'D1_tol', 'b1', 't1', 'U', 'B', 'D', 'D_tol', 'b', 't', 'f']
isn_cols = dim_cols + ['G3', 'G3S', 'B2', 'B2_tol', 'D2', 'b2', 't2', 'f2']
def emit_housing(fname, p, prefix, variant, cols, with_isn_input):
    out = []
    for d in housing(p, prefix, with_isn_input):
        for sz in sizes_of(d['label'], prefix):
            out.append([S, sz, variant] + [d.get(c, '') for c in cols] + [p])
    return write_csv(fname, ['series', 'size', 'variant'] + cols + ['src_page'], out)
# the printed header has 'S' twice (first = S col, second also S); second is stored as S_2
counts['dimensions_sn.csv'] = emit_housing('dimensions_sn.csv', 30, 'SN', 'geared motor SN (hollow shaft; PAM input)', dim_cols, False)
counts['dimensions_isn.csv'] = emit_housing('dimensions_isn.csv', 32, 'ISN', 'reducer ISN (hollow shaft; solid input shaft)', isn_cols, True)

# ---------------------------------------------------------------- p31 motor-flange dims G2/G2S and B5 table
t31 = lines_of(31)
mf, b5 = [], []
cur = None
for l in t31:
    m = re.match(r'^\s*(\d+(?:-\d+)?)\s+(\d+x\d+)\s+(.*)$', l)
    if m:
        v = m.group(3).split()
        mf.append((m.group(1), m.group(2), v))
    m = re.match(r'^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d,]+)\s*$', l)
    if m:
        b5.append([m.group(1), m.group(2), m.group(3), m.group(4), tolnum(m.group(5))])
grp = ['SN142', 'SN143', 'SN152', 'SN153', 'SN162', 'SN163', 'SN182', 'SN183']
rows = []
for iec, pmdm, v in mf:
    assert len(v) == 8, (iec, v)
    for k in range(4):
        for sz in grp[2 * k: 2 * k + 2]:
            rows.append([S, sz, 'IEC motor flange B5', iec, pmdm, '' if v[2 * k] == '/' else tolnum(v[2 * k]),
                         '' if v[2 * k + 1] == '/' else tolnum(v[2 * k + 1]), 31])
counts['dimensions_motor_flange.csv'] = write_csv('dimensions_motor_flange.csv',
    ['series', 'size', 'variant', 'IEC', 'Pm_x_Dm', 'G2', 'G2S', 'src_page'], rows)
counts['extra_motor_B5_bore.csv'] = write_csv('extra_motor_B5_bore.csv', ['series', 'iec_frame', 'Pm', 'Dm', 'bm', 'tm', 'src_page'],
    [[S] + b + [31] for b in b5])

# ---------------------------------------------------------------- motor_interface.csv + flange availability per ratio
b5d = {b[0]: b for b in b5}
mi = []
for sz in grp:
    frames = set()
    for i, fr in ratio_map[sz].items():
        frames.update(fr)
    for fr in sorted(frames, key=int):
        b = b5d.get(fr)
        mi.append([S, sz, fr, f'B5 (Pm {b[1]})' if b else 'B5', b[2] if b else '', 31, b[1] if b else ''])
counts['motor_interface.csv'] = write_csv('motor_interface.csv',
    ['series', 'size', 'iec_frame', 'flange', 'bore_mm', 'src_page', 'pm_mm'], mi)
av = []
for size, i, frames, pn in flange_rows:
    for fr in sorted(frames, key=int):
        av.append([S, size, i, fr, 'B5', pn])
counts['extra_motor_flange_availability.csv'] = write_csv('extra_motor_flange_availability.csv',
    ['series', 'size', 'i', 'iec_frame', 'flange', 'src_page'], av)

# ---------------------------------------------------------------- weights (p33)
wr = []
for l in lines_of(33):
    m = re.match(r'^\s*(\d{3})\s+(\d+)\s*$', l)
    if m:
        wr.append([S, 'ISN' + m.group(1), 'reducer without motor (table headed ISN; approximate)', '', m.group(2), 33])
counts['weights.csv'] = write_csv('weights.csv', ['series', 'size', 'variant', 'motor_frame', 'mass_kg', 'src_page'], wr)

# ---------------------------------------------------------------- lubrication (p29) + lubricants
OIL_TYPE = ('mineral oil ISO VG220 (Tamb -5..+40 C) or ISO VG150 (Tamb -15..+25 C); units SN142/3-182/3 supplied WITHOUT lubricant '
            '(fill to level plug); p27')
lub = []
L29 = lines_of(29)
hdrsz = None
for l in L29:
    t = l.split()
    if t and t[0] == 'SN' and len(t) == 9:
        hdrsz = ['SN' + x for x in t[1:]]
    elif hdrsz and t and re.match(r'^(B3|B8|B6|B7|V5|V6)$', t[0]) and len(t) == 9:
        for sz, v in zip(hdrsz, t[1:]):
            lub.append([S, sz, t[0], tolnum(v), OIL_TYPE, 29])
counts['lubrication.csv'] = write_csv('lubrication.csv', ['series', 'size', 'mounting_position', 'oil_l', 'oil_type', 'src_page'], lub)
# lubricant brand table (pp.27-28): transcribed from the text layer (merged multi-line cells), kept verbatim
lubr = [
 ('mineral', 'LAND OIL', 'ISO VG220', '(-5)-(+40)', 'GEAR POWER 220', 27), ('mineral', 'LAND OIL', 'ISO VG150', '(-15)-(+25)', '', 27),
 ('mineral', 'ENI', 'ISO VG220', '(-5)-(+40)', 'BLASIA 220', 27), ('mineral', 'ENI', 'ISO VG150', '(-15)-(+25)', 'BLASIA 150', 27),
 ('mineral', 'SHELL', 'ISO VG220', '(-5)-(+40)', 'OMALA S2 G 220', 27), ('mineral', 'SHELL', 'ISO VG150', '(-15)-(+25)', 'OMALA S2 G 150', 27),
 ('mineral', 'KLUBER', 'ISO VG220', '(-5)-(+40)', 'Kluberoil GEM 1-220N', 27), ('mineral', 'KLUBER', 'ISO VG150', '(-15)-(+25)', 'Kluberoil GEM 1-150N', 27),
 ('mineral', 'MOBIL', 'ISO VG220', '(-5)-(+40)', 'MOBILGEAR 600 XP220', 27), ('mineral', 'MOBIL', 'ISO VG150', '(-15)-(+25)', 'MOBILGEAR 600 XP150', 27),
 ('mineral', 'CASTROL', 'ISO VG220', '(-5)-(+40)', 'ALPHA SP 220', 27), ('mineral', 'CASTROL', 'ISO VG150', '(-15)-(+25)', 'ALPHA SP 150', 27),
 ('mineral', 'BP', 'ISO VG220', '(-5)-(+40)', 'ENERGOL GR-XP220', 27), ('mineral', 'BP', 'ISO VG150', '(-15)-(+25)', 'ENERGOL GR-XP150', 27),
 ('mineral', 'PETRONAS', 'ISO VG220', '(-5)-(+40)', 'GEAR MEP 220', 27), ('mineral', 'PETRONAS', 'ISO VG150', '(-15)-(+25)', 'GEAR MEP 150', 27),
]
brands28 = ['ENI', 'ENI', 'MOBIL', 'MOBIL', 'KLUBER', 'KLUBER', 'KLUBER', 'KLUBER', 'KLUBER', 'KLUBER']
brands28f = ['KLUBER'] * 5
k = 0; kf = 0; food = False
for l in lines_of(28):
    if 'food grade' in l:
        food = True; continue
    m = re.match(r'^\s*(?:[A-Z]+\s+)?\((-?\d+)\)\s*-\s*\((\+?\d+)\)\s+(.+?)\s*\((ISO VG\d+)\)\s*$', l)
    if m:
        rng = f'({m.group(1)})-({m.group(2)})'
        if not food:
            lubr.append(('polyglycol synthetic', brands28[k], m.group(4), rng, m.group(3), 28)); k += 1
        else:
            lubr.append(('polyglycol synthetic food grade', brands28f[kf], m.group(4), rng, m.group(3), 28)); kf += 1
counts['extra_lubricants.csv'] = write_csv('extra_lubricants.csv', ['series', 'oil_family', 'brand', 'iso_vg', 'tamb_c', 'product', 'src_page'],
    [[S, a, b, c, d, e, f] for (a, b, c, d, e, f) in lubr])

# ---------------------------------------------------------------- radial load parameters (pp.25-26)
rl = []
for p, shaft, sym in ((25, 'input (ISN)', 'Fr1 max'), (26, 'output (SN)', 'Fr2 max')):
    vals = {}
    for l in lines_of(p):
        m = re.match(r'^\s*(a|b|Fr[12] max\(\*\*\))\s+([\d, .]+)$', l)
        if m:
            vals[m.group(1)[0] if m.group(1) in ('a', 'b') else 'F'] = [tolnum(x) for x in m.group(2).split()]
    pre = 'ISN' if p == 25 else 'SN'
    for k2, grpn in enumerate(['142/143', '152/153', '162/163', '182/183']):
        for sz in sizes_of(grpn, pre):
            rl.append([S, sz, shaft, vals['a'][k2], vals['b'][k2], vals['F'][k2], p])
counts['radial_load_params.csv'] = write_csv('radial_load_params.csv',
    ['series', 'size', 'shaft', 'a_mm', 'b_mm', 'fr_max_n', 'src_page'], rl)

# ---------------------------------------------------------------- output flange (p39), reaction bolt (p40), shrink disc (p42), kit (p43), machine shaft (p44)
of = []
rws, labs = [], []
for l in lines_of(39):
    t = l.split()
    if t and re.match(r'^SN1\d\d/SN1\d\d$', t[0]):
        labs.append(t[0]); t = t[1:]
    if t and t[0] in ('FB', 'FC') and len(t) >= 10:
        rws.append(t[:10])
gi = -1
for r in rws:
    if r[0] == 'FB':
        gi += 1          # FC rows belong to the group of the preceding FB row (SN142/143 has FB and FC)
    code, J, M1, N, Ntol, O1, P, Ss, T, RF = r
    for sz in sizes_of(labs[gi]):
        of.append([S, sz, code, tolnum(J), M1, N, tolnum(Ntol), O1, P, Ss, T, RF, 39])
counts['dimensions_output_flange.csv'] = write_csv('dimensions_output_flange.csv',
    ['series', 'size', 'variant', 'J', 'M1', 'N', 'N_tol', 'O1', 'P', 'S', 'T', 'RF', 'src_page'], of)

def simple(p, ncol, fname, header, variant):
    rr = []
    for l in lines_of(p):
        t = l.split()
        if t and re.match(r'^SN1\d\d/SN1\d\d$', t[0]) and len(t) == ncol + 1:
            for sz in sizes_of(t[0]):
                rr.append([S, sz, variant] + [tolnum(x) for x in t[1:]] + [p])
    return write_csv(fname, ['series', 'size', 'variant'] + header + ['src_page'], rr)
counts['dimensions_reaction_bolt.csv'] = simple(40, 2, 'dimensions_reaction_bolt.csv', ['D1t', 'Lt'], 'reaction bolt')
counts['dimensions_shrink_disc.csv'] = simple(42, 14, 'dimensions_shrink_disc.csv',
    ['DC', 'D', 'D1', 'D2', 'D3', 'G4', 'L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'j', 'MT_10.9_Nm'], 'hollow shaft with shrink disc (L)')
counts['dimensions_assembly_kit.csv'] = simple(43, 3, 'dimensions_assembly_kit.csv', ['D', 'X', 'M'], 'assembling/disassembling kit')
counts['dimensions_machine_shaft.csv'] = simple(44, 3, 'dimensions_machine_shaft.csv', ['D_h6', 'E_suggested', 'm_suggested'], 'machine shaft (suggested values)')

# ---------------------------------------------------------------- misc small tables
# p34 shaft end keys UNI 6604 / DIN 6885
sk = []
for l in lines_of(34):
    m = re.match(r'^\s*(>\s+)?(\d+)\s+(\d+)\s+(\d+)\s+[x\u00d7]\s+(\d+)\s+(?:h\d+\s*/\s*h\d+\s+)?(\d+)\s+(\d+)\s+(?:[\d,]+\s+)?(\d+)\s+([\d,]+)\s+([\d,]+)\s*', l)
    if m and 'bxh' not in l:
        sk.append([S, 'general', 'key and keyway UNI 6604 / DIN 6885'] + [tolnum(m.group(k)) for k in (2, 3, 4, 5, 6, 7, 8, 9, 10)] + [34])
counts['extra_shaft_end_keys.csv'] = write_csv('extra_shaft_end_keys.csv',
    ['series', 'size', 'variant', 'd_over', 'd_to', 'b', 'h', 'L_min', 'L_max', 'b_chk', 't1', 't2', 'src_page'], sk)
# p21 critical applications, p24 bearings, p16 efficiency
crit = [[S, 'SN140', '1500<n1<3000', 'B', 21], [S, 'SN150', '1500<n1<3000', 'B', 21], [S, 'SN160', '1500<n1<3000', 'B', 21], [S, 'SN180', '1500<n1<3000', 'B', 21]]
counts['extra_critical_applications.csv'] = write_csv('extra_critical_applications.csv',
    ['series', 'size', 'input_speed_range', 'code', 'src_page'], crit)
brg = []
for l in lines_of(24):
    t = l.split()
    if t and t[0] in ('C', 'D', 'L') and len(t) == 5:
        for sz, v in zip(['142/143', '152/153', '162/163', '182/183'], t[1:]):
            for z in sizes_of(sz):
                brg.append([S, z, t[0], v, 'conical roller bearings' if v == '2' else 'ball bearings', 24])
counts['extra_output_bearings.csv'] = write_csv('extra_output_bearings.csv',
    ['series', 'size', 'version', 'bearing_code', 'meaning', 'src_page'], brg)
eff = [[S, '2', '0.98', 16], [S, '3', '0.96', 16]]
counts['extra_efficiency.csv'] = write_csv('extra_efficiency.csv', ['series', 'stages', 'efficiency', 'src_page'], eff)

# ---------------------------------------------------------------- electric motors section (pp.35-39)
# (a) body dimensions: p35 (63-160S), p36 (160M-280M)
MB = ['AC', 'AD', 'L', 'LB', 'LC', 'L_star', 'LB_star', 'LC_star', 'X', 'Y', 'V', 'D', 'D_tol', 'E', 'E1', 'f', 'F1', 'GA', 'F', 'GD', 'LL', 'Pg']
mot_dim = []
def numtok(x):
    return tolnum(x)
L35_all = lines_of(35)
cut = [k for k, l in enumerate(L35_all) if re.match(r'^\s*B5\s+M\s+N', l)][0]
L35 = L35_all[:cut]
above = None
rows35 = []
for idx, l in enumerate(L35):
    t = l.split()
    # three-number lines (L LB LC) printed above/below the frame row
    if len(t) == 3 and all(re.match(r'^\*?[\d,]+$', x) for x in t):
        rows35.append(('nums', t, idx)); continue
    m = re.match(r'^(63|71|80|90S|90L|100|112|132S|132L|160S)\s+(.*)$', l.strip())
    if m:
        rows35.append(('row', [m.group(1)] + m.group(2).split(), idx))
for k, (kind, t, idx) in enumerate(rows35):
    if kind != 'row':
        continue
    frame = t[0]; v = t[1:]
    # D token may be "11 j6" or "42k6"
    d = {}
    d['AC'], d['AD'] = numtok(v[0]), numtok(v[1])
    rest = v[2:]
    # detect whether L,LB,LC are present on this line: they are when the next 3 tokens are numeric and X(=80/98/118) follows
    has_L = len(rest) >= 18 or (len(rest) >= 3 and re.match(r'^[\d,]+$', rest[2]) and not re.match(r'^(j6|k6)', rest[2]) and len(rest) >= 17)
    # robust: count tokens: with L-block 3 more tokens
    names_after = ['X', 'Y', 'V', 'D', 'E', 'E1', 'f', 'F1', 'GA', 'F', 'GD']
    # D contains tolerance as separate token ("j6"/"k6") unless fused ("42k6")
    cnt_no_L = 11 + (1 if any(re.match(r'^[jk]\d$', x) for x in rest) else 0)
    if len(rest) == cnt_no_L + 3:
        d['L'], d['LB'], d['LC'] = numtok(rest[0]), numtok(rest[1]), numtok(rest[2]); rest = rest[3:]
    elif len(rest) == cnt_no_L:
        # L-block printed on neighbouring line(s)
        prev = rows35[k - 1] if k > 0 and rows35[k - 1][0] == 'nums' and rows35[k - 1][2] == idx - 1 else None
        nxt = rows35[k + 1] if k + 1 < len(rows35) and rows35[k + 1][0] == 'nums' and rows35[k + 1][2] == idx + 1 else None
        if prev:
            d['L'], d['LB'], d['LC'] = [numtok(x) for x in prev[1]]
        if nxt:
            d['L_star'], d['LB_star'], d['LC_star'] = [numtok(x.lstrip('*')) for x in nxt[1]]
        elif prev and not nxt:
            pass
    else:
        raise SystemExit(f'motor row parse {frame}: {rest}')
    X, Y, V = rest[:3]; rest = rest[3:]
    d['X'], d['Y'], d['V'] = X, Y, numtok(V)
    if re.match(r'^[jk]\d$', rest[1]):
        d['D'], d['D_tol'] = rest[0], rest[1]; rest = rest[2:]
    else:
        m = re.match(r'^(\d+)([jk]\d)$', rest[0]); d['D'], d['D_tol'] = m.group(1), m.group(2); rest = rest[1:]
    d['E'], d['E1'], d['f'], d['F1'], d['GA'], d['F'], d['GD'] = [numtok(x) for x in rest[:7]]
    mot_dim.append((frame, '', 'body', d, 35))
# frames 63..: the 'above' L-values for 80/90S/90L/112 -> the pre-line may be shared; verified against image in notes.
for l in lines_of(36):
    m = re.match(r'^\s*(\d{3}[A-Z])\s+([\d-]+)\s+(.*)$', l)
    if m:
        t = m.group(3).split()
        if len(t) == 14:
            d = dict(zip(['AC', 'AD', 'L', 'LB', 'X', 'D', 'E', 'f', 'GA', 'F', 'GD', 'LL', 'Pg', 'Pg_2'], [numtok(x) for x in t]))
            d['Pg'] = d['Pg'] + ' ' + d.pop('Pg_2')
            mot_dim.append((m.group(1), m.group(2), 'body', d, 36))
# (b) flange tables B5 / B14
fl = []
for l in lines_of(35):
    t = l.split()
    if len(t) == 14 and re.match(r'^\d+$', t[0]) and re.match(r'^\d+$', t[7]) and t[0] in ('63', '71', '80', '90', '100', '112', '132', '160'):
        fl.append((t[0], 'B5', dict(zip(['M', 'N', 'P', 'LA', 'S', 'T'], [numtok(x) for x in t[1:7]])), 35))
        fl.append((t[7], 'B14', dict(zip(['M', 'N', 'P', 'LA', 'S', 'T'], [numtok(x) for x in t[8:14]])), 35))
for l in lines_of(36):
    t = l.split()
    if len(t) == 7 and all(re.match(r'^\d+$', x) for x in t) and t[0] in ('160', '180', '200', '225', '250', '280'):
        fl.append((t[0], 'B5', dict(zip(['M', 'N', 'P', 'LA', 'S', 'T'], t[1:])), 36))
MDC = ['AC', 'AD', 'L', 'LB', 'LC', 'L_star', 'LB_star', 'LC_star', 'X', 'Y', 'V', 'D', 'D_tol', 'E', 'E1', 'f', 'F1', 'GA', 'F', 'GD', 'LL', 'Pg', 'M', 'N', 'P', 'LA', 'S', 'T']
out = []
for frame, poles, var, d, pg in mot_dim:
    out.append([S, frame, poles, var] + [d.get(c, '') for c in MDC] + [pg])
for frame, var, d, pg in fl:
    out.append([S, frame, '', var] + [d.get(c, '') for c in MDC] + [pg])
out = [[('' if x in ('/', '-') else x) for x in r] for r in out]
counts['motors_dimensions.csv'] = write_csv('motors_dimensions.csv', ['series', 'frame', 'poles', 'variant'] + MDC + ['src_page'], out)

# (c) nominal power table p38 -> motors.csv ; efficiency class mapping from p37
ws = pwords(38)
EFF = {'TS': 'IE1', 'TH': 'IE2', 'SH': 'IE2', 'HSH': 'IE2', 'TP': 'IE3'}
frame_re = re.compile(r'^\d{2,3}[A-Z]{0,3}$')
mrows = []
# find each block: header line (frames) at top T0, type line 'P.' at T0+~14, rows '2','4','6'
pw_words = [w for w in ws if w['text'] == 'P.']
for pwd in pw_words:
    ty = pwd['top']
    types = sorted([w for w in ws if abs(w['top'] - ty) < 3 and w['text'] in ('TS', 'TH', 'TP')], key=lambda w: w['x0'])
    hdr = sorted([w for w in ws if ty - 25 < w['top'] < ty - 3 and frame_re.match(w['text'])], key=lambda w: w['x0'])
    # poles rows
    prow = {}
    for w in ws:
        if w['text'] in ('2', '4', '6') and w['x0'] < pwd['x0'] + 15 and ty + 3 < w['top'] < ty + 50:
            prow[w['text']] = w['top']
    for tw in types:
        c = (tw['x0'] + tw['x1']) / 2
        # frame header: the nearest header word centre
        hw = min(hdr, key=lambda h: abs((h['x0'] + h['x1']) / 2 - c))
        for poles, ytop_ in prow.items():
            vals = [w for w in ws if abs(w['top'] - ytop_) < 3 and abs((w['x0'] + w['x1']) / 2 - c) < 14 and w['x0'] > pwd['x1']]
            if vals:
                v = min(vals, key=lambda w: abs((w['x0'] + w['x1']) / 2 - c))['text']
                if v not in ('-', '/'):
                    mrows.append((hw['text'], tw['text'], poles, tolnum(v)))
mrows.sort(key=lambda r: (r[0], r[2]))
counts['motors.csv'] = write_csv('motors.csv',
    ['series', 'motor_type', 'frame', 'poles', 'power_kw', 'rpm', 'voltage_v', 'efficiency_class', 'efficiency_pct', 'torque_nm', 'current_a', 'mass_kg', 'src_page'],
    [[S, t, f, po, pk, '', '', EFF[t], '', '', '', '', 38] for (f, t, po, pk) in mrows])


# ---------------------------------------------------------------- service factor (p14): digitised from the raster chart
# The chart is a bitmap (no text/vector data).  Three curves (load class A/B/C) are located by pixel analysis; each
# daily-hours column (2/8/16/24 h) has its own printed vertical scale (0.1 per grid line).  Values are READ OFF THE
# GRAPH and rounded to 0.05 -> approximate; see notes.md.
from PIL import Image
import numpy as np
tmpd = tempfile.mkdtemp()
subprocess.run(['pdftoppm', '-r', '250', '-f', '14', '-l', '14', '-png', PDF, os.path.join(tmpd, 'sf')], check=True)
im = np.array(Image.open(glob.glob(os.path.join(tmpd, 'sf*.png'))[0]).convert('L')).astype(int)
OY, OX = 400, 150                      # crop offset used while calibrating
sub = im[OY:1050, OX:2070]
XT = {5: 636, 10: 697, 20: 798, 30: 899, 40: 1000, 50: 1102, 60: 1203, 70: 1304, 80: 1406, 90: 1508, 100: 1609}  # grid x of tick labels
Y07, Y17 = 601, 202                    # y pixels of the printed 0.7 and 1.7 labels (2 h column)
BASE = {2: 0.7, 8: 0.9, 16: 1.1, 24: 1.4}   # lowest printed value of each hours column (same grid row)
pts = {0: [], 1: [], 2: []}            # 0=A lowest curve, 1=B, 2=C
for x in range(610, 1690):
    col = sub[:, x]
    ys = [y for y in np.where(col < 70)[0] if y > 250]
    groups = []
    for y in ys:
        if groups and y - groups[-1][-1] <= 2: groups[-1].append(y)
        else: groups.append([y])
    groups = [g for g in groups if 3 <= len(g) <= 9]
    if len(groups) == 3:
        for k, g in enumerate(sorted(groups, key=lambda g: -np.mean(g))):
            pts[k].append((x, float(np.mean(g))))
fits = {k: np.polyfit([a for a, b in v], [b for a, b in v], 1) for k, v in pts.items()}
sf_rows = []
for k, cls in enumerate(['A', 'B', 'C']):
    for hrs, base in BASE.items():
        for st, xp in XT.items():
            y = np.polyval(fits[k], xp)
            val = base + (Y07 - y) / (Y07 - Y17) * 1.0
            sf_rows.append([S, cls, hrs, st, '%.2f' % (round(val * 20) / 20), 14])
counts['service_factor.csv'] = write_csv('service_factor.csv',
    ['series', 'load_class', 'hours_per_day', 'starts_per_hour', 'fs', 'src_page'], sf_rows)
shutil.rmtree(tmpd)

# ---------------------------------------------------------------- designation.json (p17, 2.2.1; transcribed from the diagram)
sizes_all = ['142', '143', '152', '153', '162', '163', '182', '183']
des = {
    'series': S, 'src_page': 17,
    'pattern': 'S <SN|ISN> <size> <C|D|L> <FB|FC> <ratio> <input dims> <output dims> <mounting position> <accessories>',
    'example_in_catalogue': 'S SN 103[sample size box] C FA[sample flange box] 9,78 160x14 250x28 B3 ...',
    'nameplate_example': 'SN183C  i 33,93  B3  (p16)',
    'segments': [
        {'name': 'series', 'values': {'S': 'S series, grey / spheroidal cast iron shaft-mounted gear units'}},
        {'name': 'type', 'values': {'SN': 'geared motor version: set up for motor coupling (motor connections / PAM)', 'ISN': 'gear reducer version with solid input shaft'}},
        {'name': 'size', 'values': {z: ('2 stages' if z[-1] == '2' else '3 stages') + ' cast iron' for z in sizes_all},
         'note': 'last digit = number of reduction stages (2/3; efficiency 0.98 / 0.96, p16); 14x/15x grey cast iron, 16x/18x spheroidal cast iron (p16)'},
        {'name': 'output_shaft_version', 'values': {'C': 'foot-flange / hollow shaft fixing (keyway)', 'D': 'foot-flange / solid shaft fixing D', 'L': 'foot-flange / shrink disc shaft fixing'}, 'src_page': 18},
        {'name': 'output_flange', 'values': {'FB': 'output flange FB (see dimensions_output_flange.csv)', 'FC': 'output flange FC (SN142/143 only)'},
         'note': 'diagram box reads "FA OUTPUT FLANGE" as sample; only FB and FC are listed as options'},
        {'name': 'reduction_ratio', 'values': {'4,28 ... 222,16': 'exact ratios per size, see ratings.csv'}},
        {'name': 'input_dimensions', 'values': {'160x14': 'fitted for motor coupling (PAM flange x bore) - SN', 'ECE (28)': 'input shaft diameter - ISN'}},
        {'name': 'output_dimensions', 'values': {'250x28': 'output dimensions (sample code in the diagram)'}},
        {'name': 'mounting_position', 'values': {k: 'assembly position ' + k for k in ['B3', 'B8', 'B6', 'B7', 'V5', 'V6']},
         'note': 'B3 gives lower oil splash and heating; performance tables are for B3 or similar (p20-21); oil quantities per position p29'},
        {'name': 'accessories', 'values': {'...': 'e.g. backstop device (p41), reaction bolt (p40), shrink disc (p42), assembly/disassembly kit (p43), machine shaft (p44)'}},
    ],
    'terminal_block_position': 'unless otherwise specified supplied with terminal block in position 1 (p20)',
}
with open(os.path.join(OUT, 'designation.json'), 'w') as f:
    json.dump(des, f, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------- images
IMG = os.path.join(OUT, 'images'); os.makedirs(IMG, exist_ok=True)
for f in glob.glob(os.path.join(IMG, '*')):
    os.remove(f)
index = []
def add(img, kind, caption, page, n, size='general'):
    name = f'{S}_{size}_{kind}_p{page}_{n}.png'
    img.save(os.path.join(IMG, name))
    index.append([name, S, size, kind, caption, page, img.width, img.height])

def embedded(page, want):
    """want: dict {object_index_in_page_listing: (kind, caption)} ; images with smask merged on white"""
    lst = subprocess.run(['pdfimages', '-list', '-f', str(page), '-l', str(page), PDF], capture_output=True, text=True).stdout.splitlines()[2:]
    td = tempfile.mkdtemp()
    subprocess.run(['pdfimages', '-png', '-f', str(page), '-l', str(page), PDF, os.path.join(td, 'i')], check=True)
    files = sorted(glob.glob(os.path.join(td, 'i-*.png')))
    info = [l.split() for l in lst]
    n = 0
    for k, row in enumerate(info):
        if row[2] != 'image': continue
        if n in want:
            im = Image.open(files[k]).convert('RGB')
            if k + 1 < len(info) and info[k + 1][2] == 'smask':
                mk = Image.open(files[k + 1]).convert('L').resize(im.size)
                bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=mk); im = bg
            kind, cap = want[n]
            add(im, kind, cap, page, n + 1)
        n += 1
    shutil.rmtree(td)

embedded(1, {0: ('photo', 'Cover: SN shaft mounted geared motor')})
embedded(9, {2: ('photo', 'Shaft mounted gear reducers (S series), product overview')})
embedded(15, {0: ('photo', 'Motor connections sleeve / PAM input assembly')})
embedded(14, {0: ('diagram', 'Service factor chart: load class A/B/C vs hours/day and starts/hour')})
embedded(18, {0: ('drawing', 'Versions SN..C, SN..D, SN..L (foot-flange hollow / solid / shrink disc shaft fixing)')})
embedded(19, {0: ('render', 'Modularity: SN (motor coupling) and ISN (solid input shaft) versions')})
embedded(20, {0: ('render', 'Assembly positions B3 B8 B6 B7 V5 V6'), 1: ('drawing', 'Terminal block positions 1-4')})
embedded(25, {0: ('drawing', 'Radial load on input shaft: Frx formula geometry (a, b, x)')})
embedded(26, {0: ('drawing', 'Radial load on output shaft: Frx formula geometry (a, b, x)')})
embedded(30, {0: ('drawing', 'Dimensional drawing SN142...183 (geared motor, hollow shaft, IEC B5 motor flange)')})
embedded(32, {0: ('drawing', 'Dimensional drawing ISN142...183 (reducer with solid input shaft)')})
embedded(34, {0: ('drawing', 'Shaft end key UNI 6604 - DIN 6885')})
embedded(35, {0: ('drawing', 'Electric motor dimensional drawings B5 / B14')})
embedded(39, {0: ('drawing', 'Output flange FB/FC drawing')})
embedded(40, {0: ('drawing', 'Shaft mounting fastening - reaction bolt')})
embedded(42, {0: ('drawing', 'Hollow output shaft with shrink disc drawing')})
embedded(43, {0: ('drawing', 'Assembling/disassembling kit exploded drawing')})
embedded(44, {0: ('drawing', 'Machine shaft drawing')})
# vector figure: designation diagram p17 (crop) and backstop photos p41 (crop of full-page render)
td = tempfile.mkdtemp()
subprocess.run(['pdftoppm', '-r', '200', '-f', '17', '-l', '17', '-png', PDF, os.path.join(td, 'v')], check=True)
pg = Image.open(glob.glob(os.path.join(td, 'v*.png'))[0]).convert('RGB')
add(pg.crop((int(0.29 * pg.width), int(0.14 * pg.height), int(0.66 * pg.width), int(0.93 * pg.height))), 'diagram',
    'Type designation diagram (S, SN/ISN, size, version, flange, ratio, input/output dims, mounting, accessories)', 17, 1)
subprocess.run(['pdftoppm', '-r', '200', '-f', '41', '-l', '41', '-png', PDF, os.path.join(td, 'b')], check=True)
pg = Image.open(glob.glob(os.path.join(td, 'b*.png'))[0]).convert('RGB')
add(pg.crop((int(0.17 * pg.width), int(0.145 * pg.height), int(0.82 * pg.width), int(0.52 * pg.height))), 'other',
    'Backstop device: clockwise / anti-clockwise rotation versions for S..2 and S..3 (C-D-L)', 41, 2)
shutil.rmtree(td)
index.sort(key=lambda r: (r[5], r[0]))
write_csv('images/index.csv', ['file', 'series', 'size', 'kind', 'caption', 'src_page', 'width_px', 'height_px'], index)
counts['images/index.csv'] = len(index)

# ---------------------------------------------------------------- notes.md
import collections
per = collections.Counter((r[1], r[13]) for r in rat)
g3 = collections.Counter(g.split('n1=')[1].split()[0] for g in gate if g.startswith('G3') and 'reducer' in g)
g3gm = [g for g in gate if g.startswith('G3') and 'gearmotor' in g]
g2 = [g for g in gate if g.startswith('G2')]
dups = [g for g in gate if g.startswith('DUP')]
SPOT = [
 ('p54', 'SN163 22.00kW i=101.03 180L/4', 'n2 14.6, M2 13637, sf 1.0, Fr2 73103', 'match'),
 ('p49', 'SN153 11.00kW i=72.50 160M/4', 'n2 20.3, M2 4922, sf 1.6, Fr2 72832', 'match'),
 ('p56', 'SN163 30.00kW i=13.58 200L/4', 'n2 108.6, M2 2541, sf 4.0, Fr2 86150', 'match'),
 ('p46', 'SN143 4.00kW i=44.27 132M/6a', 'n2 21.9, M2 1653, sf 2.6, Fr2 47819', 'match'),
 ('p47', 'SN143 5.50kW i=44.27 132S/4', 'n2 33.0, M2 1517, sf 2.8, Fr2 48408', 'match'),
 ('p61', 'SN182 75.00kW i=14.77 280S/4', 'n2 100.5, M2 6932, sf 2.6, Fr2 97071', 'match'),
 ('p48', 'SN142 7.50kW i=23.36 132M/4', 'n2 62.7, M2 1104, sf 3.9, Fr2 50149', 'match'),
 ('p76', 'ISN142 725rpm i=11.96', 'Mn2 4030, Pn1 28, n2 121, Fr2 35135', 'match'),
 ('p83', 'ISN183 475rpm i=25.92', 'Mn2 18000, Pn1 36, n2 56, Fr1 20039, Fr2 85446', 'match'),
 ('p65', 'ISN153 2900rpm i=53.99', 'Mn2 8000, Pn1 -, n2 27, Fr1 2582, Fr2 55500', 'match'),
 ('p65', 'ISN152 2900rpm i=7.76', 'Mn2 5010, Pn1 -, n2 187, Fr2 33787', 'match'),
 ('p80', 'ISN143 475rpm i=197.01', 'Mn2 4300, Pn1 1, n2 7, Fr1 3499, Fr2 29600', 'match'),
 ('p70', 'ISN163 1450rpm i=115.03', 'Mn2 13000, Pn1 18, n2 13, Fr1 5167, Fr2 76000', 'match'),
]
N = []
N.append('# SN (shaft mounted, IEC) extraction notes\n')
N.append('Source: sources/catalogs/SN_shaft-mounted.pdf (90 pages, Motovario technical catalogue "S series / SN-ISN", rev. 2024). '
         'All src_page values are 1-based PDF pages (printed page number = PDF page - 2). Script: tools/extract_SN.py (run from repo root; re-creates everything in data/raw/SN/).\n')
N.append('## Page map (PDF pages)\n')
N.append('''| section | PDF pages |
|---|---|
| Contents | 3-5 |
| Company profile / products | 6-10 |
| Symbols and formulas | 11-12 |
| Product selection procedure | 13 |
| Service factor (graph) | 14 |
| Installation | 15 |
| Design features, paint, efficiency | 16 |
| Type: designation / versions / modularity | 17 / 18 / 19 |
| Assembly positions, terminal block | 20 |
| Critical applications | 21 |
| Available motor mounting flanges (per ratio, B5) | 22-23 |
| Output shaft bearings | 24 |
| Radial loads (input p25, output p26) | 25-26 |
| Lubrication (oils 27-28, quantity 29) | 27-29 |
| Dimensions SN / ISN / motor flange | 30 / 32 / 31 |
| Weights | 33 |
| Shaft end keys | 34 |
| Electric motors (dims 35-36, efficiency classes 37, nominal powers 38) | 35-38 |
| Output flange / reaction bolt / backstop / shrink disc / assembly kit / machine shaft | 39 / 40 / 41 / 42 / 43 / 44 |
| Performance: SN geared motors 50 Hz (ratings by motor kW) | 45-63 |
| Performance: ISN reducers 2900 / 1450 / 950 / 725 / 475 / 360 rpm | 64-67 / 68-71 / 72-75 / 76-79 / 80-83 / 84-87 |
| Sales conditions | 88 |
''')
N.append('## Files and row counts\n')
N.append('| file | rows |\n|---|---|')
for k in sorted(counts): N.append(f'| {k} | {counts[k]} |')
N.append('| designation.json | 1 object, 9 segments |')
N.append(f'| images/*.png | {len(index)} (see images/index.csv) |\n')
N.append('## How the tables were parsed\n')
N.append(f'''* ratings.csv: two row families, column `kind`.
  * `kind=gearmotor` (pp.45-63, "5.1 SN geared motors 50 Hz"): pdftotext -layout, one row per printed line (n2, M2, sf, i, reducer, motor size/poles, n1, Fr2); the kW block header gives p1_kw. n1_rpm = actual motor speed printed in the table (e.g. 1450, 1475, 970), not the nominal 1500/1000. `t2_nm` = M2, `fs` = sf, `motor` = e.g. `180L/4`, `motor_frames` = IEC frame number only, `poles` from the motor code. {ngm} rows.
  * `kind=reducer` (pp.64-87, "5.2-5.7 ISN gear reducer", 6 input speeds x sizes ISN142..183): Mn2 -> t2_nm, Pn1 -> p1_kw (blank where printed "-"), Fr1 -> fr1_n, Fr2 -> fr2_n, n1_rpm = speed in the page title (2900/1450/950/725/475/360). `motor_frames` = IEC frames available for that ratio from the per-ratio flange tables on pp.22-23 (B5), word-coordinate parse. {n_red} rows. These tables carry no service factor (`fs` empty): rated torque Mn2 is the nominal torque, compare with Mr2*s.f. (p13).
  * `variant`: reducers = `reducer`; gearmotors = `gearmotor_<kW>kW` (the power is appended so the schema key (series,size,n1_rpm,i,variant) stays unique: several motors of the same speed rate the same ratio at different powers).
  * `stages` derived from the last digit of the size (2 or 3; designation p17 and efficiency p16 define "2 stages / 3 stages").
  * extra columns: kind, motor, poles, fr1_n, n2_calc_rpm (= n1_rpm / i, computed for convenience; n2_rpm is always the printed value).
* designation.json: transcribed from the flow diagram on p17 (it is a figure, no text table).
* dimensions_*: pdfplumber word coordinates (tolerance superscripts such as +0,03/0 go to `<sym>_tol`). The housing table prints the header `S` twice (columns after O3); they are stored as `S` and `S_2` (first likely the dimension R of the drawing - not resolvable from the print). SN142/SN143 etc. share one printed row; it is repeated for each size.
* dimensions_motor_flange.csv (p31): G2/G2S per size and IEC frame group; "/" -> empty (motor not mountable). extra_motor_B5_bore.csv: B5 table (Pm, Dm, bm, tm) of p31; motor_interface.csv: frames that fit at least one ratio of the size (pp.22-23) with Pm and bore Dm (src_page 31 for the flange data; availability per ratio in extra_motor_flange_availability.csv).
* weights.csv (p33): table headed ISN, reducer without motor; the SN geared-motor mass is not printed.
* lubrication.csv (p29): oil quantity (l, approx.) per size and mounting position; oil type from pp.27-28 (units are supplied WITHOUT oil). extra_lubricants.csv: brand table (transcribed by hand from the text layer because cells wrap over lines).
* service_factor.csv (p14): the chart is a raster image. Curves A/B/C were located by pixel analysis (script, 250 dpi render), each daily-hours column (2/8/16/24 h) has its own printed scale. Values are READ FROM THE GRAPH and rounded to 0.05 at the printed tick positions (5,10,20,...,100 starts/h). The x scale of the print is not uniform (5 is closer to 10 than 10 to 20); ticks were taken at the gridline of each label. Treat as +-0.05 approximate; the printed load classes: A uniform (fa<=0.3), B moderate (fa<=3), C heavy (fa<=10), fa=Je/Jm.
* radial_load_params.csv (pp.25-26): a, b, max admissible Fr1 (input) / Fr2 (output) for Frx = Fr*a/(b+x). Per-ratio Fr1/Fr2 are in ratings.csv.
* extra_*: shaft end keys (p34; key tolerances/s not extracted), critical applications (p21), output bearings (p24: 2 = conical roller), efficiency (p16: 0.98 two stages, 0.96 three stages), per-ratio motor flange availability (pp.22-23).
* No thermal-power table exists in this catalogue (the text refers to a "Thermal power" paragraph that is not printed). No backstop torque table (p41 only shows rotation directions). The backstop device, shrink disc (L), reaction bolt, kit and machine-shaft dimensions are in dimensions_*.csv.
* motors.csv (pp.35-38): the catalogue prints ONLY nominal power per frame / poles / series (TS, TH, TP) on p38 (word-coordinate parse; frame cells of the header were matched to the nearest header word), plus efficiency class definitions on p37 (TS=IE1, TH=IE2, TP=IE3). Columns rpm, voltage_v, efficiency_pct, torque_nm, current_a, mass_kg are not printed -> empty. motors_dimensions.csv: body dimensions (p35 frames 63-160S, p36 160M-280M; poles only given from 160M up), and B5/B14 flange tables (variant column) with verbatim symbols; `*` values (L_star..) are the alternative lengths marked with * in the print (valid for TP80B4, SH80B4, HSH80B4, TP90S4, SH90S4, HSH90S4, TP90L4, SH90L4, HSH90L4, TP90S6, TP112M4, TP112M6). Two printed rows each for 250M and 280S/280M differ in shaft D (60/65, 65/75); the print gives no pole assignment, kept as printed.
* images: embedded rasters via pdfimages (soft masks merged on white), vector figures p17/p41 cropped from 200 dpi renders; logos/icons/QR, other series' photos on pp.9-10 and the duplicate motor drawing on p36 were dropped.
''')
N.append('## Quality gates\n')
N.append(f'1. Sizes: every size from the index (SN/ISN 142,143,152,153,162,163,182,183) appears in ratings.csv. Rows per size: ' + ', '.join(f'{k[0]}({k[1]})={v}' for k, v in sorted(per.items())) + '.')
N.append(f'2. Efficiency check t2 = 9550*P1/n2*eta, eta in 0.55-1.0: gearmotor rows -> {len([g for g in g2 if "reducer" not in g])} flagged. Reducer rows: Pn1 is printed as a rounded integer kW (small values such as 1-3 kW are +-0.5 kW rounded) so the check was run with Pn1 +-0.5 and n2 = n1/i; flagged: {len(g2)}:')
for g in g2: N.append('   * ' + g)
N.append(f'3. n2 vs n1/i within 3 %: gearmotor rows: {len(g3gm)} flagged (printed n2 has 1 decimal). **Reducer tables: the printed n2 column is identical on all six speed pages (it equals the 1450 rpm value, n2 = 1450/i), so for the 2900/950/725/475/360 rpm pages the printed n2 does not match n1/i (flag counts per page speed: {dict(g3)}). The printed n2 is kept in `n2_rpm`; the correct n1/i is in `n2_calc_rpm`.** On the 1450 page the {g3.get("1450", 0)} flags are rounding of n2 to integers at low speeds (e.g. 12 vs 11.6).')
N.append(f'4. Duplicate keys (series,size,n1_rpm,i,variant) in ratings.csv: {len(dups)}.')
N.append('5. Script: tools/extract_SN.py.\n')
N.append('## Catalogue anomalies / flags\n')
for f_ in flags: N.append('* ' + f_)
N.append('* The 45.00 kW 225M/4 block (SN152..SN183) is printed identically on PDF pages 58, 59 and 60; only the first (p58) is kept.')
N.append(f'* ratings_rejected.csv ({len(rejected)} rows): reducer rows whose ratio does not exist for that size (copy/paste leftovers: e.g. i=5.66 of ISN162 repeated in ISN163/ISN182/ISN183/ISN142/143/152/153 tables, 26.11 under ISN152, 13.58 under ISN162). Not used.')
N.append('* The p23 SN182 flange table lists ratio 14.02 as last row (a ratio of SN162, not SN182); it is kept as printed in extra_motor_flange_availability.csv and is not a ratio of SN182 in the ratings tables.')
N.append('* Gearmotor sf differs from the reducer approach: sf is the catalogue safety factor of the unit (M2 rated / required), compare with the service factor s.f. of the application (S >= s.f., p12).')
N.append('* Max torque rule p13: peak <= 200 % of Mn2 (2*Mn2). Critical applications p21: SN, 1500<n1<3000 rpm -> code B (check application / contact Motovario) for all sizes.')
N.append('* Catalogue is 50 Hz IEC; 60 Hz correction formulas on p12.\n')
N.append('## Spot-checks against rendered page images (>=10 required)\n')
N.append('| PDF page | row | printed values | result |\n|---|---|---|---|')
for a, b, c, d in SPOT: N.append(f'| {a} | {b} | {c} | {d} |')
N.append('\nAdditionally checked visually: p30 header (two columns printed `S`), p14 service-factor chart curve scale.')
N.append('\n## Open questions\n')
N.append('* Is the reducer n2 column of the 2900/950/725/475/360 rpm tables a catalogue copy error (our assumption) or is n2 meant at 1450? Pn1 values scale roughly with n1, so n2 = n1/i is assumed.')
N.append('* Pn1 on the reducer pages is not always consistent with Mn2*n2/9550/eta at the page speed (e.g. ISN142 i=4.28: 30 kW at 360 rpm vs ~20 kW computed); left as printed.')
N.append('* Meaning of the first of the two `S` columns in the housing dimension table (probably drawing symbol R).')
N.append('* Motor mass / efficiency / current / torque for SN motors are not in this catalogue.')
with open(os.path.join(OUT, 'notes.md'), 'w') as f:
    f.write('\n'.join(N) + '\n')
print('done', counts['ratings.csv'])
