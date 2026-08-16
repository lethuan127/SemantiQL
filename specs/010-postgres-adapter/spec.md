---
type: Spec
title: Postgres adapter — the second datasource
description: A Postgres adapter that proves N4 with a second engine, and the differential suite that shows the same model answers the same on both
resource: specs/010-postgres-adapter/spec.md
tags: [sdd, spec, adapters, postgres]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T00:29:12+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-15
  - id: datasources
    resource: ../docs/05-datasources.md
    title: Adapter architecture and the MVP datasource roadmap
    last_modified: 2026-08-15
  - id: adapter-protocol
    resource: ../src/semantiql/adapters/base.py
    title: The Adapter Protocol — the seam a second datasource has to fit through
    last_modified: 2026-08-17
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-17T00:29:12+07:00', checkpoint: 1,
      basis: '12 FRs, each testable; scope read from the four constraints the codebase already imposes — the Adapter Protocol, Datasource.dialect being already Literal["duckdb","postgres"], the secret-free CI rule, and doctors ColumnKind contract. FR-9 states N4 as a falsifiable check rather than an aspiration' }
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** Three conditions fail at once: a new external dependency (a Postgres driver), edits to
trust-boundary artifacts (the project manifest, `docs/05-datasources.md`, the README roadmap),
and more than three files touched.

# What

SemantiQL answers questions against a Postgres database, through the same semantic model YAML
it uses for DuckDB:

```
$ semantiql "SELECT revenue, channel FROM orders" \
    -m model.yml --datasource postgres --dsn postgresql://analyst@localhost/warehouse
channel  revenue
-------  -------
online   4821.50
retail   3390.00

$ semantiql doctor -m model.yml --datasource postgres --dsn postgresql://analyst@localhost/warehouse
orders
  ✓ source 'orders' has 12 columns
  ✗ dimension 'order_date' is declared string, but the column is timestamp without time zone
```

The model's semantic content — `tables`, `dimensions`, `measures`, `metrics` — is identical
between the two engines, and the connection details never appear in the file at all. Two things
may differ: `datasource.dialect`, and a `source` that names a **file**, because Postgres has no
file sources to point at. A model whose sources are tables moves between engines on one line;
one whose sources are CSV paths does not, and gets told so rather than shown a missing-table
error (clarification Q6).[^clarifications]

Today there is one adapter. `DuckDBAdapter` is constructed by name in `cli.py`, `--database`
takes a DuckDB file path, and `compile.py` hard-codes DuckDB as the canonical dialect it
transpiles *from*. The `Adapter` Protocol and `Datasource.dialect` both anticipate a second
engine — `dialect` is already `Literal["duckdb", "postgres"]` — but nothing has ever exercised
the seam, so "no core changes" is a claim rather than an observation.

# Why

N4 is the invariant the architecture rests on, and it is currently verified for imports and for
one transpile assertion, both of which a single-adapter repo can satisfy by accident. The
question N4 actually answers — *can someone add a datasource without touching `engine/`?* — has
never been asked of the code.

The cost of waiting compounds. Every feature since 004 has added a DuckDB-shaped decision at
the seam: `relation()` returns `read_csv_auto` for a `.csv` source, `_kind` maps DuckDB's type
names, `compile.py` names DuckDB as canonical, `validate.py` parses as DuckDB. Each is
defensible alone; together they are an abstraction nobody has tested, and the retrofit gets
more expensive with each spec that lands before it.

The `ColumnKind` contract is the sharpest case. `base.py` says in a comment that DuckDB says
`VARCHAR` where Postgres says `character varying`, and that translating between them is the
adapter's job — a design decided for a second adapter that does not exist.[^adapter-protocol] Doctor's
`_check_declared_type` treats `other` as silence, which is the right call *if* adapters
classify honestly; with one implementation there is no evidence the rule survives contact with
a type system that spells everything differently.

The user-facing case is smaller but real: the roadmap has promised DuckDB **and** Postgres as
the MVP since the constitution was written, and an analyst whose data is in Postgres cannot use
SemantiQL at all today.

# User stories

- **As an analyst whose warehouse is Postgres**, I point SemantiQL at my database with a DSN
  and ask a question in semantic SQL — so I get an answer without exporting anything to a file.
- **As a model author**, I develop against a DuckDB copy of my data and switch
  `datasource.dialect` to `postgres` for production — so the model I reviewed is the model that
  ships, unchanged.
- **As a contributor adding MySQL later**, I read one adapter module and one test module and
  know exactly what a datasource has to provide — so I do not have to reverse-engineer the seam
  from `engine/`.
- **As a maintainer**, I see a differential test fail when the two engines disagree on a number
  — so a dialect bug surfaces as a red test rather than as a wrong figure in someone's deck.

# Functional requirements

- **FR-1** — A `PostgresAdapter` satisfies the `Adapter` Protocol: `dialect`, `relation`,
  `columns`, `execute`. `isinstance(adapter, Adapter)` holds at runtime.
- **FR-2** — Semantic SQL runs end to end against a real Postgres database through
  `engine.run.run`, with no second path to the data.
- **FR-3** — For every request the existing suites answer against DuckDB, the same request
  against a Postgres copy of the same corpus returns the same rows and the same values. Numeric
  comparison tolerates representation differences (Postgres `numeric` vs DuckDB `DECIMAL`) but
  not value differences.
- **FR-4** — `columns()` classifies Postgres types into `ColumnKind` using Postgres's own type
  names, returning `other` for any type it cannot map rather than guessing. Types that are
  spelled differently but mean the same thing — `character varying`, `timestamp without time
  zone`, `double precision` — classify to the same `ColumnKind` as their DuckDB equivalents.
- **FR-5** — `semantiql doctor` runs against Postgres and produces the same three finding kinds
  it produces against DuckDB: missing column, declared-type mismatch, aggregation over a
  non-numeric column.
- **FR-6** — Connection details are supplied at the command line or the environment, never by
  the semantic model YAML. A model file carries no host, no port, no user, no password.
- **FR-7** — The CLI selects an adapter explicitly. The current DuckDB-only invocation keeps
  working unchanged, so no existing command or documented example breaks.
- **FR-8** — A Postgres that cannot be reached, or that rejects the SQL, surfaces as an
  `AdapterError` and exit code 3 — distinct from a `Refusal` and its exit code 1. A connection
  failure names what to check.
- **FR-9** — `engine/` imports nothing from `adapters/` but `adapters.base`, verified by the
  existing grep, and no file under `engine/` is modified by this change.
- **FR-10** — CI runs the Postgres suite with no repository secret, so a pull request from a
  fork runs it to completion.
- **FR-11** — With no Postgres reachable, the Postgres suite **skips with a stated reason** and
  `./scripts/verify.sh` still passes, so a fresh clone stays runnable with no database
  installed.
- **FR-12** — Every document that describes what is built is corrected in the same change: the
  README roadmap and `docs/05-datasources.md` record Postgres as shipped — both have named it MVP
  scope since before any code existed[^datasources] — the agent brief drops it from "Not yet
  built", the code map lists the new module, and the example model's comment stops claiming an
  engine swap changes nothing else in the file.
- **FR-13** — A model `source` naming a file — a `.csv` or `.parquet` path — is reported as
  unsupported on Postgres, naming the file source as the cause. It is never passed through as a
  table name, because the resulting "relation does not exist" sends the reader after the wrong
  problem. Added during clarify.[^clarifications]

# Non-functional requirements

- **N4 (canonical dialect, then transpile)** — this change exists to test N4, so it may not
  quietly weaken it: one new module under `adapters/`, zero files changed under `engine/`. If
  the seam turns out to need an engine change, that is a finding to escalate, not a diff to
  slip in.[^constitution]
- **N1 / N2 (validation over generation; a silently wrong number is the worst failure)** — the
  adapter does not validate and must not rewrite. `execute` runs already-validated,
  already-transpiled SQL. The differential suite is the N2 control for this change: two engines
  returning different numbers for one model is exactly the failure a user cannot
  detect.[^constitution]
- **N3 (the YAML is the source of truth, and datasource-independent)** — swapping engines
  changes `datasource.dialect` and nothing else. Any connection detail in the model file
  violates this.[^constitution]
- **N5 (read-only by default)** — the Postgres connection is opened read-only, and the precise
  scope of that guarantee is stated in the module docstring rather than implied, following the
  precedent `adapters/duckdb.py` set for the in-memory case.[^constitution]
- **CI stays secret-free** — the constitution's tech-stack section requires fork PRs to run to
  completion, which rules out any credential stored in repository secrets.[^constitution]
- **The dependency is not routine** — the constitution states that adding an external
  dependency is never a T1 change, and `CLAUDE.md` asks that one be raised before it is added.
  This spec is that raising; the driver choice and its rationale belong in the plan.[^constitution]

# Out of scope

- **`semantiql init`** — schema introspection for generating a first model. `columns()` is half
  of it, and it is tempting to finish it here; it is a larger design question about writing YAML
  and belongs to its own spec.
- **Connection pooling, retries, statement timeouts.** One connection per invocation, matching
  what the DuckDB adapter does. A long-lived server is post-MVP.
- **MySQL, SQLite, and SQLAlchemy.** `docs/05-datasources.md` puts them at v2 and names
  SQLAlchemy as the likely mechanism; this change adds a direct driver and does not pre-commit
  the v2 approach.
- **Postgres-specific SQL features** — schemas beyond a qualified table name, materialized
  views, extensions. The compiler emits the same canonical subset for both engines by design.
- **Moving the canonical dialect off DuckDB.** `compile.py` transpiling *from* DuckDB is a
  deliberate choice recorded in that module; a second target is what N4 asks for, not a second
  source.

[^clarifications]: `clarifications.md` — 8 ambiguities resolved before planning, all decided by
    the agent from repo evidence.
[^adapter-protocol]: `src/semantiql/adapters/base.py` — the `ColumnKind` comment naming Postgres's
    spelling, and the `Column.native_type` docstring.
[^datasources]: `docs/05-datasources.md` — the roadmap table's MVP row, "DuckDB + Postgres".
[^constitution]: `.specify/memory/constitution.md` — N1, N2, N3, N4, N5, the tech-stack section's
    secret-free CI rule and its "never a T1 change" rule for dependencies, and the trust-boundary
    list, which names the project manifest and `docs/NN-*.md`.
