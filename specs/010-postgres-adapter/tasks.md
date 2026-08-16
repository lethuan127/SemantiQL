---
type: Tasks
title: Postgres adapter — tasks
description: 13 tasks in five phases plus the two gate tasks — dependency, adapter, CLI seam, tests, then the derived copies and the gate.
resource: specs/010-postgres-adapter/tasks.md
tags: [sdd, tasks, adapters, postgres]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T01:10:00+07:00' }
sources:
  - id: plan
    resource: plan.md
    title: The approved plan and impact map these tasks derive from
    last_modified: 2026-08-17
  - id: validation
    resource: validation.md
    title: AC-1..AC-13, walked by TV
    last_modified: 2026-08-17
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-17T01:12:00+07:00', checkpoint: 3,
      basis: '14 tasks in dependency order; 2 [P] groups checked file-by-file for overlap and found disjoint — group 2 names CLAUDE.md as the one near-overlap, excluded because it is a symlink to AGENTS.md; every task carries a checkable command or observation, and TV names AC-9 as the N4 verdict rather than a formality' }
status: stable
---

13 tasks plus the two gate tasks, derived from the impact map.[^plan] Two `[P]` groups, both checked for file
overlap — see the note under each. The gate tasks walk `validation.md`.[^validation]

# Phase 1 — dependency

## ✅ T1. Add psycopg to the manifest

- **Files:** `pyproject.toml`
- **Depends on:** —
- **Do:** add `psycopg[binary]>=3.1` to `dependencies`; add `"postgres"` to `keywords`; add
  `pg: tests that need a live Postgres` to `[tool.pytest.ini_options] markers`. Add **no** mypy
  override.
- **Verification:** `uv sync && uv run mypy` passes with no `psycopg` override in the file.
  `uv run python -c "import psycopg; print(psycopg.__version__)"` prints ≥ 3.1.
- **Constitution check:** an external dependency is never a T1 change; this is the T2 path, and
  the driver rationale is clarification Q1.

# Phase 2 — the adapter

## ✅ T2. Write `PostgresAdapter`

- **Files:** `src/semantiql/adapters/postgres.py` (new)
- **Depends on:** T1
- **Do:** `dialect` → `"postgres"`; `relation()` per AD-5 (raise `AdapterError` on a `.csv` or
  `.parquet` source, else `exp.to_table`); `columns()` per AD-4 (probe built through
  `relation()`); `execute()` wrapping `psycopg.Error` in `AdapterError`; `close()`. Connection
  opened with `read_only=True`. Module docstring states the N5 scope precisely, as
  `adapters/duckdb.py` does.
- **Verification:** `uv run mypy` clean; `uv run ruff check .` clean.
- **Constitution check:** N1 — no validation, no rewriting, `execute` takes already-validated SQL.
  N5 — `read_only` is set on the connection.

## ✅ T3. Write the type classifier

- **Files:** `src/semantiql/adapters/postgres.py`
- **Depends on:** T2
- **Do:** `_KINDS` keyed on psycopg's short type `name`; `_kind(oid)` resolving through
  `psycopg.postgres.types.get(oid)`, returning `other` for `None` **and for an array OID**,
  detected as `info.oid != oid` (AD-3). `Column.native_type` carries `info.regtype`. Comment the
  array branch with why, naming the spec-009 precedent — the next reader will want to simplify it
  away.
- **Verification:** covered by T6; `uv run mypy` clean.
- **Constitution check:** N2 — an unknown type answers `other` rather than guessing, so doctor
  stays silent instead of confidently wrong.

# Phase 3 — the CLI seam

## ✅ T4. Add adapter selection

- **Files:** `src/semantiql/cli.py`
- **Depends on:** T2
- **Do:** add `--datasource {duckdb,postgres}` (default `duckdb`) and `--dsn`; add
  `_open_adapter(args) -> Adapter`; replace both `DuckDBAdapter(...)` constructions with it; make
  a mismatched flag pair (`--dsn` with `--datasource duckdb`, or `--database` with
  `--datasource postgres`) an argument error rather than a silent ignore. Update `--database`'s
  help to say it is DuckDB-only.
- **Verification:** every existing test in `tests/test_cli.py` passes unmodified (AC-7).
- **Constitution check:** N1 — `_open_adapter` returns an adapter, it does not query; `run` stays
  the only path to data.

# Phase 4 — tests

## ✅ T5. `[P]` Postgres fixtures

- **Files:** `tests/conftest.py` (amended — see below), `examples/retail/semantic_model.postgres.yml` (new)
- **Amendment:** the fixtures went into `tests/conftest.py` rather than a new `tests/postgres_fixtures.py`. `tests/` is not a package, so a separate module could not be imported, and `pytest_plugins` in a non-root conftest is an error in pytest 8. The plan allowed either ("or a `conftest.py` addition"). Session-scoped and lazily evaluated, so the unit run is unaffected.
- **Depends on:** T2
- **Do:** a session fixture reading `SEMANTIQL_TEST_DSN`, connecting, creating the retail tables
  from the CSVs, and `pytest.skip`ing with a stated reason naming the missing database when it
  cannot connect. The sibling model carries the same semantic content with `dialect: postgres`
  and table sources.
- **Verification:** with no database, `uv run pytest -m pg` reports skips with the reason visible.

## ✅ T6. `[P]` Adapter unit tests

- **Files:** `tests/test_adapter_postgres.py` (new)
- **Depends on:** T3
- **Do:** Protocol conformance and no-inheritance (mirroring `tests/test_adapter_duckdb.py`,
  including its stated `isinstance` limit); `_kind` over every `_KINDS` entry; **an array OID
  classifying `other`**; an unknown OID classifying `other`; `relation()` raising on `.csv` and
  `.parquet` and not raising on `analytics.orders`. No database needed.
- **Verification:** `uv run pytest tests/test_adapter_postgres.py` green with no Postgres running.

> **`[P]` group 1 — T5 and T6 are disjoint.** T5 writes `tests/postgres_fixtures.py` and a new
> example YAML; T6 writes `tests/test_adapter_postgres.py`. No shared file, no shared state, and
> T6 needs no fixture because `_kind` and `relation` are pure.

## ✅ T7. Differential suite

- **Files:** `tests/test_postgres_differential.py` (new)
- **Depends on:** T4, T5, T6
- **Do:** `pg`-marked. For each request the retail suites answer, run it through both adapters via
  `engine.run.run` and assert equal columns and equal values, comparing numbers as decimals; plus
  assert the hand-computed totals. Add a doctor half reproducing the three finding kinds
  `tests/test_doctor.py` pins.
- **Verification:** with a database reachable, `uv run pytest -m pg` green (AC-3, AC-5).
- **Constitution check:** N2 — this task *is* the control. A dialect disagreement is the wrong
  number a user cannot see.

## ✅ T8. Wire the suite into the gate

- **Files:** `scripts/verify.sh`
- **Depends on:** T7
- **Do:** main pytest step becomes `-m "not e2e and not pg"`; add a `pg` step with a comment
  explaining the skip-when-absent contract, mirroring the e2e step's comment.
- **Verification:** `./scripts/verify.sh` passes with no Postgres running, and the `pg` step
  prints its skip reason (AC-11).

## ✅ T9. CI service container

- **Files:** `.github/workflows/ci.yml`
- **Depends on:** T8
- **Do:** a `services.postgres` block with inline credentials, a health check, and a pinned major
  (OQ-3 — pick from what Docker Hub serves); the DSN as a plain `env` value, gated to the 3.13
  matrix leg so the 3.11 leg exercises the skip path.
- **Verification:** `grep -c "secrets\." .github/workflows/ci.yml` returns 0 (AC-10).
- **Constitution check:** CI stays secret-free, so a fork PR runs to completion.

# Phase 5 — derived copies and the gate

## ✅ T10. `[P]` README and datasources doc

- **Files:** `README.md`, `docs/05-datasources.md`
- **Depends on:** T7
- **Do:** README line 15 drops Postgres from the not-built list; the roadmap table marks it
  shipped; `docs/05-datasources.md`'s MVP row matches. **Both are trust-boundary artifacts** and
  `AGENTS.md` requires them kept in sync.
- **Verification:** the two roadmap tables agree by eye (AC-12).

## ✅ T11. `[P]` Agent brief

- **Files:** `AGENTS.md`
- **Depends on:** T7
- **Do:** drop the Postgres adapter from "Not yet built"; record in the N4 section that the claim
  is now exercised by a second engine. **Do not edit `CLAUDE.md`** — it is a symlink to this file.
- **Verification:** `ls -l CLAUDE.md` still shows the symlink; `git status` shows one file changed,
  not two.

## ✅ T12. `[P]` Code map

- **Files:** `docs/07-code-map.md`
- **Depends on:** T7
- **Do:** the module tree gains `adapters/postgres.py`; the "necessary but not sufficient" note
  keeps its three DuckDB-specific facts and gains that the transpile path now has a real second
  target. **Trust-boundary artifact.**
- **Verification:** the three facts at lines 71-76 are still stated, not deleted.

## ✅ T13. `[P]` Example model comment

- **Files:** `examples/retail/semantic_model.yml`
- **Depends on:** T5
- **Do:** correct the header comment claiming a `dialect` swap "changes nothing else in this
  file"; point at the Postgres sibling.
- **Verification:** the comment matches what clarification Q6 established.

> **`[P]` group 2 — T10, T11, T12 and T13 touch four disjoint file sets:** {`README.md`,
> `docs/05-datasources.md`} · {`AGENTS.md`} · {`docs/07-code-map.md`} · {`examples/retail/semantic_model.yml`}.
> No file appears twice. `CLAUDE.md` is explicitly *not* in T11's set because editing the symlink
> and the target would be the same file twice — the one overlap worth naming.

## ✅ TF. Final verify

- **Files:** —
- **Depends on:** T1–T13
- **Do:** run `./scripts/verify.sh`, both with and without a Postgres reachable.
- **Verification:** green both ways. The `pg` step runs in one and skips with a reason in the
  other.

## ✅ TV. Validation pass

- **Files:** `specs/010-postgres-adapter/validation.md`
- **Depends on:** TF
- **Do:** walk AC-1 through AC-13 and record the outcome of each. **AC-9 is the N4 verdict** —
  `git diff --stat` must show zero files under `src/semantiql/engine/`. A non-zero count is a
  finding about N4 to escalate and report, never a diff to justify.
- **Verification:** every AC marked met, or explicitly recorded as not met with why.

[^plan]: `plan.md` — the Repository Impact Map, AD-1..AD-7, and OQ-1..OQ-3.
[^validation]: `validation.md` — AC-1 through AC-13 and the manual verification steps.
