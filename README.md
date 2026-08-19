# SemantiQL

**A semantic layer that lets AI query your database accurately.**

SemantiQL sits between AI agents (LLMs) and your database. Instead of writing SQL against raw tables, the AI works with a business-friendly semantic model — dimensions, measures, and metrics — and SemantiQL translates that into correct, validated SQL for your database.

## Status

**Experimental, pre-release — the API will change.** Maintained by
[@lethuan127](https://github.com/lethuan127) as time allows: issues and pull requests are
triaged weekly, with no SLA. Open an issue before writing a large pull request.

The engine below runs today: a semantic model with dimensions, measures and metrics;
validation; filters, ordering, limits and time grains; sqlglot transpiling; `semantiql doctor`
to check a model against its database; **DuckDB and Postgres** adapters, with a differential
test suite asserting both return the same answer for the same model; and an **MCP server**, so
Claude asks the questions instead of you writing semantic SQL. The accuracy benchmark is not
built yet — see the [roadmap](#roadmap).

## Quickstart

Needs **Python 3.11+** and [uv](https://docs.astral.sh/uv/). No database to install.

```bash
git clone https://github.com/lethuan127/semantiql
cd semantiql
uv sync

uv run semantiql "SELECT revenue, order_count, channel FROM orders" --show-sql
```

```
-- SELECT channel AS channel, SUM(amount) AS revenue, COUNT(order_id) AS order_count
--   FROM READ_CSV_AUTO('examples/retail/orders.csv') GROUP BY channel
channel  revenue  order_count
-------  -------  -----------
partner  385.25   2
web      956.5    5
retail   344.49   3
```

A model can also be a **directory** of YAML files, one per table, so a warehouse stays reviewable
and a metric change is a small diff — see [`examples/warehouse/`](examples/warehouse/).

`revenue` and `channel` are defined in [`examples/retail/semantic_model.yml`](examples/retail/semantic_model.yml) —
not in the query. So is `revenue_per_order`, a metric derived from two measures and computed
after grouping. [docs/09-data-modeling.md](docs/09-data-modeling.md) is the full reference for writing one. Ask for something the model doesn't define and it refuses rather than guessing:

```bash
$ uv run semantiql "SELECT profit FROM orders"
refused: 'profit' is not defined on table 'orders'.
```

That refusal is the point of the project, not a limitation. Run `./scripts/verify.sh` to
check everything the CI checks.

### Through Claude

```bash
# Claude Desktop — build one file and open it; it asks for the model in a dialog
uv run python scripts/build_bundle.py          # → dist/semantiql-<version>.mcpb

# Claude Code — install the plugin from plugin/ (it also carries the skill), then:
export SEMANTIQL_HOME=$PWD SEMANTIQL_MODEL=/absolute/path/to/model.yml
```

The plugin ships the server *and* a skill that teaches Claude the dialect, how to repair a
refusal, and to stop rather than invent a definition the model does not have.

Claude then calls `describe_model` to learn your vocabulary and `query` to answer — and when a
question names something your model does not define, it reads the refusal and either fixes the
query or tells the user, rather than inventing a number. Two read-only tools; that surface is the
enforcement boundary.

**Using it on your own database?** [docs/10-adopting-semantiql.md](docs/10-adopting-semantiql.md)
walks the whole path — read-only account, modelling one table, the `doctor` loop, and what is
refused and why.

You do not write the first model from a blank file. `semantiql inspect` reads your catalogue
without needing a model, and the skill has Claude use it: read the schema, ask you the handful of
questions a schema cannot answer, write one YAML per table, then loop on `doctor` until it passes.
[docs/03-setup-workflow.md §A3](docs/03-setup-workflow.md) is that loop, step by step.

### Against Postgres

The same model, the same question, a different engine:

```bash
uv run semantiql "SELECT revenue, channel FROM orders" \
  -m examples/retail/semantic_model.postgres.yml \
  --datasource postgres --dsn postgresql://user@localhost/yourdb
```

Omit `--dsn` to use libpq's own environment (`PGHOST`, `PGUSER`, `.pgpass`), which keeps a
password out of your shell history. The connection never appears in the model file.

The two models differ on exactly two lines — `dialect`, and `source: orders` in place of
`source: orders.csv`, because Postgres has no file sources. Everything that defines what a
number *means* is identical, and
[`tests/test_postgres_differential.py`](tests/test_postgres_differential.py) fails if the two
engines ever disagree about one.

Check a model against its database before trusting it:

```bash
$ uv run semantiql doctor
✓ datasource 'retail' speaks duckdb
orders
  ✓ source 'examples/retail/orders.csv' has 5 columns
  ✓ 3 dimensions, 3 measures and 1 metric all resolve
```

> ⚠️ Early stage — under active development. Not ready for production use.

## Why

LLMs answering questions over raw SQL schemas are wrong most of the time (~16% accuracy in [published benchmarks](https://arxiv.org/abs/2405.11706)). Adding a knowledge layer raises accuracy to ~54%, and adding query validation on top reaches ~72%. SemantiQL is built around that insight: **a semantic model plus a validation layer — not a better prompt — is what makes AI-over-data reliable.**

## How it works

```
┌─────────────────────────────────────────────┐
│  AI agent (Claude via MCP, or any LLM)      │
│  asks in semantic SQL                       │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  1. Semantic Knowledge                      │
│     dimensions · measures · metrics ·       │
│     virtual views (one YAML file, in git)   │
├─────────────────────────────────────────────┤
│  2. SQL Engine                              │
│     semantic SQL → validated raw SQL        │
│     (dialect transpiling via sqlglot)       │
├─────────────────────────────────────────────┤
│  3. Data Governance                         │
│     labels · descriptions · access control  │
│     · caching                               │
├─────────────────────────────────────────────┤
│  4. Database                                │
│     DuckDB · Postgres (MVP) — more later    │
└─────────────────────────────────────────────┘
```

## Key ideas

- **One YAML file is the source of truth.** The semantic model is reviewable, diffable, and lives in git. It is database-agnostic — switch databases without rewriting the model.
- **Validation over generation.** Every query is checked against the semantic model before it runs. A silently wrong number is the worst failure mode, so the engine blocks what it cannot verify.
- **Self-improving, safely.** Confirmed question–query pairs become verified examples (few-shot/RAG) that improve accuracy over time — without ever touching metric definitions. Schema changes are only ever proposed as diffs for a human to review.
- **Mechanical work is automated; judgement is asked about.** Claude reads your schema with `semantiql inspect` and writes the model YAML itself. Which aggregation counts as revenue, and what a row *is*, come from the analyst — Claude asks rather than picking.
- **Built for non-technical users.** The MVP integrates with Claude as an MCP server: an analyst sets it up once (≤15 minutes), end users just chat.

## Roadmap

| Stage | Scope |
|---|---|
| MVP | ✅ DuckDB + Postgres · ✅ semantic model YAML · ✅ semantic SQL → raw SQL engine · ✅ MCP server for Claude · accuracy benchmark vs. raw-table querying |
| Next | MySQL, SQLite · verified-examples loop |
| Later | ✅ Databricks · ✅ Google Sheets · BigQuery, Snowflake · remote server mode · access control |

Out of scope: NoSQL databases (MongoDB, etc.).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — setup, how to run one test, and the invariants a
change must not break. Vulnerabilities go through [SECURITY.md](SECURITY.md), not public
issues.

## Development

Start with the [development guide](CONTRIBUTING.md) and the architecture documentation:
[docs/02-architecture.md](docs/02-architecture.md) for the four layers and why validation is
the centrepiece, and [docs/07-code-map.md](docs/07-code-map.md) for which module owns what.
[docs/08-positioning.md](docs/08-positioning.md) covers how this differs from other semantic
layers.

For agents, follow [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE)
