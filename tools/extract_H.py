#!/usr/bin/env python3
"""Extractor for Motovario H series helical catalogue (sources/catalogs/H_helical.pdf).
Run: python3 tools/extract_H.py [step ...]   steps: ratings (default: all implemented steps)
PDF page = printed page + 2.
"""
import csv, json, os, re, sys
import subprocess, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, 'sources/catalogs/H_helical.pdf')
OUT = os.path.join(ROOT, 'data/raw/H')
os.makedirs(OUT, exist_ok=True)
_pages = None
def page_words(p):
    """words of 1-based PDF page p as dicts text,x0,x1,top (pdftotext -bbox; fast)."""
    global _pages
    if _pages is None:
        xml = subprocess.run(['pdftotext', '-bbox', PDF, '-'], capture_output=True, text=True, check=True).stdout
        _pages = []
        rx = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')
        for chunk in xml.split('<page ')[1:]:
            _pages.append([dict(x0=float(m[1]), top=float(m[2]), x1=float(m[3]), bottom=float(m[4]),
                                text=html.unescape(m[5])) for m in rx.finditer(chunk)])
    return _pages[p - 1]

def num(s):
    """catalogue number -> dot-decimal string; '/' '-' -> ''"""
    s = s.strip()
    if s in ('', '/', '-', '–'):
        return ''
    return s.replace(',', '.')

def write_csv(name, header, rows):
    with open(os.path.join(OUT, name), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f'{name}: {len(rows)} rows')

def cluster_rows(words, tol=4):
    rows = []
    for w in sorted(words, key=lambda w: (w['top'], w['x0'])):
        if rows and abs(w['top'] - rows[-1][0]) <= tol:
            rows[-1][1].append(w)
        else:
            rows.append([w['top'], [w]])
    return [sorted(r[1], key=lambda w: w['x0']) for r in rows]

def frames(motor):
    """'100LA/112MR' -> '100;112'; '63A' -> '63'; '90S' -> '90'"""
    out = []
    for m in re.split(r'/', motor):
        mm = re.match(r'(\d+)', m)
        if mm and mm.group(1) not in out:
            out.append(mm.group(1))
    return ';'.join(out)

# ---------------------------------------------------------------- ratings
RED_SECTIONS = [(205, 218, 1750), (219, 232, 1400), (233, 246, 1140),
                (247, 260, 900), (261, 274, 700), (275, 288, 500)]
HDR = ['series', 'size', 'stages', 'n1_rpm', 'p1_kw', 'i', 'n2_rpm', 't2_nm', 'fs', 'fr2_n',
       'motor_frames', 'variant', 'src_page', 'fr1_n', 'motor_size', 'poles', 'n1_implied_rpm', 'brake_motor_only']

def ratings():
    rows = []
    numre = re.compile(r'^\d+(,\d+)?$')
    # --- geared motors p.77-204
    for p in range(77, 205):
        words = page_words(p)
        kw = None
        for r in cluster_rows(words):
            txt = [w['text'] for w in r]
            if 'kW' in txt and len(txt) == 2 and numre.match(txt[0]):
                kw = num(txt[0]); continue
            if len(r) < 8 or not all(numre.match(t) for t in txt[:4]):
                continue
            # tokens: n2 M2 fs i reducer motor... pole fr2
            n2, m2, fs, i = [num(t) for t in txt[:4]]
            red = txt[4]
            fr2 = txt[-1]; pole = txt[-2]
            motor = ''.join(txt[5:-2])
            brake = '(1)' in motor
            motor = motor.replace('(1)', '')
            rows.append(dict(size=red, n1_rpm='', p1_kw=kw, i=i, n2_rpm=n2, t2_nm=m2, fs=fs, fr2_n=fr2,
                             motor_frames=frames(motor), variant='gearmotor', src_page=p, fr1_n='',
                             motor_size=motor, poles=pole, brake=brake, ycl=r[0]['top']))
        # attach orphan "(1)" tokens (separate y-line slightly offset) -- handled via cluster tol
    # --- reducers p.205-288
    for a, b, n1 in RED_SECTIONS:
        for p in range(a, b + 1):
            words = page_words(p)
            size = None
            for r in cluster_rows(words):
                txt = [w['text'] for w in r]
                if len(txt) == 1 and re.fullmatch(r'IHA?\d+', txt[0]):
                    size = txt[0]; continue
                if len(txt) == 6 and all(numre.match(t) for t in txt):
                    mn2, i, pn1, n2, fr1, fr2 = [num(t) for t in txt]
                    rows.append(dict(size=size, n1_rpm=n1, p1_kw=pn1, i=i, n2_rpm=n2, t2_nm=mn2, fs='',
                                     fr2_n=fr2, motor_frames='', variant='reducer', src_page=p, fr1_n=fr1,
                                     motor_size='', poles='', brake=False))
    out = []
    for r in rows:
        r['stages'] = r['size'][-1]
        if r['variant'] == 'gearmotor':
            r['n1_implied_rpm'] = str(round(float(r['n2_rpm']) * float(r['i'])))
        else:
            r['n1_implied_rpm'] = ''
        out.append([ 'H', r['size'], r['stages'], r['n1_rpm'], r['p1_kw'], r['i'], r['n2_rpm'], r['t2_nm'],
                     r['fs'], r['fr2_n'], r['motor_frames'], r['variant'], r['src_page'], r['fr1_n'],
                     r['motor_size'], r['poles'], r['n1_implied_rpm'], '1' if r['brake'] else ''])
    write_csv('ratings.csv', HDR, out)


# ---------------------------------------------------------------- generic dimension-table parser
SYM = re.compile(r'^(~?[A-Za-z]{1,3}\d?|j6|f8|k6|f7|h6|H7|Pm|Dm|bm|tm)$')
LABEL = re.compile(r'^(IHA|IHR|CHA|CHR|HA|HR|IH|CH|PH|H)\d{2,3}[0-9/.A-Z-]*$')
FRAME = re.compile(r'^\d{3}[SLMA]{0,2}$')
OPT_ALL = ('D j6', 'D', 'B', 'b', 't', 'f')
FRAME_OUT = []

def is_header(r):
    toks = [w['text'] for w in r]
    ok = [t for t in toks if SYM.match(t)]
    return len(ok) >= 4 and len(ok) >= 0.6 * len(toks) and not any(re.match(r'^\d', t) for t in toks)

def is_frame_header(r):
    return sum(1 for w in r if FRAME.match(w['text']) and w['text'].startswith('0')) >= 3

def merge_header(r):
    cols = []
    for w in r:
        if not SYM.match(w['text']):
            continue
        if cols and w['x0'] - cols[-1]['x1'] < 9 and w['text'] in ('j6', 'f8', 'k6', 'f7', 'h6', 'H7'):
            cols[-1]['text'] += ' ' + w['text']; cols[-1]['x1'] = w['x1']
        else:
            cols.append(dict(w))
    return [(c['text'], (c['x0'] + c['x1']) / 2) for c in cols]

def join_vals(items):
    d = {}
    for vals in items:
        for k, v in vals.items():
            d[k] = (d[k] + ' ' + v) if k in d else v
    return d

def flush_frame(blockrows, block):
    """compact-motor X/Y/Z length tables (T | TB side by side) -> FRAME_OUT"""
    cyc = []
    for y, t, vals in blockrows:
        sym = vals.get('_sym', '')
        if sym == 'X' or not cyc:
            cyc.append([])
        cyc[-1].append((y, t, vals))
    for c in cyc:
        lab = ';'.join(sorted({t for y, t, _ in c if t}))
        cur = ''
        for y, t, vals in c:
            sym = vals.get('_sym', '')
            if sym in ('X', 'Y', 'Z'): cur = sym; star = ''
            else: star = '*'
            for k, v in vals.items():
                if k == '_sym': continue
                side = 'TB' if k.startswith('TB:') else 'T'
                FRAME_OUT.append(dict(block=block, size=lab, side=side, frame=k.split(':')[-1], sym=cur + star, value=v))

def parse_dim_page(p):
    """Position-based parser of the dimension tables of one page (stops at the IEC/G2 table).
    Returns [dict(block,size,cols{symbol:value},kind)]: one dict per size (and per shaft/flange option)."""
    rows = cluster_rows(page_words(p), tol=3)
    out = []; block = 0; cols = None; blockrows = []; kind = ''; first_x = 0; stop = False
    def flush():
        nonlocal blockrows
        if cols and blockrows:
            names = [c[0] for c in cols]
            labels = [(y, t) for y, t, _ in blockrows if t]
            if kind == 'frame':
                flush_frame(blockrows, block); blockrows = []; return
            if 'M1' in names and 'M2' in names and 'NF f8' in names: det = 'flange'
            elif 'NF f8' in names and 'G' in names and 'P' in names: det = 'P'
            elif ('D j6' in names or 'D' in names) and 'b' in names and 't' in names and 'f' in names and 'E' in names: det = 'D j6' if 'D j6' in names else 'D'
            else: det = None
            groups = {}; gi = 0
            for y, t, vals in blockrows:
                if not vals and not t: continue
                if det == 'flange':
                    if vals.get('flange') == 'FA': gi += 1
                    key = (gi, None)
                else:
                    key = min(labels, key=lambda l: abs(l[0] - y)) if labels else (0, '')
                groups.setdefault(key, []).append((y, t, vals))
            for (ly, lab), items in sorted(groups.items(), key=lambda kv: kv[0][0]):
                if det == 'flange':
                    lab = ';'.join(t for _, t, _ in items if t)
                    optrows = [v for _, _, v in items if 'flange' in v]
                    common = join_vals(v for _, _, v in items if 'flange' not in v)
                elif det is None:
                    out.append(dict(block=block, size=lab, cols=join_vals(v for _, _, v in items), kind=kind)); continue
                else:
                    optkeys = ('P', 'M', 'NF f8') if det == 'P' else OPT_ALL
                    optrows = []; rest = []
                    for y, t, v in items:
                        o = {k: x for k, x in v.items() if k in optkeys}
                        r_ = {k: x for k, x in v.items() if k not in optkeys}
                        if det in o:
                            optrows.append(o); rest.append(r_)
                        else:
                            rest.append(v)
                    common = join_vals(rest)
                for o in (optrows or [{}]):
                    d = dict(o)
                    for k, v in common.items(): d.setdefault(k, v)
                    out.append(dict(block=block, size=lab, cols=d, kind=kind))
        blockrows = []
    for r in rows:
        y = r[0]['top']
        if y < 70 or y > 800 or stop:
            continue
        toks = [w['text'] for w in r]
        if 'IEC' in toks and kind != 'frame':
            flush(); cols = None; stop = True; continue
        if any('IE1' in t for t in toks) or toks[0].startswith('*TP'):
            continue
        if is_header(r) or is_frame_header(r):
            flush(); block += 1
            if is_frame_header(r):
                cols0 = [(w['text'], (w['x0'] + w['x1']) / 2) for w in r
                         if FRAME.match(w['text']) and (w['text'].startswith('0') or w['text'][0] == '1')]
                res = []; seenn = set()
                for n, x in cols0:
                    if n in seenn: n = 'TB:' + n
                    else: seenn.add(n)
                    res.append((n, x))
                if any(n.startswith('TB:') for n, _ in res):
                    res = [(('T:' + n) if not n.startswith('TB:') else n, x) for n, x in res]
                cols = res; kind = 'frame'; first_x = min(x for _, x in res)
            else:
                cols = merge_header(r); kind = 'sym'; first_x = min(c[1] for c in cols)
            continue
        if not cols: continue
        vals = {}; label = ''
        for w in r:
            xc = (w['x0'] + w['x1']) / 2; t = w['text']
            if kind == 'frame':
                if t in ('X', 'Y', 'Z'):
                    vals.setdefault('_sym', t); continue
                if LABEL.match(t):
                    label = label or t; continue
            if w['x1'] < first_x - 12 and LABEL.match(t) and not re.match(r'^F[A-D]$', t):
                label = t; continue
            if kind == 'sym' and re.match(r'^F[A-D]$', t) and any(n == 'M1' for n, _ in cols):
                vals['flange'] = t; continue
            name = min(cols, key=lambda c: abs(c[1] - xc))[0]
            vals[name] = (vals.get(name, '') + ' ' + t).strip()
        blockrows.append((y, label, vals))
    flush()
    return out

# ---------------------------------------------------------------- dimension files
def dims():
    fams = {  # file -> [(page, section)]
        'dimensions_HA.csv': [(38, 'HA31'), (39, 'HA.1'), (43, 'HA.2'), (49, 'HA.3')],
        'dimensions_CHA.csv': [(40, 'CHA.1'), (45, 'CHA.2'), (51, 'CHA.3')],
        'dimensions_IHA.csv': [(41, 'IHA.1'), (47, 'IHA.2'), (53, 'IHA.3')],
        'dimensions_HR.csv': [(55, 'HR..1'), (57, 'CHR..1'), (59, 'IHR..1')],
        'dimensions_H.csv': [(61, 'H..2/3'), (63, 'CH..2/3'), (65, 'IH..2/3')],
    }
    for fname, pages in fams.items():
        rows = []; colset = []
        for pg, sec in pages:
            FRAME_OUT.clear()
            for r in parse_dim_page(pg):
                c = r['cols']
                for k in c:
                    if k not in colset: colset.append(k)
                rows.append(dict(size=r['size'], variant=f"{sec} table{r['block']}", cols=c, page=pg))
            for f in FRAME_OUT:
                for k in ('sym', 'frame', 'motor_type'):
                    if k not in colset: colset.append(k)
                rows.append(dict(size=f['size'], variant=f"{sec} compact-motor length X/Y/Z", page=pg,
                                 cols={'sym': f['sym'], 'frame': f['frame'], 'motor_type': f['side'], 'X/Y/Z value': f['value']}))
                if 'X/Y/Z value' not in colset: colset.append('X/Y/Z value')
        out = [['H', r['size'], r['variant']] + [r['cols'].get(k, '') for k in colset] + [r['page']] for r in rows]
        write_csv(fname, ['series', 'size', 'variant'] + colset + ['src_page'], out)


# ---------------------------------------------------------------- IEC input flange (Pm x Dm, G2) + B5/B14 motor-flange dims
IEC_FRAMES = {'063', '071', '080', '090', '100', '112', '132', '160', '180', '200', '225'}
IEC_PAGES = list(range(38, 40)) + list(range(43, 66, 2))

def iec_tables():
    g2rows = []; b5 = {}; hdr_rows = {}
    for p in IEC_PAGES:
        rows = cluster_rows(page_words(p), tol=3)
        xb5 = None; yb5 = None; xb14 = None
        for r in rows:
            for w in r:
                if w['text'] == 'B5' and w['x0'] > 250 and w['top'] > (150 if p == 38 else 300) and xb5 is None: xb5 = w['x0']; yb5 = w['top']
                if w['text'] == 'B14' and w['x0'] > 400 and w['top'] > 300 and xb14 is None: xb14 = w['x0']
        iec_y = next((r[0]['top'] for r in rows if any(w['text'] == 'IEC' for w in r) and r[0]['top'] > 70), None)
        if xb5 is None or iec_y is None: continue
        hdr = []; first_data = False
        for r in rows:
            if r[0]['top'] < min(yb5, iec_y) - 25: continue
            right = [w['text'] for w in r if w['x0'] >= xb5 - 8]
            if len(right) >= 5 and right[0] in IEC_FRAMES and re.match(r'^\d', right[1]):
                b5.setdefault((right[0], 'B5'), (right[1:5], p))
                if len(right) >= 10 and right[5] in IEC_FRAMES:
                    b5.setdefault((right[5], 'B14'), (right[6:10], p))
            left = [w for w in r if w['x1'] < xb5 - 8]
            lt = [w['text'] for w in left]
            if len(lt) >= 2 and (re.match(r'^\d{3}(-\d{3})?-?$', lt[0])) and re.match(r'^\d+[xX]\d+$', lt[1]):
                first_data = True
                pmdm = [t for t in lt[1:] if re.match(r'^\d+[xX]\d+$', t)]
                vals = [t for t in lt[1:] if t not in pmdm]
                g2rows.append(dict(page=p, iec='100-112' if lt[0].startswith('100-') else lt[0], pmdm=';'.join(pmdm), g2=';'.join(vals)))
            elif not first_data and lt and r[0]['top'] >= iec_y - 14:
                hdr.append(' '.join(lt))
        hdr_rows[p] = ' | '.join(h for h in hdr if h)
    return g2rows, b5, hdr_rows

def iec():
    g2rows, b5, hdr = iec_tables()
    write_csv('extra_input_g2.csv', ['series', 'iec_frame', 'pm_x_dm_options', 'g2_values_as_printed_left_to_right', 'g2_column_header_text', 'src_page'],
              [['H', r['iec'], r['pmdm'], r['g2'], hdr.get(r['page'], ''), r['page']] for r in g2rows])
    write_csv('extra_motor_flange_dims.csv', ['series', 'flange', 'iec_frame', 'Pm', 'Dm', 'bm', 'tm', 'src_page'],
              [['H', k[1], k[0]] + [num(x) for x in v[0]] + [v[1]] for k, v in sorted(b5.items(), key=lambda kv: (kv[0][1], kv[0][0]))])

# ---------------------------------------------------------------- motor flange availability (pp 26-30)
AV_PAGES = range(26, 31)

def availability():
    out = []
    for p in AV_PAGES:
        rows = cluster_rows(page_words(p), tol=3)
        hdr = [(i, r) for i, r in enumerate(rows) if sum(1 for w in r if re.match(r'^\*?\d{3}$', w['text'])) >= 2 and any(w['text'] == 'i' for w in r)]
        for hi, hr in hdr:
            ix = [w['x0'] for w in hr if w['text'] == 'i']
            bounds = [x - 70 if p == 26 else x - 15 for x in ix] + [10000]
            for t in range(len(ix)):
                lo, hi_x = bounds[t], bounds[t + 1]
                frames_ = [(w['text'].lstrip('*'), (w['x0'] + w['x1']) / 2) for w in hr if lo <= w['x0'] < hi_x and re.match(r'^\*?\d{3}$', w['text'])]
                title = ''
                if p != 26:
                    prev = rows[hi - 1]
                    title = ' '.join(w['text'] for w in prev if lo <= w['x0'] < hi_x)
                for r in rows[hi + 1:]:
                    if r[0]['top'] <= hr[0]['top']: continue
                    if any(w['text'] == 'i' for w in r) and r is not hr and sum(1 for w in r if re.match(r'^\*?\d{3}$', w['text'])) >= 2: break
                    ws = [w for w in r if lo <= w['x0'] < hi_x]
                    if not ws: continue
                    if p == 26:
                        lab = []; ivals = []; cells = []
                        for w in ws:
                            tx = w['text']
                            if re.match(r'^B\d', tx): cells.append(w)
                            elif tx == '÷': continue
                            elif re.match(r'^[\d,]+$', tx): ivals.append(num(tx))
                            else: lab.append(tx)
                        if not cells: continue
                        size = ''.join(lab); fam = size
                        if size.startswith('CH'): size = 'CH' + size[2:]
                        i_from, i_to = ivals[0], ivals[-1]
                    else:
                        if not re.match(r'^[\d,]+$', ws[0]['text']): continue
                        ivals = [num(ws[0]['text'])]; i_from = i_to = ivals[0]
                        cells = [w for w in ws[1:] if re.match(r'^B\d', w['text'])]
                        m = re.search(r'(\d{3})\s*$', title)
                        pre = 'HR' if 'HR' in title else 'H'
                        size = pre + (m.group(1) if m else '')
                        if 'CHR' in title: pass
                    for w in cells:
                        xc = (w['x0'] + w['x1']) / 2
                        fr = min(frames_, key=lambda f: abs(f[1] - xc))[0]
                        out.append(['H', size, i_from, i_to, fr, w['text'], p])
    write_csv('extra_motor_flange_availability.csv', ['series', 'size', 'i_from', 'i_to', 'iec_frame', 'flange_codes', 'src_page'], out)
    return out

def motor_interface():
    av = list(csv.DictReader(open(os.path.join(OUT, 'extra_motor_flange_availability.csv'))))
    fl = {(r['iec_frame'], r['flange']): r for r in csv.DictReader(open(os.path.join(OUT, 'extra_motor_flange_dims.csv')))}
    agg = {}
    for r in av:
        k = (r['size'], r['iec_frame'])
        agg.setdefault(k, {'codes': set(), 'pages': set()})
        agg[k]['codes'].update(r['flange_codes'].split('-')); agg[k]['pages'].add(r['src_page'])
    out = []
    for (size, fr), v in sorted(agg.items()):
        codes = sorted(v['codes'])
        for c in codes:
            ref = 'B5' if c in ('B5', 'B11', 'B10') else 'B14'
            d = fl.get((fr, ref)) or fl.get((fr.lstrip('0'), ref))
            bore = d['Dm'] if d else ''
            out.append(['H', size, fr, c, bore, ';'.join(sorted(v['pages']))])
    write_csv('motor_interface.csv', ['series', 'size', 'iec_frame', 'flange', 'bore_mm', 'src_page'], out)


# ---------------------------------------------------------------- weights (pp 66-67)
def wlabel(prefix, lab):
    return prefix + lab

def weights():
    out = []
    # page 66 left: reducers with motor flange (H-PH) by IEC frame, right: IH reducers
    rows = cluster_rows(page_words(66), tol=3)
    hdr = next(r for r in rows if any(w['text'] == '063' for w in r) and any(w['text'] == '225' for w in r))
    cols = [(w['text'], (w['x0'] + w['x1']) / 2) for w in hdr if re.match(r'^\d{3}', w['text']) and w['x0'] < 400]
    for r in rows:
        if r[0]['top'] <= hdr[0]['top'] + 3 or r[0]['top'] > 790: continue
        left = [w for w in r if w['x0'] < 400]; right = [w for w in r if w['x0'] >= 400]
        if left and re.match(r'^(A\d\d|\d{3}-\d{3}|R\d{3})$', left[0]['text']):
            size = wlabel('H', left[0]['text'])
            for w in left[1:]:
                fr = min(cols, key=lambda c: abs(c[1] - (w['x0'] + w['x1']) / 2))[0]
                v = num(w['text'])
                if v != '': out.append(['H', size, 'H-PH reducer (with motor flange for IEC frame, without motor)', fr, v, 66])
        if len(right) == 2 and re.match(r'^(A\d\d|\d{3}-\d{3}|R\d{3})$', right[0]['text']):
            out.append(['H', wlabel('IH', right[0]['text']), 'IH input-shaft reducer (without motor)', '', num(right[1]['text']), 66])
    # page 67: geared motors CH + motor type
    rows = cluster_rows(page_words(67), tol=3)
    titles = []
    for i, r in enumerate(rows):
        txt = [w['text'] for w in r]
        if txt and txt[0] in ('TH', 'TP') and len(txt) == 2:
            titles.append((i, txt))
    for ti, (i, txt) in enumerate(titles):
        end = titles[ti + 1][0] if ti + 1 < len(titles) else len(rows)
        hdr = rows[i + 1]
        lcols = [(w['text'], (w['x0'] + w['x1']) / 2) for w in hdr if w['text'] != 'CH' and w['x0'] < 300]
        rcols = [(w['text'], (w['x0'] + w['x1']) / 2) for w in hdr if w['text'] != 'CH' and w['x0'] >= 300]
        for r in rows[i + 2:end]:
            if r[0]['top'] > 790: continue
            left = [w for w in r if w['x0'] < 300]; right = [w for w in r if w['x0'] >= 300]
            for side, cols, mt in ((left, lcols, txt[0]), (right, rcols, txt[1])):
                if side and re.match(r'^(A\d\d|\d{3}-\d{3}|R\d{3})$', side[0]['text']):
                    size = wlabel('CH', side[0]['text'])
                    for w in side[1:]:
                        fr = min(cols, key=lambda c: abs(c[1] - (w['x0'] + w['x1']) / 2))[0]
                        v = num(w['text'])
                        if v != '': out.append(['H', size, f'CH compact geared motor with {mt} motor', fr, v, 67])
    write_csv('weights.csv', ['series', 'size', 'variant', 'motor_frame', 'mass_kg', 'src_page'], out)

# ---------------------------------------------------------------- lubrication (p 36)
def lubrication():
    rows = cluster_rows(page_words(36), tol=3)
    out = []
    # table 1: HA series (H - CH). Merged cells -> values per printed spec (verified on page image)
    pos_all = 'B3-B5;B8;B6-B7;V5-V1;V6-V3'.split(';')
    single = {'HA31': '0.07', 'HA41': '0.23', 'CHA41': '0.13', 'HA51': '0.25', 'HA61': '0.62', 'HA32': '0.68', 'HA42': '0.7', 'HA33': '1.1', 'HA43': '1.16'}
    for size, v in single.items():
        for pos in pos_all:
            out.append(['H', size, pos, v, '', 36])
    two = {'HA52': ('1.2', '1.6'), 'HA62': ('1.9', '2.1'), 'HA53': ('1.9', '2.5'), 'HA63': ('2.4', '3.1')}
    for size, (a, b) in two.items():
        for pos in pos_all[:3]: out.append(['H', size, pos, a, '', 36])
        for pos in pos_all[3:]: out.append(['H', size, pos, b, '', 36])
    # tables 2,3: parse by words
    hdrs = [i for i, r in enumerate(rows) if r[0]['top'] > 300 and sum(1 for w in r if re.match(r'^(HR|CHR|H|CH)$|^\d{3}M?(/\d{3})?$', w['text'])) >= 5 or any(w['text'] in ('041', '032/033') for w in r)]
    def read_table(hi, prefix_fn):
        hr = rows[hi]
        cols = [(w['text'], (w['x0'] + w['x1']) / 2) for w in hr if re.match(r'^\d{3}M?(/\d{3})?$', w['text'])]
        res = []
        for r in rows[hi + 1:]:
            lab = r[0]['text']
            if re.match(r'^(B3-B5|B5R|B8|B6-B7|V5-V1|V6-V3)$', lab):
                for w in r[1:]:
                    v = num(w['text'])
                    c = min(cols, key=lambda c: abs(c[1] - (w['x0'] + w['x1']) / 2))[0]
                    if v != '': res.append((c, lab, v))
            elif res and re.match(r'^V6-V3$', lab) is None and lab not in ('B3-B5',) and r[0]['top'] > rows[hi][0]['top'] + 20 and not re.match(r'^(B3-B5|B5R|B8|B6-B7|V5-V1|V6-V3)$', lab):
                break
        return res
    for i, r in enumerate(rows):
        txt = [w['text'] for w in r]
        if '041' in txt and '041M' in txt:
            for c, lab, v in read_table(i, None):
                out.append(['H', 'HR' + c if not c.endswith('M') else 'HR' + c, lab, v, '', 36])
        if '032/033' in txt:
            for c, lab, v in read_table(i, None):
                for z in c.split('/'):
                    out.append(['H', 'H' + (z if len(z) == 3 else c[:1] + z), lab, v, '', 36])
    # fix size naming for 032/033 style (e.g. 032/033 -> H032,H033)
    fixed = []
    for r_ in out:
        fixed.append(r_)
    oil = 'ISO VG220 mineral (standard, Tamb -5..+40 C) / ISO VG150 (Tamb -15..+25 C); see notes'
    for r_ in fixed: r_[4] = oil
    write_csv('lubrication.csv', ['series', 'size', 'mounting_position', 'oil_l', 'oil_type', 'src_page'], fixed)

# ---------------------------------------------------------------- thermal, radial load, inertia, factors, misc small tables
def small_tables():
    # thermal power p.24 (n1=1500)
    rows = cluster_rows(page_words(24), tol=3)
    out = []
    for r in rows:
        t = [w['text'] for w in r]
        if r[0]['top'] < 120 or r[0]['top'] > 330: continue
        for k in range(0, len(t) - 1):
            if re.match(r'^(HA|HR|H)\d{3}$', t[k]):
                out.append(['H', t[k], 'Pth at n1=1500 rpm, B3, Tamb 25C, v>=1 m/s', num(t[k + 1]), 24])
    write_csv('thermal.csv', ['series', 'size', 'variant', 'pth_kw', 'src_page'], out)
    # thermal correction factors (p.24)
    fc = [[10, '1.15', '1.21', '1.32', '1.55', '2.07'], [18, '1.07', '1.12', '1.23', '1.44', '1.93'], [25, '1.00', '1.05', '1.15', '1.35', '1.80'],
          [30, '0.93', '0.98', '1.07', '1.26', '1.67'], [40, '0.83', '0.87', '0.95', '1.12', '1.49'], [43, '0.75', '0.79', '0.86', '1.01', '1.35'],
          [50, '0.67', '0.70', '0.77', '0.90', '1.21']]
    o = []
    for r in fc:
        for d, v in zip((100, 80, 70, 40, 20), r[1:]): o.append(['H', 'Fc ambient temperature', f'T_amb={r[0]}C;duty={d}%', v, 24])
    for a, v in ((0, '1'), (750, '0.95'), (1500, '0.9'), (2250, '0.85'), (3000, '0.81')): o.append(['H', 'Fa altitude', f'altitude={a}m', v, 24])
    for n, v in (('stagnant air (<0.5 m/s)', '0.75'), ('indoor, slight ventilation', '1'), ('indoor, good ventilation (>1.4 m/s)', '1.4'), ('outdoor (>3.7 m/s)', '1.9')):
        o.append(['H', 'Fv ventilation', n, v, 24])
    write_csv('extra_thermal_correction_factors.csv', ['series', 'factor', 'condition', 'value', 'src_page'], o)
    # radial load p.32-33 (a, b, Fr max)
    o = []
    def grp(page, ytop, ybot):
        rr = [r for r in cluster_rows(page_words(page), tol=3) if ytop <= r[0]['top'] <= ybot]
        return rr
    for page in (32, 33):
        rows = cluster_rows(page_words(page), tol=3)
        i = 0
        while i < len(rows):
            r = rows[i]; t = [w['text'] for w in r]
            if t and re.match(r'^(IHR|IH|HR|H)$', t[0]) and len(t) >= 3 and re.match(r'^[A\d]', t[1]):
                names = t[1:]; ctx = t[0]
                data = {}
                for rr in rows[i + 1:i + 5]:
                    tt = [w['text'] for w in rr]
                    if tt and tt[0] in ('a', 'b', 'Fr1', 'Fr2', 'Fa'):
                        key = tt[0]
                        if key.startswith('Fr'): key = tt[0] + ' max'
                        if key == 'Fa': key = 'Fa max'
                        vals = [x for x in tt[1:] if re.match(r'^[\d,]+$', x)] if tt[0] not in ('Fr1', 'Fr2', 'Fa') else [x for x in tt if re.match(r'^[\d,]+$', x)]
                        data[key] = vals
                    elif tt and tt[0] == 'Fa':
                        pass
                # expand 'A32/A33/...' style names
                exp = []
                for n in names:
                    if '/' in n:
                        parts = n.split('/')
                        for pt in parts:
                            exp.append(pt)
                    else: exp.append(n)
                if page == 32 and ctx == 'IH' and names and names[0].startswith('A'): pass
                kind = 'input Fr1 (p.32)' if page == 32 else 'output Fr2 (p.33)'
                for k, nm in enumerate(names):
                    for key, vals in data.items():
                        if k < len(vals):
                            pref = ctx
                            o.append(['H', f'{pref} {nm}', kind, key, num(vals[k]), page])
            i += 1
    write_csv('radial_load_formula_params.csv', ['series', 'size_group', 'shaft', 'parameter', 'value', 'src_page'], o)
    # inertia p.37
    rows = cluster_rows(page_words(37), tol=3); o = []
    for r in rows:
        t = [w['text'] for w in r]
        if r[0]['top'] < 120: continue
        left = [w for w in r if w['x0'] < 300]; right = [w for w in r if w['x0'] >= 300]
        for side, grp_ in ((left, None), (right, None)):
            if len(side) == 2 and re.match(r'^[A\d]', side[0]['text']) and re.match(r'^[\d,]+$', side[1]['text']):
                o.append(['H', side[0]['text'], 'J1 moment of inertia at input [kg*m2] (estimated)', num(side[1]['text']), 37])
    write_csv('extra_inertia.csv', ['series', 'size_group', 'variant', 'j1_kgm2', 'src_page'], o)


# ---------------------------------------------------------------- electric motors (pp 69-72)
EFF = {'TS': 'IE1', 'TH': 'IE2', 'SH': 'IE2', 'HSH': 'IE2', 'TP': 'IE3'}  # p.71 text

def nearest(cols, x):
    return min(cols, key=lambda c: abs(c[1] - x))[0]

def assign(cols, ws, skip_first=True):
    d = {}
    for w in ws:
        xc = (w['x0'] + w['x1']) / 2
        n = nearest(cols, xc)
        d[n] = (d[n] + ' ' + w['text']) if n in d else w['text']
    return d

def motors():
    # ---- power table p.72 -> motors.csv
    rows = cluster_rows(page_words(72), tol=3)
    out = []
    for i, r in enumerate(rows):
        if r and r[0]['text'] == 'P.' and i > 0:
            fr = [(w['text'], (w['x0'] + w['x1']) / 2) for w in rows[i - 1] if re.match(r'^\d{2,3}[A-Z]*$', w['text'])]
            types = [(w['text'], (w['x0'] + w['x1']) / 2) for w in r[1:]]
            tf = [(t, x, nearest(fr, x)) for t, x in types]
            for pr in rows[i + 1:i + 4]:
                if pr[0]['text'] not in ('2', '4', '6'): break
                poles = pr[0]['text']
                for w in pr[1:]:
                    v = num(w['text'])
                    if v == '': continue
                    xc = (w['x0'] + w['x1']) / 2
                    t, x, f = min(tf, key=lambda q: abs(q[1] - xc))
                    out.append(['H', t, f, poles, v, '', '', EFF[t], '', '', '', '', 72])
    out.sort(key=lambda r: (r[2], r[3], r[1]))
    write_csv('motors.csv', ['series', 'motor_type', 'frame', 'poles', 'power_kw', 'rpm', 'voltage_v', 'efficiency_class',
                             'efficiency_pct', 'torque_nm', 'current_a', 'mass_kg', 'src_page'], out)
    # ---- dimensions p.69/70 -> motors_dimensions.csv
    recs = []; cols_all = []
    def add(variant, frame, d, page, poles=''):
        for k in d:
            if k not in cols_all: cols_all.append(k)
        recs.append((variant, frame, poles, d, page))
    rows = cluster_rows(page_words(69), tol=3)
    hdr = next(r for r in rows if r[0]['text'] == 'AC')
    cols = [(w['text'], (w['x0'] + w['x1']) / 2) for w in hdr]
    cur = None
    for r in rows:
        if r[0]['top'] <= hdr[0]['top'] + 3: continue
        t0 = r[0]['text']
        if t0 == 'B5': break
        if re.match(r'^\d{2,3}[SLM]?$', t0) and r[0]['x0'] < 70:
            cur = t0
            ws = r[1:]
            # merge tolerance token into D
            d = {}
            for w in ws:
                n = nearest(cols, (w['x0'] + w['x1']) / 2)
                d[n] = (d[n] + ' ' + w['text']) if n in d else w['text']
            add('IEC motor body (B3 foot dimensions as printed)', cur, {k: v for k, v in d.items()}, 69)
        elif t0.startswith('*') and cur and re.match(r'^\*[\d,]+$', t0):
            d = assign(cols, r)
            add('body, values marked * (TP80B4,SH80B4,HSH80B4,TP90S4,SH90S4,HSH90S4,TP90L4,SH90L4,HSH90L4,TP90S6,TP112M4,TP112M6)', cur, d, 69)
    # B5 / B14 on p.69
    hb = next(r for r in rows if r[0]['text'] == 'B5')
    xs14 = next(w['x0'] for w in hb if w['text'] == 'B14')
    lc = [(w['text'], (w['x0'] + w['x1']) / 2) for w in hb if w['x0'] < xs14 - 5 and w['text'] != 'B5']
    rc = [(w['text'], (w['x0'] + w['x1']) / 2) for w in hb if w['x0'] > xs14 + 5]
    for r in rows:
        if r[0]['top'] <= hb[0]['top'] + 3 or r[0]['top'] > 790: continue
        l = [w for w in r if w['x0'] < xs14 - 5]; rr = [w for w in r if w['x0'] >= xs14 - 5]
        if l and re.match(r'^\d{2,3}$', l[0]['text']): add('B5 flange', l[0]['text'], assign(lc, l[1:]), 69)
        if rr and re.match(r'^\d{2,3}$', rr[0]['text']): add('B14 flange', rr[0]['text'], assign(rc, rr[1:]), 69)
    # page 70
    rows = cluster_rows(page_words(70), tol=3)
    hdr = next(r for r in rows if r[0]['text'] == 'AC')
    cols = [(w['text'], (w['x0'] + w['x1']) / 2) for w in hdr]
    hb = next(r for r in rows if r[0]['text'] == 'B5')
    bc = [(w['text'], (w['x0'] + w['x1']) / 2) for w in hb if w['text'] != 'B5']
    for r in rows:
        if r[0]['top'] <= hdr[0]['top'] + 3 or r[0]['top'] > 790: continue
        t0 = r[0]['text']
        if r[0]['top'] < hb[0]['top'] - 5 and re.match(r'^\d{3}[LMS]$', t0):
            poles = r[1]['text'] if re.match(r'^[246](-[246])*$', r[1]['text']) else ''
            add('IEC motor body', t0, assign(cols, r[2:] if poles else r[1:]), 70, poles)
        elif r[0]['top'] > hb[0]['top'] + 3 and re.match(r'^\d{3}$', t0):
            add('B5 flange', t0, assign(bc, r[1:]), 70)
    out = []
    for variant, frame, poles, d, page in recs:
        out.append(['H', variant, frame, poles] + [num(d.get(k, '')) if re.match(r'^[\d,*]+$', d.get(k, 'x')) else d.get(k, '') for k in cols_all] + [page])
    write_csv('motors_dimensions.csv', ['series', 'variant', 'frame', 'poles'] + cols_all + ['src_page'], out)


# ---------------------------------------------------------------- service factor chart (p.14) -- digitised from the embedded raster
def service_factor():
    from PIL import Image
    import tempfile, glob
    d = tempfile.mkdtemp()
    subprocess.run(['pdfimages', '-png', '-f', '14', '-l', '14', PDF, os.path.join(d, 'sf')], check=True)
    im = Image.open(glob.glob(os.path.join(d, 'sf-*.png'))[0]).convert('L')
    W, Hh = im.size
    px = im.load()
    # calibration measured on the image: gridline rows y(k)=128+35.6*k (k=0..10) ; tick x positions of starts/h
    y0, dy = 128.0, 35.6
    ticks = {5: 590, 10: 643, 20: 733, 30: 823, 40: 913, 50: 1003, 60: 1094, 70: 1184, 80: 1274, 90: 1364, 100: 1455}
    scale0 = {24: 2.4, 16: 2.1, 8: 1.9, 2: 1.7}   # value of row 0 per hours/day column; -0.1 per row (printed scales)
    def line_y(x):
        ys = [y for y in range(100, 500) if px[x, y] < 115]
        # cluster
        cl = []
        for y in ys:
            if cl and y - cl[-1][-1] <= 3: cl[-1].append(y)
            else: cl.append([y])
        return [(c[0] + c[-1]) / 2 for c in cl if len(c) >= 4]
    out = []
    for st, x in ticks.items():
        ys = line_y(x)
        ys = sorted(ys)
        if len(ys) != 3:
            raise SystemExit(f'expected 3 lines at x={x}, got {ys}')
        for cls, y in zip('CBA', ys):   # top to bottom: C, B, A
            k = (y - y0) / dy
            for h, s0 in scale0.items():
                out.append(['H', cls, h, st, f'{s0 - 0.1 * k:.2f}', 14])
    out.sort(key=lambda r: (r[1], -r[2], r[3]))
    write_csv('service_factor.csv', ['series', 'load_class', 'hours_per_day', 'starts_per_hour', 'fs', 'src_page'], out)


# ---------------------------------------------------------------- misc small tables
def extras():
    # shaft keys p.68 (UNI 6604 - DIN 6885)
    rows = cluster_rows(page_words(68), tol=2)
    out = []
    for r in rows:
        if not any(w['text'] == '×' for w in r): continue
        def pick(lo, hi):
            for w in r:
                if lo <= w['x0'] < hi and re.match(r'^[\d,]+$', w['text']): return num(w['text'])
            return ''
        out.append(['H', pick(60, 95), pick(95, 125), pick(125, 150), pick(176, 200), pick(250, 280), pick(285, 320),
                    pick(380, 405), pick(410, 440), pick(440, 470), 68])
    write_csv('extra_shaft_keys.csv', ['series', 'd_over_mm', 'd_up_to_mm', 'key_b', 'key_h', 'L_min', 'L_max', 'b', 't1', 't2', 'src_page'], out)
    # backstop p.75
    rows = cluster_rows(page_words(75), tol=3)
    hdr = next(r for r in rows if any(w['text'] == '063' for w in r) and any(w['text'] == '225' for w in r))
    cols = [(w['text'], (w['x0'] + w['x1']) / 2) for w in hdr if re.match(r'^\d{3}', w['text'])]
    pam = next(r for r in rows if any(w['text'] == '140x11' for w in r))
    pamd = {nearest(cols, (w['x0'] + w['x1']) / 2): w['text'] for w in pam}
    out = []
    for r in rows:
        if re.match(r'^(HR|H)\d{3}$', r[0]['text']):
            for w in r[1:]:
                if w['text'] == 'B5':
                    fr = nearest(cols, (w['x0'] + w['x1']) / 2)
                    out.append(['H', r[0]['text'], fr, 'B5', pamd.get(fr, ''), 75])
    write_csv('extra_backstop_availability.csv', ['series', 'size', 'iec_frame', 'flange', 'pam_Pm_x_Dm', 'src_page'], out)
    # reinforced seals p.76
    rows = cluster_rows(page_words(76), tol=3)
    hx = {}
    for r in rows:
        for w in r:
            if w['text'] == 'Double': hx['double'] = w['x0']
            if w['text'] == 'VRM': hx['vrm'] = w['x0']
    out = []
    for r in rows:
        if re.match(r'^(HR\d{3}|H\d{3}/\d)$', r[0]['text']) and len(r) == 2 and r[1]['text'] == 'X':
            typ = 'double oil seal' if abs(r[1]['x0'] - hx['double']) < abs(r[1]['x0'] - hx['vrm']) else 'standard oil seal with VRM ring'
            out.append(['H', r[0]['text'], typ, 76])
    write_csv('extra_reinforced_seals.csv', ['series', 'size', 'reinforced_seal_solution', 'src_page'], out)
    # output shaft bearings p.31 (read from page text; ball=1, roller=2)
    bear = [('HA30', 'HA 1', 'ball', 'standard'), ('HA30', 'HA 2/3', 'ball', 'standard'), ('HA40', 'HA 1', 'ball', 'standard'), ('HA40', 'HA 2/3', 'ball', 'standard'),
            ('HA50', 'HA 1', 'ball', 'standard'), ('HA50', 'HA 2/3', 'ball', 'standard'), ('HA60', 'HA 1', 'ball', 'standard'), ('HA60', 'HA 2/3', 'ball', 'standard')]
    for sz, std, alt in (('HR041', 'ball', 'roller'), ('HR051', 'ball', 'roller'), ('HR061', 'ball', 'roller')):
        bear.append((sz, 'HR 1/M', std, 'standard')); bear.append((sz, 'HR 1/M', alt, 'on request'))
    for sz in ('HR081', 'HR101', 'HR121'): bear.append((sz, 'HR 1/M', 'roller', 'standard'))
    for sz in ('H030', 'H040', 'H050', 'H060', 'H080', 'H100', 'H125', 'H140'): bear.append((sz, 'H 2/3', 'roller', 'standard'))
    write_csv('extra_output_shaft_bearings.csv', ['series', 'size', 'version', 'bearing', 'availability', 'src_page'], [['H', a, b, c, d, 31] for a, b, c, d in bear])
    # critical applications p.25 (check marks as printed: V = verified, B = check/call, A = not recommended)
    crit = []
    ha = ['A31', 'A30', 'A40', 'A50', 'A60']
    for sz in ha:
        crit += [(sz, 'V5-V1 1500<n1<3000', 'verified'), (sz, 'V5-V1 n1>3000', 'B: check application / call technical service'), (sz, 'V3-V6', 'B: check application / call technical service')]
    hs = ['030', '040', '050', '060', '080', '100', '125', '140']
    for sz in hs:
        v1 = 'verified' if sz not in ('125', '140') else 'B: check application / call technical service'
        v2 = 'B: check application / call technical service' if sz not in ('125', '140') else 'A: application not recommended'
        crit += [('H' + sz, 'V5-V1 1500<n1<3000', v1), ('H' + sz, 'V5-V1 n1>3000', v2), ('H' + sz, 'V3-V6', 'B: check application / call technical service')]
    write_csv('extra_critical_applications.csv', ['series', 'size', 'condition', 'status', 'src_page'], [['H', a, b, c, 25] for a, b, c in crit])
    # output flange options p.73
    groups = [(['HR041', 'HR051', 'H032/H033', 'H042/H043'], 'FA;FB;FC;FD'), (['HR061', 'H052/H053'], 'FA;FB'), (['HR081', 'HR101', 'H062/H063'], 'FA;FB;FC'),
              (['HR121', 'H082/H083'], 'FA;FB;FC'), (['H102/H103'], 'FA;FB;FC'), (['H122/H123'], 'FA;FB;FC'), (['H142/H143'], 'FA;FB;FC')]
    write_csv('extra_output_flange_options.csv', ['series', 'size', 'output_flange_codes', 'src_page'],
              [['H', sz, codes, 73] for g, codes in groups for sz in g])


# ---------------------------------------------------------------- designation.json (p.15 diagram, read from the rendered page image)
def designation():
    d = {
        'source_page': 17,
        'pattern': 'H <family> <version> <size> <output flange> <ratio> <input> <output dims> <mounting position>',
        'example_as_printed': 'H H F 063 FA 118 160x14 250x40 B3',
        'note': 'Diagram on printed p.15 (PDF p.17) is a raster flow chart; field names are as printed, values listed are those printed in the boxes.',
        'segments': [
            {'name': 'series', 'values': {'H': 'Motovario H series helical gear units / geared motors'}},
            {'name': 'type_family', 'values': {'HA': 'aluminium alloy series (sizes A31..A63)', 'HR': 'cast iron single-stage series (041..121)', 'H': 'cast iron 2/3-stage series (032/033..142/143)'}},
            {'name': 'configuration', 'values': {'PH': 'PAM motoreducer fitted for motor mounting with flexible coupling', 'H': 'PAM motoreducer (IEC motor flange + coupling)',
                                                 'CH': 'compact motoreducer (motor directly coupled)', 'IH': 'gear reducer with input shaft'}},
            {'name': 'version', 'values': {'F': 'casing with flange (foot version has no letter in the diagram)', 'U': 'casing universal (foot + flange)', 'M': 'casing mono (HR single-stage only)'}},
            {'name': 'size', 'values': {'A31-A32-A33': 'HA', 'A41-A42-A43': 'HA', 'A51-A52-A53': 'HA', 'A61-A62-A63': 'HA',
                                          '041-051-061-081-101-121': 'HR (stage digit 1 = single stage)', '032-033': 'H', '042-043': 'H', '052-053': 'H', '062-063': 'H', '082-083': 'H',
                                          '102-103': 'H', '122-123': 'H', '142-143': 'H'},
             'note': 'last digit = number of stages (1,2,3); example size printed: 063'},
            {'name': 'output_flange', 'values': {'FA': 'output flange FA', 'FB': 'output flange FB', 'FC': 'output flange FC', 'FD': 'output flange FD (p.73 tables, small sizes)'}},
            {'name': 'ratio', 'values': {'range': 'from 1.23 to 353.98 (as printed), example 118'}},
            {'name': 'input_dimensions', 'values': {'PAM': 'fitted for motor coupling, e.g. 160x14 = flange Pm x bore Dm of the IEC motor', 'ECE': 'input shaft with diameter e.g. 28'}},
            {'name': 'output_dimensions', 'values': {'example': '250x40 (printed example; free field for output shaft/flange dimensions)'}},
            {'name': 'mounting_position', 'values': {'B3': 'foot, horizontal', 'B5': 'flange, horizontal', 'B8': 'ceiling foot', 'B6': 'wall foot', 'B7': 'wall foot', 'V5': 'vertical shaft down, foot', 'V1': 'vertical shaft down, flange',
                                                   'V6': 'vertical shaft up', 'V3': 'vertical shaft up'}, 'note': 'meaning of B/V codes is the standard IEC one; the catalogue shows only the codes (pictograms p.20-21, p.22-23)'},
        ],
        'terminal_box': 'Position 1 unless specified at order (p.21 text)',
    }
    with open(os.path.join(OUT, 'designation.json'), 'w') as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
    print('designation.json written')

# ---------------------------------------------------------------- images
IMG_PAGES = {
    14: ('diagram', 'general', 'Service factor chart f.s. vs starts/hour and hours/day, load classes A/B/C'),
    15: ('render', 'general', 'Motor assembly on PAM flange (coupling, sleeve)'),
    16: ('other', 'general', 'Product nameplate example'),
    17: ('diagram', 'general', 'Designation (ordering code) flow chart'),
    18: ('render', 'HA30-A60', 'Versions A30/A40/A50/A60: foot, flange, universal'),
    19: ('render', 'H030-140', 'Versions 030-140: foot, flange, universal, mono'),
    20: ('render', 'HA', 'Modularity of aluminium series (HA, CHA, IHA)'),
    21: ('render', 'H', 'Modularity of cast iron series (H, CH, PH, IH)'),
    22: ('drawing', 'HA1T-HR1T-HR1U-HA1F-HR1F-HR1M', 'Mounting positions single stage'),
    23: ('drawing', 'HA2/3-H2/3', 'Mounting positions 2/3 stage and terminal box position'),
    32: ('drawing', 'general', 'Radial load on input shaft: a, b, x'),
    33: ('drawing', 'general', 'Radial load on output shaft: a, b, x'),
    38: ('drawing', 'HA31', 'HA31 dimensional drawing'), 39: ('drawing', 'HA41-HA51-HA61', 'HA.1 dimensional drawing'),
    40: ('drawing', 'CHA41-CHA51-CHA61', 'CHA.1 dimensional drawing'), 41: ('drawing', 'IHA41-IHA51-IHA61', 'IHA.1 dimensional drawing'),
    42: ('drawing', 'HA32-HA62', 'HA.2 dimensional drawing'), 44: ('drawing', 'CHA32-CHA62', 'CHA.2 dimensional drawing'),
    46: ('drawing', 'IHA32-IHA62', 'IHA.2 dimensional drawing'), 48: ('drawing', 'HA33-HA63', 'HA.3 dimensional drawing'),
    50: ('drawing', 'CHA33-CHA63', 'CHA.3 dimensional drawing'), 52: ('drawing', 'IHA33-IHA63', 'IHA.3 dimensional drawing'),
    54: ('drawing', 'HR041-HR121', 'HR..1 dimensional drawing'), 56: ('drawing', 'CHR041-CHR121', 'CHR..1 dimensional drawing'),
    58: ('drawing', 'IHR041-IHR121', 'IHR..1 dimensional drawing'), 60: ('drawing', 'H032-H143', 'H..2/3 dimensional drawing'),
    62: ('drawing', 'CH032-CH143', 'CH..2/3 dimensional drawing'), 64: ('drawing', 'IH032-IH143', 'IH..2/3 dimensional drawing'),
    68: ('drawing', 'general', 'Shaft end key drawing'), 69: ('drawing', 'general', 'IEC motor dimensional drawing'), 70: ('drawing', 'general', 'IEC motor dimensional drawing (large frames)'),
    73: ('drawing', 'H', 'Output flange FA/FB/FC/FD'), 74: ('drawing', 'general', 'Backstop device sense of direction'),
    76: ('drawing', 'general', 'Reinforced oil seals: double seal / VRM ring'),
}

def images():
    import hashlib, tempfile, glob, shutil
    from PIL import Image
    idir = os.path.join(OUT, 'images'); os.makedirs(idir, exist_ok=True)
    for f in glob.glob(os.path.join(idir, '*')): os.remove(f)
    rows = []; seen = set()
    for pg, (kind, size, cap) in IMG_PAGES.items():
        tmp = tempfile.mkdtemp()
        subprocess.run(['pdfimages', '-png', '-f', str(pg), '-l', str(pg), PDF, os.path.join(tmp, 'i')], check=True)
        n = 0
        for fp in sorted(glob.glob(os.path.join(tmp, 'i-*.png'))):
            im = Image.open(fp)
            if im.size[0] < 150 or im.size[1] < 150: continue
            h = hashlib.md5(im.tobytes()).hexdigest()
            if h in seen: continue
            seen.add(h); n += 1
            k = kind
            if pg == 15 and im.size[0] < 400: k = 'photo'
            name = f"H_{size.replace('/', '-')}_{k}_p{pg}_{n}.png"
            shutil.copy(fp, os.path.join(idir, name))
            rows.append([name, 'H', size, k, cap + (f' (figure {n})' if n > 1 else ''), pg, im.size[0], im.size[1]])
    write_csv('images/index.csv', ['file', 'series', 'size', 'kind', 'caption', 'src_page', 'width_px', 'height_px'], rows)

STEPS = {'ratings': ratings, 'dims': dims, 'iec': iec, 'availability': availability, 'motor_interface': motor_interface,
         'weights': weights, 'lubrication': lubrication, 'small': small_tables, 'motors': motors, 'service_factor': service_factor,
         'extras': extras, 'designation': designation, 'images': images}
if __name__ == '__main__':
    for s in (sys.argv[1:] or STEPS):
        STEPS[s]()
