---
type: Tasks
title: semantiql doctor — tasks
description: 8 tasks, 2 parallel, seam before checker before CLI before docs.
resource: specs/009-doctor/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T00:04:41+07:00' }
sources:
  - id: plan
    resource: /009-doctor/plan.md
    title: The approach and impact map these tasks derive from
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-17T00:04:41+07:00', checkpoint: 3,
      basis: '8 tasks in dependency order, written before implementation; 1 [P] pair checked disjoint (README.md+AGENTS.md vs the three docs/NN files); every task carries a runnable verification' }
status: stable
---

Derived from the plan approved at checkpoint 2.[^plan]

# Phase 1 — the seam

- [x] **T1.** `adapters/base.py`: add `ColumnKind` and the `Column` dataclass; change `columns`
  to `columns(source: str) -> list[Column]`, documenting that the adapter classifies its own
  native types into the model's vocabulary and returns `other` when it cannot tell.
  - **Files:** `src/semantiql/adapters/base.py`
  - **Depends on:** —
  - **Verification:** `uv run mypy`; the Protocol still has no import of a concrete adapter.
  - **Constitution check:** N4 — no engine type vocabulary leaves the adapter.

- [x] **T2.** `adapters/duckdb.py`: build the probe from `relation(source)` instead of
  interpolating, and classify DuckDB's type names.
  - **Files:** `src/semantiql/adapters/duckdb.py`
  - **Depends on:** T1
  - **Verification:** `columns("examples/retail/orders.csv")` returns five typed columns with
    `order_date` classified `date` and `amount` `number`.
  - **Constitution check:** N4, and the no-interpolation rule `relation()` exists for.

# Phase 2 — the checker

- [x] **T3.** `doctor.py`: `Finding`, `check(model, adapter)`, and the checks in reading order —
  dialect, source readability, column existence with suggestions, declared type versus physical
  kind, aggregation applicability. A source that cannot be read stops that table's checks.
  - **Files:** `src/semantiql/doctor.py`
  - **Depends on:** T2
  - **Verification:** a healthy model yields no problem findings; each broken model yields
    exactly the expected one.
  - **Constitution check:** N3 — reports, never edits.

# Phase 3 — the CLI

- [x] **T4.** `cli.py`: the `doctor` verb, `--database`, rendering, and exit codes 0/1/2/3.
  - **Files:** `src/semantiql/cli.py`
  - **Depends on:** T3
  - **Verification:** `uv run semantiql doctor` on the bundled example exits 0; a broken model
    exits 1 and names the problem.
  - **Constitution check:** N5 — `--database` opens read-only.

# Phase 4 — tests

- [x] **T5.** `tests/test_doctor.py` — a healthy model plus one deliberately broken model per
  finding kind; `tests/test_cli.py` — doctor's exit codes.
  - **Files:** `tests/test_doctor.py`, `tests/test_cli.py`
  - **Depends on:** T4
  - **Verification:** `uv run pytest -m "not e2e"` green.
  - **Constitution check:** —

- [x] **T6.** Update the two existing `columns()` callers to the new signature.
  - **Files:** `tests/test_adapter_duckdb.py`, `tests/e2e/test_edge_semantics.py`
  - **Depends on:** T2
  - **Verification:** `uv run pytest` green, both suites.
  - **Constitution check:** —

# Phase 5 — reconcile the derived copies

- [x] **T7. [P]** The three design docs: `09-data-modeling.md` §7.2 rows that said "caught:
  never"; `03-setup-workflow.md` for what doctor does and does not do yet (FR-9);
  `07-code-map.md` for the new module and `columns()` gaining a caller.
  - **Files:** `docs/09-data-modeling.md`, `docs/03-setup-workflow.md`, `docs/07-code-map.md`
  - **Depends on:** T4
  - **Verification:** no statement contradicts a test; FR-9's gap is stated.
  - **Constitution check:** three trust-boundary files — called out in the report.

- [x] **T8. [P]** `README.md` and `AGENTS.md`: doctor moves from roadmap to shipped.
  - **Files:** `README.md`, `AGENTS.md`
  - **Depends on:** T4
  - **Verification:** the roadmap and the feature list agree with the code.
  - **Constitution check:** governance.

T7 and T8 are `[P]`: disjoint files, neither generated from the other.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh`; report output verbatim.
- [x] **TV. Validation pass** — walk `validation.md`.

[^plan]: The impact map recorded at checkpoint 2.
