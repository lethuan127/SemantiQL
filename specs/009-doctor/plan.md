---
type: Plan
title: semantiql doctor — plan
description: A checker module beside the engine, a richer adapter introspection call, and a CLI verb that renders findings and sets an exit code.
resource: specs/009-doctor/plan.md
tags: [sdd, plan, cli, adapters]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T00:04:41+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-15
  - id: base
    resource: ../src/semantiql/adapters/base.py
    title: The Adapter Protocol, and columns() taking a relation string it interpolates
    last_modified: 2026-08-15
  - id: duckdb-adapter
    resource: ../src/semantiql/adapters/duckdb.py
    title: relation() building a reader call or a table name, columns() running SELECT * LIMIT 0, and the read_only file connection
    last_modified: 2026-08-15
  - id: cli
    resource: ../src/semantiql/cli.py
    title: The NOT_YET_IMPLEMENTED verbs, the exit-code scheme, and the thin parse-run-print shape
    last_modified: 2026-08-15
  - id: model
    resource: ../src/semantiql/knowledge/model.py
    title: Dimension.type, Measure.agg, Table.dimensions/measures/metrics, and entity_names for suggestions
    last_modified: 2026-08-17
  - id: validate
    resource: ../src/semantiql/engine/validate.py
    title: _suggest, the case-insensitive close-match helper doctor reuses in spirit
    last_modified: 2026-08-17
  - id: e2e
    resource: ../tests/e2e/test_edge_semantics.py
    title: The only current caller of columns(), which this change updates
    last_modified: 2026-08-17
  - id: adapter-tests
    resource: ../tests/test_adapter_duckdb.py
    title: The adapter's own tests, which pin columns() behaviour
    last_modified: 2026-08-15
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-17T00:04:41+07:00', checkpoint: 2,
      basis: 'map derived from 7 file reads; all 7 existing-file rows footnoted; the Protocol change is scoped to one method with both call sites identified; 0 open questions' }
status: stable
---

# Constitution check

- **N4** — the seam changes, so this is the invariant to be careful with. The change keeps the
  rule it protects: type vocabulary stays *inside* the adapter, which returns the model's four
  kinds alongside its own native name, so adding Postgres still means one module and no shared
  edits.[^base][^constitution]
- **N5** — doctor only reads, and `--database` routes through the existing read-only file
  connection.[^duckdb-adapter]
- **N3** — doctor reports and suggests; it never writes the model.[^constitution]
- **N1** — untouched: doctor does not run user queries, so it is not a second path to the data.
  It reads schema metadata only.
- **Trust boundary** — `adapters/base.py` is the seam a future adapter resolves against, and
  `docs/NN-*.md` changes for FR-9. Both called out in the report.[^constitution]

# Approach

**`Adapter.columns(source)` returns `list[Column]`.** Today it takes a relation *string* and
interpolates it into `SELECT * FROM {relation} LIMIT 0` — the pattern `relation()` exists to
avoid, and one that cannot describe a CSV source without the caller rebuilding
`read_csv_auto('…')` itself.[^base][^duckdb-adapter] It becomes: take the model's `source`,
build the probe through `self.relation(source)` as an expression, and return
`Column(name, native_type, kind)` where `kind` is one of `string | date | number | boolean |
other` — the model's own vocabulary, mapped by the adapter that knows its engine's type names
(Q2). `other` means "cannot tell", and doctor treats it as silence rather than as a mismatch.

**`src/semantiql/doctor.py`** holds the checks, not `engine/`. Doctor is not part of the query
path and must not become a second way to reach data; keeping it out of `engine/` keeps that
obvious. It exposes `check(model, adapter) -> list[Finding]`, where a `Finding` carries a
level, the table it concerns, a sentence, and an optional suggestion — a shape the CLI can
render and a test can assert without parsing prose.

The checks, in the order a reader wants them: dialect agreement; then per table, whether the
source reads at all (if not, nothing below it is checkable and doctor says so rather than
emitting a cascade); then each dimension and measure's column existence, matched
case-insensitively because DuckDB resolves identifiers that way; then declared `type` against
the physical kind; then `sum`/`avg` over a non-number.

**CLI.** `doctor` leaves `NOT_YET_IMPLEMENTED` and becomes a verb; `--database` is added for
both verbs.[^cli] Exit codes follow the existing scheme, with `1` meaning "problems found" — the
same shape as a refusal: the command worked, the answer is that something is wrong.

# Architecture decisions

1. **`columns()` takes a source and returns typed columns** — Q1, Q2.
2. **A `doctor` module outside `engine/`**, so the query chokepoint stays the only thing in the
   engine that touches data.
3. **Findings as data, rendered by the CLI.** Tests assert on structure; only the CLI decides
   what a ✓ looks like.
4. **A failed source read stops that table's checks**, because twelve "column not found"
   findings under a missing table teach nothing.
5. **`other` kind is silence, not a mismatch** — an adapter that cannot classify a type must
   not manufacture a false problem.

# Repository Impact Map

**Files to modify**

- `src/semantiql/adapters/base.py` — add the `Column` dataclass and `ColumnKind`; change
  `columns` to `columns(source: str) -> list[Column]` with the contract in its docstring.[^base]
- `src/semantiql/adapters/duckdb.py` — build the probe from `relation()`, read
  `cursor.description` plus DuckDB's type names, and classify them into the model's four
  kinds.[^duckdb-adapter]
- `src/semantiql/cli.py` — a `doctor` verb, `--database`, findings rendering, exit codes.[^cli]
- `tests/test_adapter_duckdb.py` — update to the new signature; add classification cases.[^adapter-tests]
- `tests/e2e/test_edge_semantics.py` — the one existing `columns()` caller.[^e2e]
- `tests/test_cli.py` — doctor's exit codes and output.
- `docs/09-data-modeling.md` — §7.2's "caught: never" rows become "caught by doctor", and the
  section on what fails when. **Trust-boundary file.**
- `docs/03-setup-workflow.md` — what doctor does today and what still waits for the MCP bundle
  (FR-9). **Trust-boundary file.**
- `docs/07-code-map.md` — the new module, and `columns()` finally having a caller.
  **Trust-boundary file.**
- `README.md`, `AGENTS.md` — doctor moves from roadmap to shipped, with its limits stated.

**Files to add**

- `src/semantiql/doctor.py` — `Finding`, `check`, and the individual checks.
- `tests/test_doctor.py` — a healthy model, and one deliberately broken model per finding kind.

**Files not touched, but adjacent** — `engine/` in its entirety, and `knowledge/`: doctor reads
the model through the same loader and adds nothing to it.[^model] Suggestions reuse the
case-insensitive close-match approach the validator already takes, rather than a second
spelling of it.[^validate]

# Open research questions

None. The one real unknown — whether DuckDB reports usable type names through the Python
cursor — is settled by the existing `columns()` implementation reading `cursor.description`,
which carries type codes alongside names.[^duckdb-adapter]

[^constitution]: `.specify/memory/constitution.md` — N1, N3, N4, N5 and the trust-boundary section.
[^base]: `src/semantiql/adapters/base.py` — the `Adapter` Protocol and `columns(relation: str) -> list[str]`.
[^duckdb-adapter]: `src/semantiql/adapters/duckdb.py` — `relation()`, `columns()` interpolating into `SELECT * FROM {relation} LIMIT 0`, and `duckdb.connect(database, read_only=database != ":memory:")`.
[^cli]: `src/semantiql/cli.py` — `NOT_YET_IMPLEMENTED`, `_render`, and the documented exit codes 0/1/2/3.
[^model]: `src/semantiql/knowledge/model.py` — `Dimension.type`, `Measure.agg`, `Table.entity_names`.
[^validate]: `src/semantiql/engine/validate.py` — `_suggest` using `difflib.get_close_matches` case-insensitively.
[^e2e]: `tests/e2e/test_edge_semantics.py` — `test_the_adapter_can_introspect_the_corpus`.
[^adapter-tests]: `tests/test_adapter_duckdb.py` — the adapter's direct tests.
