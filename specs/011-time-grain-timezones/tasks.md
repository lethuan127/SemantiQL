---
type: Tasks
title: Time grains and time zones — tasks
description: 12 tasks in five phases plus two gate tasks — a blocking probe first, then the cast, the model field, the adapters and doctor, then the tests that can actually catch this class.
resource: specs/011-time-grain-timezones/tasks.md
tags: [sdd, tasks, engine, time-grains]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T01:45:00+07:00' }
sources:
  - id: plan
    resource: plan.md
    title: The approved plan, AD-1..AD-6 and the impact map these tasks derive from
    last_modified: 2026-08-17
  - id: clarifications
    resource: clarifications.md
    title: The measured decisions each task implements
    last_modified: 2026-08-17
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-17T01:50:00+07:00', checkpoint: 3,
      basis: '14 tasks in dependency order; 2 [P] groups checked file-by-file and found disjoint, with CLAUDE.md excluded by name as a symlink. T0 is a blocking measurement rather than code, because OQ-2 would invalidate AD-2 if it failed. T3 and T12 each carry an explicit warning against the shortcut that would destroy the check they exist for' }
status: stable
---

12 tasks plus two gate tasks, derived from the impact map.[^plan] Two `[P]` groups, both checked
for file overlap.

**T0 is blocking and comes first.** It is a measurement, not code: if it fails, AD-2 and the
whole `timezone:` mechanism are built on an assumption that does not hold, and the plan needs
revisiting before anything is written.[^clarifications]

# Phase 0 — resolve the blocking unknown

## ✅ T0. Verify `AT TIME ZONE` on DuckDB, end to end

- **Files:** none — a probe, recorded in the run report
- **Depends on:** —
- **Do:** on DuckDB, evaluate `DATE_TRUNC('month', <tstz> AT TIME ZONE 'UTC')` for a row at
  `2026-07-01T02:00:00+00`, under `SET TimeZone='UTC'` and `SET TimeZone='America/Chicago'`.
  DuckDB needs `pytz` importable to evaluate a `TIMESTAMPTZ` literal at all — that is what
  stopped this being answered during clarify (OQ-2). Repeat for all five grains (OQ-3).
- **Verification:** the bucket is identical under both session timezones, on both engines.
- **If it fails:** **stop and report.** `AT TIME ZONE` is not a portable fix, AD-2 is wrong, and
  the choice becomes refuse-always or a per-dialect construct — which would be an N4 problem
  worth its own spec.
- **✅ Result: passed**, and it found a hole. All five grains are affected and all five are fixed
  by `AT TIME ZONE` on both engines (OQ-2, OQ-3 resolved). But the probe also asked what happens
  when `AT TIME ZONE` is applied to a column that carries no timezone, and the answer is that it
  **moves the bucket** — on both engines for a naive `timestamp`, and on DuckDB for a `date`.
  AD-3 grew a second doctor check in response; T10 below carries it. Full numbers in
  clarifications Q9.

# Phase 1 — the common case

## ✅ T1. Cast inside the truncation

- **Files:** `src/semantiql/engine/compile.py`
- **Depends on:** T0
- **Do:** AD-1 — build `exp.TimestampTrunc(this=exp.cast(<column>, "TIMESTAMP"), unit=…)` when
  the dimension declares no `timezone:`. Comment *why* the cast exists (it selects Postgres's
  `timestamp` overload), because it reads as redundant on DuckDB and will be deleted by someone
  tidying up otherwise.
- **Verification:** `uv run mypy` clean; T2 and T3 assert the output.
- **Constitution check:** N4 — built in canonical SQL, verified to transpile unchanged. No
  adapter learns anything.

## ✅ T2. Update the compile assertions

- **Files:** `tests/test_compile.py`
- **Depends on:** T1
- **Do:** lines 287-288 assert the literal grain SQL; both gain the cast. **Do not** loosen them
  to substring-matching to avoid the edit — the exactness is the check.
- **Verification:** `uv run pytest tests/test_compile.py` green.

## ✅ T3. Update the e2e hand-written SQL

- **Files:** `tests/e2e/test_differential.py`
- **Depends on:** T1
- **Do:** lines 92-101 compare grains against hand-written physical SQL. The hand-written side
  gains the cast. **This is the row most at risk of being "fixed" by copying the generated
  output** — the point of that suite is that a human wrote the expected SQL independently, so
  write the cast in deliberately and confirm the *numbers* are unchanged, not just the strings.
- **Verification:** `uv run pytest -m e2e` green, and the year/quarter totals are the same values
  as before this change.
- **Constitution check:** N2 — if a total moves, the cast changed an answer that was correct, and
  that is a finding rather than a test to update.
- **✅ Result: no edit was needed, and the plan over-predicted here.** The e2e differential suite
  compares **values**, not SQL strings, and the cast is a no-op on DuckDB — so all 27 cases pass
  untouched, including the year and quarter grains. That is AC-10 satisfied by measurement
  rather than by inspection: no number moved. Recorded rather than quietly skipped, because a
  task that turns out to be unnecessary is evidence about the change, not an oversight.

# Phase 2 — the declared case

## ✅ T4. `Dimension.timezone`

- **Files:** `src/semantiql/knowledge/model.py`
- **Depends on:** T0
- **Do:** AD-2 and AD-3 — optional `timezone: str | None = None`; a validator rejecting a zone
  `zoneinfo.ZoneInfo` cannot resolve, and rejecting the key on a non-date dimension. Standard
  library only, no new dependency.
- **Verification:** covered by T6.
- **Constitution check:** N3 — **trust-boundary artifact**, the semantic model schema. The
  timezone becomes a reviewable, diffable model fact rather than a server setting.

## ✅ T5. Emit `AT TIME ZONE` when declared

- **Files:** `src/semantiql/engine/compile.py`
- **Depends on:** T1, T4
- **Do:** the second branch — `<column> AT TIME ZONE '<zone>'` inside the truncation. The zone is
  a **literal built from the model**, never interpolated into a string, for the same reason
  `relation()` builds rather than interpolates.
- **Verification:** covered by T6 and T11.

## ✅ T6. `[P]` Model and compile tests

- **Files:** `tests/test_grain_timezones.py` (new)
- **Depends on:** T4, T5
- **Do:** a valid zone loads; an unknown zone is a `ModelError` naming the zone; `timezone:` on a
  string dimension is refused; the emitted SQL carries `AT TIME ZONE` when declared and `CAST`
  when not. No database needed.
- **Verification:** `uv run pytest tests/test_grain_timezones.py` green with no database.

# Phase 3 — telling truth from lie

## ✅ T7. `Column.carries_timezone`

- **Files:** `src/semantiql/adapters/base.py`
- **Depends on:** T0
- **Do:** AD-4 — `carries_timezone: bool = False` on `Column`. **Not** a fifth `ColumnKind`; the
  docstring says why, naming the `_check_declared_type` equality comparison that a fifth kind
  would break. Defaulting to `False` keeps every existing construction valid.
- **Verification:** `uv run mypy` clean; existing adapter tests unchanged.
- **Constitution check:** N4 — this widens the seam a second time. Recorded as a finding in the
  report, as `close()` was in spec 010.

## ✅ T8. `[P]` DuckDB sets it

- **Files:** `src/semantiql/adapters/duckdb.py`
- **Depends on:** T7
- **Do:** set it from the `TIMESTAMP WITH TIME ZONE` / `TIMESTAMPTZ` spellings. Note the existing
  `startswith("TIMESTAMP")` branch already folds them into kind `date` — that stays correct and
  is not what this changes.
- **Verification:** `uv run pytest tests/test_adapter_duckdb.py` green, plus a new case.

## ✅ T9. `[P]` Postgres sets it

- **Files:** `src/semantiql/adapters/postgres.py`
- **Depends on:** T7
- **Do:** set it from the `timestamptz` type name. `timestamp` must stay `False` — the two
  spellings differ by exactly this and nothing else.
- **Verification:** `uv run pytest tests/test_adapter_postgres.py` green, plus a new case.

> **`[P]` group 1 — T8 and T9 touch one adapter each and share nothing.** Both depend on T7's
> field existing; neither reads the other.

## ✅ T10. The doctor finding

- **Files:** `src/semantiql/doctor.py`, `tests/test_doctor.py`
- **Depends on:** T8, T9
- **Do:** `_check_grain_timezone`, checking **both directions** (AD-3, extended after T0):
  (1) column carries a timezone and no `timezone:` is declared → problem;
  (2) `timezone:` is declared and the column carries none → problem, because `AT TIME ZONE` on a
  naive column *moves the bucket*. Each message names the timezone as the cause and the fix.
  Wire it into `check()`. **Leave `_check_declared_type` alone** (AD-4).
- **Verification:** `uv run pytest tests/test_doctor.py` green; both directions fire; a
  `timestamptz` column *with* a declaration and a `date` column *without* one are both silent.
- **Constitution check:** N2 — under AD-5 this check *is* the guarantee for the lying-model case,
  so a false negative here is the whole hole.

# Phase 4 — the tests that can catch this class

## ✅ T11. Server-timezone sweep

- **Files:** `tests/test_postgres_differential.py`
- **Depends on:** T5, T10
- **Do:** AD-6 — set the server's timezone to at least `UTC` and `America/Chicago` and assert the
  bucket does not move, for a declared-timezone dimension over a `timestamptz` column. **This is
  the only test in the repo able to catch this class**, because a differential comparison cannot:
  both engines agree while both are wrong. Say so in the docstring.
- **Verification:** green under both session timezones.

## ✅ T12. All five grains, plus retire the pinned test

- **Files:** `tests/test_postgres_differential.py`
- **Depends on:** T11
- **Do:** FR-3 — extend `REQUESTS` to `year`, `quarter`, `month`, `week`, `day`. FR-9 — delete
  `test_date_trunc_buckets_agree_but_postgres_attaches_a_timezone` and replace it with the real
  assertion: both engines now return the same naive value, so `DATE_TRUNC` rejoins `REQUESTS`
  and needs no special case.
- **Also:** `tests/e2e/test_postgres_parity.py` holds three grain cases as
  `xfail(strict=True)` pointing at this spec. `strict` means they **fail the build** once the
  fix lands — that is the designed signal. Move them from `GRAIN_CASES` into `CASES` and delete
  the xfail marker in this same change.
- **Verification:** `uv run pytest -m pg` green; the pinned test no longer exists.

# Phase 5 — derived copies and the gate

## ✅ T13. `[P]` Docs

- **Files:** `docs/09-data-modeling.md`, `docs/07-code-map.md`
- **Depends on:** T12
- **Do:** §3.4 and §3.7 document `timezone:`, with **AD-5's narrowing stated beside §3.4's
  existing note that `type:` is not checked against the real schema** — that is where a reader
  will be standing when it matters. The code map's `columns(source)` row gains
  `carries_timezone`. **Both are trust-boundary artifacts.**
- **Verification:** a reader can tell, from the docs alone, which timezone a month boundary is
  drawn in and what happens when it is not declared.

## ✅ T14. `[P]` Agent brief and spec 007

- **Files:** `AGENTS.md`
- **Depends on:** T12
- **Do:** the supported-constructs paragraph gains `timezone:`. Do **not** edit `CLAUDE.md` — it
  is a symlink. Spec 007's Out of scope is left as written: it was accurate when it shipped, and
  rewriting a shipped spec to look prescient is exactly what the artifact trail exists to
  prevent — 011 supersedes it by existing.
- **Verification:** `git status` shows `AGENTS.md` changed and `CLAUDE.md` not.

> **`[P]` group 2 — T13 and T14 are disjoint:** {`docs/09-data-modeling.md`,
> `docs/07-code-map.md`} · {`AGENTS.md`}. `CLAUDE.md` is excluded by name, being a symlink to
> `AGENTS.md`.

## ✅ TF. Final verify

- **Files:** —
- **Depends on:** T0–T14
- **Do:** `./scripts/verify.sh`, with and without a Postgres reachable.
- **Verification:** green both ways.

## ✅ TV. Validation pass

- **Files:** `validation.md`
- **Depends on:** TF
- **Do:** walk every AC and record the outcome. **The one to weigh rather than tick is FR-2**:
  under AD-5 it is met "for any model doctor passes", and the walk must say that rather than
  mark it green unqualified.
- **Verification:** every AC marked met, or recorded as not met with why.

[^plan]: `plan.md` — the impact map, AD-1..AD-6, and OQ-1..OQ-3.
[^clarifications]: `clarifications.md` — Q1..Q8; Q1, Q2, Q3 and Q7 measured against live engines.
