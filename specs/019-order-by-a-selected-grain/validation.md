---
type: Validation
title: Order by a time grain the request already selects — validation
description: Acceptance criteria traced to FR-1..FR-7.
resource: specs/019-order-by-a-selected-grain/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T13:47:57+00:00' }
status: stable
---

# Acceptance criteria

- [x] **AC-1** (FR-1): `ORDER BY DATE_TRUNC('<grain>', <dimension>)` is accepted when the request
      selects that dimension at that grain, and orders by the corresponding output column.
  - **Proven by:** `test_ordering_by_a_selected_grain_is_accepted`, and **the query that started this
    spec, re-run against the 2.96M-row NYC database**, which now returns five months in month order
    with January 2024 carrying 53,881,922.66.
- [x] **AC-2** (FR-2): A different grain is refused, naming the grain that is selected.
  - **Proven by:** `test_a_different_grain_is_refused_naming_the_one_selected`, and observed on real
    data: *"this request selects pickup_datetime by month, not by day, so ordering by day would
    arrange the rows by a boundary the answer does not show. Order by one of: pickup_datetime_month,
    revenue."* Both halves matter — the refusal, and the repair instruction.
- [x] **AC-3** (FR-3): A grain on a dimension the request does not select is refused.
  - **Proven by:** `test_a_grain_on_an_unselected_dimension_is_refused`.
- [x] **AC-4** (FR-4): `ASC`/`DESC` and `NULLS FIRST`/`LAST` work on the expression form.
  - **Proven by:** `test_direction_and_nulls_work_on_the_expression_form`, parametrised over three
    spellings.
- [x] **AC-5** (FR-5): Every ORDER BY refusal names the orderable names.
  - **Proven by:** `test_every_ordering_refusal_names_what_may_be_ordered_by`, parametrised over all
    four branches — position, aggregate, non-date function, and grain. **This is the defect**: one
    branch ended at *"is not one."* and a real run could only read that as "not supported".
    `_orderable()` now holds the sentence in one place, so a fifth branch cannot be added silent.
- [x] **AC-6** (FR-6): Other functions stay refused, and now say what may be ordered by instead.
  - **Proven by:** the `SUM(amount)` and `UPPER(channel)` cases in the same parametrised test.
- [x] **AC-7** (FR-7): The alias form still works.
  - **Proven by:** `test_the_alias_spelling_still_works`, which **passed before the change** — that is
    what established the capability was present and merely unreachable, and that this was a message
    defect rather than a missing feature.

# The claim that mattered most, checked directly

- [x] **No new SQL reaches the database.** Both spellings were compiled and compared:
      `compile_request` returns a **byte-identical** string for
      `ORDER BY DATE_TRUNC('month', order_date) DESC` and `ORDER BY order_date_month DESC`.
      `git diff --name-only src/` lists **only** `engine/validate.py`. AD-2 said a compiler change
      would mean the change was bigger than specced; it was not needed.
- [x] **A malformed grain refuses rather than raising.** `_grain` raises `SemanticSyntaxError` and
      `_ordering` runs outside the `try` that converts those raises, so the call is guarded.
      `test_a_malformed_grain_in_order_by_is_refused_not_raised` covers
      `DATE_TRUNC('fortnight', …)`.
- [x] **The refusal never reaches the database.**
      `test_the_wrong_grain_refusal_never_reaches_the_database` runs the wrong-grain query through
      `run` with `ExplodingAdapter`, which raises if `execute` is called.
- [x] **The rows really are ordered.** `test_a_monthly_series_comes_back_in_month_order` asserts row
      order against real output; the unit tests only prove the `OrderKey`.

# Non-functional acceptance

- [x] The verify gate is green with Postgres up and with it down.
- [x] **N1 / N2** — an accepted ORDER BY resolves to a column the request already projects. Nothing
      new becomes reachable, and the wrong-grain case is refused rather than silently re-pointed at
      the month, which would have reordered rows by something invisible.
- [x] **Trust boundary** — `engine/validate.py`, called out rather than treated as routine.
- [x] **The allowlist is unchanged**, correctly: no new node type is consumed and no new SQL emitted,
      so there is no compiler change for it to accompany.
- [x] **Both engines.** The e2e and `pg` suites pass, and the real-data check ran on Postgres.

# Manual verification

1. On the NYC database: `SELECT revenue, DATE_TRUNC('month', pickup_datetime) FROM trips ORDER BY
   DATE_TRUNC('month', pickup_datetime)` — expect five months, ascending. **Run.**
2. Same with `DATE_TRUNC('day', …)` in the ORDER BY — expect a refusal naming `month` and listing
   `pickup_datetime_month, revenue`. **Run.**
3. `ORDER BY SUM(fare_amount)` — expect a refusal that now lists the orderable names. **Run** via the
   parametrised unit test; not re-run against real data, because the branch is engine-level and the
   real database adds nothing to it.

**A note on step 1's setup.** Re-running `fetch.py` recreates the database and therefore drops the
`trips_v` view the model points at, so step 1 fails with *relation "trips_v" does not exist* until the
view is recreated. That is the model-on-a-view arrangement working as designed — the view is a database
object the model depends on — and it is worth knowing before reading that error as a regression.
