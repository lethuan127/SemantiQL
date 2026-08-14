---
type: Plan
title: Initialize the SemantiQL repo — plan
description: A src-layout Python package whose modules mirror the four architectural layers, a single verify gate, a DuckDB example over bundled CSV, and the community-health artifacts.
resource: specs/001-init-project-scaffold/plan.md
tags: [sdd, plan, scaffold]
generated: { by: claude-code/claude-opus-5, at: '2026-08-15T01:13:42+07:00' }
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-15T01:30:58+07:00', checkpoint: 2,
      basis: 'map derived from 7 reads/greps; all 4 existing-file rows footnoted to files actually read; 3 open questions resolved from evidence, none requiring an invented fact' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables and the settled tech stack, read at plan time
    last_modified: 2026-08-15
  - id: clarifications
    resource: /001-init-project-scaffold/clarifications.md
    title: The four clarify decisions this plan implements
    last_modified: 2026-08-15
  - id: readme
    resource: ../README.md
    title: README as committed — heading structure, the npx claim at line 44, Status at line 56
    last_modified: 2026-08-14
  - id: setup-doc
    resource: ../docs/03-setup-workflow.md
    title: Builder flow doc — the npx install step at line 1 of the numbered list
    last_modified: 2026-08-14
  - id: docs-index
    resource: ../docs/README.md
    title: Design-docs index — a table of 01..06, so a new doc needs a row here
    last_modified: 2026-08-14
  - id: gitignore
    resource: ../.gitignore
    title: .gitignore as committed — carries an obsolete Node section, lacks Python tool caches
    last_modified: 2026-08-14
  - id: tree
    resource: ../
    title: Repo root listing plus a find for pyproject.toml/package.json/*.py — confirmed no source or manifest exists
    last_modified: 2026-08-15
status: stable
---

# Constitution check

Every invariant this change touches, and how the plan preserves it.[^constitution]

| Invariant | How the plan holds it |
|---|---|
| **N1 / N2** validation is the centrepiece; a silent wrong number is the worst failure | `engine/validate.py` sits *on* the query path, not beside it: `engine.run()` calls validate before any adapter is reached, and the adapter API takes only already-validated SQL. FR-5's refusal test asserts the block. There is no code path from question to data that skips it. |
| **N3** one YAML file is the source of truth | `knowledge/model.py` defines pydantic models; `knowledge/loader.py` is the only reader. The example ships `examples/retail/semantic_model.yml` — no model values embedded in Python. |
| **N4** canonical dialect then transpile; one adapter per datasource, no core changes | The seam is `adapters/base.py`, a `Protocol` of `connect / introspect / execute`. `engine/` emits canonical SQL and calls `sqlglot.transpile` to the adapter's declared dialect; it never imports a concrete adapter. Adding MySQL means one new file in `adapters/` plus one registry entry. |
| **N5** read-only by default | The DuckDB adapter opens its connection `read_only=True`; the example reads CSV. No write path exists to review. |
| **N7** no NoSQL | Dependency set is sqlglot, duckdb, pydantic, pyyaml + dev tools. Nothing else enters. |
| **Trust-boundary artifacts** | This change *creates* `pyproject.toml` and `uv.lock`, and *modifies* `docs/03-setup-workflow.md`. Both are trust-boundary, so their tasks pause for confirmation before writing.[^constitution] |

No invariant needs amending.

# Approach

**A src-layout package whose module names are the architecture.** `src/semantiql/` rather than a flat
`semantiql/`, so tests import the installed package instead of accidentally importing the working directory —
the failure mode that makes "works locally, fails in CI" possible. Each of the four layers in
`docs/02-architecture.md` gets exactly one module, which is what makes FR-14 a five-line table rather than an
essay.

**One seam, declared before there is a second implementation.** N4's promise is only testable when a second
datasource arrives, so the plan pins it now: `engine/` depends on `adapters.base.Adapter`, never on
`adapters.duckdb`. If a future datasource forces an `engine/` change, that is the design smell the constitution
names, and it will be visible as a diff in the wrong module.

**The verify gate is one script, and CI runs that script.** `scripts/verify.sh` runs ruff format check, ruff
lint, mypy, pytest, and the OKF bundle validator. CI calls the same script rather than restating the steps, so
FR-6's "cannot disagree" is structural rather than a promise. Nothing in it needs a secret, which satisfies the
fork-PR constraint by construction.

**Governance is named but not built.** The fourth layer has no MVP requirement here. The code map will state
that it is unimplemented and where it will live — an empty module would be worse than an honest absence.

# Architecture decisions

1. **src layout over flat layout.** Costs one line of config; removes a whole class of import-shadowing bugs
   and makes the packaged artifact the thing under test.
2. **pydantic for the semantic model, not raw dict access.** N3 makes the YAML authoritative, which means a
   malformed model must fail loudly at load with a field-level message, not surface as a wrong number later.
   This is N2 applied to configuration.
3. **`Protocol` for the adapter seam, not an ABC.** Structural typing keeps a third-party adapter from having
   to import and subclass SemantiQL internals, which keeps "one adapter, no core changes" true for outsiders
   too.
4. **The example is CSV read through DuckDB, not a checked-in `.duckdb` file.** `.gitignore` already excludes
   `*.duckdb`,[^gitignore] and a binary fixture is unreviewable. CSV keeps the fixture diffable and proves the
   file-querying path the README advertises.
5. **`uv.lock` is committed.** Reproducible installs for strangers, which is the point of FR-1.
6. **The quickstart documents the from-source path now, not `uvx semantiql`.** See the open question below —
   this is the one place the plan knowingly differs from the constitution's wording.

# Repository Impact Map

Derived from a repo-root listing and a `find` for `pyproject.toml` / `package.json` / `*.py`, which returned
nothing outside `.claude/` — so the code side of this map is entirely additive.[^tree]

## Files to modify

- `README.md` — replace the `npx semantiql init` claim at **line 44**; add a **Quickstart** section, which the
  file currently has no heading for at all (headings are Why / How it works / Key ideas / Roadmap / Status /
  License); rewrite **Status** at line 56 from "Design phase. Follow along" to the FR-11 support statement
  naming the maintainer and weekly-triage-no-SLA.[^readme][^clarifications]
- `docs/03-setup-workflow.md` — step 1 of the builder flow says `npx semantiql init`; becomes the uv
  equivalent. **Trust-boundary artifact: pause and confirm the diff before writing.**[^setup-doc][^constitution]
- `docs/README.md` — a table of docs 01–06; add rows for the two new docs below.[^docs-index]
- `.gitignore` — delete the obsolete `# Node` section (`node_modules/`, `dist/`); add `.ruff_cache/`,
  `.mypy_cache/`, `.pytest_cache/`. Leave `uv.lock` tracked, and keep the existing `.env*` and `*.duckdb`
  rules.[^gitignore]

## Files to add

**Package and tooling**

- `pyproject.toml` — project metadata, `license = "MIT"` matching `LICENSE`, `requires-python = ">=3.11"`,
  the `semantiql` console script, and ruff/mypy/pytest config in one file. *Trust-boundary from creation.*
- `uv.lock` — generated, committed.
- `scripts/verify.sh` — the single verify gate; exits non-zero naming the failed step.

**Source — one module per architectural layer**

- `src/semantiql/__init__.py` — version and public surface.
- `src/semantiql/knowledge/model.py` — pydantic models for dimensions, measures, metrics, virtual views.
- `src/semantiql/knowledge/loader.py` — the only YAML reader.
- `src/semantiql/engine/validate.py` — validates a request against the loaded model; returns a refusal reason.
- `src/semantiql/engine/compile.py` — semantic SQL → canonical SQL → `sqlglot.transpile` to the target dialect.
- `src/semantiql/engine/run.py` — the one entry point: validate, compile, execute. The chokepoint N1 depends on.
- `src/semantiql/adapters/base.py` — the `Adapter` Protocol and dialect declaration. **The N4 seam.**
- `src/semantiql/adapters/duckdb.py` — read-only DuckDB adapter.
- `src/semantiql/cli.py` — the console entry point.

**Example and tests**

- `examples/retail/semantic_model.yml` — the example model.
- `examples/retail/orders.csv` — small, diffable fixture.
- `tests/test_loader.py`, `tests/test_compile.py`, `tests/test_adapter_duckdb.py` — unit level.
- `tests/test_example_end_to_end.py` — FR-4: the example produces the correct answer.
- `tests/test_validation_refuses.py` — FR-5: an unvalidatable request is refused, not guessed.

**Community health**

- `SECURITY.md` — GitHub private reporting only, 5-business-day ack, 30-day fix-or-timeline.[^clarifications]
- `CODE_OF_CONDUCT.md` — Contributor Covenant verbatim. **Blocked: the personal reporting address is not yet
  supplied**, so this file's task cannot complete.[^clarifications]
- `CONTRIBUTING.md` — setup, all-checks and single-test commands, mergeable-PR criteria, weekly-triage-no-SLA,
  what is out of scope.
- `.github/workflows/ci.yml` — calls `scripts/verify.sh` on push and pull_request; `permissions: contents:
  read`; no secrets.
- `.github/ISSUE_TEMPLATE/bug.yml`, `.github/ISSUE_TEMPLATE/feature.yml`, `.github/PULL_REQUEST_TEMPLATE.md`.

**Documentation**

- `docs/07-code-map.md` — FR-14: each of the four layers → its module, and the adapter seam with what the core
  guarantees either side.
- `docs/08-positioning.md` — FR-15: how SemantiQL differs from Cube, dbt Semantic Layer, MetricFlow, Malloy.

## Files not touched, but adjacent

- `LICENSE` — correct MIT text and holder already; only the SPDX id gets mirrored into `pyproject.toml`.
- `docs/01,02,04,05,06-*.md` — the design spec this build follows. If the build contradicts one, that is a
  finding for a later spec, not a silent edit here. `docs/06` names the prior art that `docs/08` will analyse.
- `.claude/`, `.specify/`, `specs/` — agent tooling and change records; untouched by this change.
- `CLAUDE.md` — already corrected when the runtime was decided; no further change expected.

# Open research questions

**All three resolved at checkpoint 2 from evidence, autonomously.** Each resolution and its rejected
alternative is recorded below; none required inventing a fact.

1. **Resolved: document the from-source path.** Publishing is out of scope in the spec, so `uvx semantiql`
   cannot work yet. README and `docs/03` show `git clone` → `uv sync` → `uv run semantiql`, and name `uvx` as
   arriving with the first release. *Rejected:* publishing to PyPI inside this spec, which the spec's Out of
   scope forbids.
2. **Resolved: two new docs.** `docs/07-code-map.md` and `docs/08-positioning.md`. *Rejected:* extending
   `docs/06-research-notes.md`, which would be a trust-boundary write carrying genuinely new content rather
   than a correction.
3. **Resolved: `requires-python = ">=3.11"`.** Nothing in the dependency set needs 3.12. Local verification
   runs on 3.13 because 3.11 is not installed on this machine; CI covers 3.11 explicitly so the floor is
   tested rather than merely declared.

Original framing, kept for the record:

1. **`uvx semantiql init` cannot work until the package is on PyPI, and publishing is out of scope for this
   spec.** The constitution's tech-stack section states the command as if it works.[^constitution] So a literal
   reading of FR-13 — "every published command is the command that actually works" — conflicts with a literal
   reading of the constitution. **Proposed resolution:** README and `docs/03` document the from-source path
   (`git clone` → `uv sync` → `uv run semantiql …`) as the working quickstart, and mention `uvx semantiql`
   explicitly as arriving with the first release. This keeps FR-13 true today and needs a one-line constitution
   note rather than an invariant change. Confirm at gate 2.
2. **Does `docs/` gain two files or does existing content absorb them?** `docs/06-research-notes.md` already
   lists the prior art as "to study", so FR-15 could extend it instead of adding `docs/08`. The plan proposes
   new files because editing `docs/06` is a trust-boundary write for content that is genuinely new rather than
   corrected. Either is defensible; gate 2 is the place to choose.
3. **Python floor: 3.11 or 3.12?** The constitution says 3.11+. Nothing in the dependency set requires 3.12.
   Staying at 3.11 widens the contributor base; the plan assumes 3.11 and the CI matrix will test 3.11 and 3.13.

[^constitution]: `.specify/memory/constitution.md` — N1–N7, trust-boundary artifacts, and the settled Python/uv tech stack.
[^clarifications]: `clarifications.md` — the runtime, security-channel, conduct-contact and review-turnaround decisions.
[^readme]: `README.md` as committed — heading list, the `npx semantiql init` claim at line 44, the Status section at line 56.
[^setup-doc]: `docs/03-setup-workflow.md` as committed — `npx semantiql init` as step 1 of the builder flow.
[^docs-index]: `docs/README.md` as committed — a table indexing docs 01 through 06.
[^gitignore]: `.gitignore` as committed — Node section at lines 1–4, Python section at 6–12, `*.duckdb` at line 24.
[^tree]: Repo-root listing and a `find` for `pyproject.toml` / `package.json` / `*.py`, run 2026-08-15: no manifest and no Python source outside `.claude/`.
