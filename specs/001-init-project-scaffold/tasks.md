---
type: Tasks
title: Initialize the SemantiQL repo — tasks
description: 16 tasks in five phases, scaffold before wiring, with one blocked on the missing conduct address.
resource: specs/001-init-project-scaffold/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-15T01:30:58+07:00' }
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-15T01:30:58+07:00', checkpoint: 3,
      basis: '16 tasks in dependency order; 3 [P] groups checked for file overlap and disjoint; every task carries a checkable verification' }
sources:
  - id: plan
    resource: /001-init-project-scaffold/plan.md
    title: The impact map these tasks derive from, attested at checkpoint 2
    last_modified: 2026-08-15
status: stable
---

Derived from the checkpoint-2 impact map.[^plan]

`[P]` marks tasks touching disjoint files with no shared mutable state. Checked: the three `[P]` groups below
share no file, and none of them touches `pyproject.toml`.

# Phase 1 — Scaffold

- [x] **T1.** Write `pyproject.toml` — hatchling backend, `requires-python = ">=3.11"`, `license = "MIT"`,
      runtime deps (sqlglot, duckdb, pydantic, pyyaml), dev deps (pytest, ruff, mypy), the `semantiql`
      console script, and ruff/mypy/pytest config.
  - **Files:** `pyproject.toml`
  - **Depends on:** —
  - **Verification:** `uv sync` resolves and writes `uv.lock`.
  - **Constitution check:** trust-boundary artifact from creation; SPDX id must match `LICENSE`.
- [x] **T2.** `uv sync`, committing `uv.lock`.
  - **Files:** `uv.lock`
  - **Depends on:** T1
  - **Verification:** `uv run python -c "import sqlglot, duckdb, pydantic"` succeeds.

# Phase 2 — Source, one module per layer

- [x] **T3.** Semantic Knowledge — pydantic models and the single YAML reader.
  - **Files:** `src/semantiql/__init__.py`, `src/semantiql/knowledge/__init__.py`,
    `src/semantiql/knowledge/model.py`, `src/semantiql/knowledge/loader.py`
  - **Depends on:** T2
  - **Verification:** `uv run pytest tests/test_loader.py`
  - **Constitution check:** N3 — the loader is the only YAML reader; no model values in Python.
- [x] **T4.** The adapter seam and the DuckDB adapter.
  - **Files:** `src/semantiql/adapters/__init__.py`, `src/semantiql/adapters/base.py`,
    `src/semantiql/adapters/duckdb.py`
  - **Depends on:** T2
  - **Verification:** `uv run pytest tests/test_adapter_duckdb.py`
  - **Constitution check:** N4 — `base.py` is a Protocol; N5 — connection opened read-only.
- [x] **T5. [P]** Validation — resolve every identifier against the model, refuse otherwise.
  - **Files:** `src/semantiql/engine/__init__.py`, `src/semantiql/engine/validate.py`
  - **Depends on:** T3
  - **Verification:** `uv run pytest tests/test_validation_refuses.py`
  - **Constitution check:** N1, N2 — an unresolvable request returns a refusal, never a guess.
- [x] **T6. [P]** Compile — semantic SQL → physical SQL, transpiled with sqlglot.
  - **Files:** `src/semantiql/engine/compile.py`
  - **Depends on:** T3
  - **Verification:** `uv run pytest tests/test_compile.py`
  - **Constitution check:** N4 — canonical dialect then transpile; no adapter import.
- [x] **T7.** The chokepoint — `run()` calls validate before compile before execute.
  - **Files:** `src/semantiql/engine/run.py`
  - **Depends on:** T5, T6, T4
  - **Verification:** `uv run pytest tests/test_example_end_to_end.py`
  - **Constitution check:** N1 — no path reaches an adapter without passing validation.
- [x] **T8.** CLI entry point.
  - **Files:** `src/semantiql/cli.py`
  - **Depends on:** T7
  - **Verification:** `uv run semantiql --help`, then a real query against the example.

# Phase 3 — Example and tests

- [x] **T9.** The example model and its fixture.
  - **Files:** `examples/retail/semantic_model.yml`, `examples/retail/orders.csv`
  - **Depends on:** T3
  - **Verification:** the CSV parses; every model column exists in it.
  - **Constitution check:** N3 — the model is YAML on disk; N5 — read-only CSV.
- [x] **T10.** The five test modules.
  - **Files:** `tests/test_loader.py`, `tests/test_compile.py`, `tests/test_adapter_duckdb.py`,
    `tests/test_example_end_to_end.py`, `tests/test_validation_refuses.py`
  - **Depends on:** T7, T9
  - **Verification:** `uv run pytest` — all pass; the end-to-end value matches a hand-computed figure.

# Phase 4 — Gate, CI, community health

- [x] **T11.** The verify gate.
  - **Files:** `scripts/verify.sh`
  - **Depends on:** T10
  - **Verification:** exits 0 clean; exits non-zero naming the step when a check is broken.
- [x] **T12. [P]** CI calling that script, secret-free.
  - **Files:** `.github/workflows/ci.yml`
  - **Depends on:** T11
  - **Verification:** the workflow invokes `scripts/verify.sh`; `permissions: contents: read`; no `secrets.`
        reference anywhere in the file.
  - **Constitution check:** FR-6 — must complete on a fork PR.
- [x] **T13. [P]** Issue forms, PR template, `SECURITY.md`, `CONTRIBUTING.md`.
  - **Files:** `.github/ISSUE_TEMPLATE/bug.yml`, `.github/ISSUE_TEMPLATE/feature.yml`,
    `.github/PULL_REQUEST_TEMPLATE.md`, `SECURITY.md`, `CONTRIBUTING.md`
  - **Depends on:** T11
  - **Verification:** every command `CONTRIBUTING.md` lists runs from a clean clone; `SECURITY.md` states the
        5-business-day window and names no email.
- [x] **T14.** `CODE_OF_CONDUCT.md` — Contributor Covenant verbatim.
  - **Files:** `CODE_OF_CONDUCT.md`
  - **Depends on:** the maintainer supplying a personal reporting address
  - **Verification:** diff against upstream Covenant shows only the contact line differs.
  - **Unblocked 2026-08-15:** the maintainer supplied `levanthuan127@gmail.com`. Contributor Covenant 2.1 taken
    from the upstream source; `diff` against it shows exactly one changed line, the contact.

# Phase 5 — Docs and reconciliation

- [x] **T15. [P]** New docs, and the index row for each.
  - **Files:** `docs/07-code-map.md`, `docs/08-positioning.md`, `docs/README.md`
  - **Depends on:** T8
  - **Verification:** every path `07` names exists in the tree; every comparative claim in `08` is sourced or
        marked as intent.
- [x] **T16.** Correct the stale published commands, and `.gitignore`.
  - **Files:** `README.md`, `docs/03-setup-workflow.md`, `.gitignore`
  - **Depends on:** T8, T11
  - **Verification:** `grep -rn "npx semantiql" README.md docs/` returns nothing; every command shown runs.
  - **Constitution check:** `docs/03` is trust-boundary — summarise the diff in the report.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh`, output verbatim, plus the OKF bundle validator.
- [x] **TV. Validation pass** — walk `validation.md`, ticking each AC and naming what proves it.

[^plan]: The Repository Impact Map attested at checkpoint 2 — 4 files to modify, 27 to add.
