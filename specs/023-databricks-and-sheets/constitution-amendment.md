---
type: Reference
title: Proposed constitution amendment — the datasource roadmap
description: The roadmap line to change now that Databricks and Google Sheets ship, prepared for the owner to apply.
resource: specs/023-databricks-and-sheets/constitution-amendment.md
tags: [sdd, constitution, proposal]
generated: { by: claude-code/claude-opus-5, at: '2026-08-19T00:00:00+00:00' }
status: stable
---

# Proposed amendment, for the owner to apply

**No agent amends the constitution.** This is a diff, not a change. The README and
`docs/05-datasources.md` have been updated because they are documentation; the constitution has not,
because it is governance.

## What shipped

Spec 023 added two adapters behind optional dependency groups:

- **Databricks**, which the constitution's roadmap places in v3.
- **Google Sheets**, which the roadmap does not mention at all.

Both were requested, and the v3 position was raised **before** any code was written, together with the
rule that a new connector is never a routine change. The decision to bring Databricks forward was the
owner's.

## The line

`.specify/memory/constitution.md`, in the roadmap table:

```diff
-| Later | BigQuery, Snowflake, Databricks · remote server mode · access control |
+| Later | ✅ Databricks · ✅ Google Sheets · BigQuery, Snowflake · remote server mode · access control |
```

## What does not need amending, and why that matters

- **N4 is unchanged and better evidenced.** Two datasources changed **zero files** under `engine/`.
  Databricks needed no engine work because sqlglot already emits its dialect; Sheets needed none because
  it borrows DuckDB as its engine.
- **N5 is unchanged.** Neither adapter has a write path. Neither driver offers a read-only session flag
  of the kind `psycopg` has, so the guarantee rests on `validate` refusing every non-`SELECT` — the same
  position already documented for in-memory DuckDB.
- **N7 is not in play.** "No NoSQL" refuses document stores. A spreadsheet is a table with the type
  information filed off: a data-quality problem, not a shape problem, and it is the shape N7 refuses.
- **The dependency rule is honoured rather than excepted.** Both drivers are optional extras;
  `dependencies` is untouched and `uv sync` installs neither.

## Worth deciding at the same time

The roadmap's stage names now fit awkwardly. Databricks shipping before MySQL means "v2" and "v3" no
longer describe an order anything follows. A stage-free table — shipped, next, later — would stop
describing a plan nobody is executing. **Not proposed here**, because renaming the stages is a change to
how the roadmap reads rather than to what it says, and that is the owner's call too.
