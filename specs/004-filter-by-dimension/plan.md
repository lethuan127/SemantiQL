---
type: Plan
title: Filter a request by its dimensions — plan
description: Validate the WHERE into a neutral predicate IR, then rebuild it in the compiler from the model — nothing the caller wrote reaches the database.
resource: specs/004-filter-by-dimension/plan.md
tags: [sdd, plan, validation, compile]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T22:45:37+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-15
  - id: validate
    resource: ../src/semantiql/engine/validate.py
    title: The allowlists, the refusal helpers, ValidRequest, and the check order after spec 003
    last_modified: 2026-08-16
  - id: compile
    resource: ../src/semantiql/engine/compile.py
    title: How projections and the relation are built — expressions constructed, never parsed
    last_modified: 2026-08-15
  - id: model
    resource: ../src/semantiql/knowledge/model.py
    title: Dimension.type, the four allowed values, and that nothing reads it yet
    last_modified: 2026-08-15
  - id: refusal-tests
    resource: ../tests/test_validation_refuses.py
    title: ExplodingAdapter and the parametrized suites the new refusals join
    last_modified: 2026-08-16
  - id: compile-tests
    resource: ../tests/test_compile.py
    title: The relation-injection regression and the transpile tripwire this change must not break
    last_modified: 2026-08-15
  - id: e2e-tests
    resource: ../tests/test_example_end_to_end.py
    title: Hand-computed figures over examples/retail/orders.csv the filtered assertions extend
    last_modified: 2026-08-15
  - id: corpus
    resource: ../examples/retail/orders.csv
    title: The ten rows the expected filtered totals are computed from
    last_modified: 2026-08-15
  - id: predicate-probe
    resource: ../src/semantiql/engine/validate.py
    title: AST probes at plan time over sqlglot 30.17.0 — node types and scalar flags for all 18 predicate forms in FR-2 and FR-5
    last_modified: 2026-08-16
  - id: coverage-map
    resource: ../docs/09-data-modeling.md
    title: Appendix A, section 8, and section 3.4's claim that `type:` is declarative only
    last_modified: 2026-08-16
  - id: agents-brief
    resource: ../AGENTS.md
    title: The invariants section listing WHERE among the refused clauses
    last_modified: 2026-08-16
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T22:45:37+07:00', checkpoint: 2,
      basis: 'map derived from 9 file reads plus two AST probes over sqlglot 30.17.0 covering 18 predicate forms; all 7 existing-file rows footnoted; the 5 expected filtered totals recomputed from examples/retail/orders.csv rather than asserted from memory; 0 open questions' }
status: stable
---

# Constitution check

- **N1 — validation over generation.** Filters are resolved and typed in `validate`, before
  `run` touches an adapter. A refused filter never reaches the datasource, tested with
  `ExplodingAdapter`.[^constitution][^refusal-tests]
- **N2 — a silently wrong number is the worst failure.** Two hazards, both named and handled:
  a predicate the validator does not fully understand must be refused rather than partly
  applied, and a negation carried as a **scalar flag** (`Like(negate=True)`) must not be
  dropped during the rebuild — that would invert a filter in silence.[^predicate-probe]
- **N3 — the YAML is the source of truth.** Filters address dimensions by their model names;
  physical column names appear only when the compiler substitutes them.[^constitution]
- **N4 — canonical dialect, then transpile.** Predicates are built as canonical sqlglot
  expressions and transpiled with the rest of the statement. Date literals become an explicit
  `CAST(… AS DATE)` rather than relying on each engine's implicit coercion.[^constitution]
- **N5 — read-only.** A predicate cannot introduce a write; the statement-type refusal is
  untouched.
- **Trust boundary.** `engine/validate.py` and `docs/09-data-modeling.md` again. Called out
  explicitly in the run report.[^constitution]

No invariant needs amending. Note that `where` joining `_SELECT_ARGS` is the allowlist working
as designed, not a weakening of it: spec 003's rule is that a construct becomes answerable
**in the change that teaches the compiler to honour it**, which is this change.[^validate]

# Approach

Three pieces, in the order the data flows.

**1. A neutral predicate IR** (`validate.py`). Validation produces typed dataclasses rather
than handing on sqlglot nodes (Q1):

```
Predicate = Comparison | BoolOp | Negation
Comparison(dimension: str, operator: str, values: tuple[str|float|bool|date, ...])
BoolOp(op: "and"|"or", operands: tuple[Predicate, ...])
Negation(operand: Predicate)
```

`ValidRequest` gains `filter: Predicate | None`. Because the IR holds *model* names and
*Python* values, nothing the caller wrote survives into compilation — the compiler cannot
accidentally carry an argument the validator never inspected.

**2. Validation of the WHERE subtree** (`validate.py`). The same allowlist discipline as spec
003, applied to predicates. An AST probe at plan time over sqlglot 30.17.0 gives the exact
node set:[^predicate-probe]

| Form | Parses as | Notes |
|---|---|---|
| `=`, `<>`/`!=`, `<`, `<=`, `>`, `>=` | `EQ`, `NEQ`, `LT`, `LTE`, `GT`, `GTE` | column on one side, literal on the other |
| `IN (…)`, `NOT IN (…)` | `In`, wrapped in `Not` | |
| `BETWEEN a AND b`, `NOT BETWEEN` | `Between`, wrapped in `Not` | |
| `LIKE`, `NOT LIKE` | `Like` — negation is **`negate=True`, a scalar flag** | the hazard above |
| `IS NULL`, `IS NOT NULL` | `Is` with `Null`, wrapped in `Not` | |
| `AND`, `OR`, `NOT`, parentheses | `And`, `Or`, `Not`, `Paren` | `Paren` is unwrapped, not honoured as a node |
| refused | `Upper`/any function, `Add`/arithmetic, `Subquery`, `Column` on both sides | |

Each `Comparison` must name a **dimension** of the request's table. A measure is refused with
a message that says measure filters need `HAVING` and are not supported; an unknown name gets
the existing did-you-mean suggestion. Literals are checked against the dimension's declared
`type` (Q3), which makes this the first code in the repo to read that field.

Every node is checked for unconsumed arguments, exactly as `_FROM_NODE_ARGS` does, so a flag
like `negate` cannot be silently ignored — it is either read by the builder or it refuses.

**3. Rebuilding in the compiler** (`compile.py`). `_predicate(pred, table)` walks the IR and
constructs `exp.EQ`, `exp.In`, `exp.Between`, `exp.Like(negate=…)`, `exp.Is`, `exp.And`,
`exp.Or`, `exp.Not` over `exp.column(dimension.column)` and freshly built literals: strings via
`exp.Literal.string`, numbers via `exp.Literal.number`, booleans via `exp.Boolean`, dates via
`exp.cast(exp.Literal.string(...), "date")`. The result is attached with `select.where(...)`.

Because every literal is built rather than interpolated, a value containing a quote is escaped
by sqlglot — the same property `tests/test_compile.py` already asserts for a hostile `source`,
and the new suite asserts it for a hostile filter value.[^compile-tests]

# Architecture decisions

1. **Neutral IR over AST reuse** — Q1. Makes FR-6 structural.
2. **Explicit `CAST(… AS DATE)`** — Q2. Portability over brevity.
3. **`type:` becomes load-bearing** — Q3. Documented as declarative until now, so the docs
   change in the same commit as the behaviour.
4. **Both negation representations handled** — Q4. `negate` flags and `Not` wrappers.
5. **Filters are independent of projections.** `SELECT revenue FROM orders WHERE channel =
   'web'` is a single-row answer; filtering on a dimension does not add it to the `GROUP BY`,
   because grouping is driven by what was *selected*. This preserves the existing rule rather
   than introducing a second one.

# Repository Impact Map

**Files to modify**

- `src/semantiql/engine/validate.py` — add `"where"` to `_SELECT_ARGS`; add the `Comparison` /
  `BoolOp` / `Negation` dataclasses and `Predicate`; add `filter` to `ValidRequest`; add the
  predicate walker with its operator table, per-node argument check, dimension resolution and
  literal typing; extend `_NODE_LABELS`/`_CLAUSE_LABELS` where a predicate refusal needs a
  name.[^validate]
- `src/semantiql/engine/compile.py` — add `_predicate` and `_literal`; attach the built
  predicate with `select.where(...)` before the `GROUP BY` is added.[^compile]
- `tests/test_validation_refuses.py` — refusals: measure in a filter, unknown name in a
  filter, function, arithmetic, subquery, column-to-column, type mismatch per dimension type,
  `LIKE` on a non-string dimension; each through `run` with `ExplodingAdapter`.[^refusal-tests]
- `tests/test_compile.py` — `NOT LIKE` keeps its negation; a date literal renders as a cast; a
  hostile filter value cannot add structure to the query.[^compile-tests]
- `tests/test_example_end_to_end.py` — hand-computed filtered figures over the ten-row
  corpus: `channel = 'web'` → 956.50; July only → 1491.74; July **and** web → 826.50;
  `channel IN ('web','retail')` → 1300.99; `region = 'north'` → 690.74. Each figure was
  recomputed from the corpus at plan time.[^corpus] The suite's existing pattern is
  unchanged.[^e2e-tests]
- `docs/09-data-modeling.md` — §3.4 loses the "declarative only" warning for `type:`; §8's
  "Filters of any kind" bullet is rewritten; A.2's `WHERE` row becomes ✅ with its predicate
  set; A.5 gains the supported operators; A.6 records `where` joining the allowlist; the
  `NOT IN` NULL trap joins the trap list.[^coverage-map] **Trust-boundary file.**
- `AGENTS.md` — `WHERE` moves out of the refused-clause list, with the dimension-only and
  typed-literal constraints stated.[^agents-brief]

**Files to add**

- None.

**Files not touched, but adjacent**

- `src/semantiql/knowledge/model.py` — `Dimension.type` already exists with the four values
  this change needs; no model change is required.[^model]
- `src/semantiql/engine/run.py` — the chokepoint is unchanged; `ValidRequest` simply carries
  more.[^validate]
- `src/semantiql/adapters/*` — unchanged; adapters still receive a finished SQL string.
- `README.md` — lists no clause-level detail, so nothing there goes stale.

# Open research questions

None outstanding. Q1–Q5 were each resolved from evidence, and the predicate probe fixes the
node set the walker must accept, so no part of the file list depends on an unresolved
question.

[^constitution]: `.specify/memory/constitution.md` — N1–N5 and the trust-boundary artifacts section.
[^validate]: `src/semantiql/engine/validate.py` — `_SELECT_ARGS`, `_FROM_NODE_ARGS`, `_unsupported`, `_suggest`, `ValidRequest`, and the check order established by spec 003.
[^compile]: `src/semantiql/engine/compile.py` — `compile_request` builds projections and takes the relation as a built expression; the same construction discipline applies to predicates.
[^model]: `src/semantiql/knowledge/model.py` — `Dimension.type` is `string | date | number | boolean`, defaulting to `string`, and no code reads it today.
[^refusal-tests]: `tests/test_validation_refuses.py` — `ExplodingAdapter`, the silent-drop suite, and the protected-surface suite.
[^compile-tests]: `tests/test_compile.py` — `test_relation_is_never_reparsed` and the transpile tripwire.
[^e2e-tests]: `tests/test_example_end_to_end.py` — the pattern of asserting hand-computed figures.
[^corpus]: `examples/retail/orders.csv` — ten rows; the filtered totals above were computed from them by hand.
[^coverage-map]: `docs/09-data-modeling.md` — section 3.4's "declarative only" warning on `type:`, section 8's filters bullet, and Appendix A.2 / A.5 / A.6.
[^predicate-probe]: AST probes over sqlglot 30.17.0 run at plan time: node types for all supported and refused predicate forms, and the scalar-flag check that found `Like(negate=True)` and `ILike(negate=True)`.
[^agents-brief]: `AGENTS.md` — the N1/N2 section listing the refused clauses.
