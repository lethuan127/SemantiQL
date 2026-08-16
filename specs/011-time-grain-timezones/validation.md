---
type: Validation
title: Time grains and time zones — validation
description: Acceptance criteria traced to FR-1..FR-9, with FR-2's narrowing under AD-5 made explicit rather than tickable.
resource: specs/011-time-grain-timezones/validation.md
tags: [sdd, validation, engine, time-grains]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T01:52:00+07:00' }
status: stable
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
- **AC-6** (FR-6) — doctor checks **both directions**: it reports a `timestamptz` column with no
  `timezone:`, **and** a `timezone:` declared over a `timestamp` or `date` column. It stays
  silent for a `timestamptz` *with* a declaration and for a naive column *without* one. The
  second direction matters more than it looks: T0 measured that `AT TIME ZONE` on a naive column
  moves the bucket, so a misplaced declaration introduces the fault rather than missing it.
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
5. Declare `timezone:` on a dimension over a plain `date` column and confirm doctor reports it —
   the direction added after T0.
6. Confirm `tests/e2e/test_postgres_parity.py`'s three grain cases have moved out of
   `GRAIN_CASES` and no longer carry an xfail.

# Results — walked 2026-08-17

Verified against PostgreSQL 17.10 and DuckDB, and with no database reachable. Every AC met; two
are recorded with qualifications rather than ticked flat.

| AC | Outcome | Evidence |
|---|---|---|
| AC-1 | met | all five grains in the differential suite's `REQUESTS`; the server-timezone sweep holds across UTC / America/Chicago / Asia/Tokyo |
| AC-2 | **met, with the narrowing stated** | doctor reports both directions and exits non-zero; a request is *not* refused at query time. The guarantee is "for any model `doctor` passes" (AD-5), and `docs/09-data-modeling.md` §3.4 now says so where a model author will read it |
| AC-3 | met | `year`, `quarter`, `month`, `week`, `day` all in `REQUESTS` |
| AC-4 | met | declared → `AT TIME ZONE`; undeclared over a zoned column → doctor problem |
| AC-5 | met | `timezone:` is a model field; no environment variable participates |
| AC-6 | met | all four combinations checked: zoned-without, declared-over-naive → problems; zoned-with, naive-without → silent |
| AC-7 | met | `test_grains_now_return_the_same_naive_value` asserts `tzinfo is None` on both engines |
| AC-8 | met | §3.4 and a new §3.7 subsection, including the do-not-set-it warning |
| AC-9 | met | the pinned test is gone; `DATE_TRUNC` is back in `REQUESTS` with no special case |
| AC-10 | **met by measurement** | the e2e suite needed **no edit** — it compares values, and the cast is a no-op on DuckDB. All 27 cases pass untouched, so no number moved |
| AC-11 | **met in substance, not literally** | `engine/` still imports only `adapters.base`. The AC also said "no adapter contains the word `grain`" — three do, all in **comments** explaining why `carries_timezone` is a flag rather than a `kind`. No adapter contains grain *logic*. The AC was worded as a grep and the grep is the wrong instrument; recorded rather than quietly passed |

**Non-functional:** `./scripts/verify.sh` green both ways — 268 unit, 27 e2e, 57 pg, 0 OKF
errors. No new dependency (`zoneinfo` is standard library). `Column.carries_timezone` defaults
to `False`, so a third-party adapter keeps working.

## What the probes changed

- **T0 passed and found a hole.** `AT TIME ZONE` holds for all five grains on both engines, but
  only on a genuinely zone-carrying column. On a naive `timestamp` it moves the bucket on both
  engines; on a `date`, DuckDB moves it and Postgres does not. AD-3 grew its second doctor check
  in response — without it, a well-meant `timezone:` would *introduce* this spec's own fault.
- **T3 turned out unnecessary**, which is itself the AC-10 evidence.
- **The `strict` xfail did its job.** `tests/e2e/test_postgres_parity.py` held three grain cases
  as `xfail(strict=True)`; the fix turned them into hard failures, which is what moved them into
  `CASES`. The mechanism worked as designed rather than needing to be remembered.

## Carried forward

- **AD-5's residual gap is unchanged and intended:** a model nobody runs `doctor` against can
  still bucket by a timezone nobody chose. Closing it means a database round-trip inside `run`,
  which needs its own spec.
