---
type: Plan
title: Order and limit a request — plan
description: Extend the select-argument allowlist to order/limit/offset, validate each against the projection list, and rebuild them in the compiler.
resource: specs/005-order-and-limit/plan.md
tags: [sdd, plan, validation, compile]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:16:47+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-15
  - id: validate
    resource: ../src/semantiql/engine/validate.py
    title: _SELECT_ARGS, the predicate IR and walker, Projection, and the check order after specs 003 and 004
    last_modified: 2026-08-16
  - id: compile
    resource: ../src/semantiql/engine/compile.py
    title: How projections, the relation and the predicate are built, and where GROUP BY is attached
    last_modified: 2026-08-16
  - id: compile-tests
    resource: ../tests/test_compile.py
    title: The transpile tripwire and its instruction to replace itself once a dialect renders differently
    last_modified: 2026-08-16
  - id: refusal-tests
    resource: ../tests/test_validation_refuses.py
    title: ExplodingAdapter and the suites the new refusals join
    last_modified: 2026-08-16
  - id: e2e-tests
    resource: ../tests/test_example_end_to_end.py
    title: The hand-computed corpus figures the ordered assertions extend
    last_modified: 2026-08-16
  - id: order-probe
    resource: ../src/semantiql/engine/validate.py
    title: AST probes at plan time over sqlglot 30.17.0 — Ordered/Limit/Offset arguments, nulls_first behaviour, and the T-SQL rendering of LIMIT
    last_modified: 2026-08-16
  - id: coverage-map
    resource: ../docs/09-data-modeling.md
    title: Appendix A.2's ORDER BY / LIMIT rows and section 8's ordering bullet
    last_modified: 2026-08-16
  - id: agents-brief
    resource: ../AGENTS.md
    title: The refused-construct list, which still names ORDER BY and LIMIT
    last_modified: 2026-08-16
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T23:16:47+07:00', checkpoint: 2,
      basis: 'map derived from 7 file reads plus AST probes over sqlglot 30.17.0 covering 10 ordering/limit forms and the cross-dialect rendering; all 6 existing-file rows footnoted; 0 open questions' }
status: stable
---

# Constitution check

- **N1** — ordering and limit resolution happen in `validate`, before any adapter call.[^constitution][^validate]
- **N2** — a dropped `DESC` or `LIMIT` changes what a reader sees, so both are treated as
  answer-bearing. Every argument on an `Ordered` node is read or refused, the rule spec 004
  established for predicates.[^order-probe]
- **N4** — this is the change that makes the claim testable. `LIMIT 5` renders as `SELECT TOP
  5` on T-SQL and as `LIMIT 5` on DuckDB and Postgres, all from one canonical statement, with
  no dialect branching in `compile.py`.[^order-probe][^compile]
- **N3, N5, N6, N7** — untouched.
- **Trust boundary** — `engine/validate.py` and `docs/09-data-modeling.md`, called out in the
  report.[^constitution]

# Approach

Three small additions, each following a pattern the codebase already has.

**Allowlist.** `_SELECT_ARGS` gains `order`, `limit`, `offset` — answerable because the
compiler learns to build them in this same change.[^validate]

**Validation.** An `Ordered` node carries `this`, `desc`, `nulls_first` and `with_fill`; the
first three are read and `with_fill` is refused by the per-node argument check.[^order-probe]
The target must be a `Column` whose name matches a projection's entity **or** its output
alias — an ordinal parses as a `Literal` and an aggregate as a `Sum`, so both fall out as
refusals without needing a special case. `Limit`/`Offset` carry `expression`, which must be a
non-negative integer `Literal`; `LIMIT 1+1` arrives as an `Add` and is refused.

`ValidRequest` gains `order: tuple[OrderKey, ...]`, `limit: int | None`, `offset: int | None`,
where `OrderKey` holds the output name, `desc`, and `nulls_first` — Python values again, so
the compiler rebuilds rather than carries.

**Compilation.** `compile_request` orders by the **output alias**, which is what the caller
named and what both MVP engines accept, then applies `limit` and `offset`. Ordering is
attached after the `GROUP BY` so the canonical statement reads in SQL's own order.

# Architecture decisions

1. **Order by projected names only** — Q1. Refuses ordinals and aggregates as a side effect.
2. **Order by the alias, not a repeated expression.** `ORDER BY revenue DESC` re-states the
   name the caller used; repeating `SUM(amount)` would be equivalent SQL that no longer
   resembles the request, and it would need the aggregate rebuilt in a second place.
3. **`nulls_first` carried through** — Q2.
4. **The tripwire test is replaced, not deleted.** Its docstring asks for exactly that once a
   dialect renders differently; the replacement asserts T-SQL emits `TOP` while DuckDB emits
   `LIMIT`, from one canonical statement.[^compile-tests]

# Repository Impact Map

**Files to modify**

- `src/semantiql/engine/validate.py` — add `order`, `limit`, `offset` to `_SELECT_ARGS`; add
  the `OrderKey` dataclass and the three `ValidRequest` fields; add `_ordering` and
  `_row_count`, with the per-node argument check applied to `Ordered`.[^validate]
- `src/semantiql/engine/compile.py` — attach `order_by`, `limit` and `offset` to the built
  select, ordering by the projection's output name.[^compile]
- `tests/test_compile.py` — **replace** `test_transpiling_is_currently_a_no_op_for_everything_we_emit`
  with a real cross-dialect assertion, and add ordering/limit rendering cases.[^compile-tests]
- `tests/test_validation_refuses.py` — refusals: ordinal, aggregate, unprojected name,
  expression limit, negative limit, `WITH FILL`; all through `run` with `ExplodingAdapter`.[^refusal-tests]
- `tests/test_example_end_to_end.py` — the ranked answer: channels ordered by revenue
  descending are `web, partner, retail`, and `LIMIT 1` returns `web` alone.[^e2e-tests]
- `docs/09-data-modeling.md` — A.2's `ORDER BY` / `LIMIT` / `OFFSET` rows become ✅ with their
  constraints; section 8's "Ordering and limits" bullet is rewritten; the null placement rule
  is stated.[^coverage-map] **Trust-boundary file.**
- `AGENTS.md` — `ORDER BY` and `LIMIT` leave the refused list.[^agents-brief]

**Files to add** — none.

**Files not touched, but adjacent** — `run.py`, the adapters, `knowledge/`, and the README,
none of which describe clause-level behaviour.[^validate]

# Open research questions

None. The probe fixed every node shape the walker must handle, including the cross-dialect
rendering that FR-8 asserts.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N4 and the trust-boundary section.
[^validate]: `src/semantiql/engine/validate.py` — `_SELECT_ARGS`, `_PREDICATE_ARGS`, `Projection`, `ValidRequest`, and the argument-check pattern.
[^compile]: `src/semantiql/engine/compile.py` — `compile_request` builds projections, predicate and GROUP BY, then transpiles once.
[^compile-tests]: `tests/test_compile.py` — the tripwire's docstring: "It is meant to fail the moment the engine starts emitting something dialect-specific … replace it with a real assertion".
[^refusal-tests]: `tests/test_validation_refuses.py` — the refusal suites and `ExplodingAdapter`.
[^e2e-tests]: `tests/test_example_end_to_end.py` — per-channel figures already asserted: web 956.50, partner 385.25, retail 344.49.
[^order-probe]: AST probes over sqlglot 30.17.0 at plan time: `Ordered(this, desc, nulls_first, with_fill)`; `nulls_first` is True only when written; `Limit.expression` is a `Literal` and `LIMIT 1+1` an `Add`; `SELECT a FROM t LIMIT 5` renders as `SELECT TOP 5 a FROM t` on T-SQL.
[^coverage-map]: `docs/09-data-modeling.md` — Appendix A.2 and section 8.
[^agents-brief]: `AGENTS.md` — the refused-construct list in the N1/N2 section.
