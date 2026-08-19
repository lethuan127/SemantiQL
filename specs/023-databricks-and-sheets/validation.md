---
type: Validation
title: Databricks and Google Sheets as datasources — validation
description: Acceptance criteria traced to FR-1..FR-11, and a plain statement of what has not been exercised.
resource: specs/023-databricks-and-sheets/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-19T09:33:04+00:00' }
status: stable
---

# The limit, first, because it decides how to read everything below

**Neither adapter has been run against a real service.** There is no Databricks workspace and no Google
service-account credential on this machine, and both drivers are optional extras that are not
installed. So the fetch, the auth, and every quirk of a real warehouse or a real spreadsheet are
**unverified**.

What *is* verified is more than it sounds, and for Sheets it is nearly everything, because the adapter
accepts injected rows and after the fetch it is ordinary DuckDB. That is a property of the design — the
argument for borrowing a query engine rather than writing one — and not luck.

# Acceptance criteria

- [x] **AC-1, AC-2** (FR-1, FR-2): `DatabricksAdapter` satisfies the Protocol and declares
      `dialect = "databricks"`.
  - **Proven by:** `uv run mypy` holding it to the Protocol, plus
    `test_the_dialect_is_databricks_so_the_engine_transpiles` and
    `test_the_engine_emits_valid_databricks_sql_for_a_time_grain` — the latter checking sqlglot
    actually produces `TIMESTAMP_NTZ`, which is what keeps the adapter thin.
- [x] **AC-3, AC-4** (FR-3, FR-4): `SheetsAdapter` satisfies the Protocol with `dialect = "duckdb"`,
      and columns come from the header row.
  - **Proven by:** fifteen tests, including a real `GROUP BY` returning **15600.75** for two rows that
    sum to it, and `test_types_are_inferred_from_text_the_way_a_csv_is` showing DuckDB deriving
    `string / number / date / boolean` from strings.
- [x] **AC-5** (FR-5): read-only.
  - **Proven by:** neither adapter exposing a write path, and the read-only Sheets scope asserted by
    `test_the_read_only_scope_is_the_one_requested`. **Stated honestly**: neither driver offers a
    read-only session flag of the kind `psycopg` has, so the guarantee rests on `validate` refusing
    every non-`SELECT` — the same position already documented for in-memory DuckDB.
- [x] **AC-6** (FR-6): optional dependency groups, and a missing driver is an instruction.
  - **Proven by:** `uv sync` leaving both absent (checked with `importlib.util.find_spec`),
    `test_a_missing_optional_driver_names_the_extra` for both, and imports placed inside `__init__` so
    the module stays importable. **The order was made consistent during implementation**: Databricks
    checked the driver first and Sheets checked credentials first; the driver is the more fundamental
    blocker, so both now check it first.
- [x] **AC-7** (FR-7): both reachable through the one factory, with credentials refused by name.
  - **Proven by:** `test_the_new_datasources_are_accepted_choices`,
    `test_an_unknown_datasource_is_still_refused`, and the observed message
    *"Google Sheets needs --sheet-id / SEMANTIQL_SHEET_ID, --sheet-credentials / …"*.
- [x] **AC-8** (FR-8): `engine/` unchanged.
  - **Proven by:** `git diff --name-only src/semantiql/engine/` returning **zero files**, and the
    constitution's grep still finding only `adapters.base`. **This is the strongest evidence N4 has
    had**: the first two adapters were built alongside the engine, these two were not.
- [x] **AC-9** (FR-9): live tests skip with a stated reason; pure tests always run.
  - **Proven by:** the `dbx`/`sheets` skips, and 22 + 15 tests passing offline.
- [x] **AC-10** (FR-10): the roadmap updated in the two documents, and **proposed** for the third.
  - **Proven by:** `README.md`, `docs/05-datasources.md`, and
    `constitution-amendment.md` — a diff, because **no agent amends the constitution**.
- [x] **AC-11** (FR-11): the Sheets fetch cost is documented where a user meets it.
  - **Proven by:** the adapter's docstring and `docs/05-datasources.md`: the whole range is fetched
    when the adapter opens, which is right for a spreadsheet and wrong for anything large.

# Things worth knowing that the work surfaced

- [x] **Spark inverts the timestamp names.** `TIMESTAMP` is zone-aware; `TIMESTAMP_NTZ` is naive — the
      opposite of what the longer name suggests. Backwards, this would declare `timezone:` on a naive
      column and *move* buckets instead of pinning them (spec 011). Pinned by
      `test_timestamp_carries_a_zone_and_timestamp_ntz_does_not`.
- [x] **A spreadsheet has no zone-aware type at all**, so a model over Sheets must never set
      `timezone:`. Asserted by `test_no_column_claims_to_carry_a_timezone`.
- [x] **Cell escaping is this adapter's problem.** Values reach DuckDB's reader as CSV, so an unescaped
      comma would shift every later column — a plausible wrong number rather than an error. Covered by
      `test_a_cell_containing_a_comma_survives`.
- [x] **Short rows are normal.** Spreadsheets omit trailing empty cells, so rows are padded rather than
      dropped or refused.

# Non-functional acceptance

- [x] The verify gate is green with Postgres up, with it down, and with **neither** extra installed.
- [x] **The default install did not grow.** `dependencies` untouched; two `optional-dependencies`
      groups added.
- [x] **N1 / N2** — no new query path, and the Sheets adapter deliberately does not interpret SQL.
- [x] **N7 untouched** — a spreadsheet is a table with the types filed off, not a document store.
- [x] mypy strict passes over both adapters, with an `ignore_missing_imports` override for the two
      unstubbed drivers, following the existing `duckdb.*` precedent.

# Manual verification

1. `semantiql inspect --datasource databricks` with no extra installed — expect exit 3 and the install
   line. **Run.**
2. `semantiql inspect --datasource sheets` likewise. **Run.**
3. A Sheets adapter over injected rows: columns, profile, and a `GROUP BY`. **Run** — the sums are
   quoted above.
4. Against a real Databricks warehouse and a real spreadsheet — **not run, and not runnable here.**
   This is the step that would turn "satisfies the Protocol" into "works", and it needs credentials the
   owner holds. Until then, treat both adapters as unexercised.
