---
type: Tasks
title: An end-to-end suite over a large dataset — tasks
description: 6 tasks. Written after implementation as a record, so no checkpoint-3 attestation.
resource: specs/008-e2e-suite/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:53:52+07:00' }
sources:
  - id: plan
    resource: /008-e2e-suite/plan.md
    title: The approach and impact map these tasks derive from
status: stable
---

> **Written after the work, not before it.** The run went from the plan straight into
> implementation, so checkpoint 3 never fired and this file carries no `verified` entry. It is
> a record of what was done, which is worth having, but it is weaker evidence than a task list
> that shaped the work — a later reader should treat the plan's impact map as the artifact the
> implementation was actually held to.[^plan]

- [x] **T1.** `tests/e2e/conftest.py` — session fixture: generate TPC-H at
  `SEMANTIQL_E2E_SF` (default 0.01) into a temporary DuckDB file, denormalise to `sales`,
  build the `edge` table, close the writable connection, hand back a read-only adapter and a
  separate oracle connection. Skip the package if `dbgen` is unavailable.
- [x] **T2.** `tests/e2e/semantic_model.yml` — 6 dimensions, 8 measures, 3 metrics over
  `sales`; 2 dimensions, 5 measures, 1 metric over `edge`.
- [x] **T3.** `tests/e2e/test_differential.py` — 17 semantic/physical pairs covering every
  supported construct, one combining all of them, a corpus-shape tripwire, and a limit that
  demonstrably bounds a large result.
- [x] **T4.** `tests/e2e/test_edge_semantics.py` — null counting, a negated filter dropping
  nulls, a boolean dimension, a metric with and without a divisor, the read-only connection
  refusing a write, and `Adapter.columns`.
- [x] **T5.** `pyproject.toml` marker registration; `scripts/verify.sh` runs the two suites as
  separate steps.
- [x] **T6.** `CONTRIBUTING.md` and `AGENTS.md` — what the two suites are, how to scale or skip
  the large one, and why a skip is not a failure.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh`, output in the run report.
- [x] **TV. Validation pass** — `validation.md`, walked below.

[^plan]: The impact map recorded at checkpoint 2.
