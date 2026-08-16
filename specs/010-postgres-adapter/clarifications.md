---
type: Clarifications
title: Postgres adapter — clarifications
description: 8 ambiguities resolved before planning — driver, dependency shape, CLI selection, corpus, type classification, file sources, read-only scope, and how CI gets a database without a secret.
resource: specs/010-postgres-adapter/clarifications.md
tags: [sdd, clarifications, adapters, postgres]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T00:35:00+07:00' }
sources:
  - id: duckdb-adapter
    resource: ../src/semantiql/adapters/duckdb.py
    title: The one existing adapter — the precedent every decision here is measured against
    last_modified: 2026-08-17
  - id: e2e-conftest
    resource: ../tests/e2e/conftest.py
    title: The skip-with-a-reason precedent for a suite that needs something not always present
    last_modified: 2026-08-16
  - id: verify
    resource: ../scripts/verify.sh
    title: The verify gate — where a new suite becomes a visible step with a visible skip
    last_modified: 2026-08-16
  - id: ci
    resource: ../.github/workflows/ci.yml
    title: The secret-free CI contract that fork PRs depend on
    last_modified: 2026-08-15
status: stable
---

Every decision below was made **by the agent** on an autonomous run, from the evidence named in
each rationale. None was made by the user. Q2, Q3 and Q6 are flagged in the run report as
judgement calls, because reversing them later costs more than the others.

## Q1: Which Postgres driver?

- (a) `psycopg` v3 with the `binary` extra — prebuilt wheels, sync API, ships `py.typed`
- (b) `psycopg2-binary` — the older, most widely deployed driver
- (c) `pg8000` — pure Python, no wheels or libpq needed at all
- (d) `asyncpg` — fastest, async-only

**Chosen: (a) `psycopg[binary]>=3.1` — decided by the agent from the manifest and the mypy
config.** (d) is the wrong shape: every call site here is synchronous, and adding an event loop
to satisfy a driver is the tail wagging the dog. (b) is in maintenance rather than development
and needs `types-psycopg2` stubs. (c) is genuinely attractive for the zero-setup promise, but it
is a much smaller project and its type coverage is weaker. The deciding evidence is
`pyproject.toml`: `mypy` runs `strict`, and `duckdb` already needed an `ignore_missing_imports`
override because it ships no stubs. psycopg 3 ships `py.typed`, so it needs no such override —
this change adds a dependency **and removes** a reason to add a second strict-mode exemption.
The `binary` extra means no libpq build step, which is what the ≤15-minute setup rule requires.

## Q2: Hard dependency, or an optional `semantiql[postgres]` extra?

- (a) Hard dependency, alongside `duckdb`
- (b) Optional extra, imported lazily, with an install hint when it is missing

**Chosen: (a) hard dependency — decided by the agent from the constitution's roadmap.** The
roadmap table names the MVP as "DuckDB + Postgres", not DuckDB with Postgres available
separately; an extra would make one of the two MVP engines second-class. (b) also introduces a
runtime failure mode — an `ImportError` at adapter construction — in a project whose setup rule
is that every error carries a fix instruction, and `duckdb` is a substantially larger wheel than
`psycopg[binary]`, so the "keep the base install lean" argument does not survive contact with
what is already installed. **Flagged as a judgement call:** moving to an extra later is a
breaking change for anyone who relied on the base install pulling Postgres in.

## Q3: How does the user choose an adapter?

- (a) Explicit `--datasource {duckdb,postgres}`, defaulting to `duckdb`
- (b) Infer it from the model's `datasource.dialect`
- (c) Overload `--database` — a DSN-looking value means Postgres

**Chosen: (a) explicit `--datasource` — decided by the agent from `engine/run.py:38`.** (b) reads
as the elegant answer and is the wrong one: `run` already refuses when
`model.datasource.dialect != adapter.dialect`, and inferring the adapter from the model makes
that refusal unreachable by construction. That check is not ceremony — it is what catches "this
model was written for DuckDB and I meant to query Postgres", and under (b) that mistake silently
opens DuckDB instead of reporting anything. (c) guesses from the shape of a string, which is the
class of behaviour N2 exists to refuse. Under (a) the mismatch stays a loud, early refusal.
`--database` keeps its current DuckDB-only meaning, so FR-7 holds. **Flagged as a judgement
call:** it costs the user one more flag than (b).

## Q4: How are connection details supplied?

- (a) `--dsn`, required whenever `--datasource postgres`
- (b) `--dsn`, falling back to libpq's own environment variables (`PGHOST`, `PGUSER`, …)
- (c) A new `SEMANTIQL_DSN` environment variable

**Chosen: (b) — decided by the agent from FR-6 and from how psycopg already behaves.** Passing
no conninfo makes libpq read its standard environment, so (b) is free rather than extra code,
and it is the mechanism every Postgres tool on the analyst's machine already uses — including
`.pgpass`, which is how a password stays out of shell history and out of `ps` output. (c) would
invent a project-specific spelling for a thing that has a universal one. Either way the model
YAML carries no connection detail, which is the actual requirement.

## Q5: What corpus does the differential suite compare on?

- (a) The TPC-H corpus from `tests/e2e/`, copied into Postgres table by table
- (b) The ten-row `examples/retail/` corpus, loaded into Postgres by a fixture
- (c) A new Postgres-only corpus

**Chosen: (b) — decided by the agent from what the suites already assert.** The question the
differential suite answers is whether two dialects agree, not whether the engine scales; ten
rows falsify a dialect bug exactly as well as sixty thousand and cost nothing to load. `tests/`
already carries hand-computed totals over the retail corpus, so a Postgres run that disagrees
with them is wrong against an independent third answer rather than merely against DuckDB. (a)
would make the Postgres suite inherit the e2e suite's network-dependent `dbgen` skip on top of
its own database skip — two reasons to be silent, which is how a suite quietly stops running.

## Q6: A model `source` of `orders.csv` on Postgres — what happens?

- (a) Treat it as a table name, as `relation()` does for anything without a known suffix
- (b) Raise `AdapterError` naming the file source as unsupported on this engine
- (c) Let it through and rely on Postgres's own error

**Chosen: (b) — decided by the agent from N2.** Under (a) and (c) the analyst gets
`relation "orders.csv" does not exist`, which sends them looking for a missing table when the
real problem is that Postgres has no file sources at all. The suffix check that
`DuckDBAdapter.relation` uses to *enable* CSV and Parquet is the same check that identifies them
here, so this costs one branch.[^duckdb-adapter] Schema-qualified names are unaffected: only
`.csv` and `.parquet` are recognised, so `analytics.orders` stays an ordinary qualified table.

**This corrects the spec.** `spec.md` claimed the model is identical between engines except for
`datasource.dialect`. That is true of `tables`, `dimensions`, `measures` and `metrics` — the
semantic content — but a `source` naming a file cannot be honoured by an engine with no file
sources. The What section is amended to say so rather than to overstate N3.

## Q7: How does `columns()` learn a Postgres type's name?

- (a) Probe with `SELECT * … LIMIT 0` and map the OID in `cursor.description` to a type name
- (b) Query `information_schema.columns` for `data_type`

**Chosen: (a) — decided by the agent from the shape of the Protocol.** `Adapter.columns` takes a
model `source` and is documented as building its probe through `relation()` so the value is
built in rather than interpolated (spec 009). (b) would abandon that and interpolate a parsed
schema and table name into a catalogue query — reintroducing exactly the injection surface 009
closed, and failing on anything `information_schema` does not list. (a) mirrors
`DuckDBAdapter.columns` line for line, which also means a reader who understands one adapter
understands both. psycopg exposes the OID as `description[i].type_code` and carries a type
registry to resolve it to a name; **the plan must verify that API against the installed version
before the adapter is written**, following the AST-probe precedent set by spec 004.

## Q8: How does CI get a Postgres without a repository secret?

- (a) A GitHub Actions service container, credentials written inline in the workflow
- (b) Skip the Postgres suite in CI entirely, leaving it a local-only check
- (c) A hosted test database behind a repository secret

**Chosen: (a) — decided by the agent from `.github/workflows/ci.yml`.** (c) is ruled out by the
constitution: a repository secret is unavailable to a fork PR, which is precisely the failure
that workflow's header comment says it exists to avoid.[^ci] (b) makes the suite decorative — a
check that only runs when someone remembers is one `pytest.ini` comment already calls out as
rotting. A service container needs no secret at all: `POSTGRES_PASSWORD` is a literal in the
workflow file, the database is created fresh per job and destroyed with it, and there is nothing
to leak because nothing outlives the run.

The local half is the `e2e` precedent: the suite gets its own `pg` marker and its own step in
`scripts/verify.sh`, and a fixture that **skips with a stated reason** when no Postgres is
reachable.[^e2e-conftest] So a fresh clone with no database still passes `verify.sh`, and the
skip is visible as its own line rather than buried in the unit run — which is exactly why the
e2e suite is a separate step rather than folded into the main one.[^verify]

[^duckdb-adapter]: `src/semantiql/adapters/duckdb.py` — `relation()`'s `.csv` / `.parquet` suffix branch.
[^ci]: `.github/workflows/ci.yml` — the header comment on why no repository secret may be used.
[^e2e-conftest]: `tests/e2e/conftest.py` — `pytest.skip` with a stated reason at line 102.
[^verify]: `scripts/verify.sh` — the e2e step and its comment on why a skip must stay visible.
