---
type: Plan
title: Postgres adapter — plan
description: One new adapter module plus an adapter-selection seam in the CLI, with a differential suite over the retail corpus and a secret-free CI service container; zero files changed under engine/.
resource: specs/010-postgres-adapter/plan.md
tags: [sdd, plan, adapters, postgres]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T00:52:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-15
  - id: clarifications
    resource: clarifications.md
    title: The 8 decisions this plan implements
    last_modified: 2026-08-17
  - id: base
    resource: ../src/semantiql/adapters/base.py
    title: The Adapter Protocol, ColumnKind, Column, AdapterError — the seam to fit
    last_modified: 2026-08-17
  - id: duckdb-adapter
    resource: ../src/semantiql/adapters/duckdb.py
    title: The existing adapter — relation(), _KINDS, _kind(), columns() probe, execute(), close()
    last_modified: 2026-08-17
  - id: cli
    resource: ../src/semantiql/cli.py
    title: Where DuckDBAdapter is constructed by name, and where --database is parsed
    last_modified: 2026-08-17
  - id: run
    resource: ../src/semantiql/engine/run.py
    title: The chokepoint, and the dialect-mismatch refusal at line 38
    last_modified: 2026-08-15
  - id: compile
    resource: ../src/semantiql/engine/compile.py
    title: CANONICAL_DIALECT = duckdb, and the transpile at line 223
    last_modified: 2026-08-16
  - id: doctor
    resource: ../src/semantiql/doctor.py
    title: check() takes an Adapter, not a DuckDBAdapter — already engine-agnostic
    last_modified: 2026-08-17
  - id: model
    resource: ../src/semantiql/knowledge/model.py
    title: Datasource.dialect is already Literal["duckdb", "postgres"]
    last_modified: 2026-08-16
  - id: conftest
    resource: ../tests/conftest.py
    title: The session `model` and function `adapter` fixtures over the retail corpus
    last_modified: 2026-08-15
  - id: adapter-test
    resource: ../tests/test_adapter_duckdb.py
    title: The Protocol-conformance test shape, and its stated limit
    last_modified: 2026-08-17
  - id: doctor-test
    resource: ../tests/test_doctor.py
    title: The finding-kind assertions a Postgres run has to reproduce
    last_modified: 2026-08-17
  - id: e2e-conftest
    resource: ../tests/e2e/conftest.py
    title: The skip-with-a-stated-reason fixture precedent
    last_modified: 2026-08-17
  - id: verify
    resource: ../scripts/verify.sh
    title: The gate's steps, and why e2e is a separate one
    last_modified: 2026-08-17
  - id: ci
    resource: ../.github/workflows/ci.yml
    title: The secret-free contract, the 3.11/3.13 matrix, and the single verify step
    last_modified: 2026-08-15
  - id: pyproject
    resource: ../pyproject.toml
    title: Dependencies, the duckdb mypy override, and the pytest markers block
    last_modified: 2026-08-17
  - id: readme
    resource: ../README.md
    title: Line 15 says Postgres is not built yet; the roadmap table at line 101
    last_modified: 2026-08-17
  - id: datasources-doc
    resource: ../docs/05-datasources.md
    title: The roadmap table this change has to keep in sync with the README
    last_modified: 2026-08-15
  - id: example-model
    resource: ../examples/retail/semantic_model.yml
    title: The retail model — CSV sources, and the comment claiming a one-line engine swap
    last_modified: 2026-08-16
  - id: code-map
    resource: ../docs/07-code-map.md
    title: The module table, the N4 grep, and the "necessary but not sufficient" note at lines 71-76
    last_modified: 2026-08-17
  - id: agents
    resource: ../AGENTS.md
    title: The agent brief — "Not yet built" and the N4 section; CLAUDE.md is a symlink to it
    last_modified: 2026-08-17
  - id: psycopg-probe
    resource: specs/010-postgres-adapter/plan.md
    title: Live probe of psycopg 3.3.4 run at plan time — results recorded in decision 3 below
    last_modified: 2026-08-17
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-17T01:02:00+07:00', checkpoint: 2,
      basis: 'map derived from 19 file reads plus a live psycopg 3.3.4 probe; all 10 existing-file rows footnoted to a sources entry, after a self-audit caught 2 rows (docs/07-code-map.md, AGENTS.md) listed from CLAUDE.md description rather than from the files — both then read and re-footnoted, recorded as OQ-2. 3 open questions stated: OQ-1 unverifiable until the differential suite runs by design, OQ-2 resolved, OQ-3 has no repo evidence and is cheap to change' }
status: stable
---

# Constitution check

**N1 / N2 — validation over generation; a silently wrong number is the worst failure.** The
adapter neither validates nor rewrites: `execute` takes a string that `engine.run.run` has
already validated and transpiled, and the CLI reaches the data only through `run`.[^run] No new
query path is added — `_doctor` in the CLI keeps calling `check`, which calls `columns` and never
`execute`.[^cli] [^doctor] The N2 control specific to this change is the differential suite: two
engines disagreeing about one model is the exact failure a non-technical user cannot
see.[^constitution]

**N3 — the YAML is the source of truth, and datasource-independent.** Connection details reach
the adapter from the command line or libpq's environment, never from the model.[^clarifications]
One honest qualification, recorded rather than glossed: `examples/retail/semantic_model.yml`
carries a comment saying swapping `datasource.dialect` to postgres "changes nothing else in this
file", and that is not true of a model whose sources are CSV paths.[^example-model] The comment
is corrected in this change. N3's real claim — the *semantic* content is engine-independent —
survives; the overstatement does not.

**N4 — canonical dialect, then transpile.** This is the invariant under test. One new module
under `adapters/`, and **zero files changed under `engine/`**. `compile.py` keeps DuckDB as the
dialect it transpiles *from*, which is what "canonical" means; Postgres becomes a second value of
the `dialect` argument `run` already passes.[^compile] [^run] The existing grep stays the
check.[^constitution]

**N5 — read-only by default.** Stronger here than on DuckDB. `psycopg.Connection.read_only` is a
real attribute (probe-confirmed), and setting it makes the server itself reject a write, so the
guarantee does not rest only on `validate` refusing non-SELECTs — unlike the in-memory DuckDB
path, where it does.[^duckdb-adapter] The module docstring states this precisely, following the
precedent `adapters/duckdb.py` set.

**Amended during implement, after measuring rather than assuming.** `read_only` sets
*transaction* characteristics, so on an `autocommit=True` connection **it is silently ignored and
writes succeed**. Measured against the live server: with `autocommit=True` and `read_only = True`
both set, `CREATE TABLE` completed. So `autocommit` staying `False` is load-bearing for N5, not an
untouched default, and it is now commented as such with a test
(`test_a_write_is_rejected_by_the_server`) that fails if anyone turns it on. The cost is an
`idle in transaction` connection between queries, harmless for a CLI that opens, asks and closes,
and recorded in the docstring for whoever builds a server mode.

**N6, N7** — untouched. No learning loop, no NoSQL.

**Secret-free CI.** A service container's credentials are literals in the workflow file, so a
fork PR runs the suite to completion.[^ci] [^clarifications]

**Trust-boundary artifacts.** Three are touched, deliberately and in scope: `pyproject.toml`
(the manifest), `README.md`, and `docs/05-datasources.md`.[^constitution] Each is named in the
impact map below rather than discovered mid-implement, so no hard escalation should fire. The
constitution and `.claude/skills/*/SKILL.md` are **not** touched.

# Approach

**One module, one seam, one suite.**

`src/semantiql/adapters/postgres.py` mirrors `adapters/duckdb.py` structurally — same four
Protocol members, same probe-based `columns`, same `close()`. A reader who knows one knows the
other, which is the property that makes the seam teachable to the next contributor.[^duckdb-adapter]

The CLI grows an **adapter-selection function** rather than more branches at the call sites.
`cli.py` constructs `DuckDBAdapter` in two places today — `_doctor` and `main`.[^cli] Both move
to one `_open_adapter(args)` helper that returns an `Adapter`. That is the smallest change that
keeps the two paths from drifting, and it is the seam a third adapter plugs into.

`doctor.check` needs no change at all: it is already typed against `Adapter`, not
`DuckDBAdapter`.[^doctor] That is the first piece of evidence that N4 holds, and it is worth
saying that it was free.

Tests run at two seams. `tests/test_adapter_postgres.py` checks the adapter in isolation —
Protocol conformance, type classification, the file-source refusal — and most of it needs no
database at all, because `_kind` is a pure classmethod exactly as DuckDB's is.[^duckdb-adapter]
It reuses the conformance-test shape from `tests/test_adapter_duckdb.py`, including that test's
own stated limit: `isinstance` on a `runtime_checkable` Protocol compares member *names* only, so
mypy strict is what actually verifies the signatures.[^adapter-test]

`tests/test_postgres_differential.py` needs a live database and carries the `pg` marker: it loads
the retail CSVs into Postgres, then runs the same semantic SQL through both adapters and asserts
the answers match, plus asserts against the hand-computed totals `tests/` already
holds.[^conftest] [^clarifications] Its doctor half reproduces the three finding kinds
`tests/test_doctor.py` already pins for DuckDB, which is what makes "doctor works on Postgres" a
comparison rather than a fresh set of expectations.[^doctor-test]

**External dependency:** `psycopg[binary]>=3.1`, one line in `pyproject.toml`, no mypy override
needed.[^pyproject]

# Architecture decisions

**AD-1 — `_open_adapter(args) -> Adapter` in `cli.py`, not an adapter registry.** A registry
(name → class, populated by entry points) is where this ends up if third-party adapters become a
goal, and `base.py`'s docstring says a third-party adapter should not import SemantiQL
internals.[^base] But two adapters do not justify the indirection, and a registry would hide
which adapters exist from anyone reading the CLI. A function with an explicit two-branch match is
honest about the current state and costs nothing to replace later.

**AD-2 — the CLI keeps `--database` for DuckDB and adds `--dsn` for Postgres.** Not one
overloaded flag. `--database` means "a DuckDB file" today and every documented example and test
passes it that way.[^cli] [^readme] Overloading it would make the meaning depend on the value,
which clarification Q3 rejected on N2 grounds.[^clarifications] Supplying `--dsn` with
`--datasource duckdb` (or the reverse) is an argument error, reported by the parser rather than
half-honoured.

**AD-3 — type classification maps psycopg's short type *name*, and detects arrays by OID
identity.** Probe of psycopg 3.3.4, run at plan time:[^psycopg-probe]

```
psycopg.postgres.types.get(1043) -> name='varchar'  regtype='character varying'  oid=1043
psycopg.postgres.types.get(1015) -> name='varchar'  regtype='character varying'  oid=1043   # varchar[]
psycopg.postgres.types.get(1007) -> name='int4'     regtype='integer'            oid=23     # int4[]
psycopg.postgres.types.get(999999) -> None
```

Two things follow, and the second is the important one.

*Name versus regtype.* `name` is short and stable (`varchar`, `int4`, `timestamptz`); `regtype`
is what a DBA reads (`character varying`, `integer`, `timestamp with time zone`). So `_KINDS` is
keyed on `name` and `Column.native_type` carries `regtype` — which is exactly what `base.py` asks
for, "the engine's own name, kept for error messages a DBA will recognise".[^base]

*Arrays are actively disguised.* `types.get()` accepts an **array OID and returns the element
type**, with no flag saying so. A naive `types.get(oid).name` classifies an `integer[]` column as
`number`, and doctor would then bless a model that asks Postgres to `SUM` an array — the same bug
spec 009 found in DuckDB's `INTEGER[]`, arriving by a completely different route and invisible to
the same test.[^duckdb-adapter] Detection: the returned info carries its own `oid`, so
`info.oid != probed_oid` means the probed OID was the array form. Those classify `other`. **This
gets a test naming the bug**, because the next person to read the registry docs will be tempted
to simplify it back.

*Unknown OIDs return `None`*, which maps to `other` — the honest-unknown behaviour `base.py`
requires, for free.[^base]

**AD-4 — `columns()` probes with `SELECT * … LIMIT 0` built through `relation()`.** Identical to
DuckDB's, for the reason spec 009 gave: the `source` is built into the expression rather than
interpolated, so a quote in it stays a value.[^duckdb-adapter] Rejected: querying
`information_schema.columns`, which would require interpolating a parsed schema/table pair back
into a catalogue query.[^clarifications]

**AD-5 — a file `source` raises `AdapterError` from `relation()`.** `relation()` runs inside
`run` before `execute`, so the error surfaces through the CLI's existing exit-code-3
path.[^run] [^cli] Only `.csv` and `.parquet` are recognised as file suffixes, so a
schema-qualified `analytics.orders` is unaffected.[^clarifications]

**AD-6 — the `pg` suite is its own marker and its own verify step.** Mirrors `e2e`: `markers` in
`pyproject.toml`, a session fixture that `pytest.skip`s with a stated reason when no database is
reachable, and a separate `step` in `verify.sh` so both the cost and any skip are visible instead
of buried.[^pyproject] [^e2e-conftest] [^verify] The main pytest step becomes
`-m "not e2e and not pg"`.

**AD-7 — CI runs Postgres as a service container on the 3.13 matrix leg only.** The database is
the same for both legs; running it twice tests Docker, not SemantiQL. The DSN reaches pytest as a
plain env var set in the workflow, so on the 3.11 leg the suite skips through the same path a
laptop uses — which means the skip path itself is exercised on every CI run rather than only when
it breaks.[^ci]

**AD-8 — `close()` joins the `Adapter` Protocol. Added mid-implement; this is the change's
first real N4 finding.**

`cli.py` calls `adapter.close()` in a `finally`, and both concrete adapters define it — but
`base.Adapter` never declared it. Nothing caught that, because the CLI was typed against
`DuckDBAdapter` rather than against the Protocol. The moment `_open_adapter` returned an
`Adapter` (T4), mypy said:

```
src/semantiql/cli.py:93: error: "Adapter" has no attribute "close"  [attr-defined]
src/semantiql/cli.py:197: error: "Adapter" has no attribute "close"  [attr-defined]
```

So the seam was **incomplete and could not be known to be incomplete with one implementation**:
a third-party adapter written to the Protocol as published would satisfy mypy, satisfy
`isinstance`, and then crash the CLI on the way out. That is the exact class of defect this spec
was written to expose, arriving before the differential suite even ran.

The fix is to declare it — SemantiQL opens connections and must be able to release them, so
"closable" is part of what a datasource *is*, not a DuckDB detail. An adapter with nothing to
release implements it as a no-op.

**This contradicts the plan as written**, which listed `adapters/base.py` under *Files not
touched* and said that if the Protocol needed widening, that was "a finding about N4, not a diff
to slip in". It is being recorded as a finding **and** fixed, rather than either alone. Two
things make that the right call rather than the convenient one:

- **FR-9 is untouched.** Zero files change under `engine/`. N4's load-bearing claim — the engine
  does not learn about datasources — holds exactly as stated.
- **The seam definition is not the core.** `base.py` is the contract adapters satisfy, and this
  widens it to match what the codebase already required of every adapter. No behaviour changes
  for DuckDB.

The honest qualification, which belongs in the report rather than buried here: N4 is worded as
"one new adapter, **no core changes**", and this change is one new adapter *plus one line on the
Protocol*. The wording implies the seam is already complete. It was not. Whether that means N4
should say "one new adapter, and any gap it reveals in the seam" is a constitution question, and
this spec does not answer it — it is raised in the report.

# Repository Impact Map

## Files to add

- `src/semantiql/adapters/postgres.py` — the adapter. `PostgresAdapter` with `dialect`,
  `relation`, `columns`, `execute`, `close`; module-level `_KINDS: dict[str, ColumnKind]` keyed
  on psycopg type names; `_kind(oid)` classmethod handling the array and unknown cases.
- `tests/test_adapter_postgres.py` — Protocol conformance, `_kind` classification including the
  array and unknown cases, and the file-source refusal. No database needed.
- `tests/test_postgres_differential.py` — `pg`-marked. Loads the retail corpus into Postgres,
  runs each request through both adapters, asserts equal answers and the hand-computed totals;
  plus a doctor run producing the three finding kinds.
- `tests/postgres_fixtures.py` (or a `conftest.py` addition) — the session fixture that connects,
  creates the tables from the retail CSVs, and skips with a stated reason when unreachable.
- `examples/retail/semantic_model.postgres.yml` — the same semantic content with
  `dialect: postgres` and table sources, so the file-vs-table difference is demonstrated rather
  than described.

## Files to modify

- `pyproject.toml` — add `psycopg[binary]>=3.1` to `dependencies`; add `pg` to
  `[tool.pytest.ini_options] markers`; add `"postgres"` to `keywords`. **No mypy override**, and
  the plan asserts that: psycopg ships `py.typed` (probe-confirmed), unlike the `duckdb` entry
  directly above it.[^pyproject] [^psycopg-probe]
- `src/semantiql/cli.py` — add `--datasource {duckdb,postgres}` (default `duckdb`) and `--dsn`;
  add `_open_adapter(args) -> Adapter`; replace the two `DuckDBAdapter(...)` constructions in
  `_doctor` and `main` with calls to it; widen `_doctor`'s signature from `(model_path, database)`
  to take the parsed args or an already-open adapter.[^cli]
- `scripts/verify.sh` — the pytest step becomes `-m "not e2e and not pg"`; a new step runs
  `-m pg` with a comment explaining the skip-when-absent contract, mirroring the e2e step's
  comment.[^verify]
- `.github/workflows/ci.yml` — a `services.postgres` block on the verify job with inline
  credentials and a health check, plus the env var carrying the DSN, gated to the 3.13
  leg.[^ci]
- `examples/retail/semantic_model.yml` — correct the header comment that claims swapping
  `dialect` "changes nothing else in this file"; point at the Postgres sibling
  model.[^example-model]
- `README.md` — line 15's "Postgres … not built yet" list loses Postgres; the roadmap table at
  line 101 marks it shipped. **Trust-boundary artifact.**[^readme]
- `docs/05-datasources.md` — the roadmap table's MVP row records Postgres as shipped, kept in
  sync with the README as `CLAUDE.md` requires. **Trust-boundary artifact.**[^datasources-doc]
- `AGENTS.md` — "Not yet built" drops the Postgres adapter; the N4 section records that the claim
  is now exercised by a second engine rather than by imports alone. Canonical source; `CLAUDE.md`
  is a symlink to it (`ls -l` confirms) and needs **no separate edit** — the derived copy
  re-syncs itself.[^agents]
- `docs/07-code-map.md` — the module tree at lines 16-18 gains `adapters/postgres.py`; the
  "necessary but not sufficient" note at lines 71-76 keeps its three DuckDB-specific facts (they
  are unchanged and still true) and gains the fact that the transpile path is now exercised by a
  real second target rather than by one assertion. **Trust-boundary artifact.**[^code-map]

## Files not touched, but adjacent

- `src/semantiql/engine/run.py`, `compile.py`, `validate.py` — **zero changes**, which is FR-9.
  `run` already passes `adapter.dialect` through to `compile_request`, and `compile.py` already
  transpiles when the target differs from canonical.[^run] [^compile]
- `src/semantiql/doctor.py` — no change. `check(model, adapter)` is typed against the Protocol
  already.[^doctor]
- `src/semantiql/knowledge/model.py` — no change. `Datasource.dialect` is already
  `Literal["duckdb", "postgres"]`.[^model]
- ~~`src/semantiql/adapters/base.py` — no change.~~ **Amended mid-implement: it does change.**
  `close()` is added to the Protocol. See AD-8 for what forced it and why it is recorded as an
  N4 finding rather than treated as routine.[^base]
- `tests/conftest.py` — the existing `adapter` fixture stays DuckDB-only; the Postgres fixture is
  separate so a database outage cannot affect the unit run.[^conftest]
- `tests/e2e/` — untouched. Clarification Q5 keeps the differential suite off TPC-H.[^clarifications]
- `.github/workflows/publish.yml` — untouched.

# Open research questions

- **OQ-1 — does the canonical→Postgres transpile hold for every construct the compiler emits?**
  `DATE_TRUNC`, `CAST(… AS DATE)`, `LIMIT`/`OFFSET`, and the guarded-divisor metric expression all
  exist in Postgres, and sqlglot handles the dialect pair. Confidence is high but this is
  *unverified until the differential suite runs* — which is precisely what the suite is for. A
  failure here is a finding worth reporting, not a reason to patch `compile.py` quietly.
- **OQ-2 — resolved during the checkpoint-2 self-audit.** `docs/07-code-map.md` and `AGENTS.md`
  were originally listed from `CLAUDE.md`'s description rather than from the files. Both were then
  read, and the rows are footnoted to what they actually say — including that `CLAUDE.md` is a
  symlink, so it is not a second edit. Recorded rather than deleted because the near-miss is the
  point: an unfootnoted row is what this checkpoint exists to catch.
- **OQ-3 — Postgres major version for CI.** The plan proposes pinning a specific major in the
  service container rather than `postgres:latest`, so a CI failure is never caused by an upstream
  release nobody chose. The exact major is picked during implement from what Docker Hub actually
  serves — no repo evidence fixes it, and it is cheap to change.

[^constitution]: `.specify/memory/constitution.md` — N1–N5, the tech-stack secret-free CI rule, and the trust-boundary list.
[^clarifications]: `clarifications.md` — Q1 through Q8, all decided by the agent from repo evidence.
[^base]: `src/semantiql/adapters/base.py` — the Protocol, `ColumnKind`, and the `native_type` docstring.
[^duckdb-adapter]: `src/semantiql/adapters/duckdb.py` — `relation()`'s suffix branch, `_KINDS`, `_kind()`'s array and prefix comments, the `columns()` probe, and the read-only docstring.
[^cli]: `src/semantiql/cli.py` — `DuckDBAdapter` constructed at lines 64 and 139; `--database` parsed at line 106; exit codes documented at line 112.
[^run]: `src/semantiql/engine/run.py` — the dialect-mismatch refusal at line 38, `relation()` at line 49, and `dialect=adapter.dialect` at line 55.
[^compile]: `src/semantiql/engine/compile.py` — `CANONICAL_DIALECT = "duckdb"` at line 40 and the transpile at line 223.
[^doctor]: `src/semantiql/doctor.py` — `check(model, adapter)` at line 135, typed against `Adapter`.
[^model]: `src/semantiql/knowledge/model.py` — `Datasource.dialect` at line 118.
[^conftest]: `tests/conftest.py` — the session `model` and function `adapter` fixtures.
[^adapter-test]: `tests/test_adapter_duckdb.py` — the Protocol-conformance test and its stated `isinstance` limit.
[^doctor-test]: `tests/test_doctor.py` — the finding kinds a Postgres run reproduces.
[^e2e-conftest]: `tests/e2e/conftest.py` — the `pytest.skip` with a stated reason at line 102.
[^verify]: `scripts/verify.sh` — the pytest step and the separate e2e step with its skip comment.
[^ci]: `.github/workflows/ci.yml` — the no-secrets header comment, the 3.11/3.13 matrix, and the single verify step.
[^pyproject]: `pyproject.toml` — `dependencies`, the `duckdb` `ignore_missing_imports` override, and the `markers` block.
[^readme]: `README.md` — line 15's not-built-yet sentence and the roadmap table at line 101.
[^datasources-doc]: `docs/05-datasources.md` — the roadmap table's MVP row.
[^example-model]: `examples/retail/semantic_model.yml` — the header comment claiming a one-line engine swap.
[^code-map]: `docs/07-code-map.md` — the module tree at lines 16-18, the adapter-seam table at line 88, and the "necessary but not sufficient" note at lines 71-76 naming the three DuckDB-specific facts inside `engine/`.
[^agents]: `AGENTS.md` — the "Not yet built" list and the N4 section; `ls -l CLAUDE.md` shows it is a symlink to this file.
[^psycopg-probe]: Live probe of psycopg 3.3.4 run at plan time; the four registry lookups and the `py.typed` check are transcribed verbatim in AD-3.
