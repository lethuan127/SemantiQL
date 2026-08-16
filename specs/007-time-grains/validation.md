---
type: Validation
title: Ask for a date dimension at a coarser grain — validation
description: Acceptance criteria traced to FR-1..FR-7.
resource: specs/007-time-grains/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:36:49+07:00' }
status: stable
---

# Acceptance criteria

- [x] **AC-1** (FR-1): `DATE_TRUNC('month', order_date)` is accepted for each of the five grains.
  - **Proven by:** a parametrized validation case per grain.
- [x] **AC-2** (FR-2): a grained request returns one row per period, named `<dimension>_<grain>`
  unless aliased.
  - **Proven by:** an end-to-end assertion of July 1491.74 and August 194.50, computed from the
    corpus by hand, plus a column-name assertion and an aliased case.
- [x] **AC-3** (FR-3): `MONTH()`, `YEAR()` and `EXTRACT()` are refused, and the message explains
  that they extract rather than truncate.
  - **Proven by:** refusal cases asserting the message names `DATE_TRUNC`.
- [x] **AC-4** (FR-4): an unknown grain, a grain on a non-date dimension, a grain on a measure,
  and a nested argument are each refused.
  - **Proven by:** four refusal cases.
- [x] **AC-5** (FR-5): none of the above reaches the datasource.
  - **Proven by:** every refusal case runs through `run` with `ExplodingAdapter`.
- [x] **AC-6** (FR-6): the existing surface still validates.
  - **Proven by:** the protected-surface suite, unchanged.
- [x] **AC-7** (FR-7): the docs record grains, the refused forms, and the rendering.
  - **Proven by:** reading `docs/09-data-modeling.md` §8, A.5 and the grains subsection.

# Non-functional acceptance

- [x] The repo's verify gate is green: `./scripts/verify.sh`.
- [x] **N2** — the monthly totals are asserted as arithmetic; a year-collapsing form is refused.
- [x] **N4** — the cross-dialect test covers the truncation, showing BigQuery's distinct form.
- [x] No existing check weakened.

# Manual verification

1. `uv run semantiql "SELECT revenue, DATE_TRUNC('month', order_date) FROM orders" --show-sql`
   — expect two rows, July and August, and a repeated `DATE_TRUNC` in the SQL.
2. `uv run semantiql "SELECT revenue, MONTH(order_date) FROM orders"` — expect a refusal that
   names `DATE_TRUNC`.
3. `uv run semantiql "SELECT revenue, DATE_TRUNC('fortnight', order_date) FROM orders"` —
   expect a refusal listing the grains.
