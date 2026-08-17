---
type: Validation
title: Model directory — validation
description: Acceptance criteria traced to FR-1..FR-12, all met and all machine-checked — unusually for this project, nothing here needs a human to confirm.
resource: specs/015-model-directory/validation.md
tags: [sdd, validation, knowledge, mcp]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T04:45:00+07:00' }
status: stable
---

# Results — walked 2026-08-18

Every AC met, and **every one by the gate** — no manual step, because nothing here depends on an
application this repository cannot drive.

| AC | FR | Evidence |
|---|---|---|
| AC-1 | 1 | `-m examples/warehouse` loads; every existing single-file test unchanged |
| AC-2 | 2 | subdirectories contribute, sorted order |
| AC-3 | 3 | two declarations refused naming both files; none refused |
| AC-4 | 4 | a table in two files refused, naming both files and the table |
| AC-5 | 5 | `orders.yml` in `sales/` sources `../../retail/orders.csv`; `tickets.yml` sources a CSV beside itself. Both resolve |
| AC-6 | 6 | every refusal message contains its filename, asserted |
| AC-7 | 7 | a file declaring nothing, and a typo'd `tabels:`, are both errors naming the file |
| AC-8 | 8 | two tables → index only, `detail` empty, `next_step` set; one table → full detail, no `next_step` |
| AC-9 | 9 | naming a table returns its entities, with the index still present |
| AC-10 | 10 | an unknown name is answered with the available ones |
| AC-11 | 11 | `sorted(tools) == ["describe_model", "query"]`, asserted; `table` is optional |
| AC-12 | 12 | the skill's two-step section; `docs/09` §2b with the four rules; `docs/10`, `docs/07`, README, AGENTS |

**Non-functional:** gate green both ways — 340 unit, 27 e2e, 58 pg, bundle build, 0 OKF errors.
`knowledge/loader.py` is still the only reader of the model (N3). No change to `engine/`.

## Amendments

**`knowledge/model.py` changed, and the plan had said it would not.** FR-8 promised the index
carries each table's description, and `Table` had no such field — only its dimensions, measures and
metrics did. Recorded in `plan.md` before the code was written. One optional field, no behaviour
change, still one validation pass. **Trust-boundary artifact**, so it is named rather than absorbed.

**Four existing server tests changed.** Entities moved from `tables` to `detail`, which is FR-8
doing what it says. They were updated to the new contract; none was loosened, and each now states
in its docstring which shape it is asserting and why.

## Judgement calls

1. **The one-table shortcut is a rule, not a threshold.** "Exactly one table returns full detail;
   two or more return the index." A size cut-off would have made the reply shape unpredictable and
   the tool untestable.
2. **A file that contributes nothing is an error** (OQ-1). The friendlier reading — ignore files
   without a recognised key — would also silently ignore a typo'd `tabels:`, which is a table
   someone believes they modelled. If the strictness proves annoying, an explicit opt-out marker is
   a smaller change than loosening the rule.
3. **`datasource` is declared once, not merged.** Requiring identical copies everywhere would mean
   thirty places to change one dialect, and two differing values would leave nothing authoritative.

## Carried forward

- **OQ-2 stands, unresolved and low-stakes.** `describe_model`'s output schema gained fields, so a
  client that cached the old one mid-conversation would see fields it did not expect. Local
  single-session servers make this unlikely to matter; stated rather than assumed.
- **`semantiql init` should write a directory**, now that one is the better shape for anything
  larger than a table or two. Its own spec.
