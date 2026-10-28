#!/usr/bin/env python3
"""Extract Motovario HPL planetary catalogue (sources/catalogs/HPL_planetary.pdf) into data/raw/HPL/.
Run:  python3 tools/extract_HPL.py   (from repo root).  Requires pdftotext + pdfplumber.
All page numbers are 1-based PDF pages (printed page = PDF page - 2)."""
import csv, json, os, re, subprocess, sys
import pdfplumber

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, 'sources/catalogs/HPL_planetary.pdf')
OUT = os.path.join(ROOT, 'data/raw/HPL')
os.makedirs(OUT, exist_ok=True)
S = 'HPL'

TXT = subprocess.run(['pdftotext', '-layout', PDF, '-'], capture_output=True, text=True).stdout.split('\f')
PL = pdfplumber.open(PDF)

def page_lines(p):
    return [l for l in TXT[p - 1].split('\n') if l.strip()]

def num(s):
    """catalogue number -> dot-decimal string; '/', '-', '' -> ''"""
    s = s.strip().replace('−', '-')
    if s in ('', '/', '-', '–'):
        return ''
    return s.replace(',', '.')

def write_csv(name, cols, rows):
    with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, '') for c in cols})
    print(f'{name}: {len(rows)} rows')
    return len(rows)

def dedouble(s):
    """pdf text of some table headers has every glyph doubled ('6633AA' -> '63A')"""
    return s[::2] if len(s) % 2 == 0 and all(s[i] == s[i + 1] for i in range(0, len(s), 2)) else s

# ---------------------------------------------------------------- motors (5.4)
def extract_motors():
    # nominal power table, page 83
    pg = PL.pages[82]
    rows = {}
    for w in pg.extract_words():
        rows.setdefault(round(w['top'] / 3), []).append(w)
    lines = [sorted(v, key=lambda w: w['x0']) for k, v in sorted(rows.items())]
    out = []
    frames = None; types = None
    for ln in lines:
        txt = [w['text'] for w in ln]
        if txt and re.fullmatch(r'(\d\d\d?|\d{4,6})[A-Z]*', txt[0]) and all(re.fullmatch(r'[0-9A-Z]+', t) for t in txt) and len(dedouble(txt[0])) <= 5 and txt[0] != 'P.':
            frames = [(dedouble(w['text']), (w['x0'] + w['x1']) / 2) for w in ln]
        elif txt and txt[0] == 'P.':
            types = [(dedouble(w['text']), (w['x0'] + w['x1']) / 2) for w in ln[1:]]
        elif frames and types and txt and txt[0] in ('2', '4', '6') and len(ln) > 3:
            poles = txt[0]
            vals = [w for w in ln[1:]]
            for w in vals:
                c = (w['x0'] + w['x1']) / 2
                tcol = min(types, key=lambda t: abs(t[1] - c))
                fr = min(frames, key=lambda f: abs(f[1] - c))
                if num(w['text']) == '':
                    continue
                typ = tcol[0]
                out.append(dict(series=S, motor_type=typ, frame=fr[0], poles=poles, power_kw=num(w['text']),
                                rpm='', voltage_v='', efficiency_class={'TS': 'IE1', 'TH': 'IE2', 'TP': 'IE3'}.get(typ, ''),
                                efficiency_pct='', torque_nm='', current_a='', mass_kg='', src_page=83))
    cols = 'series,motor_type,frame,poles,power_kw,rpm,voltage_v,efficiency_class,efficiency_pct,torque_nm,current_a,mass_kg,src_page'.split(',')
    write_csv('motors.csv', cols, out)
    return out


def extract_motors_dimensions():
    rows = []
    # page 80 body table (frames 63-160S) and page 81 (160M-280M); then B5 / B14 flange tables
    body_re = re.compile(r'^\s*(\d{2,3}[A-Z]?)\s+(?:([246](?:-[46])*(?:-[46])?)\s+)?(.*)$')
    for pg in (80, 81):
        prev = None
        for l in page_lines(pg):
            ls = l.strip()
            m = re.match(r'^\*([\d,\.]+)\s+\*([\d,\.]+)\s+\*([\d,\.]+)$', ls)
            if m and prev is not None:
                prev['L_star'], prev['LB_star'], prev['LC_star'] = [num(x) for x in m.groups()]
                continue
            m = body_re.match(l)
            if not m:
                continue
            frame, poles, rest = m.groups()
            rest = re.sub(r'(\d)\s*([jk]6)', r'\1 \2', rest)
            tok = rest.split()
            if pg == 80:
                # AC AD L LB LC X Y V D tol E E1 f F1 GA F GD
                if len(tok) != 17 or not re.fullmatch(r'[jk]6', tok[9]) or frame in ('63', '71') and False:
                    continue
                keys = 'AC,AD,L,LB,LC,X,Y,V,D,D_tol,E,E1,f,F1,GA,F,GD'.split(',')
                r = dict(series=S, size=frame, variant='body', poles='', src_page=pg)
            else:
                # AC AD L LB X Y V D E f F1 GA F GD LL Pg_cable Pg_aux
                if len(tok) != 17:
                    continue
                keys = 'AC,AD,L,LB,X,Y,V,D,E,f,F1,GA,F,GD,LL,Pg_cable,Pg_aux'.split(',')
                r = dict(series=S, size=frame, variant='body', poles=poles or '', src_page=pg)
            for k, v in zip(keys, tok):
                r[k] = v.replace(',', '.') if k in ('D_tol', 'f', 'Pg_cable', 'Pg_aux') else num(v)
            rows.append(r); prev = r
    # flange tables: B5 (M N P LA S T), B14 (M N P LA S T)
    for pg in (80, 81):
        for l in page_lines(pg):
            tok = l.split()
            if pg == 80 and len(tok) == 14 and re.fullmatch(r'\d{2,3}', tok[0]) and re.fullmatch(r'\d{2,3}', tok[7]):
                for off, var in ((0, 'B5'), (7, 'B14')):
                    t = tok[off:off + 7]
                    rows.append(dict(series=S, size=t[0], variant=var, M=num(t[1]), N=num(t[2]), P=num(t[3]), LA=num(t[4]), S=num(t[5]), T=num(t[6]), src_page=pg))
            elif pg == 81 and len(tok) == 7 and re.fullmatch(r'\d{3}', tok[0]) and all(re.fullmatch(r'[\d,\.]+', t) for t in tok):
                t = tok
                rows.append(dict(series=S, size=t[0], variant='B5', M=num(t[1]), N=num(t[2]), P=num(t[3]), LA=num(t[4]), S=num(t[5]), T=num(t[6]), src_page=pg))
    cols = ['series', 'size', 'variant', 'poles', 'AC', 'AD', 'L', 'LB', 'LC', 'L_star', 'LB_star', 'LC_star', 'X', 'Y', 'V', 'D', 'D_tol', 'E', 'E1', 'f', 'F1', 'GA', 'F', 'GD', 'LL', 'Pg_cable', 'Pg_aux', 'M', 'N', 'P', 'LA', 'S', 'T', 'src_page']
    write_csv('motors_dimensions.csv', cols, rows)
    return rows


# ---------------------------------------------------------------- ratings (7.1 HL, 7.2-7.5 IHL, 13.1 VP)
RATING_COLS = ['series', 'size', 'stages', 'n1_rpm', 'p1_kw', 'i', 'n2_rpm', 't2_nm', 'fs', 'fr2_n', 'motor_frames', 'variant', 'src_page',
               'type', 'poles', 'fr2_ss_n', 't2max_nm', 'mn2_nm', 'mn2_highlight', 'i_worm', 'i_planetary']

def size_name(code):
    return f'HPL {code}'

def extract_ratings_hl():
    rows = []
    pat = re.compile(r'^\s*([\d,\.]+)\s+(\d+)\s+([\d,]+)\s+([\d,\.]+)\s+HL(\d)\s+(\d{3})\s+(\S+)\s+(\d)\s+(\d+)\s+(\d+)\s*$')
    for p in range(97, 134):
        kw = None
        for l in page_lines(p):
            m = re.match(r'^\s*([\d,]+)\s*kW\s*$', l)
            if m:
                kw = num(m.group(1)); continue
            m = pat.match(l)
            if not m:
                continue
            n2, m2, fs, i, st, sz, motor, poles, frcs, frss = m.groups()
            rows.append(dict(series=S, size=size_name(sz), stages=st, n1_rpm='', p1_kw=kw, i=num(i), n2_rpm=num(n2), t2_nm=m2,
                             fs=num(fs), fr2_n=frcs, motor_frames=motor.replace('/', ';'), variant='geared motor', src_page=p,
                             type=f'HL{st} {sz}', poles=poles, fr2_ss_n=frss))
    return rows

def cell_colour(pg, w):
    """Mn2 cells that are 'independent of Pn1' are drawn with a coloured frame: a filled outer rect (h~9.6) in dark blue-grey or magenta
    with a white inner rect.  Returns 'box_dark' (catalogue text p.13 calls it grey) / 'box_magenta' (purple) / ''."""
    cx = (w['x0'] + w['x1']) / 2; cy = (w['top'] + w['bottom']) / 2
    for r in pg.rects:
        c = r.get('non_stroking_color')
        if not r.get('fill') or not isinstance(c, (tuple, list)) or len(c) != 3:
            continue
        if r['height'] > 11 or r['width'] > 40 or r['width'] < 20:
            continue
        if r['x0'] <= cx <= r['x1'] and r['top'] <= cy <= r['bottom']:
            c = tuple(round(x, 2) for x in c)
            if c == (0.85, 0.43, 0.8):
                return 'box_magenta'
            if c == (0.04, 0.16, 0.22):
                return 'box_dark'
    return ''

def extract_ratings_ihl():
    rows = []
    for p in range(134, 168):
        pg = PL.pages[p - 1]
        lines = {}
        for w in pg.extract_words():
            lines.setdefault(round(w['top']), []).append(w)
        m = re.search(r'IHL GEAR REDUCER - (\d+) rpm', TXT[p - 1])
        n1 = m.group(1)
        titles = {'L': [], 'R': []}
        for top in sorted(lines):
            ws = sorted(lines[top], key=lambda w: w['x0'])
            for a, b in zip(ws, ws[1:]):
                if re.fullmatch(r'IHL\d', a['text']) and re.fullmatch(r'\d{3}', b['text']):
                    titles['L' if a['x0'] < 300 else 'R'].append((top, a['text'], b['text']))
        for top in sorted(lines):
            ws = sorted(lines[top], key=lambda w: w['x0'])
            for side, sel in (('L', [w for w in ws if w['x0'] < 310]), ('R', [w for w in ws if w['x0'] >= 310])):
                if len(sel) == 7 and all(re.fullmatch(r'[\d,\.]+', w['text']) for w in sel):
                    t = [x for x in titles[side] if x[0] < top]
                    if not t:
                        raise SystemExit(f'no title p{p} {top}')
                    _, ih, sz = t[-1]
                    mn2, i, pn1, n2, frcs, frss, m2max = [w['text'] for w in sel]
                    rows.append(dict(series=S, size=size_name(sz), stages=ih[-1], n1_rpm=n1, p1_kw=num(pn1), i=num(i), n2_rpm=num(n2),
                                     t2_nm=mn2, fs='', fr2_n=frcs, motor_frames='', variant='reducer (IHL input shaft)', src_page=p,
                                     type=f'{ih} {sz}', fr2_ss_n=frss, t2max_nm=m2max, mn2_nm=mn2, mn2_highlight=cell_colour(pg, sel[0])))
    return rows

def extract_ratings_vp():
    rows = []
    pat = re.compile(r'^\s*([\d,\.]+)\s+(\d+)\s+(\d+)\s+([\d,]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+(\d+)\s+VP\s+(P\d+)\s+(\S+?)(\d)(\s+\S+)?\s+(\d+)\s+(\d+)\s*$')
    for p in range(207, 214):
        kw = None
        for l in page_lines(p):
            m = re.match(r'^\s*([\d,]+)\s*kW\s*$', l)
            if m:
                kw = num(m.group(1)); continue
            m = pat.match(l)
            if not m:
                continue
            n2, m2, mn2, fs, ivsf, ihpl, itot, sz, mot, poles, extra, frcs, frss = m.groups()
            frame = re.sub(r'^(TH|TP|TS)', '', mot)
            rows.append(dict(series=S, size=f'VP {sz}', stages='3', n1_rpm='', p1_kw=kw, i=itot, n2_rpm=num(n2), t2_nm=m2, fs=num(fs),
                             fr2_n=frcs, motor_frames=frame + ((' ' + extra.strip()) if extra else ''), variant='VP geared motor', src_page=p,
                             type=f'VP {sz}', poles=poles, fr2_ss_n=frss, mn2_nm=mn2, i_worm=num(ivsf), i_planetary=num(ihpl)))
            rows[-1]['motor_frames'] = rows[-1]['motor_frames']
            rows[-1]['motor_type_printed'] = mot + poles + (extra or '')
    return rows

def extract_ratings():
    hl, ihl, vp = extract_ratings_hl(), extract_ratings_ihl(), extract_ratings_vp()
    write_csv('ratings.csv', RATING_COLS, hl + ihl + vp)
    return hl, ihl, vp


# ---------------------------------------------------------------- generic helpers for text tables
SIZES = ['010', '020', '030', '050', '080', '130', '180', '220', '380']

def toks(l):
    return l.split()

# ---------------------------------------------------------------- service factor (1.5)
def extract_service_factor():
    rows = []
    L = page_lines(19)
    txt = '\n'.join(L)
    # table fsa: load class x hours/day
    hours = [2, 4, 8, 16, 24]
    for l in L:
        m = re.match(r'^\s*(Uniform|Moderate|Heavy)\s+((?:\d,\d\d\s*){5})$', l)
        if m:
            for h, v in zip(hours, m.group(2).split()):
                rows.append(dict(series=S, load_class=m.group(1).lower(), hours_per_day=h, starts_per_hour='', fs=num(v), src_page=19, table='fsa'))
    starts = ['<6', '6-20', '20-60', '60-120']
    for l in L:
        m = re.match(r'^\s*(Uniform|Moderate|Heavy)\s+((?:\d(?:,\d+)?\s*){4})$', l)
        if m and ',' not in l.split(None, 1)[1].split()[0] or (m and len(m.group(2).split()) == 4):
            vals = m.group(2).split()
            if len(vals) == 4 and not any(r['table'] == 'fsb' and r['load_class'] == m.group(1).lower() for r in rows):
                for st, v in zip(starts, vals):
                    rows.append(dict(series=S, load_class=m.group(1).lower(), hours_per_day='', starts_per_hour=st, fs=num(v), src_page=19, table='fsb'))
    for name, v in (('electric motor', '1,00'), ('reciprocating multiple-cylinder motor', '1,25'), ('reciprocating single-cylinder motor', '1,50')):
        rows.append(dict(series=S, load_class=name, hours_per_day='', starts_per_hour='', fs=num(v), src_page=19, table='fsc'))
    write_csv('service_factor.csv', ['series', 'load_class', 'hours_per_day', 'starts_per_hour', 'fs', 'src_page', 'table'], rows)
    # application classification (pages 20-21): two side-by-side column groups "Application | Type of load" -> pdfplumber words.
    # Cells are vertically centred, so wrapped fragments are assigned to the nearest class word (Uniform/Moderate/Heavy) by y.
    app = []
    for p in (20, 21):
        ws = words_of(p)
        for side, lo, hi in (('L', 0, 297), ('R', 297, 700)):
            col = [w for w in ws if lo <= w['x0'] < hi and 90 < w['top'] < 790]
            classes = [w for w in col if w['text'] in ('Uniform', 'Moderate', 'Heavy') and w['x0'] > lo + 120]
            lines = {}
            for w in col:
                if w in classes:
                    continue
                lines.setdefault(round(w['top']), []).append(w)
            frag = []   # (top, text)
            cats = []   # (top, text)
            for k in sorted(lines):
                t = ' '.join(w['text'] for w in sorted(lines[k], key=lambda w: w['x0']))
                if t.startswith('Application') or 'Type of load' in t or 'TECHNICAL' in t:
                    continue
                if t.startswith('loads) ') :
                    cats.append((k, 'loads)')); t = t[len('loads) '):]
                first = t.split()[0]
                if first.replace('-', '').isupper() and len(first) > 2:
                    cats.append((k, t))
                else:
                    frag.append((k, t))
            # merge consecutive category lines closer than 13pt (wrapped heading)
            mc = []
            for k, t in cats:
                if mc and k - mc[-1][2] < 13:
                    mc[-1] = (mc[-1][0], mc[-1][1] + ' ' + t, k)
                else:
                    mc.append((k, t, k))
            assign = {}
            for k, t in frag:
                c = min(classes, key=lambda w: abs(w['top'] - k))
                assign.setdefault(id(c), []).append((k, t))
            for c in sorted(classes, key=lambda w: w['top']):
                txt = ' '.join(t for k, t in sorted(assign.get(id(c), [])))
                cat = ''
                for k, t, _ in mc:
                    if k <= c['top'] + 1:
                        cat = t
                app.append(dict(series=S, group=cat, application=txt, type_of_load=c['text'], src_page=p))
    write_csv('extra_service_factor_application_class.csv', ['series', 'group', 'application', 'type_of_load', 'src_page'], app)
    return rows

# ---------------------------------------------------------------- thermal (4.3)
def extract_thermal():
    rows = []
    for p in (43,):
        ver = None
        for l in page_lines(p):
            if l.strip().startswith('Version T'):
                ver = ('T', 'B3')
            elif l.strip().startswith('Version F'):
                ver = ('F', 'B5')
            for m in re.finditer(r'HPL (\d)-(\d{3})\s+([\d\.,]+|-)', l):
                st, sz, v = m.groups()
                rows.append(dict(series=S, size=size_name(sz), stages=st, version=ver[0], mounting_position=ver[1], n1_rpm=1500, pth_kw=num(v), src_page=p))
    write_csv('thermal.csv', ['series', 'size', 'stages', 'version', 'mounting_position', 'n1_rpm', 'pth_kw', 'src_page'], rows)
    # correction factors (page 44) -- hand-parsed from text lines
    L = page_lines(44)
    fac = []
    for a, b in ((0, 1000, 1), (1000, 2000, 0.9), (2000, 3000, 0.8)) if False else ():
        pass
    for lo, hi, v in (('0', '1000', '1'), ('1000', '2000', '0,9'), ('2000', '3000', '0,8')):
        fac.append(dict(series=S, table='fta', key1=f'altitude {lo}-{hi} m', key2='', value=num(v), src_page=44))
    # ftc: ambient temperature x duty %
    duty = None
    for l in L:
        m = re.match(r'^.*Fc\s+((?:\d+\s+)+\d+)\s*$', l)
        if m:
            pass
    ftc_hdr = None
    for l in L:
        m = re.search(r'\bFc\s+(100)\s+(80)\s+(70)\s+(40)\s+(20)', l)
        if m:
            ftc_hdr = m.groups()
        m = re.search(r'\s(10|20|25|30|40|45|50)\s+((?:\d,?\d*\s+){4}\d,?\d*)\s*$', l)
        if m and ftc_hdr:
            vals = m.group(2).split()
            if len(vals) == 5:
                for d, v in zip(ftc_hdr, vals):
                    fac.append(dict(series=S, table='ftc', key1=f'ambient {m.group(1)} C', key2=f'duty {d} %', value=num(v), src_page=44))
    # ftn
    ftn_n = [500, 700, 900, 1150, 1400, 1750, 2250, 2800]
    ftn = {}
    for l in L:
        m = re.match(r'^\s*B6 - B7\s+((?:\d,?\d*\s+){7}\d,?\d*)\s*$', l)
        if m:
            ftn['B3/B5; B6-B7; B8'] = m.group(1).split()
        m = re.match(r'^\s+(1,3\s+1,16\s+1\s+0,81\s+0,65\s+0,5\s+0,4\s+0,25)(?:\s{3,}.*)?$', l)
        if m:
            ftn['V5/V1; V6/V3'] = m.group(1).split()
    # B3/B5 row: factors = B6-B7 row with different assignment not printed separately; keep only printed groups
    for k, vals in ftn.items():
        for n, v in zip(ftn_n, vals):
            fac.append(dict(series=S, table='ftn', key1=k, key2=f'n1 {n} rpm', value=num(v), src_page=44))
    for k, v in (('stagnant air (<0.5 m/s)', '0,54'), ('indoor, slight ventilation', '0,71'), ('indoor, good ventilation (>1.4 m/s)', '1'), ('outdoor (>3.7 m/s)', '1,4')):
        fac.append(dict(series=S, table='ftv', key1=k, key2='', value=num(v), src_page=44))
    write_csv('extra_thermal_factors.csv', ['series', 'table', 'key1', 'key2', 'value', 'src_page'], fac)
    return rows



# ---------------------------------------------------------------- weights (5.2, 10.2)
def extract_weights():
    rows = []
    frames = ['71', '80', '90', '100-112', '132', '160', '180', '200', '225', '250']
    for l in page_lines(76):
        t = toks(l)
        if len(t) == 13 and re.fullmatch(r'\d-\d{3}', t[0]) and t[11].startswith(t[0][:1] + '-'):
            st, sz = t[0].split('-')
            for fr, v in zip(frames, t[1:11]):
                if num(v) != '':
                    rows.append(dict(series=S, size=size_name(sz), variant='HL/PHL foot (T) reducer with PAM flange, no motor, no oil', motor_frame=fr, mass_kg=num(v), src_page=76, stages=st))
            if num(t[12]) != '':
                rows.append(dict(series=S, size=size_name(sz), variant='IHL foot (T) reducer, no oil', motor_frame='', mass_kg=num(t[12]), src_page=76, stages=st))
    for l in page_lines(76):
        m = re.match(r'^\s*(\d{3}(?:-\d{3})?)\s+([\d,\.]+)\s*$', l)
        if m:
            a = m.group(1)
            rng = {'010-020': ['010', '020'], '030-050': ['030', '050'], '080': ['080'], '130': ['130'], '180': ['180'], '220': ['220'], '380': ['380']}[a]
            for sz in rng:
                rows.append(dict(series=S, size=size_name(sz), variant='deduction for flange (F) version: subtract from foot-version mass (HL/PHL/IHL/CHL)', motor_frame='', mass_kg=num(m.group(2)), src_page=76, stages=''))
    # CHL gearmotors p77 (TH/TP) and p78 (TBH/TBP)
    for p, (la, lb) in ((77, ('TH', 'TP')), (78, ('TBH', 'TBP'))):
        thf = ['71', '80']
        tpf = ['80', '90S', '90L', '100', '112', '132S', '132M']
        for l in page_lines(p):
            t = toks(l)
            if len(t) == 11 and re.fullmatch(r'\d-\d{3}', t[0]) and t[3] == t[0]:
                st, sz = t[0].split('-')
                for fr, v in zip(thf, t[1:3]):
                    if num(v) != '':
                        rows.append(dict(series=S, size=size_name(sz), variant=f'CHL foot gearmotor with {la} motor (mass of complete gearmotor)', motor_frame=fr, mass_kg=num(v), src_page=p, stages=st))
                for fr, v in zip(tpf, t[4:11]):
                    if num(v) != '':
                        rows.append(dict(series=S, size=size_name(sz), variant=f'CHL foot gearmotor with {lb} motor (mass of complete gearmotor)', motor_frame=fr, mass_kg=num(v), src_page=p, stages=st))
    # VP p201
    ver = None
    for l in page_lines(201):
        if 'Version T' in l: ver = 'T'
        if 'Version F' in l: ver = 'F'
        m = re.match(r'^\s*(P\d+)\s+([\d,\.]+)\s*$', l)
        if m and ver:
            rows.append(dict(series=S, size=f'VP {m.group(1)}', variant=f'VP version {ver} reducer without motor (only worm-stage lubricant)', motor_frame='', mass_kg=num(m.group(2)), src_page=201, stages='3'))
    write_csv('weights.csv', ['series', 'size', 'variant', 'motor_frame', 'mass_kg', 'src_page', 'stages'], rows)
    return rows

# ---------------------------------------------------------------- lubrication (2.3)
def extract_lubrication():
    rows = []
    groups = [('B3/B5/B6/B7/B8', 0), ('V1/V5', 1), ('V3/V6', 2)]
    for l in page_lines(37):
        t = toks(l)
        if len(t) == 13 and t[0] in SIZES:
            vals = t[1:]
            for st in range(4):
                for mp, k in groups:
                    v = num(vals[st * 3 + k])
                    if v != '':
                        rows.append(dict(series=S, size=size_name(t[0]), mounting_position=mp, oil_l=v,
                                         oil_type='ISO VG 320 PAO optional first fill (reducer supplied without oil; see extra_lubricant_viscosity.csv)', src_page=37, stages=st + 1))
    # VP combined: NMRV-P worm stage + planetary stage (HL2)
    vpmap = {'P613': '010', 'P623': '020', 'P633': '030', 'P653': '050', 'P983': '080', 'P1133': '130', 'P1183': '180'}
    L = page_lines(37)
    cur = None
    for l in L:
        t = toks(l)
        if len(t) == 2 and t[0].startswith('NMRV-P'):
            cur = ('worm', t[0], num(t[1])); wormoil = cur; continue
        if len(t) == 1 and re.fullmatch(r'P\d+', t[0]):
            vp = t[0]
            rows.append(dict(series=S, size=f'VP {vp}', mounting_position='all', oil_l=wormoil[2], oil_type=f'{wormoil[1]} worm stage: lifetime synthetic polyglycol LAND OIL GEAR SINT (supplied filled)', src_page=37, stages='worm stage'))
            pending_vp = vp
        m = re.match(r'^\s*HL2 (\d{3})\s+((?:[\d,]+\s+){4}[\d,]+)\s*$', l)
        if m:
            v = m.group(2).split()
            for mp, val in zip(['B3/B5', 'B6/B7', 'B8', 'V1/V5', 'V3/V6'], v):
                rows.append(dict(series=S, size=f'VP {pending_vp}', mounting_position=mp, oil_l=num(val), oil_type='planetary part: see HPL lubricant table (supplied without oil)', src_page=37, stages='planetary part (HL2 %s)' % m.group(1)))
    write_csv('lubrication.csv', ['series', 'size', 'mounting_position', 'oil_l', 'oil_type', 'src_page', 'stages'], rows)
    visc = [('n2 > 150 rpm', 'PAO', 150, 60, 70), ('n2 > 150 rpm', 'MIN', 220, 55, 70), ('n2 >= 5 rpm', 'PAO', 220, 70, 80),
            ('n2 >= 5 rpm', 'PAO', 320, 80, 95), ('n2 >= 5 rpm', 'MIN', 320, 65, 80), ('n2 < 5 rpm', 'PAO', 320, 65, 90), ('n2 < 5 rpm', 'MIN', 460, 65, 85)]
    write_csv('extra_lubricant_viscosity.csv', ['series', 'output_speed', 'oil_type', 'iso_vg', 'max_casing_temp_S1_c', 'max_casing_temp_intermittent_or_fs_gt_1_5_c', 'src_page'],
              [dict(series=S, output_speed=a, oil_type=b, iso_vg=c, max_casing_temp_S1_c=d, max_casing_temp_intermittent_or_fs_gt_1_5_c=e, src_page=36) for a, b, c, d, e in visc])
    return rows



# ---------------------------------------------------------------- motor flange availability (4.5), PAM geometry (5.1 tables)
_WORDS = {}
def words_of(p):
    if p not in _WORDS:
        _WORDS[p] = PL.pages[p - 1].extract_words()
    return _WORDS[p]

def extract_flange_availability():
    """4.5 Motor flange availability: one grid per (stages,size); header glyphs are doubled in the PDF text layer ('007711' = 071)."""
    avail = []
    for p in range(46, 55):
        ws = words_of(p)
        lines = {}
        for w in ws:
            lines.setdefault(round(w['top']), []).append(w)
        size = None
        for l in page_lines(p):
            m = re.match(r'^\s*HL (\d{3})\s*$', l)
            if m:
                size = m.group(1)
        tops = sorted(lines)
        titles = []   # (top, x0, stages)
        headers = []  # (top, ix, xr, [(frame, xc)])
        for top in tops:
            lw = sorted(lines[top], key=lambda w: w['x0'])
            doubled = any(w['text'] == 'ii' for w in lw) or any(w['text'] in ('CCHHLL', 'HHLL') for w in lw)
            tx = [(dedouble(w['text']) if doubled else w['text'], w) for w in lw]
            for t, w in tx:
                if re.fullmatch(r'\d-\d{3}', t):
                    titles.append((top, w['x0'], t[0]))
            iws = [w for t, w in tx if t == 'i']
            for k, iw in enumerate(iws):
                xr = iws[k + 1]['x0'] - 5 if k + 1 < len(iws) else 1e9
                frs = [(t, (w['x0'] + w['x1']) / 2) for t, w in tx if iw['x0'] < w['x0'] < xr and re.fullmatch(r'\d{2,3}', t)]
                headers.append((top, iw['x0'], xr, frs))
        for top in tops:
            lw = sorted(lines[top], key=lambda w: w['x0'])
            for h in headers:
                htop, ix, xr, frs = h
                cands = [x for x in headers if x[0] < top and abs(x[1] - ix) < 5]
                if top <= htop or not cands or cands[-1] is not h:
                    continue
                first = [w for w in lw if abs(w['x0'] - ix) < 45 and re.fullmatch(r'[\d\.,]+', w['text'])]
                if not first:
                    continue
                ratio = num(first[0]['text'])
                tt = [t for t in titles if t[0] < htop and ix - 60 <= t[1] < xr]
                stages = tt[-1][2] if tt else ''
                for w in lw:
                    if re.fullmatch(r'B5(-B11)?', w['text']) and ix + 15 < w['x0'] < xr:
                        xc = (w['x0'] + w['x1']) / 2
                        fr = min(frs, key=lambda f: abs(f[1] - xc))
                        avail.append(dict(series=S, size=size_name(size), stages=stages, i=ratio, iec_frame=fr[0].lstrip('0'), flange=w['text'].replace('-', ';'), src_page=p))
    write_csv('extra_motor_flange_availability.csv', ['series', 'size', 'stages', 'i', 'iec_frame', 'flange', 'src_page'], avail)
    return avail

DM = {'71': ('160', '14', '5', '16.3'), '80': ('200', '19', '6', '21.8'), '90': ('200', '24', '8', '27.3'), '100': ('250', '28', '8', '31.3'),
      '112': ('250', '28', '8', '31.3'), '132': ('300', '38', '10', '41.3'), '160': ('350', '42', '12', '45.3'), '180': ('350', '48', '14', '51.8'),
      '200': ('400', '55', '16', '59.3'), '225': ('450', '60', '18', '64.4'), '250': ('550', '65', '18', '69.4')}

def extract_motor_interface(avail):
    # coupling geometry table printed beside each PHL table: B5 frame, Pm, Dm, bm, tm  (verified identical on all pages)
    seen = {}
    pat = re.compile(r'\b(0\d\d|1\d\d|2\d\d)\s+(\d{3})\s+(\d{2})\s+(\d{1,2})\s+(\d\d,\d)\s*$')
    for pg in (56, 59, 60, 64, 65, 70, 71):
        for l in page_lines(pg):
            m = pat.search(l)
            if m:
                fr, pm, dm, bm, tm = m.groups()
                seen[fr.lstrip('0')] = (pm, dm, bm, num(tm), pg)
    for k, v in DM.items():
        if k not in seen or seen[k][:4] != v:
            print('WARN PAM geometry mismatch', k, seen.get(k), v)
    rows = []
    agg = {}
    for a in avail:
        key = (a['size'], a['stages'], a['iec_frame'])
        agg.setdefault(key, {'fl': set(), 'n': 0, 'pg': a['src_page']})
        agg[key]['fl'].add(a['flange']); agg[key]['n'] += 1
    tot = {}
    for a in avail:
        tot.setdefault((a['size'], a['stages']), set()).add(a['i'])
    for (size, st, fr), v in sorted(agg.items()):
        pm, dm, bm, tm, pg = seen.get(fr, ('', '', '', '', ''))
        flg = ';'.join(sorted({x for f in v['fl'] for x in f.split(';')}))
        rows.append(dict(series=S, size=size, iec_frame=fr, flange=flg, bore_mm=dm, src_page=v['pg'], stages=st, pm_mm=pm, bm_mm=bm, tm_mm=tm,
                         ratios_available=v['n'], ratios_total=len(tot[(size, st)]), geometry_src_page=pg))
    write_csv('motor_interface.csv', ['series', 'size', 'iec_frame', 'flange', 'bore_mm', 'src_page', 'stages', 'pm_mm', 'bm_mm', 'tm_mm', 'ratios_available', 'ratios_total', 'geometry_src_page'], rows)
    return rows



# ---------------------------------------------------------------- dimensions (5.1)
# page -> (variant, stages, sizes expected, table kind)
DIM_PAGES = {55: ('HL/PHL-1', 1), 57: ('CHL-1', 1), 58: ('IHL-1', 1), 59: ('HL/PHL-2', 2), 60: ('HL/PHL-2', 2), 61: ('CHL-2', 2),
             62: ('IHL-2', 2), 63: ('IHL-2', 2), 64: ('HL/PHL-3', 3), 65: ('HL/PHL-3', 3), 66: ('CHL-3', 3), 67: ('CHL-3', 3),
             68: ('IHL-3', 3), 69: ('IHL-3', 3), 70: ('HL/PHL-4', 4), 71: ('HL/PHL-4', 4), 72: ('CHL-4', 4), 73: ('CHL-4', 4),
             74: ('IHL-4', 4), 75: ('IHL-4', 4)}

def merge_tol(t):
    """join '(H7/g6)' style tokens onto the previous token"""
    out = []
    for x in t:
        if x.startswith('(') and out:
            out[-1] += ' ' + x
        else:
            out.append(x)
    return out

MAIN_RE = re.compile(r'^\s*(\d{3})\s+(\d{2,3})\s+([hjkm]\d)\s+(.*)$')
FL_RE = re.compile(r'^\s*(\d{3})\s+(\d{3})\s+(\d{3})\s+(\d{3})\s+(.*)$')

def extract_dimensions_gearbox():
    rows = []
    coupling = []
    inp = []
    chl = []
    for pg, (var, stages) in DIM_PAGES.items():
        main = {}
        flange = {}
        lastfl = None
        L = page_lines(pg)
        for idx, l in enumerate(L):
            m = MAIN_RE.match(l)
            if m and len(l.split()) >= 21:
                sz, D, tol, rest = m.groups()
                t = rest.split()
                if len(t) == 18 + 0 or True:
                    # B b t f B1 [G] [G1] C E F H K M N O O_n Q R S T V
                    n = len(t)
                    keys_tail = 'C,E,F,H,K,M,N,O,O_n,Q,R,S,T,V'.split(',')
                    keys_head = 'B,b,t,f,B1'.split(',')
                    mid = n - len(keys_head) - len(keys_tail)
                    if mid not in (0, 1, 2):
                        print('WARN main row', pg, l); continue
                    midk = {0: [], 1: ['G1'], 2: ['G', 'G1']}[mid]
                    r = dict(series=S, size=size_name(sz), variant=var, D=D, D_tol=tol, src_page=pg, stages=stages)
                    for k, v in zip(keys_head + midk + keys_tail, t):
                        r[k] = v.replace('n°', '') if k == 'O_n' else num(v) if k != 'f' else v
                    main[sz] = r
                continue
            ft = l.split()
            # flange rows (010-130 style): size PF MF NF GF JF OF n° SF TF   |  size-only lines
            if re.fullmatch(r'\d{3}', ft[0]) and ft[0] in SIZES and len(ft) >= 2 and any(re.match(r'^\d+°', x) for x in ft):
                if pg == 69 and ft[0] == '380' and len(ft) == 13 and ft[1] == '380':
                    ft = [ft[0]] + ft[2:]   # catalogue anomaly: spurious extra '380' before PF (PF=428 on every other page)
                if len(ft) == 10 and ft[7].startswith('n°'):
                    f = dict(PF=ft[1], MF=ft[2], NF=ft[3], GF=ft[4], JF=ft[5], OF=ft[6], OF_n=ft[7][2:], SF=ft[8], TF=ft[9])
                elif len(ft) == 12 and ft[9].startswith('n°'):
                    f = dict(PF=ft[1], MF=ft[2], NF=ft[3], NF2=ft[4], GF=ft[5], GF2=ft[6], JF=ft[7], OF=ft[8], OF_n=ft[9][2:], TF=ft[10], TF2=ft[11])
                else:
                    # possible 'JF' like 20°/10°/10° makes same token count; handle generic
                    print('WARN flange row', pg, l); continue
                f = {k: num(v) if k != 'JF' else v for k, v in f.items()}
                flange[ft[0]] = f; lastfl = ft[0]
        # propagate shared flange rows (010 -> 020, 030 -> 050) as printed with a combined label
        for sz in list(main):
            if sz not in flange:
                src = {'020': '010', '050': '030'}.get(sz)
                if src and src in flange:
                    flange[sz] = dict(flange[src]); flange[sz]['_shared'] = src
        for sz, r in main.items():
            f = flange.get(sz)
            if f is None:
                print('WARN no flange row', pg, sz); continue
            r.update({k: v for k, v in f.items() if k != '_shared'})
            r['flange_row_shared_with'] = f.get('_shared', '')
            rows.append(r)
        # IHL input shaft table: G3 D2 B2 b2 t2 f2
        for l in L:
            m = re.match(r'^\s*(\d{3}(?:/…/\d{3})?|010/…/\d{3}|\d{3}/…/\d{3})\s+([\d,\.]+)\s+(\d+)\s+([jk]6)\s+(\d+)\s+(\d+)\s+(\d+)\s+(M\d+)\s*$', l)
            if m and var.startswith('IHL'):
                lab, G3, D2, tol, B2, b2, t2, f2 = m.groups()
                if '/' in lab:
                    lo, hi = lab.split('/…/') if '/…/' in lab else (lab.split('/')[0], lab.split('/')[-1])
                    lo = lo; hi = hi
                    sizes = [x for x in main if lo <= x <= hi]
                else:
                    sizes = [lab]
                for sz in sizes:
                    inp.append(dict(series=S, size=size_name(sz), variant=var, G3=num(G3), D2=D2, D2_tol=tol, B2=B2, b2=b2, t2=t2, f2=f2, src_page=pg, stages=stages))
        # CHL motor envelope X, *X, Y, Z (T and TB)
        if var.startswith('CHL'):
            chl_rows = parse_chl_xyz(pg, L)
            sizes = sorted(main)
            for sz in sizes:
                for rr in chl_rows:
                    chl.append(dict(series=S, size=size_name(sz), variant=var + ' ' + rr['version'], motor_frame=rr['frame'], X=rr['X'], X_star=rr['X_star'], Y=rr['Y'], Z=rr['Z'], src_page=pg, stages=stages))
    cols = ['series', 'size', 'variant', 'D', 'D_tol', 'B', 'b', 't', 'f', 'B1', 'G', 'G1', 'C', 'E', 'F', 'H', 'K', 'M', 'N', 'O', 'O_n', 'Q', 'R', 'S', 'T', 'V',
            'PF', 'MF', 'NF', 'NF2', 'GF', 'GF2', 'JF', 'OF', 'OF_n', 'SF', 'TF', 'TF2', 'src_page', 'stages', 'flange_row_shared_with']
    write_csv('dimensions_gearbox.csv', cols, rows)
    write_csv('dimensions_ihl_input_shaft.csv', ['series', 'size', 'variant', 'G3', 'D2', 'D2_tol', 'B2', 'b2', 't2', 'f2', 'src_page', 'stages'], inp)
    write_csv('dimensions_chl_motor_envelope.csv', ['series', 'size', 'variant', 'motor_frame', 'X', 'X_star', 'Y', 'Z', 'src_page', 'stages'], chl)
    return rows

def parse_chl_xyz(pg, L):
    """X, *X, Y, Z rows for CHL ...T (left table) and ...TB (right table).
    The X row is printed on two text lines because several frame cells are merged (71, 100, 132S, 132M/L): the
    first line holds 80, 90S, 90L, 112 and the second line the merged cells (verified on the rendered page)."""
    frames = ['71', '80', '90S', '90L', '100', '112', '132S', '132M/L']
    def find(label, first=True):
        c = [i for i, l in enumerate(L) if label in l.split()]
        return c
    def lr(line, label):
        t = line.split()
        idx = [i for i, x in enumerate(t) if x == label]
        left = t[idx[0] + 1: idx[1]] if len(idx) > 1 else t[idx[0] + 1:]
        right = t[idx[1] + 1:] if len(idx) > 1 else []
        return left, right
    ix = [i for i in find('X') if re.match(r'^\s*X\s+\d', L[i])][0]
    Xl1, Xr1 = lr(L[ix], 'X')
    sec = [x.replace(',', '.') for x in L[ix + 1].split() if re.fullmatch(r'[\d\.,]+', x)]
    assert len(sec) == 8, (pg, sec)
    Sl, Sr = lr(L[find('*X')[0]], '*X')
    Yl, Yr = lr(L[find('Y')[0]], 'Y')
    Zl, Zr = lr(L[find('Z')[0]], 'Z')
    out = []
    for ver, X1, sc, S_, Y_, Z_ in (('T', Xl1, sec[:4], Sl, Yl, Zl), ('TB', Xr1, sec[4:], Sr, Yr, Zr)):
        Xv = {'71': sc[0], '80': X1[0], '90S': X1[1], '90L': X1[2], '100': sc[1], '112': X1[3], '132S': sc[2], '132M/L': sc[3]}
        Sv = {'80': S_[0], '90S': S_[1], '90L': S_[2], '112': S_[3]}
        for fr, y, z in zip(frames, Y_, Z_):
            out.append(dict(version=ver, frame=fr, X=num(Xv[fr]), X_star=num(Sv.get(fr, '')), Y=num(y), Z=num(z)))
    return out


# ---------------------------------------------------------------- radial / axial load (2.2)
VPSZ = {'613': 'P613', '623': 'P623', '633': 'P633', '653': 'P653', '983': 'P983', '1133': 'P1133', '1183': 'P1183'}

def expand_title(title):
    """'HPL 010-020 - VP 613-623' -> [('HPL','010'),('HPL','020'),('VP','P613'),('VP','P623')]"""
    out = []
    m = re.match(r'HPL (\d{3})(?:-(\d{3}))?(?: - VP (\d+)(?:-(\d+))?)?', title)
    a, b, c, d = m.groups()
    hp = SIZES[SIZES.index(a): SIZES.index(b or a) + 1]
    out += [size_name(x) for x in hp]
    if c:
        vps = list(VPSZ)
        out += ['VP ' + VPSZ[x] for x in vps[vps.index(c): vps.index(d or c) + 1]]
    return out

def extract_radial():
    ax, fh, tip = [], [], []
    h2 = ['10000', '25000', '50000', '100000', '300000', '500000', '1000000']
    for p in range(27, 34):
        L = page_lines(p)
        title = None
        for l in L:
            m = re.match(r'^\s*(HPL \d{3}(?:-\d{3})?(?: - VP \d+(?:-\d+)?)?)\s*$', l)
            if m:
                title = m.group(1)
        if title is None:
            continue
        sizes = expand_title(title)
        for l in L:
            m = re.match(r'^\s*CS - SS\s+(\d+)\s+(\d+)\s*$', l)
            if m:
                for sz in sizes:
                    ax.append(dict(series=S, size=sz, variant='CS/SS output shaft', fa2_plus_n=m.group(1), fa2_minus_n=m.group(2), src_page=p))
            m = re.match(r'^\s*(CS - SS|CS|SS)\s+((?:[\d,]+\s+){6}[\d,]+)\s*$', l)
            if m:
                for sz in sizes:
                    for k, v in zip(h2, m.group(2).split()):
                        fh.append(dict(series=S, size=sz, variant=m.group(1).replace(' - ', '/'), fh2_n2h=k, factor=num(v), src_page=p))
            m = re.match(r'^\s*(\d{3})\s+(\d+)\s*$', l)
            if m and m.group(1) in ('180', '220', '380') and p >= 31:
                tip.append(dict(series=S, size=size_name(m.group(1)), variant='T (foot) version, B3 load up / B8 load down', mfr_max_nm=m.group(2), src_page=p))
    write_csv('radial_load_axial.csv', ['series', 'size', 'variant', 'fa2_plus_n', 'fa2_minus_n', 'src_page'], ax)
    write_csv('radial_load_fh2.csv', ['series', 'size', 'variant', 'fh2_n2h', 'factor', 'src_page'], fh)
    write_csv('radial_load_tipping_moment.csv', ['series', 'size', 'variant', 'mfr_max_nm', 'src_page'], tip)
    inp = []
    for l in page_lines(26):
        m = re.match(r'^\s*IHL (\d+x\d+)\s+(\d+) N', l)
        if m:
            inp.append(dict(series=S, size='IHL input shaft ' + m.group(1), variant='load at shaft centre line', fr1_n=m.group(2), src_page=26))
    write_csv('radial_load_input.csv', ['series', 'size', 'variant', 'fr1_n', 'src_page'], inp)
    fz = [('gear pinion', '1.1'), ('chain wheel', '1.4'), ('v-pulley', '1.7'), ('flat pulley', '2.5')]
    write_csv('extra_radial_load_fz.csv', ['series', 'transmission_member', 'fz', 'src_page'], [dict(series=S, transmission_member=a, fz=b, src_page=25) for a, b in fz])
    return ax, fh, tip, inp

# ---------------------------------------------------------------- misc tables (product selection, critical applications, installation, accessories)
def extract_misc():
    # M2max (p16) : HPL 010..130 and 180..380, CS/SS/HS value then HM value
    rows = []
    L = page_lines(16)
    names1 = ['010', '020', '030', '050', '080', '130']
    names2 = ['180', '220', '380']
    for i, l in enumerate(L):
        t = l.split()
        if len(t) == 12 and all(re.fullmatch(r'\d+', x) for x in t):
            for k, sz in enumerate(names1):
                rows.append(dict(series=S, size=size_name(sz), shaft='CS/SS/HS', m2max_nm=t[2 * k], src_page=16))
                rows.append(dict(series=S, size=size_name(sz), shaft='HM (shrink disc by Motovario)', m2max_nm=t[2 * k + 1], src_page=16))
        if len(t) == 6 and all(re.fullmatch(r'\d+', x) for x in t):
            for k, sz in enumerate(names2):
                rows.append(dict(series=S, size=size_name(sz), shaft='CS/SS/HS', m2max_nm=t[2 * k], src_page=16))
                rows.append(dict(series=S, size=size_name(sz), shaft='HM (shrink disc by Motovario)', m2max_nm=t[2 * k + 1], src_page=16))
    write_csv('extra_m2max.csv', ['series', 'size', 'shaft', 'm2max_nm', 'src_page'], rows)
    # ECE gear reducer M2max by ratio (p17)
    ece = []
    cur = None
    L = page_lines(17)
    for i, l in enumerate(L):
        m = re.match(r'^\s*IHL (\d{3})\b', l)
        if m:
            cur = m.group(1); ratios = None; continue
        t = l.split()
        if cur and t and t[0] == 'i' and len(t) > 2:
            ratios = t[1:]
        elif cur and l.strip().startswith('M2max') and ratios:
            vals = l.split()[2:]
            for r_, v in zip(ratios, vals):
                ece.append(dict(series=S, size=size_name(cur), variant='IHL ECE version', i=num(r_), m2max_nm=v, src_page=17))
    write_csv('extra_m2max_ece_by_ratio.csv', ['series', 'size', 'variant', 'i', 'm2max_nm', 'src_page'], ece)
    # M1 max input torque (p18): the version label sits on its own line, rows are in this order
    m1 = []
    order = ['IHL1', 'IHL1', 'IHL2', 'IHL2', 'IHL3-IHL4']
    for l in page_lines(18):
        m = re.match(r'^\s*(?:(?:IHL\d(?:-IHL\d)?)\s+)?(\d{3}(?:-\d{3})?)\s+(\d+)\s+(\d+)\s*$', l)
        if m and len(m1) < 5:
            m1.append(dict(series=S, variant=order[len(m1)], sizes=m.group(1), m1_lt_100000_starts_nm=m.group(2), m1_gt_100000_starts_nm=m.group(3), src_page=18))
    write_csv('extra_m1_input_torque_limit.csv', ['series', 'variant', 'sizes', 'm1_lt_100000_starts_nm', 'm1_gt_100000_starts_nm', 'src_page'], m1)
    # n1max (p45)
    n1 = []
    for l in page_lines(45):
        m = re.match(r'^\s*(\d{3})\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$', l)
        if m and m.group(1) in SIZES:
            for dur, v in zip(('1s', '2s', '3s', '4s'), m.groups()[1:]):
                n1.append(dict(series=S, size=size_name(m.group(1)), duty_duration=dur, n1max_rpm=v, src_page=45))
    write_csv('extra_n1max_intermittent.csv', ['series', 'size', 'duty_duration', 'n1max_rpm', 'src_page'], n1)
    # mounting screws (p22)
    scr = []
    for l in page_lines(22):
        m = re.match(r'^\s*(\d{3}-\d{3}|\d{3})\s+(M\d+x\d+)\s+([\d,]+)\s+n°(\d+)\s+(M\d+x\d+)\s+(\d+)\s+n°(\d+)\s*$', l, re.I)
        if m:
            scr.append(dict(series=S, size=m.group(1), shaft='all', LV_screw=m.group(2), LV_max_hole_dia='', OF_dia=num(m.group(3)), OF_holes=m.group(4), LVP_screw=m.group(5), O_dia=m.group(6), O_holes=m.group(7), src_page=22))
    big = {}
    for l in page_lines(22):
        m = re.match(r'^\s*HPL (\d{3}) (CS-SS|HS|HM)\s*(M16x\d+)?(?:\s+(\d+)\s+N[º°](\d+)\s+/\s+(\d+)\s+n°(\d+))?\s*$', l)
        if m:
            sz, sh, scw, od, of_n, o_d, o_n = m.groups()
            big.setdefault(sz, {})[sh] = scw
            if od:
                big[sz]['_oth'] = (od, of_n, o_d, o_n)
    for sz, d in big.items():
        od, of_n, o_d, o_n = d['_oth']
        known = [v for k, v in d.items() if k != '_oth' and v]
        for sh in ('CS-SS', 'HS', 'HM'):
            v = d.get(sh) or (known[0] if sz == '380' else '')
            scr.append(dict(series=S, size=sz, shaft=sh, LV_screw=v + ' (min length)', OF_dia=od, OF_holes=of_n, LVP_screw='', O_dia=o_d, O_holes=o_n, src_page=22))
    write_csv('extra_mounting_screws.csv', ['series', 'size', 'shaft', 'LV_screw', 'OF_dia', 'OF_holes', 'LVP_screw', 'O_dia', 'O_holes', 'src_page'], scr)
    # backstop (p94): the 'HL n' label is on a separate line; rows come in fixed groups (4,5,8,7 rows)
    bs = []
    frames = ['71', '80', '90', '100-112', '132', '160', '180', '200']
    groups = [('1', 4), ('2', 5), ('3', 8), ('4', 7)]
    rowsb = []
    for l in page_lines(94):
        m = re.match(r'^\s*(?:HL ?\d\s+)?(\d{3}(?:/\d{3})*)\s+((?:(?:B5|/)\s+){7}(?:B5|/))\s*$', l)
        if m:
            rowsb.append((m.group(1), m.group(2).split()))
    assert len(rowsb) == 24, len(rowsb)
    k = 0
    for g, n in groups:
        for lab, vals in rowsb[k:k + n]:
            labs = lab.split('/')
            if g == '1' and lab.startswith('050'):
                labs = ['050', '080', '130', '180', '220', '380']
            for sz in labs:
                for fr, v in zip(frames, vals):
                    bs.append(dict(series=S, size=size_name(sz), stages=g, iec_frame=fr, flange='' if v == '/' else v, available='yes' if v == 'B5' else 'no', src_page=94))
        k += n
    write_csv('extra_backstop_availability.csv', ['series', 'size', 'stages', 'iec_frame', 'flange', 'available', 'src_page'], bs)
    return rows



# ---------------------------------------------------------------- PHL coupling lengths (G, G1, G2 by IEC motor frame)
def extract_phl_coupling():
    rows = []
    pages = {56: ('HL/PHL-1', 1, ['010', '020', '030', '050', '080', '130'], 2), 59: ('HL/PHL-2', 2, ['010', '020', '030', '050', '080', '130'], 2),
             60: ('HL/PHL-2', 2, ['180', '220', '380'], 3), 64: ('HL/PHL-3', 3, ['010', '020', '030', '050', '080', '130'], 2),
             65: ('HL/PHL-3', 3, ['180', '220', '380'], 3), 70: ('HL/PHL-4', 4, ['010', '020', '030', '050', '080', '130'], 2),
             71: ('HL/PHL-4', 4, ['180', '220', '380'], 3)}
    pat = re.compile(r'^\s*(71|80|90|100-112|100-|132|160|180|200|225|250)\s+(\d+)x(\d+)\s+(.*)$')
    for pg, (var, st, sizes, per) in pages.items():
        for l in page_lines(pg):
            m = pat.match(l)
            if not m:
                continue
            fr, pm, dm, rest = m.groups()
            fr = '100-112' if fr == '100-' else fr
            t = rest.split()[:per * len(sizes)]
            if len(t) != per * len(sizes):
                print('WARN phl row', pg, l); continue
            for k, sz in enumerate(sizes):
                v = t[k * per:(k + 1) * per]
                if all(x == '/' for x in v):
                    continue
                r = dict(series=S, size=size_name(sz), variant=var, iec_frame=fr, Pm=pm, Dm=dm, src_page=pg, stages=st)
                if per == 2:
                    r['G'], r['G2'] = num(v[0]), num(v[1])
                else:
                    r['G'], r['G1'], r['G2'] = [num(x) for x in v]
                rows.append(r)
    write_csv('dimensions_phl_coupling.csv', ['series', 'size', 'variant', 'iec_frame', 'Pm', 'Dm', 'G', 'G1', 'G2', 'src_page', 'stages'], rows)
    return rows

# ---------------------------------------------------------------- output shaft options and accessories (6.x), shaft end keys (5.3)
def tolmerge(t):
    return merge_tol(t)

def extract_shaft_options():
    # --- shrink disc shafts HM0/HM1 (p84 small, p86 large)
    rows = []
    for pg in (84, 86):
        for l in page_lines(pg):
            m = re.match(r'^\s*(\d{3})\s+(.*)$', l)
            if not m or m.group(1) not in SIZES or '(H' not in m.group(2):
                continue
            t = re.findall(r'\d+(?:,\d+)?(?:\s*\([^)]*\))?', m.group(2))
            t = [x for x in t]
            if pg == 84 and len(t) == 12:
                keys = 'D3,D4,D5,G4,R,T1,T2,T3,T4,X_min,CL,MT_nm'.split(',')
            elif pg == 86 and len(t) == 9:
                keys = 'D3,D5,G4,R,T1,T3,X_min,CL,MT_nm'.split(',')
            else:
                continue
            r = dict(series=S, size=size_name(m.group(1)), variant='HM0/HM1 shrink-disc hollow shaft (F version only, not V3)', src_page=pg)
            for k, v in zip(keys, t):
                mm = re.match(r'^(\d+(?:,\d+)?)\s*(?:\(([^)]*)\))?$', v)
                r[k] = num(mm.group(1))
                if mm.group(2):
                    r[k + '_tol'] = mm.group(2)
            rows.append(r)
    write_csv('dimensions_shrink_disk_shaft.csv', ['series', 'size', 'variant', 'D3', 'D3_tol', 'D4', 'D4_tol', 'D5', 'G4', 'R', 'T1', 'T2', 'T3', 'T4', 'X_min', 'CL', 'MT_nm', 'src_page'], rows)
    # --- splined solid shaft SS (p87, p88)
    rows = []
    for pg in (87, 88):
        for l in page_lines(pg):
            m = re.match(r'^\s*(\d{3})\s+(B\d+x\d+ DIN5482)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(M\d+x\d+)\s*$', l)
            if m:
                g = m.groups()
                rows.append(dict(series=S, size=size_name(g[0]), variant='SS splined solid shaft', D1=g[1], D2_f7=g[2], D3_f7=g[3], D4=g[4], L1=g[5], L2=g[6], L3=g[7], L4=g[8], MxL=g[9], src_page=pg))
            m = re.match(r'^\s*(\d{3})\s+(B\d+x\d+ DIN5482)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(M\d+x\d+)', l)
    write_csv('dimensions_splined_solid_shaft.csv', ['series', 'size', 'variant', 'D1', 'D2_f7', 'D3_f7', 'D4', 'L1', 'L2', 'L3', 'L4', 'MxL', 'src_page'], rows)
    # --- splined hollow shaft HS (p89 small, p90 large)
    rows = []
    for pg in (89,):
        for l in page_lines(pg):
            m = re.match(r'^\s*(\d{3})\s+(A\d+x\d+ DIN5482)\s+(\d+ H\d)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d,]+)\s+([\d,]+)\s*$', l)
            if m:
                g = m.groups()
                rows.append(dict(series=S, size=size_name(g[0]), variant='HS splined hollow shaft', D1=g[1], D=g[2].split()[0], D_tol=g[2].split()[1], D2_H8=g[3], L=g[4], L1=g[5], L2=num(g[6]), L3=num(g[7]), src_page=pg))
    for l in page_lines(90):
        m = re.match(r'^\s*(\d{3})\s+(A\d+x\d+(?: H10)? DIN ?5482)\s+(\d+ H\d)\s+(\d+)\s+(\d+)\s*$', l)
        if m:
            g = m.groups()
            rows.append(dict(series=S, size=size_name(g[0]), variant='HS splined hollow shaft', D1=g[1], D=g[2].split()[0], D_tol=g[2].split()[1], L1=g[3], L2=g[4], src_page=90))
    write_csv('dimensions_splined_hollow_shaft.csv', ['series', 'size', 'variant', 'D1', 'D', 'D_tol', 'D2_H8', 'L', 'L1', 'L2', 'L3', 'src_page'], rows)
    # --- wheel flange (p91, first table) and axial fixing washer (p91 second table = p92)
    rows = []; wr = []
    for l in page_lines(91):
        m = re.match(r'^\s*(\d{3})\s+(A\d+x\d+(?: H10)? DIN ?5482)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d,]+)\s+\(n°(\d+)\)\s*$', l)
        if m:
            g = m.groups()
            keys = 'D1,D2_H7,D3_f7,D4,D5,A,B,C,L,L1,L2,L3,J,O'.split(',')
            r = dict(series=S, size=size_name(g[0]), variant='wheel flange (for SS shaft)', src_page=91)
            for k, v in zip(keys, g[1:15]):
                r[k] = num(v)
            r['O_n'] = g[15]
            rows.append(r)
    write_csv('dimensions_wheel_flange.csv', ['series', 'size', 'variant', 'D1', 'D2_H7', 'D3_f7', 'D4', 'D5', 'A', 'B', 'C', 'L', 'L1', 'L2', 'L3', 'J', 'O', 'O_n', 'src_page'], rows)
    for pg in (92,):
        for l in page_lines(pg):
            m = re.match(r'^\s*(\d{3})\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d,]+)\s+([\d,]+)\s+(M\d+x\d+)\s+\(n°(\d+)\)\s*$', l)
            if m:
                g = m.groups()
                wr.append(dict(series=S, size=size_name(g[0]), variant='axial fixing washer (for SS shaft)', DC_H7=g[1], D1C_f7=g[2], D2C=g[3], D4C=g[4], LC=num(g[5]), L1C=num(g[6]), MxLV=g[7], MxLV_n=g[8], src_page=pg))
    write_csv('dimensions_axial_fixing_washer.csv', ['series', 'size', 'variant', 'DC_H7', 'D1C_f7', 'D2C', 'D4C', 'LC', 'L1C', 'MxLV', 'MxLV_n', 'src_page'], wr)
    # --- torque arm (p93)
    ta = []
    for l in page_lines(93):
        m = re.match(r'^\s*(\d{3})\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$', l)
        if m and m.group(1) in SIZES:
            g = m.groups()
            ta.append(dict(series=S, size=size_name(g[0]), variant='torque arm (suggested values, S355JR, F version)', KI=g[1], KL=g[2], KH=g[3], G=g[4], G1=g[5], S=g[6], src_page=93))
    write_csv('dimensions_torque_arm.csv', ['series', 'size', 'variant', 'KI', 'KL', 'KH', 'G', 'G1', 'S', 'src_page'], ta)
    # --- shaft end keys UNI 6604 / DIN 6885 (p79)
    keys = []
    for l in page_lines(79):
        m = re.match(r'^\s*(?:>\s*)?(\d+)\s+(\d+)\s+(\d+)\s*[×x]\s*(\d+)\s+(?:h\d\s*/\s*h\d+\s+)?(\d+)\s+(\d+)\s+(.*)$', l)
        if not m:
            continue
        d1, d2, b, h, lmin, lmax, rest = m.groups()
        t = [x for x in rest.split()]
        # drop tolerance tokens until the repeated b
        k = next((i for i, x in enumerate(t) if x == b), None)
        if k is None or len(t) < k + 3:
            print('WARN key row', l); continue
        keys.append(dict(series=S, d_over_mm=d1, d_up_to_mm=d2, b=b, h=h, L_min=lmin, L_max=lmax, t1=num(t[k + 1]), t2=num(t[k + 2]), src_page=79))
    write_csv('extra_shaft_end_keys.csv', ['series', 'd_over_mm', 'd_up_to_mm', 'b', 'h', 'L_min', 'L_max', 't1', 't2', 'src_page'], keys)

# ---------------------------------------------------------------- working cycles n2*h (7.6)
N2H = ['10000', '25000', '50000', '100000', '300000', '500000', '1000000', '1800000', '2500000', '3500000', '5000000']

def extract_working_cycles():
    rows = []
    for p in range(168, 187):
        pg = PL.pages[p - 1]
        ws = words_of(p)
        darks = [r for r in pg.rects if r.get('fill') and isinstance(r.get('non_stroking_color'), (tuple, list)) and tuple(round(x, 2) for x in r['non_stroking_color']) == (0.04, 0.16, 0.22) and r['height'] < 16 and 30 < r['width'] < 50]
        lines = {}
        for w in ws:
            lines.setdefault(round(w['top']), []).append(w)
        title = None
        for top in sorted(lines):
            lw = sorted(lines[top], key=lambda w: w['x0'])
            t = ' '.join(w['text'] for w in lw)
            m = re.match(r'^HL(\d) / IHL(\d) (\d{3})$', t)
            if m:
                title = m.groups(); continue
            if title and len(lw) == 12 and re.fullmatch(r'\d+(?:,\d+)?', lw[0]['text']) and all(re.fullmatch(r'\d+', w['text']) for w in lw[1:]):
                hl = []
                for w, n in zip(lw[1:], N2H):
                    cx = (w['x0'] + w['x1']) / 2; cy = (w['top'] + w['bottom']) / 2
                    if any(r['x0'] <= cx <= r['x1'] and r['top'] <= cy <= r['bottom'] for r in darks):
                        hl.append(n)
                for w, n in zip(lw[1:], N2H):
                    rows.append(dict(series=S, size=size_name(title[2]), variant=f'HL{title[0]} / IHL{title[1]}', stages=title[0], i=num(lw[0]['text']), n2h=n, mn2_nm=w['text'],
                                     check_input_torque='yes' if n in hl else '', src_page=p))
    write_csv('extra_working_cycles.csv', ['series', 'size', 'variant', 'stages', 'i', 'n2h', 'mn2_nm', 'check_input_torque', 'src_page'], rows)
    return rows

# ---------------------------------------------------------------- VP combined (worm + planetary) tables
VPLIST = ['P613', 'P623', 'P633', 'P653', 'P983', 'P1133', 'P1183']

def extract_vp_tables():
    # mesh data p193
    ratios = ['7.5', '10', '15', '20', '25', '30', '40', '50', '60', '80', '100']
    rows = []
    L = page_lines(193)
    groups = [['P613', 'P623', 'P633', 'P653'], ['P983'], ['P1133', 'P1183']]
    gi = -1
    kinds = []
    for l in L:
        t = l.split()
        if ('ηδ(1400)' in t or 'ηs' in t or any('1400' in x for x in t)) and len(t) >= 12:
            vals = t[-11:]
            kind = 'eta_s' if 'ηs' in t[:2] else 'eta_dyn_1400'
            kinds.append((kind, vals))
    # order printed: [dyn, s] for each of three groups (first group dyn line carries the label 'P613')
    assert len(kinds) == 6, kinds
    for g, (d, st) in zip(groups, (kinds[0:2], kinds[2:4], kinds[4:6])):
        for sz in g:
            for r_, a, b in zip(ratios, d[1], st[1]):
                rows.append(dict(series=S, size=f'VP {sz}', i_worm=r_, eta_dyn_1400=num(a), eta_static=num(b), src_page=193))
    write_csv('extra_vp_efficiency.csv', ['series', 'size', 'i_worm', 'eta_dyn_1400', 'eta_static', 'src_page'], rows)
    # ratio tables p197
    rt = []
    L = page_lines(197)
    first = ['P613', 'P623', 'P633', 'P653']
    second = ['P983', 'P1133', 'P1183']
    part = 1
    for l in L:
        if re.match(r'^\s*i\s+VP\s+i1\s+i2\s+i\s+VP', l):
            part = 2 if part == 1 and any(True for _ in ()) is False and rt else part
        t = [x for x in l.split() if x not in ('VP',) and not re.fullmatch(r'P\d+', x)]
        if all(re.fullmatch(r'[\d,]+', x) for x in t) and t:
            n = len(t)
            if n % 3 == 0 and n >= 3 and all(re.fullmatch(r'\d+,\d', t[i + 2]) for i in range(0, n, 3)):
                blocks = [t[i:i + 3] for i in range(0, n, 3)]
                names = first if (n == 12 and not rt_second_started(rt)) else second
                for nm, b in zip(names, blocks):
                    rt.append(dict(series=S, size=f'VP {nm}', i=num(b[0]), i_worm=num(b[1]), i_planetary=num(b[2]), src_page=197))
    write_csv('extra_vp_ratios.csv', ['series', 'size', 'i', 'i_worm', 'i_planetary', 'src_page'], rt)
    return rows

def rt_second_started(rt):
    return any(r['size'] in ('VP P983', 'VP P1133', 'VP P1183') for r in rt)



def extract_vp_dims():
    # VP flange availability (p196)
    structure = [(['P613', 'P623', 'P633', 'P653'], ['90', '80', '71']), (['P983'], ['100/112', '90', '80']), (['P1133', 'P1183'], ['132', '100/112', '90', '80'])]
    pam = []; sym = []
    ratios = ['5', '7.5', '10', '15', '20', '25', '30', '40', '50', '60', '80', '100']
    for l in page_lines(196):
        t = l.split()
        m = re.match(r'^\s*(?:P\d+\s+)*(\d+(?:/\d+)?B(?:5|14))\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)(.*)$', l)
        if m:
            name, N, M, P, D, rest = m.groups()
            pam.append(dict(pam=name, N=N, M=M, P=P, D=D))
            tt = rest.split()
            if len(tt) == 12:
                sym.append(tt)
            continue
        tt = [x for x in l.split() if not re.fullmatch(r'P\d+', x)]
        if len(tt) == 12 and all(x in ('**', '•', '+') for x in tt):
            sym.append(tt)
    rows = []
    # expected symbol-rows: 3 (P613..653), 3 (P983), 4 (P1133/P1183: 132B5 inline + 3 pairs)
    assert len(sym) == 10, len(sym)
    si = 0; pi = 0
    for sizes, frames in structure:
        for fr in frames:
            n_pam = 1 if fr == '132' else 2
            symrow = sym[si]; si += 1
            for pm in pam[pi:pi + n_pam]:
                for sz in sizes:
                    for r_, v in zip(ratios, symrow):
                        rows.append(dict(series=S, size=f'VP {sz}', pam_iec=pm['pam'], N=pm['N'], M=pm['M'], P=pm['P'], D=pm['D'], i_worm=r_,
                                         status={'•': 'feasible', '**': 'not feasible', '+': 'not to be used (out of warranty)'}[v], src_page=196))
            pi += n_pam
    write_csv('extra_vp_flange_availability.csv', ['series', 'size', 'pam_iec', 'N', 'M', 'P', 'D', 'i_worm', 'status', 'src_page'], rows)

    # VP dimensions p198 / p199 (main + flange + Z/Z1)
    out = []
    zmap = {}
    for pg in (198, 199):
        L = page_lines(pg)
        for l in L:
            m = re.match(r'^\s*(P\d+)\s+([\d,]+)\s+([\d,]+)\s*$', l)
            if m:
                zmap[m.group(1)] = (num(m.group(2)), num(m.group(3)))
        main = {}; fl = {}
        for l in L:
            m = re.match(r'^\s*(P\d+)\s+(\d+)\s+([hm]\d)\s+(.*)$', l)
            if m:
                sz, D, tol, rest = m.groups()
                t = rest.split()
                keys = 'B,b,t,f,B1,C,E,F,H,K,M,N,O,O_n,Q,R,S,T,V'.split(',')
                if len(t) != len(keys):
                    print('WARN vp main', l); continue
                r = dict(series=S, size=f'VP {sz}', variant='VP reducer (T/F)', D=D, D_tol=tol, src_page=pg)
                for k, v in zip(keys, t):
                    r[k] = v.replace('n°', '') if k == 'O_n' else (v if k == 'f' else num(v))
                main[sz] = r
            ft = l.split()
            if ft and re.fullmatch(r'P\d+', ft[0]) and any(re.match(r'^\d+°', x) for x in ft):
                if len(ft) == 10:
                    fl[ft[0]] = dict(PF=ft[1], MF=ft[2], NF=ft[3], GF=ft[4], JF=ft[5], OF=ft[6], OF_n=ft[7][2:], SF=ft[8], TF=ft[9])
                elif len(ft) == 12:
                    fl[ft[0]] = dict(PF=ft[1], MF=ft[2], NF=ft[3], NF2=ft[4], GF=ft[5], GF2=ft[6], JF=ft[7], OF=ft[8], OF_n=ft[9][2:], TF=ft[10], TF2=ft[11])
        # shared flange rows: P623 <- P613 ; P653 <- P633
        for sz in main:
            f = fl.get(sz) or fl.get({'P623': 'P613', 'P653': 'P633'}.get(sz, ''))
            if f is None:
                print('WARN vp flange', sz); continue
            main[sz].update({k: num(v) if k != 'JF' else v for k, v in f.items()})
            if sz in ('P623', 'P653'):
                main[sz]['flange_row_shared_with'] = {'P623': 'P613', 'P653': 'P633'}[sz]
            out.append(main[sz])
    for r in out:
        sz = r['size'].split()[1]
        if sz in zmap:
            r['Z'], r['Z1'] = zmap[sz]
    cols = ['series', 'size', 'variant', 'D', 'D_tol', 'B', 'b', 't', 'f', 'B1', 'C', 'E', 'F', 'H', 'K', 'M', 'N', 'O', 'O_n', 'Q', 'R', 'S', 'T', 'V', 'Z', 'Z1',
            'PF', 'MF', 'NF', 'NF2', 'GF', 'GF2', 'JF', 'OF', 'OF_n', 'SF', 'TF', 'TF2', 'src_page', 'flange_row_shared_with']
    write_csv('dimensions_vp.csv', cols, out)
    # worm-stage input dimensions p200 (left table only; raw strings for the 3 size groups)
    ws = words_of(200)
    lines = {}
    for w in ws:
        if w['x0'] < 330 and 60 < w['top'] < 780:
            lines.setdefault(round(w['top'] / 2), []).append(w)
    rows = []
    for k in sorted(lines):
        lw = sorted(lines[k], key=lambda w: w['x0'])
        sym_ = lw[0]['text']
        if sym_ in ('A', 'A1', 'B', 'D1', 'G', 'G1', 'G3', 'H', 'H1', 'I', 'K', 'KE', 'L', 'M', 'N', 'N1', 'O', 'P', 'Q', 'R', 'S', 'S1', 'V', 'W', 'b1', 't1', 'f1'):
            cols_ = {'c1': [], 'c2': [], 'c3': []}
            for w in lw[1:]:
                xc = (w['x0'] + w['x1']) / 2
                key = 'c1' if xc < 150 else 'c2' if xc < 215 else 'c3'
                cols_[key].append(w['text'])
            if sym_ == 'P' and any(x in ('P',) for x in cols_['c1']):
                continue   # vertical axis label of the drawing, not a table row
            if sym_ == 'D1':
                cols_['c1'] = [x for x in cols_['c1'] if x != 'j6']
                sym_ = 'D1 (j6)'
            if sym_ == 'G' and not cols_['c3']:
                assert '185,5 (PAM 132)' in TXT[199] and '168 (PAM 080/112)' in TXT[199]
                cols_['c3'] = ['185.5 (PAM 132); 168 (PAM 080/112)']
            rows.append(dict(series=S, size='VP worm input (P613-P653 | P983 | P1133-P1183)', variant='worm-stage PAM flange', symbol=sym_,
                             P613_P653=num(' '.join(cols_['c1'])) if len(cols_['c1']) == 1 else ' '.join(cols_['c1']),
                             P983=num(' '.join(cols_['c2'])) if len(cols_['c2']) == 1 else ' '.join(cols_['c2']),
                             P1133_P1183=num(' '.join(cols_['c3'])) if len(cols_['c3']) == 1 else ' '.join(cols_['c3']), src_page=200))
    write_csv('dimensions_vp_worm_input.csv', ['series', 'size', 'variant', 'symbol', 'P613_P653', 'P983', 'P1133_P1183', 'src_page'], rows)
    # VPL torque limiter (p205)
    vpl = []
    for l in page_lines(205):
        m = re.match(r'^\s*(I|S|Dg|g)\s+([\d,\.]+|M\d+x[\d,\.]+)\s+([\d,\.]+|M\d+x[\d,\.]+)\s*$', l)
        if m:
            vpl.append(dict(series=S, size='VPL P613-P653 | P983', variant='torque limiter', symbol=m.group(1), P613_P653=num(m.group(2)) if not m.group(2).startswith('M') else m.group(2), P983=num(m.group(3)) if not m.group(3).startswith('M') else m.group(3), src_page=205))
    write_csv('dimensions_vpl_torque_limiter.csv', ['series', 'size', 'variant', 'symbol', 'P613_P653', 'P983', 'src_page'], vpl)



# ---------------------------------------------------------------- designation.json (pages 39-40, 41-42, 188-191) -- hand-transcribed from the rendered flow charts
def build_designation():
    d = {
        'series': S,
        'source_pages': [39, 40, 41, 42, 188, 189, 190, 191],
        'note': 'Transcribed from the designation flow charts (PDF p.39 for HL, p.188 for VP) which are raster images; verified on rendered pages. '
                'Right-angle codes (PHB, HB, CHB, IHB and mounting B3A..V3D) appear in the chart but belong to another catalogue (not tabulated here).',
        'HL': {
            'pattern': 'HL 2 010 F 300x38 CS 50x82 3,44 B3 [accessories-options]',
            'segments': [
                {'name': 'gearbox_type', 'example': 'HL', 'values': {
                    'PHL': 'coaxial planetary, PAM motor-mounting version fitted for motor with flexible coupling (up to IEC 132)',
                    'HL': 'coaxial planetary, PAM motor reducer (flange + coupling for IEC motor; geared motor version)',
                    'CHL': 'coaxial planetary, compact electric motor version (motor flange-mounted directly, B11 compact)',
                    'IHL': 'coaxial planetary, input shaft version (gear reducer)',
                    'PHB': 'right angle (not in this catalogue)', 'HB': 'right angle (not in this catalogue)', 'CHB': 'right angle (not in this catalogue)', 'IHB': 'right angle (not in this catalogue)'}},
                {'name': 'stages', 'example': '2', 'values': {'1': '1 stage', '2': '2 stages', '3': '3 stages', '4': '4 stages'}},
                {'name': 'size', 'example': '010', 'values': {k: f'HPL size {k}' for k in SIZES}},
                {'name': 'casing_version', 'example': 'F', 'values': {'T': 'foot', 'F': 'flange'}},
                {'name': 'input_dimension', 'example': '300x38', 'values': {'55X110': 'ECE (input shaft version)', '300X38': 'PAM (flange diameter Pm x motor shaft bore Dm, e.g. 300x38 = IEC 132)'},
                 'iec_pam_codes': {fr: f'{v[0]}x{v[1]}' for fr, v in DM.items()}},
                {'name': 'output_shaft_version', 'example': 'CS', 'values': {'CS': 'solid shaft (keyed)', 'SS': 'splined solid shaft (DIN 5482)', 'HS': 'splined hollow shaft (DIN 5482)',
                                                                           'HM1': 'hollow shaft with shrink disc (disc supplied unassembled)', 'HM0': 'hollow shaft for shrink disc (disc not supplied)'}},
                {'name': 'output_dimension', 'example': '50x82', 'values': {'DxL': 'shaft diameter x length, e.g. 50x82', 'D': 'diameter only, e.g. 35'}},
                {'name': 'reduction_ratio', 'example': '3,44', 'values': {'range': 'from 3,44 to 2500 (exact ratios in ratings.csv / extra_motor_flange_availability.csv)'}},
                {'name': 'mounting_position_version_L', 'example': 'B3', 'values': {
                    'B3': 'foot, horizontal (T)', 'B6': 'foot, wall (T)', 'B7': 'foot, wall (T)', 'B8': 'foot, ceiling (T)', 'V5': 'foot, vertical output down-side wall (T) (flange version equivalent V1)',
                    'V6': 'foot, vertical wall (T) (flange version equivalent V3)', 'B5': 'flange horizontal (F) (equivalent of B3 for flange)', 'V1': 'flange vertical output down (F)', 'V3': 'flange vertical output up (F)'},
                 'note': 'p.41: HL..T uses B3, B6, B7, B8, V5, V6; HL..F uses B5, V1, V3. B3 gives lower oil splash, better lubrication and less heating. Chart shows B3 (B5), V5 (V1), V6 (V3).'},
                {'name': 'accessories_options', 'example': '...', 'values': {'see': 'shaft options, wheel flange, axial washer, torque arm, backstop, reinforced seals VR/VRM or FPM, blue RAL 5010 paint, VG320 PAO first fill (sections 6.1-6.7)'}},
            ],
            'terminal_box_position': {'values': {'1': 'top (default)', '2': 'right', '3': 'bottom', '4': 'left'}, 'note': 'Default position 1 unless specified (p.40).'},
        },
        'VP': {
            'pattern': 'VP P613 F 300x38 CS 50x82 348 AK B3 [accessories-options]',
            'segments': [
                {'name': 'gearbox_type', 'example': 'VP', 'values': {'VP': 'combined reducer (NMRV-P worm first stage + 2 planetary stages)', 'VPL': 'combined reducer with torque limiter (P613-P983)'}},
                {'name': 'size', 'example': 'P613', 'values': {k: f'VP {k}' for k in VPLIST}},
                {'name': 'casing_version', 'example': 'F', 'values': {'T': 'foot', 'F': 'flange'}},
                {'name': 'input_dimension', 'example': '300x38', 'values': {'PAM': 'PAM flange for IEC motor'}},
                {'name': 'output_shaft_version', 'example': 'CS', 'values': {'CS': 'solid shaft', 'SS': 'splined solid shaft', 'HS': 'splined hollow shaft', 'HM1': 'shrink disc shaft (disc supplied)', 'HM0': 'hollow shaft for shrink disc'}},
                {'name': 'output_dimension', 'example': '50x82', 'values': {'DxL': 'diameter x length', 'D': 'diameter'}},
                {'name': 'reduction_ratio', 'example': '348', 'values': {'range': 'from 215 to 3190 (extra_vp_ratios.csv)'}},
                {'name': 'execution', 'values': {c: 'worm-stage input/shaft execution (drawings p.190)' for c in ('AJ', 'AK', 'BJ', 'BK', 'PJ', 'PK', 'VJ', 'VK')}},
                {'name': 'mounting_position', 'example': 'B3', 'values': {'B3 (B5)': 'standard B3/AK', 'B6': '', 'B7': '', 'B8': '', 'V5 (V1)': '', 'V6 (V3)': ''}},
                {'name': 'accessories_options', 'example': '...', 'values': {'see': 'section 11 / HPL section 6'}},
            ],
        },
    }
    with open(os.path.join(OUT, 'designation.json'), 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print('designation.json written')

# ---------------------------------------------------------------- images
def image_plan():
    """page -> (kind, caption-prefix).  Embedded rasters in this PDF are the drawings/renders themselves."""
    plan = {1: ('photo', 'cover')}
    for p in (22, 23): plan[p] = ('diagram', 'installation')
    for p in range(26, 34): plan[p] = ('diagram', 'radial/axial load')
    plan.update({39: ('diagram', 'designation flow chart HL'), 40: ('diagram', 'versions legend'), 41: ('render', 'mounting positions'), 42: ('drawing', 'terminal box positions')})
    for p in range(55, 76):
        if p != 56: plan[p] = ('drawing', 'dimensions')
    plan.update({79: ('drawing', 'shaft end key'), 80: ('drawing', 'electric motor dimensions'), 81: ('drawing', 'electric motor dimensions')})
    for p in range(84, 96): plan[p] = ('drawing', 'accessory / shaft option')
    plan.update({188: ('diagram', 'designation flow chart VP'), 189: ('diagram', 'VP modularity legend'), 190: ('render', 'VP mounting positions / executions'), 191: ('drawing', 'VP terminal box'),
                 194: ('diagram', 'VP direction of rotation'), 196: ('drawing', 'VP motor flange'), 197: ('render', 'VP combined reducer'),
                 198: ('drawing', 'VP dimensions'), 199: ('drawing', 'VP dimensions'), 200: ('drawing', 'VP worm input dimensions'), 202: ('drawing', 'VP shaft cover'),
                 204: ('diagram', 'torque limiter principle'), 205: ('drawing', 'VPL dimensions'), 206: ('diagram', 'VPL adjustment graphs')})
    return plan

def extract_images():
    import shutil
    from PIL import Image
    imgdir = os.path.join(OUT, 'images')
    os.makedirs(imgdir, exist_ok=True)
    rows = []
    tmp = os.path.join('/tmp', 'hpl_img_render') if not os.environ.get('HPL_TMP') else os.environ['HPL_TMP']
    os.makedirs(tmp, exist_ok=True)
    for p, (kind, cap) in sorted(image_plan().items()):
        pg = PL.pages[p - 1]
        imgs = [i for i in pg.images if (i['x1'] - i['x0']) > 30 and (i['bottom'] - i['top']) > 30]
        # drop full-page background (divider pages) and tiny logos
        imgs = [i for i in imgs if not ((i['x1'] - i['x0']) > 560 and (i['bottom'] - i['top']) > 800)]
        if p == 1:
            imgs = [i for i in imgs if i['srcsize'] and i['srcsize'][0] in (1000, 1207)]
        imgs.sort(key=lambda i: (round(i['top'] / 5), i['x0']))
        if not imgs:
            continue
        subprocess.run(['pdftoppm', '-r', '220', '-f', str(p), '-l', str(p), '-png', PDF, os.path.join(tmp, f'p{p}')], check=True)
        pngs = [f for f in os.listdir(tmp) if f.startswith(f'p{p}-')]
        page_img = Image.open(os.path.join(tmp, pngs[0])).convert('RGB')
        sc = 220 / 72.0
        head = ''
        for l in page_lines(p)[1:4]:
            if re.match(r'^\s*\d+\.\d+', l) or re.match(r'^\s*[A-Z0-9 /\.\-]+\s{3,}TECHNICAL', l):
                head = re.sub(r'\s{2,}.*', '', l.strip())
                break
        sub = next((re.sub(r'\s+', ' ', l.strip()) for l in page_lines(p)[2:6] if re.match(r'^\s*\d+\.\d+\.\d+', l)), '')
        for n, im in enumerate(imgs, 1):
            box = (int(im['x0'] * sc), int(im['top'] * sc), int(im['x1'] * sc), int(im['bottom'] * sc))
            crop = page_img.crop(box)
            k = kind
            if p == 190 and (im['x1'] - im['x0']) < 150:
                k = 'diagram'
            name = f'HPL_general_{k}_p{p}_{n}.png'
            crop.save(os.path.join(imgdir, name))
            rows.append(dict(file=name, series=S, size='general', kind=k, caption=f'{cap}' + (f' - {head}' if head else '') + (f' ({sub})' if sub and sub != head else ''),
                             src_page=p, width_px=crop.width, height_px=crop.height))
    write_csv('images/index.csv', ['file', 'series', 'size', 'kind', 'caption', 'src_page', 'width_px', 'height_px'], rows)
    return rows


if __name__ == '__main__':
    extract_motors()
    extract_motors_dimensions()
    extract_ratings()
    extract_service_factor()
    extract_thermal()
    extract_weights()
    extract_lubrication()
    extract_motor_interface(extract_flange_availability())
    extract_dimensions_gearbox()
    extract_radial()
    extract_misc()
    extract_phl_coupling()
    extract_shaft_options()
    extract_working_cycles()
    extract_vp_tables()
    extract_vp_dims()
    build_designation()
    extract_images()
