# Datasources

**Architecture first, list second:** the engine generates SQL in one canonical dialect, then transpiles to the target dialect with **sqlglot**, connecting through a thin adapter. Adding a datasource = writing one adapter (connect + introspect schema + run query) — no core changes.

## Roadmap

| Stage | Datasources | Rationale |
|---|---|---|
| MVP | **DuckDB** + **Postgres** | DuckDB: zero-setup demo, reads CSV/Parquet — anyone cloning the repo can run it immediately (matters for GitHub). Postgres: the most common real-world use case. |
| v2 | MySQL, SQLite | Cheap thanks to sqlglot + SQLAlchemy; covers most OLTP. |
| v3 | BigQuery, Snowflake, Databricks | Warehouses — where data analysts actually work; needed for company adoption. |

## Notes

- DuckDB reading CSV/Parquet means the MVP natively supports "Q&A over files" — an attractive demo for non-technical users with no database at all.
- The semantic model YAML is **datasource-independent** — switching databases doesn't mean rewriting the model (unlike hand-written SQL).
- **No NoSQL** (MongoDB, …) — out of scope; stated clearly in the README to avoid off-topic issues.
