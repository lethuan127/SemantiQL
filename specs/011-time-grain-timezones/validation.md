---
type: Validation
title: Time grains and time zones — validation
description: Acceptance criteria traced to FR-1..FR-9, with FR-2's narrowing under AD-5 made explicit rather than tickable.
resource: specs/011-time-grain-timezones/validation.md
tags: [sdd, validation, engine, time-grains]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T01:52:00+07:00' }
status: draft
---

# Acceptance criteria

- **AC-1** (FR-1) — for a `date` column, all five grains return the same bucket **and the same
  naive value** on DuckDB and Postgres; for a `timestamptz` column with a declared `timezone:`,
  the bucket is unchanged across at least two server timezone settings.
- **AC-2** (FR-2) — **the one to weigh, not tick.** Under AD-5 this is met *for any model
  `semantiql doctor` passes*. The walk must record it in those words. A model declaring
  `type: date` over a timezone-carrying column with no `timezone:` is reported by doctor as a
  problem with a non-zero exit; it is **not** refused at query time, and the reasoning is AD-5.
- **AC-3** (FR-3) — `REQUESTS` in the differential suite covers `year`, `quarter`, `month`,
  `week`, `day`.
- **AC-4** (FR-4) — a timezone-carrying column under a grain is either computed in a declared
  zone or flagged by doctor. Neither silently session-dependent nor undetectable.
- **AC-5** (FR-5) — the chosen zone appears in the model YAML, and `git diff` on the model shows
  it changing. No environment variable and no server setting participates.
- **AC-6** (FR-6) — doctor emits the new finding for a `timestamptz` column with no `timezone:`,
  and does **not** emit it for a naive `timestamp` or a `date` column.
- **AC-7** (FR-7) — both engines return the same Python type for the same grain request. Checked
  by asserting `tzinfo` is `None` on both for the undeclared case, and equal for the declared
  case.
- **AC-8** (FR-8) — `docs/09-data-modeling.md` documents `timezone:`, and states what happens
  when it is absent over a tz-carrying column, beside §3.4's existing note that `type:` is not
  schema-checked.
- **AC-9** (FR-9) — `test_date_trunc_buckets_agree_but_postgres_attaches_a_timezone` no longer
  exists, and `DATE_TRUNC` is back in `REQUESTS` with no special case.
- **AC-10** (backward compatibility NFR) — **every number the retail, e2e and differential
  suites assert today is unchanged.** A moved total means the cast altered a correct answer and
  is a finding, not a test to update.
- **AC-11** (N4) — `grep -rnE "adapters(\.|[[:space:]]+import)" src/semantiql/engine/` still
  matches only `adapters.base`, and no adapter contains the word `grain`.

# Non-functional acceptance

- `./scripts/verify.sh` green with and without a Postgres reachable.
- No new external dependency — `zoneinfo` is standard library.
- `Column.carries_timezone` defaults to `False`, so no third-party adapter breaks.

# Manual verification

1. Run T0's probe and record its output, before trusting AD-2.
2. Write a model with `timezone: America/Chicago` over a `timestamptz` column; run the same
   question against a Postgres set to `UTC` and to `Asia/Tokyo`; confirm identical buckets.
3. Remove the `timezone:` key and confirm `semantiql doctor` reports it and exits non-zero.
4. Typo the zone (`America/Chigago`) and confirm the model fails to load, naming the zone.
