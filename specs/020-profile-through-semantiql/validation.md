---
type: Validation
title: Profile a relation through SemantiQL, not through psql — validation
description: Acceptance criteria traced to FR-1..FR-11.
resource: specs/020-profile-through-semantiql/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T14:41:46+00:00' }
status: stable
---

# Acceptance criteria

- [x] **AC-1..AC-4** (FR-1..FR-4): row count; nulls and distinct per column; min/max/sum for numbers;
      min/max for dates.
  - **Proven by:** `test_profile_counts_rows_nulls_and_distinct_values`,
    `test_profile_sums_a_numeric_column_exactly`, `test_profile_reports_a_timestamp_bound_as_text`,
    and on Postgres `test_profile_reports_rows_sums_and_a_distribution`. On the real taxi table:
    2,964,624 rows, `fare_amount` **53882224.76**, `total_amount` **79456384.28** — both matching
    `examiner/ANSWERS.md`, which was computed independently.
- [x] **AC-5** (FR-5): the value distribution of a low-cardinality column.
  - **Proven by:** `test_profile_reports_the_distribution_of_a_coded_column` and
    `test_profile_leaves_a_high_cardinality_column_without_a_distribution`. On real data
    `payment_type` came back `1(2,319,046) 2(439,191) 0(140,162) 4(46,628) 3(19,597)` — the coded
    column made legible, which is the whole reason the verb exists.
- [x] **AC-6** (FR-6): read-only, engine-authored, no caller SQL or expression.
  - **Proven by:** the signature — `profile(source)` takes a relation name and nothing else, so there
    is no parameter through which SQL could arrive. Aggregates are chosen by `ColumnKind` from a
    fixed template. `test_profile_quotes_a_column_whose_name_is_reserved` proves the identifier
    handling, which matters because the SQL is built here rather than supplied.
- [x] **AC-7** (FR-7): no model required.
  - **Proven by:** `test_profile_needs_no_model`.
- [x] **AC-8** (FR-8): `--json`.
  - **Proven by:** `test_profile_reports_the_sum_that_prices_a_definition` and
    `test_profile_json_carries_the_distribution_of_a_coded_column`.
- [x] **AC-9** (FR-9): identical on both engines, dialect SQL in the adapter.
  - **Proven by:** the same contract asserted in both adapter suites, and
    `grep -rnE "adapters(\.|[[:space:]]+import)" src/semantiql/engine/` still returning only
    `adapters.base`. **`engine/` did not change.**
- [x] **AC-10** (FR-10): the skill teaches `profile`, forbids raw SQL, and prints DDL instead of
      running it.
  - **Proven by:** `test_the_skill_teaches_profile`,
    `test_the_skill_forbids_running_sql_against_the_database`,
    `test_the_skill_forbids_writing_to_the_database`.
- [x] **AC-11** (FR-11): the prohibition names the clients, so it is followable.
  - **Proven by:** the same test asserting `psql` and `duckdb` appear by name. A rule that says "no
    raw SQL" without naming the tools is one a reader can satisfy while breaking it.

# Things found by running it, not by reading it

- [x] **DuckDB cannot return a `timestamptz` to Python without `pytz`.** The first implementation
      raised `ModuleNotFoundError`. Date bounds are now rendered to text in the database — no new
      dependency. The comment records what that does *not* fix: a tz-carrying bound is still in the
      session's timezone, which is why `carries_timezone` remains the field that decides `timezone:`.
- [x] **The sum cast was in the wrong place.** `sum(x)::numeric` returned `53882224.7599785`;
      `sum(x::numeric)` returns `53882224.76`. Float drift had already accumulated before the cast
      ran. Fixed on both engines, and the docstrings now carry the measured figures rather than a
      claim of exactness.
- [x] **A reserved-word column.** This file's own fixture failed on a column named `at`, which
      prompted asserting that `profile` handles `"order"` and `"select"` — it does, because the SQL
      is built through sqlglot rather than concatenated.

# Non-functional acceptance

- [x] The verify gate is green with Postgres up and with it down.
- [x] **N1** — `profile` authors no caller SQL, so it does not route through `run`; the same standing
      as `doctor` and `columns()`, both of which already read the database outside it.
- [x] **N2** — every figure a human is shown to decide a definition now comes from one reviewed
      template.
- [x] **N4** — `engine/` unchanged; aggregate SQL lives in each adapter.
- [x] **N5** — `SELECT` only, and Postgres rolls back after fetching:
      `test_profile_leaves_no_open_transaction` asserts the backend is `idle`, not
      `idle in transaction`.
- [x] **N6** — untouched. Profiling reports what is in a column, never what it means.
- [x] **The MCP surface is still two tools.** Profiling is a build-time verb;
      `test_the_skill_still_names_no_tool_the_server_lacks` guards against it being taught as a third.
- [x] **Spec 016's exclusion is reconciled**, with the reason it failed: it lived in a spec and not in
      the skill.

# Manual verification

1. `semantiql profile --datasource postgres --table trips` against the 2.96M-row database — expect
   sums matching `examiner/ANSWERS.md` and `payment_type` shown as a distribution. **Run.**
2. `semantiql profile` with no `--table` — expect exit 2 and a message naming `--table`. **Run.**
3. **A real discovery run under `run-debug.sh`, checking the transcript for `psql`.** This is the only
   check that tests the prohibition against the thing it is aimed at. **Not yet run** — it needs a
   fresh session, and it is the first thing to do next. Until then, AC-10 and AC-11 prove the skill
   *says* it; nothing here proves a model *obeys* it.
