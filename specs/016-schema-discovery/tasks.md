---
type: Tasks
title: Schema discovery — Claude reads the database and writes the model — tasks
description: 12 tasks, 4 parallel, seam before consumer before documentation.
resource: specs/016-schema-discovery/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T09:49:47+00:00' }
sources:
  - id: plan
    resource: /016-schema-discovery/plan.md
    title: The approved plan these tasks derive from
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T09:49:47+00:00', checkpoint: 3,
      basis: 'Ordering derived from the impact map. The seam widening comes first because mypy names every test double that needs updating, which turns a discovery problem into a compiler error. Documentation comes last because A3 cannot be written truthfully until the command it describes has been run.' }
---

Derived from the approved plan.[^plan]

`[P]` marks tasks that touch disjoint files and share no mutable state.

**Why this order.** Widening the Protocol first makes mypy enumerate every implementation and test
double that now falls short — a list that is otherwise assembled by hand and assembled wrong. The
skill and the docs come last, and only after the command has actually been run, because both make
claims about output that must be quoted rather than imagined.

# Phase 1 — The seam

- [x] **T1.** Add `tables() -> list[str]` to the `Adapter` Protocol, documenting what a *displayed
      name* is: qualified only outside the engine's default schema, system schemas excluded.
  - **Files:** `src/semantiql/adapters/base.py`
  - **Depends on:** —
  - **Verification:** `uv run mypy` fails, naming every type that no longer satisfies the Protocol.
    That failure list is the input to T2 and T3.
  - **Constitution check:** N4 — the widening is in `base.py`, and `engine/` is untouched.

- [x] **T2. [P]** Implement it on the DuckDB adapter over `information_schema.tables`, leaving
      `main` unqualified.
  - **Files:** `src/semantiql/adapters/duckdb.py`
  - **Depends on:** T1
  - **Verification:** `tests/adapters/test_duckdb_adapter.py` — a table, a view, a
    non-default schema, and an empty catalogue.
  - **Constitution check:** N5 — metadata only; no rows are read.

- [x] **T3. [P]** Implement it on the Postgres adapter, excluding `pg_catalog` and
      `information_schema`, leaving `public` unqualified, rolling back after the fetch.
  - **Files:** `src/semantiql/adapters/postgres.py`
  - **Depends on:** T1
  - **Verification:** `tests/adapters/test_postgres_adapter.py`, marked `pg`.
  - **Constitution check:** N5 — the rollback leaves the connection `idle`, not
    `idle in transaction`, so a read-only session does not hold a snapshot open.

- [x] **T4. [P]** Update the four test doubles mypy named.
  - **Files:** the doubles under `tests/`
  - **Depends on:** T1
  - **Verification:** `uv run mypy` is clean.
  - **Constitution check:** — . Note the finding: a double that satisfies a Protocol only because
    nothing calls the new member is a double that will silently stop representing the real thing.

# Phase 2 — The consumer

- [x] **T5.** Add the `inspect` verb: relations by default, `--table` for columns, `--json` for
      machine output, and **no model required**.
  - **Files:** `src/semantiql/cli.py`
  - **Depends on:** T2, T3
  - **Verification:** run it against `examples/retail/` and against Postgres; both shapes print.
  - **Constitution check:** N1 — `inspect` reads catalogue metadata and never returns rows, so it
    is not a query path and does not need to route through `engine.run.run`. Stated because
    "a new way to reach the database" is otherwise exactly the shortcut the constitution refuses.

- [x] **T6.** Make the empty-catalogue case explain itself rather than printing nothing.
  - **Files:** `src/semantiql/cli.py`
  - **Depends on:** T5
  - **Verification:** `semantiql inspect` with no `--database` prints why an in-memory DuckDB
    reading CSV files has no catalogue objects.
  - **Constitution check:** — . Silence reads as a broken command; this is the one place a
    paragraph beats brevity.

- [x] **T7.** CLI tests for both shapes, `--json`, needs-no-model, the empty catalogue, an
      unreachable datasource, and a relation that does not exist.
  - **Files:** `tests/interfaces/test_cli.py`
  - **Depends on:** T5, T6
  - **Verification:** `uv run pytest tests/interfaces/test_cli.py -q`
  - **Constitution check:** — .

# Phase 3 — The skill, which is where the behaviour actually lives

- [x] **T8.** Add the discovery loop to the skill: inspect → shortlist → **ask the judgement
      questions** → write one YAML per table → `doctor` → show the analyst.
  - **Files:** `plugin/skills/semantiql/SKILL.md`
  - **Depends on:** T5
  - **Verification:** the loop names `semantiql inspect` and `semantiql doctor` as commands, not
    as MCP tools — there is no shell in Claude Desktop, so a tool name would fail silently there.
  - **Constitution check:** N6 — and this is the task that could break it. Two sentences are
    non-negotiable: never invent a measure's aggregation or a metric's formula, and never change a
    model to answer a question.

- [x] **T9.** Drift tests for every claim T8 added, including the N6 limits verbatim and a check
      that no invented tool name appears.
  - **Files:** `tests/interfaces/test_plugin.py`
  - **Depends on:** T8
  - **Verification:** `uv run pytest tests/interfaces/test_plugin.py -q`
  - **Constitution check:** N6 — a limit with no test is a limit that survives until someone tidies
    the file.

# Phase 4 — Documentation

- [x] **T10.** Rewrite `03-setup-workflow.md` A3 as the discovery loop, with real captured output,
      and reconcile A1 (Claude Code is needed for A3), A4 (no longer stands in for a wizard), the
      design principles, and the open question about `init`.
  - **Files:** `docs/03-setup-workflow.md`
  - **Depends on:** T5, T8
  - **Verification:** every command in A3 was run; the `inspect` transcript is quoted, not written.
  - **Constitution check:** trust boundary — `docs/NN-*.md` is a trust-boundary artifact, so this
    is not a routine edit and is called out as such.

- [x] **T11. [P]** Reconcile the other documents that described hand-writing as the flow.
  - **Files:** `docs/10-adopting-semantiql.md`, `docs/09-data-modeling.md`, `README.md`,
    `AGENTS.md`
  - **Depends on:** T10
  - **Verification:** `grep -rn "wizard" README.md docs/` returns only deliberate uses.
  - **Constitution check:** the README's Key ideas and the invariant list must still agree.

- [x] **T12.** Reconcile `02-architecture.md` and `07-code-map.md` with what changed: the seam
      gains a fifth member, and the architecture now has to explain why *building* has a shell that
      *asking* deliberately lacks.
  - **Files:** `docs/02-architecture.md`, `docs/07-code-map.md`
  - **Depends on:** T10
  - **Verification:** the two-modes table states the tool surface for each mode and which one may
    change a definition.
  - **Constitution check:** N6 — the doc previously implied Claude never writes the model. The true
    statement is narrower: never *as a side effect of answering*. Left unreconciled, a reader would
    have concluded the skill violates the architecture.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh` both ways: with Postgres up, and with it down,
      so the `pg` skips are proven to skip rather than fail.
- [x] **TV. Validation pass** — walk `validation.md`, ticking each AC and naming what proves it.

[^plan]: The impact map approved at gate 2.
