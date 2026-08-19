# Datasources

**Architecture first, list second:** the engine generates SQL in one canonical dialect, then transpiles to the target dialect with **sqlglot**, connecting through a thin adapter. Adding a datasource = writing one adapter (connect + introspect schema + run query) — no core changes.

## Roadmap

| Stage | Datasources | Rationale |
|---|---|---|
| MVP | ✅ **DuckDB** + ✅ **Postgres** | DuckDB: zero-setup demo, reads CSV/Parquet — anyone cloning the repo can run it immediately (matters for GitHub). Postgres: the most common real-world use case. Both ship; a differential suite asserts they answer the same model identically. |
| v2 | MySQL, SQLite | Cheap thanks to sqlglot + SQLAlchemy; covers most OLTP. |
| v3 | ✅ **Databricks**, BigQuery, Snowflake | Warehouses — where data analysts actually work; needed for company adoption. **Databricks was brought forward** from v3 by an owner decision (spec 023), behind an optional dependency group so a default install does not carry its driver. |
| — | ✅ **Google Sheets** | Not previously on this roadmap. Added on request (spec 023): a spreadsheet is where a surprising amount of real business data lives, and it is the only datasource here with **no query engine of its own**. |

## Walkthroughs

| Cookbook | What it covers |
|---|---|
| [cookbooks/postgres.md](cookbooks/postgres.md) | empty database → read-only role → model → answer, **every figure captured from a real run** |
| [cookbooks/databricks.md](cookbooks/databricks.md) | the same shape on a SQL warehouse, with the workspace steps marked as **not run** |

## Two adapters that are not databases

**Google Sheets has no query engine**, so its adapter borrows one: it fetches the worksheet, loads it
into an in-memory DuckDB, and executes there. Its declared `dialect` is therefore `duckdb` — a statement
about which engine runs the query, not a pretence that Sheets speaks SQL.

The rejected alternative was to interpret the SQL in Python. That would be a second query
implementation, and the first time it disagreed with DuckDB about a `NULL` inside an average the answer
would be quietly wrong rather than an error. N2 decides it.

Its one honest limit, stated where a user will meet it: **the whole range is fetched when the adapter
opens.** A spreadsheet is small by construction, so this is right for Sheets and wrong for anything
large. Types are inferred from text, exactly as they are for a `.csv` source, so one stray word in a
numeric column makes the whole column text — `doctor` is what catches that.

**Databricks needed no engine work at all**, which is the clearest evidence for N4 so far: sqlglot
already emits Databricks SQL, including the `TIMESTAMP_NTZ` cast a time grain requires. Two new
datasources changed **zero files** under `engine/`.

One Spark trap worth knowing: `TIMESTAMP` **is** zone-aware and `TIMESTAMP_NTZ` is the naive one, which
is the opposite of what the longer name suggests to anyone arriving from Postgres. Getting it backwards
would put a `timezone:` on a naive column, which moves buckets rather than pinning them.

## Notes

- DuckDB reading CSV/Parquet means the MVP natively supports "Q&A over files" — an attractive demo for non-technical users with no database at all.
- The semantic model YAML is **datasource-independent** — switching databases doesn't mean rewriting the model (unlike hand-written SQL). One honest qualification, learned from actually shipping the second adapter: a `source` naming a *file* cannot move to an engine with no file sources. Everything that defines what a number means moves unchanged; a CSV path does not, and the adapter says so by name rather than reporting a missing table.
- **Postgres has no file sources**, so a model built for the DuckDB demo needs its `source` pointed at a table. See `examples/retail/semantic_model.postgres.yml` for the two lines that differ.
- **No NoSQL** (MongoDB, …) — out of scope; stated clearly in the README to avoid off-topic issues.
