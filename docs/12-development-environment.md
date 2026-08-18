# Setting up a development machine

Everything you need beyond `git clone`, in the order to install it, with **what breaks if you skip it**.
That last column is the point: most of this is optional, and a list that does not say which is optional
leaves you installing a Postgres client to run a unit test.

Every command here was run on a real machine while writing this. Where something cannot be reproduced
at all, it says so rather than pretending.

## Required — the gate will not pass without these

| Tool | Why | Install |
|---|---|---|
| **Python 3.11+** | the runtime | your platform's package manager, or `uv python install 3.11` |
| **uv** | dependencies, the venv, every documented command | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **git** | the OKF change records and one gate check read git itself | your platform's package manager |

```bash
git clone https://github.com/lethuan127/semantiql && cd semantiql
uv sync
./scripts/verify.sh
```

**That gate passes with nothing else installed.** It skips the Postgres suite with a stated reason and
skips the plugin-manifest step if the Claude CLI is absent. If it fails on a fresh clone, that is a bug
worth reporting rather than something for you to work around.

## Optional — each unlocks one thing

| Tool | Unlocks | Skipping it costs you | Install |
|---|---|---|---|
| **Docker** | the `pg` suite: 64 tests over real Postgres, incl. TPC-H parity | those tests skip; the gate still passes | Docker Desktop, or Colima |
| **`psql`** | the fixture loaders, which shell out to it to create databases | `scripts/fixtures/*.py` fail; nothing else | `brew install postgresql@17` (client is enough) |
| **Claude Code** | the plugin, the skill, and the manifest gate step | one gate step skips, saying why | https://claude.com/claude-code |
| **tmux** | interactive eval runs, where the skill can actually *ask* a question | headless runs only — and headless cannot ask, which changes what you observe | `brew install tmux` |
| **PluginEval** | scoring the skill (`scripts/eval_plugin.py`) | that script skips with an install hint | see below |

### Docker, for the Postgres suite

```bash
docker compose up -d --wait
SEMANTIQL_TEST_DSN=postgresql://postgres:postgres@127.0.0.1:55432/semantiql_test ./scripts/verify.sh
docker compose down
```

The container binds `127.0.0.1:55432` and uses tmpfs, so it is throwaway. Without `SEMANTIQL_TEST_DSN`
the `pg` step skips with a stated reason **and the gate still passes** — that is deliberate and
load-bearing, so never make the gate depend on Docker.

### PluginEval, for scoring the skill

```bash
claude plugin marketplace add wshobson/agents
claude plugin install plugin-eval@claude-code-workflows
uv run python scripts/eval_plugin.py --runs 3
```

MIT-licensed, installed at user scope, and **not** a project dependency — `pyproject.toml` does not
mention it. `scripts/eval_plugin.py` skips with an install hint when it is absent.

### The plugin itself

```bash
claude plugin marketplace add "$PWD"          # the repo root, not plugin/
claude plugin install semantiql@semantiql
```

Use the default scope. `--scope local` also works and writes an absolute path to your checkout into
`.claude/settings.local.json`, inside the repository.

## Fetched at runtime, so a first run needs network

Three DuckDB extensions are downloaded on first use and cached after. They are easy to miss because
nothing declares them:

| Extension | Used by | Fetched when |
|---|---|---|
| `httpfs` | reading parquet over HTTPS | the taxi loader |
| `postgres` | `ATTACH`-ing Postgres to copy data in | every fixture loader |
| `excel` | reading the retail workbook | the retail loader |

The `e2e` suite likewise fetches DuckDB's TPC-H generator once. **Offline, on a first run, it skips with
a stated reason** rather than failing — but it will not produce a corpus until it has been online once.

## The fixtures

`scripts/fixtures/` holds the loaders. They are **committed**; their output is not — it lands in
`.test-workspace/`, which is git-ignored in its entirety.

| Script | Loads | Needs |
|---|---|---|
| `build.py` | a 5-row DuckDB fixture with hand-checkable totals | nothing |
| `seed.sql` | the same fixture on Postgres | `psql`, Docker |
| `fetch.py` | 2.96M real NYC taxi trips | `psql`, Docker, network |
| `fetch_retail.py` | 1,067,371 real UK retail invoice lines (CC BY 4.0) | `psql`, Docker, network |
| `fetch_salt.py` | SAP SALT ERP sales data | as above, **plus access — see below** |
| `judge.py` | grades a discovery-run transcript: rules in code, rubric by LLM | a transcript |
| `run-debug.sh` | launches a run with full debug logging into `.test-workspace/logs/` | `tmux` for the interactive mode |

```bash
docker compose up -d --wait
uv run python scripts/fixtures/fetch_retail.py     # ~2 min, downloads 46 MB
```

## What cannot be reproduced, on any machine, right now

Named rather than omitted, so you do not spend an afternoon looking for your mistake.

**`claude plugin eval` is gated.** It exits 1 with *"`plugin eval` is currently in early access"*. The
gate is an account entitlement inside a compiled binary — there is no flag, and nothing in settings
changes it. So `plugin/evals/` has never been scored. Its schema is documented in
[11-plugin-eval.md](11-plugin-eval.md).

**SAP SALT is not accessible.** `fetch_salt.py` is finished and its failure path is what has been
exercised. With a valid token, Hugging Face answers 403: *"Access to dataset SAP/SALT is restricted and
you are not in the authorized list."* Accept the terms at
https://huggingface.co/datasets/SAP/SALT with the account the token belongs to, put
`HF_ACCESS_TOKEN=<token>` in `.env` (already git-ignored), and the loader reads it **itself** — the
token is never printed, never passed as an argument, and never seen by an agent.

## Secrets

`.env` and `.env.*` are git-ignored and nothing env-shaped is tracked. Postgres credentials for the
throwaway container are in `compose.yaml` on purpose: it binds to localhost, holds only fixtures, and
CI must stay secret-free so fork pull requests run. Never add a real credential to it.
