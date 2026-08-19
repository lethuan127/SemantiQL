---
type: Plan
title: Databricks and Google Sheets as datasources — plan
description: Two adapters, two optional extras, and a Sheets design that borrows DuckDB rather than reimplementing SQL.
resource: specs/023-databricks-and-sheets/plan.md
tags: [sdd, plan]
generated: { by: claude-code/claude-opus-5, at: '2026-08-19T09:21:37+00:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 
  - id: postgres
    resource: ../src/semantiql/adapters/postgres.py
    title: The adapter both of these are modelled on — probe from relation(), rollback after fetch
    last_modified: 2026-08-18
  - id: duckdb-adapter
    resource: ../src/semantiql/adapters/duckdb.py
    title: relation() dispatching on suffix, and the in-memory connection Sheets will borrow
    last_modified: 2026-08-18
  - id: cli
    resource: ../src/semantiql/cli.py
    title: _open_adapter and the datasource choices argparse accepts
    last_modified: 2026-08-18
  - id: pyproject
    resource: ../pyproject.toml
    title: dependencies today, and the absence of any optional group to follow
    last_modified: 2026-08-17
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-19T09:21:37+00:00', checkpoint: 2,
      basis: 'Five rows, all footnoted. The decisive reads were the Postgres adapter for the probe-from-relation pattern both new adapters copy, and the DuckDB adapter for the in-memory connection the Sheets adapter borrows as its engine. sqlglot databricks support and DuckDB-over-HTTPS were both executed before the design rather than assumed.' }
---

# Constitution check

**N4 — one canonical dialect, then transpile.** This is the invariant on trial. `DatabricksAdapter`
declares `dialect = "databricks"` and sqlglot does the rest. `SheetsAdapter` declares `duckdb`, which
looks like a cheat and is not: DuckDB genuinely *is* its execution engine. `engine/` must not change,
and that is checked with the constitution's own grep.[^constitution]

**N5 — read-only.** Neither adapter has a write path. Databricks gets a read-only session where the
driver supports it; both ultimately rely on `validate` refusing non-`SELECT`, which is the same honest
position the DuckDB in-memory case already documents.

**N1 / N2 — no second query path.** The Sheets adapter must not interpret SQL. Fetch, register, hand to
DuckDB. A hand-rolled filter would be a second query implementation whose disagreements with DuckDB
would surface as wrong numbers rather than errors.

**The dependency rule.** Two optional groups, `dependencies` untouched. A fresh `uv sync` installs
neither driver.[^pyproject]

**No agent amends the constitution.** Its roadmap line is prepared as a diff for the owner; the README
and `docs/05` are updated directly, and the three are named as needing to stay in sync.

# Approach

**Both adapters copy the Postgres one**, which is the worked example the constitution points at: build
every probe from `relation()` rather than interpolating a `source`, so a quote in a model value stays a
value; classify native types into `ColumnKind` in the adapter, because that translation is the
adapter's job; and roll back after fetching where the driver holds a transaction open.[^postgres]

**Databricks.** `databricks.sql.connect(server_hostname, http_path, access_token)`. `tables()` and
`columns()` come from `information_schema`, which Unity Catalog provides, with a `DESCRIBE`-shaped
fallback avoided in favour of one code path. Type names are Spark's — `STRING`, `BIGINT`, `DOUBLE`,
`DECIMAL(p,s)`, `TIMESTAMP`, `TIMESTAMP_NTZ`, `DATE`, `BOOLEAN` — and `TIMESTAMP` carries a zone in
Spark semantics while `TIMESTAMP_NTZ` does not, which is exactly the `carries_timezone` bit.

**Sheets.** `spreadsheets.values.get` returns a range as lists of strings. The adapter takes the first
row as the header, creates a DuckDB table from the rest, and lets DuckDB infer types from the text —
the same inference it already applies to a CSV.[^duckdb-adapter] `relation()` then returns the
registered table name, and `execute()` is DuckDB's. Everything else follows.

The honest limit, documented rather than hidden: **the whole range is fetched when the adapter opens.**
That is right for a spreadsheet, which is small by construction, and wrong for anything large — and it
is the reason this is a Sheets adapter and not a warehouse one.

**Imports are deferred.** Each driver is imported inside the adapter's `__init__`, not at module import,
so `adapters/__init__` stays importable without either extra and the error is an install instruction.

# Architecture decisions

1. **Sheets borrows DuckDB instead of interpreting SQL.** Rejected: a Python filter/aggregate layer. It
   is a second query engine, and its first disagreement with DuckDB about `NULL` in an average is a
   wrong number rather than an error. N2 decides this.

2. **`SheetsAdapter.dialect` is `duckdb`, not a new `sheets` dialect.** The dialect names the SQL the
   adapter will be handed, and it will be handed DuckDB SQL because DuckDB executes it. Inventing a
   dialect sqlglot does not have would break transpilation for no gain.

3. **Optional dependency groups, and deferred imports.** Rejected: hard dependencies, which grow every
   install for two datasources most users do not have; and a top-level `try: import` with a module-level
   flag, which turns a missing driver into a silent capability change instead of a message.

4. **`information_schema` on Databricks, not `SHOW TABLES`.** One code path shared with the Postgres
   adapter's shape, and it returns types in the same query rather than needing a second round trip.

5. **Types inferred from text on Sheets, not declared in the model.** Rejected: asking the model author
   for a type per column, which duplicates what `doctor` already checks and would drift from the sheet.
   DuckDB's CSV-style inference is the same behaviour a user already gets from a `.csv` source.

6. **Live tests skip; pure tests always run.** The `pg` suite's pattern. Neither service is reachable
   from here, so the alternative to skipping is pretending.

# Repository Impact Map

## Files to add

- `src/semantiql/adapters/databricks.py` — the adapter. Modelled on `postgres.py`.[^postgres]
- `src/semantiql/adapters/sheets.py` — fetch, load into DuckDB, delegate.[^duckdb-adapter]
- `tests/adapters/test_databricks_adapter.py`, `tests/adapters/test_sheets_adapter.py` — pure parts
  offline, live parts marked `dbx` / `sheets` and skipping with a stated reason.
- `specs/023-databricks-and-sheets/constitution-amendment.md` — the roadmap diff, for the owner.

## Files to modify

- `pyproject.toml` — two `[project.optional-dependencies]` groups. `dependencies` untouched.[^pyproject]
- `src/semantiql/cli.py` — `_open_adapter` gains two branches; `--datasource` gains two choices; new
  connection flags and their environment fallbacks.[^cli]
- `src/semantiql/knowledge/model.py` — `Datasource.dialect` is a `Literal`; it gains the two values, or
  a model naming them cannot load.
- `docs/05-datasources.md`, `README.md` — the roadmap, kept in sync as `AGENTS.md` requires.
- `tests/engine/` — wherever a test asserts the set of accepted dialects.

## Files not touched

- `src/semantiql/engine/` — **N4's whole claim.** If this needs editing, the design is wrong.
- `.specify/memory/constitution.md` — proposed diff only.

# Open research questions

- **Does the Databricks driver expose a read-only session flag?** Postgres has one and it is
  load-bearing there. If Databricks does not, N5 rests entirely on `validate`, which is the same
  position as in-memory DuckDB — worth stating in the adapter rather than discovering later.
- **Sheets type inference on a column of mixed text and numbers.** DuckDB will pick something; whether
  it picks `VARCHAR` and quietly makes a measure unusable is worth a test once a real sheet exists.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N4, N5, the dependency rule, the roadmap, and the no-unilateral-amendment rule.
[^postgres]: `src/semantiql/adapters/postgres.py` — probe from `relation()`, `_kind` translation, rollback after fetch.
[^duckdb-adapter]: `src/semantiql/adapters/duckdb.py` — the in-memory connection and CSV-style type inference.
[^cli]: `src/semantiql/cli.py` — `_open_adapter`, `--datasource` choices, and the environment fallbacks.
[^pyproject]: `pyproject.toml` — `dependencies`, and the absence of any optional group today.
