---
type: Spec
title: Ask for a date dimension at a coarser grain
description: DATE_TRUNC over a date dimension — by month, quarter, year — with the year-collapsing forms refused
resource: specs/007-time-grains/spec.md
tags: [sdd, spec, validation, compile]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:36:49+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-15
  - id: filters
    resource: ../specs/004-filter-by-dimension/spec.md
    title: "The spec that made `type: date` load-bearing, which this extends"
    last_modified: 2026-08-16
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T23:36:49+07:00', checkpoint: 1,
      basis: '7 FRs, each testable; FR-3 written from a probe showing MONTH() returns 7 for both July 2025 and July 2026, so refusing it prevents a silent year collapse; NFRs bind to N2 and N4' }
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** The change edits the query-validation layer and admits the first function into a
projection, so the grammar it opens has to be closed precisely.

# What

A request may ask for a date dimension at a coarser grain:

```
SELECT revenue, DATE_TRUNC('month', order_date) FROM orders
```

Revenue by month, with each month a real month — July 2026 distinct from July 2025. The
grains are `year`, `quarter`, `month`, `week` and `day`, and the argument must be a dimension
the model declares as `type: date`.

Today no grain exists. A `date` dimension groups by the exact date only, so "revenue by month"
over a year of data returns three hundred rows instead of twelve, and the caller must
aggregate them itself — which puts the arithmetic outside the layer that is supposed to own it.

# Why

Nearly every report is a time series, and almost none of them are daily. "By month" is the
default unit of business reporting, and it is currently unaskable.

The reason this needs care rather than a quick function whitelist is what the obvious
alternative does. Written the way an LLM often writes it, `MONTH(order_date)` returns the
month *number* — `7` for July 2026 and `7` for July 2025 alike — so a two-year query silently
merges the two into one row labelled `7`. The total is real, the label is plausible, and
nothing in the answer reveals that two years were added together. That is the exact failure
this project exists to refuse, so `MONTH()`, `YEAR()` and `EXTRACT()` are refused with a
message that explains the difference rather than accepted as near-enough.

This is also the strongest available demonstration of N4. `DATE_TRUNC('month', d)` is spelled
five different ways across the dialects sqlglot knows — `TIMESTAMP_TRUNC(d, MONTH)` on
BigQuery, `DATETRUNC(MONTH, d)` on T-SQL, and a `DATE_ADD`/`TIMESTAMPDIFF` construction on
MySQL — all from one canonical statement.

# User stories

- **As a business user**, I ask for revenue by month and get one row per calendar month — so
  the answer is a time series I can read.
- **As an analyst**, a request that would merge two Julys is refused with an explanation — so
  the mistake is caught at the layer that can see it, not in a meeting.
- **As a contributor**, a grain proves the transpiler does real work on more than one clause.

# Functional requirements

- **FR-1** — A projection may be `DATE_TRUNC('<grain>', <dimension>)`, where the grain is one
  of `year`, `quarter`, `month`, `week`, `day`, and the dimension is declared `type: date`.
- **FR-2** — A grained projection groups by the truncated value, so one row is returned per
  period, and it may carry an alias. Without one, the result column is named
  `<dimension>_<grain>`.
- **FR-3** — `MONTH()`, `YEAR()`, `QUARTER()`, `DAY()`, `WEEK()` and `EXTRACT(... FROM ...)`
  are refused, with a message stating that they extract a number rather than truncate, and
  naming the `DATE_TRUNC` form that does what was probably meant.
- **FR-4** — An unknown grain, a grain on a non-date dimension, a grain on a measure or
  metric, and a nested or otherwise non-plain argument are each refused.
- **FR-5** — Every refusal is decided before the datasource is reached.
- **FR-6** — Every request answerable before this change is still answered, unchanged.
- **FR-7** — The bundled documentation records grains, the refused forms and why, and the
  cross-dialect rendering.

# Non-functional requirements

- **N2 (a silently wrong number is the worst failure)** — the year-collapsing forms are the
  hazard, and they are refused rather than translated into something close.[^constitution]
- **N4 (canonical dialect, then transpile)** — one canonical `DATE_TRUNC`, rendered per
  dialect by sqlglot, with no dialect branching in the compiler.[^constitution]
- **N3 (the YAML is the source of truth)** — a grain is a way of asking, not a definition, so
  it stays in the request; `type: date` in the model is what authorises it.[^filters]

# Out of scope

- **Filtering on a truncated value** — `WHERE DATE_TRUNC('month', order_date) = …`. Filter on
  the date dimension itself with a range, which already works.
- **Grains below a day**, since the model's date type has no time component.
- **Fiscal calendars, week-start configuration, and time zones.**
- **Declaring a grain in the model** as a pre-made dimension, which remains possible for a
  modeller to do by hand with a database view.

[^constitution]: `.specify/memory/constitution.md` — N2, N3, N4.
[^filters]: `specs/004-filter-by-dimension/spec.md` — where `type: date` first became enforced.
