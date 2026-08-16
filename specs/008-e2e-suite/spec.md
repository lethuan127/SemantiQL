---
type: Spec
title: An end-to-end suite over a large dataset
description: Prove the engine on 60k+ rows against independently written SQL, alongside the fast unit tests
resource: specs/008-e2e-suite/spec.md
tags: [sdd, spec, testing]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:52:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-15
  - id: dataset-research
    resource: ../tests/conftest.py
    title: "Dataset probes run at spec time: TPC-H scale, cardinality, null coverage, and the read-only adapter path"
    last_modified: 2026-08-16
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T23:52:00+07:00', checkpoint: 1,
      basis: '8 FRs, each testable; the dataset choice is backed by measured generation cost and cardinality at three scale factors, and FR-6 exists because the chosen corpus provably cannot cover null semantics' }
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** Registering a pytest marker edits the project manifest, which the constitution names a
trust-boundary artifact.

# What

A second test suite, running beside the unit tests, that exercises the whole path — model,
validation, compilation, execution — against a dataset large enough that a mistake cannot hide
in ten rows.

Each case states a question twice: once as semantic SQL, once as physical SQL written by hand,
and asserts the two agree. Where the answer is a fixed figure, it is pinned.

Today the only end-to-end evidence is a ten-row CSV whose expected totals were computed by
hand. That is precise and worth keeping, but it cannot catch a fault that only appears with
many groups, several years of dates, or a hundred thousand rows.

# Why

Seven specs have shipped since the corpus was written, and the engine now filters, orders,
limits, derives metrics and truncates dates. Every one of those was proven on the same ten
rows — where a month contains eight rows, `LIMIT 2` is most of the table, and every date is in
one of two months. A grain bug that only shows across years, or a grouping bug that only
appears with more than three groups, would pass the whole suite today.

The unit tests should stay as they are: fast, exact, hand-computed, and the thing that runs on
every save. What is missing is the other kind of evidence — scale, variety, and an oracle
that is not a number someone typed.

# User stories

- **As a contributor**, I can run a suite that would catch a bug the ten-row corpus cannot —
  so a green build means more than it did.
- **As a contributor working offline or on a plane**, the suite skips rather than fails, and
  the fast tests still run.
- **As a reviewer**, each case shows the physical SQL it is checked against — so I can see
  what "correct" means without trusting the engine to tell me.

# Functional requirements

- **FR-1** — A large corpus is generated locally, deterministically, with no credentials and
  no committed data file, at a scale the runner chooses.
- **FR-2** — Each end-to-end case pairs a semantic request with independently written physical
  SQL and asserts the two return the same rows.
- **FR-3** — The suite covers every construct the engine now supports: measures, metrics,
  dimensions, filters, ordering, limits, offsets, and time grains — including at least one
  case combining all of them.
- **FR-4** — The suite is separately selectable, so it can be scaled up or skipped without
  touching the unit tests, and the unit tests keep running exactly as they do now.
- **FR-5** — When the corpus cannot be built — no network on a first run — the suite skips
  with a clear reason and the verify gate stays green.
- **FR-6** — A small companion table covers what the large corpus provably cannot: nulls,
  a boolean dimension, and a group whose metric divisor is zero.
- **FR-7** — The suite exercises the file-backed, read-only adapter path, which nothing tests
  today, and asserts the connection itself refuses a write.
- **FR-8** — Running the suite, and changing its scale, is documented where a contributor
  looks.

# Non-functional requirements

- **N1/N2** — the point of the suite: an answer that differs from independently written SQL is
  a wrong number, and it must fail the build.[^constitution]
- **N5 (read-only)** — FR-7 tests the half of the guarantee the in-memory path cannot
  demonstrate.[^constitution]
- **Fast by default** — the unit suite must not get slower; the large suite at its default
  scale must stay within a few seconds.[^dataset-research]

# Out of scope

- **Committing a dataset file** to the repository.
- **A performance benchmark.** This measures correctness at scale, not speed.
- **The accuracy benchmark against raw-table querying**, which is a different thing the README
  promises and this does not deliver.
- **Multi-table cases**, since the engine is single-table by design.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N5.
[^dataset-research]: Probes at spec time: TPC-H `dbgen` at sf=0.01/0.1/1 took 0.18s/1.3s/9.5s
    producing 60,175/600,572/6,001,215 rows; the denormalised view spans 1992-01-01 to
    1998-08-02 with 5 segments, 25 nations, 5 regions, 7 ship modes and 1,000 customers, and
    contains no nulls and no boolean column.
