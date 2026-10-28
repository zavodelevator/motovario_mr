# KP (Комерційна пропозиція): Document Specification

Status: accepted for MVP. Date: 2026-10-27. Companion: `docs/ARCHITECTURE.md` (§3 data model, §4 selection, ADR-003/005/008).
The KP language is Ukrainian. Field labels below are the exact Ukrainian strings to print (they go into `config/locales/uk.yml` under `kp.*`).
Reference layouts: the four SEW-Eurodrive KPs in `sources/sew-samples/` (field list the owner is used to) and Motovario catalogue pages 1-5 (visual style).

## 1. Principles

1. **The seller issues the document.** The seller's name, requisites and contact person appear on every page. Motovario is the product brand. Its logo is printed only when `seller_profile.brand_mark_enabled` is true (default false, ADR-008).
2. **Frozen content.** The KP renders only from `quotes`, `quote_items.tech_snapshot_json` and `quotes.seller_snapshot_json`. It never reads live catalogue rows, so a re-import or a settings change cannot alter an issued KP.
3. **No empty rows.** A technical field with a null value is omitted, not printed as "-". A price column disappears entirely when the quote is unpriced.
4. **Prices are UAH including 20% VAT**, rounded per the CRM rule (ARCHITECTURE §3.3). Until prices exist (owner decision D1), the KP is a technical-commercial offer without prices.

Source codes used in the tables:
**I** = manager input (form or API) · **C** = computed by the app · **K** = catalogue data (frozen into the snapshot) · **S** = configurable setting (seller profile or `config/selection.yml`), editable per quote where noted · **P** = pricing hook (present only when priced).

## 2. Page header (every page)

| Field | Label (uk) | Source | Required | Notes |
|---|---|---|---|---|
| Seller logo | none | S | yes | `seller_profile.logo`, top-left, max height 14 mm |
| Motovario mark | none | S | no | Only if `brand_mark_enabled`; top-right, max height 10 mm, with "a TECO Group company" kept as in the original artwork |
| Breadcrumb | e.g. `Motovario ∕ Мотор-редуктори ∕ Комерційна пропозиція` | C | yes | Small text above the band, mirrors the catalogue's "H Series ∕ Standard ∕ IEC" |
| Document title | `КОМЕРЦІЙНА ПРОПОЗИЦІЯ` | fixed | yes | In the grey band, blue caps |
| Number | `№` | C | yes | `MV-2026-0012`, plus `/2` from revision 2. Drafts print `ЧЕРНЕТКА` instead and a diagonal watermark |
| Date | `Дата` | I (default today) | yes | `dd.mm.yyyy` |
| Page | `Сторінка N / M` | C | yes | Printed once per page, in the footer (§5.3), by the Puppeteer `footerTemplate` |

## 3. Page 1: parties, greeting, summary, terms

### 3.1 Parties

| Field | Label (uk) | Source | Required | Notes |
|---|---|---|---|---|
| Customer code | `№ клієнта` | I | no | Customer number in the seller's system / CRM |
| Request date | `Дата запиту` | I (default = date) | yes | |
| Seller one-liner | none | S | yes | `ТОВ «…», адреса`, small grey line above the addressee (as SEW) |
| Customer legal name | none | I | yes | Addressee block, left column |
| Customer ЄДРПОУ | `ЄДРПОУ` | I | no | |
| Customer address | none | I | yes | Multi-line |
| Contact person | none | I | no | `Пан/Пані <ПІБ>`; the honorific is optional (`contact_honorific`) |
| Contact phone / email | none | I | no | |
| Manager (seller contact) | `Контактна особа` | C (current user) | yes | Right column: name, position, phone, email |
| Seller office block | none | S | no | Office name, general phone, general email (right column, under the manager) |

### 3.2 Greeting

`<Ім'я контактної особи>, дякуємо за інтерес до нашої продукції. Ми підготували пропозицію на основі Вашого запиту.`
Source: S (template text `kp.greeting`), with the name from I. Without a contact person it starts at `Дякуємо…`.

### 3.3 Summary table of positions

| Column | Label (uk) | Source | Shown |
|---|---|---|---|
| Position | `Поз.` | C | always (`01`, `02` …) |
| Quantity | `Кількість` | I | always (`1 шт`) |
| Description | `Опис` | C/K | always: type name (`Циліндричний мотор-редуктор`, `Конічно-циліндричний мотор-редуктор`, `Черв'ячний мотор-редуктор`, `Планетарний мотор-редуктор`, `Насадний мотор-редуктор`, `Паралельно-вальний / конічний редуктор`, or `… редуктор` for reducer-only) |
| Designation | `Позначення` | C (or I on override) | always, second line under the description |
| Customer item ref | `Ваш № товару` | I | only if any item has one |
| Unit price | `Ціна за од. з ПДВ, грн` | P | only when priced |
| Line total | `Сума з ПДВ, грн` | P | only when priced |

Totals block (only when priced):

| Line | Label (uk) | Source |
|---|---|---|
| Total gross | `Разом з ПДВ, грн` | P (sum of lines) |
| VAT included | `у т.ч. ПДВ 20 %, грн` | P (gross - net) |
| Net | `Разом без ПДВ, грн` | P |
| Amount in words | `Сума прописом` | C (gross, Ukrainian words, e.g. `сто двадцять дві тисячі п'ятсот дві гривні 00 копійок`) |

When unpriced, the table ends with the line `Ціни надаються за окремим запитом.` (S, `kp.unpriced_note`, editable per quote).

Number format: thousands separated by a narrow no-break space, comma decimal (`122 502,00`), as is standard in Ukrainian documents (the SEW samples use the German `122.502,00`; deliberately not copied).

### 3.4 Commercial terms (two-column label/value table)

| Field | Label (uk) | Source | Default (seller profile) |
|---|---|---|---|
| Payment terms | `Умови оплати` | S, editable per quote | `50 % попередня оплата, 50 % протягом 10 днів від дати повідомлення про готовність товару до відвантаження.` |
| Price basis / currency clause | `Ціни` | S + C | `Ціни вказано в гривнях з ПДВ 20 %, розраховано за курсом {fx} грн/EUR на {date}. У разі зміни курсу більш ніж на 3 % ціна може бути переглянута.` Shown only when priced; the fx rate and date come from the quote |
| Delivery basis | `Базис поставки` | S, editable | `DAP <місто>, Incoterms® 2020` (incoterms code + place) |
| Delivery method | `Спосіб доставки` | S, editable | `Транспортний перевізник` |
| Lead time | `Строк поставки` | I (default S) | `6–7 тижнів` |
| Lead-time condition | none | S | `Строк поставки відраховується з моменту отримання передоплати та повного технічного погодження.` |
| Warranty | `Гарантія` | S, editable | `12 місяців з дня відвантаження` |
| Validity | `Пропозиція дійсна до` | C = date + `validity_days` (S, default 30), editable | `dd.mm.yyyy` |

Under the terms: `Детальні технічні дані позицій наведено на наступних сторінках.` (fixed).

## 4. Per-position section (one block per item, starting on page 2)

### 4.1 Position bar

A full-width blue bar: `ПОЗ. 01` · quantity · type name · designation (bold) · unit price and line total on the right (when priced).

### 4.2 Image and notes row

| Element | Source | Rules |
|---|---|---|
| Product image | K (`catalog_images` kind `photo` or `render`, size-level if present, else series-level) | Left, 60 mm wide box, white background, never stretched. No image: the box is omitted and the data block takes the full width |
| Image note | fixed | `Колір і технічні характеристики можуть відрізнятися від показаних на зображенні. Технічна специфікація відповідає наведеним нижче даним.` |
| Verification mark | C | `✓ Підбір перевірено за каталогом Motovario` when `verification_status` = passed or warnings. If `failed_overridden`: `Позицію задано вручну; перевірку за каталогом не пройдено` plus the override reason, in the accent colour |

### 4.3 Selection basis box (`Вихідні дані підбору`)

A small grey box. It shows what the selection relied on and replaces SEW's generic "our calculation is based on your data" sentence with the actual data.

| Field | Label (uk) | Source |
|---|---|---|
| Load torque | `Момент навантаження, Нм` | I (or C from power) |
| Absorbed power | `Потужність навантаження, кВт` | I (if given) |
| Target speed / ratio | `Потрібна частота на виході, об/хв` / `Потрібне передавальне число` | I |
| Load class | `Клас навантаження` | I (`A – рівномірне`, `B – помірні поштовхи`, `C – сильні поштовхи`) |
| Duty | `Режим роботи` | I (`{h} год/добу, {s} пусків/год`) |
| Required fs | `Потрібний сервіс-фактор` | C, with its source (`за діаграмою каталогу` / `задано вручну`) |
| Applied radial load | `Радіальне навантаження на вихідний вал, Н` | I/C (if given) |
| Ambient | `Температура довкілля, °C` | I (only if not the default 25) |

### 4.4 Technical data block (`Технічні дані`), two columns

Left column = gear unit; right column = motor (as in SEW). Keys are the `tech_snapshot_json` keys.

**Left: Редуктор**

| Key | Label (uk) | Source | Shown when |
|---|---|---|---|
| `gear.series` | `Серія` | K (`H – циліндрична`, etc.) | always |
| `gear.size` | `Типорозмір` | K | always |
| `gear.stages` | `Кількість ступенів` | K | known |
| `gear.version` | `Виконання` | K/I (`на лапах`, `фланцеве`, `насадне з порожнистим валом`, `з моментним важелем`) | always |
| `gear.output_shaft` | `Вихідний вал` | K (`Ø70 × 140 мм, зі шпонкою` / `порожнистий Ø60 мм`) | known |
| `gear.mounting_position` | `Монтажне положення` | I (default B3/M1) | always |
| `gear.terminal_box_position` | `Положення клемної коробки` | I | given |
| `gear.i` | `Передавальне число i` | K (exact, 2 decimals) | always |
| `gear.n1_n2` | `Частота обертання вх./вих., об/хв` | K (`1400 / 53,3`) | always |
| `gear.m2` | `Крутний момент на виході M2, Нм` | K/C | always |
| `gear.mn2` | `Номінальний момент редуктора Mn2, Нм` | K/C | always |
| `gear.fs_catalogue` | `Сервіс-фактор (каталожний) fs` | K | gearmotor rows |
| `gear.fs_app` | `Сервіс-фактор застосування` | C (`Mn2 / Mнавант`) | always |
| `gear.utilisation` | `Використання за моментом, %` | C | always |
| `gear.fr2` | `Допустиме радіальне навантаження Fr2, Н` | K (at mid-shaft, or `Frx` at x) | known |
| `gear.lubricant` | `Мастило / кількість, л` | K (`синтетичне …, 1,6 л` / `заправлено мастилом на весь термін служби`) | known |
| `gear.paint` | `Покриття` | S (default `RAL 5010 (синій), епоксидно-поліефірне`) per the catalogue painting spec | always |
| `gear.thermal` | `Термічна потужність Pth, кВт` | K | known and checked |
| `gear.options` | `Опції` | I (backstop, reinforced seals, output flange, torque arm …) | given |

**Right: Двигун** (omitted entirely for reducer-only items; then `Двигун не входить у комплект поставки; фланець IEC {frame} {B5/B14}` is printed instead)

| Key | Label (uk) | Source | Shown when |
|---|---|---|---|
| `motor.type` | `Тип двигуна` | K (`TP – IE3`, `TH – IE2` …) | always |
| `motor.frame` | `Типорозмір IEC` | K (`160MA`) | always |
| `motor.poles` | `Кількість полюсів` | K | always |
| `motor.p_kw` | `Потужність, кВт` | K | always |
| `motor.n_rpm` | `Номінальна частота обертання, об/хв` | K | known (M catalogue) |
| `motor.voltage` | `Напруга, В / схема` | S rule: `230/400 Δ/Y` up to 3 kW, `400/690 Δ/Y` from 4 kW; editable | always |
| `motor.frequency` | `Частота мережі, Гц` | fixed `50` | always |
| `motor.ie_class` | `Клас енергоефективності` | K | always |
| `motor.ip` | `Ступінь захисту` | S default `IP55` (M-series standard) | always |
| `motor.insulation` | `Клас ізоляції` | S default `F` | always |
| `motor.duty` | `Режим роботи` | fixed `S1` | always |
| `motor.brake` | `Гальмо` | I | brake = true |
| `motor.i_n` | `Номінальний струм, А` | K | known (M catalogue) |
| `motor.cos_phi` | `cos φ` | K | known |
| `motor.eta` | `ККД, %` | K | known |
| `motor.flange` | `Фланець` | K (`B5 Ø300`) | known |

### 4.5 ATEX block (`Вибухозахист`), only when the item has `atex_json`

Manual input fields (I), because the standard catalogues do not carry ATEX data (ARCHITECTURE R5): `Директива` (default `2014/34/EU (ATEX)`), `Маркування редуктора, газ`, `Маркування редуктора, пил`, `Маркування двигуна`, `Сертифікат`, `Температурний клас`, `Температура довкілля, °C`. A fixed note follows: `Дані вибухозахисту наведено за інформацією виробника і підтверджуються при оформленні замовлення.`

### 4.6 Position footer row

| Field | Label (uk) | Source |
|---|---|---|
| Net mass | `Маса нетто, прибл.` | K (`catalog_weights`; reducer + motor if listed separately), `{m} кг/шт · {m×qty} кг/поз.` Omitted if unknown |
| HS code | `Код УКТ ЗЕД` | C from the S table in `config/selection.yml`: gearmotor with motor ≤ 7.5 kW -> `8501 52 20 00`, > 7.5 kW and ≤ 37 kW -> `8501 52 30 00` (both match the SEW samples), > 37 kW -> owner to confirm; reducer only -> owner to confirm (`8483 40`); editable per item |
| Catalogue reference | `Джерело даних` | K: `Каталог Motovario {series} ({edition}), с. {printed pages}` |

### 4.7 Drawings appendix (`Габаритні креслення`)

One section per position that has a `drawing_image_id`, after all positions: the catalogue dimensional drawing (K, `catalog_images` kind `drawing`) at full content width, and below it a table with the key dimension values for the selected size and variant (K, `catalog_dimensions`; the symbols follow the catalogue). Note: `Розміри, мм. Креслення не є робочим; остаточні розміри за даними виробника.` This replaces SEW's drawing download links (there is no per-order CAD service).

## 5. Closing section and footer

### 5.1 Closing (last content page)

| Element | Source |
|---|---|
| `Загальна маса нетто, прибл. {sum} кг` | C (only if every item has a mass; otherwise omitted) |
| Totals repeated (as §3.3) | P, only when priced |
| `Сподіваємося, що пропозиція Вас зацікавить. Будемо раді відповісти на запитання.` | S (`kp.closing`) |
| `З повагою,` / manager name, position / seller short name | C/S |
| `Будь ласка, вказуйте номер пропозиції {number} у листуванні.` | S + C |

### 5.2 Legal and disclaimer lines (small type above the footer on the last page)

All are S (`seller_profile.disclaimer_texts_json`, defaults below). The owner can edit them; the app does not give legal advice and these defaults are assumptions to confirm.

1. `Підбір виконано на підставі наданих Вами даних про застосування. Просимо перевірити їх повноту і правильність; за зміни умов експлуатації підбір потребує перегляду.`
2. `Технічні дані наведено за технічними каталогами Motovario; виробник може змінювати характеристики без попереднього повідомлення. Зображення не є зобов'язальними.` (mirrors the catalogue's own sales-conditions note)
3. `Ця комерційна пропозиція не є публічною офертою.`
4. `Motovario® є зареєстрованою торговельною маркою Motovario S.p.A. (TECO Group).`
5. `dealer_statement_uk` (only if set, e.g. `ТОВ «…» є офіційним дистриб'ютором Motovario в Україні.`; the app never adds this by default)

### 5.3 Footer (every page)

A thin blue rule, then three small columns: (1) legal name, ЄДРПОУ, ІПН / VAT status; (2) address, phone, email, website; (3) IBAN, bank, МФО. Right edge: `№ {number} · Сторінка N / M`. All S, frozen into `seller_snapshot_json` at issue.

## 6. Field classification summary

| Class | Fields |
|---|---|
| **Inputs (I)** | date, request date, customer block, contact person, customer code, per item: qty, selection inputs (§4.3), mounting position, terminal box, options, brake, ATEX data, customer item ref, lead time (prefilled), override designation + reason, fx rate (when priced), manual price (when priced) |
| **Computed (C)** | number + revision, page numbers, valid-until, type name, designation, fs required/applied, utilisation, totals, VAT, amount in words, HS code (overridable), total mass, verification mark, breadcrumb |
| **Catalogue (K)** | everything in §4.4 marked K, images, drawings, dimensions, masses, catalogue references |
| **Configurable (S)** | seller requisites, logo, `brand_mark_enabled`, dealer statement, number prefix, validity days (30), payment terms, incoterms + place, delivery method, warranty, lead-time default and condition, greeting, closing, unpriced note, disclaimers, voltage rule, IP/insulation defaults, paint text, HS-code table, VAT rate (20 %) |
| **Pricing hook (P)** | unit price, line total, totals, price clause; all absent when `quote.priced?` is false |

## 7. Layout and visual style

Format A4 portrait. Margins: top 30 mm (the header band lives in the margin through the Puppeteer `headerTemplate`), bottom 22 mm (footer), left and right 15 mm. Baseline grid 4 mm.

### 7.1 Design tokens (shared by screen and PDF, `tokens.css`)

Sampled from the rendered catalogue pages (`sources/catalogs/H_helical.pdf` p.1 and p.5):

| Token | Value | Use |
|---|---|---|
| `--mv-blue` | `#00407C` | Section bars, table header fill, title text, position bar, rules |
| `--mv-blue-tint` | `#E4EAF1` | Zebra rows, selection-basis box background |
| `--mv-blue-mid` | `#A5BCD1` | Utilisation bar track, secondary rules |
| `--mv-grey-band` | `#D3D3D3` | Page header band (behind the title) |
| `--mv-grey-text` | `#5F6670` | Labels, breadcrumb, footer text |
| `--mv-text` | `#1E2328` | Body text |
| `--mv-red` | `#A03233` | Accent only: warnings, override notice, series badge for H. Never for prices |
| `--mv-white` | `#FFFFFF` | Page and bar text |

### 7.2 Typography

Montserrat (OFL, self-hosted woff2) as the substitute for the catalogue's Gotham. Title: Light 300, 20 pt, uppercase, letter-spacing 0.02 em, `--mv-blue`. Section bar text: SemiBold 600, 9 pt, uppercase, white. Body: Regular 400, 8.5 pt, line height 1.35. Labels: Regular 400, 7.5 pt, `--mv-grey-text`. Values and numbers: Medium 500 with `font-variant-numeric: tabular-nums`. Designation: Bold 700, 10 pt. Footer: 6.5 pt.

### 7.3 Components

- **Header band** (every page): a full-bleed `--mv-grey-band` strip, 11 mm high. The title is left in `--mv-blue`. On the right, a `--mv-blue` tab (like the catalogue's "TECHNICAL CATALOGUE" tab) with white text `№ {number} · {date}`. The breadcrumb sits 3 mm above the band; the logos sit above the breadcrumb line.
- **Section bars**: a `--mv-blue` fill, white caps text, 6 mm high, left-aligned, width fitted to the text plus 6 mm padding (as the catalogue's "5. PERFORMANCES" bars). Sections: `ПОЗИЦІЇ`, `УМОВИ`, `ТЕХНІЧНІ ДАНІ`, `ГАБАРИТНІ КРЕСЛЕННЯ`.
- **Tables**: header row `--mv-blue` with white 7.5 pt text; body rows alternate white / `--mv-blue-tint`; 0.3 pt `--mv-blue-mid` horizontal rules; numbers right-aligned.
- **Position bar**: the full content width, `--mv-blue`, 8 mm, white text; `break-after: avoid`.
- **Two-column technical block**: CSS grid `1fr 1fr`, 6 mm gutter. Each column is a label/value list with 0.3 pt dotted rules. Column titles `РЕДУКТОР` / `ДВИГУН` in a 5 mm `--mv-blue-tint` strip with blue text. `break-inside: avoid` per row group; a position may split between the technical block and the footer row, never inside a row.
- **Utilisation indicator**: a thin bar (40 mm × 2 mm) in `--mv-blue` on a `--mv-blue-mid` track next to the percentage; red if > 95 %.
- **Product image**: left of the selection-basis box on the position's first page, 60 × 45 mm box, `object-fit: contain`. Drawings go in the appendix at full width (max height 150 mm).
- **Page 1 order**: header -> parties (2 columns) -> greeting -> `ПОЗИЦІЇ` bar + summary table (+ totals) -> `УМОВИ` bar + terms table. Positions start on page 2 (`break-before: page`). Each subsequent position starts on a new page if fewer than 90 mm remain.

### 7.4 Rendering rules

Grover options: `format: 'A4'`, `printBackground: true`, `preferCSSPageSize: true`, `displayHeaderFooter: true`, `margin` as §7, `timeout: 30000`. All images are data URIs, downscaled at import to ≤ 1600 px on the long side. Fonts are loaded from local files with `font-display: block`. Nothing is fetched from the network at render time. The preview page `/quotes/:id/preview` uses the same template with an on-screen page frame.

## 8. Deliberately left out (SEW-specific blocks)

| SEW block | Why it is out | Replacement |
|---|---|---|
| `Експлуат. коеф. SEW-FB` and `Ма макс` | SEW's definition (fB = Ma max / Ma) | Motovario `fs` (catalogue), `Mn2`, application fs and utilisation % |
| `Схема підключення R13 / 680010306`, `Номер документації А`, `Креслення отворів під різьб. пр.` | SEW internal document and wiring-diagram numbers | None |
| `Розташ. клем. кор. 0 (R) / каб. ввід`, `Розміщ. головн. табл.`, `Зав. табличка: Англійська`, `Інст. по експлуат. мова/кіл-ть`, `Перелік деталей` | SEW configurator options with no Motovario catalogue equivalent | Terminal box position as an optional input only |
| `Символ СЕ: Так`, `Україна: Так`, `Знак UkrSEPRO: Так` | Certification marks that the reseller cannot assert per order from catalogue data (UkrSEPRO is also obsolete) | None; if needed, a configurable conformity line can be added to the disclaimers |
| `Кожух`, `Сапун`, `Варіант вентиляції`, `Лакофарб. покр. RAL7031` | SEW-specific options and colour | Motovario paint `RAL 5010` line; breather/plug info only if the catalogue lubrication data has it |
| `Пусковий струм / ном. струм`, `TE/TA-час`, `Ступінь викор. по кл. ізол.`, `Діапазон напруги` | Motor electrical data not available (no M catalogue, ARCHITECTURE R2) | Added later via the nullable `catalog_motors` columns |
| "Перегляд трансакцій" online portal paragraph and `docu.sew-eurodrive.com` drawing links | SEW services | Drawings appendix (§4.7) |
| EUR net prices with VAT added on top | Owner decision D3 | UAH gross, rounded up to a multiple of 3, VAT included |
| Payment in UAH at the interbank EUR rate on the day before the invoice | SEW's currency mechanism | A fixed fx rate per quote plus a configurable review clause (§3.4) |

## 9. Assumptions (decided, not asked)

1. Numbering `MV-YYYY-NNNN` per seller profile, yearly sequence, assigned at issue. Revisions append `/N`.
2. Validity 30 days by default (the SEW samples use 30).
3. Warranty 12 months from shipment, payment 50/50, and DAP Incoterms 2020 as defaults (taken from the SEW samples, which the owner accepts as a customer). All are editable.
4. The motor voltage default rule (230/400 V up to 3 kW, 400/690 V from 4 kW) is the common IEC convention. It is editable per item until the M catalogue confirms it.
5. Amount in words is printed when priced (common in Ukrainian commercial documents, not legally required for a KP).
6. The "не є публічною офертою" line and the trademark line are defaults for the owner to confirm. They are not legal advice.
7. A KP with an overridden, unverified position may still be issued; the position carries the visible override notice (§4.2).

## Prototype notes (VSF prototype, 2026-10-28)

Implemented in `prototype/vsf/` (single HTML, `tools/build_prototype_data.py`). Deviations where the data contradicts or does not carry the spec:
- **Motor electrical data** (rpm, current, cos φ, efficiency) and **motor mass** are absent from the VSF catalogue: those rows are hidden. The position footer prints `Маса редуктора нетто, прибл.` (gearbox only, without motor and oil); the closing total mass is printed only when all items are reducers.
- **Reducer-only (NRV/NRV-P)** has an input shaft, not an IEC flange: the right column prints `Двигун не входить у комплект поставки; вхідний вал` plus a motor power hint (no flange line, unlike §4.4).
- **Product photos**: the catalogue holds series-level renders only (montage pages 18/19, cropped per family); no per-size photos. Motovario logo graphic is not in the data; the toggle prints a plain text mark.
- **Service factor** is the digitised nomogram (±0.03); hours use the next tabulated column (2/8/16/24), starts are interpolated, result rounded up to 0.05.
- **Pagination** is fixed: one A4 `.page` per block with a computed `Сторінка N / M` (no running Puppeteer footer needed); positions never split.
- `Ціна`/price columns are absent because `priceHook()` returns null; motor `Напруга`, `IP55`, insulation `F`, `S1`, paint `RAL 5010` are the §4.4 defaults (S), not catalogue values for VSF.
- ATEX block, Pth, terminal-box position (manual field only) are not implemented or not in the data.

## Concept 3D notes (2026-10-28, ADR 'concept-3d')

- `prototype/vsf/src/model3d.js`: `buildModelSpec(cand, motor, data, {mounting, version})` builds a JSON spec of primitives only from catalogue dimension tables (housing p52/p56, shaft bore, motors p66-67). The symbol -> geometry map is the header comment of that file. Missing dimension -> `{error:'no_dimensions'}` and the UI shows the catalogue photo. `specToThree` / `renderSpecToPng` / `createViewer` are the browser layer (three.js r160 vendored in `prototype/vsf/vendor/`, inlined lazily into `index.html`).
- KP position block: image slot = 1200x900 PNG of the model (fixed isometric camera, B3 reference orientation, white background); the catalogue photo stays as a small second image in the corner (fallback when no spec). Footnote under the image, verbatim: `Ілюстрація, концептуальна модель; розміри — за каталогом Motovario`. All numbers in the KP still come from catalogue data, never from the geometry.
- Not drawn / not supported: NMRV025 (drawing only), combined and pre-stage units, SW/ISW, motor frame 56, output-flange and torque-arm executions (tables not extracted), terminal box for motor frames 160-280 (p67 prints no Y/V). Style-only parameters (edge radii, fins, fan cover length, hub diameter) are listed in `spec.style`; used assumptions in `spec.assumptions`.
- `models/manifest.json` (generated by `tools/build_prototype_data.py`): one entry per generated part type, `source: parametric-from-catalogue`, `status: concept`, `src_pages`; replace entries with `status: official` when the client's CAD arrives.

## Simple mode (prototype, 2026-10-28)

- Two modes, toggle at the top (choice kept in `localStorage`, try/catch): **Простий** (default) and **Складний** (the full form, unchanged). Quote list, KP and 3D are shared.
- Simple input: motor kW + output rpm (extras under «Додатково»: poles, NMRV/NMRV-P, min fs = 1.0, qty). Engine: `selectSimple({p_kw,n2_rpm,poles?,family?,min_fs?,tol_pct?,limit?}, data)` in `engine.js`: gearmotor rows with motor power = typed kW (else the next catalogue power, with chips), n2 within ±5 % (±10 % only if fewer than 3 variants), fs = Mn2/M2 >= min_fs, up to 12 rows ordered by housing size, fs closest to the minimum, speed error.
- Table: Двигун об/хв (2800/1400/900 from poles), i, overall size Д×Ш×В mm (bbox of the concept 3D model in B3, motor included; hidden when no catalogue dimensions), fs badge (green >= 1.25, amber 1.0-1.25, red < 1.0), M2. Row click/Enter opens the detail panel (all KP technical data, source pages, 3D, «Додати до КП», «Перейти до складного підбору з цими даними»).
- Duty (class B, 8 h/day, 10 starts/h, load torque T = M2) is used only for the «застосування» fs line and is editable in the detail panel. If it fails, the KP item is added as a flagged position with an auto reason.
