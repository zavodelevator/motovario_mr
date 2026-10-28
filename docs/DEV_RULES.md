# Development rules — Motovario Quote Calculator

Owner decision 2026-10-28. These rules apply to this repo only and narrow the vault work-modes
(`vault/Розробка/Правила розробки.md`). Where they are silent, the vault orchestration rule applies.

## Model routing

| Work | Model |
|---|---|
| **Implementation** (writing/changing app code, engine, templates, tests) | **Sonnet 5.5** |
| **Everything else**: recon, search, docs, notes, session notes, refactors by pattern, fixtures, formatting, running checks, reports | **Haiku 5.5** |
| **Design of descriptions, data processing, table building** (spec text, catalogue-to-CSV/JSON pipelines, table shaping, translations of labels) | **DeepSeek via connector** — *when a connector is connected*; otherwise Haiku |
| Opus | Not used by default. Only on explicit owner request (e.g. an adversarial review). |

Status of the DeepSeek connector: **not connected in this workspace** (checked 2026-10-28: not among installed connectors, not in the registry). Until it is connected, its work runs on Haiku. When it appears, add its tool names here.

## Hard rules (kept from the vault)

1. **Executors make no architectural decisions.** Haiku/DeepSeek return the question to the planner (the main session).
2. **Every Haiku/DeepSeek step is fully specified:** files to touch, expected result, runnable check. No spec, no hand-off.
3. **Escalation:** the same step fails twice on Haiku/DeepSeek -> it goes to Sonnet.
4. **Critical zones always get Sonnet at minimum, never Haiku-only:** deploy, secrets/tokens, API auth, anything touching customer data or prices.
5. **Verification loop is mandatory for implementation:** tests/screenshots shown as evidence before "done".
6. **No invented catalogue values.** Every data row carries `src_page`; missing = hidden in the KP.

## DeepSeek data-privacy rule

DeepSeek is an external service. Send it **only public catalogue material** (Motovario catalogue text/tables, public specs). **Never** send: customer names/requisites, quotes, prices, price lists, margins, CRM data, tokens, or the owner's SEW samples. Strip such fields before any call.

## Reporting

The final report of each task states which models did the work.
