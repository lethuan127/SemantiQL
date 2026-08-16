---
type: Clarifications
title: Ask for a date dimension at a coarser grain — clarifications
description: 4 ambiguities resolved before planning.
resource: specs/007-time-grains/clarifications.md
tags: [sdd, clarifications]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:36:49+07:00' }
status: stable
---

## Q1: What is the syntax — a function in the query, or a grain declared in the model?

- (a) The modeller predeclares `order_month`, `order_quarter`, `order_year` as dimensions.
- (b) The request writes `DATE_TRUNC('month', order_date)`.
- **Chosen:** (b) — decided by the agent from what each option costs the two audiences. Option
  (a) keeps the query language untouched, which is attractive, but it makes the model author
  enumerate every grain anyone might ever want, and a question about a grain nobody anticipated
  gets refused for a reason that has nothing to do with the data. A grain is a way of *asking*,
  not a definition of a business number, so it belongs in the request; `type: date` in the
  model is what authorises it. Option (a) also remains available to anyone who wants it, via a
  view.

## Q2: Which spellings are supported?

- (a) `DATE_TRUNC` plus the convenience forms `MONTH(x)`, `YEAR(x)`, `EXTRACT(MONTH FROM x)`.
- (b) `DATE_TRUNC` only; the others refused with an explanation.
- **Chosen:** (b) — decided by the agent from a probe at clarify time. `MONTH(DATE
  '2026-07-15')` and `MONTH(DATE '2025-07-02')` both return `7`, so grouping by it merges every
  July in the corpus into one row whose total is real, whose label looks right, and whose
  meaning is wrong. Supporting it "because the caller probably meant month-of-year" is exactly
  the guess this engine refuses to make. The refusal names `DATE_TRUNC('month', …)`, so the
  caller is one edit away from the answer.

## Q3: How is the result column named?

- (a) Require an explicit alias.
- (b) Default to `<dimension>_<grain>`, honouring an alias when given.
- **Chosen:** (b) — decided by the agent from the existing projection rule, which already
  derives a default output name and honours an alias when present. `order_date_month` is
  predictable and readable, and requiring an alias would make the common case noisier than the
  feature it enables.

## Q4: Does the GROUP BY use the alias or the expression?

- (a) Group by the output alias.
- (b) Group by the truncated expression, repeated.
- **Chosen:** (b) — decided by the agent from portability. Ordering by an alias is standard and
  both MVP engines accept it, which is why spec 005 used it there; grouping by an alias is
  *not* uniformly supported across the dialects sqlglot targets. Repeating the expression is
  valid everywhere, and sqlglot renders both occurrences consistently, so the cost is a longer
  statement rather than a semantic risk.
