# Sources: Motovario motor catalogue and 2D/3D CAD (research 2026-10-28)

Status legend: VERIFIED = page content read in this session; UNVERIFIED = found by search only, content not readable from the sandbox.

## 1. Electric-motor catalogue

| Source | URL | Status | Notes |
|---|---|---|---|
| M series IEC size 56-132 technical catalogue (official) | https://www.motovario.com/eng/download/electric-motors--m-series -> doc "TECHNICAL CATALOGUE - M / IEC Size 56-132" (`my.motovario.com/file.php?s=42k9`) | VERIFIED listing, PDF not fetched | Best primary source. A `file.php` redirect, needs a browser download. |
| Same catalogue, Motovario Poland mirror | https://motovario.com.pl/wp-content/uploads/2023/12/TECHNICAL-CATALOGUE_M_IEC_STD_EN_rev0_2023.pdf | UNVERIFIED | Direct PDF; shell download blocked (proxy 403). |
| IE1/IE2 motor datasheet mirror | https://www.motovarioprevodovky.cz/pdf/D_IE1_IE2_en.pdf | UNVERIFIED | Binary, not readable here. |
| "Technical catalogue Standard IEC drives" (D series) | https://www.motovarioprevodovky.cz/pdf/D_en.pdf | VERIFIED | NOT the motor catalogue: 36 pages, mostly DRIVON inverter-motors. Do not use for motor tables. |
| DirectIndustry "Electric motors" | https://pdf.directindustry.com/pdf/motovario/electric-motors/2245-544535.html | VERIFIED | 6 pages of marketing text, no data tables. |

Conclusion: the motor data tables (rpm, current, efficiency, mass) exist only in the official M catalogue. The owner must download/attach it (see section 3). Until then the app uses nominal kW/frame/poles from the gear catalogues.

## 2. 2D drawings and 3D models

| Source | URL | Status | Notes |
|---|---|---|---|
| Motovario official CAD portal (CADENAS PARTcommunity) | https://motovario.partcommunity.com/ | UNVERIFIED (fetch failed) | "MOTOVARIO 2D/3D drawings". Formats and licence terms not confirmed. |
| Official configurator links for the M motors | https://my.motovario.com/product-selection-3/configurator-1/m/m-10/ (and `/m-teco/m-10/`) | Listing VERIFIED, page not on the fetch allowlist | "DOWNLOAD 2D/3D CAD DRAWINGS - M". Gear-unit series have analogous configurators on my.motovario.com. |
| 3Dfindit library | https://www.3dfindit.com/en/cad-bim-library/manufacturer/motovario/gear-motors-and-gear-units/ | UNVERIFIED (fetch failed) | Same CADENAS data, free download listed in search snippet. |
| Third-party free models (CGTrader, Sketchfab, 3DMDB) | see search results | Not used | Not official, licence unknown, accuracy unknown. Do not use in quotes. |

## 3. Proposed use in the calculator and the KP (needs owner action first)

1. **Owner downloads**, from the official portal with their own login, STEP (3D) and DXF/PDF (2D) for the sizes the calculator offers, plus the M-series motor catalogue PDF, and attaches them. The sandbox cannot reach these hosts.
2. **Licence check before use:** confirm the portal terms allow dealer use of the drawings in quotations and on a web page; keep Motovario's mark off unless dealer status is confirmed (KP_SPEC, ADR-008).
3. **Pipeline (Sonnet implements, Haiku for batch steps):** STEP -> glTF (python `trimesh`/`cadquery` via pip, reachable) -> per-size `models/<series>_<size>.glb` + rendered PNG for the KP (fixed isometric view, white background) + SVG outline from DXF for the dimension drawing page.
4. **Calculator visualisation:** three.js (npm/CDN) viewer in the candidate row; orbit view; mounting-position selector rotating the model. KP uses the PNG, not the live viewer.
5. Until models arrive, keep the catalogue crops in `data/raw/*/images` (already in the KP).

## Sources
- [Motovario M series download page](https://www.motovario.com/eng/download/electric-motors--m-series)
- [Motovario CAD portal](https://motovario.partcommunity.com/)
- [3Dfindit Motovario library](https://www.3dfindit.com/en/cad-bim-library/manufacturer/motovario/gear-motors-and-gear-units/shaft-mounted-geared-motors-and-gear-units?path=motovario%2Fmotoriduttori_e_riduttori%2Fpendolare)
- [Motovario Poland M IEC 2023 PDF](https://motovario.com.pl/wp-content/uploads/2023/12/TECHNICAL-CATALOGUE_M_IEC_STD_EN_rev0_2023.pdf)
- [D series Standard IEC drives (not a motor catalogue)](https://www.motovarioprevodovky.cz/pdf/D_en.pdf)
