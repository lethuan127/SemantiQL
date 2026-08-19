# AGENTS.md

Guidance for AI coding agents working in this repository, whichever tool you are.

This is the single agent brief. `CLAUDE.md` is a **symlink to this file**, so there is one
copy to keep true rather than two that drift — if you are reading this as `CLAUDE.md`, you
are reading `AGENTS.md`.

Humans: [CONTRIBUTING.md](CONTRIBUTING.md) covers the same ground with more context.

## What this project is

SemantiQL sits between an LLM and a SQL database. The model writes **semantic SQL** against
a business model — dimensions, measures, metrics — and SemantiQL validates it, compiles it
to physical SQL, and runs it. All three exist in the model today; metrics are derived from
measures under a closed expression grammar, checked when the model loads (spec 006). Four layers, described in
[docs/02-architecture.md](docs/02-architecture.md) and mapped to modules in
[docs/07-code-map.md](docs/07-code-map.md).

**Read the code map before your first change.** It tells you which module owns what, and
it is short.

## Repository layout

Three documents describe where things live, and they are not redundant. **The constitution's Taxonomy
is authoritative** for what it covers; [docs/07-code-map.md](docs/07-code-map.md) owns module ownership
inside `src/`; this table adds the one thing neither does — **what you are allowed to do to each
directory**.

| Path | Holds | The rule for you |
|---|---|---|
| `src/semantiql/` | the four layers | module ownership is in the code map. Read it before your first change |
| `tests/` | three suites, mirroring `src/` | the directory says which layer; the **marker** says what it needs. A suite that cannot run must skip, never fail |
| `examples/` | the bundled example **and** the unit suite's corpus | totals are asserted by hand. Changing a row means recomputing them |
| `specs/` | SDD change records, an OKF bundle | validate with `specs/`, never the repo root |
| `docs/NN-*.md` | the design docs | **trust-boundary artifacts.** Editing one is never routine — say so explicitly |
| `docs/cookbooks/` | per-datasource walkthroughs | not trust-boundary. Every output must be labelled captured or not |
| `scripts/verify.sh` | the gate | never weaken a check to make it pass. Adding a step means its cost and any skip are visible |
| `scripts/fixtures/` | fixture loaders and the run judge | **committed on purpose**; their output goes to `.test-workspace/` |
| `.claude-plugin/` | `marketplace.json` — the marketplace this repo *is* | shipped product. Without it `claude plugin install` cannot reach the plugin at all |
| `plugin/` | the shipped plugin: `.mcp.json`, `skills/semantiql/SKILL.md`, `evals/` | shipped product. That `SKILL.md` is a trust boundary, and N6 applies to it as much as to code |
| `bundle/` | a three-line entry point | the manifest and source are **generated** at build time. Never a second copy of the package in git |
| `compose.yaml` | a throwaway Postgres | the gate may never require Docker |
| `.specify/memory/` | the constitution | **no agent amends it.** Propose a diff and stop |
| `.claude/` | this repo's own tooling | not shipped. Do not mix it with `.claude-plugin/` — they differ by a hyphen and are opposites |
| `.test-workspace/` | fixture data, answer keys, run logs | git-ignored **output only**. If code lands here it is invisible to a clone |
| `dist/` | build output | ignored |

Four things that are easy to get wrong, and each has cost something:

**`.claude-plugin/` and `.claude/` are opposites.** The first is shipped product — the marketplace
manifest that makes the plugin installable. The second is this repository's own tooling. The names
differ by a hyphen and a word.

**Code in `.test-workspace/` is invisible.** Seven fixture scripts lived there while their own
docstrings claimed *the script is the artefact and the data is output* — and a fresh clone had none of
them (spec 022). Output belongs there; code belongs in `scripts/fixtures/`.

**`bundle/` holds no copy of the package.** `scripts/build_bundle.py` generates the manifest and copies
the source at build time, so git never carries two copies to drift apart.

**Answer keys are the examiner's copy.** `.test-workspace/examiner/` must stay out of any directory a
run under evaluation can read, or "does it ask the human what these columns mean" becomes reading
comprehension.

> **Known gap, for a human to close.** The constitution's Taxonomy predates `plugin/`,
> `.claude-plugin/`, `bundle/` and `src/`, so it has no row for any of them — and it explicitly says
> "the rows above cover the top level only". This table is not a substitute: the constitution governs,
> and **no agent amends it**. The proposed rows, for a human to apply to
> `.specify/memory/constitution.md`:
>
> ```
> | `src/` | the four layers; module ownership is mapped in docs/07-code-map.md, not here |
> | `plugin/`, `.claude-plugin/` | shipped product — the plugin, and the marketplace manifest that installs it |
> | `bundle/` | the Desktop bundle's entry point; its manifest and source are generated at build time |
> | `.test-workspace/` | ignored output only — fixture data, answer keys, run logs. Never code |
> ```

## Setup and checks

Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                  # venv + dependencies from uv.lock
./scripts/verify.sh      # everything CI runs: ruff format, ruff lint, mypy, pytest, OKF
```

While iterating:

```bash
uv run pytest tests/test_compile.py::test_each_predicate_renders   # one test
uv run pytest -m "not e2e"                                         # skip the slow suite
uv run ruff format . && uv run ruff check --fix .                  # fix style
uv run mypy                                                        # strict
```

Three suites, and `tests/` mirrors `src/semantiql/` — `knowledge/`, `engine/`, `adapters/`, plus
`interfaces/`, `integration/` and `tooling/`. The directory says which layer a test covers; the
**marker** says what it needs to run. Take repository paths from `tests/_support.py`, never by
counting `..`. The unit suite runs against the ten-row `examples/retail/` corpus with hand-computed
totals. `tests/e2e/` generates a TPC-H corpus and checks the engine against hand-written
physical SQL — scale it with `SEMANTIQL_E2E_SF`, and expect it to skip offline on a first run
because the generator extension is fetched once from DuckDB's repository. The `pg` suite runs
the same questions on DuckDB **and** Postgres and fails if they disagree; it needs a database,
so `compose.yaml` provides a throwaway one:

```bash
docker compose up -d --wait
SEMANTIQL_TEST_DSN=postgresql://postgres:postgres@127.0.0.1:55432/semantiql_test ./scripts/verify.sh
docker compose down
```

Without `SEMANTIQL_TEST_DSN` the `pg` step **skips with a stated reason and the gate still
passes** — that is deliberate and load-bearing (spec 010, FR-11), so never make the gate depend
on Docker.

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

Also refused, for the same reason: any construct the compiler cannot honour — `HAVING`,
`DISTINCT`, CTEs, subqueries, joins, `TABLESAMPLE`, `PIVOT`.

What *is* supported, and how tightly: `WHERE` over **dimensions** compared to **literals**
whose type matches the dimension's declared `type`, with the predicate rebuilt from the model
rather than carried over (spec 004); and `ORDER BY` over names the request **selects**, plus
`LIMIT`/`OFFSET` as non-negative whole numbers (spec 005); metrics derived from measures under
a closed expression grammar (spec 006); and `DATE_TRUNC('<grain>', <date dimension>)` in the
SELECT list (spec 007), truncating a **cast** column so the bucket cannot depend on the database
server's timezone, or an `AT TIME ZONE` conversion when the dimension declares `timezone:`
(spec 011). Filtering a measure is refused as needing `HAVING`; ordering by a
position or an unselected name is refused; and `MONTH()`/`EXTRACT()` are refused because they
extract a number rather than truncating, which would collapse every July into one row.

The reason refusal is the default: `compile_request` rebuilds the query from the model, so an
unvalidated construct would *vanish* and the caller would get a wrong number.

That check is an **allowlist**: `_SELECT_ARGS` and `_FROM_NODE_ARGS` in `validate.py` name
what the compiler consumes — node types *and* the arguments each may carry — and everything
else is refused for being absent from them. It used to be a denylist and it failed:
`TABLESAMPLE` and `PIVOT` were listed by name and still slipped through, because sqlglot
attaches them to the table rather than to the SELECT, and `ONLY`/`WITH ORDINALITY` slipped
through a node-type check because sqlglot stores them as bare flags (spec 003). So:
if you implement a construct, add it to the allowlist **in the same change that teaches the
compiler to honour it — never before**.

**N3 — The semantic model YAML is the source of truth.** `knowledge/loader.py` is the only
thing that reads it. Never hard-code a model value in Python.

A model may be one file or a **directory** of them, one per table (spec 015). Every ambiguity in
the merge is refused naming the files — a table defined twice, `datasource` declared twice or not
at all, a file contributing nothing — because last-one-wins across files is the same silent
redefinition the duplicate-key check refuses within one.

The model is written by **Claude, reviewed by a human** — not by a wizard and not usually by hand.
`semantiql inspect` reads a datasource's catalogue with no model required, and the skill drives it:
inspect, ask the analyst what a schema cannot say, write one YAML per table, loop on `doctor`
(spec 016). Two limits are in the skill and tested for drift: **never invent a measure's
aggregation or a metric's formula**, and **never change a model to answer a question** — the
second is N6, since editing a definition mid-answer is exactly the unreviewed change it forbids.

**N4 — One canonical dialect, then transpile.** Adding a datasource is one new module under
`adapters/` satisfying `adapters/base.py`, with **no change to `engine/`**. Verify with:

```bash
grep -rnE "adapters(\.|[[:space:]]+import)" src/semantiql/engine/   # only adapters.base
```

That catches imports only. DuckDB is also the hard-coded canonical dialect in
`compile.py` and the parse dialect in `validate.py` — deliberate, and unchanged by the second
adapter. See [docs/07-code-map.md](docs/07-code-map.md).

**N4 has now been tested rather than assumed** (spec 010). Adding Postgres changed **zero files
under `engine/`**, and `tests/test_postgres_differential.py` asserts both engines answer the
same model identically. Two things that only a second adapter could reveal:

- **The seam was incomplete.** `close()` was called by the CLI and implemented by both adapters
  but never declared on the `Adapter` Protocol. It went unnoticed because the CLI was typed
  against `DuckDBAdapter`; an outside adapter written to the published Protocol would have
  passed `isinstance`, passed mypy, then crashed on exit. Adding it was part of 010.
- **`DATE_TRUNC` diverges on identical SQL.** Postgres resolves `date_trunc(text, date)` to its
  `timestamptz` overload, so the result carries the server's timezone where DuckDB's does not.
  Buckets and totals agree today, so it is pinned by a test rather than fixed — fixing it means
  changing `compile.py`, which needs its own spec.

So the shape of N4 holds. Read "no core changes" as a claim about `engine/`, not as a promise
that the adapter seam is already complete — a gap in the seam is a finding, and finding one is
not a reason to touch `engine/`.

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

So you don't propose these as bugs: the `semantiql init` wizard (`inspect` reads a
catalogue as of spec 016, but nothing writes a model non-interactively), the accuracy
benchmark, the self-improvement loop, and the Data Governance layer (layer 3 — named in the code
map, deliberately unimplemented).

The MCP server ships (spec 012), packaged as a plugin with a skill (spec 013), with exactly
**two** read-only tools, `describe_model` and `query`. That surface is the enforcement boundary, not a starting set: a shell-based skill would
be easier and would let the model reach the database by any route. Adding a third tool is a
design decision, not a convenience — and a refusal must keep travelling as a normal answer
carrying its reason, because that reason is what lets Claude repair its own query.

**`.claude-plugin/`, `plugin/` and `bundle/` are shipped product; `.claude/` is this repo's own
tooling.** Don't mix them — the first and the last differ by a hyphen and a word, and they are
opposites. `.claude-plugin/marketplace.json` is what makes the plugin installable at all: Claude Code
installs from a *marketplace*, so the two documented commands are

```bash
claude plugin marketplace add "$PWD"      # the repo root, not plugin/
claude plugin install semantiql@semantiql
```

and pointing `marketplace add` at `plugin/` fails, which is what `docs/03-setup-workflow.md` A1 used
to tell people to do (spec 017). `bundle/` holds only a three-line entry point — `scripts/build_bundle.py` generates the
manifest and copies the source at build time, so there is never a second copy of the package in
git. `dist/` is build output and ignored. And N6
applies to `plugin/skills/semantiql/SKILL.md` as much as to code: a skill that told Claude to add
a missing metric would put the meaning tier under automatic change. It says stop, and
`tests/test_plugin.py` asserts that it still does — along with asserting the grains it teaches are
exactly the grains `validate` accepts.

Two decisions are open and should be flagged rather than silently resolved: auth for a
shared multi-user server, and Open Semantic Interchange compatibility for the model YAML.
