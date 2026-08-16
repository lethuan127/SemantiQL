---
type: Tasks
title: Order and limit a request — tasks
description: 6 tasks, 2 parallel, validation before compilation before tests before docs.
resource: specs/005-order-and-limit/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:16:47+07:00' }
sources:
  - id: plan
    resource: /005-order-and-limit/plan.md
    title: The approach and impact map these tasks derive from
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T23:16:47+07:00', checkpoint: 3,
      basis: '6 tasks in dependency order; 1 [P] group of 2 checked disjoint by file path (docs/09-data-modeling.md vs AGENTS.md); every task carries a runnable verification' }
status: stable
---

Derived from the plan approved at checkpoint 2.[^plan]

# Phase 1 — validation

- [x] **T1.** Add `order`, `limit`, `offset` to `_SELECT_ARGS`; add `OrderKey` and the three
  `ValidRequest` fields; add `_ordering` (target must match a projection's entity or alias;
  `desc` and `nulls_first` read; every other argument refused) and `_row_count` (non-negative
  integer literal only).
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** —
  - **Verification:** `ORDER BY revenue DESC LIMIT 5` validates; `ORDER BY 1`, `ORDER BY
    SUM(amount)`, `ORDER BY region` (unprojected), `LIMIT 1+1`, `LIMIT -1` all refuse.
  - **Constitution check:** N2 — an unread ordering argument must refuse.

# Phase 2 — compilation

- [x] **T2.** Attach `order_by`, `limit` and `offset` in `compile_request`, ordering by the
  projection's output name.
  - **Files:** `src/semantiql/engine/compile.py`
  - **Depends on:** T1
  - **Verification:** `uv run semantiql "SELECT revenue, channel FROM orders ORDER BY revenue
    DESC LIMIT 2"` returns web then partner.
  - **Constitution check:** N4 — no dialect branching.

# Phase 3 — tests

- [x] **T3.** Refusal cases: ordinal, aggregate, unprojected name, `LIMIT 1+1`, `LIMIT -1`,
  `WITH FILL`.
  - **Files:** `tests/test_validation_refuses.py`
  - **Depends on:** T1
  - **Verification:** `uv run pytest tests/test_validation_refuses.py` green.
  - **Constitution check:** N1 — through `run` with `ExplodingAdapter`.

- [x] **T4.** Replace the transpile tripwire with a real cross-dialect assertion; add
  rendering cases for `DESC`, `NULLS FIRST`, `LIMIT`, `OFFSET`; add the ranked end-to-end
  answer and `LIMIT 1`.
  - **Files:** `tests/test_compile.py`, `tests/test_example_end_to_end.py`
  - **Depends on:** T2
  - **Verification:** `uv run pytest tests/` green; the new transpile test fails if
    `sqlglot.transpile` is removed from `compile_request`.
  - **Constitution check:** N4 — this is the assertion that makes the claim testable.

# Phase 4 — reconcile the derived copies

- [x] **T5. [P]** Coverage map: A.2 rows for `ORDER BY`, `LIMIT`, `OFFSET`; section 8's
  ordering bullet; the null placement rule.
  - **Files:** `docs/09-data-modeling.md`
  - **Depends on:** T2
  - **Verification:** no statement contradicts a test.
  - **Constitution check:** trust-boundary artifact.

- [x] **T6. [P]** Agent brief: `ORDER BY` and `LIMIT` leave the refused list.
  - **Files:** `AGENTS.md`
  - **Depends on:** T2
  - **Verification:** `grep -n "ORDER BY" AGENTS.md` describes support.
  - **Constitution check:** governance.

T5 and T6 are `[P]`: disjoint files.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh`; report output verbatim.
- [x] **TV. Validation pass** — walk `validation.md`.

[^plan]: The impact map recorded at checkpoint 2.
