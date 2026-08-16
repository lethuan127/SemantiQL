# Code map — the four layers, and where each one lives

[02-architecture.md](02-architecture.md) describes four layers. This file maps them to
modules, so a change has an obvious home. If the tree and this file disagree, the tree is
right and this file is stale — please fix it.

```
src/semantiql/
  knowledge/     1. Semantic Knowledge
    model.py       pydantic models: Dimension, Measure, Table, SemanticModel
    loader.py      the only reader of the semantic model YAML
  engine/        2. SQL Engine
    validate.py    resolve every identifier against the model, or refuse
    compile.py     canonical SQL, then sqlglot transpile to the target dialect
    run.py         validate → compile → execute. The single path to the data.
  adapters/      4. Database
    base.py        the Adapter Protocol — the seam a new datasource plugs into
    duckdb.py      DuckDB; reads CSV and Parquet directly
    postgres.py    Postgres; tables and views only, read-only connection
  doctor.py      checks a model against the database — `semantiql doctor`
  cli.py         the `semantiql` command
```

`doctor.py` sits beside the layers rather than inside one: it reads a model and a datasource's
schema, and it is deliberately **not** in `engine/`, because the engine has exactly one path to
data and a checker living next to it would blur that. It reads metadata, never rows.

**Layer 3, Data Governance, is not implemented.** Labels, access control and caching have
no MVP requirement yet. When they arrive they belong at `src/semantiql/governance/`, and
they sit between the engine and the adapter. Stating the gap is more useful than an empty
module that looks like a feature.

## Where does my change go?

| Change | Module |
|---|---|
| A new kind of dimension, measure, or model field | `knowledge/model.py`, then `loader.py` if loading needs it |
| A request should be refused that currently isn't | `engine/validate.py` |
| The generated SQL is wrong or inefficient | `engine/compile.py` |
| Support a new database | one new file in `adapters/` — **and nothing else** |
| A new CLI verb | `cli.py`, routing through `engine.run.run` |
| A new model-versus-reality check | `doctor.py` |

## The two rules the layout exists to enforce

**One chokepoint to the data.** `engine.run.run` validates before compiling and compiles
before executing. Adapters never validate and never rewrite, so every query that reaches
the database has been checked against the model — and anything the compiler cannot honour
is refused rather than quietly dropped.

If you add a way to query, route it through `run`. A helper that reaches an adapter directly
is the one change most likely to be rejected.

**Be precise about how strong this is.** `Adapter.execute` takes a plain `str`; nothing in
the type system stops you calling it directly, and `tests/test_adapter_duckdb.py` does
exactly that. So the chokepoint is enforced by *this* rule and by review, not by the
compiler. Making it structural would need a distinct validated-SQL type — worth doing, not
yet done.

**One adapter, no core changes.** `engine/` imports `adapters.base`, never a concrete
adapter. `base.Adapter` is a `Protocol`, not a base class, so an adapter maintained outside
this repo never imports SemantiQL internals either.

Check it holds:

```bash
# Matches every import spelling, including `from semantiql.adapters import duckdb`,
# which the narrower `grep "adapters\."` misses.
grep -rnE "adapters(\.|[[:space:]]+import)" src/semantiql/engine/   # only adapters.base
```

The grep is necessary but not sufficient. Three DuckDB-specific things do live in `engine/`
and no import check will find them: `validate.py` parses input with `read="duckdb"`,
`compile.py` sets `CANONICAL_DIALECT = "duckdb"`, and DuckDB is the one dialect that skips
transpiling. Those are deliberate — DuckDB *is* the canonical dialect — and all three are
unchanged by the Postgres adapter.

**Behaviour is now verified too** (spec 010). Adding Postgres changed zero files under
`engine/`, and `tests/test_postgres_differential.py` runs the same requests through both
engines and fails if the answers differ — which is the only check that can catch a dialect bug
producing a plausible wrong number. Two findings came out of it, both worth knowing before you
touch the seam:

- `close()` was missing from the `Adapter` Protocol. Both adapters had it and the CLI called
  it; nothing caught the gap because the CLI was typed against the concrete class. **One
  implementation cannot tell you a seam is incomplete.**
- `DATE_TRUNC` on a date column returns a timezone-aware value on Postgres and a naive one on
  DuckDB, from byte-identical SQL — Postgres picks its `timestamptz` overload. Buckets and
  totals agree, so a test pins the difference; resolving it properly means changing how
  `compile.py` emits the truncation, which is a spec of its own.

If adding a datasource forces a change under `engine/`, that is the design smell the
constitution names — raise it as an issue rather than working around it.

## The adapter seam in detail

An adapter provides four things, and `adapters/duckdb.py` is the worked example:

| Member | Contract |
|---|---|
| `dialect` | the sqlglot dialect name SQL is transpiled to before `execute` |
| `relation(source)` | how a model's `source` becomes a selectable relation — a table name passes through, a `.csv`/`.parquet` path becomes a reader call. Returns a **built sqlglot expression, never a string**: a string would be re-parsed by the compiler, letting a quote in `source` inject relations into the FROM clause |
| `columns(source)` | describes a model `source` as `Column(name, native_type, kind)`, building its probe through `relation()` rather than interpolating. `kind` translates the engine's own type names into the model's four, so `doctor` can compare a column to `type:` without learning any dialect's vocabulary — that translation is the adapter's job (N4). `carries_timezone` rides alongside as one bit rather than a fifth `kind`, because it matters for exactly one thing (time grains) and a fifth kind would make `doctor` report every `timestamptz` column as a filter-typing mismatch (spec 011) |
| `execute(sql)` | run validated SQL; return `(column names, rows)` |

What the core guarantees in return: `execute` only ever receives SQL whose every identifier
resolved against the semantic model, already transpiled to the adapter's declared dialect,
and only ever a single-table `SELECT`. An adapter does not need to defend itself against
the query text.

## The example

`examples/retail/` is both the demo and the test corpus: `semantic_model.yml` plus a
ten-row `orders.csv`. DuckDB reads the CSV directly, so it runs with no database, no
credentials and no network. `tests/test_example_end_to_end.py` asserts the answers against
figures computed by hand, so a regression that changes a number fails the build.
