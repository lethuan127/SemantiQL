---
type: Tasks
title: Databricks and Google Sheets as datasources — tasks
description: 9 tasks — extras and the model first, so a wrong dialect fails at load rather than at query time.
resource: specs/023-databricks-and-sheets/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-19T09:22:13+00:00' }
sources:
  - id: plan
    resource: /023-databricks-and-sheets/plan.md
    title: The approved plan these tasks derive from
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-19T09:22:13+00:00', checkpoint: 3,
      basis: 'The model dialect widens first because it is a `Literal`: until it accepts the new names, no fixture model for either adapter can even load, so every later task would be blocked in a way that looks like an adapter bug. Databricks precedes Sheets because sqlglot already speaks it, which makes it the one that tests N4 cleanly before the harder design lands.' }
---

Derived from the approved plan.[^plan]

# Phase 1 — Make the new names sayable

- [x] **T1.** Two optional dependency groups in `pyproject.toml`; `dependencies` untouched.
  - **Verification:** `uv sync` installs neither driver, and the gate stays green.
  - **Constitution check:** the dependency rule — a fresh clone must not grow.

- [x] **T2.** `Datasource.dialect` accepts `databricks` and `sheets`.
  - **Depends on:** T1
  - **Verification:** a model naming either loads; a model naming nonsense still fails at load.
  - **Constitution check:** N3 — the model stays the source of truth, so a dialect it cannot express
    is a dialect no adapter should accept.

# Phase 2 — Databricks, the one that tests N4

- [x] **T3.** `DatabricksAdapter`: all seven Protocol members, `dialect = "databricks"`, probes built
      from `relation()`, Spark type names mapped to `ColumnKind`, `TIMESTAMP` versus `TIMESTAMP_NTZ`
      driving `carries_timezone`.
  - **Depends on:** T2
  - **Verification:** the pure parts under test offline; the driver imported inside `__init__` so a
    missing extra is an install instruction, not a traceback.
  - **Constitution check:** N4 — and `engine/` unchanged, by the constitution's own grep.

- [x] **T4.** Its tests: relation building, type mapping, the install message, and a live suite marked
      `dbx` that skips with a stated reason.
  - **Depends on:** T3
  - **Constitution check:** N5 — assert there is no write path, and state where the guarantee comes
    from if the driver has no read-only flag.

# Phase 3 — Sheets, the one that tests the design

- [x] **T5.** `SheetsAdapter`: fetch the range, load it into an in-memory DuckDB, delegate `execute`.
      `dialect = "duckdb"`, because DuckDB is the engine it borrows.
  - **Depends on:** T2
  - **Verification:** with rows injected rather than fetched, every Protocol member works end to end.
  - **Constitution check:** **N1/N2 — it must not interpret SQL.** A hand-rolled filter would be a
    second query engine whose disagreements become wrong numbers.

- [x] **T6.** Its tests: header handling, type inference, the whole Protocol against injected rows, and
      a live suite marked `sheets` that skips.
  - **Depends on:** T5

# Phase 4 — Reachable, documented, honest

- [x] **T7.** `_open_adapter` gains two branches; `--datasource` gains two choices; connection flags and
      environment fallbacks; a missing credential refused **by name**.
  - **Depends on:** T3, T5
  - **Constitution check:** one factory, not a second construction site.

- [x] **T8.** `docs/05-datasources.md` and `README.md` roadmaps updated together, plus the Sheets
      fetch-cost limit stated where a user will meet it.
  - **Depends on:** T7
  - **Constitution check:** trust boundary, and `AGENTS.md` requires those two stay in sync.

- [x] **T9.** `constitution-amendment.md`: the roadmap diff, for the owner to apply.
  - **Depends on:** T8
  - **Constitution check:** **no agent amends the constitution.** This proposes; it does not apply.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh` with Postgres up and down, and with neither new extra
      installed.
- [x] **TV. Validation pass** — walk `validation.md`, and state plainly which adapter has been exercised
      against a real service. Neither has.

[^plan]: The impact map approved at gate 2.
