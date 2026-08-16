---
type: Spec
title: Derived metrics in the semantic model
description: Let the model define a number built from its measures — ratios and shares — with a closed expression grammar and a guarded divisor
resource: specs/006-derived-metrics/spec.md
tags: [sdd, spec, knowledge, compile]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:26:51+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-15
  - id: architecture
    resource: ../docs/02-architecture.md
    title: Layer 1 described as "dimensions, measures, metrics, virtual views" — metrics being the gap this closes
    last_modified: 2026-08-15
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T23:26:51+07:00', checkpoint: 1,
      basis: '8 FRs, each testable; FR-4 written from a probe showing DuckDB returns inf for 1/0 while Postgres raises, so the guard is required rather than defensive; NFRs bind to N2, N3 and N4' }
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** The change adds a construct to the semantic model — the artifact every other layer
resolves against — and touches the compiler.

# What

A table may define **metrics**: numbers derived from its measures.

```yaml
metrics:
  revenue_per_order:
    expression: revenue / order_count
    description: Revenue divided by orders. The sanctioned way to state it.
```

A request selects a metric exactly as it selects a measure, and grouping works the same way:
`SELECT revenue_per_order, channel FROM orders` gives the ratio within each channel.

Today the model has no such thing. A number that is one column and one aggregation can be
defined; a number that is one measure divided by another cannot be defined at all, in the
model or in a query. The README and [02-architecture.md](../../docs/02-architecture.md) both
describe layer 1 as "dimensions, measures, metrics, virtual views", so this closes a gap
between what the project says it is and what it does.[^architecture]

# Why

Most of what a business actually watches is a ratio: revenue per order, conversion rate,
margin percentage, cost per acquisition. None of them can be expressed today, and the two
workarounds are both bad. Asking for the parts and dividing them in the client puts the
definition of a business number outside the model, which is the one thing this project exists
to prevent. Pre-computing the ratio in a database view hides it from the diffable YAML and
gets it wrong the moment the request groups by something.

That last point is the substance. A ratio must be computed **after** grouping, from the
grouped parts — revenue per order for the web channel is that channel's revenue over that
channel's orders. A ratio averaged from pre-computed row-level ratios is a different, wrong
number, and nothing in the answer would show it.

There is also a correctness hazard specific to this feature. On DuckDB, dividing by zero
returns `inf`; on Postgres it raises. So the same model, unguarded, gives a nonsense number on
one engine and an error on the other — and `inf` in a report is exactly the plausible-looking
wrong answer N2 names.

# User stories

- **As an analyst**, I define revenue per order once, in the model — so every answer uses the
  same definition and a reviewer can see it in a diff.
- **As a business user**, I ask for revenue per order by channel and get each channel's own
  ratio — not an average of averages.
- **As a reader of a report**, a period with no orders shows no value rather than `inf` — so
  nothing meaningless is presented as a figure.

# Functional requirements

- **FR-1** — A table may declare `metrics:`, each with an `expression` and optional `label`
  and `description`.
- **FR-2** — A request may select a metric wherever it may select a measure. A request
  selecting only metrics satisfies the rule that a request must compute a number, and
  selecting a metric alongside dimensions groups the same way a measure does.
- **FR-3** — The expression grammar is closed: measure names of the same table, numeric
  literals, `+`, `-`, `*`, `/`, unary minus, and parentheses. A function, a raw aggregate, a
  column, a dimension, another metric, or an unknown name is rejected **when the model
  loads**, naming what was wrong.
- **FR-4** — Division is guarded: a zero divisor yields no value rather than `inf`, an error,
  or an engine-dependent result.
- **FR-5** — A name is at most one of dimension, measure, or metric on a table; any overlap is
  rejected at load, extending the existing rule.
- **FR-6** — Filtering on a metric is refused as it is for a measure. Ordering by a metric the
  request selects works as it does for a measure.
- **FR-7** — Every request answerable before this change is still answered, unchanged.
- **FR-8** — The bundled example gains a metric, and the documentation records metrics as
  supported — including why a ratio is computed after grouping.

# Non-functional requirements

- **N2 (a silently wrong number is the worst failure)** — the two hazards here are `inf` from
  a zero divisor and a ratio computed at the wrong grain. Both are addressed by construction,
  and both get a test that asserts the arithmetic rather than the SQL.[^constitution]
- **N3 (the YAML is the source of truth)** — a metric is a definition, so it lives in the
  model and nowhere else. A malformed expression fails at load, loudly, rather than at query
  time.[^constitution]
- **N4 (canonical dialect, then transpile)** — the guarded division is built canonically and
  transpiled; no engine-specific spelling enters the compiler.[^constitution]

# Out of scope

- **A metric referencing another metric.** Measures only, so there are no cycles to detect;
  refused with a message that says so.
- **Aggregations inside an expression** — `SUM(amount) / 2` — which would move the choice of
  aggregation out of the measure layer.
- **Window functions, period comparison, and share-of-total**, all of which need `OVER`.
- **Formatting** — a metric is a number, not a percentage sign.

[^constitution]: `.specify/memory/constitution.md` — N2, N3, N4.
[^architecture]: `docs/02-architecture.md` — layer 1's description, which names metrics.
