---
type: Plan
title: Time grains and time zones — plan
description: Cast inside the truncation for the common case, an optional dimension `timezone:` emitting AT TIME ZONE for the tz-carrying case, and a doctor check for the model that lies about which it has.
resource: specs/011-time-grain-timezones/plan.md
tags: [sdd, plan, engine, time-grains]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T01:25:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-15
  - id: clarifications
    resource: clarifications.md
    title: The 8 decisions this plan implements, four of them measured
    last_modified: 2026-08-17
  - id: compile
    resource: ../../src/semantiql/engine/compile.py
    title: exp.TimestampTrunc(this=built, unit=…) over the bare column at line 191
    last_modified: 2026-08-16
  - id: validate
    resource: ../../src/semantiql/engine/validate.py
    title: _GRAINS at 161, the grain-on-a-date-dimension refusal at 642, Projection.grain at 219
    last_modified: 2026-08-16
  - id: model
    resource: ../../src/semantiql/knowledge/model.py
    title: Dimension — column, type, label, description; frozen, extra=forbid
    last_modified: 2026-08-16
  - id: doctor
    resource: ../../src/semantiql/doctor.py
    title: _check_declared_type's equality comparison at 97, _check_aggregation at 117, check() at 135
    last_modified: 2026-08-17
  - id: base
    resource: ../../src/semantiql/adapters/base.py
    title: Column(name, native_type, kind) and the ColumnKind vocabulary
    last_modified: 2026-08-17
  - id: duckdb-adapter
    resource: ../../src/semantiql/adapters/duckdb.py
    title: _kind()'s TIMESTAMP prefix branch, which folds TIMESTAMPTZ into date
    last_modified: 2026-08-17
  - id: postgres-adapter
    resource: ../../src/semantiql/adapters/postgres.py
    title: _KINDS mapping timestamp and timestamptz both to date
    last_modified: 2026-08-17
  - id: differential
    resource: ../../tests/test_postgres_differential.py
    title: The pinned-divergence test FR-9 replaces, and REQUESTS, which covers one grain
    last_modified: 2026-08-17
  - id: compile-test
    resource: ../../tests/test_compile.py
    title: The literal grain-SQL assertions at lines 287-288
    last_modified: 2026-08-16
  - id: doctor-test
    resource: ../../tests/test_doctor.py
    title: The tmp_path + duck fixture shape the eight finding tests use
    last_modified: 2026-08-17
  - id: e2e-differential
    resource: ../../tests/e2e/test_differential.py
    title: Grain checks against hand-written physical SQL, lines 92-101
    last_modified: 2026-08-17
  - id: data-modeling
    resource: ../../docs/09-data-modeling.md
    title: 3.4 Dimension fields, 3.7 Time grains, and the note that type is not schema-checked
    last_modified: 2026-08-17
  - id: code-map
    resource: ../../docs/07-code-map.md
    title: The adapter-seam table's columns(source) row
    last_modified: 2026-08-17
  - id: example-model
    resource: ../../examples/retail/semantic_model.yml
    title: The retail dimensions — date, string, string; none needs a timezone
    last_modified: 2026-08-17
  - id: agents
    resource: ../../AGENTS.md
    title: The agent brief's supported-constructs paragraph and N4 note; CLAUDE.md symlinks to it
    last_modified: 2026-08-17
  - id: spec-007
    resource: ../007-time-grains/spec.md
    title: What the grain feature promised, and that time zones were deferred
    last_modified: 2026-08-16
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-17T01:40:00+07:00', checkpoint: 2,
      basis: 'map derived from 14 file reads plus a live two-engine probe; all 14 existing-file rows footnoted after a self-audit caught 6 listed without evidence — reading them found that tests/e2e/test_differential.py checks grains against hand-written physical SQL, which the map had called conditional and is in fact certain. AD-4 reverses clarification Q6 on evidence from doctor.py. AD-5 narrows FR-2 and is flagged as the decision most worth overruling; 3 open questions stated, OQ-2 blocking the first implement task' }
status: stable
---

# Constitution check

**N1 — validation before the data.** No new path to the database, and `validate` keeps running
before the adapter is consulted. The one thing this plan deliberately does *not* do is have
`run` ask the adapter about column types mid-flight, which would put a database round-trip
inside the chokepoint — see AD-5 for what that costs and why it is still the right
call.[^validate]

**N2 — a silently wrong number is the worst failure.** The tie-breaker throughout, and the
reason `timezone:` is not defaulted to UTC.[^clarifications] Read AD-5 before accepting this
plan: it narrows FR-2's guarantee, and the narrowing is the most important sentence here.

**N3 — the YAML is the source of truth.** The timezone a grain is drawn in becomes a model
field, reviewable and diffable, rather than an environment variable or a server
setting.[^constitution] `knowledge/model.py` defines the semantic model's schema, which the
constitution's trust-boundary list names explicitly — so this change is T2 on that ground alone.

**N4 — canonical dialect, then transpile.** Both constructs — `CAST(x AS TIMESTAMP)` and
`x AT TIME ZONE 'zone'` — were measured through sqlglot duckdb→postgres and pass through
unchanged, so the fix is built once in canonical SQL and every future engine inherits
it.[^clarifications] **No adapter learns anything about grains.**

**N5, N6, N7** — untouched.

**Trust-boundary artifacts** in scope, all planned rather than discovered: `knowledge/model.py`
(the model schema), `docs/09-data-modeling.md` and `docs/07-code-map.md`. The constitution is
not touched.

# Approach

Spec 007 built the grain feature and explicitly deferred time zones, so this plan extends that
feature rather than reopening it.[^spec-007] Two problems wearing one costume,[^clarifications]
so two mechanisms, and the split is what
keeps the common case free:

**The common case — a `date` or naive `timestamp` column — gets a cast and nothing else.**
`compile.py` wraps the column in `CAST(… AS TIMESTAMP)` before truncating. That picks Postgres's
`timestamp` overload instead of its `timestamptz` one, so both engines return the same naive
value and neither consults a session setting. No model change, no new syntax, no refusal, and
measurement says no bucket moves.[^compile]

**The tz-carrying case gets an explicit declaration.** `Dimension` gains an optional
`timezone: str | None`. Declared, `compile.py` emits `<column> AT TIME ZONE '<zone>'` inside the
truncation, which measurement shows is stable across server timezones.[^model] [^clarifications]

**The model that lies gets caught by `doctor`, not by `validate`.** A dimension over a
`timestamptz` column with no `timezone:` declared is a model that misdescribes reality, which is
the same class of error as a wrong `column:` — and this repo already answers that class with
`doctor` rather than with a runtime refusal. `Column` gains `carries_timezone: bool` so doctor
can see it.[^base] [^doctor]

Tests run at three seams: `compile` (the emitted SQL, no database), `doctor` (the new finding),
and the differential suite (all five grains, both engines, plus a server-timezone sweep that is
the only test able to catch this class at all).[^differential]

# Architecture decisions

**AD-1 — the cast goes inside `TimestampTrunc`, in canonical SQL.**
`exp.TimestampTrunc(this=exp.cast(exp.column(c), "TIMESTAMP"), unit=…)`. Measured to render
identically on both dialects.[^clarifications] Rejected: casting the *result*, which leaves the
overload resolution — and therefore the bucketing — untouched.

**AD-2 — `Dimension.timezone: str | None = None`, validated as a real IANA zone at load.**
`zoneinfo.ZoneInfo(value)` raises on an unknown zone, and the standard library already ships the
database, so this needs no dependency. Validating at load rather than at query time matches
where the model's other errors surface, and means a typo'd zone is a model error rather than a
mystery at 2am.[^model]

**AD-3 — `timezone:` on a non-date dimension is refused at model load, and `doctor` checks the
declaration against the physical column in both directions.** The loader half is unchanged: the
key means nothing on a string or a number, and a key that silently does nothing is how a model
grows lies. It is a loader check because it is a property of the model alone.[^model]

**The second half was added after T0 measured it**, and it is the reason this AD grew. `AT TIME
ZONE` is correct **if and only if** the column genuinely carries a timezone:

```
  column type   postgres                   duckdb
  timestamptz   stable                     stable
  timestamp     bucket moves               bucket moves
  date          stable                     bucket moves
```

On a `date` the two engines resolve the implicit cast in opposite directions — Postgres to
`timestamp`, DuckDB to `timestamptz`. So a `timezone:` on the wrong column does not merely fail
to help: **it introduces the exact fault this spec exists to remove**, and it does so on the
engine the canonical dialect is modelled on.[^clarifications]

The loader cannot catch that, because `type: date` covers `date`, `timestamp` and `timestamptz`
alike and the loader never sees the database. So `doctor` validates both directions:

1. column carries a timezone, no `timezone:` declared → problem
2. `timezone:` declared, column carries none → problem

Direction 2 is not symmetry for its own sake. Without it the declaration is trusted blindly, and
a model author trying to *do the right thing* is the one who breaks their own numbers.

**AD-4 — `Column.carries_timezone: bool`, not a fifth `ColumnKind`.** Reversed from
clarification Q6's first answer once `doctor.py` was read: `_check_declared_type` compares
`column.kind == declared` for equality, so a fifth kind makes every `timestamptz` column report a
spurious *"filters on it will be typed wrongly"*.[^doctor] A boolean leaves every existing
comparison untouched. Both adapters set it: DuckDB from its `TIMESTAMP WITH TIME ZONE` /
`TIMESTAMPTZ` spellings, Postgres from the `timestamptz` OID.[^duckdb-adapter] [^postgres-adapter]

**AD-5 — the guarantee is "given a model `doctor` passes", and FR-2 is amended to say so.**

This is the plan's weakest point and it should be read rather than skimmed.

FR-2 says a request that cannot be made configuration-independent is *refused*. Under this plan
it is refused **only when the model tells the truth about its columns**. A model declaring
`type: date` over a `timestamptz` column with no `timezone:` still compiles, still runs, and
still buckets in the session timezone — exactly today's bug. `doctor` reports it; `validate`
cannot, because `validate` runs before the adapter by design, and that ordering is what makes N1
structural rather than conventional.[^validate]

The alternative is to have `run` fetch column metadata whenever a request carries a grain and the
dimension declares no timezone, then refuse. That closes the hole completely. It also puts a
database round-trip inside the one function the whole architecture funnels through, on a path
that currently does exactly three things in a fixed order — and it makes `run`'s behaviour depend
on live schema, which is a different and larger claim than "validated against the model".

**Decided: model-declared plus doctor, and FR-2 is narrowed to match** — "refused, for any model
that `doctor` passes". Not left as an unstated gap. **This is the judgement call to overrule if
you overrule one**: the counter-argument is that N2 does not care whose fault the wrong number
is, and doctor is advisory while the bug is silent. Reversing it means a new spec for the
round-trip, not a patch to this one.

**Re-examined after T0, and it survives — but only because AD-3 grew.** T0 showed a misplaced
`timezone:` actively introduces the fault rather than merely failing to prevent it. That would
have made this trade materially worse than it was accepted on: doctor would be the only thing
standing between a well-intentioned model author and a wrong number they caused themselves. With
AD-3's direction-2 check, doctor covers both ways the declaration can disagree with reality, and
the residual gap is what it always was — *a model nobody ran `doctor` against*.

**AD-6 — the server-timezone sweep is the only test that can catch this class.** A differential
suite compares two engines; here they agree while both being wrong.[^clarifications] So the new
test varies the *server's* timezone across one engine and asserts the bucket does not move. It is
the control this repo did not previously have, and the reason it is called out separately from
FR-3's coverage work.

# Repository Impact Map

## Files to modify

- `src/semantiql/engine/compile.py` — wrap the grain column: `exp.cast(built, "TIMESTAMP")` when
  the dimension declares no timezone, `exp.AtTimeZone` when it does. One branch at line
  191.[^compile]
- `src/semantiql/knowledge/model.py` — `Dimension.timezone: str | None = None`; a validator
  rejecting an unknown IANA zone (AD-2) and rejecting the key on a non-date dimension (AD-3).
  **Trust-boundary artifact — the semantic model schema.**[^model]
- `src/semantiql/engine/validate.py` — `Projection` already carries `grain`; the compiler needs
  the dimension's `timezone`, which it reads from the model rather than from the request, so
  **this file may need no change at all**. Listed because the grain refusals at line 642 are
  where a new one would go if AD-5 is overruled.[^validate]
- `src/semantiql/adapters/base.py` — `Column` gains `carries_timezone: bool = False`. Widens the
  seam a second time; the default keeps every existing construction valid.[^base]
- `src/semantiql/adapters/duckdb.py` — set it from the `TIMESTAMP WITH TIME ZONE` / `TIMESTAMPTZ`
  spellings. Note the existing `startswith("TIMESTAMP")` branch already folds them into
  `date`.[^duckdb-adapter]
- `src/semantiql/adapters/postgres.py` — set it from the `timestamptz` type name.[^postgres-adapter]
- `src/semantiql/doctor.py` — a new `_check_grain_timezone`, and its wiring into `check()`.
  Deliberately **not** a change to `_check_declared_type`, per AD-4.[^doctor]
- `tests/test_postgres_differential.py` — replace the pinned-divergence test (FR-9); extend
  `REQUESTS` to all five grains (FR-3); add the server-timezone sweep (AD-6).[^differential]
- `tests/test_compile.py` — lines 287-288 assert the literal strings
  `"DATE_TRUNC('MONTH', order_date) AS order_date_month"` and
  `"GROUP BY DATE_TRUNC('MONTH', order_date)"`. Both change to carry the cast. Confirmed by
  reading, not assumed.[^compile-test]
- `tests/test_doctor.py` — a test for the new finding, following the `tmp_path` + `duck` fixture
  shape the eight existing tests use.[^doctor-test]
- `tests/e2e/test_differential.py` — **confirmed in scope, and it is the sharpest row here.**
  Lines 92-101 check grains against **hand-written physical SQL** (`DATE_TRUNC('year', …)`,
  `DATE_TRUNC('quarter', …)`), so the hand-written side has to gain the cast too. That is exactly
  the assertion most able to catch a mistake in AD-1 — and exactly the one where "just make it
  match" would destroy the check. It gets updated deliberately, with the reasoning
  recorded.[^e2e-differential]
- `docs/09-data-modeling.md` — §3.4 documents `Dimension`'s fields and §3.7 documents time
  grains; both gain `timezone:`. §3.4's existing note that `type:` is *not* checked against the
  real schema is the paragraph AD-5's narrowing belongs beside. **Trust-boundary
  artifact.**[^data-modeling]
- `docs/07-code-map.md` — the adapter-seam table's `columns(source)` row gains
  `carries_timezone`. **Trust-boundary artifact.**[^code-map]
- `AGENTS.md` — the supported-constructs paragraph gains `timezone:`, and the N4 note records
  that the seam widened a second time. **Added during analyze**, which found T14 editing a file
  the map had not listed — the gap this phase exists to catch. `CLAUDE.md` is a symlink to it
  and is explicitly not a second edit.[^agents]
- `examples/retail/semantic_model.yml` and `semantic_model.postgres.yml` — only if the change
  reads better with a worked `timezone:` example; not required by any FR. Both models' dimensions
  are `date`, `string`, `string`, so neither needs one to keep working.[^example-model]

## Files to add

- `tests/test_grain_timezones.py` — the model-level checks (AD-2, AD-3) and the compile-level
  emission, none of which need a database.

## Files not touched, but adjacent

- `src/semantiql/engine/run.py` — **no change**, and AD-5 is the decision that keeps it that way.
- `src/semantiql/cli.py` — no change; no new verb or flag.
- `src/semantiql/knowledge/expression.py` — metrics are unaffected; a grain applies to a
  dimension.

# Open research questions

- **OQ-1 — does the cast move any answer the suites currently assert?** Measurement says no
  (DuckDB already returns naive for `date_trunc` over a `DATE`), but that is a prediction until
  the retail, TPC-H and differential suites run. Clarification Q8 makes it an explicit task
  whose failure is a finding.[^clarifications]
- **OQ-2 — does `AT TIME ZONE` behave identically on DuckDB?** Verified stable on Postgres and
  verified to transpile unchanged; **not yet run end to end on DuckDB**, because DuckDB needed
  `pytz` installed to evaluate a `TIMESTAMPTZ` literal at all during clarify. First task of the
  implement phase, before any code depends on it.
- **OQ-3 — is `week` affected by the timezone question too?** All five grains agree between
  engines for a `date` column, but the sweep in AD-6 has only been reasoned about for `month`. If
  a week boundary moves under a timezone change where a month boundary does not, that is worth
  knowing before the docs make a general claim.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N3, N4, and the trust-boundary list naming the semantic model schema and `docs/NN-*.md`.
[^clarifications]: `clarifications.md` — Q1 through Q8; Q1, Q2, Q3 and Q7 measured against live DuckDB and PostgreSQL 17.10.
[^compile]: `src/semantiql/engine/compile.py` — `exp.TimestampTrunc(this=built, unit=exp.var(item.grain))` at line 191.
[^validate]: `src/semantiql/engine/validate.py` — `_GRAINS` at 161, `Projection.grain` at 219, the grain refusals at 642-652.
[^model]: `src/semantiql/knowledge/model.py` — `Dimension` at 25, frozen with `extra="forbid"`.
[^doctor]: `src/semantiql/doctor.py` — `_check_declared_type`'s `column.kind == declared` at 97, and `check()` at 135.
[^base]: `src/semantiql/adapters/base.py` — `Column(name, native_type, kind)` and the `ColumnKind` docstring.
[^duckdb-adapter]: `src/semantiql/adapters/duckdb.py` — `_kind`'s `startswith("TIMESTAMP")` branch.
[^postgres-adapter]: `src/semantiql/adapters/postgres.py` — `_KINDS` mapping `timestamp` and `timestamptz` both to `date`.
[^differential]: `tests/test_postgres_differential.py` — `REQUESTS`, and `test_date_trunc_buckets_agree_but_postgres_attaches_a_timezone`.
[^spec-007]: `specs/007-time-grains/spec.md` — the grain feature and its deferral of time zones.
[^compile-test]: `tests/test_compile.py` — the literal grain assertions at lines 287-288.
[^doctor-test]: `tests/test_doctor.py` — the eight finding tests and their `tmp_path` + `duck` fixtures.
[^e2e-differential]: `tests/e2e/test_differential.py` — grains checked against hand-written physical SQL, lines 92-101.
[^data-modeling]: `docs/09-data-modeling.md` — §3.4 `Dimension`, §3.7 Time grains, and §3.4's note that `type:` is not checked against the real schema.
[^code-map]: `docs/07-code-map.md` — the adapter-seam table's `columns(source)` row.
[^agents]: `AGENTS.md` — the supported-constructs paragraph and the N4 section, both updated by spec 010; `ls -l CLAUDE.md` shows the symlink.
[^example-model]: `examples/retail/semantic_model.yml` — the three dimensions and their declared types.
