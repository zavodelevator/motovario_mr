# H series (Motovario H helical, IEC) - extraction notes

Source: `sources/catalogs/H_helical.pdf` (292 pp). PDF page = printed page + 2. Script: `tools/extract_H.py` (run `python3 tools/extract_H.py`, ~1 min; steps: ratings dims iec availability motor_interface weights lubrication small motors service_factor extras designation images).
Tools: `pdftotext -bbox` word boxes (x/y clustering), PIL for the chart digitisation, `pdfimages` for figures. pdfplumber was too slow on the dense tables.

## Page map (PDF pages)
General 6-15 (symbols 11-12, selection 13, service factor 14, installation 15); designation 17; versions 18-19; modularity 20-21; mounting positions 22-23; thermal 24; critical applications 25; motor flange availability 26-30; output bearings 31; radial load 32-33; lubrication 34-36; inertia 37; dimensions 38-65 (tables on text pages 38-41,43,45,...,65; drawings 42,44,...,64); weights 66-67; shaft end 68; electric motors 69-72; output flange 73; backstop 74-75; reinforced seals 76; performance tables: H/HA geared motors 77-204 (50 Hz, by motor kW), IH/IHA reducers 205-288 (1750/1400/1140/900/700/500 rpm); sales conditions 289.

## Files and row counts
ratings.csv 7812 (geared motor 5256 + reducer 2556); designation.json; dimensions_HA 65, _CHA 296, _IHA 75, _HR 229 (HR/CHR/IHR), _H 262 (H/CH/IH); weights 392; lubrication 211; motor_interface 299; motors 69; motors_dimensions 50; thermal 14; service_factor 132; images 42 files + images/index.csv.
extra_*: backstop_availability 88, critical_applications 39, inertia 22, input_g2 35, motor_flange_availability 1382, motor_flange_dims 16, output_flange_options 14, output_shaft_bearings 25, reinforced_seals 14, shaft_keys 19, thermal_correction_factors 44; radial_load_formula_params 120 (a, b, Fr max per size group, p.32-33).

## ratings.csv specifics
- Two table families in one file, `variant` = `gearmotor` (pp 77-204: rated per motor kW, columns n2, M2, fs, i, reducer, motor size, poles, Fr2) or `reducer` (pp 205-288, IH/IHA: Mn2, i, Pn1, n2, Fr1, Fr2, grouped by input speed section).
- Gearmotor rows: input speed n1 is NOT printed, only motor poles (2/4/6, 50 Hz). `n1_rpm` is therefore empty; `n1_implied_rpm` = round(n2*i) (derived, accuracy limited by n2 printed to 0.1 rpm; observed 2-pole 2782-2948, 4-pole 1310-1486, 6-pole 797-983). `p1_kw` = kW heading of the table. `t2_nm`=M2 (rated at printed fs), `fs`, `fr2_n`, `motor_frames` from motor size (e.g. `100LA/112MR` -> `100;112`).
- Reducer rows: `n1_rpm` from section title, `p1_kw`=Pn1, `t2_nm`=Mn2, `fs` empty, extra `fr1_n` (input radial load).
- Extra columns: fr1_n, motor_size (as printed), poles, n1_implied_rpm, brake_motor_only (1 = marked "(1) Available only with brake motor (TBS)", 506 rows).
- Sizes keep catalogue spelling: HA31..HA63, H032..H143 (the single-stage cast-iron series HR is printed as H041/H051/H061/H081/H101/H121 in these tables, whereas dimension/weight/availability pages call it HR041...). `stages` = last digit of the size.
- Dedup key (size,n1,i,variant) is not unique for gearmotors (same size/ratio appears under several kW); uniqueness holds on (size,i,p1_kw,poles,motor_size,fs): 0 duplicates. Reducer key (size,n1,i): 0 duplicates.
- Catalogue footnote: M2max/peak torque not given per row; rule in text: peak <= 2*Mn2.

## Quality gates
1. All index sizes present (67 size/variant groups, 30-302 rows each; HA31-63 x3 stages, H032-143, IH032-143, IHA32-63).
2. Implied efficiency eta = M2*n2/(9550*P): range 0.787-1.187; 74 rows outside 0.55-1.0, ALL are printed-rounding effects, not parsing errors: gearmotor rows with M2 printed as integer Nm <= 19 Nm (45 rows, eta 1.0001-1.07) and reducer rows with Pn1 printed to 2 decimals / low Mn2 (29 rows; worst IHA33 i=240.55 Pn1=0.02 -> 1.187, p.275; IHA33 i=347.29 -> 0.79, p.275, IHA43 347.29 -> 0.79 p.276). Checked against page images; not altered.
3. Reducers: n2 vs n1/i within 3 % for all 2556 rows (0 flagged). Gearmotors: implied n1 consistent with pole speeds (see above).
4. No duplicate keys (see above).
5. Script in tools/extract_H.py.

## Spot checks (rendered page crops vs CSV rows, all OK)
p141 H103 1.5kW i69.69 (13.3rpm,1019Nm,fs3.6,100L/100LA,6p,22000N); p106 H042 0.55kW i26.04 (52.6,96,2.7,71C/80A,4p,6600); p155 H082 2.2kW i48.13 (19.3,1054,1.6,112M/112MA,6p,18000); p86 HA53 0.18kW i88.02 (10.2,160,2.0,71A,6p,6000); p91 HA33 0.25kW i59.65 (46.9,46,1.6,63B,2p,1940); p183 H102 7.5kW i30.72 (94.7,700,3.4,132M/132SB,2p,21707); p95 HA31 0.37kW i3.18 (878.3,4,4.0,63C,2p,522); p149 H051 2.2kW i2.13 (437.6,47,1.3,112M/112MA,6p,2053); p283 IH063 500rpm i268.00 (914Nm,0.19kW,1.9rpm,2769,12000); p212 IH062 1750rpm i20.28 (799,7.52,86.3,1999,10787); p272 IH122 700rpm i24.47 (5313,16.33,28.6,2788,30000); p233 IHA41 1140rpm i10.83 (21,0.23,105.2,330,1072). Also visually verified: p14 service-factor chart, p72 motor power table, p36 lubrication table 1 (merged cells).

## Other files - how parsed / caveats
- service_factor.csv: the catalogue gives a CHART (p.14, raster), not a table. Values were DIGITISED by script from the pixel positions of the A/B/C lines at the tick marks 5,10,...,100 starts/h and read on the printed scale of each hours/day column (24/16/8/2); accuracy about +-0.02. Treat as approximate. Load class definitions (fa = Je/Jm: A <=0.3, B <=3, C <=10) are in text p.14.
- dimensions_*.csv: position-based generic parser. One row per size (and per shaft option / flange option / compact-motor length). `variant` = section + table number on the page (table1 = body/shaft dims, table2 = flange, table3 = input-shaft/extra); multi-line cells are joined with spaces (e.g. several shaft diameters of HA31 on page 38 stay in one row, `N` of HR rows may contain "130 125 (041M)"). Compact motor lengths X/Y/Z (T=standard, TB=brake) are rows with variant "compact-motor length X/Y/Z" (columns sym, frame, motor_type, X/Y/Z value; value with `*` = TP/SH/HSH footnote variants). Catalogue symbols kept verbatim; first-letter shaft tolerance appended to D (e.g. "25 j6").
- extra_input_g2.csv: IEC input table (Pm x Dm and G2 value per IEC frame) as printed, values left-to-right; mapping of columns to sizes is given in the `g2_column_header_text` (not split per size automatically).
- extra_motor_flange_availability.csv + motor_interface.csv: from pp 26-30; flange codes B5/B14 (HA, H), B10 (HA compact CH), B11 (compact motor on H). motor_interface.csv is the union over ratios per (size, IEC frame) with bore Dm from the B5 table (B14 uses B5 value when no B14 dim exists - NOTE: bore is by frame, same for B5/B14 in these tables); iec_frame has the catalogue 3-digit form (063...).
- weights.csv: p.66 H-PH reducers per IEC frame (mass without motor, incl. oil) and IH reducers; p.67 CH geared motors by motor type TH/TBH/TP/TBP and frame. size labels e.g. HA32, H032-033, HR041, CH..., IH...
- lubrication.csv: oil quantity (l, approx) per mounting-position group (B3-B5, B5R, B8, B6-B7, V5-V1, V6-V3). `oil_type`: text of the catalogue (ISO VG220 standard, VG150 low temp; H122-142 supplied without oil).
- thermal.csv: Pth at n1=1500 rpm (HA31 '/' = not given -> empty). Correction factors Fc/Fa/Fv in extra_thermal_correction_factors.csv.
- motors.csv: only what p.72 prints: rated kW per frame x type (TS/TH/TP) x poles. rpm, voltage, efficiency %, torque, current, mass are NOT in the catalogue -> empty; efficiency_class from the p.71 text (TS IE1, TH/SH/HSH IE2, TP IE3). Brake versions (TBS/TBH/TBP) are mentioned but no separate power table. motors_dimensions.csv: p.69-70 tables (body AC..GD, B5, B14 flange) incl. `*` rows (TP/SH/HSH variants).
- designation.json read from the raster flow chart (p.17); meaning of the B/V mounting codes is standard, catalogue only shows pictograms (images p.22-23).
- Not extracted as tables: sales conditions (p.289), company/profile pages, design-feature text (p.16), selection guidance text (p.13).

## Known gaps / open questions
- No n1 for gearmotor rows (only poles); no per-row max torque.
- No explicit radial_load_*.csv per size beyond a, b, Fr max parameters (per-row Fr1/Fr2 are in ratings.csv).
- Dimensions of HA31 (p.38) are one merged row; check against drawing if needed.
- Output dimensions field of the designation (example "250x40") is not explained in the catalogue.
