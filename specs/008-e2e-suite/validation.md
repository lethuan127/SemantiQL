---
type: Validation
title: An end-to-end suite over a large dataset — validation
description: Acceptance criteria traced to FR-1..FR-8, walked after implementation.
resource: specs/008-e2e-suite/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:53:52+07:00' }
status: stable
---

# Acceptance criteria

- [x] **AC-1** (FR-1): the corpus is generated locally, deterministically, at a chosen scale.
  - **Proven by:** `tests/e2e/conftest.py` calls `dbgen(sf=…)` from `SEMANTIQL_E2E_SF`; no data
    file is committed; the suite was run at sf=0.01 (60,175 rows) and sf=0.1 (600,572 rows).
- [x] **AC-2** (FR-2): each case is checked against independently written physical SQL.
  - **Proven by:** the 17 pairs in `test_differential.py`, compared row for row.
- [x] **AC-3** (FR-3): every supported construct is covered, including one case combining them.
  - **Proven by:** cases for all six aggregations, metrics, grouping, six filter forms, three
    grains, ordering, limit and offset, plus the combined case.
- [x] **AC-4** (FR-4): the suite is separately selectable and the unit tests are untouched.
  - **Proven by:** the `e2e` marker; `pytest -m "not e2e"` reports 194 passed, 27 deselected in
    0.41s — the same 194 tests as before this change.
- [x] **AC-5** (FR-5): the suite skips, with a reason, when the corpus cannot be built.
  - **Proven by:** the fixture catches `duckdb.Error` and calls `pytest.skip`; verified by
    reproducing the failure with autoload disabled, which raises the Catalog Error the fixture
    handles.
- [x] **AC-6** (FR-6): nulls, a boolean dimension, and a zero divisor are covered.
  - **Proven by:** `test_edge_semantics.py` — `count` 6 vs `count(label)` 5 vs
    `count_distinct` 2; `<> 'busy'` returning 2 of 6; a boolean filter; and a metric returning
    `None` for the group whose divisor is missing while still dividing where it is not.
- [x] **AC-7** (FR-7): the file-backed read-only path is exercised.
  - **Proven by:** `test_the_file_backed_connection_is_read_only`, where DuckDB rejects a
    `CREATE` before validation would have — the half of N5 the in-memory CLI cannot show.
- [x] **AC-8** (FR-8): running and scaling the suite is documented.
  - **Proven by:** `CONTRIBUTING.md` ("The two test suites") and `AGENTS.md`.

# Non-functional acceptance

- [x] The verify gate is green, with the two suites as separate, visible steps.
- [x] **N1/N2** — a disagreement with hand-written SQL fails the build.
- [x] **N5** — AC-7.
- [x] The unit suite did not get slower: 0.41s for 194 tests, and the large suite adds 0.48s at
  the default scale.

# Manual verification

1. `uv run pytest -m "not e2e"` — 194 passed, unchanged.
2. `SEMANTIQL_E2E_SF=0.1 uv run pytest -m e2e` — 27 passed against 600,572 rows, proving the
   cases are scale-independent rather than pinned to one corpus.
3. `./scripts/verify.sh` — both steps listed separately.
