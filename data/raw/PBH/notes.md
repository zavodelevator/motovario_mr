# PBH extraction notes

Catalogue: `sources/catalogs/PBH_parallel-bevel.pdf` (Motovario PBH Series, parallel helical PH + bevel helical BH, IEC, REV.0 2018, 116 pages).
Reproduce with `python3 -I tools/extract_PBH.py` (from repo root). `src_page` = 1-based PDF page; printed page = PDF page - 2.
Catalogue uses decimal comma; all files use dot decimal.

## Page map (PDF pages)
| section | pages |
|---|---|
| cover, index | 1-3 |
| company / products & software (marketing only) | 6-11 |
| designation (flow diagram) | 13 |
| versions, gear trains | 14-15 |
| available motor mounting flanges (frame x gear train matrix) | 16 |
| range (Mn2 max, i min/max at 1400 rpm) | 17 |
| executions | 18; mounting positions 19-20 |
| product selection, service factor tables fsa/fsb/fsc, application classification | 21-24 |
| thermal power Pth, correction factors, Pta cooling | 25-27 |
| max input speed | 28 |
| lubrication (oils, ISO VG, oil quantities) | 29-30 |
| direction of rotation | 31 |
| radial / axial loads (input p32-33, output p34-40) | 32-40 |
| dimensions P1H..B4H | 41-47 |
| weights | 48 |
| shaft ends | 49-50 |
| hollow / splined shafts | 51-53 |
| motor input flanges PH / BH | 54-57 |
| devices: cooling fan, lube pump | 58-60 |
| accessories: output flange, reaction bolt, backstop, cover, kit, seals | 61-65 |
| installation, oil change, plug torque | 66-68 |
| symbols, formulas | 69-70 |
| performance tables PH: 1750/1400/1140/900/700/500 rpm | 71-94 (4 pages per speed: P1H, P2H, P3H, P4H) |
| performance tables BH: same speeds | 95-112 (3 pages per speed: B2H, B3H, B4H) |
| sales conditions, notes | 113-115 |

## Mapping of the selection tables to schema columns
The catalogue rates by nominal output torque and nominal input power (no fs column, no radial load column, no motor frames in the rows):
- `t2_nm` = Mn2 [Nm] (nominal torque), `p1_kw` = Pn1 [kW] (nominal input power), `i` = i, `n2_rpm` = n2, `n1_rpm` = speed in the section title (1750/1400/1140/900/700/500).
- `fs` = "" (the table is the nominal rating; selection formula is Mn2 >= M2 * fs, fs = fsa*fsb*fsc, see service_factor.csv). Implied fs of a table row is 1.
- `fr2_n` = "" : the text (p32) says radial loads are in the performance tables, but they are NOT printed there. Output radial limits are in radial_load_output_max.csv / radial_load_output_life.csv, input in radial_load_input.csv.
- `size` = `<train> <frame>` as printed in table headers, e.g. `P2H 180`, `B3H 355`. `stages` = digit of the train (P1H=1, B2H=2 ...; for B it is the number of gear stages incl. bevel stage as in the designation `2H..4H`).
- `variant` = `reducer` (the catalogue has only reducer tables, no gearmotor tables).
- `motor_frames` = IEC frames from the p16 matrix for that (train, size) (merged cells expanded; `100-112` -> 100;112, `250-280` -> 250;280). This is per train/size, not per ratio row.
- Sizes use the train+frame form everywhere train-specific. Tables common to PH-BH (shaft ends, hollow shafts, output flange, accessories) use `size` = frame number (`180`..`355`) and a `variant` starting with `PH-BH`; join on the last token of `size`.
- Extra info: tables are rated for input speed up to 1750 rpm; for higher n1 contact Motovario (p19).

## Files and row counts
ratings.csv 3420 (42 train-size x 6 speeds; P1H 9 rows, P2H/P3H/B2H/B3H 14, P4H/B4H 15 per speed);
dimensions_reducer.csv 42; weights.csv 42; lubrication.csv 252; thermal.csv 42; service_factor.csv 60;
radial_load_input.csv 42; radial_load_output_max.csv 12; radial_load_output_life.csv 90;
dimensions_shaft_input.csv 12; dimensions_shaft_output.csv 6; dimensions_hollow_shaft.csv 18; dimensions_splined_shaft.csv 6;
dimensions_input_flange.csv 117; motor_interface.csv 157; dimensions_cooling_fan.csv 24; dimensions_lube_pump.csv 42;
dimensions_output_flange.csv 6; dimensions_reaction_bolt.csv 6; dimensions_shaft_cover.csv 6; dimensions_assembly_kit.csv 6;
extra_*: thermal_pta_cooling 98, thermal_correction_factors 96, max_input_speed 42, range 12, service_factor_fsa_fsb 27, service_factor_fsc 3,
application_classification 80, oil_iso_viscosity 4, oil_recommended_brands 8, oil_change_interval 2.
designation.json; images/ 73 PNG + index.csv.

## Parsing notes and quirks
- Tools: `pdftotext -layout` per page for all text tables; `pdfplumber.extract_tables` for p16 matrix and p54-57 flange tables (size label printed once per merged cell); `pdfplumber` crop by column for p22-23; pdfplumber image boxes + `pdftoppm -r 200` crops for images.
- Ratings: each page has 3 header lines of two sizes side by side; each data line has 8 numbers (4 per size: Mn2, i, Pn1, n2). Any other row length would be flagged (none).
- dimensions_reducer.csv: wide, catalogue symbols verbatim. For P1H, `D1,B1` are the values for in <= 4 and `D1_in_gt4,B1_in_gt4` for in > 4 (empty for other trains). `H1,H2` only P4H, `F` only P1H-P4H, `G3` only B trains, `G1` only P trains in the first table (for B the table has G1 and G3). `-` -> empty (C3 of size 180 P1H/P2H/B2H/B3H). P4H `I` = 599.5 / 759.1 (comma decimals converted).
- dimensions_hollow_shaft.csv variants: `hollow_keyway_D3_H7/h6`, `hollow_shrink_disc_D3_H7/g7_D4_H7/f7`, `hollow_splined_DIN5480`; unused columns empty. `MT_12.9_Nm` = tightening torque of screws.
- dimensions_input_flange.csv: `dm` kept as printed (e.g. `42-48` = a range of motor shaft diameters sharing a flange, `65-75`). `GF` is for PH tables, `GF1` for BH tables (catalogue header differs). `OF`=thread, `OF_n`=number of holes, `W` angle.
- dimensions_cooling_fan.csv columns E1,G1,G2,L,K,N = catalogue E11/E13, G11/G13, G12/G14, L11/L13, K11/K13, N11/N13 (11 for P1H/P2H, 13 for B2H/B3H); only P1H, P2H, B2H, B3H have fan data.
- dimensions_lube_pump.csv: table groups P1H-B2H, P2H-B3H, P3H-B4H, P4H share DP, KP; `I` as printed (equals frame number for P1H/B2H).
- dimensions_output_flange.csv: header `NU G6` read as NU with G6 tolerance (`NU_fit`).
- weights.csv: reducer mass without lubricant (`reducer_dry_no_oil`), `motor_frame` empty (no gearmotor masses).
- lubrication.csv: `oil_l` per mounting position B3/B8/B6/B7/V5/V6 (p30, "~ [l]"). `oil_type` left empty (catalogue gives oil by n2 via ISO VG table -> extra_oil_iso_viscosity.csv, brands -> extra_oil_recommended_brands.csv).
- thermal.csv: Pth [kW] at B3, continuous, n1 <= 1500, 20 C, sea level, air >= 1 m/s. Correction factors (fta, ftb, ftc, ftn, fts, ftv, Fmp) in extra_thermal_correction_factors.csv: the small irregular tables on p26 were transcribed in the script (Fmp rows are asserted against the text layer; others checked visually against p26).
- service_factor.csv: the catalogue prints fsa (load class x h/day) and fsb (load class x starts/h) and fsc (motor type) separately and fs = fsa*fsb*fsc. `fs` here is the COMPUTED product fsa*fsb with fsc = 1.00 (electric motor); raw tables in extra_service_factor_fsa_fsb.csv / extra_service_factor_fsc.csv. Starts/h column values `<8`, `8-32`, `32-64`, `64-128` (printed `8 ... 32` etc.). Hours 2,4,8,16,24.
- extra_application_classification.csv: application -> load class (uniform/moderate/heavy), e.g. Screw conveyor = Heavy, Belt/Scraper/Bucket/Roller = Moderate. Application text kept as printed (one wrapped entry keeps the printed "loads loads" typo).
- radial_load_input.csv: a, b, Fr1 at n1 = 1400 rpm per train-size. radial_load_output_max.csv: a, b, Fr2 max per size (groups P1H-P2H-B2H and P3H-P4H-B3H-B4H). radial_load_output_life.csv: Fr2 at 100/75/50 % Mn and Fa at 100 % Mn vs n2*Lh cycles, per size (valid for all trains).
- motor_interface.csv: built from the input flange tables (PF/NF/MF per motor shaft dia `dm`). `iec_frame` is NOT printed in those tables: it is DERIVED from dm via standard IEC shaft diameters (28->100;112, 38->132, 42->160, 48->180, 55->200;225, 60->225;250, 65->250;280;315, 75->280, 80->315). Treat as candidates; the authoritative frame/train compatibility is `motor_frames` in ratings.csv (p16 matrix). `flange` text = `B5 PF.. NF.. MF..` (B5 is assumed as the flange type; the catalogue calls them "motor mounting flanges" for PAM bell-housing input). `bore_mm` = dm; ranges like `42-48` are expanded to one row per value.
- designation.json: the catalogue only has a flow diagram (p13) without a worked example. Segment order read from the diagram: PBH, B|P, stages (1H..4H), size, execution, input (I|P), input dimension (PFxdm or D1xB1), output version (CS HC HL CD HS SS SD), output dimension, ratio (diagram: 1,22 ... 762,36), mounting (B3 B6 B7 B8 V5 V6). Execution meanings are my reading of the p18 drawings (AZ/AU single input, DZ/DU double input, bevel LR/LL/SR/SL/DR/DL = output side and input geometry) - flagged as visual interpretation. Mounting position meanings are only drawn (p19-20), not described in text.

## Quality gates
1. Row counts: every train-size of the index (PH 180-355 x P1H-P4H, BH 180-355 x B2H-B4H = 42) appears in ratings.csv at all 6 speeds (252 combos).
2. Efficiency check t2*n2/(9550*p1): min 0.913, max 0.986 over all 3420 rows -> no row outside 0.55-1.0.
3. |n1/i - n2|/n2 <= 3 % for all rows (no flags).
4. No duplicate (series,size,n1,i,variant) keys.
5. Script: tools/extract_PBH.py.

## Spot checks (ratings rows vs rendered page image, 90 dpi render of the PDF page)
All 10 matched exactly (Mn2, i, Pn1, n2):
1. p78 P4H 180 @1400, i 353: 11300 Nm, 5.09 kW, 3.96 rpm - OK
2. p78 P4H 280 @1400, i 320: 45000, 22.4, 4.37 - OK
3. p109 B4H 180 @700, i 487: 11400, 1.86, 1.44 - OK
4. p109 B4H 250 @700, i 134: 30700, 18.2, 5.21 - OK
5. p83 P1H 280 @900, i 2.24: 25700, 1100, 402 - OK
6. p83 P1H 180 @900, i 2.83: 8500, 289, 318 - OK
7. p99 B3H 280 @1400, i 72.6: 42100, 90.4, 19.3 - OK
8. p99 B3H 200 @1400, i 125: 14000, 17.5, 11.2 - OK
9. p103 B4H 180 @1140, i 197: 10700, 7.03, 5.79 - OK
10. p103 B4H 180 @1140, i 432: 12600, 3.80, 2.64 - OK
Also viewed p42 (P2H drawing crop), p16 (motor matrix), p13 (designation), p18 (executions), p61 (output flange header) for layout checks.

## Gaps / open questions
- ELECTRIC MOTORS: the catalogue contains NO motor data tables. Pages 6-11 only have a marketing blurb (motors up to 90 kW, 2/4/6 poles, IP66, brake). Therefore `motors.csv` and `motors_dimensions.csv` were NOT created (nothing to extract, no invention). Series is sold as reducers (solid input shaft or bell-housing input for IEC motors).
- No gearmotor/mass-with-motor tables, no fs column in selection tables, no per-row radial load, no inertia (J) tables, no efficiency table (only the formulas on p21 with eta).
- Ratio range: designation diagram prints 1.22 ... 762.36, while the range table (p17) and performance tables show max i about 635 (PH) / 634 (BH) and min about 1.95 / 5.27. Performance tables are the authoritative rated ratios.
- Backstop (p63), optional seals (p65), cooling/heating unit (p58), installation texts (p66-68) are text only, no tables extracted; oil change interval and plug torques (p67): interval extracted, plug torque table not extracted (GAS 1/2 3/4 1 plug size by frame: 1/2 for 180-200, 3/4 for 225-280, 1 for 355; torque 60/70/70 Nm hex wrench, 30/40/50 Nm allen key).
- Product pages 6-11, logos not imaged; image set: designation diagram, versions, gear trains, executions, mounting positions, rotation, load drawings, all dimension drawings (one per train page), accessory drawings (73 files). Gear train / execution images are in reading order of the page; captions are per page, not per figure (kind `render` for 3D renders).
