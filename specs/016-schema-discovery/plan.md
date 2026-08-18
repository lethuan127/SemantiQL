---
type: Plan
title: Schema discovery — plan
description: One Protocol method backed by information_schema on both engines, an inspect verb with a two-step shape and JSON output, and a skill section that puts the judgement questions to the analyst.
resource: specs/016-schema-discovery/plan.md
tags: [sdd, plan, discovery, adapters]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T05:20:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time — N4, N5, N6, trust boundaries
    last_modified: 2026-08-18
  - id: probe
    resource: plan.md
    title: Live probe at plan time — information_schema.tables on DuckDB 1.x and PostgreSQL 17.10
  - id: base
    resource: ../../src/semantiql/adapters/base.py
    title: The Protocol, Column, and the two prior widenings
    last_modified: 2026-08-18
  - id: duckdb-adapter
    resource: ../../src/semantiql/adapters/duckdb.py
    title: columns()'s probe pattern, _kind, _carries_timezone
    last_modified: 2026-08-18
  - id: postgres-adapter
    resource: ../../src/semantiql/adapters/postgres.py
    title: The same, plus the rollback after fetching
    last_modified: 2026-08-18
  - id: cli
    resource: ../../src/semantiql/cli.py
    title: _open_adapter, the verb routing, and the exit-code contract
    last_modified: 2026-08-18
  - id: skill
    resource: ../../plugin/skills/semantiql/SKILL.md
    title: Where the discovery section goes, and the drift test that guards it
    last_modified: 2026-08-18
  - id: test-plugin
    resource: ../../tests/interfaces/test_plugin.py
    title: The drift test asserting the skill's rules against the engine
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T05:24:00+07:00', checkpoint: 2,
      basis: 'map derived from 6 file reads plus a live probe of information_schema on both engines, which returns the same shape on each — so one query pattern serves both and only the excluded schemas differ. AD-1 keeps the return type a list of strings rather than a richer record, because a Protocol third parties implement should carry the least that does the job. AD-4 records the third seam widening as a finding rather than absorbing it' }
status: stable
---

# Constitution check

**N4 — this widens the seam a third time.** `close()` (spec 010), `carries_timezone` (011), now
`tables()`. Each was found by building something new against the Protocol, which is the seam working
as intended — but three is a pattern, and AD-4 records it rather than letting it pass as
routine.[^base] [^constitution]

**N5 — read-only, and further from the data than anything else here.** Enumeration reads the
catalogue. No rows.

**N6 — a conversation is not automatic change.** The analyst answers the judgement questions and
accepts the files. What N6 forbids is a model changing to answer a question, and FR-9 puts that limit
in the skill where Claude will read it.[^constitution]

**Trust-boundary artifacts** in scope: `docs/03-setup-workflow.md`, `docs/07-code-map.md`. The
constitution is not touched.

# Approach

**One Protocol method, one query pattern.** Probed at plan time, `information_schema.tables` returns
`(table_schema, table_name, table_type)` on **both** engines, so the implementations differ only in
which schemas they exclude and which one is "default".[^probe]

```
DuckDB     main    → bare name        other schema → schema.name
Postgres   public  → bare name        other schema → schema.name
                                      pg_catalog, information_schema → excluded
```

Returned as names `columns()` already accepts, so discovery composes with what exists rather than
adding a parallel path.[^duckdb-adapter] [^postgres-adapter]

**`inspect` is the only command that needs no model.** It takes the datasource flags and nothing
else — which is the point, since it runs before a model exists. Two steps: relations by default,
columns when one is named. `--json` for Claude; a readable table for a human.[^cli]

**The skill orchestrates and the analyst decides.** Inspect, propose a shortlist, ask the questions
a schema cannot answer, write one file per table, run `doctor`, fix. The existing drift test keeps
the skill honest about what the engine accepts.[^skill] [^test-plugin]

# Architecture decisions

**AD-1 — `tables()` returns `list[str]`, not a record.** Knowing table-from-view is mildly useful and
a Protocol that third parties implement should carry the least that does the job. A name is what
`columns()` needs; `inspect` can say more later without changing the seam.

**AD-2 — schema qualification only where it is needed.** Returning `public.orders` always would make
every model in existence read worse for no gain, and returning bare names always would make
`analytics.daily` ambiguous. Qualify when the schema is not the default.

**AD-3 — `--json` rather than JSON by default.** An analyst runs `inspect` too, and a wall of JSON is
a worse first experience than a table. Claude passes the flag; the skill says so.

**AD-4 — the third widening, recorded.** `close()`, `carries_timezone`, `tables()`. Every one was
found by building a real consumer, which is the argument for building real consumers. It also means
`base.Adapter` has grown 60% since it was written, and a fourth should prompt asking whether the
Protocol is the right shape rather than just adding a fifth.

**AD-5 — `inspect` reports the *semantic* type, not only the native one.** `timestamp with time zone`
tells an analyst what the database holds; `type: date` plus `carries a timezone` tells Claude what to
write. Both are printed, because the point is to write a model.

# Repository Impact Map

## Files to modify

- `src/semantiql/adapters/base.py` — `tables()` on the Protocol. **Third widening**; the docstring
  says so and says why the return type is minimal.[^base]
- `src/semantiql/adapters/duckdb.py` — implement it over `information_schema.tables`, `main` as
  default schema.[^duckdb-adapter]
- `src/semantiql/adapters/postgres.py` — the same, `public` as default, system schemas
  excluded.[^postgres-adapter]
- `src/semantiql/cli.py` — the `inspect` verb, `--table` and `--json`, no model required.[^cli]
- `plugin/skills/semantiql/SKILL.md` — the discovery workflow, and FR-9's limits.[^skill]
- `docs/03-setup-workflow.md` — A3 becomes the discovery flow; hand-writing stays documented.
  **Trust-boundary artifact.**
- `docs/07-code-map.md` — the adapter-seam table gains `tables()`. **Trust-boundary artifact.**
- `docs/09-data-modeling.md` — a pointer from the field reference to discovery.
- `README.md`, `AGENTS.md` — a line each; `CLAUDE.md` is a symlink and **not** a second edit.
- `tests/adapters/test_duckdb_adapter.py`, `tests/adapters/test_postgres_adapter.py` — enumeration.
- `tests/interfaces/test_cli.py` — the verb, both shapes, JSON, and that it needs no model.
- `tests/interfaces/test_plugin.py` — the skill's new claims stay pinned to the engine.

## Files not touched, but adjacent

- `src/semantiql/server.py` — **no change.** FR-10: the surface stays two read-only tools. The client
  has a shell; the server does not need to grow.
- `src/semantiql/engine/` — no change. `inspect` is not a query path.
- `src/semantiql/doctor.py` — no change. It already consumes `columns()`, and it is what closes the
  discovery loop.

# Open research questions

- **OQ-1 — does DuckDB's `information_schema` list a CSV read as a relation?** It does not: a
  `read_csv_auto` source is not a catalogue object. So `inspect` on an in-memory DuckDB shows
  nothing, which is correct and will look like a bug. The command should say so rather than print an
  empty list.
- **OQ-2 — how large can `inspect --json` get before it is a problem?** A 500-table list is small;
  500 tables' *columns* would not be. FR-7's two steps handle it, and the skill should be told to
  inspect the tables it shortlisted rather than all of them.
- **OQ-3 — should `inspect` respect a read-only account's visibility?** It will, for free:
  `information_schema` shows what the connected role can see, so a restricted account produces a
  restricted list. Worth stating because it is a feature, not an accident.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N4, N5, N6, the ≤15-minute rule, and the trust-boundary list.
[^probe]: Live probe at plan time — `information_schema.tables` on DuckDB 1.x and PostgreSQL 17.10, returning `(table_schema, table_name, table_type)` on both.
[^base]: `src/semantiql/adapters/base.py` — the Protocol, `Column`, and the `close()` and `carries_timezone` widenings.
[^duckdb-adapter]: `src/semantiql/adapters/duckdb.py` — the `columns()` probe, `_kind`, `_carries_timezone`.
[^postgres-adapter]: `src/semantiql/adapters/postgres.py` — the same, and the rollback after fetching.
[^cli]: `src/semantiql/cli.py` — `_open_adapter`, verb routing, exit codes.
[^skill]: `plugin/skills/semantiql/SKILL.md` — the describe-first section and where discovery belongs.
[^test-plugin]: `tests/interfaces/test_plugin.py` — the drift test.
