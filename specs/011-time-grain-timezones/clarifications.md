---
type: Clarifications
title: Time grains and time zones — clarifications
description: 8 ambiguities resolved before planning, four of them by measuring both engines rather than reasoning — including one that corrects the spec's framing of the problem.
resource: specs/011-time-grain-timezones/clarifications.md
tags: [sdd, clarifications, engine, time-grains]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T01:12:00+07:00' }
sources:
  - id: probe
    resource: clarifications.md
    title: Live probe of DuckDB 1.x and PostgreSQL 17.10 run at clarify time — results transcribed in Q1, Q2, Q3 and Q7
    last_modified: 2026-08-17
  - id: model
    resource: ../../src/semantiql/knowledge/model.py
    title: Dimension.type is Literal["string","date","number","boolean"] — no way to say "carries a timezone"
    last_modified: 2026-08-16
  - id: compile
    resource: ../../src/semantiql/engine/compile.py
    title: exp.TimestampTrunc built over the bare column, line 191
    last_modified: 2026-08-16
  - id: base
    resource: ../../src/semantiql/adapters/base.py
    title: ColumnKind — the four-word vocabulary that cannot currently express "timestamptz"
    last_modified: 2026-08-17
status: draft
---

Every decision below was made **by the agent**, autonomously. Four were settled by running both
engines rather than by reasoning about them, and the first one **contradicts the spec** — the
measurement was worth more than the hypothesis.

## Q1: Is this an engine *divergence*, or something worse?

- (a) Postgres diverges from DuckDB — the framing `spec.md` was written with
- (b) Both engines behave the same way, and both depend on a session setting

**Chosen: (b), by measurement.**[^probe] The spec presents this as Postgres disagreeing with
DuckDB. That is true of the *return type* and false of the thing that matters. Both engines
were pointed at one row, `2026-07-01T02:00:00+00`, in a timezone-carrying column:

```
                     server = UTC        server = America/Chicago
  Postgres           2026-07-01          2026-06-01
  DuckDB             2026-07-01          2026-06-01
```

They agree — and they are **both** wrong in the same way, because both truncate in the session's
timezone. That is materially worse than a divergence, for one reason worth stating plainly: a
differential suite can never catch it. Two engines agreeing is exactly what that suite checks
for, so the strongest control this repo has is structurally blind here.

**Consequence for the spec.** The Why section is amended: the problem is not "Postgres is
different", it is "a grain is computed in a timezone nobody declared, on every engine". FR-1's
wording — identical on every engine *and every server configuration* — already covers it; the
motivation prose did not.

## Q2: What fixes the `date`-column case?

- (a) `CAST(<column> AS TIMESTAMP)` inside the truncation
- (b) Cast the result afterwards
- (c) Leave it; the buckets already agree

**Chosen: (a) — measured.**[^probe] The whole `date`-column symptom is Postgres resolving
`date_trunc(text, date)` to its `timestamptz` overload. Casting the argument picks the
`timestamp` overload instead:

```
  date_trunc('month', d)                        -> 2026-01-01 00:00:00+07:00
  date_trunc('month', CAST(d AS timestamp))     -> 2026-01-01 00:00:00
```

DuckDB returns `2026-01-01 00:00:00` with or without the cast, so after this both engines return
the same naive value — FR-7 satisfied, with no bucket moving on either. (c) is rejected because
"the numbers happen to line up" is not a property anyone can rely on; the type difference is
real and a client formatting it renders two different strings today.

**And it is one line in canonical SQL.** `exp.TimestampTrunc(this=exp.cast(col, "TIMESTAMP"), …)`
renders identically in both dialects, and sqlglot passes it through duckdb→postgres unchanged,
so N4 holds and MySQL and BigQuery inherit the fix rather than rediscovering it.[^compile]

## Q3: Does that cast also fix a timezone-carrying column?

- (a) Yes, one fix covers both
- (b) No — it converts to the session timezone first, then discards the offset

**Chosen: (b) — measured, and this is the load-bearing finding.**[^probe]

```
  server = America/Chicago
    date_trunc('month', tstz)                     -> 2026-06-01
    date_trunc('month', CAST(tstz AS timestamp))  -> 2026-06-01     <- cast does NOT help
    date_trunc('month', tstz AT TIME ZONE 'UTC')  -> 2026-07-01     <- stable across servers
```

So there are two problems wearing one costume, and Q2's cheap fix solves only the first. `AT
TIME ZONE '<zone>'` is the construct that makes the answer configuration-independent, verified
stable across `UTC` and `America/Chicago`, and sqlglot transpiles it unchanged.

## Q4: For a timezone-carrying column, compute or refuse?

- (a) Refuse the grain unless the model declares which timezone the buckets are drawn in
- (b) Default to UTC and proceed
- (c) Proceed in the session timezone, as today, and document it

**Chosen: (a) — decided by the agent from N2.** (c) is the status quo and is the bug. (b) is the
tempting one and it is still a guess: "revenue by month, in UTC" is a *different question* from
"revenue by month, in the timezone the business operates in", and a company in Chicago asking
for monthly revenue does not mean UTC. Picking one silently produces a number that is defensible,
plausible, and not what was asked — which is the definition N2 gives of the worst failure
available. Declared, it is reviewable in git (N3); undeclared, the request is refused with a
message naming the timezone as the cause (FR-2).

## Q5: How does the model say "this column carries a timezone"?

- (a) A new `type:` value, e.g. `type: timestamptz`
- (b) Keep `type: date` and add an optional `timezone:` key to the dimension
- (c) Infer it from the database at query time

**Chosen: (b) — decided by the agent from where each field is already used.**[^model]
`Dimension.type` is `Literal["string","date","number","boolean"]` and it drives **filter literal
typing** — spec 004 made it enforced rather than declarative. Adding a fifth value would make
every `type`-consuming branch ask "is this one of the two date-ish ones?", which is how a small
vocabulary rots. `timezone:` is orthogonal: it answers "in which zone are buckets drawn", it is
absent for the overwhelming majority of models, and its absence over a tz-carrying column is
exactly the condition Q4 refuses on.

(c) is rejected outright: `validate` runs before the adapter is consulted, by design — that
ordering is what makes N1 structural — so runtime inference would either move validation after
the database or add a second path to it.

## Q6: What tells anyone the column carries a timezone at all?

- (a) `ColumnKind` gains a value, so the adapter reports it — **rejected on evidence, see below**
- (b) `Column` gains a boolean field
- (c) Only the model's `timezone:` key matters; the physical type is never consulted

**Chosen: (b) — reversed from (a) during planning, on evidence.** (c) is rejected outright: it
would leave a model author's mistake undetectable, which is the failure `doctor` exists to
prevent. Today both adapters map `timestamp` and `timestamptz` to kind `date`, so the two are
indistinguishable at exactly the layer that needs to tell them apart — a second gap in the seam,
found the same way the missing `close()` was.

**(a) was chosen first and is wrong**, and reading `doctor.py` is what said so.
`_check_declared_type` compares `column.kind == declared` for equality. Add a fifth `ColumnKind`
and every `timestamptz` column declared `type: date` immediately reports *"declared date, but
column is timestamp with time zone — filters on it will be typed wrongly"*. That message is
false: filtering a `timestamptz` against a date literal works fine, and it is not what this spec
is about. Fixing it would mean teaching the equality check that two of the five kinds are
interchangeable for filtering but not for grains — which is how a four-word vocabulary stops
being worth having.[^base]

`Column.carries_timezone: bool` leaves `kind` and every existing comparison untouched, and
carries exactly the one fact the new check needs. Recorded rather than quietly swapped, because
the first answer had a real argument behind it and the reason it loses is worth keeping.

## Q7: Do the five grains agree across engines today?

- (a) Yes, all five
- (b) No, and `week` is the suspect

**Chosen: (a) — measured, and the spec's suspicion was wrong.**[^probe] All of `year`,
`quarter`, `month`, `week`, `day` produce identical buckets on both engines for a `date` column;
`week` starts Monday on both (`2026-01-01` → `2025-12-29`). So FR-3 is a **coverage** task, not
a bug hunt: add the four missing grains to the differential suite so the agreement is asserted
rather than assumed. Recorded because the spec named `week` as "the next one to doubt", and it
turned out not to be.

## Q8: Does adding the cast change any answer that is correct today?

- (a) No — verify and proceed
- (b) Unknown, so gate it behind a flag

**Chosen: (a), with the verification made an explicit task rather than an assumption.** DuckDB
already returns a naive timestamp for `date_trunc` over a `DATE`, with and without the cast, so
the retail and TPC-H suites should be untouched. That is a prediction until the suites run, so
the plan carries it as a task whose failure is a finding, not a nuisance — the backward-
compatibility NFR exists precisely because a change that fixes one number by moving another is
worse than the bug.

[^probe]: Live probe run at clarify time against DuckDB 1.x in-process and PostgreSQL 17.10 on
    localhost; the tables in Q1, Q2, Q3 and Q7 transcribe its output.
[^model]: `src/semantiql/knowledge/model.py` — `Dimension` and its `type` Literal at line 29.
[^compile]: `src/semantiql/engine/compile.py` — `exp.TimestampTrunc` over the bare column at line 191.
[^base]: `src/semantiql/adapters/base.py` — `Column` and the `ColumnKind` vocabulary.
