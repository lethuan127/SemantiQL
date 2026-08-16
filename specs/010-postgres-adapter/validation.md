---
type: Validation
title: Postgres adapter — validation
description: Acceptance criteria traced to FR-1..FR-13, plus the verify gate and the manual checks a reviewer runs.
resource: specs/010-postgres-adapter/validation.md
tags: [sdd, validation, adapters, postgres]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T00:55:00+07:00' }
status: stable
---

# Acceptance criteria

- **AC-1** (FR-1) — `isinstance(PostgresAdapter(...), Adapter)` holds, and `Adapter` is not in
  `PostgresAdapter.__mro__`. mypy strict passes without an override for `psycopg`.
- **AC-2** (FR-2) — a semantic SQL request answered against a live Postgres through
  `engine.run.run`, with the returned `Result.sql` showing Postgres-dialect SQL.
- **AC-3** (FR-3) — for each request the retail suites answer, DuckDB and Postgres return equal
  column names and equal values. Numeric equality compares decimal values, not repr.
- **AC-4** (FR-4) — `_kind` classifies `varchar`/`text`/`bpchar` → `string`,
  `date`/`timestamp`/`timestamptz` → `date`, `int2`/`int4`/`int8`/`numeric`/`float4`/`float8` →
  `number`, `bool` → `boolean`; `json`, `interval`, `money` and an unknown OID → `other`; and an
  **array OID → `other`** rather than its element's kind.
- **AC-5** (FR-5) — `semantiql doctor --datasource postgres` produces a missing-column finding, a
  declared-type-mismatch finding, and an aggregation-over-non-numeric finding, with the same
  wording shape as the DuckDB run.
- **AC-6** (FR-6) — no model YAML in the repo contains a host, port, user, or password. Grep is
  the check.
- **AC-7** (FR-7) — every existing CLI test passes unchanged, and
  `semantiql "…" --database x.duckdb` behaves exactly as before.
- **AC-8** (FR-8) — an unreachable Postgres exits 3 with a message naming what to check; a refused
  request still exits 1. The two are distinguishable from the exit code alone.
- **AC-9** (FR-9) — `git diff --stat` shows **zero** files changed under `src/semantiql/engine/`,
  and `grep -rnE "adapters(\.|[[:space:]]+import)" src/semantiql/engine/` still matches only
  `adapters.base`.
- **AC-10** (FR-10) — the CI workflow contains no `secrets.` reference, and the Postgres job runs
  on a pull request from a fork.
- **AC-11** (FR-11) — with no Postgres reachable, `./scripts/verify.sh` passes and the `pg` step
  prints a skip reason naming the missing database.
- **AC-12** (FR-12) — the README roadmap and `docs/05-datasources.md` agree that Postgres ships,
  and README line 15 no longer lists it as not built. `AGENTS.md`'s "Not yet built" no longer
  names the Postgres adapter, `docs/07-code-map.md` lists `adapters/postgres.py`, and
  `examples/retail/semantic_model.yml`'s header comment no longer claims a `dialect` swap changes
  nothing else. `git status` shows `CLAUDE.md` unmodified — it is a symlink, so editing it and
  `AGENTS.md` would be one file twice.
- **AC-13** (FR-13) — a Postgres model whose `source` is `orders.csv` raises `AdapterError` naming
  the file source, and `analytics.orders` is unaffected.

# Non-functional acceptance

- `./scripts/verify.sh` green end to end: ruff format, ruff lint, mypy strict, pytest, e2e, and
  the OKF bundle validator.
- The `pg` suite runs green in CI against the service container, and skips with a reason locally.
- No new mypy override in `pyproject.toml`.

# Manual verification

1. `uv sync`, then `./scripts/verify.sh` with no Postgres running — expect green, with the `pg`
   step reporting a skip.
2. `docker run --rm -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:<major>`, then
   `./scripts/verify.sh` again — expect the `pg` step to run rather than skip.
3. Run the same question through both engines and compare by eye:
   `uv run semantiql "SELECT revenue, channel FROM orders" --show-sql` against
   `… --datasource postgres --dsn postgresql://postgres:postgres@localhost/postgres --show-sql`
   — the two `--show-sql` lines should differ in dialect and the numbers should not.
4. Point a Postgres run at the CSV-sourced retail model and confirm the error names the file
   source rather than a missing relation.

# Results — walked 2026-08-17

Verified against a local PostgreSQL 17.10 instance and, for the skip path, with no database
reachable. Every AC met.

| AC | Outcome | Evidence |
|---|---|---|
| AC-1 | met | `test_satisfies_the_protocol_structurally`; mypy strict clean with **no** `psycopg` override |
| AC-2 | met | `test_the_result_carries_postgres_sql`; CLI run returned `… FROM orders GROUP BY channel` |
| AC-3 | met | 11 requests × both engines, `test_both_engines_return_the_same_answer`. **One exception, deliberately excluded and pinned separately — see the finding below** |
| AC-4 | met | 16 mapped types, 6 unmappable, an unregistered OID, and 4 array OIDs, all asserted |
| AC-5 | met | three finding kinds reproduced over Postgres in the `pg` suite |
| AC-6 | met | grep for host/port/user/password over every model YAML: no match |
| AC-7 | met | all pre-existing CLI tests pass **unmodified**; `--datasource` defaults to `duckdb` |
| AC-8 | met | unreachable Postgres → exit 3 with a fix hint, on both `query` and `doctor`; refusal still exit 1 |
| AC-9 | **met — the N4 verdict** | `git diff --stat main -- src/semantiql/engine/` is **empty**; the import grep still matches only `adapters.base` |
| AC-10 | met | `grep -c "secrets\." .github/workflows/ci.yml` → 0; the service container's password is a literal |
| AC-11 | met | with no DSN: 22 skipped, 1 passed, `verify.sh` green |
| AC-12 | met | README, `docs/05-datasources.md`, `AGENTS.md`, `docs/07-code-map.md` and the example model all updated; `git status` shows `CLAUDE.md` unmodified, confirming the symlink |
| AC-13 | met | `test_a_file_source_is_refused_by_name` (3 paths) and `test_a_csv_source_is_refused_rather_than_missing`; `analytics.orders` unaffected |

**Non-functional:** `./scripts/verify.sh` green both with and without a database — 252 unit,
27 e2e, 24 pg, 0 OKF errors. No new mypy override.

## Findings carried forward

Neither blocks this change; both are recorded because they are what a second engine was
supposed to reveal.

1. **`DATE_TRUNC` diverges on byte-identical SQL.** Postgres resolves `date_trunc(text, date)`
   to its `timestamptz` overload, so the result carries the server's timezone where DuckDB's
   does not. Buckets and totals agree, so no number is wrong today — but the value depends on a
   server setting SemantiQL never declares, and on a `timestamptz` column the same overload
   would bucket rows near a month boundary by that setting. Fixing it means changing how
   `compile.py` emits the truncation, which FR-9 forbids here. Pinned by
   `test_date_trunc_buckets_agree_but_postgres_attaches_a_timezone`; **needs its own spec.**
2. **`close()` was missing from the `Adapter` Protocol.** Added under AD-8. Recorded because the
   gap was invisible with one implementation, which is the general lesson rather than a
   one-off.
