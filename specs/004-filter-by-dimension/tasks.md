---
type: Tasks
title: Filter a request by its dimensions — tasks
description: 8 tasks, 2 parallel, IR before validation before compilation before docs.
resource: specs/004-filter-by-dimension/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T22:45:37+07:00' }
sources:
  - id: plan
    resource: /004-filter-by-dimension/plan.md
    title: The approach and impact map these tasks derive from
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T22:45:37+07:00', checkpoint: 3,
      basis: '8 tasks in dependency order; 1 [P] group of 2 checked disjoint by file path (docs/09-data-modeling.md vs AGENTS.md); every task carries a runnable verification command' }
status: stable
---

Derived from the plan approved at checkpoint 2.[^plan]

`[P]` marks tasks that touch disjoint files and share no mutable state.

# Phase 1 — the predicate IR

- [x] **T1.** Add `Comparison`, `BoolOp`, `Negation` and the `Predicate` alias to
  `validate.py`, and give `ValidRequest` a `filter: Predicate | None = None` field. Values are
  Python values, never sqlglot nodes.
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** —
  - **Verification:** `uv run mypy` clean; existing tests still pass with the default `None`.
  - **Constitution check:** N2 — the IR must hold no caller-supplied node.

# Phase 2 — validation

- [x] **T2.** Add `"where"` to `_SELECT_ARGS` and walk the predicate: an operator table
  mapping each allowed node type to its arity and shape, a per-node unconsumed-argument check
  (so `Like(negate=…)` is read or refused), `Paren` unwrapping, and `And`/`Or`/`Not` recursion.
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** T1
  - **Verification:** `SELECT revenue FROM orders WHERE channel = 'web'` validates to a
    `ValidRequest` carrying one `Comparison`; `UPPER(channel) = 'WEB'` is refused.
  - **Constitution check:** N2 — a form the walker does not fully consume must refuse.

- [x] **T3.** Resolve each filtered name against the model: a dimension is accepted, a measure
  is refused naming `HAVING`, an unknown name is refused with `_suggest`. Then type-check every
  literal against the dimension's `type` — string / number / boolean / ISO date, `LIKE` only on
  `string`, ordering comparisons refused on `boolean`.
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** T2
  - **Verification:** `WHERE revenue > 1` refused naming HAVING; `WHERE chanel = 'web'`
    suggests `channel`; `WHERE order_date >= 'yesterday'` refused as a bad date.
  - **Constitution check:** N1 — all of this decides before the adapter is consulted.

# Phase 3 — compilation

- [x] **T4.** Add `_literal` and `_predicate` to `compile.py`, rebuilding each IR node as a
  freshly constructed sqlglot expression over the dimension's physical column, and attach it
  with `select.where(...)`. Dates become `CAST(<string> AS DATE)`.
  - **Files:** `src/semantiql/engine/compile.py`
  - **Depends on:** T3
  - **Verification:** `uv run semantiql "SELECT revenue FROM orders WHERE channel = 'web'"
    --show-sql` prints a `WHERE` and returns 956.5.
  - **Constitution check:** N4 — built canonically, then transpiled; no adapter import.

# Phase 4 — tests

- [x] **T5.** Refusal suite: measure filter, unknown name, function, arithmetic, subquery,
  column-to-column, one type mismatch per dimension type, `LIKE` on a date. All through `run`
  with `ExplodingAdapter`.
  - **Files:** `tests/test_validation_refuses.py`
  - **Depends on:** T3
  - **Verification:** `uv run pytest tests/test_validation_refuses.py` green.
  - **Constitution check:** N1 — asserts the datasource was never reached.

- [x] **T6.** Compile and end-to-end suites: one compile case per supported predicate form;
  `NOT LIKE` keeps its negation; a date renders as a cast; a hostile literal cannot add
  structure; and the five hand-computed filtered totals.
  - **Files:** `tests/test_compile.py`, `tests/test_example_end_to_end.py`
  - **Depends on:** T4
  - **Verification:** `uv run pytest tests/` green, including the pre-existing transpile
    tripwire.
  - **Constitution check:** N2 — the totals are computed independently, not read from output.

# Phase 5 — reconcile the derived copies

- [x] **T7. [P]** Coverage map and modelling reference: §3.4 `type:` is now enforced, §8's
  filter bullet rewritten, A.2 `WHERE` row ✅ with its predicate set, A.5 operators, A.6 records
  `where` joining the allowlist, and the `NOT IN` NULL trap added.
  - **Files:** `docs/09-data-modeling.md`
  - **Depends on:** T4
  - **Verification:** no statement in the doc contradicts a test; every named symbol exists.
  - **Constitution check:** trust-boundary artifact — called out in the report.

- [x] **T8. [P]** Agent brief: `WHERE` leaves the refused list, with the dimension-only and
  typed-literal constraints stated.
  - **Files:** `AGENTS.md`
  - **Depends on:** T4
  - **Verification:** `grep -n "WHERE" AGENTS.md` describes support, not refusal.
  - **Constitution check:** governance — `CLAUDE.md` mirrors this file and must not contradict
    the code.

T7 and T8 are `[P]`: disjoint files, neither generated from the other.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh`; report output verbatim.
- [x] **TV. Validation pass** — walk `validation.md`, ticking each AC and naming what proves it.

[^plan]: The impact map recorded at checkpoint 2.
