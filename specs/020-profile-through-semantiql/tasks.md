---
type: Tasks
title: Profile a relation through SemantiQL, not through psql — tasks
description: 9 tasks, 2 parallel — the seam first so mypy names the doubles, the prohibition last so it is tested.
resource: specs/020-profile-through-semantiql/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T14:27:33+00:00' }
sources:
  - id: plan
    resource: /020-profile-through-semantiql/plan.md
    title: The approved plan these tasks derive from
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T14:27:33+00:00', checkpoint: 3,
      basis: 'Seam first, because mypy then enumerates every implementation and double rather than leaving that list to be assembled by hand — the pattern that worked for tables() in 016. The skill prohibition is last and carries its own test, because spec 016 established that an exclusion living only in prose is not an exclusion.' }
---

Derived from the approved plan.[^plan]

# Phase 1 — The seam

- [x] **T1.** `ColumnProfile`, `RelationProfile`, and `profile(source)` on the Protocol.
  - **Files:** `src/semantiql/adapters/base.py`
  - **Depends on:** —
  - **Verification:** `uv run mypy` fails, naming every type that no longer satisfies the Protocol.
    That list is the input to T2–T4.
  - **Constitution check:** N4 — the widening is in `base.py`; `engine/` is untouched.

- [x] **T2. [P]** Implement on DuckDB: one wide aggregate query from `relation()`, plus a grouped
      query per low-cardinality column.
  - **Files:** `src/semantiql/adapters/duckdb.py`
  - **Depends on:** T1
  - **Verification:** row count, nulls, distinct, min/max/sum, and the distribution, against a fixture
    with known values.
  - **Constitution check:** N5 — `SELECT` only.

- [x] **T3. [P]** Implement on Postgres, with `FILTER (WHERE …)`, numeric casts for exact sums, and a
      **rollback after fetching**.
  - **Files:** `src/semantiql/adapters/postgres.py`
  - **Depends on:** T1
  - **Verification:** marked `pg`; a test asserts the connection is left `idle`, not
    `idle in transaction`.
  - **Constitution check:** N5 — the rollback is what stops a snapshot being pinned.

- [x] **T4.** Update the test doubles mypy named.
  - **Files:** the doubles under `tests/`
  - **Depends on:** T1
  - **Verification:** `uv run mypy` clean.
  - **Constitution check:** — .

# Phase 2 — The verb

- [x] **T5.** `semantiql profile --table X`, `--json`, no model required, `--table` mandatory.
  - **Files:** `src/semantiql/cli.py`
  - **Depends on:** T2, T3
  - **Verification:** run it against the 2.96M-row NYC table and against the retail CSV; the sums must
    match `examiner/ANSWERS.md`, which was computed independently.
  - **Constitution check:** N1 — profiling authors no caller SQL, so it does not route through `run`;
    stated because "a new way to reach the database" is otherwise exactly the shortcut refused
    elsewhere.

- [x] **T6.** CLI tests: both shapes, `--json`, needs-no-model, `--table` required, unreachable
      datasource.
  - **Files:** `tests/interfaces/test_cli.py`
  - **Depends on:** T5
  - **Verification:** `uv run pytest tests/interfaces/test_cli.py -q`
  - **Constitution check:** — .

# Phase 3 — The prohibition, which is the actual fix

- [x] **T7.** Teach `profile` in the discovery loop, **forbid raw SQL against the database**, and make
      DDL something the skill prints for the human to run.
  - **Files:** `plugin/skills/semantiql/SKILL.md`
  - **Depends on:** T5
  - **Verification:** the loop's step for pricing a judgement question names `profile`; the limits
    section forbids `psql` and any other client.
  - **Constitution check:** **trust boundary**, and N5 — this is where the write path closes. The
    observed run executed `CREATE OR REPLACE VIEW` through `psql`.

- [x] **T8.** Test the prohibition: the skill names no SQL client as a route to data.
  - **Files:** `tests/interfaces/test_plugin.py`
  - **Depends on:** T7
  - **Verification:** `uv run pytest tests/interfaces/test_plugin.py -q`
  - **Constitution check:** spec 016's lesson — an exclusion with no test is a suggestion.

- [x] **T9.** Record the reversal in spec 016's own artifacts: profiling was excluded there and is
      in scope here, with the reason.
  - **Files:** `specs/016-schema-discovery/spec.md`
  - **Depends on:** T7
  - **Verification:** the Out of scope entry points forward to 020 rather than contradicting it.
  - **Constitution check:** never leave a shipped artifact asserting something the tree no longer does.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh` with Postgres up and down.
- [x] **TV. Validation pass** — walk `validation.md`, and re-run a real discovery run under
      `run-debug.sh`, checking the transcript for `psql`. That is the only check that proves the
      prohibition works on the thing it is aimed at.

[^plan]: The impact map approved at gate 2.
