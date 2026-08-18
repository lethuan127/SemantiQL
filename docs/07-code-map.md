# Code map — the four layers, and where each one lives

[02-architecture.md](02-architecture.md) describes four layers. This file maps them to
modules, so a change has an obvious home. If the tree and this file disagree, the tree is
right and this file is stale — please fix it.

```
src/semantiql/
  knowledge/     1. Semantic Knowledge
    model.py       pydantic models: Dimension, Measure, Table, SemanticModel
    loader.py      the only reader of the model YAML — one file, or a directory of them
  engine/        2. SQL Engine
    validate.py    resolve every identifier against the model, or refuse
    compile.py     canonical SQL, then sqlglot transpile to the target dialect
    run.py         validate → compile → execute. The single path to the data.
  adapters/      4. Database
    base.py        the Adapter Protocol — the seam a new datasource plugs into
    duckdb.py      DuckDB; reads CSV and Parquet directly
    postgres.py    Postgres; tables and views only, read-only connection
  doctor.py      checks a model against the database — `semantiql doctor`
  cli.py         the `semantiql` command — query, doctor, serve, and inspect
  server.py      the MCP server — two read-only tools over stdio, `semantiql serve`
  __main__.py    lets `python -m semantiql` work, so a connector config can name an interpreter
```

Everything outside `src/` that a change is likely to touch:

```
tests/                  laid out to mirror the layers above, so a change has an obvious test home
  conftest.py             fixtures for every suite, including the Postgres corpora
  _support.py             REPO_ROOT and friends — found by walking up to pyproject.toml
  knowledge/              the model, its loader, and the metric grammar
  engine/                 validate and compile — mostly refusals, which is the point
  adapters/              one file per datasource; the pure parts need no database
  interfaces/             cli, server, and what is shipped to install them
  integration/            whole-stack answers over the ten-row corpus, and the two-engine checks
  tooling/                development tooling that is real logic
  e2e/                    the large-corpus suites, with their own conftest
    conftest.py             generates TPC-H via DuckDB's dbgen, and copies it into Postgres
    semantic_model.yml      the model under test, plus a `.postgres.yml` sibling
examples/retail/        the bundled example — and the unit suite's corpus. Not free to edit.
examples/warehouse/     a worked directory model: one YAML per table, datasource declared once
  orders.csv              ten rows whose totals are asserted by hand in tests/
  semantic_model.yml      the model the README quickstart runs, plus a `.postgres.yml` sibling
bundle/                 the Claude Desktop bundle's committed parts
  server.py               a three-line entry point; all the logic stays in cli.py, which is tested
.claude-plugin/         marketplace.json — what makes the plugin *installable*. Shipped product,
                        and not to be confused with .claude/, which is this repo's own tooling
plugin/                 the shipped Claude plugin — installs the server *and* the skill
  .claude-plugin/         plugin.json manifest; the location is what makes it discoverable
  .mcp.json               how to launch the server, via ${SEMANTIQL_HOME} — an explicit variable,
                          because deriving the checkout from the plugin's own location breaks the
                          moment the plugin is copied or unzipped (spec 013)
  skills/semantiql/       SKILL.md — how Claude should work. Pinned to the engine by tests.
compose.yaml            a throwaway Postgres for the `pg` suite; CI starts it from this file too
scripts/
  verify.sh               the gate. One command CI and a contributor both run.
  build_bundle.py         assembles dist/*.mcpb — generates the manifest, copies the source
  lint_commit_msg.py      commit-message rules, tested by tests/test_commit_msg_lint.py
  install-hooks.sh        points git at .githooks/
.githooks/              pre-commit runs the gate; commit-msg runs the linter above
```

Two of those are easier to break than they look — three, counting `plugin/skills/`, which is
**not** the same thing as `.claude/skills/`: the first is shipped product, the second is this
repo's own development tooling (`okf`, `sdd`). Keeping them apart is the only way anyone can tell
which is which.

**`examples/retail/` is test data, not sample data.** The unit suite asserts totals computed by
hand from `orders.csv` — change a row and tests fail for a reason that has nothing to do with
the code. It is also what the README quickstart runs, so it is simultaneously the demo. Adding a
row means recomputing the expected figures in `tests/test_example_end_to_end.py`.

**The directories mirror the layers; the *markers* are what split by cost.** A file's directory
says which layer it tests, and its marker says what it needs to run. Those are different questions
and conflating them is how a fast suite ends up gated behind a database.

Every path constant comes from `tests/_support.py`, which finds the repository by walking up to
`pyproject.toml`. Counting `..` from a test file is what broke four tests the moment they moved one
directory deeper, and the failure read as a missing fixture rather than a moved file.

**There are three test suites, not one**, split by what they need rather than by what they cover:

| Suite | Marker | Needs | Absent that |
|---|---|---|---|
| unit | — | nothing | always runs |
| large-corpus | `e2e` | DuckDB's `tpch` extension, fetched once from DuckDB | skips with a reason |
| two-engine | `pg` | a Postgres, via `SEMANTIQL_TEST_DSN` | skips with a reason |

Both skips are deliberate and load-bearing: a fresh clone has to pass the gate with nothing
installed and no network. Never make either a hard failure, and never make the gate require
Docker — `compose.yaml` exists to make the `pg` suite *easy*, not mandatory.

`server.py` and `cli.py` are **callers**, not layers. Both reach data only through
`engine.run.run`, and the server's tool surface is deliberately two calls wide: those two are
the only things a client can do, which is what makes the boundary structural rather than a rule
someone remembers. Adding a third widens it.

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
| Something Claude should see about a database before a model exists | the seam in `adapters/base.py`, then `cli.py` to display it |
| A new tool Claude can call | `server.py` — and think hard first: those tools are the whole boundary |
| A new check in the gate | `scripts/verify.sh` — as its own step, so its cost and any skip are visible |
| A test that needs a database | the matching layer directory, marked `pg`, and it must **skip** when there is none |
| A test for a layer | `tests/<layer>/` — the directory mirrors `src/semantiql/` |
| A bigger or different corpus | `tests/e2e/conftest.py` — never `examples/retail/`, whose totals are asserted by hand |

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
- `tables()` was missing for the same reason, one spec later: nothing needed to enumerate a
  catalogue until discovery did. **Three widenings, each found by building a real consumer** —
  `close()` by the CLI, `carries_timezone` by time grains, `tables()` by `inspect`. The seam is
  correct where something exercises it and unfalsified elsewhere; a new consumer is the only
  reliable way to tell which.
- `DATE_TRUNC` on a date column returns a timezone-aware value on Postgres and a naive one on
  DuckDB, from byte-identical SQL — Postgres picks its `timestamptz` overload. Buckets and
  totals agree, so a test pins the difference; resolving it properly means changing how
  `compile.py` emits the truncation, which is a spec of its own.

If adding a datasource forces a change under `engine/`, that is the design smell the
constitution names — raise it as an issue rather than working around it.

## The adapter seam in detail

An adapter provides five things, and `adapters/duckdb.py` is the worked example:

| Member | Contract |
|---|---|
| `dialect` | the sqlglot dialect name SQL is transpiled to before `execute` |
| `relation(source)` | how a model's `source` becomes a selectable relation — a table name passes through, a `.csv`/`.parquet` path becomes a reader call. Returns a **built sqlglot expression, never a string**: a string would be re-parsed by the compiler, letting a quote in `source` inject relations into the FROM clause |
| `columns(source)` | describes a model `source` as `Column(name, native_type, kind)`, building its probe through `relation()` rather than interpolating. `kind` translates the engine's own type names into the model's four, so `doctor` can compare a column to `type:` without learning any dialect's vocabulary — that translation is the adapter's job (N4). `carries_timezone` rides alongside as one bit rather than a fifth `kind`, because it matters for exactly one thing (time grains) and a fifth kind would make `doctor` report every `timestamptz` column as a filter-typing mismatch (spec 011) |
| `tables()` | every relation a model could name, as displayed names — qualified only outside the engine's default schema (`main`, `public`), system schemas excluded, sorted by what is displayed. This is the one member that answers a question asked *before* a model exists, which is why `semantiql inspect` needs no `-m` (spec 016) |
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
