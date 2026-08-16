---
type: Tasks
title: Refuse every construct the compiler cannot honour, wherever it appears — tasks
description: 8 tasks (T8 added during implement), 2 parallel, ordered allowlists before wiring before docs.
resource: specs/003-refuse-unimplemented-constructs/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-15T23:15:31+07:00' }
sources:
  - id: plan
    resource: /003-refuse-unimplemented-constructs/plan.md
    title: The approach and impact map these tasks derive from
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-15T23:15:31+07:00', checkpoint: 3,
      basis: '7 tasks in dependency order; 1 [P] group of 2 checked disjoint by file path (docs/09-data-modeling.md vs AGENTS.md); every task carries a runnable verification command' }
status: stable
---

Derived from the plan approved at checkpoint 2.[^plan]

`[P]` marks tasks that touch disjoint files and share no mutable state.

# Phase 1 — invert the check

- [x] **T1.** Replace `_UNSUPPORTED_CLAUSES` with the two allowlists and the two label maps:
  `_SELECT_ARGS = {"expressions", "from"}`, `_FROM_NODES = {From, Table, Identifier,
  TableAlias}`, `_CLAUSE_LABELS` for select-argument wording (carrying today's entries), and
  `_NODE_LABELS` for node wording (`TableSample`, `Pivot`). Normalise argument names by
  stripping one trailing underscore so `from_` and `from` both match.
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** —
  - **Verification:** `uv run mypy` clean; the constants carry no behaviour yet.
  - **Constitution check:** N2 — the label maps must not gate any refusal decision.

- [x] **T2.** Wire the select-argument check: refuse any truthy argument whose normalised name
  is outside `_SELECT_ARGS`, in place of the loop at line 150, keeping the existing message
  text so `WHERE`, `LIMIT`, `JOIN`, `DISTINCT` and the rest read exactly as they do today.
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** T1
  - **Verification:** `uv run pytest tests/test_validation_refuses.py` — the 13 existing
    parametrized cases and `test_the_refusal_names_the_clause` still pass unchanged.
  - **Constitution check:** N1 — the check stays ahead of identifier resolution and of the adapter.

- [x] **T3.** Wire the FROM-subtree check: after the single-table check and before
  `model.table(...)`, walk the `FROM` subtree and refuse any node type outside `_FROM_NODES`,
  naming it from `_NODE_LABELS` or from the node's type.
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** T2
  - **Verification:** `uv run semantiql "SELECT revenue FROM orders TABLESAMPLE (10 PERCENT)"`
    exits 1 with a refusal naming TABLESAMPLE.
  - **Constitution check:** N2 — this is the branch that closes the silent drop.

- [x] **T4.** Rewrite the module docstring: it currently teaches the enumerate-the-bad model
  and lists clauses by name. It should state the allowlist rule, why the previous shape failed
  (both constructs were listed and still did not fire), and what a contributor must do when
  implementing a construct.
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** T3
  - **Verification:** `uv run ruff format --check .` and a read-through against the plan's
    Architecture decisions.
  - **Constitution check:** —

# Phase 2 — regressions

- [x] **T5.** Extend the refusal suite: add `TABLESAMPLE`, `PIVOT` and `UNPIVOT` to the
  parametrized silent-drop cases; assert the `TABLESAMPLE` refusal names the construct; add a
  parametrized test that the nine FR-5 forms still produce a `ValidRequest`; add a test that a
  construct absent from both label maps is still refused.
  - **Files:** `tests/test_validation_refuses.py`
  - **Depends on:** T3
  - **Verification:** `uv run pytest tests/` — all green, and the three new refusal cases fail
    if reverted against the pre-change `validate.py`.
  - **Constitution check:** N1 — the new cases run through `run` with `ExplodingAdapter`, so
    they assert the datasource was never reached.

# Phase 3 — reconcile the derived copies

- [x] **T6. [P]** Correct the published coverage map: A.2's two ⚠️ rows become ❌, A.6 is
  rewritten from a defect note into the default-refuse rule, and the two
  `_UNSUPPORTED_CLAUSES` references are renamed.
  - **Files:** `docs/09-data-modeling.md`
  - **Depends on:** T3
  - **Verification:** no `⚠️` remains in Appendix A; every named symbol exists in
    `validate.py`.
  - **Constitution check:** trust-boundary artifact — `docs/NN-*.md`; the edit is called out
    explicitly in the run report.

- [x] **T7. [P]** Update the agent brief: line 64 names `_UNSUPPORTED_CLAUSES` as the thing to
  edit when implementing a clause. Restate it as adding to the allowlist in the same change.
  - **Files:** `AGENTS.md` (`CLAUDE.md` is a symlink to it — no separate edit)
  - **Depends on:** T3
  - **Verification:** `grep -rn "_UNSUPPORTED_CLAUSES" AGENTS.md docs/ src/` returns nothing.
  - **Constitution check:** governance — `CLAUDE.md` mirrors the constitution and must not
    contradict the code it describes.

T6 and T7 are `[P]`: `docs/09-data-modeling.md` and `AGENTS.md` are disjoint files, and
neither is imported or generated by the other.

# Phase 4 — added during implement

- [x] **T8.** Close the residual hole found by self-review: `walk()` yields only expression
  nodes, so scalar arguments on the table (`only=True` from `FROM ONLY orders`,
  `ordinality=True` from `WITH ORDINALITY`) bypassed the node-type walk and were still
  accepted and dropped. Replace `_FROM_NODES` with `_FROM_NODE_ARGS` — allowed node type →
  allowed argument names — and refuse both an unknown type and an unknown argument on a known
  type. Extend the regression suite, the coverage map, and the agent brief to match.
  - **Files:** `src/semantiql/engine/validate.py`, `tests/test_validation_refuses.py`,
    `docs/09-data-modeling.md`, `AGENTS.md`
  - **Depends on:** T7
  - **Verification:** `SELECT revenue FROM ONLY orders` and `SELECT revenue FROM orders WITH
    ORDINALITY` are both refused; the 11 protected forms still validate; `./scripts/verify.sh`
    green.
  - **Constitution check:** N2 — this is the same silent-drop class, found in this change's
    own output.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh`; report output verbatim.
- [x] **TV. Validation pass** — walk `validation.md`, ticking each AC and naming what proves it.

[^plan]: The impact map recorded at checkpoint 2.
