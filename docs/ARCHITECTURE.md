# Motovario Quote Calculator: Architecture

Status: accepted for MVP build. Author: Quality Architect. Date: 2026-10-27.
Companion docs: `docs/DATA_SCHEMA.md` (catalogue CSV produced by the extractors), `docs/KP_SPEC.md` (the commercial proposal document), `docs/motor_catalogue_sources.md`.

## 0. Scope and constraints

**Goal.** A web calculator that selects a Motovario gearmotor (or gear reducer plus IEC motor) from application parameters, ranks candidates, and produces a commercial proposal (KP) PDF in Motovario visual style. UI and KP are in Ukrainian. The users are managers of a reseller organisation: the owner's second organisation, which has its own instance in the Rails CRM `new_ax_crm`.

**Owner decisions (fixed inputs to this design).**

| # | Decision | Consequence here |
|---|---|---|
| D1 | No prices yet. Prices plug in later as an EUR purchase price list plus margin. | Money fields exist and are nullable. A `Pricing` strategy hook ships with a null strategy. The KP renders without price columns. |
| D2 | Standalone site now. CRM integration later, as a separate task, through a contract. | Own repo, own DB, a versioned HTTP API (`/api/v1`). No shared tables, no imports of CRM code. See vault `Модульність проєктів — Правило`. |
| D3 | KP currency is UAH incl. 20% VAT. The manager enters the exchange rate. Rounding follows the CRM rule: round up to an integer divisible by 3. | Applied in `Pricing::UahRounding` once prices exist. Exchange rate and VAT rate are stored per quote. |
| D4 | Selection works from parameters (torque or power, output rpm or ratio, series or type, mounting, service factor from duty class), with a recommended motor and a manual override of the code. | §4 algorithm. Manual override runs the same checks in verify mode. |

**Environment facts.** Ruby 3.3.6, Node 22, Chromium with Playwright preinstalled. The owner's CRM runs Ruby 3.4.6, Rails, Postgres, Hotwire, Prawn and Grover. The owner is a strong Rails developer and weaker on JS and DevOps. The CRM already made the Grover decision for HTML-faithful PDFs (vault `projects/new_ax_crm/decisions/2026-05-23_document-constructor-architecture.md`) and moved Grover rendering into a background job because each render costs 1-3 s and 100-300 MB (`sessions/2026-06-27_security-perf-hardening-stages-0-4.md`).

**Mode.** `optimal` (new product, data model, public API). See §11 for per-task model tiers.

---

## 1. Recommended stack (summary)

| Concern | Choice | One-line reason |
|---|---|---|
| App framework | **Rails 8.0 monolith**, Hotwire (Turbo + Stimulus), importmap, no JS bundler | Owner's strongest skill; same idioms as the CRM; the API for the CRM comes almost free |
| Database | **SQLite 3** (Rails 8 production-grade defaults), one file on a volume | Catalogue data is read-mostly and reloadable from CSV; few users; lowest ops cost. Postgres is a one-line switch later (ADR-002) |
| PDF | **Grover** (Puppeteer and headless Chromium) rendering an ERB/HTML template with print CSS | Brand fidelity (bars, tables, photos, fonts) from the same HTML as the on-screen preview; already known from the CRM |
| Background jobs | Solid Queue (Rails 8 default, runs on the same SQLite) | PDF render off the request thread, as in the CRM |
| Auth (UI) | Rails 8 authentication generator (`has_secure_password`, sessions) | A handful of managers; no external IdP needed |
| Auth (API) | Bearer tokens per API client, stored as SHA-256 digests | Simple, revocable, scoped |
| Styling | Plain CSS with design tokens (`app/assets/stylesheets/tokens.css`), no Tailwind | Vault pattern `Патерн — Дизайн-токени поверх CSS-фреймворку`; the same tokens drive screen and PDF |
| Fonts | **Montserrat** (SIL OFL), self-hosted woff2 files | The catalogue uses Gotham (commercial licence). Montserrat is the closest free geometric sans. Never fetch fonts at PDF time |
| Tests | Minitest (Rails default), `capybara-playwright-driver` for system tests, `pdftotext` for PDF assertions | Uses the preinstalled Playwright and Chromium; no Selenium or chromedriver to manage |
| Deploy | Dockerfile (Ruby + Node + Chromium) + `compose.yml` + `hub.yml` manifest | Modularity rule: the platform reads the app's manifest |

### 1.1 App framework: Rails vs lightweight alternatives

| Option | Fit for owner | Selection UI | KP PDF | Future CRM API | Ops cost | Verdict |
|---|---|---|---|---|---|---|
| **Rails 8 monolith** | ★★★ (daily tool) | Turbo Frames: form posts, candidate table re-renders, no JS app | Grover, as in CRM | `Api::V1` controllers + JSON schemas in the same codebase | One container, SQLite file | **Chosen** |
| Sinatra/Roda + Sequel | ★★ | Hand-rolled forms, no Turbo conventions | Grover works, but no ActiveJob or mailer glue | Easy, but auth and versioning built by hand | Same as Rails | Saves ~30 MB RAM; costs days of glue code the owner would maintain in an unfamiliar shape |
| Node (Next.js / Remix) | ★ (owner weaker in JS) | Rich client | Puppeteer native | Fine | Node runtime + build pipeline | Wrong skill fit; no reuse of CRM patterns |
| Static SPA (data as JSON, client PDF via pdfmake/jsPDF) | ★ | Instant, offline | Client PDF libraries have weak typography and Cyrillic font handling; style fidelity drops | None (no server), so the CRM contract has nothing to talk to | Near zero hosting | Fails D2 (needs an API later), quotes not stored, prices would leak to the browser once added |

Rails costs a heavier container than Sinatra. In return it gives one stack across the owner's two products, conventions the auditor prompts already know, and a direct path to the API. Decision: ADR-001.

### 1.2 PDF: Prawn vs Chromium HTML (Grover)

| Criterion | Prawn (+ prawn-table) | Grover (HTML + print CSS -> Chromium) |
|---|---|---|
| Motovario style fidelity (blue bars, grey bands, tab headers, zebra tables, product photos, light/bold weights) | Achievable, but each element is drawn by coordinates; two-column technical blocks that break across pages need manual measuring | CSS grid/flex, `break-inside: avoid`, `@page` margins, running header/footer via Puppeteer `headerTemplate`/`footerTemplate` |
| Iteration speed on layout | Slow (re-run, inspect) | Fast: the same page renders in the browser as `/quotes/:id/preview` |
| Screen preview = PDF | No (two renderers) | Yes (one template) |
| Cyrillic + custom fonts | Needs TTF registration per family and weight; fine once set | `@font-face` with local woff2; fine |
| Determinism and tests | Excellent (pure Ruby, fast) | Good. Pin the Chromium version; assert with `pdftotext` and page-count checks; screenshot comparison with Playwright |
| Ops cost | Zero extra runtime | Node + puppeteer + Chromium in the image (~350 MB); 100-300 MB RAM per render; needs a job queue |
| Owner familiarity | 7+ Prawn PDFs in CRM | Grover in CRM Document Builder, incl. async job |

Decision: **Grover** (ADR-003). The product is a branded sales document whose value is that it looks like Motovario's catalogue. HTML gives that fidelity at the lowest build and maintenance effort, and the preview is free. The ops cost is real but bounded: one render per issued KP, run in Solid Queue with concurrency 1, and the image already needs Chromium for the system tests. Prawn stays the fallback if the host cannot run Chromium. The view-model (`Kp::Document`) is renderer-agnostic, so a Prawn renderer could be added without touching selection or pricing.

---

## 2. Module layout

Boundaries follow the vault patterns `Rails Service Form Query Object` and `Clean Architecture та межі сервісу`. The selection core is pure Ruby with no ActiveRecord inside, so the UI, the API and the tests all call the same code.

```
app/
  models/
    catalog/            # ActiveRecord, read-only at runtime (written only by the importer)
      dataset.rb  series.rb  gear_size.rb  rating.rb  motor.rb  motor_interface.rb
      service_factor_entry.rb  radial_load_factor.rb  thermal_rating.rb
      dimension.rb  weight.rb  lubrication.rb  image.rb  efficiency.rb
    quote.rb  quote_item.rb  seller_profile.rb  user.rb  api_client.rb
    price_list.rb  price_list_entry.rb          # tables created in the pricing task, empty now
  selection/            # PORO core, no AR calls; depends on a Repository interface
    request.rb          # value object + validation (ActiveModel::Model)
    duty.rb             # service-factor lookup (load class, h/day, starts/h, fa)
    engine.rb           # §4 steps, returns Result
    checks/             # torque.rb  motor.rb  radial.rb  thermal.rb  peak.rb  fit.rb  critical.rb
    candidate.rb  result.rb  ranking.rb
    designation_parser.rb   # manual override: code -> series/size/i/motor
    repository.rb       # interface; Catalog::Repository implements it with AR
  pricing/
    strategy.rb  null_strategy.rb  price_list_strategy.rb (later)  uah_rounding.rb  money.rb
  kp/
    document.rb         # view-model built from Quote (frozen snapshots only)
    numbering.rb        # MV-YYYY-NNNN per seller profile
    pdf_renderer.rb     # Grover wrapper; data-URI images; pinned options
  jobs/render_kp_pdf_job.rb
  controllers/
    selections_controller.rb  quotes_controller.rb  quote_items_controller.rb
    settings/seller_profiles_controller.rb  admin/datasets_controller.rb
    api/v1/base_controller.rb  api/v1/selections_controller.rb  api/v1/quotes_controller.rb  api/v1/meta_controller.rb
  views/ (uk only)  quotes/kp.html.erb  layouts/kp.html.erb
lib/
  catalog_import/       # CSV -> Catalog::Dataset; validators mirror DATA_SCHEMA quality gates
    importer.rb  series_adapter.rb  adapters/{h,hpl,pbh,vsf,b,sn}.rb  report.rb
  tasks/catalog.rake    # bin/rails catalog:import[data/raw] catalog:activate[VERSION]
config/
  selection.yml         # tolerances, efficiency defaults, fz table, HS-code table, mounting->variant maps
  locales/uk.yml
```

**Dependency direction.** `controllers -> selection/pricing/kp -> repository interface <- catalog models`. `selection/` never requires `pricing/` or `kp/`. `kp/` reads only `Quote`/`QuoteItem` snapshots, never live catalogue rows. Prices therefore cannot change an issued KP, and neither can a catalogue re-import.

---

## 3. Data model

All catalogue tables carry `dataset_id` and `src_page`. Catalogue rows are immutable once imported; a re-import creates a new `Catalog::Dataset` and an admin activates it. Money is stored as integer minor units (`*_cents` for EUR, `*_kop` for UAH), so SQLite's lack of a true decimal type does not matter (ADR-005).

### 3.1 Catalogue (read-only at runtime)

```
catalog_datasets      id, version (string, e.g. "2026-10-27a"), source_manifest_json (file -> sha256),
                      import_report_json (row counts, flags), active (bool, exactly one true), imported_at
catalog_series        id, dataset_id, code (H|HPL|PBH|VSF|B|SN), name_uk, gear_type
                      (helical|planetary|parallel_helical|bevel_helical|worm|shaft_mounted),
                      shaft_arrangement (inline|parallel|right_angle), mn2_max_nm, catalogue_file,
                      catalogue_edition, sort_order
catalog_gear_sizes    id, dataset_id, series_id, code (canonical, e.g. "H062"), family_code,
                      stages, size_rank (int, ascending by max Mn2 within series), output_shaft_d_mm,
                      hollow_shaft_d_mm, atex_available (bool|null)
catalog_ratings       id, dataset_id, series_id, gear_size_id, kind (gearmotor|reducer),
                      n1_rpm, p1_kw, i, n2_rpm, m2_nm (gearmotor: torque at motor rating),
                      mn2_nm (reducer: nominal torque; gearmotor: matched or derived, see §4.4),
                      mn2_source (table|derived), fs (printed), fr1_n, fr2_n,
                      motor_frame (gearmotor rows), motor_poles, variant, extra_json, src_page
                      index: (series_id, kind, n1_rpm, n2_rpm), (gear_size_id, i)
catalog_motors        id, dataset_id, frame ("160MA"), iec_size (160), poles, p_kw, line (TS|TH|TP|SH|HSH|TBP...),
                      efficiency_class (IE1|IE2|IE3), n_rpm (null until M catalogue), voltage_text, ip,
                      insulation_class, i_n_a, cos_phi, eta_pct (null until M catalogue),
                      brake (bool), mass_kg, dims_json, src_series, src_page
catalog_motor_interfaces  dataset_id, gear_size_id, iec_frame (63..280), flange (B5|B14), pam_code, bore_mm, src_page
catalog_service_factor_entries  dataset_id, series_id (null = generic chart), load_class (A|B|C),
                      hours_per_day, starts_per_hour, fs, verified_by (string), src_page
catalog_radial_load_factors     dataset_id, gear_size_id, shaft (input|output), a_mm, b_mm, fr_max_n, fa_max_n, src_page
catalog_thermal_ratings         dataset_id, gear_size_id, n1_rpm, pth_kw, src_page
catalog_efficiencies            dataset_id, series_id, stages, eta (H: 1 -> 0.97, 2 -> 0.96, 3 -> 0.94, p.~11 of H catalogue)
catalog_dimensions    dataset_id, gear_size_id, variant, symbol, value_text, src_page   (long format)
catalog_weights       dataset_id, gear_size_id, variant, motor_frame, mass_kg, src_page
catalog_lubrications  dataset_id, gear_size_id, mounting_position, oil_l, oil_type, src_page
catalog_images        dataset_id, series_id, gear_size_id (null = series-level), kind (photo|render|drawing|diagram),
                      file_path, caption, width_px, height_px, src_page
```

### 3.2 Quotes

```
seller_profiles   id, org_name, short_name, edrpou, ipn, vat_payer (bool), address, phone, email, website,
                  iban, bank_name, mfo, logo (ActiveStorage), brand_mark_enabled (bool, default false),
                  dealer_statement_uk (text, null), number_prefix ("MV"), default_validity_days (30),
                  default_payment_terms_uk, default_incoterms ("DAP"), default_delivery_place,
                  default_delivery_method_uk, default_lead_time_uk, default_warranty_uk,
                  default_vat_rate_bp (2000), disclaimer_texts_json
users             id, name, position_uk, phone, email, password_digest, role (manager|admin)
quotes            id, seller_profile_id, user_id (manager = contact person), number (null while draft),
                  revision (int, 1), status (draft|issued|superseded|cancelled), issued_at,
                  date, request_date, valid_until,
                  customer_name, customer_edrpou, customer_address, customer_code,
                  contact_name, contact_honorific (Пан|Пані|null), contact_phone, contact_email,
                  currency ("UAH"), fx_eur_uah_e4 (int, rate x 10^4, null), vat_rate_bp (2000),
                  pricing_mode (none|manual|price_list), price_list_id (null),
                  payment_terms_uk, incoterms, delivery_place, delivery_method_uk, lead_time_uk,
                  warranty_uk, notes_uk, seller_snapshot_json (frozen at issue),
                  catalog_dataset_id, total_gross_kop, total_net_kop, total_vat_kop (null when unpriced),
                  external_system (null|"new_ax_crm"), external_ref (CRM deal id), idempotency_key (unique, null),
                  pdf (ActiveStorage), pdf_rendered_at
quote_items       id, quote_id, position (1..), qty, unit_uk ("шт"), type_name_uk ("Циліндричний мотор-редуктор"),
                  designation (full code as printed on KP), customer_item_ref,
                  selection_request_json (inputs as entered), selection_result_json (candidate + checks + warnings),
                  rating_id, motor_id, gear_size_id (refs into the dataset the quote pins),
                  override (bool), override_reason_uk, verification_status (passed|warnings|failed_overridden),
                  tech_snapshot_json (every KP technical field, frozen; keys per KP_SPEC §4),
                  image_id, drawing_image_id, mass_kg, hs_code, atex_json (manual ATEX fields, null),
                  -- pricing hook (all nullable now) --
                  purchase_eur_cents, margin_bp, price_source (none|manual|price_list),
                  price_list_entry_id, unit_gross_kop, unit_net_kop, line_gross_kop, line_net_kop, line_vat_kop
api_clients       id, name, token_digest, scopes (csv), last_used_at, revoked_at
```

### 3.3 Pricing hook (designed now, implemented later)

```
price_lists          id, supplier ("Motovario"), currency ("EUR"), valid_from, valid_to, source_file, imported_at
price_list_entries   id, price_list_id, match_kind (designation|size_motor|size|adder),
                     series_code, gear_size_code, motor_frame, option_code, pattern (designation glob),
                     price_eur_cents, notes
```

`Pricing::Strategy#price(item, quote) -> Pricing::Quote(unit_purchase_eur_cents, source)`. `NullStrategy` returns nil, which makes `quote.priced?` false, and the KP hides every price column (KP_SPEC §6). `PriceListStrategy` (later) sums the base entry and the option adders.

Conversion and rounding, applied per unit (D3 and CRM rule):

```
unit_net_uah_exact   = purchase_eur * (1 + margin) * fx_eur_uah
unit_gross_uah       = ceil_to_3( ceil( unit_net_uah_exact * (1 + vat) ) )   # integer UAH, divisible by 3
unit_net_kop         = round_half_up( unit_gross_uah * 100 / (1 + vat) )     # net is back-calculated
unit_vat_kop         = unit_gross_uah * 100 - unit_net_kop
line_gross_kop       = unit_gross_uah * 100 * qty                            # stays divisible by 3 UAH
totals               = sums of line values; total_vat = total_gross - total_net
ceil_to_3(n)         = ((n + 2) / 3) * 3   (integer division)                # 122500 -> 122502, 122502 -> 122502
```

Gross is the anchor because the CRM rule targets the price with VAT. Rounding the net price first would break divisibility by 3. Manual price entry (`price_source = manual`) takes `unit_gross_uah` directly and validates `% 3 == 0`.

---

## 4. Selection algorithm

Implemented in `Selection::Engine#call(request) -> Result`. All numbers are SI as in the catalogue: torque Nm, speed rpm, power kW, force N, length mm.

### 4.1 Inputs (`Selection::Request`)

| Field | Type | Required | Default |
|---|---|---|---|
| `load_torque_nm` (T_load) | float | one of T or P | none |
| `load_power_kw` (P_load, absorbed at output) | float | one of T or P | none |
| `n2_rpm` target | float | one of n2 or i | none |
| `ratio` target | float | one of n2 or i | none |
| `n2_tolerance_pct` | float | no | 5 (auto-widen to 10, flagged) |
| `ratio_tolerance_pct` | float | no | 3 |
| `poles` | 2, 4, 6 or `any` | no | 4 |
| `series` | list of codes, ordered by preference | no | all |
| `shaft_arrangement` | inline, parallel, right_angle | no | any |
| `mounting` | foot, flange, shaft_mounted (hollow + torque arm) | no | any |
| `output_shaft` | solid, hollow | no | any |
| `mounting_position` | catalogue code (B3, V5 ... or M1..M6) | no | B3/M1 |
| `kind` | gearmotor, reducer_plus_motor, any | no | any (gearmotor tables first) |
| `load_class` | A, B, C | yes unless fs given | none |
| `fa` (Je/Jm) | float | no | if given, derives the load class |
| `hours_per_day` | float | yes unless fs given | 8 |
| `starts_per_hour` | float | yes unless fs given | 5 |
| `fs_min` (manual service factor) | float | no | overrides the lookup if higher; replaces it if `fs_override: true` |
| `radial_load_n` (Fr2 applied) or (`transmission_element`, `element_diameter_mm`) | float/enum | no | none |
| `radial_load_x_mm` (distance from shaft shoulder) | float | no | mid-shaft |
| `peak_torque_nm` | float | no | none |
| `ambient_c`, `altitude_m`, `ventilation` | float/enum | no | 25, 0, indoor_slight |
| `atex` | bool | no | false |
| `brake` | bool | no | false |

### 4.2 Step 1: normalise and validate

1. If only `P_load` is given: `T_load = 9550 * P_load / n2`. If only `ratio` is given (no n2): `n2_target = n1_nominal(poles) / ratio`, with n1_nominal = 2800 / 1400 / 900 (the catalogue's table speeds). This is used for filtering only; each row's own n2 is used afterwards.
2. If both T and P are given: require `|9550*P/n2 - T| / T <= 10%`, else reject with both values shown.
3. If both n2 and ratio are given: require `|n1_nominal/ratio - n2| / n2 <= 3%`, else reject.
4. Apply the §5 validation rules. Hard violations stop the run; soft ones become warnings on the Result.

### 4.3 Step 2: required service factor

1. Load class: use `load_class` if given. Otherwise derive it from `fa = Je/Jm`: `fa <= 0.3 -> A`, `<= 3 -> B`, `<= 10 -> C`, `> 10 -> hard error "звернутися до техслужби Motovario"` (catalogue §1.5).
2. Table: `service_factor_entries` for the series under test; if the series has none, use the generic (H) chart and add the warning `fs_chart_generic`.
3. Hours: take the smallest tabulated `hours_per_day` that is `>= input` (columns 2, 8, 16, 24). Conservative, no interpolation between hour columns.
4. Starts: clamp `starts < 5` to 5. Linearly interpolate between the tabulated starts points. `starts > 100` is a hard error (outside the chart).
5. `fs_lookup` = interpolated value rounded **up** to 0.05.
6. `fs_req = max(fs_lookup, fs_min)`. If `fs_override` is true: `fs_req = fs_min` and add the warning `fs_overridden` (recorded on the item).
7. 60 Hz is out of MVP scope. A 50 Hz-only notice appears in the UI.

`fs_req` depends on the series because the worm chart (VSF) differs from the helical one. Step 3 therefore runs per series.

### 4.4 Step 3: required output torque and candidate rows

```
T2_req = T_load * fs_req
```

**Path A, gearmotor rows** (`kind = gearmotor`). A row is a candidate when all of these hold:

| # | Condition | Meaning |
|---|---|---|
| A1 | series and size allowed by the filters (series list, shaft arrangement, mounting -> variant map from `config/selection.yml`, output shaft, ATEX if required and known) | type fit |
| A2 | `motor_poles == poles` (unless `any`) | speed family |
| A3 | `abs(row.n2 - n2_target) / n2_target <= n2_tol`, or in ratio mode `abs(row.i - i_target)/i_target <= i_tol` | speed fit |
| A4 | `row.m2_nm >= T_load` | the motor is not overloaded at rated power |
| A5 | `row.mn2_nm >= T2_req`, where `mn2_nm` = the matching reducer-table Mn2 (same canonical size, `abs(i_red - i)/i <= 0.5%`, `mn2_source = table`) or else `m2_nm * fs` (`mn2_source = derived`, warning `mn2_derived` because the printed M2 and fs are rounded) | gearbox strength incl. duty |

Application service factor reported: `fs_app = mn2 / T_load`. Catalogue (motor-based) service factor reported: `row.fs`.

**Path B, reducer rows + separate motor** (`kind = reducer`). Used when `kind` allows it, or when Path A returns nothing for a series:

1. Rows with `n1_rpm` equal to the motor family speed (1400 table for 4-pole; nearest table for 2/6-pole, warning if it is not exact) and the A1 and A3 conditions.
2. `mn2_nm >= T2_req`.
3. `P_req = T_load * row.n2 / (9550 * eta)`, where `eta` comes from `catalog_efficiencies(series, stages)`. If missing, use the row's implied `eta = mn2 * n2 / (9550 * pn1)` clamped to [0.5, 0.98], with warning `eta_implied`.
4. Motor = the smallest `catalog_motors` entry with `poles` matching, `p_kw >= P_req`, `iec_frame` listed in `motor_interfaces` for this gear size, preferring line TP (IE3) when the catalogue offers it at that power, then TH/SH.
5. Motor-to-gearbox fs: `fs_motor = row.pn1 / motor.p_kw`. If `< 1.0`: warning `motor_can_overload_gearbox` (a stalled load can drive more than Mn2 through the box).
6. `fs_app = mn2 / T_load`. Motor torque at output: `M2_motor = 9550 * motor.p_kw * eta / row.n2`.

### 4.5 Step 4: checks per candidate (hard = reject, soft = warning)

| Check | Rule | Severity | Source |
|---|---|---|---|
| Radial load | If `Fr2` is not given but a transmission element is: `Fre = 2000 * T_load * fz / D`, with fz = 1.1 gear pinion, 1.4 chain wheel, 1.7 V-pulley, 2.5 flat pulley. Allowed at x: `Frx = Fr2_row * a / (b + x)` when `radial_load_factors` exist, else `Fr2_row` (mid-shaft) with warning `fr_mid_shaft_only`. Require `Fre <= min(Frx, fr_max)`. | hard | H cat. §2.8 |
| Axial load | If an axial load is given: `Fa <= Fr_row / 5` when combined with a radial load. Ball-bearing sizes (catalogue note) allow no axial load. | hard | §2.8.1 |
| Peak torque | `peak_torque <= 2 * mn2` | hard | §1.4 B |
| Motor fit | gearmotor: `row.motor_frame` exists in `motors`; reducer+motor: `iec_frame` in `motor_interfaces(gear_size)` with the mounting's flange type (B5/B14) | hard | §2.6 |
| Motor support | `iec_size >= 180`: warning "можлива потреба в опорі двигуна на лапах" | soft | §1.4 D |
| Thermal | If `thermal_ratings` exist and stages <= 2: `P1 <= Pth * Fc(ambient, duty) * Fv(ventilation) * Fa(altitude)` (ISO 14179 tables stored in `config/selection.yml`). Missing data: warning `thermal_not_verified`. 3-stage units are skipped, as the catalogue allows. | hard when data exist | §2.4 |
| Critical application | Mounting position and n1 against the catalogue's critical-application table (V5/V1 with n1 > 1500, V3/V6): `B` -> warning "перевірити з техслужбою", `A` -> hard reject | mixed | §2.5 |
| Ambient | `< -5 or > 40 °C` -> warning (catalogue: call technical service) | soft | §1.6 |
| Speed sanity | `abs(row.n1 / row.i - row.n2) / row.n2 <= 3%`, else drop the row and log a data defect | hard (data) | DATA_SCHEMA gate 3 |
| ATEX | `atex` requested and `gear_size.atex_available` not true -> warning `atex_manual` (ATEX data are not in the standard catalogues; the ATEX block on the KP is filled manually) | soft | §6 |
| Worm irreversibility | VSF and the application is hoisting -> warning: no reliance on self-locking | soft | VSF §2.4.2 |

### 4.6 Step 5: smallest adequate size, then rank

1. Within each series, group the surviving candidates by `gear_size.size_rank`. Keep the **smallest size** that has at least one candidate. Also keep the next size up as an alternative.
2. Within a kept size, order the rows by `abs(n2 deviation)`, then by motor `p_kw` ascending.
3. Across series, order by: (a) the user's series preference order if given; (b) `mn2_nm` ascending (smallest adequate gearbox); (c) `abs(n2 deviation)` ascending; (d) `motor.p_kw` ascending; (e) `mass_kg` ascending when known; (f) designation string (a stable tiebreak).
4. Output at most 10 candidates. The first one is `recommended`.

Each candidate carries:

```
designation, series, size, kind, i, n1, n2, n2_deviation_pct,
motor {frame, poles, p_kw, line, ie_class}, m2_nm, mn2_nm, mn2_source,
fs_catalogue, fs_req, fs_app,
utilisation_gear_pct  = T2_req / mn2 * 100,
utilisation_motor_pct = T_load / M2_motor * 100,     # M2_motor = m2_nm in Path A
fr2_allowed_n, fr2_applied_n, mass_kg, src_pages [...], warnings [...], checks {name: pass|warn|fail}
```

Bands shown in the UI: gear utilisation `> 100%` cannot occur (filtered); `85-100%` is "впритул"; `< 50%` is "завеликий запас" (an advisory that a smaller series may fit).

5. Empty result: return `no_candidate` with the reason ranking (which check failed most often), plus the three nearest rejected rows with the failed check. Examples: "максимум серії SN 10250 Нм < потрібні 12000 Нм -> PBH".

### 4.7 Manual override (D4)

1. The manager types a designation, or picks series + size + i + motor from dropdowns.
2. `Selection::DesignationParser` parses it with `designation.json` from the active dataset into `{series, size, variant, i, motor_frame, mounting_position, options}`. Segments it cannot parse are kept verbatim, with warning `designation_unparsed`.
3. The engine runs the §4.5 checks in **verify mode** against the matching rating row (exact `i` match within 0.5%). Failures do not block: the item gets `verification_status = failed_overridden`, the manager must enter `override_reason_uk`, and the KP shows no "перевірено" mark for that item (KP_SPEC §4.6).
4. Overriding the recommended motor only (same gearbox) re-runs A4/Path-B-5 and the motor-fit check.

### 4.8 Determinism

The engine is a pure function of `(request, dataset_version, config/selection.yml digest)`. The Result stores all three, so any quote item can be re-run and diffed later.

---

## 5. Validation rules (physical sanity)

Request (`Selection::Request` validations; messages in Ukrainian):

| Field | Hard limits | Soft (warning) |
|---|---|---|
| T_load | 0 < T <= 120000 Nm | T > series max of the filtered set -> early message |
| P_load | 0 < P <= 90 kW (largest motor in the catalogues: 280M 4p 90 kW) | none |
| n2 | 0.1 <= n2 <= 1500 rpm and n2 < n1_nominal(poles) | n2 < 1 or n2 > 500: unusual |
| ratio | 1 <= i <= 2700 | none |
| T/P/n2 consistency | within 10% if all three are given | none |
| hours_per_day | 0 < h <= 24 | none |
| starts_per_hour | 0 <= s <= 100 | s > 30: check the motor's thermal starts limit |
| fa | 0 <= fa <= 10 | none |
| fs manual | 0.7 <= fs <= 3.0 | fs < 1.0 |
| tolerances | n2 tolerance 0-20%, ratio tolerance 0-10% | > 10% speed tolerance |
| radial load | Fr >= 0; D > 0 when an element is given; 0 <= x <= shaft length (from dimensions) | none |
| peak torque | >= T_load | none |
| ambient | -40..+60 °C | outside -5..+40 |
| altitude | 0..4000 m | > 1000 m |
| qty (quote item) | integer 1..999 | none |
| fx_eur_uah | 10.0000 .. 200.0000 when pricing is on | change > 5% vs the previous quote: confirm |
| unit_gross_uah (manual) | > 0 and divisible by 3 | none |

Data (import time, `lib/catalog_import`): every DATA_SCHEMA quality gate is re-checked. Rows failing gate 3 (`n2 ≈ n1/i` within 3%) or gate 4 (duplicate key) are rejected into the import report. Rows with implied efficiency outside 0.55-1.0 are imported with `extra_json.flag = "eta_out_of_range"` and excluded from selection unless an admin clears the flag. A dataset with zero ratings for a series listed in `catalog_series`, or with any size from the catalogue index missing, cannot be activated.

---

## 6. API contract sketch (for later CRM integration)

The owner of the schema is this project. The contract note will live in the vault at `projects/new_ax_crm/contracts/new_ax_crm-motovario-quote-calculator.md` (the dependent project holds it, per the modularity rule §4). The CRM-side adapter lives in `new_ax_crm`; nothing CRM-specific lives here beyond the generic `external_system`/`external_ref` fields.

- Base: `https://<host>/api/v1`, JSON only, UTF-8, `Accept: application/json`.
- Auth: `Authorization: Bearer <token>`. The token is generated in Admin, shown once, and stored as a SHA-256 digest. Scopes: `selection:read`, `quotes:write`, `quotes:read`. HTTPS only. Rails 8 `rate_limit` 60 req/min per client.
- Versioning: in the path. Within v1 only additive changes are allowed (new optional fields, new enum values announced in `/meta`). Removing or renaming a field, or changing its unit or meaning, requires `/api/v2`, with v1 kept at least 90 days. JSON Schemas are in `docs/api/v1/*.schema.json`, and request tests validate responses against them.
- Errors: `application/problem+json` (RFC 9457): `{type, title, status, detail, errors: [{field, code, message_uk}]}`.
- Money: `{amount_minor: 1225020, currency: "UAH"}`. Never floats.
- Idempotency: `POST /quotes` requires the header `Idempotency-Key`. A repeat with the same key and body returns the original 201 body; the same key with a different body returns 409 (vault `Патерн — Ідемпотентність та версіонування`).

| Method & path | Scope | Purpose |
|---|---|---|
| `GET /meta` | any | `{api_version, dataset_version, series:[...], enums:{load_class, mounting, ...}, units}` |
| `POST /selections` | selection:read | Body = §4.1 request. Returns `{dataset_version, fs_req_by_series, candidates:[§4.6], warnings, recommended_index}`. Stateless. |
| `POST /selections/verify` | selection:read | `{designation, request}` -> verify-mode result (§4.7) |
| `POST /quotes` | quotes:write | `{external_system, external_ref, customer{...}, contact{...}, terms{...}, items:[{qty, candidate_token | designation, request}], fx_eur_uah?}` -> 201 `{id, status:"draft", links}`. `candidate_token` is a signed, 24-hour token returned with each candidate, which freezes the selection result. |
| `POST /quotes/:id/issue` | quotes:write | Assigns the number, freezes snapshots, enqueues the PDF -> 202 |
| `GET /quotes/:id` | quotes:read | Full quote JSON incl. items, tech snapshot, totals (null when unpriced), `pdf_status` |
| `GET /quotes/:id/pdf` | quotes:read | 302 to a signed short-lived URL, or 409 while rendering |
| `GET /quotes?external_ref=...` | quotes:read | Lookup by CRM deal |

A later MCP surface (tools `gearmotor_select`, `gearmotor_quote_create`, named without any foreign-project prefix) wraps the same endpoints and is listed in this repo's `hub.yml`.

---

## 7. Testing strategy

Verification loop per the orchestration rule §3: every task below states its runnable check.

1. **Unit: Duty** (`test/selection/duty_test.rb`). Table-driven cases taken from the chart itself, e.g. class B, 8 h/day, 5 starts -> the chart's value, read and approved once (§9 R1). Includes hour bracket rounding, starts clamping and interpolation, and the error for > 100 starts.
2. **Unit: Engine with a fixture dataset.** A small hand-made dataset (`test/fixtures/catalog_mini/`), 30-60 rating rows copied verbatim from real catalogue pages with `src_page`. It covers both paths, mn2 matched vs derived, a radial-load rejection, a thermal rejection, a critical-application warning, and an empty result.
3. **Invariant tests over the real active dataset** (vault `Патерн — Мутаційні інваріант-тести від специфікації`): for 500 random valid requests, every returned candidate satisfies A4, A5, the radial check and `fs_app >= fs_req`. **Monotonicity:** increasing T_load never yields a smaller recommended mn2. Raising fs_req never yields a smaller one. Narrowing a series filter never adds candidates. **Negative mutations:** multiplying T_load by 10 must change the recommendation or return `no_candidate`, and the test must be red against a deliberately broken check (e.g. A5 disabled) before it is trusted. Assert the count of checked requests so it cannot pass empty.
4. **Golden cases from the four SEW samples** (`test/golden/sew_cases.yml`). The Motovario series mapping is **advisory**: SEW F (parallel shaft-mounted) maps to Motovario SN, with PBH above SN's range; SEW K (helical-bevel) maps to Motovario B, with PBH above B's range. Inputs: T_load = SEW output torque Ma, n2 = SEW n2, `fs_min` = SEW fB with `fs_override: true` (to reproduce the SEW margin), 4-pole, mounting from the sample.

| Case | SEW source | Inputs | Expected (assert properties, not one code) |
|---|---|---|---|
| G1 | 426313093 K97 DRN160M4 | T 1990 Nm, n2 53, fs 2.20, right_angle, foot, solid shaft 70 mm, M1 | B-series recommended; mn2 >= 4378 Nm; motor 11 kW 4p (one standard step either way allowed); n2 within ±5% |
| G2 | 424172597 FA87/G ATEX EDRN160M4 | T 1100 Nm, n2 95, fs 2.20, parallel, shaft_mounted hollow, Fr2 11400 N, atex | SN candidate; mn2 >= 2420; fr2_allowed >= 11400 or the radial check fails visibly; warning `atex_manual` present |
| G3 | 425961153 pos01 FA97/G DRN132S4 | T 2090, n2 25, fs 2.10, parallel, hollow | SN; mn2 >= 4389; motor 5.5 kW 4p |
| G4 | 425961153 pos03 FA87/G DRN132S4 | T 2040, n2 26, fs 1.45 | SN; mn2 >= 2958; the same or a smaller size than G3 |
| G5 | 425961153 pos02/04 ATEX variants | as G3/G4, atex, Fr2 37000 / 16000 | as G3/G4 + `atex_manual`; radial check applied |
| G6 | 423942292 pos02 FA127/G DRN225S4 | T 8890, n2 40, fs 1.35, parallel, hollow 100 mm | `T2_req = 12002 Nm > SN max 10250`: no SN candidate, the reason names the SN maximum, and the PBH candidate is recommended; motor 37 kW 4p |
| G7 | 423942292 pos01 KA127/T DRN225S4 | T 8640, n2 41, fs 1.50, right_angle, hollow + torque arm | T2_req 12960 <= B max 14000: B if a size has Mn2 >= 12960, else PBH; motor 37 kW |
| G8 | G1 entered as power | P 11 kW, n2 53 | T_load = 1982 Nm; same recommendation as G1 |

   Once the human-reviewed dataset is active, the exact recommended designation per case is pinned in `test/golden/approved.yml` (an approved-snapshot test). A dataset change that alters a pinned result fails CI until a person re-approves it with a reason.
5. **Pricing** (later task): `ceil_to_3` table (122500->122502, 122501->122502, 122502->122502, 1->3, 0->0), the gross anchor, totals equal the sum of lines, VAT = gross - net, a manual price not divisible by 3 is rejected.
6. **Import**: each quality gate has a red fixture (a duplicate key, n2 off by 5%, eta 0.4, a missing size) that blocks activation.
7. **KP**: request test renders the HTML preview. PDF test runs Grover on a fixture quote, then `pdftotext` asserts every KP_SPEC mandatory field label and value, the page count, `Сторінка N / M`, and **no price strings when unpriced**. A Playwright screenshot of page 1 is compared with an approved PNG at a tolerance (catches layout breaks such as the header band disappearing or a table overflowing).
8. **API**: request tests validate responses against the JSON Schemas; idempotency repeat (201 then same body) and conflict (409); auth (401 without a token, 403 on a wrong scope).
9. **System** (Capybara + Playwright): fill the selection form -> candidate table -> add to quote -> issue -> PDF link appears (Turbo Stream).

CI command: `bin/rails test && bin/rails test:system`. Local equivalent: `bin/ci`.

---

## 8. Repo layout

```
motovario-quote-calculator/
  app/ lib/ config/ db/ test/            # Rails 8 app (§2)
  bin/ci                                 # rubocop + tests
  data/raw/<SERIES>/                     # extractor output (read-only for the app; never edited by hand)
  data/overrides/<SERIES>/*.csv          # human corrections, same columns + reason + approved_by; applied after raw
  data/service_factor/generic_H.csv      # digitised chart if extractors cannot produce it (R1), reviewed
  sources/catalogs/  sources/sew-samples/
  tools/extract_<SERIES>.py              # extractors (exist)
  app/assets/fonts/montserrat/*.woff2    # OFL licence file alongside
  docs/ARCHITECTURE.md  docs/KP_SPEC.md  docs/DATA_SCHEMA.md  docs/api/v1/*.schema.json
  Dockerfile  compose.yml  hub.yml  .ruby-version (3.3.6)  CLAUDE.md (with the vault orchestration include)
```

---

## 9. Risks and unknowns

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | The service-factor table is a **chart** (H catalogue p.12: lines A/B/C over starts/h, four hour scales), not a text table, so extractors may not produce `service_factor.csv` | fs_req wrong means an undersized drive | Digitise into `data/service_factor/generic_H.csv` at points 5, 10, 20 ... 100 starts and 2/8/16/24 h, reviewed by a person against the page image (`verified_by`). Until then the UI forces a manual fs entry with the chart image shown. Per-series charts (VSF) are used when they exist |
| R2 | No electrical motor data (current, cos φ, efficiency, actual rpm): the M-series catalogue is not downloadable here | The KP motor block is thinner than the SEW samples | Those fields are nullable and hidden when empty (KP_SPEC). Import the M catalogue later into the same `catalog_motors` columns |
| R3 | Gearmotor-table semantics (M2 at motor rating, fs = Mn2/M2) differ from reducer tables (Mn2); size codes carry version prefixes (HA/IHA/CH...) | Wrong torque comparisons | Two `kind`s, canonical size codes from `designation.json`, matched vs derived Mn2 flagged (§4.4) |
| R4 | Designation formats are graphic pages; `designation.json` may be incomplete | Override parser cannot validate every code | Unparsed segments kept verbatim plus a warning; the manager confirms |
| R5 | ATEX data are not in the standard catalogues | ATEX quotes cannot be auto-verified | `atex_manual` warning; ATEX block entered by hand; the KP marks it "за даними виробника, підтверджується при замовленні" |
| R6 | Brand and trademark: KP "in Motovario style" issued by a reseller | Could read as a Motovario document | The seller is always the issuer (name and requisites in the header and footer). The Motovario logo is **off by default** (`brand_mark_enabled`), switched on only when the owner confirms dealer status. A trademark line is in the footer. Montserrat replaces the licensed Gotham font |
| R7 | Future price list structure unknown (per-code price vs base + adders) | Pricing rework | `price_list_entries.match_kind` supports both; the strategy interface is isolated |
| R8 | Extraction errors | Wrong selection | `src_page` everywhere and shown in the UI candidate row (links to the catalogue page); invariant tests; approved golden snapshots; overrides layer |
| R9 | Chromium in production (RAM, version drift) | PDF failures | Job concurrency 1, pinned puppeteer/Chromium versions, timeout 30 s, retry 2; Prawn fallback stays possible |
| R10 | Ruby 3.3.6 here vs 3.4.6 in the CRM | Minor | `.ruby-version 3.3.6` now, Gemfile `ruby ">= 3.3"`; bump to 3.4.x in the Dockerfile at deploy (no shared code with the CRM, so no coupling) |
| R11 | Hosting target not chosen | Deploy delay | Dockerfile + compose + `hub.yml` manifest; the platform choice is outside this repo |
| R12 | KP numbering may later be owned by the CRM | Duplicate numbers | `Kp::Numbering` per seller-profile prefix; the API accepts `number` from the caller when `external_system` is set (v1 optional field) |
| R13 | 60 Hz, brake motors, inverter duty, variators | Not selectable | Out of MVP; a brake flag only changes the designation and the KP text |
| R14 | PBH extraction not started yet (no `data/raw/PBH`) | Golden G6/G7 cannot pass yet | G6/G7 are marked `pending_data` until PBH is imported |

---

## 10. ADR log

**ADR-001: Rails 8 monolith with Hotwire.** Context: §1.1. Decision: Rails 8, Turbo, Stimulus, importmap, no SPA. Consequences: one stack with the CRM; heavier image than Sinatra; JS kept to small Stimulus controllers (unit toggles, tolerance slider).

**ADR-002: SQLite now, Postgres on trigger.** Context: read-mostly catalogue (~10^4-10^5 rows), < 10 users, owner weak in DevOps. Decision: SQLite with WAL, Solid Queue and Solid Cache on SQLite, a daily `.backup` copy. Switch triggers: more than one app instance, more than 20 concurrent users, or a need for DB-level reporting. No SQLite-only SQL is allowed (portable migrations; money as integers; no JSON operators in queries; JSON columns used only for whole-document reads).

**ADR-003: PDF via Grover (HTML -> Chromium).** Context: §1.2. Decision: Grover, A4, `printBackground: true`, `preferCSSPageSize: true`, header and footer templates, images inlined as data URIs, fonts from local files, rendered in `RenderKpPdfJob`; the PDF is attached to the quote at issue and re-rendered only on a new revision. Consequences: Chromium in the image; layout iterated in the browser.

**ADR-004: Immutable, versioned catalogue datasets + quote snapshots.** Decision: each import creates a dataset; one is active. A quote pins `catalog_dataset_id`, and each item stores `tech_snapshot_json` and `selection_result_json` at add time (refreshed only on explicit "перерахувати"). Consequences: issued KPs never change; storage is duplicated (negligible).

**ADR-005: Money as integer minor units, gross-anchored UAH rounding.** Decision: §3.3. Consequences: exact sums; gross is always divisible by 3; net is derived.

**ADR-006: Selection engine as a pure PORO over a repository interface.** Decision: `Selection::Engine` gets a repository and config, returns value objects, no AR. Consequences: fast unit tests with in-memory fixtures; the same code serves UI, API and invariant tests.

**ADR-007: CRM integration through `/api/v1` only.** Decision: §6. No shared DB, no CRM gems or engines here. Consequences: integration is a separate task per D2, with a contract note in the vault first.

**ADR-008: Seller is the issuer; Motovario as product brand, style only.** Decision: R6. Brand colours sampled from the catalogue renders: blue `#00407C`, band grey `#D3D3D3`, accent red `#A03233` (the H-series mark); the paint colour of the product is RAL 5010.

**ADR-009: Service factor from a human-verified digitised chart; manual fs always possible.** Decision: R1 and §4.3. Consequences: the fs source is shown on each candidate (`series chart` / `generic chart` / `manual`).

**ADR-010: Golden cases are property assertions plus approved snapshots.** Decision: §7.4. SEW-to-Motovario mapping is advisory and never hard-coded in the engine.

---

## 11. Build plan (tasks, model tiers, done criteria)

Tiers follow the vault work-mode table (`Правила розробки.md`): Opus 5.5 for checkpoints and architectural judgment, Sonnet 5.5 for judgment-bearing implementation, Haiku 5.5 for fully specified mechanical steps. Deploy, secrets and API auth are critical zones and therefore never `economy`. Each Haiku step below is fully specified (files, result, check); if Haiku fails one twice, the step goes to Sonnet.

| # | Task | Tier | Depends | Done when (runnable check) |
|---|---|---|---|---|
| T0 | Architecture + KP spec (this doc) | Opus | none | Docs reviewed by the owner |
| T1 | `rails new` (Rails 8, sqlite3, importmap, no Tailwind), uk default locale, Rails auth generator, `bin/ci`, `CLAUDE.md` with the vault include, `.ruby-version` | Haiku | T0 | `bin/ci` green on an empty app; login page renders in Ukrainian |
| T2 | Catalogue migrations + models (§3.1), `Catalog::Repository`, importer core with the DATA_SCHEMA gates and an import report, `catalog:import` / `catalog:activate` | Sonnet | T1 | Import of `test/fixtures/catalog_mini` passes; each red gate fixture blocks activation |
| T3 | Per-series import adapters (H, HPL, VSF, B, SN; PBH when its data lands), following each series `notes.md`, canonical size codes from `designation.json` | Haiku (one series per step, spec = that series' notes.md + T2 adapter interface) | T2 + extractor output | `catalog:import data/raw` report shows row counts equal to the `notes.md` counts per series |
| T4 | Service-factor chart digitisation review + dataset activation review | Opus + owner | T3 | `generic_H.csv` has `verified_by`; import report reviewed; dataset activated |
| T5 | `Selection::Duty`, `Request`, `Engine`, checks, ranking (§4), `config/selection.yml` | Sonnet | T2 (fixture data suffices) | Unit + fixture tests green; invariant suite green and shown red against a disabled A5 |
| T6 | Golden case fixtures G1-G8 (`test/golden/sew_cases.yml`) per the §7.4 table | Haiku | T5 | Tests run; G6/G7 `pending_data` until PBH |
| T7 | Adversarial review of T5 against §4/§5 | Opus | T5, T6 | Findings list resolved or deferred in the session note |
| T8 | Selection UI: form (Turbo), candidate table with utilisation bars, warnings, src_page links, manual override + verify | Sonnet | T5 | System test: form -> candidates -> pick -> add to quote |
| T9 | Quote/QuoteItem models, snapshots, numbering, KP HTML template (KP_SPEC), Grover renderer + job, preview page | Sonnet | T8 | PDF test: all mandatory labels present, no prices when unpriced, page 1 screenshot approved |
| T10 | Seller profile settings screen, default terms, disclaimer texts, Montserrat fonts, design tokens | Haiku | T9 | Settings saved and reflected in the PDF test fixture |
| T11 | Pricing hook: `Money`, `UahRounding`, `NullStrategy`, manual price entry, fx field, price columns toggle; empty `price_lists` tables | Sonnet | T9 | Rounding table tests; a priced fixture KP shows totals divisible by 3 |
| T12 | API v1 (§6), token auth, JSON Schemas, idempotency | Sonnet | T9 | Request tests incl. schema validation, 401/403/409 |
| T13 | Contract note in the vault + API review + adversarial review of the MVP | Opus | T12 | Contract note exists; review passed |
| T14 | Dockerfile (Ruby 3.4.x, Node, Chromium), compose, `hub.yml`, backups | Sonnet (`optimal`, critical zone) | T12 | Container boots, `/up` 200, PDF renders inside the container |
| T15 | Later, separate task: price list import + `PriceListStrategy` | Sonnet | price list file from owner | Price list fixture -> priced KP |
| T16 | Later, separate task in `new_ax_crm`: CRM adapter calling `/api/v1` | Sonnet (in the CRM repo) | T13 | Per CRM session rules |

Parallelism: T3 (per series) runs alongside T5 (which uses fixture data). T8 and T12 both depend on T5 and T9 and touch disjoint files, so they can run concurrently.

---

## 12. Amendment 2026-10-28 — ADR-011: prototype first, CRM-compatible target

**Context.** Rubygems is blocked in the build sandbox (proxy 403), so Rails cannot be installed or tested there; npm/pip are reachable. The owner's CRM (`new_ax_crm`) runs **Rails 7.2.3, Ruby 3.4.6**, Prawn 2.5, Grover 1.2.10, Turbo/Stimulus (checked in its Gemfile.lock). §1 above assumed Rails 8 — superseded.

**Decision (owner, 2026-10-28).** (1) Data first: all six catalogues go to CSV + images (done by extractors). (2) One complete, verifiable prototype for the **VSF worm (NMRV-type)** series as a single self-contained HTML calculator with product images, a selection engine and a printable KP in Motovario style. (3) The whole project stays designed for the CRM: target **Rails 7.2 / Ruby 3.4** (not 8), the selection rules and KP spec in this folder are the contract, and the prototype's engine is written as small pure functions with the same inputs/outputs as `Selection::Request/Engine` (§4) so the later Rails port is a transcription, tested against the same golden cases.

**Consequences.** T1–T3 (Rails scaffold/import) are deferred until rubygems is reachable or the owner builds locally; use `rails _7.2.3_ new`, not Rails 8 generators (e.g. Rails 8 auth generator and Solid* defaults do not apply; CRM uses solid_queue already). Data loading for the prototype: `tools/build_prototype_data.py` turns `data/raw/VSF/*` into one JSON consumed by `prototype/vsf/index.html`.
