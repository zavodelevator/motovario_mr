# Catalogue extraction — shared data schema

Every extractor agent writes ONLY into `data/raw/<SERIES>/` (its own directory).
Language of all files: English. Numbers: dot decimal, no thousands separator, SI units as in catalogue.
**Never invent or interpolate values.** Every row carries `src_page` (1-based PDF page index, not printed page number).
Empty = `""` (not 0, not "-"). Catalogue "/" or "-" means not available → `""`.

Series dirs: `H`, `HPL`, `PBH`, `VSF`, `B`, `SN`.

## Required files per series

### `ratings.csv` — the selection table (core of the calculator)
One row per (size, input speed, ratio) combination exactly as printed in the "selection tables / gearmotors / reducers" section.

| column | meaning |
|---|---|
| series | H / HPL / PBH / VSF / B / SN |
| size | printed size code, e.g. `H062`, `VSF 63`, `B 502` — keep catalogue spelling, one canonical form per size |
| stages | number of reduction stages if given (e.g. 2, 3), else "" |
| n1_rpm | input speed the row is rated at (e.g. 1400, 2800, 900) |
| p1_kw | rated input power, kW (if table lists power) |
| i | exact ratio as printed (e.g. 12.35) |
| n2_rpm | output speed, rpm |
| t2_nm | output torque, Nm (rated, at the stated fs) |
| fs | service factor printed in the row, "" if none |
| fr2_n | permissible radial load on output shaft, N, "" if none |
| motor_frames | IEC motor frames that fit this row, `;`-separated (e.g. `63;71;80`), "" if not given |
| variant | table variant / sub-table title if several (e.g. `reducer`, `gearmotor`, `foot`, `hollow`) |
| src_page | PDF page |

Add extra columns only if the catalogue has meaningful ones (e.g. `t2max_nm`, `efficiency`); list them in `notes.md`.

### `designation.json` — ordering code
Segments of the type designation in order, with allowed values and their meaning, e.g.
`{"pattern":"H 062 FA 2 ...", "segments":[{"name":"series","values":{"H":"helical"}}, ...]}`. Include mounting-position codes, output-shaft options, flange codes, options.

### `dimensions_*.csv` — dimension tables
One file per dimension table family (e.g. `dimensions_foot.csv`, `dimensions_flange.csv`, `dimensions_hollow_shaft.csv`). Long or wide format, but first columns always `series,size,variant`, then the catalogue's own letter-symbols as column names (D,B,b,t,C,E,F,G ...), then `src_page`. Keep catalogue symbols verbatim.

### `weights.csv`
`series,size,variant,motor_frame,mass_kg,src_page` (reducer or gearmotor mass; say which in `variant`).

### `lubrication.csv`
`series,size,mounting_position,oil_l,oil_type,src_page` (if the catalogue has it).

### `motor_interface.csv`
Which IEC motor frame/flange (B5/B14, Pm x Dm, bore) mates to which size: `series,size,iec_frame,flange,bore_mm,src_page`.

### `thermal.csv`, `radial_load_*.csv`, `service_factor.csv`
Only if present and tabular. Service-factor tables (load class × hours/day × starts/h) are IMPORTANT: `service_factor.csv` = `series,load_class,hours_per_day,starts_per_hour,fs,src_page`.

### `weights/other` — anything else tabular that a quotation could need goes in `extra_<name>.csv`.

### `images/` + `images/index.csv`
Cut out every product photo, 3D render and dimensional drawing (one file per figure) as PNG (render at ≥200 dpi when vector; use `pdfimages -png` for embedded rasters; crop page renders with Pillow/pdftoppm -x -y -W -H for vector art). Drop logos, icons, page decorations, duplicates.
`index.csv`: `file,series,size,kind,caption,src_page,width_px,height_px` where `kind` ∈ `photo|render|drawing|diagram|other`. Name files `<SERIES>_<size|general>_<kind>_p<page>_<n>.png`.

### `notes.md`
Page map of the catalogue (section → pages), how each table was parsed (tool, quirks), row counts per file, known gaps/ambiguities, list of the spot-checks done (≥10 random ratings rows compared against the rendered page image — give page, row, result).

## Quality gates (extractor must pass before reporting)
1. Row counts per size are plausible and each size listed in the catalogue index appears in `ratings.csv`.
2. Physical sanity: for every ratings row `t2_nm ≈ 9550 * p1_kw / n2_rpm * eta` — flag rows where the implied efficiency is outside 0.55–1.0 (worm gears can be low) in `notes.md`; do not silently fix, re-check the page.
3. `n2_rpm ≈ n1_rpm / i` within 3 %, else flag.
4. No duplicate (series,size,n1_rpm,i,variant) keys.
5. Scripts used for parsing live in `tools/extract_<SERIES>.py` (repo-root `tools/`, one file per series) so the run is reproducible. Parse with scripts (pdftotext -layout / pdfplumber); read page images only to verify and for layouts the text layer cannot resolve.

Do not git commit. Report: files written, row counts, gaps, open questions (short).
