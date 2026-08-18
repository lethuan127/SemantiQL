---
type: Spec
title: Profile a relation through SemantiQL, not through psql
description: The discovery loop read every figure it showed the analyst with raw psql; profiling becomes a read-only verb on the adapter seam and raw SQL becomes forbidden.
resource: specs/020-profile-through-semantiql/spec.md
tags: [sdd, spec]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T14:25:51+00:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-17
  - id: transcript
    resource: ../.test-workspace/logs/README.md
    title: How the finding was established — the run's own tool-call transcript
    last_modified: 2026-08-18
  - id: scope-016
    resource: ../specs/016-schema-discovery/spec.md
    title: Out of scope — row-level profiling, excluded and then done anyway
    last_modified: 2026-08-18
  - id: columns
    resource: ../src/semantiql/adapters/duckdb.py
    title: columns() — the precedent for engine-authored SQL built from relation()
    last_modified: 2026-08-18
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T14:25:51+00:00', checkpoint: 1,
      basis: 'The finding is evidenced by the run transcript, not by impression: 12+ raw psql calls including a JOIN and a CREATE OR REPLACE VIEW, extracted programmatically. The user identified it. Scope was settled by them choosing to route profiling through SemantiQL over the two alternatives — forbidding row reads outright, or sanctioning the shell — because the numbers are what make the judgement questions answerable and the read path should still be reviewable.' }
sdd_phase: shipped
sdd_tier: T2
---

**T2.** Widens the adapter `Protocol` and edits `plugin/skills/semantiql/SKILL.md`; both are
trust-boundary artifacts.

# What

`semantiql profile --table <relation>` reports what is *in* a relation — row count, nulls, ranges,
totals, and the value distribution of any low-cardinality column — read-only, with no model required.
The skill uses it, and is forbidden from issuing raw SQL.

**Today the skill is silent and the agent improvises.** A run building a model over 2.96M real NYC
taxi trips used `semantiql inspect` for metadata, correctly, and then **12+ raw `psql` calls** for
every number it showed the analyst — including a JOIN across two tables, tip-rate ratios, residual
arithmetic across all ten money columns, and a `CREATE OR REPLACE VIEW`.[^transcript]

# Why

Three separate problems, and only the first is obvious.

**Every figure that drove a definition decision was unvalidated.** The run asked the right question —
*"which column is revenue?"* — and priced it: `total_amount` $79.46M against `fare_amount` $53.88M.
That pricing is what made the question answerable by a non-technical analyst. It also came from SQL
nothing checked. The figures happened to be right. Nothing *made* them right, and N2's whole claim is
that a plausible wrong number is the worst outcome because no one downstream can catch it. Here it
would arrive at the exact moment a definition is chosen, and then be baked into the model.[^constitution]

**Spec 016 excluded row-level profiling, and it happened anyway.** Its Out of scope says: *"Row-level
profiling — distinct counts, ranges, sample values. Useful for naming, and it reads rows, which is a
bigger claim than metadata."* The skill never says not to, so the exclusion existed only in a spec
nobody reads at runtime. **An exclusion that is not in the skill is not an exclusion.**[^scope-016]

**The shell is the hole the two-tool MCP surface exists to close.** `docs/02-architecture.md` says the
*asking* surface is two read-only tools precisely because "a shell-based skill would be easier and
would let the model reach the database by any route". Build mode legitimately has a shell — a model
cannot be written without one — so the same hole is open there, and a `CREATE OR REPLACE VIEW` went
through it. That write was authorised by the analyst, but N5's read-only guarantee comes from
`validate` refusing non-SELECT, which a shell bypasses entirely.[^constitution]

**Why not simply forbid reading rows.** Because the numbers are the value. *"Revenue is 53.9M or
79.5M, which do you mean"* is a question an analyst can answer; *"which of these five columns is
revenue"* is one they will guess at. Removing the figures makes the loop worse at the one thing it is
for. So the fix is to make the read path a reviewed one rather than to close it.

**Why this is not "another way to query".** N1 requires a way to *query* to route through
`engine.run.run`, and that is about **caller-authored SQL**. Profiling authors no caller SQL: the
relation comes from the catalogue, the columns come from `columns()`, and the aggregates are a fixed
template per column kind. It is the same shape as `doctor`, which already reads the database outside
`run`, and as `columns()` itself, which builds its probe from `relation()` inside the
adapter.[^columns]

# User stories

- **As Claude in the discovery loop**, one command gives me the distribution of a coded column and the
  totals of each money column — so I can price a judgement question without writing SQL.
- **As an analyst**, the numbers I am shown came from a path someone reviewed.
- **As a maintainer**, raw SQL in a discovery run is a rule violation with a test, not a style
  preference.

# Functional requirements

- **FR-1** — `profile` reports the relation's row count.
- **FR-2** — For every column: null count and distinct count.
- **FR-3** — For a numeric column: min, max and sum. Sum is what prices a revenue question.
- **FR-4** — For a date column: min and max, which is what reveals rows outside the intended period.
- **FR-5** — For any column whose distinct count is at or below a fixed threshold, the value
  distribution — value and row count, most frequent first. **This is what makes a coded integer
  legible**; `payment_type` is a number by type and a category in truth.
- **FR-6** — Read-only. `SELECT` only, authored by the engine, never accepting caller SQL or a caller
  expression.
- **FR-7** — No model required, like `inspect`. Profiling happens before a model exists.
- **FR-8** — `--json` for machine consumption, since the consumer is Claude.
- **FR-9** — Works identically on DuckDB and Postgres, with per-dialect SQL living in the adapter.
- **FR-10** — The skill instructs Claude to use `profile`, and **forbids raw SQL against the
  database**. If a view is needed, the skill prints the DDL for the human to run rather than executing
  it.
- **FR-11** — A test asserts the skill contains no raw-SQL instruction and names no client (`psql`,
  `duckdb`) as a way to reach data.

# Non-functional requirements

- **N1 / N2** — no caller SQL reaches the database, and every figure a human sees now comes from one
  reviewed template.[^constitution]
- **N4** — aggregate SQL is dialect-specific (`count(*) FILTER`, quoting, casts), so it belongs in the
  adapter. `engine/` must not change.[^constitution]
- **N5** — `SELECT` only. The write path closes: the skill stops executing DDL.
- **N6** — untouched. Profiling reports what is in a column, never what it means.
- **Trust boundary** — `adapters/base.py` and `SKILL.md`. This is the seam's **fourth** widening, after
  `close()`, `carries_timezone` and `tables()`, and again found by building a real consumer.[^columns]

# Out of scope

- **Percentiles, histograms, correlations.** A fixed cheap set, or profiling becomes a statistics
  package with a per-dialect surface to match.
- **Sampling.** Full-table aggregates on 2.96M rows are already sub-second; a sampled figure that
  *looks* exact is the wrong trade for a number that decides a definition.
- **Profiling a JOIN, or any expression.** FR-6 forbids caller expressions. The engine refuses joins;
  discovery does not get a side door.
- **Creating the view for the analyst.** FR-10 prints the DDL deliberately. Executing DDL is the write
  path this spec closes.
- **Making `inspect` do this.** Metadata and row reads are different claims on a database and keeping
  the verbs separate keeps that visible; `inspect` stays the one that touches no rows.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N4, N5, N6, and the trust-boundary artifact list; plus `docs/02-architecture.md` on why the asking surface is two tools.
[^transcript]: `.test-workspace/logs/README.md` — how the run's tool calls were extracted, and what they showed.
[^scope-016]: `specs/016-schema-discovery/spec.md` — Out of scope, "Row-level profiling".
[^columns]: `src/semantiql/adapters/duckdb.py` — `columns()` building its probe from `relation()` and running it on the adapter's own connection.
