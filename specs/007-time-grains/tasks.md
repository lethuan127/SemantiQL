---
type: Tasks
title: Ask for a date dimension at a coarser grain — tasks
description: 5 tasks, 2 parallel, validation before compilation before tests before docs.
resource: specs/007-time-grains/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:36:49+07:00' }
sources:
  - id: plan
    resource: /007-time-grains/plan.md
    title: The approach and impact map these tasks derive from
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T23:36:49+07:00', checkpoint: 3,
      basis: '5 tasks in dependency order; 1 [P] group of 2 checked disjoint by file path (docs/09-data-modeling.md vs AGENTS.md); every task carries a runnable verification' }
status: stable
---

Derived from the plan approved at checkpoint 2.[^plan]

# Phase 1 — validation

- [x] **T1.** Add `grain` to `Projection`, the closed grain vocabulary, and `_TRUNC_ARGS`.
  Extend `_projections` with the `TimestampTrunc` shape, the date-type check, the default
  output name, and a dedicated refusal for the extract forms.
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** —
  - **Verification:** each of the five grains validates; `MONTH(order_date)` refuses naming
    `DATE_TRUNC`; `DATE_TRUNC('month', channel)` refuses as not a date.
  - **Constitution check:** N2 — the extract forms must not be translated into a truncation.

# Phase 2 — compilation

- [x] **T2.** Build the truncation and repeat it in the `GROUP BY`; the grouping loop reads the
  dimension projections rather than `request.dimensions`.
  - **Files:** `src/semantiql/engine/compile.py`
  - **Depends on:** T1
  - **Verification:** `uv run semantiql "SELECT revenue, DATE_TRUNC('month', order_date) FROM
    orders"` returns two rows.
  - **Constitution check:** N4 — no dialect branching.

# Phase 3 — tests

- [x] **T3.** Refusals, rendering, the extended cross-dialect assertion, and the hand-computed
  monthly totals.
  - **Files:** `tests/test_validation_refuses.py`, `tests/test_compile.py`,
    `tests/test_example_end_to_end.py`
  - **Depends on:** T2
  - **Verification:** `uv run pytest tests/` green.
  - **Constitution check:** N1, N2.

# Phase 4 — reconcile the derived copies

- [x] **T4. [P]** `docs/09-data-modeling.md`: a grains subsection, A.5's date row, section 8's
  bullet, and the `MONTH()` hazard.
  - **Files:** `docs/09-data-modeling.md`
  - **Depends on:** T2
  - **Verification:** no statement contradicts a test.
  - **Constitution check:** trust-boundary artifact.

- [x] **T5. [P]** `AGENTS.md`: the supported-construct summary gains grains.
  - **Files:** `AGENTS.md`
  - **Depends on:** T2
  - **Verification:** the summary matches the coverage map.
  - **Constitution check:** governance.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh`; report output verbatim.
- [x] **TV. Validation pass** — walk `validation.md`.

[^plan]: The impact map recorded at checkpoint 2.
