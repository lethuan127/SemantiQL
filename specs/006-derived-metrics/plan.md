---
type: Plan
title: Derived metrics in the semantic model — plan
description: Parse each metric expression at load into a small IR under a closed grammar, and have the compiler build a guarded aggregate expression from it.
resource: specs/006-derived-metrics/plan.md
tags: [sdd, plan, knowledge, compile]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:26:51+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-15
  - id: model
    resource: ../src/semantiql/knowledge/model.py
    title: Dimension/Measure/Table/SemanticModel, the _Strict base, entity(), entity_names, and the existing dimension-vs-measure clash validator
    last_modified: 2026-08-15
  - id: loader
    resource: ../src/semantiql/knowledge/loader.py
    title: The single reader of the YAML, its ModelError message shape, and that pydantic validation errors surface field-level
    last_modified: 2026-08-15
  - id: validate
    resource: ../src/semantiql/engine/validate.py
    title: Where projections resolve to measures or dimensions, the no-measure rule, filter resolution, and ordering over projections
    last_modified: 2026-08-16
  - id: compile
    resource: ../src/semantiql/engine/compile.py
    title: _aggregate and the _AGG map, and how projections become aliased expressions
    last_modified: 2026-08-16
  - id: example
    resource: ../examples/retail/semantic_model.yml
    title: The bundled model a metric is added to, and its existing avg measure
    last_modified: 2026-08-15
  - id: e2e-tests
    resource: ../tests/test_example_end_to_end.py
    title: Hand-computed corpus figures the metric assertions extend
    last_modified: 2026-08-16
  - id: metric-probe
    resource: ../src/semantiql/knowledge/model.py
    title: Probes at plan time — DuckDB evaluates 1/0 to inf while NULLIF yields NULL, and sqlglot parses each candidate expression into Div/Mul/Add/Sub/Paren/Neg/Column/Literal
    last_modified: 2026-08-16
  - id: coverage-map
    resource: ../docs/09-data-modeling.md
    title: Section 3, section 8's "derived or ratio metrics" bullet, and Appendix A.4
    last_modified: 2026-08-16
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T23:26:51+07:00', checkpoint: 2,
      basis: 'map derived from 7 file reads plus probes of DuckDB division semantics and sqlglot expression parsing; all 7 existing-file rows footnoted; 1 new module justified in the approach; 0 open questions' }
status: stable
---

# Constitution check

- **N2** — two hazards, both structural rather than advisory: `inf` from a zero divisor is
  removed by guarding every division, and a ratio at the wrong grain is impossible because the
  metric is built from the *aggregates*, so grouping applies to the parts before the
  division.[^metric-probe]
- **N3** — a metric is a definition and lives only in the YAML. Loading parses and resolves
  every expression, so a malformed one fails at load with a field-level message, matching what
  `knowledge/model.py` already promises.[^model][^loader]
- **N4** — the guarded division is built canonically and transpiled. Worth recording: sqlglot
  already renders `SUM(a)/NULLIF(COUNT(b),0)` for Postgres as a `CAST(… AS DOUBLE PRECISION)`
  division, handling integer-division semantics the compiler never has to know about.[^metric-probe]
- **N1, N5, N6, N7** — untouched.
- **Trust boundary** — the semantic model's schema is named by the constitution as a
  trust-boundary artifact, and `docs/NN-*.md` changes too. Both called out in the report.[^constitution]

# Approach

**A metric is an expression over measures, parsed once.** `knowledge/expression.py` (new)
holds a small IR — `Ref(measure)`, `Num(value)`, `BinOp(op, left, right)`, `Neg(operand)` —
and `parse_expression(text, measures)`, which parses with sqlglot and walks the result under a
node allowlist: `Div`, `Mul`, `Add`, `Sub`, `Paren`, `Neg`, `Column`, `Literal`. Anything
else — a function, a raw `SUM(...)`, an unknown name — raises `ExpressionError` naming
it.[^metric-probe]

Parsing text is normally what this codebase refuses to do, so the difference is worth stating:
this text comes from the model file in git, not from a caller; it is parsed **once at load**,
under a closed grammar, into an IR that the compiler builds from. No caller-supplied string is
ever parsed, and the compiler still constructs every node it emits.

**Where it hooks in.** `Metric` joins `Dimension` and `Measure` in `model.py`; `Table` gains
`metrics`, extends the name-clash validator to three-way, and validates each expression in its
`model_validator` — the only place with both the metrics and the measures in hand.[^model]
`entity()` and `entity_names` learn about metrics, which is what makes suggestions and the
"not defined" refusal cover them for free.[^model]

**Engine.** `validate` treats a metric like a measure: selecting one satisfies the
must-compute-a-number rule, and it does not become a `GROUP BY` key. Filtering on one is
refused with the measure message. Ordering by one works already, because ordering resolves
against projections rather than against the model.[^validate]

`compile` gains `_metric`, which walks the IR and substitutes each `Ref` with that measure's
sanctioned aggregation — the existing `_aggregate` logic, reused — then wraps every divisor in
`NULLIF(divisor, 0)`.[^compile] The result is one aliased expression in the projection list,
so grouping applies to the parts and the division happens after it.

# Architecture decisions

1. **Expression string, closed grammar, parsed at load** — Q1 and Q4.
2. **Guard every division, not only the ones that look risky.** `NULLIF(d, 0)` on each
   divisor. A divisor that is a literal zero is refused at load instead.
3. **Metrics compose from measures only** — Q3.
4. **A metric is not a measure.** They are separate mappings in the YAML and separate fields on
   `Table`, because a measure carries `column` + `agg` and a metric carries an expression;
   collapsing them would make both fields optional on one type and admit a nonsense model that
   declares neither.

# Repository Impact Map

**Files to modify**

- `src/semantiql/knowledge/model.py` — add `Metric`; add `metrics` to `Table`; extend the
  clash validator from two-way to three-way; validate each expression in the table validator;
  teach `entity()` and `entity_names` about metrics.[^model]
- `src/semantiql/engine/validate.py` — count a metric as computing a number, keep it out of the
  `GROUP BY` set, and refuse filtering on one with the measure message.[^validate]
- `src/semantiql/engine/compile.py` — add `_metric`, reuse `_aggregate` per referenced measure,
  guard divisors.[^compile]
- `examples/retail/semantic_model.yml` — add `revenue_per_order`.[^example]
- `tests/test_loader.py` — a bad expression, an unknown name, a metric/measure clash, a
  literal-zero divisor.
- `tests/test_compile.py` — the emitted expression, and the guard.
- `tests/test_example_end_to_end.py` — the ratio per channel, computed by hand, and a filtered
  case whose denominator is zero returning no value.[^e2e-tests]
- `tests/test_validation_refuses.py` — filtering on a metric is refused.
- `docs/09-data-modeling.md` — a metrics section, A.4's note that only six aggregations exist
  gains the metric escape hatch, section 8's "derived or ratio metrics" bullet is
  rewritten.[^coverage-map] **Trust-boundary file.**
- `AGENTS.md`, `README.md` — the model is now "dimensions, measures, metrics" in code as well
  as in prose.

**Files to add**

- `src/semantiql/knowledge/expression.py` — the metric expression IR, its parser, and
  `ExpressionError`. A new module rather than more of `model.py`, because it is the only part
  of layer 1 that touches sqlglot and it is the piece the compiler imports.

**Files not touched, but adjacent** — `loader.py` needs no change: a `ValueError` raised in a
table validator already surfaces as a field-level `ModelError`.[^loader] Adapters and `run.py`
are untouched.

# Open research questions

None. Both probes resolved the open behaviour: division semantics per engine, and the exact
node set the grammar must admit.

[^constitution]: `.specify/memory/constitution.md` — N2, N3, N4 and the trust-boundary section naming the semantic model's schema.
[^model]: `src/semantiql/knowledge/model.py` — `_Strict`, `Dimension`, `Measure`, `Table._names_must_not_overlap`, `entity`, `entity_names`.
[^loader]: `src/semantiql/knowledge/loader.py` — `load_model` turns a pydantic `ValidationError` into a `ModelError` naming the field path.
[^validate]: `src/semantiql/engine/validate.py` — projection resolution, the no-measure refusal, `_filtered_dimension`, and `_ordering` resolving against projections.
[^compile]: `src/semantiql/engine/compile.py` — `_AGG`, `_aggregate`, and the projection loop.
[^example]: `examples/retail/semantic_model.yml` — measures `revenue`, `order_count`, `average_order_value`.
[^e2e-tests]: `tests/test_example_end_to_end.py` — the hand-computed corpus pattern.
[^metric-probe]: Probes at plan time: DuckDB `SELECT 1/0` → `inf`, `SELECT 1/NULLIF(0,0)` → NULL; sqlglot parses the candidate expressions into `Div`/`Mul`/`Add`/`Sub`/`Paren`/`Neg`/`Column`/`Literal`, and renders `SUM(a)/NULLIF(COUNT(b),0)` on Postgres with an explicit double-precision cast.
[^coverage-map]: `docs/09-data-modeling.md` — section 3's field reference, section 8, Appendix A.4.
