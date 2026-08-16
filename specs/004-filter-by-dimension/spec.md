---
type: Spec
title: Filter a request by its dimensions
description: Support WHERE over model dimensions — typed literals, rebuilt from the model, with everything the compiler cannot honour still refused
resource: specs/004-filter-by-dimension/spec.md
tags: [sdd, spec, validation, compile]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T22:41:40+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-15
  - id: allowlist
    resource: ../specs/003-refuse-unimplemented-constructs/spec.md
    title: The allowlist rule this change is the first feature to extend
    last_modified: 2026-08-16
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T22:41:40+07:00', checkpoint: 1,
      basis: '8 FRs, each testable; FR-2 enumerates the exact predicate set so the allowlist has a fixed target; NFRs bind the change to N1, N2, N4, N5 and to spec 003 rule that a construct becomes answerable only when the compiler honours it' }
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** The change edits the query-validation layer and the compiler — the first is a
trust-boundary artifact by name, and the change adds a construct that reaches the database
carrying user-supplied values.

# What

A request may narrow what it counts. `SELECT revenue, channel FROM orders WHERE order_date
>= '2026-07-01' AND channel IN ('web', 'retail')` answers with revenue for those channels in
that period, instead of for everything.

Only dimensions defined in the semantic model may be filtered, and only against literal
values. Anything else inside the `WHERE` — a measure, an unknown name, a function, a
subquery, arithmetic — is refused, as it is today.

Today every `WHERE` is refused outright, so no report can ask about a period, a region, or a
channel.

# Why

A report is almost always about a slice: this month, this region, this product line. Without
a filter the engine answers only "everything, grouped by something", which is the one
question a business user rarely asks. This is the single largest gap between what the engine
does and what a report needs.

A concrete scenario: a sales manager asks Claude "how much did we make from web orders in
July?". Claude writes the obvious semantic SQL with a `WHERE`. SemantiQL refuses, and the
manager gets no answer at all — correct, but useless. Every dated question fails this way.

The reason it was refused rather than ignored is the reason this must be built carefully: the
compiler rebuilds each request from the model, so a filter it did not understand would
vanish and the manager would be shown the all-time total as if it were July's.

# User stories

- **As a business user**, I ask about a period or a segment and get that number — so the
  answer matches the question I asked.
- **As an analyst**, a filter on something the model does not define is refused by name — so
  a typo or a physical column never becomes a silently different population.
- **As a reviewer**, the value I filtered by cannot change the structure of the executed
  query — so a quote or a semicolon in a literal is data, never SQL.

# Functional requirements

- **FR-1** — A request may carry a `WHERE` that filters on dimensions defined for the table,
  and the filter is applied to the executed query.
- **FR-2** — Supported predicates: `=`, `<>`/`!=`, `<`, `<=`, `>`, `>=`, `IN`, `NOT IN`,
  `BETWEEN`, `LIKE`, `NOT LIKE`, `IS NULL`, `IS NOT NULL`, combined with `AND`, `OR`, `NOT`
  and parentheses. Each compares one dimension against literal values.
- **FR-3** — A filter on anything that is not a dimension of the table is refused: a measure
  is refused with a message saying measure filters are not supported, and an unknown name is
  refused with the existing did-you-mean suggestion.
- **FR-4** — A literal that contradicts the dimension's declared `type` is refused before
  execution — a text value against a `number` dimension, a non-date string against a `date`
  dimension.
- **FR-5** — Anything else inside a `WHERE` is refused: functions, arithmetic, `CASE`,
  subqueries, comparisons between two columns, and any predicate form not in FR-2.
- **FR-6** — The executed predicate is rebuilt from the semantic model, never carried over
  from the caller's parsed text. A literal containing a quote, a parenthesis or a semicolon
  is escaped as a value and cannot alter the query's structure.
- **FR-7** — Every request answerable before this change is still answered, unchanged.
- **FR-8** — The published documentation records filters as supported: the coverage map, the
  "what the model cannot express" section, and the agent brief.

# Non-functional requirements

- **N1 (validation over generation)** — a refused filter must never reach the datasource;
  tested with the adapter that raises if called.[^constitution]
- **N2 (a silently wrong number is the worst failure)** — a filter is either applied exactly
  as written or refused. Nothing in this change may make a `WHERE` partially applied, and the
  allowlist established by spec 003 must stay closed: `where` becomes answerable only because
  the compiler now honours it.[^allowlist]
- **N4 (canonical dialect, then transpile)** — predicates are built as canonical expressions
  and transpiled; no adapter import enters `engine/`.[^constitution]
- **N5 (read-only)** — unchanged; a filter cannot introduce a write.
- **Trust boundary** — `engine/validate.py` and `docs/NN-*.md` are both touched, so this
  change ships with tests for the refusal path and for the arithmetic of the filtered
  answer.[^constitution]

# Out of scope

- **Measure filters / `HAVING`** — filtering on an aggregate is a separate spec; here it is
  an explicit refusal.
- **`ORDER BY`, `LIMIT`, `OFFSET`** — the next spec (005), deliberately separate so this one
  can concentrate on literal safety and typing.
- **Time grains** — `WHERE order_date >= '2026-07-01'` is in scope; `GROUP BY month` is not.
- **Model-level or default filters** declared in the YAML, and parameter binding.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N4, N5 and the trust-boundary
    artifacts section naming the query-validation layer.
[^allowlist]: `specs/003-refuse-unimplemented-constructs/spec.md` — FR-3 and its rule that a
    construct becomes answerable only in the change that teaches the compiler to honour it.
