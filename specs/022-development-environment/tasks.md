---
type: Tasks
title: A new machine can reproduce the development rig — tasks
description: 6 tasks — move, repoint, guard, document.
resource: specs/022-development-environment/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T16:20:54+00:00' }
sources:
  - id: plan
    resource: /022-development-environment/plan.md
    title: The approved plan these tasks derive from
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T16:20:54+00:00', checkpoint: 3,
      basis: 'The guard test comes before the document because the document asserts the scripts exist on a clone; writing it first would make it briefly untrue. Repointing output is its own task rather than part of the move, because a move that silently starts writing a 46 MB workbook into a tracked directory is the failure being fixed, reintroduced.' }
---

Derived from the approved plan.[^plan]

- [x] **T1.** `git mv` the seven scripts into `scripts/fixtures/`.
  - **Verification:** `git ls-files scripts/fixtures` lists all seven.
  - **Constitution check:** code only — no data moves.

- [x] **T2.** Repoint every output path at `<repo>/.test-workspace/` via a root walk.
  - **Depends on:** T1
  - **Verification:** run each loader; data lands in `.test-workspace/data`, keys in
    `.test-workspace/examiner`, and `git status` stays clean.
  - **Constitution check:** **the one that matters.** A relative path left as-is would write the 46 MB
    workbook into tracked `scripts/fixtures/data/`.

- [x] **T3.** The guard test: the scripts are tracked by git, and each parses.
  - **Depends on:** T1
  - **Verification:** watched failing with a path that is ignored, so it is known to detect the flaw.
  - **Constitution check:** — .

- [x] **T4.** `docs/12-development-environment.md`: required and optional tools, what each is for, what
      breaks without it, and what cannot be reproduced at all.
  - **Depends on:** T2
  - **Verification:** every command in it was run on this machine.
  - **Constitution check:** **trust-boundary artifact.**

- [x] **T5.** `scripts/fixtures/README.md`, and `CONTRIBUTING.md` linking to the new document.
  - **Depends on:** T4

- [x] **T6.** Reduce `.test-workspace/README.md` to a pointer.
  - **Depends on:** T4

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh` with Postgres up and down, and confirm no gate step
      gained a `psql`, `tmux`, Docker or network dependency.
- [x] **TV. Validation pass** — walk `validation.md`; confirm `git status` shows no data, and that a
      simulated fresh clone would carry all seven scripts.

[^plan]: The impact map approved at gate 2.
