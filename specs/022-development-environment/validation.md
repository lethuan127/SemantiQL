---
type: Validation
title: A new machine can reproduce the development rig — validation
description: Acceptance criteria traced to FR-1..FR-8.
resource: specs/022-development-environment/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T16:27:32+00:00' }
status: stable
---

# Acceptance criteria

- [x] **AC-1** (FR-1): The seven scripts are in `scripts/fixtures/` and tracked.
  - **Proven by:** `git ls-files scripts/fixtures` listing all seven, and
    `test_each_fixture_script_is_tracked_by_git` parametrised over each by name — **named, not
    globbed**, because a glob over a silently emptied directory passes with zero files, which is the
    failure being guarded.
- [x] **AC-2** (FR-2): They still work, and their output still lands in the ignored workspace.
  - **Proven by:** running `build.py` and `fetch_retail.py` from the new location — the fixture rebuilt
    and 1,067,371 rows reloaded, with 136 MB under `.test-workspace/data` and `git status` clean.
- [x] **AC-3** (FR-3): Code and output are separated.
  - **Proven by:** `test_no_fixture_output_is_tracked` (no `.parquet`/`.xlsx`/`.zip`/`.duckdb` tracked)
    and `test_each_python_fixture_script_writes_only_into_the_ignored_workspace`, which asserts each
    loader walks to the repository root rather than assuming where it sits. `.gitignore` was **not**
    changed: the `.test-workspace/` rule was always right, and only became true once the code left.
- [x] **AC-4** (FR-4): Every dependency documented with its purpose and what breaks without it.
  - **Proven by:** `docs/12-development-environment.md`, split required/optional, with a
    "skipping it costs you" column. Every command in it was run on this machine.
- [x] **AC-5** (FR-5): The two irreproducible things are named.
  - **Proven by:** the same document — `claude plugin eval` (early access, exit 1) and SAP SALT (403,
    "not in the authorized list").
- [x] **AC-6** (FR-6): The runtime-fetched DuckDB extensions are recorded.
  - **Proven by:** the `httpfs`/`postgres`/`excel` table, and the note that a first run therefore needs
    network while the e2e suite skips offline with a stated reason.
- [x] **AC-7** (FR-7): `CONTRIBUTING.md` links to it from Setup.
- [x] **AC-8** (FR-8): A test stops the flaw returning.
  - **Proven by:** `tests/tooling/test_fixture_scripts.py`. **The mechanism was verified rather than
    assumed**: an untracked file placed in `scripts/fixtures/` is visible on disk and absent from
    `_tracked()`, so an on-disk-but-ignored script fails the guard. A first attempt to mutate the repo
    instead was refused by `git rm --cached` and proved nothing — recorded because a green test that
    ran against unchanged state is worse than no test.

# Found by the move itself

- [x] **mypy started checking these scripts**, because they left the ignored directory, and immediately
      found a real bug: `fetch_retail.py` indexed `fetchone()` without handling `None`. Fixed. The
      scripts had been outside every check in this repository for as long as they existed.

# Non-functional acceptance

- [x] **No data committed.** `git status` clean of the 46 MB workbook, the 50 MB parquet, the answer
      keys and the logs; `.env` rules untouched.
- [x] **No new project dependency.** `pyproject.toml` unchanged.
- [x] **The gate is unchanged and still offline.** `scripts/verify.sh` gained no step, so it still needs
      no `psql`, `tmux`, Docker or network.
- [x] **Trust boundary.** `docs/12-development-environment.md` is a new `docs/NN-*.md`, called out.
- [x] Gate green with Postgres up and with it down.

# Manual verification

1. Run each loader from the new path. **Run** for `build.py` and `fetch_retail.py`; `fetch.py` was run
   before the move and its output is still present; `fetch_salt.py` reaches its 403 as designed.
2. `git ls-files scripts/fixtures` — expect seven files. **Run.**
3. `./scripts/verify.sh` on a machine with none of the optional tools — **not run as a clean-machine
   test.** This machine has all of them. What *is* verified is that the gate gained no step and that
   both skipping paths (`pg` without a DSN, plugin validation without the CLI) still pass, which is the
   same property from the other side.
