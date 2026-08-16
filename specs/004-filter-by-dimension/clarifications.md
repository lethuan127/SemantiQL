---
type: Clarifications
title: Filter a request by its dimensions — clarifications
description: 5 ambiguities resolved before planning.
resource: specs/004-filter-by-dimension/clarifications.md
tags: [sdd, clarifications]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T22:45:37+07:00' }
status: stable
---

## Q1: Does the compiler reuse the caller's parsed predicate, or rebuild it?

- (a) Re-map the column names inside the parsed `WHERE` subtree and hand the rewritten AST to
  the compiler.
- (b) Validate the predicate into a neutral intermediate form — dimension, operator, typed
  values — and have the compiler build fresh sqlglot nodes from it.
- **Chosen:** (b) — decided by the agent from FR-6 and from how the rest of the engine already
  works. `compile_request` rebuilds the projection list from the model rather than editing what
  the caller wrote, and the relation is built rather than parsed for the same reason. Reusing
  the caller's nodes would make the predicate the one part of the query carried over verbatim,
  and any argument on those nodes that the validator did not think to inspect would ride along
  into the executed SQL. A neutral form makes "rebuilt from the model" structural rather than
  a promise — nothing reaches the database that the validator did not explicitly construct.

## Q2: How are date literals emitted?

- (a) As a bare string literal and let the engine's implicit cast handle it.
- (b) As an explicit `CAST(<literal> AS DATE)`.
- **Chosen:** (b) — decided by the agent from N3 and N4. The model is meant to survive a
  change of database, and implicit string-to-date coercion is exactly the kind of behaviour
  that differs between engines. An explicit cast means DuckDB and Postgres compare the same
  two things. It also gives the transpile step its first genuinely typed construct, which the
  tripwire test at `tests/test_compile.py:57` was written to notice.

## Q3: What makes a literal type-compatible with a dimension (FR-4)?

- (a) Accept any literal and let the database decide.
- (b) Check the literal against the dimension's declared `type` and refuse a contradiction.
- **Chosen:** (b) — decided by the agent from FR-4 and N2. Option (a) turns a modelling error
  into an `AdapterError` at execution time, or worse, into a silent coercion — Postgres and
  DuckDB do not agree on what `'abc' > 5` means. The rules: `string` takes string literals;
  `number` takes numeric literals; `boolean` takes `TRUE`/`FALSE`; `date` takes a string
  parseable as an ISO date. `LIKE` is refused on anything but a `string` dimension, and
  ordering comparisons are refused on `boolean`. `IS NULL` / `IS NOT NULL` carry no value and
  are allowed on every type.

  This is also the first thing in the codebase that reads `type:`, which until now was
  documented as declarative only — `docs/09-data-modeling.md` §3.4 must change with it.

## Q4: `NOT LIKE` is a flag, not a node. How is that handled?

- (a) Walk the predicate by node type and rebuild each node found.
- (b) Read every scalar argument explicitly, and refuse any argument the builder does not
  consume.
- **Chosen:** (b) — decided by the agent from an AST probe run at clarify time, and from the
  amendment in spec 003. sqlglot represents `channel NOT LIKE 'x'` as `Like(negate=True)` —
  the negation is a **bare flag on the node**, not a `Not` wrapper, and the same holds for
  `NOT ILIKE`. A type-driven rebuild that did not read `negate` would emit `LIKE` for a
  request that said `NOT LIKE`: a filter inverted in silence, which is the worst class of bug
  this project recognises. `NOT IN`, `NOT BETWEEN` and `IS NOT NULL` do use a `Not` wrapper,
  so the two representations coexist and both must be handled.

## Q5: Are `NOT IN` and `<>` refused for their NULL behaviour?

- (a) Refuse them, because `NOT IN (…)` drops rows where the column is NULL, which surprises
  people.
- (b) Support them, and document the behaviour.
- **Chosen:** (b) — decided by the agent from the repo's existing stance on the same class of
  trap. `count` already ignores NULLs and the documentation teaches that rather than removing
  the aggregation. The engine's job is to apply what was asked faithfully; standard SQL
  three-valued logic is not a SemantiQL surprise to be papered over, and refusing a predicate
  that behaves exactly as SQL specifies would be a different kind of wrong. It goes in the
  coverage map's trap list alongside `count`.
