# AGENTS.md

Guidance for AI coding agents working in this repository, whichever tool you are.

This is the single agent brief. `CLAUDE.md` is a **symlink to this file**, so there is one
copy to keep true rather than two that drift — if you are reading this as `CLAUDE.md`, you
are reading `AGENTS.md`.

Humans: [CONTRIBUTING.md](CONTRIBUTING.md) covers the same ground with more context.

## What this project is

SemantiQL sits between an LLM and a SQL database. The model writes **semantic SQL** against
a business model — dimensions, measures, metrics — and SemantiQL validates it, compiles it
to physical SQL, and runs it. Four layers, described in
[docs/02-architecture.md](docs/02-architecture.md) and mapped to modules in
[docs/07-code-map.md](docs/07-code-map.md).

**Read the code map before your first change.** It tells you which module owns what, and
it is short.

## Setup and checks

Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                  # venv + dependencies from uv.lock
./scripts/verify.sh      # everything CI runs: ruff format, ruff lint, mypy, pytest, OKF
```

While iterating:

```bash
uv run pytest tests/test_compile.py::test_transpiles_to_another_dialect   # one test
uv run ruff format . && uv run ruff check --fix .                          # fix style
uv run mypy                                                                # strict
```

`./scripts/verify.sh` must pass before you propose a change. It stops at the first failure
and names the step.

## The invariants

These are recorded in [`.specify/memory/constitution.md`](.specify/memory/constitution.md),
which is authoritative. A change that needs one amended needs its own spec first — do not
decide to relax one mid-task.

**N1/N2 — Validation is the point, and a wrong number is worse than no number.**
Every query is checked against the semantic model before it runs. A query that cannot be
resolved is **refused, never guessed at**. The end user is non-technical and never sees SQL,
so a plausible wrong figure is undetectable and gets pasted into a deck.

`engine/run.py` is the single path to the data: it validates, then compiles, then executes.
**If you add a way to query — a CLI verb, an MCP tool, a helper — route it through `run`.**
A shortcut to an adapter is the change most likely to be rejected.

This is a rule, not a guarantee: `Adapter.execute` takes a plain string and nothing prevents
calling it directly. Treat it as load-bearing convention until a validated-SQL type exists.

Also refused, for the same reason: any clause the compiler cannot honour — `WHERE`,
`HAVING`, `ORDER BY`, `LIMIT`, `DISTINCT`, CTEs, subqueries, joins. `compile_request`
rebuilds the query from the model, so an unvalidated clause would *vanish* and the caller
would get a wrong number. If you implement one of those, remove it from
`_UNSUPPORTED_CLAUSES` in the same change — never before.

**N3 — The semantic model YAML is the source of truth.** `knowledge/loader.py` is the only
thing that reads it. Never hard-code a model value in Python.

**N4 — One canonical dialect, then transpile.** Adding a datasource is one new module under
`adapters/` satisfying `adapters/base.py`, with **no change to `engine/`**. Verify with:

```bash
grep -rnE "adapters(\.|[[:space:]]+import)" src/semantiql/engine/   # only adapters.base
```

That catches imports only. DuckDB is also the hard-coded canonical dialect in
`compile.py` and the parse dialect in `validate.py` — deliberate, but it means the claim is
verified for imports, not for behaviour. See [docs/07-code-map.md](docs/07-code-map.md).

**N5 — Read-only by default.** Nothing in the query path needs write access. Precisely: a
file-backed DuckDB connection is opened `read_only=True`, but DuckDB *cannot* open an
in-memory database read-only, and in-memory is the CLI default — so on that path the
guarantee comes from `validate` refusing every non-SELECT, not from the connection.

**N7 — No NoSQL.** Permanently out of scope.

## Tech stack

Decided 2026-08-15; the constitution's tech-stack section is authoritative. sqlglot is
Python-only and is named by N4, so the stack follows that constraint rather than working
around it.

| Layer | Choice |
|---|---|
| Runtime | Python 3.11+, single runtime |
| Deps, distribution | uv; `uvx semantiql` once the first release is published |
| Transpile · engines | sqlglot · DuckDB, then Postgres |
| Model validation | pydantic over the YAML |
| Test · lint · types | pytest · ruff · mypy (strict) |
| CI | GitHub Actions, secret-free so fork PRs run |

Adding an external dependency, connector, or MCP server is never a routine change — raise
it in an issue first. The dependency set is deliberately small.

## Scope boundaries

- **MVP datasources are DuckDB + Postgres only.** MySQL and SQLite are v2; BigQuery,
  Snowflake and Databricks are v3. DuckDB comes first because it makes a fresh clone
  runnable with zero setup, and gives Q&A over CSV/Parquet for free.
- **The MVP MCP server is local**, deliberately, with a path to remote. Don't add hosting or
  multi-user auth scope to it.
- **No UI in the MVP** — Claude Desktop is the interface. A desktop app for analysts is
  post-MVP, and only once value is proven through Claude.
- **Builder setup must complete in ≤ 15 minutes**, every step automatically checked, every
  error carrying a fix instruction. End users never touch a connection string or YAML.

## How changes are made here

Non-trivial changes run through a spec-driven lifecycle and leave an artifact trail under
[`specs/`](specs/) — one directory per change, holding the spec, plan (with a repository
impact map), tasks, and validation criteria. `specs/index.md` lists them; `specs/log.md` is
the dated history.

Two consequences for you:

- **Before changing behaviour, read the relevant `specs/NNN-*/` if one exists.** It records
  what was decided and why, which is usually the answer to "why is this like this".
- **Those artifacts carry provenance.** Each records who wrote it and whether a human
  approved it. Never mark something as human-reviewed that a human did not review.

Documentation-only work and mechanical fixes are deliberately outside that lifecycle.

## Working rules

- **Never weaken a check to make it pass.** Not a lint rule, not a type, not a test
  assertion. That converts a visible failure into a silent one, which is the exact trade
  this project exists to refuse.
- **Behaviour changes need a test.** For validation changes, test the *refusal* path — that
  the request is refused **and** that the database was never reached.
  `tests/test_validation_refuses.py` shows the pattern with an adapter that raises if
  called.
- **Don't invent facts.** No placeholder contact addresses, no invented response-time
  commitments, no unsourced numbers. If a required value cannot be derived from the repo,
  stop and ask.
- **Don't edit `.claude/skills/okf/scripts/validate_bundle.py`.** It is a vendored copy of
  an upstream file; ruff is configured to skip it for that reason.
- **`docs/NN-*.md` and the constitution are trust-boundary files.** Changing one is never a
  routine edit — say so explicitly when you do.

## Conventions

- **Cite research claims.** The accuracy figures (16% / 54% / 72%) trace to
  arXiv:2405.11706 and are marked as verified against the paper. Don't add a number without
  a source.
- **Never state a fact about another product** — Cube, dbt Semantic Layer, MetricFlow,
  Malloy — without a citation. [docs/08-positioning.md](docs/08-positioning.md) frames every
  comparison as SemantiQL's intent for exactly this reason.
- **Keep the README roadmap and `docs/05-datasources.md` in sync.**
- The README's Key ideas summarise the invariants above; changing one means changing both.

## Not yet built

So you don't propose these as bugs: the MCP server, the Postgres adapter, schema
introspection (`semantiql init`), the accuracy benchmark, the self-improvement loop, and the
Data Governance layer (layer 3 — named in the code map, deliberately unimplemented).

Two decisions are open and should be flagged rather than silently resolved: auth for a
shared multi-user server, and Open Semantic Interchange compatibility for the model YAML.
