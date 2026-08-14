# implement phase

Execute the approved task list, verifying at every step.

## Pre-flight

Identify the active spec dir and verify every prerequisite:

- The constitution has been read this session.
- `spec.md` `sdd_phase` is at least `tasking`.
- `plan.md` carries a Repository Impact Map.
- **The checkpoints are on record:** `spec.md` has its checkpoint-1 `verified` entry and `plan.md` its checkpoint-2 entry; at T2, `tasks.md` has checkpoint 3. Machine attestations satisfy this on an autonomous run. A missing entry means that checkpoint never fired — run it, rather than treating the conversation as the record.
- `tasks.md` (or the Inline tasks section of `plan.md`) was approved, or analyze came back clean.
- `validation.md` exists.
- The working tree is on the feature branch `NNN-name`, or the user waived that.

Any prerequisite missing → stop and report. Don't improvise.

## Per-task loop

For each task in dependency order:

1. **Read** the task's Files, Depends on, Verification, and Constitution check fields.
2. **Run the scope-drift detector** — `git status`, and compare the files changed so far against the impact map. Files outside the map mean escalation; see below.
3. **Trust-boundary files.** Touching a trust-boundary artifact: autonomous runs summarise the diff in the report and proceed, because the constitution already forced this change to T2. **The constitution itself is the exception** — never edit it without explicit approval, autonomous or not; propose the diff and continue with the rest of the tasks.
4. **Implement it**, driving `/tdd` at the seams the plan agreed — one red-green slice at a time.
5. **Verify** with the task's own verification step, plus the repo's structural check for any manifest or layout change, and a re-sync check where derived copies exist.
6. **Tick the checkbox** in `tasks.md` (or in the Inline tasks section).
7. **Deviation → amend the artifacts first.** Update `spec.md` / `plan.md`, then change the code. Spec-anchored discipline is not optional.

`[P]` tasks may be batched, but verify each one individually.

## Escalation

When the drift detector fires on an `sdd_tier: T1` spec, pick the mode by what the unplanned files are:

**Soft escalation (default)** — no trust-boundary artifact and no constitutional invariant in the new scope:

1. Edit `sdd_tier: T1` → `T2` in `spec.md` frontmatter.
2. Append a tier-escalation note to `plan.md` giving (a) the original file count and which T1 condition failed, (b) the new file list, (c) confirmation that no trust-boundary artifact is in scope. Add a `specs/log.md` line: `* **Update**: Soft-escalated NNN to T2 — <which condition failed>`.
3. Continue, without re-running clarify / plan / tasks.

**Hard escalation (forced)** — the new scope touches a trust-boundary artifact or a constitutional invariant:

1. **HALT.** Don't implement the task.
2. Report which artifact forced it.
3. Offer two choices: revert the new scope and stay in T1, or flip the spec to T2 and re-run plan to redo the impact map and earn checkpoint 3.

Hard escalation halts even on an autonomous run. It is not a review preference — it fires precisely when the change has grown into territory the approved impact map never covered.

## Final gate

Once every task is ticked:

1. **Run the repo's verify gate** — the `TF` task, typically `./scripts/verify.sh`. Report its output verbatim. Absent, say which gate this expects and fall back to the repo's own lint / typecheck / test commands.
2. **Validate the bundle** — `python3.13 .claude/skills/okf/scripts/validate_bundle.py specs/`. Errors block shipping; the one expected `no index.md` warning per spec dir does not.
3. **Walk `validation.md`**, ticking each AC and naming the verification step that proves it.
4. **Run `/code-review`** over the diff — Standards and Spec axes both.
5. **Close the artifacts out:**
   - `spec.md` → `sdd_phase: shipped`, `status: stable`.
   - `plan.md`, `tasks.md`, `validation.md`, `clarifications.md` → `status: stable`.
   - `specs/index.md` → update the change's line to `shipped`.
   - `specs/log.md` → `* **Update**: Shipped NNN [NNN](/NNN-short-kebab-name/spec.md)`.

   Leave `stale_after` off all of them: what shipped is settled.
6. **Summarise:** tasks completed, `git diff --stat`, verify result, and every spec / plan amendment made along the way.
7. **Propose** the commit message and PR description. Commit or push only once the user says so.

## If verify fails

Report it verbatim. Diagnose before touching anything: which step failed, which file, and whether this session caused it.

Autonomous: apply a minimal fix if this session caused the failure, and record it as an amendment. A pre-existing failure, or one needing a non-trivial fix, is reported rather than fixed — it earns its own spec instead of riding along in this one. Never report the gate green when it is not, and never weaken a check to make it pass; that converts a visible failure into a silent one, which is the worst trade this lifecycle can make.
