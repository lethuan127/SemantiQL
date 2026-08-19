---
type: Spec
title: Databricks and Google Sheets as datasources
description: Two adapters behind optional dependency groups — Databricks brought forward from v3 by owner decision, and Sheets which borrows DuckDB because a spreadsheet has no query engine.
resource: specs/023-databricks-and-sheets/spec.md
tags: [sdd, spec]
generated: { by: claude-code/claude-opus-5, at: '2026-08-19T09:20:41+00:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: N4, N5, N7, the dependency rule, and the datasource roadmap that names Databricks v3
    last_modified: 2026-08-17
  - id: datasources
    resource: ../docs/05-datasources.md
    title: The roadmap table, and the adapter contract a new datasource satisfies
    last_modified: 2026-08-17
  - id: base
    resource: ../src/semantiql/adapters/base.py
    title: The five-member Protocol both adapters must satisfy
    last_modified: 2026-08-18
  - id: cli-factory
    resource: ../src/semantiql/cli.py
    title: _open_adapter — the one place a concrete adapter is chosen
    last_modified: 2026-08-18
  - id: measured
    resource: ../specs/023-databricks-and-sheets/plan.md
    title: What was measured before designing — sqlglot dialects and DuckDB over HTTPS
    last_modified: 2026-08-19
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-19T09:20:41+00:00', checkpoint: 1,
      basis: 'Two things were measured before this was written: sqlglot already transpiles to the databricks dialect, which is what keeps N4 intact and the adapter thin; and DuckDB reads a CSV straight over HTTPS, which is what makes a Sheets adapter able to borrow a query engine instead of inventing one. The scope conflict was raised with the repository owner before any code — Databricks is recorded as v3 — and they chose to bring it forward as an optional extra. That decision is theirs and is recorded as such, not absorbed.' }
sdd_phase: shipped
sdd_tier: T2
---

**T2.** Two new adapter modules, two new optional dependency groups, and a recorded roadmap position
brought forward. Any one of those rules out T1.

# What

`semantiql --datasource databricks` and `--datasource sheets` work, each behind an optional dependency
group so the default install is unchanged.

**Today there are two adapters, DuckDB and Postgres**, and the roadmap places Databricks in v3 with
Google Sheets absent entirely.[^datasources]

# Why

**The owner asked for both, and was told what each costs before deciding.** Databricks is recorded as
v3 in the constitution's own roadmap.[^constitution] That position was raised rather than stepped over,
along with the rule that a new connector is never a routine change, and the decision to bring it
forward as an **optional extra** is the owner's. It is recorded here so the roadmap's history stays
readable rather than appearing to have drifted.

**Databricks is the cheap one, because sqlglot already speaks it.** N4 says the engine emits one
canonical dialect and transpiles; `sqlglot.transpile(..., write="databricks")` already produces valid
Databricks SQL, including the `TIMESTAMP_NTZ` cast a time grain needs. So the adapter is connect,
introspect, run — and `engine/` does not change, which is the claim N4 exists to protect.[^measured]

**Google Sheets is the interesting one, because a spreadsheet has no query engine.** Every other
adapter hands transpiled SQL to a database and gets rows back. Sheets cannot do that at all: the API
returns cell ranges. Two ways out, and only one of them keeps the engine honest.

The rejected way is to interpret the SQL in Python — filter and aggregate by hand. That would put a
second, weaker query implementation in the codebase, and the first time it disagreed with DuckDB about
a `NULL` in an average, the answer would be quietly wrong. N2 is the whole argument against it.

The chosen way is to **borrow DuckDB**. The adapter fetches the sheet's range once, registers it as an
in-memory relation, and executes the canonical SQL against it. Its `dialect` is therefore `duckdb` —
not because Sheets speaks SQL, but because DuckDB is the engine it is using. Nothing is
reimplemented, `compile.py` is untouched, and `profile` and `doctor` work for free.

**N7 is not in play.** "No NoSQL" is about document stores. A spreadsheet is a table with the type
information filed off, which is a data-quality problem rather than a shape problem — and it is the
shape that N7 refuses.[^constitution]

# User stories

- **As an analyst whose warehouse is Databricks**, I point a model at it and ask questions, without
  the team installing a Databricks driver they do not need.
- **As an analyst whose budget lives in a Google Sheet**, I model it and query it like a table.
- **As a contributor on a fresh clone**, `uv sync` installs neither driver and the gate still passes.

# Functional requirements

- **FR-1** — A `DatabricksAdapter` satisfies the `Adapter` Protocol: `dialect`, `relation`, `tables`,
  `columns`, `profile`, `execute`, `close`.[^base]
- **FR-2** — Its `dialect` is `databricks`, so the engine transpiles rather than special-casing.
- **FR-3** — A `SheetsAdapter` satisfies the same Protocol, with `dialect` = `duckdb`, executing
  through an in-memory DuckDB into which the sheet's range has been loaded.
- **FR-4** — A Sheets `source` names a worksheet; its columns come from the header row.
- **FR-5** — Both are read-only. Databricks opens a read-only session where the driver allows it, and
  in both cases the guarantee also comes from `validate` refusing every non-`SELECT` (N5).
- **FR-6** — Each driver is an **optional dependency group**. `uv sync` without extras installs
  neither, and importing an adapter whose driver is absent fails with an install instruction rather
  than a traceback.
- **FR-7** — `--datasource databricks` and `--datasource sheets` are accepted through the single
  adapter factory, not a second construction site,[^cli-factory] with the connection
  details taken from flags or the environment, and a **missing credential is refused by name**.
- **FR-8** — `engine/` is unchanged. Verified with the same grep the constitution names.[^constitution]
- **FR-9** — Live tests are marked and **skip with a stated reason** when credentials are absent, as
  the `pg` suite does; the pure parts — relation building, type mapping, SQL emitted — are tested
  offline and always run.
- **FR-10** — The roadmap is updated in all three places that state it: the README, `docs/05`, and the
  constitution — the last as a **proposed diff for the owner to apply**, since an agent may not amend
  it.[^constitution]
- **FR-11** — The Sheets adapter documents its one honest limit: the whole range is fetched per
  connection, so it suits a spreadsheet and not a warehouse.

# Non-functional requirements

- **N4** — the point of the exercise. Two adapters, no core change, verified by grep.[^constitution]
- **N5** — read-only. Neither adapter offers a write path, and `validate` refuses non-`SELECT`.
- **N1 / N2** — no new query path. Everything still routes through `engine.run.run`, and the Sheets
  adapter deliberately does **not** interpret SQL itself.
- **The default install must not grow.** Two optional groups; `dependencies` is untouched.[^constitution]
- **Honesty about verification** — neither adapter can be exercised against a real service here. What
  is tested is stated precisely, and what is not is stated too.

# Out of scope

- **BigQuery and Snowflake.** Same v3 line, not asked for.
- **Writing to either datasource.** N5.
- **Databricks Unity Catalog governance, or Sheets cell formatting.** The adapters read relations and
  columns; anything richer is a different feature.
- **Making either driver a hard dependency.** FR-6 is the constraint that keeps a fresh clone light.
- **Caching or incremental refresh for Sheets.** FR-11 documents the fetch cost rather than optimising
  it.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N4, N5, N7, the dependency rule at line 116, the roadmap at line 124, and the rule that no agent amends the constitution unilaterally.
[^datasources]: `docs/05-datasources.md` — the roadmap table placing Databricks in v3, and the adapter contract.
[^base]: `src/semantiql/adapters/base.py` — the Protocol's five members plus `close`.
[^cli-factory]: `src/semantiql/cli.py` — `_open_adapter`, the single place a concrete adapter is chosen.
[^measured]: Measured before designing: `sqlglot.transpile(..., write="databricks")` emits `DATE_TRUNC('MONTH', CAST(x AS TIMESTAMP_NTZ))`; and DuckDB read a 265-row CSV straight over HTTPS with typed columns.
