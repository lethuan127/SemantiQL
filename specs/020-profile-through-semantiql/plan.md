---
type: Plan
title: Profile a relation through SemantiQL, not through psql — plan
description: A fifth adapter member building fixed aggregate SQL from relation(), a profile verb, and a skill rule with a test.
resource: specs/020-profile-through-semantiql/plan.md
tags: [sdd, plan]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T14:27:01+00:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-17
  - id: base
    resource: ../src/semantiql/adapters/base.py
    title: The Protocol — Column, ColumnKind, and the four widenings so far
    last_modified: 2026-08-18
  - id: duck-columns
    resource: ../src/semantiql/adapters/duckdb.py
    title: columns() building its probe from relation() and running it on its own connection
    last_modified: 2026-08-18
  - id: pg-adapter
    resource: ../src/semantiql/adapters/postgres.py
    title: The Postgres adapter — autocommit=False, and the rollback after each fetch
    last_modified: 2026-08-18
  - id: cli
    resource: ../src/semantiql/cli.py
    title: _inspect and _render_inspection — the model-free verb this mirrors
    last_modified: 2026-08-18
  - id: skill
    resource: ../plugin/skills/semantiql/SKILL.md
    title: The discovery loop, and its silence about reading rows
    last_modified: 2026-08-18
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T14:27:01+00:00', checkpoint: 2,
      basis: 'Six rows, all footnoted. The decisive read was columns() in duckdb.py: engine-authored SQL is built from relation() and run on the adapter own connection, never handed to execute() as a string from outside. That settles where profiling goes and makes the seam widening the conservative option rather than the ambitious one. Postgres was read for its rollback-after-fetch, which profiling must repeat or it leaves a snapshot pinned.' }
---

# Constitution check

**N1 — the single path to the data.** The rule binds a way to *query*: caller-authored SQL must route
through `run`. Profiling authors nothing on the caller's behalf — the relation comes from the
catalogue, the columns from `columns()`, the aggregates from a fixed template per `ColumnKind`. The
precedent is in the tree: `doctor` reads the database outside `run`, and `columns()` builds a probe
from `relation()`. Nothing here accepts a caller expression, so there is no route for unvalidated SQL
to arrive.[^constitution] [^duck-columns]

**N4 — one canonical dialect, then transpile.** Aggregate SQL is where dialects actually diverge:
`count(*) FILTER (WHERE …)`, numeric casts, identifier quoting, ordering of grouped counts. Putting it
in `engine/` would mean the engine knowing two dialects. It goes in the adapter, and `engine/` does
not change — verified the usual way.[^constitution]

**N5 — read-only.** `SELECT` only, and Postgres must roll back after fetching, as `execute` already
does, or a long-lived connection sits `idle in transaction` holding a snapshot open.[^pg-adapter]

**N2 — the reason this exists.** Every figure a human is shown to decide a definition now comes from
one reviewed template instead of whatever SQL an agent improvised.

**Trust boundary** — `adapters/base.py` and `plugin/skills/semantiql/SKILL.md`. Called out.

# Approach

A fifth member on the `Adapter` Protocol:

```python
def profile(self, source: str) -> RelationProfile: ...
```

returning a frozen dataclass — `rows`, plus a `ColumnProfile` per column carrying `nulls`,
`distinct`, optional `minimum`/`maximum`/`total`, and an optional `values` list of
`(value, count)`.[^base]

The adapter builds the SQL, because that is where dialect knowledge lives and where the existing
precedent puts it.[^duck-columns] Two round trips per relation, not one per column: a single
`SELECT count(*), count(col1), count(DISTINCT col1), min(col1), …` covers every column in one pass,
then one grouped query per low-cardinality column for its distribution. On 2.96M rows the first is a
single sequential scan.

`ColumnKind` decides which aggregates apply — `min`/`max`/`sum` for `number`, `min`/`max` for `date`,
neither for `string`/`boolean`/`other`. That mapping already exists and is already the adapter's
job.[^base]

**The value distribution is the part that earns this.** `payment_type` is `bigint`, so every
type-driven heuristic calls it a number; it is a category, and a model that groups by it produces a
chart labelled 1, 2, 3. Cardinality reveals what type cannot: distinct count at or below a threshold
means the column is categorical whatever its type says. The threshold is a module constant, not a
flag, so two runs of `profile` on the same relation cannot disagree.

The CLI verb mirrors `_inspect`: no model, `--table` required, `--json`, and a rendered form for a
human.[^cli] `--table` is required rather than defaulting to every relation, because profiling reads
rows and a 500-table warehouse should not be scanned because someone omitted an argument.

The skill gains the verb and, more importantly, a prohibition: **no raw SQL against the database**,
and DDL is printed for the human rather than executed. That prohibition is the actual fix — the verb
without it just adds an option the agent may ignore, which is what happened to spec 016's exclusion
when it lived only in a spec.[^skill]

# Architecture decisions

1. **On the adapter seam, not in `engine/`.** Rejected: an `engine/profile.py` calling
   `adapter.execute()` with a hand-built string. Shorter, and it is precisely the "shortcut to an
   adapter" `AGENTS.md` names as the change most likely to be rejected — plus it would put
   `FILTER (WHERE …)` and cast syntax in the engine, which is N4 inverted.

2. **One wide query for the scalar aggregates.** Rejected: a query per column, which is 19 round trips
   on the taxi table for no benefit. Rejected also: one query per *kind*, which is the same cost with
   more code.

3. **Cardinality decides categorical, not type.** Rejected: treating only `string` as categorical,
   which is exactly the mistake that makes `payment_type` come back as a number nobody can read.

4. **The threshold is a constant.** Rejected: a `--top` flag. A flag makes the output depend on how it
   was invoked, and the consumer is a model that will not remember which invocation it used.

5. **`--table` is required.** Rejected: profiling every relation by default. Reading rows is a bigger
   claim than reading metadata, and it should take a deliberate argument.

6. **The prohibition is tested, not just written.** Rejected: adding the verb and trusting the skill.
   Spec 016 proved an unenforced exclusion is not an exclusion.

# Open research questions

- **Is the `Adapter` Protocol still the right shape?** `base.py` carries a note, written in spec 016,
  saying that three widenings are a pattern and that a fourth "should prompt asking whether this is
  still the right shape, rather than adding a fifth". This is the fourth, so the question is asked
  here rather than skipped.

  The observation the note was reaching for: six members now serve **three** unrelated concerns.
  `relation()` and `execute()` are the query path. `tables()`, `columns()` and `profile()` are
  introspection. `close()` is lifecycle. Splitting introspection into its own Protocol — implemented
  by the same classes — would make future growth read as "the introspection surface grew", which is
  informative, instead of "the adapter grew", which is not. It would also let a read-only
  catalogue-only implementation exist.

  **Not done here, deliberately.** It is a refactor of a trust-boundary file with no behaviour change,
  which makes it its own spec and its own review rather than a passenger on this one. Recorded so the
  next person adding a member finds the question already framed, and so the note in `base.py` is
  answered rather than repeated.

# Repository Impact Map

## Files to modify

- `src/semantiql/adapters/base.py` — `ColumnProfile` and `RelationProfile` dataclasses, and
  `profile(source)` on the Protocol. **Fifth widening**, documented alongside the other four.[^base]
- `src/semantiql/adapters/duckdb.py` — implement it: one wide aggregate query built from `relation()`,
  plus a grouped query per low-cardinality column.[^duck-columns]
- `src/semantiql/adapters/postgres.py` — the same, with `FILTER (WHERE …)`, numeric casts for exact
  sums, and **a rollback after fetching**.[^pg-adapter]
- `src/semantiql/cli.py` — a `profile` verb beside `inspect`: no model, `--table` required, `--json`,
  and a rendered form.[^cli]
- `plugin/skills/semantiql/SKILL.md` — teach `profile`; forbid raw SQL; print DDL instead of executing
  it. **Trust-boundary artifact.**[^skill]
- `tests/adapters/test_duckdb_adapter.py`, `tests/adapters/test_postgres_adapter.py` — the aggregates,
  the distribution, the threshold boundary, and read-only.
- `tests/interfaces/test_cli.py` — the verb, both shapes, needs-no-model, `--table` required.
- `tests/interfaces/test_plugin.py` — FR-11: the skill names no SQL client as a way to reach data.
- The four test doubles that implement the Protocol — mypy will name them.

## Files not touched

- `src/semantiql/engine/` — **N4's check.** If this needs editing, AD-1 was wrong.
- `src/semantiql/server.py` — the MCP surface stays two tools. Profiling is a build-time verb and
  build mode has a shell; adding a third tool would widen the asking surface for a job it never does.
- `src/semantiql/knowledge/` — profiling reports what is in a column, never what it means.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N4, N5, the trust-boundary list; `AGENTS.md` on `execute` being a plain string held by convention.
[^base]: `src/semantiql/adapters/base.py` — `Column`, `ColumnKind`, and the four widenings recorded there.
[^duck-columns]: `src/semantiql/adapters/duckdb.py` — `columns()` building its probe from `relation()` and running it on the adapter's own connection.
[^pg-adapter]: `src/semantiql/adapters/postgres.py` — `autocommit=False` and the `rollback()` after fetching.
[^cli]: `src/semantiql/cli.py` — `_inspect` and `_render_inspection`.
[^skill]: `plugin/skills/semantiql/SKILL.md` — the discovery loop.
