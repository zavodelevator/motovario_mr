# SN (shaft mounted, IEC) extraction notes

Source: sources/catalogs/SN_shaft-mounted.pdf (90 pages, Motovario technical catalogue "S series / SN-ISN", rev. 2024). All src_page values are 1-based PDF pages (printed page number = PDF page - 2). Script: tools/extract_SN.py (run from repo root; re-creates everything in data/raw/SN/).

## Page map (PDF pages)

| section | PDF pages |
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

## Files and row counts

| file | rows |
|---|---|
| dimensions_assembly_kit.csv | 8 |
| dimensions_isn.csv | 8 |
| dimensions_machine_shaft.csv | 8 |
| dimensions_motor_flange.csv | 72 |
| dimensions_output_flange.csv | 10 |
| dimensions_reaction_bolt.csv | 8 |
| dimensions_shrink_disc.csv | 8 |
| dimensions_sn.csv | 8 |
| extra_critical_applications.csv | 4 |
| extra_efficiency.csv | 2 |
| extra_lubricants.csv | 31 |
| extra_motor_B5_bore.csv | 10 |
| extra_motor_flange_availability.csv | 349 |
| extra_output_bearings.csv | 24 |
| extra_shaft_end_keys.csv | 19 |
| images/index.csv | 21 |
| lubrication.csv | 48 |
| motor_interface.csv | 40 |
| motors.csv | 69 |
| motors_dimensions.csv | 46 |
| radial_load_params.csv | 16 |
| ratings.csv | 1347 |
| ratings_rejected.csv | 9 |
| service_factor.csv | 132 |
| weights.csv | 8 |
| designation.json | 1 object, 9 segments |
| images/*.png | 21 (see images/index.csv) |

## How the tables were parsed

* ratings.csv: two row families, column `kind`.
  * `kind=gearmotor` (pp.45-63, "5.1 SN geared motors 50 Hz"): pdftotext -layout, one row per printed line (n2, M2, sf, i, reducer, motor size/poles, n1, Fr2); the kW block header gives p1_kw. n1_rpm = actual motor speed printed in the table (e.g. 1450, 1475, 970), not the nominal 1500/1000. `t2_nm` = M2, `fs` = sf, `motor` = e.g. `180L/4`, `motor_frames` = IEC frame number only, `poles` from the motor code. 611 rows.
  * `kind=reducer` (pp.64-87, "5.2-5.7 ISN gear reducer", 6 input speeds x sizes ISN142..183): Mn2 -> t2_nm, Pn1 -> p1_kw (blank where printed "-"), Fr1 -> fr1_n, Fr2 -> fr2_n, n1_rpm = speed in the page title (2900/1450/950/725/475/360). `motor_frames` = IEC frames available for that ratio from the per-ratio flange tables on pp.22-23 (B5), word-coordinate parse. 736 rows. These tables carry no service factor (`fs` empty): rated torque Mn2 is the nominal torque, compare with Mr2*s.f. (p13).
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

## Quality gates

1. Sizes: every size from the index (SN/ISN 142,143,152,153,162,163,182,183) appears in ratings.csv. Rows per size: ISN142(reducer)=101, ISN143(reducer)=95, ISN152(reducer)=95, ISN153(reducer)=131, ISN162(reducer)=54, ISN163(reducer)=106, ISN182(reducer)=47, ISN183(reducer)=107, SN142(gearmotor)=62, SN143(gearmotor)=77, SN152(gearmotor)=50, SN153(gearmotor)=116, SN162(gearmotor)=40, SN163(gearmotor)=116, SN182(gearmotor)=45, SN183(gearmotor)=105.
2. Efficiency check t2 = 9550*P1/n2*eta, eta in 0.55-1.0: gearmotor rows -> 0 flagged. Reducer rows: Pn1 is printed as a rounded integer kW (small values such as 1-3 kW are +-0.5 kW rounded) so the check was run with Pn1 +-0.5 and n2 = n1/i; flagged: 2:
   * G2 reducer eta(n1/i) 1.026 (eta w/ printed n2 0.515) p64 ISN142 n1=2900 i=20.20 Pn1=63 Mn2=4300
   * G2 reducer eta(n1/i) 1.067 (eta w/ printed n2 0.536) p65 ISN152 n1=2900 i=22.77 Pn1=100 Mn2=8000
3. n2 vs n1/i within 3 %: gearmotor rows: 0 flagged (printed n2 has 1 decimal). **Reducer tables: the printed n2 column is identical on all six speed pages (it equals the 1450 rpm value, n2 = 1450/i), so for the 2900/950/725/475/360 rpm pages the printed n2 does not match n1/i (flag counts per page speed: {'2900': 124, '1450': 12, '950': 119, '725': 124, '475': 124, '360': 124}). The printed n2 is kept in `n2_rpm`; the correct n1/i is in `n2_calc_rpm`.** On the 1450 page the 12 flags are rounding of n2 to integers at low speeds (e.g. 12 vs 11.6).
4. Duplicate keys (series,size,n1_rpm,i,variant) in ratings.csv: 0.
5. Script: tools/extract_SN.py.

## Catalogue anomalies / flags

* Duplicate printed row dropped (identical to earlier page/row): p45 SN143 1.50kW 100L/6 i=124.53
* Duplicate printed row dropped (identical to earlier page/row): p59 SN152 45.00kW 225M/4 i=10.23
* Duplicate printed row dropped (identical to earlier page/row): p59 SN152 45.00kW 225M/4 i=9.00
* Duplicate printed row dropped (identical to earlier page/row): p59 SN152 45.00kW 225M/4 i=8.70
* Duplicate printed row dropped (identical to earlier page/row): p59 SN152 45.00kW 225M/4 i=7.76
* Duplicate printed row dropped (identical to earlier page/row): p59 SN152 45.00kW 225M/4 i=6.97
* Duplicate printed row dropped (identical to earlier page/row): p59 SN152 45.00kW 225M/4 i=6.58
* Duplicate printed row dropped (identical to earlier page/row): p59 SN152 45.00kW 225M/4 i=5.75
* Duplicate printed row dropped (identical to earlier page/row): p59 SN152 45.00kW 225M/4 i=5.06
* Duplicate printed row dropped (identical to earlier page/row): p59 SN152 45.00kW 225M/4 i=4.47
* Duplicate printed row dropped (identical to earlier page/row): p59 SN153 45.00kW 225M/4 i=27.65
* Duplicate printed row dropped (identical to earlier page/row): p59 SN153 45.00kW 225M/4 i=24.06
* Duplicate printed row dropped (identical to earlier page/row): p59 SN153 45.00kW 225M/4 i=20.87
* Duplicate printed row dropped (identical to earlier page/row): p59 SN153 45.00kW 225M/4 i=18.61
* Duplicate printed row dropped (identical to earlier page/row): p59 SN153 45.00kW 225M/4 i=17.95
* Duplicate printed row dropped (identical to earlier page/row): p59 SN162 45.00kW 225M/4 i=14.02
* Duplicate printed row dropped (identical to earlier page/row): p59 SN162 45.00kW 225M/4 i=12.36
* Duplicate printed row dropped (identical to earlier page/row): p59 SN162 45.00kW 225M/4 i=10.97
* Duplicate printed row dropped (identical to earlier page/row): p59 SN162 45.00kW 225M/4 i=9.78
* Duplicate printed row dropped (identical to earlier page/row): p59 SN162 45.00kW 225M/4 i=8.75
* Duplicate printed row dropped (identical to earlier page/row): p59 SN162 45.00kW 225M/4 i=8.12
* Duplicate printed row dropped (identical to earlier page/row): p59 SN162 45.00kW 225M/4 i=7.16
* Duplicate printed row dropped (identical to earlier page/row): p59 SN162 45.00kW 225M/4 i=6.35
* Duplicate printed row dropped (identical to earlier page/row): p59 SN162 45.00kW 225M/4 i=5.66
* Duplicate printed row dropped (identical to earlier page/row): p59 SN163 45.00kW 225M/4 i=45.41
* Duplicate printed row dropped (identical to earlier page/row): p59 SN163 45.00kW 225M/4 i=39.92
* Duplicate printed row dropped (identical to earlier page/row): p59 SN163 45.00kW 225M/4 i=35.24
* Duplicate printed row dropped (identical to earlier page/row): p59 SN163 45.00kW 225M/4 i=30.50
* Duplicate printed row dropped (identical to earlier page/row): p59 SN163 45.00kW 225M/4 i=26.66
* Duplicate printed row dropped (identical to earlier page/row): p59 SN163 45.00kW 225M/4 i=23.44
* Duplicate printed row dropped (identical to earlier page/row): p59 SN163 45.00kW 225M/4 i=17.67
* Duplicate printed row dropped (identical to earlier page/row): p59 SN163 45.00kW 225M/4 i=15.45
* Duplicate printed row dropped (identical to earlier page/row): p59 SN163 45.00kW 225M/4 i=13.58
* Duplicate printed row dropped (identical to earlier page/row): p59 SN182 45.00kW 225M/4 i=16.64
* Duplicate printed row dropped (identical to earlier page/row): p59 SN183 45.00kW 225M/4 i=63.36
* Duplicate printed row dropped (identical to earlier page/row): p59 SN183 45.00kW 225M/4 i=56.21
* Duplicate printed row dropped (identical to earlier page/row): p59 SN183 45.00kW 225M/4 i=50.12
* Duplicate printed row dropped (identical to earlier page/row): p59 SN183 45.00kW 225M/4 i=43.38
* Duplicate printed row dropped (identical to earlier page/row): p59 SN183 45.00kW 225M/4 i=38.24
* Duplicate printed row dropped (identical to earlier page/row): p59 SN183 45.00kW 225M/4 i=33.93
* The 45.00 kW 225M/4 block (SN152..SN183) is printed identically on PDF pages 58, 59 and 60; only the first (p58) is kept.
* ratings_rejected.csv (9 rows): reducer rows whose ratio does not exist for that size (copy/paste leftovers: e.g. i=5.66 of ISN162 repeated in ISN163/ISN182/ISN183/ISN142/143/152/153 tables, 26.11 under ISN152, 13.58 under ISN162). Not used.
* The p23 SN182 flange table lists ratio 14.02 as last row (a ratio of SN162, not SN182); it is kept as printed in extra_motor_flange_availability.csv and is not a ratio of SN182 in the ratings tables.
* Gearmotor sf differs from the reducer approach: sf is the catalogue safety factor of the unit (M2 rated / required), compare with the service factor s.f. of the application (S >= s.f., p12).
* Max torque rule p13: peak <= 200 % of Mn2 (2*Mn2). Critical applications p21: SN, 1500<n1<3000 rpm -> code B (check application / contact Motovario) for all sizes.
* Catalogue is 50 Hz IEC; 60 Hz correction formulas on p12.

## Spot-checks against rendered page images (>=10 required)

| PDF page | row | printed values | result |
|---|---|---|---|
| p54 | SN163 22.00kW i=101.03 180L/4 | n2 14.6, M2 13637, sf 1.0, Fr2 73103 | match |
| p49 | SN153 11.00kW i=72.50 160M/4 | n2 20.3, M2 4922, sf 1.6, Fr2 72832 | match |
| p56 | SN163 30.00kW i=13.58 200L/4 | n2 108.6, M2 2541, sf 4.0, Fr2 86150 | match |
| p46 | SN143 4.00kW i=44.27 132M/6a | n2 21.9, M2 1653, sf 2.6, Fr2 47819 | match |
| p47 | SN143 5.50kW i=44.27 132S/4 | n2 33.0, M2 1517, sf 2.8, Fr2 48408 | match |
| p61 | SN182 75.00kW i=14.77 280S/4 | n2 100.5, M2 6932, sf 2.6, Fr2 97071 | match |
| p48 | SN142 7.50kW i=23.36 132M/4 | n2 62.7, M2 1104, sf 3.9, Fr2 50149 | match |
| p76 | ISN142 725rpm i=11.96 | Mn2 4030, Pn1 28, n2 121, Fr2 35135 | match |
| p83 | ISN183 475rpm i=25.92 | Mn2 18000, Pn1 36, n2 56, Fr1 20039, Fr2 85446 | match |
| p65 | ISN153 2900rpm i=53.99 | Mn2 8000, Pn1 -, n2 27, Fr1 2582, Fr2 55500 | match |
| p65 | ISN152 2900rpm i=7.76 | Mn2 5010, Pn1 -, n2 187, Fr2 33787 | match |
| p80 | ISN143 475rpm i=197.01 | Mn2 4300, Pn1 1, n2 7, Fr1 3499, Fr2 29600 | match |
| p70 | ISN163 1450rpm i=115.03 | Mn2 13000, Pn1 18, n2 13, Fr1 5167, Fr2 76000 | match |

Additionally checked visually: p30 header (two columns printed `S`), p14 service-factor chart curve scale.

## Open questions

* Is the reducer n2 column of the 2900/950/725/475/360 rpm tables a catalogue copy error (our assumption) or is n2 meant at 1450? Pn1 values scale roughly with n1, so n2 = n1/i is assumed.
* Pn1 on the reducer pages is not always consistent with Mn2*n2/9550/eta at the page speed (e.g. ISN142 i=4.28: 30 kW at 360 rpm vs ~20 kW computed); left as printed.
* Meaning of the first of the two `S` columns in the housing dimension table (probably drawing symbol R).
* Motor mass / efficiency / current / torque for SN motors are not in this catalogue.
