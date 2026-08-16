---
type: Plan
title: An end-to-end suite over a large dataset — plan
description: A session fixture that generates TPC-H locally, a semantic model over a denormalised view, and cases checked against hand-written physical SQL.
resource: specs/008-e2e-suite/plan.md
tags: [sdd, plan, testing]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:53:52+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-15
  - id: conftest
    resource: ../tests/conftest.py
    title: The existing session model fixture and per-test adapter fixture the new suite parallels
    last_modified: 2026-08-15
  - id: e2e-tests
    resource: ../tests/test_example_end_to_end.py
    title: The ten-row suite this complements — hand-computed figures, kept as they are
    last_modified: 2026-08-16
  - id: adapter
    resource: ../src/semantiql/adapters/duckdb.py
    title: "DuckDBAdapter(database=...) opening a file read_only=True, and relation() treating a bare name as a table or view"
    last_modified: 2026-08-15
  - id: manifest
    resource: ../pyproject.toml
    title: "tool.pytest.ini_options with testpaths and addopts, where the marker is registered"
    last_modified: 2026-08-15
  - id: verify
    resource: ../scripts/verify.sh
    title: The pytest step the suite runs within, and the fail-fast step naming
    last_modified: 2026-08-15
  - id: contributing
    resource: ../CONTRIBUTING.md
    title: Where a contributor is told how to run the checks
    last_modified: 2026-08-15
  - id: probe
    resource: ../src/semantiql/adapters/duckdb.py
    title: "Probes at plan time: dbgen cost and cardinality at three scales, zero nulls in the corpus, and the read-only file adapter refusing CREATE"
    last_modified: 2026-08-16
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T23:53:52+07:00', checkpoint: 2,
      basis: 'map derived from 6 file reads plus dataset probes at three scale factors; all 4 existing-file rows footnoted; 5 files to add, each justified; 0 open questions' }
status: stable
---

# Constitution check

- **N1/N2** — the suite's whole purpose. Every case compares the engine's answer with SQL
  written independently, so a mistranslation fails rather than being pinned in place.[^constitution]
- **N5** — the file-backed adapter is opened `read_only=True`, and a probe confirms DuckDB
  itself then rejects `CREATE`. That is the half of N5 the in-memory CLI path cannot show, and
  nothing tests it today.[^probe][^adapter]
- **N3** — the end-to-end model is a YAML file like any other, read by the same loader. No
  model values are constructed in Python.[^constitution]
- **N4** — untouched; the suite runs the DuckDB adapter only.
- **Trust boundary** — `pyproject.toml` is the project manifest. The edit registers one marker
  and nothing else; called out in the report.[^manifest]

# Approach

**One session fixture builds everything.** `tests/e2e/conftest.py` creates a temporary DuckDB
*file*, calls `dbgen(sf=…)` with the scale from `SEMANTIQL_E2E_SF` (default `0.01`),
denormalises the eight TPC-H tables into a single `sales` view, and creates a small `edge`
table for what TPC-H lacks. It then closes its writable connection and hands the tests a
`DuckDBAdapter` opened on the same file — read-only, which is the path FR-7 exercises.[^adapter]

If `dbgen` is unavailable — the extension is fetched once from DuckDB's repository, so this is
the offline first run — the fixture skips the whole package with the reason.[^probe]

**The model is a committed YAML file**, `tests/e2e/semantic_model.yml`, pointing `source` at
the view. It is the largest model in the repo and doubles as a worked example: string, date and
number dimensions; all six aggregations; and two metrics. Because it is a real file read by the
real loader, it also tests that a model of that size loads.

**Each case is a pair.** `test_differential.py` parametrises `(semantic_sql, physical_sql)` and
asserts equal rows. The physical SQL is written by hand against `sales`, so it is an
independent statement of the question rather than a transcript of the engine's output (Q2).
A handful of totals are additionally pinned, because a differential test passes if *both*
sides are wrong in the same way — pinning catches a corpus that silently changed.

**Selection.** Registering an `e2e` marker in the manifest lets a contributor run `-m "not
e2e"` while iterating and raise `SEMANTIQL_E2E_SF` for a soak run. The default run includes
them: at sf=0.01 the cost is a fraction of a second, and an opt-in suite rots (Q3).[^manifest]

# Architecture decisions

1. **TPC-H via `dbgen`, generated per session** — Q1. No committed data, no credentials, a
   scale knob.
2. **Differential oracle over pinned figures** — Q2, with a few pins as a corpus tripwire.
3. **A companion `edge` table** for nulls, a boolean dimension and a zero divisor — Q5, since
   the probe proved TPC-H has none of them.
4. **A separate `tests/e2e/` package with its own conftest**, so the unit fixtures stay
   untouched and the expensive fixture is never built for a unit run.[^conftest]
5. **Skip, never fail, when the corpus cannot be built** — Q4.

# Repository Impact Map

**Files to modify**

- `pyproject.toml` — register the `e2e` marker under `tool.pytest.ini_options`. `testpaths`
  already covers `tests`, so the new package is collected without further change.[^manifest]
- `scripts/verify.sh` — the pytest step gains a second invocation so the suite's cost and any
  skip reason are visible as their own line rather than buried.[^verify]
- `CONTRIBUTING.md` — how to run the suite, how to scale it, and what a skip means.[^contributing]
- `AGENTS.md` — the same, in the checks section.

**Files to add**

- `tests/e2e/__init__.py` — package marker.
- `tests/e2e/conftest.py` — the session fixture: generate, denormalise, build the edge table,
  hand back a read-only adapter; skip if `dbgen` is unavailable.
- `tests/e2e/semantic_model.yml` — the model over `sales` and `edge`.
- `tests/e2e/test_differential.py` — the semantic-versus-physical pairs, covering every
  supported construct and one case combining all of them.
- `tests/e2e/test_edge_semantics.py` — nulls, boolean dimension, zero divisor, and the
  read-only guarantee.

**Files not touched, but adjacent**

- `tests/conftest.py`: unchanged, and the unit run must stay exactly as fast.[^conftest]
- `tests/test_example_end_to_end.py`: kept as it is — hand-computed figures on ten rows are a
  different and still-valuable kind of evidence.[^e2e-tests]
- `src/` — no production code changes. If the suite finds a bug, that is a separate spec.
- `.github/workflows/ci.yml` — no change needed: it runs `verify.sh`, which now includes the
  suite, and CI has the network the first generation needs.

# Open research questions

None. The dataset question was answered with measurements, and the null/boolean gap was
measured rather than assumed.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N3, N5 and the trust-boundary section naming the project manifest.
[^conftest]: `tests/conftest.py` — the session-scoped `model` fixture and function-scoped `adapter` fixture.
[^e2e-tests]: `tests/test_example_end_to_end.py` — the ten-row corpus with hand-computed figures.
[^adapter]: `src/semantiql/adapters/duckdb.py` — `DuckDBAdapter.__init__` opens a non-memory database with `read_only=True`; `relation()` passes a bare name through as a table or view.
[^manifest]: `pyproject.toml` — `[tool.pytest.ini_options]`, `testpaths = ["tests"]`, `addopts = "-q"`.
[^verify]: `scripts/verify.sh` — `step "tests (pytest)"` then `uv run pytest || fail "pytest"`.
[^contributing]: `CONTRIBUTING.md` — the setup and checks section.
[^probe]: Probes at plan time: `dbgen` at sf=0.01/0.1/1 → 60,175/600,572/6,001,215 rows in 0.18s/1.29s/9.47s, DB file 4.5/27.5/264 MB; the denormalised view has 5 segments, 25 nations, 5 regions, 7 ship modes, 1,000 customers, dates 1992-01-01..1998-08-02, and zero nulls; `DuckDBAdapter(path)` reads it and rejects `CREATE TABLE` with "Cannot execute statement of type CREATE".
