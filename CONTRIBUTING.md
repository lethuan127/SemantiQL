# Contributing to SemantiQL

Written for someone with no context and no access to anything private. If a step here does
not work from a clean clone, that is a bug in this file — please report it.

## Status and what to expect

SemantiQL is **experimental and pre-release**. The API will change.

Maintained by [@lethuan127](https://github.com/lethuan127) as time allows: **issues and
pull requests are triaged weekly, with no SLA.** That is an honest description rather than
a target — if something is urgent, it is better to fork than to wait.

**Open an issue before writing a large pull request.** An unsolicited large PR is usually
declined, not because it is unwelcome but because the design may not fit, and that is a
frustrating way to discover it. A short issue first costs you ten minutes and can save a
weekend.

## Setup

Requires **Python 3.11 or newer** and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/lethuan127/semantiql
cd semantiql
uv sync                 # creates the venv and installs everything, including dev tools
```

`uv sync` reads `uv.lock`, so you get the same dependency versions CI does. If `uv` is
missing, `scripts/verify.sh` will tell you how to install it rather than failing obscurely.

Check it worked:

```bash
uv run semantiql "SELECT revenue, channel FROM orders" --show-sql
```

## Git hooks

Optional but recommended — one command wires them up:

```bash
./scripts/install-hooks.sh     # sets core.hooksPath to the tracked .githooks/
```

- **pre-commit** runs `./scripts/verify.sh`, so a broken commit never leaves your machine.
  It checks the *working tree*, not the staged snapshot — a partial stage can still differ
  from what you commit, which is why CI checks the real thing.
- **commit-msg** lints against Conventional Commits (below).

Bypass either with `git commit --no-verify`. Turn them off with
`git config --unset core.hooksPath`.

## Commit messages

Conventional Commits, enforced by the `commit-msg` hook:

```
<type>(<optional scope>): <description>

feat(engine): refuse WHERE instead of dropping it
fix: resolve a relative source against the model file
docs(code-map): correct the read-only claim
```

Types: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`, `init`.
Subject ≤ 72 characters, no trailing full stop, blank line before any body. Merge, revert
and fixup messages are exempt. The linter is dependency-free Python
(`scripts/lint_commit_msg.py`) rather than commitlint, which would have pulled in a second
runtime.

## Running the checks

One command runs everything CI runs:

```bash
./scripts/verify.sh
```

It stops at the first failure and names the step. To run pieces while iterating:

```bash
uv run pytest                                   # all tests
uv run pytest -m "not e2e"                      # skip the end-to-end suite while iterating
uv run pytest tests/test_compile.py             # one file
uv run pytest tests/test_compile.py::test_alias_is_honoured_not_discarded   # one test
uv run pytest -k refus                          # tests matching a name
uv run ruff format .                            # fix formatting
uv run ruff check --fix .                        # fix what is safely fixable
uv run mypy                                      # types (strict)
```

### The three test suites

**Unit tests** run against `examples/retail/` — ten rows whose expected totals were computed
by hand. They are exact, they need nothing installed, and they are what you run on every save.

**End-to-end tests** (`tests/e2e/`, marked `e2e`) generate a TPC-H corpus into a temporary
DuckDB file and check the engine against **hand-written physical SQL** rather than against
pinned numbers — so a mistranslation fails the first time it runs. Sixty thousand rows and
seven years of dates at the default scale, which costs a fraction of a second.

```bash
SEMANTIQL_E2E_SF=1 uv run pytest -m e2e         # six million rows, for a soak run
```

Building the corpus uses DuckDB's `tpch` extension, which is fetched once from DuckDB's
extension repository. **With no network on a first run the suite skips rather than fails** —
the clone still has to work on a plane — so if you see it skip, that is why.

**Postgres tests** (marked `pg`) ask the same questions on DuckDB *and* Postgres and fail if the
two disagree — the only check that can catch a dialect bug that returns a plausible wrong
number. They need a database, so the repo ships one:

```bash
docker compose up -d --wait                      # postgres on 55432, data in memory
SEMANTIQL_TEST_DSN=postgresql://postgres:postgres@127.0.0.1:55432/semantiql_test \
  uv run pytest -m pg
docker compose down
```

Two things worth knowing. The port is **55432 rather than 5432 on purpose**: the fixtures
`DROP TABLE` before loading each corpus, and an unusual port means a mistyped or pasted DSN
reaches this container or nothing at all. And **the gate never requires Docker** — with
`SEMANTIQL_TEST_DSN` unset the `pg` step skips with a stated reason and `./scripts/verify.sh`
still passes, because a fresh clone has to run with nothing installed.

## What makes a pull request mergeable

- **`./scripts/verify.sh` passes.** No exceptions, and please don't weaken a check to make
  it pass — that turns a visible failure into a silent one.
- **A behaviour change comes with a test.** For anything touching validation, a test that
  proves the *refusal* path, not only the happy one.
- **One concern per PR.** A formatting sweep mixed into a logic change is hard to review
  and harder to revert.
- **Types are real.** mypy runs strict; `Any` at a database boundary is fine, `Any` to
  silence an error is not.

## The invariants a change must not break

These are not style preferences. They are recorded in
[`.specify/memory/constitution.md`](.specify/memory/constitution.md), and a change that
needs one amended needs its own spec first.

- **Validation is the point.** Every query is checked against the semantic model before it
  runs, and a query that cannot be validated is **refused, never guessed at**. A plausible
  wrong number is the worst thing this project can produce, because the person reading it
  never sees the SQL. `engine/run.py` is the single chokepoint — don't add a second path to
  the data.
- **The semantic model YAML is the source of truth.** `knowledge/loader.py` is the only
  thing that reads it. No model values hard-coded in Python.
- **One canonical dialect, then transpile.** Adding a datasource means one new module under
  `adapters/` satisfying `adapters/base.py`, and **no change to `engine/`**. If a
  datasource forces an `engine/` change, that is a design problem worth raising as an
  issue.
- **Read-only by default.** Nothing in the query path needs write access.
- **No NoSQL.** Permanently out of scope.

[`docs/07-code-map.md`](docs/07-code-map.md) maps the architecture to the modules, and is
the fastest way to find where a change belongs.

## Out of scope

Please don't open PRs for these; they will be declined:

- NoSQL support of any kind.
- Removing the validation step, or adding a "just run this SQL" escape hatch.
- Replacing sqlglot with a different transpiler.
- Large dependency additions. Ask in an issue first — the dependency set is deliberately
  small.

## Commits and reviews

No commit-message convention is enforced. Write a subject line that says what changed and
why; if it needs a paragraph, add one.

There is no CLA or DCO to sign.
