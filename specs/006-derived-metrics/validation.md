---
type: Validation
title: Derived metrics in the semantic model — validation
description: Acceptance criteria traced to FR-1..FR-8.
resource: specs/006-derived-metrics/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:26:51+07:00' }
status: stable
---

# Acceptance criteria

- [x] **AC-1** (FR-1): a model declaring `metrics:` loads, and the metric is addressable.
  - **Proven by:** the bundled example gains `revenue_per_order`, and a loader test reads it.
- [x] **AC-2** (FR-2): a metric may be selected wherever a measure may be, alone or with
  dimensions, and grouping applies to the parts.
  - **Proven by:** an end-to-end assertion that the ratio per channel equals that channel's
    revenue over that channel's orders — computed by hand, not read from output.
- [x] **AC-3** (FR-3): the grammar is closed and enforced at load.
  - **Proven by:** loader tests for a function, a raw aggregate, an unknown name, a dimension
    reference, and a metric reference — each raising `ModelError` naming the offender.
- [x] **AC-4** (FR-4): a zero divisor yields no value.
  - **Proven by:** a compile assertion that the divisor is guarded, and an end-to-end query
    whose filter leaves no rows returning `None` rather than `inf` or an error.
- [x] **AC-5** (FR-5): a name used twice across dimensions/measures/metrics fails to load.
  - **Proven by:** a loader test per overlapping pair.
- [x] **AC-6** (FR-6): filtering on a metric is refused; ordering by a selected metric works.
  - **Proven by:** a refusal case via `ExplodingAdapter`, and an ordering case.
- [x] **AC-7** (FR-7): the existing surface is unchanged.
  - **Proven by:** the existing suites, green and unmodified.
- [x] **AC-8** (FR-8): the docs record metrics, including the after-grouping rule.
  - **Proven by:** reading `docs/09-data-modeling.md` §3, §8 and A.4.

# Non-functional acceptance

- [x] The repo's verify gate is green: `./scripts/verify.sh`.
- [x] **N2** — the ratio and the zero-divisor cases assert arithmetic, not SQL text.
- [x] **N3** — no metric value is computed anywhere but from the YAML definition.
- [x] **N4** — no engine-specific spelling in `compile.py`; the grep still matches only
  `adapters.base`.

# Manual verification

1. `uv run semantiql "SELECT revenue_per_order, channel FROM orders" --show-sql` — expect a
   guarded division per channel.
2. `uv run semantiql "SELECT revenue_per_order FROM orders WHERE channel = 'nothing'"` —
   expect an empty value, not `inf`.
3. `uv run semantiql "SELECT revenue FROM orders WHERE revenue_per_order > 1"` — expect a
   refusal.
