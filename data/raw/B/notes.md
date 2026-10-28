# Series B (Motovario B / BA helical-bevel, IEC) - extraction notes

Source: `sources/catalogs/B_helical-bevel.pdf` (188 pages). `src_page` = 1-based PDF page; printed page = PDF page - 2.
Reproduce with `python3 tools/extract_B.py` (about 1 min; `--no-images` skips the image crops).
Tools: pdfplumber `find_tables()` for the vector tables (dimensions, weights, flange availability, etc.), `pdftotext -layout` + regex for the
ratings tables, `pdftoppm` for image crops and verification renders.

Size naming: canonical `BA42 BA52 BA53 BA72 BA73` (aluminium) and `B063 B083 B103 B123 B143 B153 B163` (cast iron). Printed prefixes
CB / IB / PB / CBA / IBA and bare `A42` / `063` are mapped to these; the printed code is kept in `ratings.csv` column `printed_size`
and in the `variant` column of dimension files. Note p27/p32/p35 print "A40/A50/A70" and "060...160" series-group names; those are kept as printed in `extra_*` files.

## Page map (PDF pages)
| section | PDF pages |
|---|---|
| Index | 3-5 |
| 1.3 symbols/formulas | 11-12 |
| 1.4 product selection | 13 |
| 1.5 service factor (chart, raster) | 14 |
| 1.6 installation | 15 |
| 2.1 design features / efficiency (B..3st 0.9, BA.2 0.95, BA.3 0.9) | 16 |
| 2.2 designation chart (image) / versions / modularity | 17 / 18-21 / 22-23 |
| 2.3 mounting positions, terminal box | 24 |
| 2.4 thermal power | 25 |
| 2.5 direction of rotation | 26 |
| 2.6 critical applications | 27 |
| 2.7 motor flange availability (BA/CBA p28, B/CB/PB p29-31) | 28-31 |
| 2.8 output shaft bearings | 32 |
| 2.9 radial load (input p33, output p34) | 33-34 |
| 2.10 lubrication (standard p35, special p36, quantity p37) | 35-37 |
| 2.11 moments of inertia | 38 |
| 3.1 dimensions BA.2 / BA.3 / CBA.2 / CBA.3 / IBA.2 / IBA.3 | 39-44 |
| 3.1 dimensions B / CB / IB (drawing + tables) | 45-46 / 47-48 / 49-50 |
| 3.2 weights | 51 |
| 3.3 shaft end keyways | 52 |
| 3.4 electric motors (dimensions 53-54, efficiency text 55, nominal power 56) | 53-56 |
| 4.1 low speed shafts | 57 |
| 4.2 output flange (BA p58, B p59) | 58-59 |
| 4.3 torque arm (BA p60, B p61-62) | 60-62 |
| 4.4 output shaft cover | 63 |
| 4.5 backstop device | 64 |
| 4.6 shrink disc | 65 |
| 4.7 reinforced seals | 66 |
| 4.8 assembling kit | 67 |
| 4.9 machine axis | 68 |
| 5.1 B/BA geared motors 50 Hz (selection tables) | 69-135 |
| 5.2-5.7 IB/IBA gear reducers at 1750 / 1400 / 1140 / 900 / 700 / 500 rpm | 136-143 / 144-151 / 152-159 / 160-167 / 168-175 / 176-183 |
| 6 sales conditions | 184-188 |

## Files and row counts
| file | rows | source / remark |
|---|---|---|
| ratings.csv | 4315 | 2725 `gearmotor` (p69-135) + 1590 `reducer` (p136-183) |
| designation.json | - | field order read from the chart image p17 (text layer empty) + p18-24 |
| motor_interface.csv | 1001 | one row per (size, ratio or ratio range, IEC frame): flange string verbatim (B5, B14, B5-B14, B5-B11, B10); `bore_mm` = Dm of the B5 flange of that frame (p39/46 tables, not printed in the availability tables); `version` = CBA / BA / B/CB/PB |
| dimensions_BA_housing.csv | 27 | BA / CBA / IBA .2 and .3 (p39-44), one row per size x hollow-bore option (`D H7`) |
| dimensions_B_housing.csv | 12 | B / CB / IB (tables on p46 are identical on p48 and p50), one row per size x `D1 H7` option |
| dimensions_input_shaft.csv | 12 | IBA (G3,D1,B1,b1,t1,f; p43-44) and IB (G3,B2,D2,b2,t2,f2; p50) |
| dimensions_compact_motor_CB.csv | 120 | X/Y/Z of CBA (p41-42) and CB (p48) for motor types T and TB per IEC frame; `X_star` = value printed with asterisk (TP80B4, SH80B4 ... motors, footnote p41) |
| dimensions_motor_flange_G2.csv | 107 | G2 per IEC frame and size, with Pm x Dm for B5 and B14 |
| dimensions_motor_flange.csv | 18 | Pm, Dm, bm, tm for B5 / B14 |
| dimensions_low_speed_shaft / output_flange_BA / output_flange_B / torque_arm / output_shaft_cover / shrink_disc / assembling_kit / machine_axis .csv | 10 / 16 / 16 / 16 / 7 / 12 / 18 / 14 | section 4 |
| weights.csv | 178 | variants: `reducer B-PB (... without motor)` by motor-flange group, `reducer IB`, `gearmotor CB TH/TBH/TP/TBP` by motor frame |
| lubrication.csv | 102 | oil quantity (l) per size and mounting position; oil type from p35 |
| thermal.csv | 7 | Pth at n1=1500 (B063-B163 only; "not necessary for BA") |
| radial_load_input.csv / radial_load_output.csv | 12 / 12 | a, b and Fr1 max / Fr2 max (D-S-P and C) per size |
| service_factor.csv | 132 | chart reading, see below |
| motors.csv | 69 | section 3.4: nominal power by frame/poles/series TS-TH-TP (p56) |
| motors_dimensions.csv | 46 | motor body dimensions (p53-54) and B5/B14 flange dimensions; `*_star` columns = values printed with asterisk |
| extra_*.csv | torque-arm positions 144, output-flange availability 20, thermal factors 44, bearings 68, inertia 12, critical applications 40, backstop 35, seals 7, keyways 19, lubricants 24+15 | |
| images/ + images/index.csv | 66 | PNG at 200 dpi cropped from page renders |

Extra columns in ratings.csv: `fr2_c_n` (Fr2 hollow shaft C, N), `fr1_n` (input radial load, reducers only), `motor_size` (printed motor, e.g. 71C/80A), `poles`,
`n1_implied_rpm` (= n2 x i, gearmotor only), `printed_size`. `fr2_n` = Fr2 for D-S-P (solid shaft); BA42/52/53 print "-" -> empty.
Gearmotor rows: `p1_kw` = motor power block header, `fs` as printed; reducer rows: `t2_nm` = Mn2, `p1_kw` = Pn1, `fs` empty.
`motor_frames` = digits of the printed motor size (71C/80A -> 71;80).

## Decisions / conventions
- **n1 for gearmotors is not printed** (only motor poles). `n1_rpm` = 2800 / 1400 / 900 for 2 / 4 / 6 poles (nominal 50 Hz convention, mine); the real catalogue speed is `n1_implied_rpm` = n2 x i (range 2784-2962 / 1324-1486 / 841-982). Therefore gate 3 (|n2 - n1/i| < 3 %) fails for 1956 gearmotor rows purely because of this nominal-speed convention (motor slip, up to +9 % for 6 poles); all 1590 reducer rows (n1 printed) pass. Use `n1_implied_rpm` for gearmotor speed checks.
- Duplicate-key gate: (size, n1, i, variant) is not unique in gearmotor rows (675 keys repeat) because the same ratio appears for several motor powers; the key (size, n1, i, variant, p1_kw, motor_size) has 0 duplicates. Reducer rows are unique on the spec key.
- Stages: BA42/52/72 = 2, BA53/73 = 3, B063-B163 = 3 (from the efficiency paragraph p16).
- Output shaft versions S and D are both "solid shaft" and L/M both "shrink disc" in the catalogue; the difference is not explained in text (see open questions).

## Quality gates
1. Every catalogue size appears: BA42 BA52 BA53 BA72 BA73 B063 B083 B103 B123 B143 B153 B163 in both variants. Rows per size (gearmotor / reducer): B063 262/156, B083 328/168, B103 373/180, B123 340/186, B143 313/180, B153 277/180, B163 234/180, BA42 130/78, BA52 145/78, BA53 61/54, BA72 128/72, BA73 134/78. Each reducer speed page set has exactly 265 rows.
2. Efficiency gate (eta = t2*n2/(9550*p1)): no row below 0.55; 12 rows slightly above 1.0 (1.000-1.010), all rounding artefacts of the printed values (checked against the page text/image, values are as printed): gearmotor 0.37 kW rows p75-76 (BA42 i=12.95, 16.47, 31.27; BA52 i=14.63, 17.11, 20.46, 25.03, 35.10; BA72 i=40.87, 45.64, 54.94) and reducer BA42 i=78.17 at 500 rpm p168 (Pn1 0.11 printed with 2 decimals).
3. See "n1 for gearmotors" above.
4. See duplicate-key remark above.
5. Script: `tools/extract_B.py`.

## Spot checks (ratings rows vs rendered page image, 130 dpi crops of the printed row; all 12 identical)
1. p101 B083 3.00 kW i=51.19: n2 56.7, M2 439, fs 1.4, Fr2 18000/5358 - OK
2. p84 B083 0.75 kW i=100.57: 14.3 / 450 / 1.9 / 18000 / 8763 - OK
3. p108 B123 4.00 kW i=49.80: 29.1 / 1181 / 2.7 / 30000 / 10965 - OK
4. p134 B163 45.00 kW i=15.52: 95.7 / 4043 / 2.5 / 61331 / 61331 - OK
5. p73 BA73 0.25 kW i=97.29 (63D/71A, 4p): 13.9 / 154 / 2.9 / 10000 / 5500 - OK
6. p76 B063 0.37 kW i=50.81 (71C/80A, 6p): 18.5 / 182 / 3.4 / 12000 / 5367 - OK
7. p122 B153 11.00 kW i=54.64 (160L, 6p): 17.8 / 5379 / 1.6 / 65000 / 65000 - OK
8. p78 BA52 0.55 kW i=64.87 (71B, 2p): 43.6 / 110 / 1.3 / "-" / 3147 - OK
9. p158 reducer B153 1140 rpm i=42.30: Mn2 8200, Pn1 25.46, n2 26.9, Fr1 8590, Fr2 54522/54522 - OK
10. p171 reducer B103 700 rpm i=68.58: 1806 / 2.11 / 10.2 / 2472 / 22000 / 10980 - OK
11. p139 reducer B103 1750 rpm i=14.99: 1128 / 15.33 / 116.8 / 1526 / 16275 / 4650 - OK
12. p166 reducer B163 900 rpm i=21.94: 10920 / 51.59 / 41.0 / 8206 / 71371 / 65000 - OK
Also checked visually: dimension table p39 (BA42 has one bore D=20; BA52 has 25 and 28; BA72 has 35 and 30 - the text layer misplaces the vertically centred size labels), p46 (B153 bores 90 and 80), p51 weights, p60/61 torque-arm marks, version tile images p18-21.

## Known gaps / ambiguities
- `service_factor.csv`: the catalogue gives the service factor only as a raster chart (p14), no table. Values are measured from the three straight load-class lines (A, B, C) with the four hours/day scales (2, 8, 16, 24 h) and rounded to 0.05; starts/h at the x position of the axis labels 5, 10 ... 100 (40 from the straight-line fit because the letter box hides the line). Treat as approximate (+/-0.05). The chart labels give exactly (starts <= 5): A 0.8/1.0/1.2/1.5, B 1.0/1.2/1.4/1.7, C 1.2/1.4/1.6/1.9 for 2/8/16/24 h (read from the printed scales).
- Motors (section 3.4): the catalogue prints only dimensions (p53-54), efficiency-class text (TS=IE1, TH=IE2, TP=IE3, p55) and nominal power per frame/pole (p56). rpm, voltage, efficiency %, torque, current and mass are NOT printed -> empty columns in `motors.csv`. p55 also mentions SH/HSH/TBS/TBH/TBP motor series that do not appear in the p56 table.
- p42: CBA73 frame 090L X is printed `262*` / `295` (asterisk on the wrong number; p41 prints `262` / `*295`); stored as X=262, X_star=295.
- `lubrication.csv`: for BA sizes (p37, tables "B" and "CB") one value is printed in a merged cell spanning all mounting positions; it is repeated for B3,B8,B6,B7,V5,V6 (note column). B6/B7 are printed in one row only for the BA tables; the B table (p37 third table) has separate rows.
- `extra_torque_arm_positions.csv`: empty cell in the printed table is interpreted as "available" (legend only explains "/" = not available and "*" = not available with shrink disc).
- `dimensions_output_flange_B.csv`: C and G1 are printed once per size (merged cell) and repeated on that size's FA/FB/FC rows.
- Designation chart p17 is an image: segment order (type, size, casing, shaft, flange, ratio, input dims, output dims, mounting position, accessories) read from it; example "B 083 F C FA 91,3 160x14 250x28 B3". Meaning of V5/V6 orientations is as drawn on p24 (not described in text).
- Dimension drawings (p45, p47, p49) are single images; no separate per-size tables beyond p46/48/50.
- Not exported as images: product photos of other series on p9-10 (only the IEC motor photo p10 and the B cover photo p1 are kept), logos, nameplate (p16), p188.
