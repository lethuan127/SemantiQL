---
type: Spec
title: A time grain must not depend on the database server's timezone
description: DATE_TRUNC buckets by the server's TimeZone setting on Postgres, so the same model over the same data answers differently on two servers — and only one grain is currently checked across engines
resource: specs/011-time-grain-timezones/spec.md
tags: [sdd, spec, engine, time-grains, postgres]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T00:57:34+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-15
  - id: spec-007
    resource: ../007-time-grains/spec.md
    title: The time-grain spec, which put time zones explicitly out of scope
    last_modified: 2026-08-16
  - id: spec-010-validation
    resource: ../010-postgres-adapter/validation.md
    title: Where the divergence was found and recorded as a carried-forward finding
    last_modified: 2026-08-17
  - id: compile
    resource: ../../src/semantiql/engine/compile.py
    title: Where the truncation is built — exp.TimestampTrunc over the bare column
    last_modified: 2026-08-16
  - id: validate
    resource: ../../src/semantiql/engine/validate.py
    title: The closed grain set, and that a grain is only allowed on a date dimension
    last_modified: 2026-08-16
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-17T00:57:34+07:00', checkpoint: 1,
      basis: '9 FRs, each testable. Scope derived from a measured divergence rather than a suspicion — spec 010 ran both engines and recorded the result. FR-3 exists because the self-audit found the differential suite compares one grain of five, so this spec does not inherit an unearned assumption about the other four' }
status: draft
sdd_phase: tasking
sdd_tier: T2
---

**T2.** The fix lives in `engine/compile.py` — the layer every answer passes through — and the
change is very likely to touch `engine/validate.py`, the semantic model's type vocabulary, and
`docs/NN-*.md`. More than three files, and a trust-boundary artifact among them.

# What

A time grain answers the same way regardless of which machine the database runs on.

Today it does not. `SELECT revenue, DATE_TRUNC('month', order_date) FROM orders` bucketed on
Postgres depends on that server's `TimeZone` setting: the same model, over the same rows, gives
one answer on a server in UTC and a different one on a server in `Asia/Ho_Chi_Minh`. Nothing in
the request, the model, or the output says which one you got.

After this change, a grain either produces an answer that is the same everywhere, or SemantiQL
refuses to compute it — and the user is told which, rather than being handed a number whose
meaning depends on a setting they cannot see.

# Why

Found by spec 010's differential suite, which is exactly what that suite was
built for.[^spec-010-validation] `compile.py` emits `DATE_TRUNC('MONTH', order_date)` over the
bare column.[^compile] Postgres has three `date_trunc` overloads and resolves a `date` argument
to the `timestamptz` one, so it converts to the server's timezone, truncates there, and returns
a timezone-aware value. DuckDB returns a naive one. **The SQL sent to both engines is byte for
byte identical** — sqlglot is not involved, so this is not a transpile bug and cannot be fixed
by one.

**Amended after clarify measured it: this is not a divergence, and that is worse.** The framing
above describes the *return type*, which is the visible symptom. On the thing that matters —
which bucket a row lands in — **both engines behave identically, and both are wrong the same
way**. One row at `2026-07-01T02:00:00+00` in a timezone-carrying column buckets into July on a
server set to UTC and into June on a server set to `America/Chicago`, **on DuckDB as much as on
Postgres**.[^clarifications]

That reframes the whole change. The problem is not that one engine disagrees; it is that a grain
is computed in a timezone nobody declared, on every engine SemantiQL supports. And it means the
strongest control this repo owns is blind to it: a differential suite asks whether two engines
agree, and here they do.

**The harmless case, and why it is not the real problem.** With a `date` column, every value is
midnight, so truncating to month lands on the 1st either way. Buckets and totals match. Only the
rendering carries a spurious offset. That is what ships today, pinned by a test.

**The case that produces a wrong number.** A `timestamptz` column may legally be declared
`type: date` in the model — nothing refuses it, and `semantiql doctor` actively blesses it,
because the Postgres adapter classifies `timestamptz` as kind `date`. Now the overload is not a
formality: a row at `2026-07-01T02:00:00Z` buckets into **July** on a UTC server and into
**June** on a server in UTC-5. Revenue moves between months. The report is wrong, internally
consistent, reproducible on that machine, and undetectable by the analyst — the precise failure
N2 names as the worst one available.[^constitution]

**Spec 007 deferred this deliberately, and the deferral has come due.** Its Out of scope section
reads "Fiscal calendars, week-start configuration, and time zones", which was right when one
engine existed and the model's date type had no time component.[^spec-007] A second engine
removed the first assumption; `timestamptz` was always able to remove the second.

**A gap in what spec 010 actually verified, stated plainly.** The differential suite compares
`month` and no other grain. `_GRAINS` allows five — `year`, `quarter`, `month`, `week`,
`day`.[^validate] So "the two engines agree on grains" was evidence about one grain out of five.

Clarify measured the other four: **all five agree**, `week` included — both engines start it on
Monday. So FR-3 is a coverage task rather than a bug hunt, and the suspicion recorded here
before measuring (that `week` was the one to doubt) was wrong.[^clarifications] It stays written
down because the gap in coverage was real even though the bug behind it was not.

# User stories

- **As an analyst**, I get the same monthly revenue whether my company's Postgres runs in UTC or
  in local time — so a figure I paste into a deck does not depend on a DBA's configuration.
- **As a model author**, I point a `type: date` dimension at a `timestamptz` column and find out
  immediately whether that is safe — so I am not silently opted into timezone-dependent
  bucketing.
- **As a maintainer**, I see every supported grain compared across both engines — so "the
  engines agree" is a measured claim rather than an extrapolation from `month`.
- **As someone reading a report**, I can tell which timezone a month boundary was drawn in — so
  two reports that disagree can be reconciled instead of argued about.

# Functional requirements

- **FR-1** — A grain over a given column and a given set of rows produces identical buckets on
  every engine and every server configuration, or the request is refused.
- **FR-2** — Where a grain cannot be made configuration-independent, the request is **refused
  with a message naming the timezone as the cause** and what to change. Never computed and
  labelled. **Narrowed during planning** to: for any model that `semantiql doctor` passes. A
  model that misdescribes its own columns — declaring `type: date` over a timezone-carrying
  column with no timezone stated — is caught by `doctor` rather than refused at query time,
  because `validate` runs before the adapter by design and cannot see the physical type. The
  cost of closing that last gap is a database round-trip inside `run`, which is a larger change
  than this spec; the trade-off is argued in the plan's AD-5 and is the decision most worth
  overruling.[^clarifications]
- **FR-3** — Every grain in `_GRAINS` — `year`, `quarter`, `month`, `week`, `day` — is compared
  across DuckDB and Postgres by the differential suite, not just `month`.
- **FR-4** — Truncating a column that carries a timezone is either handled explicitly or
  refused. The current situation, where it is neither, ends.
- **FR-5** — Where the answer depends on a chosen timezone, that choice is visible in the
  semantic model rather than inherited from the server, and it is reviewable in git.
- **FR-6** — `semantiql doctor` reports a dimension whose declared type and whose column's
  timezone-carrying nature would produce configuration-dependent bucketing.
- **FR-7** — The result a caller receives is of a consistent type across engines for the same
  request, so a client formatting it cannot render two different strings for one answer.
- **FR-8** — The behaviour that ships today is documented in `docs/`, whichever way FR-2 and
  FR-4 resolve, so a reader can tell what a month boundary means.
- **FR-9** — `tests/test_postgres_differential.py`'s pinned-divergence test is replaced by the
  real assertion, rather than left pinning a behaviour this spec changed.

# Non-functional requirements

- **N2 (a silently wrong number is the worst failure)** — the tie-breaker throughout. Where a
  timezone-correct answer and a refusal are both available, refuse.[^constitution]
- **N3 (the YAML is the source of truth)** — if a timezone becomes part of what a grain means,
  it belongs in the model, reviewable and diffable, not in an environment variable or a server
  setting.[^constitution]
- **N4 (canonical dialect, then transpile)** — the fix belongs in the canonical SQL that
  `compile.py` builds, so it holds for MySQL and BigQuery too. A per-adapter patch would be a
  rule every future datasource has to rediscover.[^constitution]
- **Backward compatibility** — every answer the retail and TPC-H suites give today for a `date`
  column must be unchanged, or the change is altering correct answers to fix an incorrect one.

# Out of scope

- **Fiscal calendars and configurable week start.** `week` is in scope only to the extent of
  *measuring* whether the engines already disagree (FR-3) and refusing if they do. Making the
  start day configurable is its own change.
- **Sub-day grains.** Still out, as in spec 007 — but the reasoning changes: it was "the model's
  date type has no time component", and a `timestamptz` column means that was never quite true.
  Worth a clarification, not scope creep.
- **Filtering on a truncated value**, still deferred from spec 007.
- **Converting stored data.** SemantiQL reads; migrating a column's type is the operator's call.

[^clarifications]: `clarifications.md` — 8 ambiguities resolved before planning; Q1, Q2, Q3 and Q7 were settled by running both engines.
[^constitution]: `.specify/memory/constitution.md` — N2, N3, N4.
[^spec-007]: `specs/007-time-grains/spec.md` — the Out of scope section deferring time zones.
[^spec-010-validation]: `specs/010-postgres-adapter/validation.md` — finding 1 under "Findings carried forward".
[^compile]: `src/semantiql/engine/compile.py` — `exp.TimestampTrunc(this=built, unit=exp.var(item.grain))` at line 191, built over the bare column with no cast.
[^validate]: `src/semantiql/engine/validate.py` — `_GRAINS` at line 161, and the refusal at line 642 restricting a grain to a date dimension.
