# NMRV intermediate model: layers, CalcHost contract, quote JSON, CRM mapping

Status: intermediate model, 2026-10-28. Output: `prototype/nmrv/index.html` (one self-contained file, NMRV / NMRV-P only). Built by `python3 -I tools/build_nmrv.py`; `prototype/vsf` is untouched.
Target: a drop-in calculator for the owner's second company inside `new_ax_crm` (Rails 7.2, Stimulus/Turbo, Bootstrap 5, Pundit, UAH). No real prices or customer data are in the repo.

## 1. Source layers (`prototype/nmrv/src`)

| Layer | File | Rules |
|---|---|---|
| Data | `data.json` (built from `data/raw/VSF`, NMRV / NMRV-P gearmotor rows only, every row has `pg` = catalogue page) | Read-only. Reducer Mn2 is joined at build time (`mn2_tab`) so no NRV rows are shipped. |
| Engine | `engine.js` (UMD, node + browser) | Pure: selection, simple mode, **pricing**, **quote JSON** (`buildQuote`, `partiesFromQuote`, `quoteToRecord`). No DOM, no storage, no host calls. Port = transcription to Ruby, same golden tests. |
| KP template | `kp-template.js` + `kp.css` | Pure HTML-string rendering of the KP (`NmrvKP.create(deps).build({P, items, pricing})`). Restyle/relabel here only. |
| UI | `app.js` | Forms, tables, saved list, 3D dialog. Talks to the outside world ONLY through `CalcHost` (top of the file). |
| 3D | `model3d.js` + `vendor/` | Concept model from catalogue dimensions; lazy-loaded. |

## 2. CalcHost (adapter, one object at the top of `app.js`)

Standalone default: `localStorage` (every access in try/catch) + `window.print`. To embed: replace this object with `fetch()` calls to `/api/v1`, or set `window.CalcHostOverride = {...}` before `app.js` runs (its methods replace the defaults; tested in `test/nmrv/host.test.py`).

| Method | Returns | Standalone default | Rails port |
|---|---|---|---|
| `getSeller()` | `{name, short_name, edrpou, ipn, address, phone, email, site, iban, bank, mfo, dealer_statement}` | last typed seller (localStorage) | the second organisation's profile |
| `getManager()` | `{name, position, phone, email, office_name, office_contacts}` | last typed manager | `current_user` |
| `getCustomerCandidates(q)` | `[{company:{code,name,edrpou,address}, person:{name,honorific,phone,email}}]` | customers of saved quotes | CRM Company + Person search |
| `getFxRate()` | number (UAH per EUR) or `null` | `null` | CRM / NBU rate |
| `getPrice(articleKey)` | `{purchase_eur, margin_pct?}` or `null` | **`null`** ("ціна за запитом") | price-list lookup |
| `saveQuote(quote)` | `Promise<{id}>` | localStorage upsert | `POST/PATCH /api/v1/quotes` |
| `loadQuotes()` | `Promise<quote[]>`, newest first | localStorage | `GET /api/v1/quotes` |
| `deleteQuote(id)` | `Promise<void>` | localStorage | `DELETE` |
| `exportPdf(quote)` | `Promise<void>` | `window.print()` | server PDF (Grover) |
| `rememberProfile(p)` | optional, standalone only | stores seller + manager | omit |

Getters are synchronous (the host page already has the data: Rails view locals / Stimulus values); only I/O methods are async. `articleKey` format: `series|size|i<ratio>|single|comb|frame/poles/kW` (see `NmrvEngine.articleKey`).

## 3. Pricing (engine, ARCHITECTURE §3.3)

`unit_gross_uah = ceil_to_3( ceil( purchase_eur × (1 + margin) × fx × 1.20 ) )`, net back-calculated in kopecks, line = unit × qty (stays divisible by 3 UAH). The quote is **priced only if fx > 0 and every position has a price**; otherwise the price column, totals and the fx clause are hidden and the KP prints "Ціни надаються за окремим запитом." Tests use a fake fixture inside the tests only (`pricing.test.js`, `host.test.py`).

## 4. Quote JSON (`schema: "motovario_nmrv_quote/1"`)

```
{ schema, id, status:"draft", created_at, updated_at, engine_version,
  number|null, draft:bool, date,
  seller{name,short_name,edrpou,ipn,address,phone,email,site,iban,bank,mfo,dealer_statement,brand_mark},
  customer{code,name,edrpou,address,request_date}, contact{name,honorific,phone,email},
  manager{name,position,phone,email,office_name,office_contacts},
  terms{payment_terms,incoterms,delivery_place,delivery_method,lead_time,lead_cond,warranty,validity_days,unpriced_note},
  currency:"UAH", vat_pct:20, fx_eur_uah|null, priced:bool,
  items:[{pos, qty, article_key, designation, request{...selection form}, candidate{...engine candidate, incl. src_pages},
          tech{...techSnapshot}, override, reason, status, customer_ref, terminal_box, options, hs_code,
          price|null {unit_gross_uah, unit_net_kop, unit_vat_kop, line_gross_kop}}],
  totals|null { gross_uah, vat_uah, net_uah } }
```
Money is UAH in whole units for gross/totals and integer kopecks for net/VAT parts (API rule: never floats for the real API: the Rails side should send `{amount_minor, currency}`; `quoteToRecord` already works from kopeck values).

## 5. Mapping to the CRM

`NmrvEngine.quoteToRecord(quote)` returns the `CalculationRecord` attributes:

| CalculationRecord | Value |
|---|---|
| `user` | `current_user` (set by Rails, not in JSON) |
| `deal_id` | set by the Rails controller from the page context (not in JSON) |
| `calc_type` | `"motovario_nmrv"` (add to `CalculationRecord::CALC_TYPES`) |
| `description` | `КП <number|ЧЕРНЕТКА> · <customer> · <designations…>` |
| `params` | inputs needed to recompute: `schema, date, fx_eur_uah, terms, customer, contact, manager, seller, items[{article_key, qty, request, override, reason, customer_ref, terminal_box, options, hs_code}]` |
| `result_data` | frozen result: `schema, engine_version, priced, totals, items[{pos, designation, candidate, tech, status, price}]` |
| `price` | `totals.gross_uah` (UAH incl. VAT) or `null` when unpriced |

Party blocks map to CRM models (field names on the Rails side to be confirmed by the owner; this repo does not invent them):
`customer` -> `Company` (name, ЄДРПОУ, address, code); `contact` -> `Person` (name, honorific, phones/emails JSONB); `manager` -> `User`; `seller` -> the second organisation's settings (`AppSetting`); `Deal` links the record through `deal_id`.
Per the CRM rule, every calculator also needs a `save` action; here that is `CalcHost.saveQuote` -> `POST /api/v1/quotes` -> `CalculationRecord.create!`.

## 6. Known gaps

- Amount in words (KP_SPEC §3.3) is not implemented.
- `getCustomerCandidates` has no async search; for large CRMs filter server-side and refill the picker.
- `status` is always `draft` (no issue/freeze workflow yet).
