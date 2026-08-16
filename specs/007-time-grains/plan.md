---
type: Plan
title: Ask for a date dimension at a coarser grain — plan
description: Admit one function into projections under a closed grain vocabulary, carry the grain on the projection IR, and build the truncation in the compiler.
resource: specs/007-time-grains/plan.md
tags: [sdd, plan, validation, compile]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:36:49+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-15
  - id: validate
    resource: ../src/semantiql/engine/validate.py
    title: _projections and its SemanticSyntaxError message, Projection, the dimension/measure split, and _ordering resolving against projections
    last_modified: 2026-08-16
  - id: compile
    resource: ../src/semantiql/engine/compile.py
    title: The projection loop and the GROUP BY loop that currently reads request.dimensions
    last_modified: 2026-08-16
  - id: model
    resource: ../src/semantiql/knowledge/model.py
    title: "Dimension.type, which authorises a grain"
    last_modified: 2026-08-16
  - id: compile-tests
    resource: ../tests/test_compile.py
    title: The cross-dialect transpile assertion this change strengthens
    last_modified: 2026-08-16
  - id: e2e-tests
    resource: ../tests/test_example_end_to_end.py
    title: The corpus, whose ten rows span July and August 2026 — enough for a real month split
    last_modified: 2026-08-16
  - id: corpus
    resource: ../examples/retail/orders.csv
    title: Order dates from 2026-07-02 to 2026-08-03, the basis for the expected monthly totals
    last_modified: 2026-08-15
  - id: grain-probe
    resource: ../src/semantiql/engine/validate.py
    title: Probes at plan time — DATE_TRUNC parses to TimestampTrunc(this, unit), renders five ways across dialects, and MONTH() returns 7 for both July 2025 and July 2026
    last_modified: 2026-08-16
  - id: coverage-map
    resource: ../docs/09-data-modeling.md
    title: "Appendix A.5 date-function row, section 8 time-grain bullet, and section 3.4 on the type field"
    last_modified: 2026-08-16
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T23:36:49+07:00', checkpoint: 2,
      basis: 'map derived from 6 file reads plus probes of parse shape, cross-dialect rendering and MONTH() semantics; all 6 existing-file rows footnoted; expected monthly totals recomputed from the corpus; 0 open questions' }
status: stable
---

# Constitution check

- **N2** — the hazard is the year-collapsing spelling, and it is refused rather than
  approximated. The grain vocabulary is closed, so an unrecognised unit refuses instead of
  reaching the engine as text.[^grain-probe]
- **N4** — one canonical `DATE_TRUNC`, five renderings. This is a materially stronger
  demonstration than `LIMIT`, and the existing cross-dialect test grows to cover it.[^grain-probe][^compile-tests]
- **N3** — the model still authorises: only a dimension declared `type: date` may be
  truncated, so the grain cannot be applied to something the model never said was a date.[^model]
- **N1, N5** — unchanged.
- **Trust boundary** — `engine/validate.py` and `docs/09-data-modeling.md`.[^constitution]

# Approach

**The projection IR gains a grain.** `Projection(entity, output)` becomes
`Projection(entity, output, grain=None)`, and everything else follows from that one field: a
grained projection is still a dimension, still groups, still orders by its output name.[^validate]

**Validation.** `_projections` currently admits a bare `Column` or an `Alias` over one. It
gains a third shape: `TimestampTrunc(this=Column, unit=Var)` — what sqlglot parses
`DATE_TRUNC('month', d)` into — with its arguments checked against `{this, unit}` so a time
zone or any future argument refuses rather than being dropped.[^grain-probe] The unit is
lower-cased and looked up in a closed vocabulary; the column must resolve to a dimension whose
`type` is `date`. The default output name is `<dimension>_<grain>`.

The year-collapsing forms are refused by name. `exp.Month`, `exp.Year`, `exp.Quarter`,
`exp.Day`, `exp.Week` and `exp.Extract` get a dedicated message rather than the generic "must
be a plain dimension or measure name", because the generic one would send a caller looking for
a typo when the real problem is that the function means something else.[^validate]

**Compilation.** A grained dimension projects as `exp.TimestampTrunc(this=column,
unit=exp.var(grain))` and the *same expression* is repeated in the `GROUP BY` (Q4). The
grouping loop moves from iterating `request.dimensions` — a tuple of names, which cannot carry
a grain — to iterating the dimension projections themselves, preserving order.[^compile]

# Architecture decisions

1. **One function, closed vocabulary** — Q1, Q2. This is the first function admitted into a
   projection; the allowlist is the grain names, and the argument must be a plain dimension.
2. **Refuse the extract forms with a specific message** — Q2. A refusal that explains beats a
   refusal that merely declines.
3. **Group by the expression, order by the alias** — Q4, and consistent with spec 005: aliases
   in `ORDER BY` are portable, aliases in `GROUP BY` are not.
4. **`grain` on `Projection` rather than a parallel structure.** Keeps one list as the single
   description of what the request selects, so ordering and the measure/dimension split need no
   changes at all.

# Repository Impact Map

**Files to modify**

- `src/semantiql/engine/validate.py` — add the grain vocabulary and `_TRUNC_ARGS`; add `grain`
  to `Projection`; extend `_projections` with the truncation shape, the extract-form refusal,
  and the date-type check.[^validate]
- `src/semantiql/engine/compile.py` — build the truncation for a grained projection and group
  by the expression; the grouping loop reads projections rather than `request.dimensions`.[^compile]
- `tests/test_validation_refuses.py` — refusals: `MONTH()`, `EXTRACT()`, an unknown grain, a
  grain on a string dimension, a grain on a measure, a nested argument.
- `tests/test_compile.py` — the rendering, the repeated `GROUP BY` expression, and the
  cross-dialect assertion extended to BigQuery's `TIMESTAMP_TRUNC` form.[^compile-tests]
- `tests/test_example_end_to_end.py` — monthly totals over the corpus: July 1491.74, August
  194.50, recomputed from the ten rows at plan time.[^corpus] The suite's pattern is
  unchanged.[^e2e-tests]
- `docs/09-data-modeling.md` — A.5's date row, section 8's time-grain bullet, and a grains
  subsection with the `MONTH()` hazard spelled out.[^coverage-map] **Trust-boundary file.**
- `AGENTS.md` — the supported-construct summary.

**Files to add** — none.

**Files not touched, but adjacent** — `knowledge/`, `run.py` and the adapters. A grain is a
request-shape change, so layer 1 needs nothing new.[^model]

# Open research questions

None. The probes fixed the parse shape, the rendering per dialect, and the semantics that
justify the refusal.

[^constitution]: `.specify/memory/constitution.md` — N1–N5 and the trust-boundary section.
[^validate]: `src/semantiql/engine/validate.py` — `Projection`, `_projections`, the entity split, `_ordering`.
[^compile]: `src/semantiql/engine/compile.py` — the projection loop and the `request.dimensions` grouping loop.
[^model]: `src/semantiql/knowledge/model.py` — `Dimension.type`, enforced for filters since spec 004.
[^compile-tests]: `tests/test_compile.py` — `test_transpiling_actually_changes_the_sql`.
[^e2e-tests]: `tests/test_example_end_to_end.py` — the hand-computed corpus pattern.
[^corpus]: `examples/retail/orders.csv` — eight July rows and two August rows.
[^grain-probe]: Probes over sqlglot 30.17.0 and DuckDB at plan time: `DATE_TRUNC('month', d)` → `TimestampTrunc(this=Column, unit=Var)`; renders as `TIMESTAMP_TRUNC(d, MONTH)` on BigQuery, `DATETRUNC(MONTH, d)` on T-SQL, `DATE_ADD`/`TIMESTAMPDIFF` on MySQL; `MONTH(DATE '2026-07-15')` and `MONTH(DATE '2025-07-02')` both return 7.
[^coverage-map]: `docs/09-data-modeling.md` — Appendix A.5, section 8, section 3.4.
