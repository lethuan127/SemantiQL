---
type: Plan
title: A new machine can reproduce the development rig — plan
description: Move seven scripts to scripts/fixtures/, point their output at the ignored workspace, and document the machine.
resource: specs/022-development-environment/plan.md
tags: [sdd, plan]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T16:20:54+00:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-17
  - id: gitignore
    resource: ../.gitignore
    title: The .test-workspace/ rule, and the .env rules that must survive untouched
    last_modified: 2026-08-18
  - id: fetch-retail
    resource: ../.test-workspace/fetch_retail.py
    title: HERE = Path(__file__).parent — the line that decides where output lands after a move
    last_modified: 2026-08-18
  - id: verify
    resource: ../scripts/verify.sh
    title: The gate — read to confirm no step gains a psql, tmux, Docker or network dependency
    last_modified: 2026-08-18
  - id: support
    resource: ../tests/_support.py
    title: REPO_ROOT, found by walking up to pyproject.toml — how the new test locates the scripts
    last_modified: 2026-08-18
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T16:20:54+00:00', checkpoint: 2,
      basis: 'Five rows, all footnoted. The decisive read was `HERE = Path(__file__).parent` in each script: it is what makes a move break the output paths, so AD-1 replaces it with a repo-root walk rather than a relative hop. The gate was read to confirm the offline promise is a property of which steps exist, not an accident.' }
---

# Constitution check

**Never commit data or secrets.** This moves *code*. The workbook, the parquet, the answer keys and the
run logs stay under `.test-workspace/`, and the `.env` rules are not touched.[^gitignore]

**The gate stays offline and free.** No step in `scripts/verify.sh` may start needing `psql`, `tmux`,
Docker or a fetch. Moving scripts into `scripts/` does not enrol them in anything — the gate runs named
steps, not a directory.[^verify]

**Dependency discipline.**[^constitution] Nothing is added to `pyproject.toml`. Every tool named is external, and the
three DuckDB extensions were already being fetched at runtime; documenting them is the change.

**Trust boundary.** A new `docs/12-development-environment.md`, stated as such.

# Approach

**Code moves, output does not.** `scripts/fixtures/` gets the seven files; `.test-workspace/` keeps
being where data, answer keys and logs land. The `.gitignore` gains nothing — the existing
`.test-workspace/` rule already covers output, and once the scripts are outside it the rule finally
means what it says.

**Each script needs one line changed.** They all compute `HERE = Path(__file__).parent` and write to
`HERE / "data"` and `HERE / "examiner"`.[^fetch-retail] After the move that would put a 46 MB workbook
in `scripts/fixtures/data/`, which is *not* ignored — so the fix is not cosmetic. Each script instead
walks up to the repository root and writes to `<root>/.test-workspace/`, which is the same walk
`tests/_support.py` already does to find `REPO_ROOT`.[^support]

**The document is organised by what breaks.** A dependency list that only says "install these" leaves a
reader unable to triage. Each entry says what it is for and what stops working without it, so someone
with no Docker knows exactly which suite skips and that the gate still passes.

# Architecture decisions

1. **Absolute output paths derived from the repository root, not a relative hop.** Rejected:
   `HERE.parent / ".test-workspace"`, which is correct only while the scripts sit exactly one level
   down. The root walk survives being moved again, and it is the pattern already in the test support
   module.

2. **`scripts/fixtures/`, not `scripts/`.** The existing `scripts/` holds things the gate and CI run.
   These are development rigs that download hundreds of megabytes; mixing them invites someone to wire
   one into `verify.sh`.

3. **One document, split required and optional.** Rejected: extending `CONTRIBUTING.md` inline, which
   would double its length and bury the mergeable-PR rules a contributor actually needs first.
   `CONTRIBUTING.md` links out instead.

4. **The gated things are named, not omitted.** `claude plugin eval` and SAP SALT cannot be reproduced
   on any machine right now. A setup document that quietly leaves them out sends the next person
   hunting for a mistake they did not make.

5. **A test asserts the scripts are tracked.** The flaw was invisible because everything worked locally.
   `git ls-files` is the only thing that would have caught it, so that is what the test runs.

# Repository Impact Map

## Files to move

- `.test-workspace/{build.py,fetch.py,fetch_retail.py,fetch_salt.py,judge.py,run-debug.sh,seed.sql}`
  → `scripts/fixtures/`, each with its output paths repointed at `<repo>/.test-workspace/`.[^fetch-retail]

## Files to add

- `docs/12-development-environment.md` — every dependency, what it is for, what breaks without it, and
  what cannot be reproduced at all. **Trust-boundary artifact.**
- `scripts/fixtures/README.md` — what each script does and the order to run them in.

## Files to modify

- `CONTRIBUTING.md` — the Setup section links to the new document.[^contributing]
- `tests/tooling/test_fixture_scripts.py` — FR-8: the scripts are tracked, and they parse.
- `.test-workspace/README.md` — reduced to a pointer, since the substance now lives in committed docs.
  It stays ignored, so it is a convenience rather than an artifact.

## Files not touched

- `.gitignore` — the `.test-workspace/` rule is already correct once the code is outside it, and the
  `.env` rules must not be disturbed.[^gitignore]
- `scripts/verify.sh` — unchanged, deliberately. If this needed a new step, the offline promise broke.
- `pyproject.toml` — no new dependency.

[^constitution]: `.specify/memory/constitution.md`.
[^gitignore]: `.gitignore` — `.test-workspace/`, `.env`, `.env.*`.
[^fetch-retail]: `.test-workspace/fetch_retail.py` — `HERE = Path(__file__).parent`, `DATA = HERE / "data"`, and the answer key at `HERE / "examiner"`.
[^verify]: `scripts/verify.sh` — the named steps, and the `pg` step's stated-reason skip.
[^support]: `tests/_support.py` — `REPO_ROOT` by walking up to `pyproject.toml`.
[^contributing]: `CONTRIBUTING.md` — the Setup section.
