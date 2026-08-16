---
type: Tasks
title: Derived metrics in the semantic model — tasks
description: 7 tasks, 2 parallel, expression module before model before engine before docs.
resource: specs/006-derived-metrics/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:26:51+07:00' }
sources:
  - id: plan
    resource: /006-derived-metrics/plan.md
    title: The approach and impact map these tasks derive from
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T23:26:51+07:00', checkpoint: 3,
      basis: '7 tasks in dependency order; 1 [P] group of 2 checked disjoint by file path (docs/09-data-modeling.md vs AGENTS.md + README.md); every task carries a runnable verification' }
status: stable
---

Derived from the plan approved at checkpoint 2.[^plan]

# Phase 1 — the expression module

- [x] **T1.** Add `knowledge/expression.py`: the `Ref`/`Num`/`BinOp`/`Neg` IR,
  `ExpressionError`, and `parse_expression(text, measures)` walking sqlglot output under the
  node allowlist. Refuse a literal-zero divisor at parse time.
  - **Files:** `src/semantiql/knowledge/expression.py`
  - **Depends on:** —
  - **Verification:** `uv run mypy`; `parse_expression("revenue / order_count", {...})` returns
    a `BinOp`, and `"UPPER(x)"`, `"SUM(a)"`, `"nope"`, `"revenue / 0"` each raise.
  - **Constitution check:** N3 — parsing happens once, at load.

# Phase 2 — the model

- [x] **T2.** Add `Metric`; add `metrics` to `Table`; extend the clash validator to three-way;
  validate each expression in the table validator; teach `entity()`/`entity_names`.
  - **Files:** `src/semantiql/knowledge/model.py`
  - **Depends on:** T1
  - **Verification:** a model with a bad metric fails `load_model` with a field-level message.
  - **Constitution check:** N3 — a malformed model fails loudly at load.

# Phase 3 — the engine

- [x] **T3.** `validate`: a metric satisfies the must-compute-a-number rule, never becomes a
  `GROUP BY` key, and cannot be filtered on.
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** T2
  - **Verification:** `SELECT revenue_per_order FROM orders` validates; `WHERE
    revenue_per_order > 1` refuses.
  - **Constitution check:** N1.

- [x] **T4.** `compile`: `_metric` walks the IR, substitutes each measure's sanctioned
  aggregation, and guards every divisor.
  - **Files:** `src/semantiql/engine/compile.py`, `examples/retail/semantic_model.yml`
  - **Depends on:** T3
  - **Verification:** `uv run semantiql "SELECT revenue_per_order, channel FROM orders"
    --show-sql` shows `SUM(amount) / NULLIF(COUNT(order_id), 0)`.
  - **Constitution check:** N2, N4.

# Phase 4 — tests

- [x] **T5.** Loader, compile, refusal and end-to-end cases per `validation.md`, including the
  hand-computed ratio per channel and the empty-denominator case.
  - **Files:** `tests/test_loader.py`, `tests/test_compile.py`,
    `tests/test_validation_refuses.py`, `tests/test_example_end_to_end.py`
  - **Depends on:** T4
  - **Verification:** `uv run pytest tests/` green.
  - **Constitution check:** N2 — assert arithmetic, not SQL text.

# Phase 5 — reconcile the derived copies

- [x] **T6. [P]** `docs/09-data-modeling.md`: a metrics section in §3, §8's ratio bullet
  rewritten, A.4's escape-hatch note, and the after-grouping rule.
  - **Files:** `docs/09-data-modeling.md`
  - **Depends on:** T4
  - **Verification:** no statement contradicts a test.
  - **Constitution check:** trust-boundary artifact.

- [x] **T7. [P]** `AGENTS.md` and `README.md`: metrics are now real.
  - **Files:** `AGENTS.md`, `README.md`
  - **Depends on:** T4
  - **Verification:** neither describes metrics as unbuilt.
  - **Constitution check:** governance.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh`; report output verbatim.
- [x] **TV. Validation pass** — walk `validation.md`.

[^plan]: The impact map recorded at checkpoint 2.
