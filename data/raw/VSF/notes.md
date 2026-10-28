# VSF (Motovario VSF / NMRV-type worm gearmotors, IEC) - extraction notes

Source: `sources/catalogs/VSF_worm_NMRV.pdf` (328 pp). Printed page = PDF page - 2. All `src_page` values are 1-based PDF pages.
Re-run: `python3 tools/extract_VSF.py [ratings|tables|images]` (about 5 min in total; pdfplumber is slow on tables).

## Families inside the catalogue (kept apart by `family`, `config`, `variant`)
- NMRV 025-150 / NMRV-P 063-110 worm geared motors (IEC motor flange) and NRV / NRV-P worm reducers (input shaft).
- SW 030-105 geared motors and ISW 030-105 reducers (SW = same worm range with different housing/feet/flange executions PA/PB/PV...).
- Pre-stage helical modules: HA31 (NMRV040/050, SW040-090), HW030/HW040 (NMRV-P063-110), IHW040 (NMRV-P090/110).
- Combined (two worm stages) units, e.g. NMRV025/030, NMRV-P063/150, NRV030/040, SW030/040, ISW050/105.
- `ratings.csv.variant`: `gearmotor` (tables 5.1 / 6.1, rated per motor kW) or `reducer` (5.2-5.17 / 6.2-6.13, rated per input speed).
  `family` in {NMRV, NMRV-P, NRV, NRV-P, SW, ISW, HA31+NMRV, HA31+SW, HW+NMRV-P, IHW+NMRV-P}; `config` in {single, combined, prestage}.
  `size` = printed designation (e.g. `NMRV040`, `NMRV-P063/150` = NMRV-P063 + NMRV150, `HA31+NMRV040`, `HW030+NMRV-P063`).

## Page map (PDF pages)
| section | pdf pages |
|---|---|
| index | 3-6 |
| symbols/formulas, selection, service factor (nomogram image), installation | 7-11 |
| design features | 12 |
| designation flow diagrams (images) | 13-17 |
| versions / modularity (images) | 18-23 |
| mounting positions, terminal box | 24-27 |
| efficiency / irreversibility, mesh data (eta per size and ratio) | 28-29 |
| backlash, direction of rotation, critical applications | 30-32 |
| motor flange availability NMRV(-P) / hybrid / HA31 / HW / SW / SW hybrid / HA31+SW | 33-39 |
| ratios of combined units | 40-43 |
| output shaft bearings, overhung load | 44-46 |
| lubrication (oils, quantity) | 47-49 |
| moments of inertia | 50 |
| dimensions reducers/geared motors | 51-65 |
| electric motors: dimensions, efficiency classes, nominal power | 66-69 |
| weights | 70 |
| end shaft key, low speed shafts, output flange, torque arm, cover, torque limiter | 71-81 |
| NMRV/NMRV-P geared motor selection tables (50 Hz) | 82-162 |
| NRV/NRV-P reducers and combined, 2800/1750/1400/1140/900/500 rpm, IHW prestage | 163-230 |
| SW geared motor selection tables | 231-280 |
| ISW reducers and combined | 281-323 |
| sales conditions | 323-328 |

## Files and row counts
| file | rows | source / method |
|---|---|---|
| ratings.csv | 8543 (5315 gearmotor + 3228 reducer) | pdftotext -layout + regex; `(1)` superscript flags via pdfplumber |
| designation.json | 5 designation patterns | manual transcription of the flow-diagram images (pp13-17) |
| dimensions_housing.csv | 79 | pdfplumber find_tables, pp52,55,56,59,60,61 |
| dimensions_shaft_bore.csv | 74 | same pages (hollow-shaft bore D H8 / key b,t,T per size) |
| dimensions_motor_input_flange.csv | 46 | B5 / B14 Pm,Dm,bm,tm tables (pp52,55,60,61) |
| dimensions_combined.csv | 45 | pp62-65 (IHW, combined units) |
| weights.csv | 98 | p70 (reducer without motor, without oil) |
| lubrication.csv | 90 | p49 (oil litres by position; oil type from p47/49) |
| motor_interface.csv | 89 | pp33,37 (IEC frame, B5/B14, bore D, N/M/P) |
| extra_motor_flange_ratio_matrix.csv | 1068 | same tables: feasibility per ratio (`status`, raw `cell`) |
| service_factor.csv | 132 | p10 nomogram, DIGITISED from the image (see below) |
| motors.csv | 88 | p69 nominal power by frame x poles x series (TS/TH/TP) |
| motors_dimensions.csv | 46 | pp66-67 motor dimensions + B5/B14 flange |
| radial_load_params.csv | 35 | pp45-46 (a, b, Fr1max/Fr2max per size) |
| extra_mesh_efficiency.csv | 120 | p29 (Z1, lead angle, Mx, dynamic eta at 1400, static eta) |
| extra_backlash.csv, extra_output_bearings.csv, extra_inertia.csv, extra_low_speed_shafts.csv, extra_torque_arm.csv, extra_output_shaft_cover.csv | 16/11/18/11/11/10 | pp30,44,50,72,76,77 |
| images/ + images/index.csv | 62 PNGs | `pdfimages -png` (all figures are embedded rasters) |
| _ratings_parse_log.json | - | page lists used for parsing + parse issues (none) |

## ratings.csv - conventions and deviations from the schema
- Gearmotor tables print per row: n2, M2, fs, i, reducer, motor (frame + poles), Fr2 under a heading "x kW". `p1_kw` = that heading (motor rated power); `t2_nm` = printed M2 (at the printed fs, integer-rounded by the catalogue); `fr2_n` printed; `motor_frames` = leading numbers of the printed motor size (`71C/80A` -> `71;80`); full printed string in `motor_size`; `poles` printed.
- **`n1_rpm` is not printed in the gearmotor tables.** It is set to the nominal speed of the pole count (2 -> 2800, 4 -> 1400, 6 -> 900), the same speeds the reducer tables use. The speed actually implied by the row is `n1_implied_rpm = n2 * i` (real motors run below nominal, e.g. 0.09 kW 4-pole ~1250). Range of implied n1 for rows with n2 >= 10 rpm: 2-pole 2640-2940, 4-pole 1240-1480, 6-pole 773-1000. Gate 3 (3 %) therefore cannot be applied to gearmotor rows; 2548 of 5315 deviate more than 3 % from the nominal pole speed (slip + printed rounding).
- Reducer tables print Mn2, i, Pn1, n2, Fr1, Fr2 per input speed (2800/1750/1400/1140/900/500 rpm; `n1_rpm` from the section title). `p1_kw` = Pn1, `t2_nm` = Mn2, `fs` empty, `fr1_n` (extra column) = input shaft radial load. IHW prestage tables exist only for 1750/1400/1140/900.
- Extra columns: `family, config, motor_size, poles, n1_implied_rpm, fr1_n, brake_motor_only, section`. `brake_motor_only=1` marks motor sizes printed with footnote (1) "Available only with brake motor (TBS)".
- `stages` is empty (the catalogue does not give a stage count; `config=combined` means two worm stages, `prestage` means helical + worm).
- Numbers: catalogue decimal comma -> dot; values kept as printed (`30.00`, `0.09`).
- **Key uniqueness (gate 4):** (series,size,n1_rpm,i,variant) is NOT unique for gearmotor rows (same size/ratio appears for several motor powers: 1143 key groups). It is unique when `p1_kw` and `motor_size` are added (0 duplicates, 0 identical rows). Reducer rows are unique on the schema key.
- p1_kw printed as `0.00` (rounding) in 6 reducer rows (NRV/ISW 030/040 and 030/050 at i = 4000/5000, pp197,207,217,305,312,319); kept as printed. HA31+SW040/SW050 have no selection-table rows in the catalogue (only HA31+SW063/075/090 appear).

## Quality gates
1. Sizes: all 84 designations present (NMRV025-150, NMRV-P063-110, NRV/NRV-P, SW030-105, ISW030-105, all combined pairs in the weight tables, HA31, HW030/040, IHW040). NMRV025 appears only as geared motor (there is no NRV025). Min rows per (variant,size): 1 (combined geared motor NMRV025/030, NMRV025/040, only a few ratios exist).
2. Efficiency, implied eta = t2 * n2 / (9550 * p1): 8537 rows (p1 > 0). Range gearmotor 0.264-0.948 (mean 0.68), reducer 0.083-0.92. Rows outside 0.3-0.95: 247, **all rounding artefacts** (Pn1 printed to 0.01 kW and n2 to 0.1 rpm: 235 reducer rows with Pn1 <= 0.14 kW and n2 <= 0.9 rpm at i >= 2400, 12 gearmotor rows with p1 = 0.09 kW, i = 2400, n2 = 0.5). Restricting to rounding-robust rows (p1 >= 0.25 kW and n2 >= 5 rpm: 4308 rows) none is outside 0.3-0.95. Cross-check with the mesh table (p29): for 152 single-stage reducer rows at 1400 rpm the implied eta differs from the printed dynamic eta by -0.011..+0.024. Rows outside the schema's 0.55-1.0 window: 2571 (107 among robust rows) - normal for worm stages at high ratio / combined units (eta product), no page error found.
3. n2 vs n1/i (reducers): 632 of 3228 differ by more than 3 %; 570 of them have n2 < 5 rpm (rounding of the printed n2); 62 rows with n2 >= 5 rpm are printed values that are truncated/rounded in the catalogue (e.g. 1140/100 = 11.4 printed as 11.0, p193-196; 500/40 = 12.5 printed 13, p213). Not corrected. Gearmotor rows: see n1 note above.
4. Duplicates: see key uniqueness note.

## Spot checks against rendered page images (12 random ratings rows, seed 20261028; all columns except the "x kW" heading compared)
pdf page / row -> result
- p273 SW105 i=30 n2=47 M2=246 fs=2.5 motor 90L/90LA 4p Fr2=6181 -> match
- p261 SW075 i=20 n2=47 M2=90 fs=3.0 80B 6p Fr2=4474 -> match
- p266 HA31+SW063 i=29.44 n2=31 M2=178 fs=0.8 80C 6p Fr2=4281 -> match
- p90 HW030+NMRV-P075 i=136.36 n2=6 M2=121 fs=3.5 63B 6p Fr2=7380 -> match
- p265 SW050 i=15 n2=93 M2=64 fs=1.3 80B 4p Fr2=2274 -> match
- p123 HW030+NMRV-P075 i=272.73 n2=5 M2=373 fs=1.0 71B 4p Fr2=7380 -> match
- p89 NMRV050 i=100 n2=13 M2=43 fs=1.3 63A 4p Fr2=4280 -> match
- p281 ISW030 i=20 Mn2=12 Pn1=0.22 n2=140 Fr1=146 Fr2=752 -> match
- p286 ISW050/090 i=1200 Mn2=700 Pn1=0.34 n2=2.3 Fr1=490 Fr2=8180 -> match
- p182 NRV-P063/130 i=500 Mn2=1550 Pn1=1.05 n2=3.5 Fr1=579 Fr2=13500 -> match
- p198 NRV040/050 i=1800 Mn2=145 Pn1=0.03 n2=0.6 Fr1=350 Fr2=4840 -> match
- p163 NRV050 i=30 Mn2=64 Pn1=0.81 n2=93 Fr1=490 Fr2=2274 -> match
Also checked visually: table headers on p273,261,266,90,265,123,89; page 33 motor-flange table; p49 lubrication table; p70 weight tables; p69 motor power table; p10 nomogram.

## Other tables - parsing remarks
- Bold table headers have every glyph doubled in the PDF text layer (`GG11` = `G1`); undone by `dd()` in the script.
- dimensions_housing.csv: one row per (size, variant); columns are the catalogue symbols (A,A1,B,D1 j6,G,G1,G3,H,H1,I,K,KE,L,M,N,N1,O,P,Q,R,S,S1,V,W,b1,t1,f1 and the SW/ISW foot/flange symbols C,EA,EB,EC,F,H2,K0,K1,R1,AS..SS, G2,G4,G5,G6,I2). Rows for SW/ISW carry the execution group in `variant`, e.g. `SW[...PA/...PB/...PV]` (symbols A,C,EA.. valid for PA/PB/PV), `SW[...PAS/...PBS/...PVS]` (AS,CS..). First SW table (G,G1,... printed with group `...T/...PA..PVS`) applies to all executions. `/` in the catalogue (not available) = empty. `K` = `90 - 95` and `A1 = 164 - 170`, `V = 82 - 85` are ranges kept as text. `G` of NMRV110 is two values (`185.5 (PAM 132)` / `168 (PAM 080/112)`) - see rendered page 52 image; the CSV cell keeps the pdfplumber text.
- **NMRV 025 dimensions exist only as a drawing (p51)**: no table, not in dimensions_housing.csv (image saved). Dimensions of SW/ISW drawings pp53-54,57-58 are partly in the drawing only.
- weights.csv: `size` follows the ratings spelling for singles/prestage (NMRV-P063 etc.); for combined units `size` is the printed pair (`063-150`) and `variant` names the family. Mass is without motor and without oil. `NMRV150 = 7 kg` is printed so on p70 (NRV150 = 77 kg; probably a typo for 77), kept as printed. `motor_frame` = motor flange size for HA31 / HW rows.
- service_factor.csv: the catalogue gives f.s. only as a nomogram (p10). Curves A (uniform), B (moderate shocks), C (heavy shocks) were digitised at starts/hour = 5,10,20,...,100 by pixel measurement; scale offsets for hours/day 2/8/16/24 read from the left-hand scales (bottom-row values 0.7/0.9/1.1/1.4, 0.1 per row). Accuracy about +-0.02-0.03; values at 5 starts/h come out as exact 0.8/1.0/1.2 (2 h). Treat as approximate; if exact values are needed re-read from the image `images/VSF_general_diagram_p10_1.png`.
- motors.csv: the catalogue prints only nominal power per frame x poles x series (TS = IE1, TH = IE2, TP = IE3 per p68). It does NOT print rpm, voltage, efficiency %, torque, current or mass - those columns are empty. Rows are only for combinations printed (dashes dropped). 112MR/112MS appear in two table blocks (identical, de-duplicated). 3.2.2 availability table (power ranges by efficiency class) not extracted. `motor_type` = series code TS/TH/TP; brake versions (TBS/TBH/TBP) are mentioned only in p68.
- motors_dimensions.csv: `variant` = motor_body (063-160S, p66), motor_body_160-280 (p67), flange_B5, flange_B14. `L_brake/LB_brake/LC_brake` = the `*(...)` values printed under L/LB/LC for 80B4, 90S4, 90L4, 90S6, 112M4/6 (TP motors, footnote). 112M row L/LB/LC `*(408/348/472)` assigned to size 112. `Pg` = two cable-gland entries joined by a space.
- motor_interface.csv: `size` as in ratings (NMRV025/030/040/050/130/150, NMRV-P063-110, SW030-105); `bore_mm` = D. Matrix `extra_motor_flange_ratio_matrix.csv`: `status` from legend (`•` feasible, `•*` feasible with low-profile key, `**` not feasible, `+` not to be used out of warranty). One cell in NMRV025/56B14 at i=5 prints `9` (not a symbol; stored as `raw:9`). Merged cells (one marker row for the B5/B14 pair) were expanded to both flanges.
- lubrication.csv: merged cells (025-110, SW) = same oil quantity for all positions; oil type TELIUM VSF (ISO VG320) lube-for-life per p49 (alternatives in p47-48 not tabulated).

## Not extracted (gaps)
- Hybrid motor flange tables 2.9.2 / 2.9.6 (bore per ratio, pp34,38) and pre-stage motor/flange matrices 2.9.3, 2.9.4, 2.9.7 (HA31/HW, pp35,36,39).
- Ratio tables of combined units i = i1 x i2 (pp40-43) (the ratings tables already list every available i).
- Critical application tables (p32), output flange execution table (p73), end shaft key table (p71), torque arm positions (pp74-75), torque limiter (pp78-81), lubricant lists (pp47-48), 3.2.2 motor availability table (p68).
- Drawings contain dimension values not available as tables (NMRV025 p51, SW/ISW drawings); they are cut out as images only.
- Output torque limits (M2max = 2 x Mn2), thermal power: not tabulated in the catalogue.

## Images (images/index.csv)
62 embedded rasters via `pdfimages -png` (>= 200 dpi source): designation diagrams (pp13-17), versions/modularity renders (pp18-23, one image per page containing several units), mounting/terminal diagrams (pp24-27,31), flange sketches, dimension drawings (pp51-65,66-67), accessories drawings (pp71-79), and the service factor nomogram (p10). Pages 51-65 hold one figure per drawing; multi-view pages are one file per embedded image, not further split. Logo images (p1) and soft masks excluded.
