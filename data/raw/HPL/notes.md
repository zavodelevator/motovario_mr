# HPL extraction notes

Source: sources/catalogs/HPL_planetary.pdf (216 pp). Script: tools/extract_HPL.py (run from repo root; about 10 min, pdfplumber). Printed page = PDF page - 2. src_page is the 1-based PDF page. Decimal commas converted to dots; "/" and "-" cells become "".

## Page map (PDF pages)
- 37-55 selection/ordering, designation (39-42), flange availability (46-54)
- 56-96 service factor, thermal, lubrication, loads, weights, motors (80-83), dimensions
- 97-133 7.1 HL geared motors ratings (by kW)
- 134-167 IHL reducers ratings (side-by-side tables, by n1)
- 188-216 VP (HPL + VSF worm) geared motors: designation 188-191, ratings 207-213, dimensions
- designation.json: transcribed visually from raster flow charts (pp. 39-42, 188-191).

## Row counts
ratings 3359 (HL 1478, IHL 1642, VP 239); motors 69; motors_dimensions 46; service_factor 30; thermal 72; weights 595; lubrication 141; motor_interface 187; radial_load_axial 16, _fh2 119, _tipping_moment 3, _input 2; dimensions_gearbox 90, ihl_input_shaft 31, chl_motor_envelope 416, phl_coupling 129, shrink_disk_shaft/splined_solid/splined_hollow/wheel_flange/axial_fixing_washer/torque_arm 9 each, vp 7, vp_worm_input 27, vpl_torque_limiter 4; extra_* see directory; images 88 (index.csv).

## ratings.csv extra columns (beyond schema)
type (printed reducer code e.g. HL3 010), poles, fr2_ss_n (FrSS), t2max_nm (M2max, IHL), mn2_nm, mn2_highlight (box_dark = dark-outlined/grey box, box_magenta = magenta box; "Mn2 independent of Pn1" per catalogue legend), i_worm, i_planetary (VP). fr2_n = FrCS convention. Size names: "HPL 010".."HPL 380", "VP P613".."VP P1183". variant: geared motor / reducer (IHL input shaft) / VP geared motor.

## Gaps
- n1_rpm not printed for HL and VP rows (empty); IHL n1 from table header.
- motors.csv: rpm, voltage, efficiency, torque, current, mass are not printed in the catalogue (empty); only frame/poles/power.
- Lubricant temperature colour map not captured; application-class table (extra_service_factor_application_class) is best effort.
- Right-angle codes in designation chart belong to another catalogue.

## Quality gates
- All 16 sizes present in ratings.
- Gate efficiency (t2*n2/9550/p1 in 0.55-1.0): 141 rows outside: 136 IHL rows where Pn1 is capped (incl. highlighted Mn2 rows) and 5 VP worm low-efficiency rows. Flagged, kept as printed.
- Gate n2 ~ n1/i within 3% (IHL only): 196 rows exceed, all from 1-decimal rounding of printed low n2 (<= ~1.5 rpm).
- Duplicate keys (series,size,n1,i,variant): HL rows lack n1, so 31 pairs share (size,i,kW,frame) but differ in printed n2/M2 (different motor/reducer combos in the catalogue); one pair (HPL 380, i 639, 4.00 kW 112M, p116) differs only in M2 (14907 vs 14410) as printed. Not removed.
- Anomalies: p69 IHL3 380 flange row has a spurious extra "380" (dropped); motor 180L AC value "34" printed as is.

## Spot-checks (rows vs rendered/text pages)
Rendered image checks: p104 HPL 080 i905 1.10kW n2 1.6 M2 5882 fs1.6 FrCS 72650 OK; p104 HPL 130 i899 M2 5847 FrCS 80000 OK; p153 IHL2 130 i38.8 Pn1 25.86 n2 23.2 Mn2 10000 FrCS 52400 OK; p153 IHL2 080 highlighted rows (5520, 6510, 6880) flagged OK.
Text-page checks (values located on the stated page): p106 HPL130 i899 7973 OK; p101 HPL050 i425 1929 OK; p102 HPL220 i2240 9843 OK; p129 HPL380 i204 22325/98000 OK; p112 HPL080 i291 5244 OK; p137 HPL030 i73.3 1920 OK; p158 HPL180 i410 21100 OK; p149 HPL030 i831 2580 OK; p134 HPL030 i9.30 188.2/740 OK; p147 HPL080 i122 8830 OK.
