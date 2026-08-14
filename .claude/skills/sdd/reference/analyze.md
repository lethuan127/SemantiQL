# analyze phase

Cross-check the artifacts for consistency and coverage. The last review before code gets written.

## Steps

0. **Tier check.** At `sdd_tier: T1`, report `analyze auto-skipped: Tier T1` and exit — checkpoint 2 already covered the review this phase mechanises.
1. **Identify the active spec dir** and read all four artifacts end to end.
2. **Run these checks, in order:**
   - **Requirement coverage** (spec → tasks) — for each `FR-N`, find the task(s) implementing it. Report any FR with zero matching tasks.
   - **Task justification** (tasks → spec) — for each task, trace it back to an FR, NFR, or architecture decision. Report any task with no clear justification.
   - **Acceptance coverage** (spec → validation) — for each `FR-N`, find its `AC-N`. Report any FR with no acceptance criterion.
   - **Manifest ↔ filesystem consistency** — every new directory in the impact map has a registration task, and every new registration entry has a directory-creation task.
   - **Canonicality** — every change to a derived copy traces to a change in its canonical source, plus a re-sync task. A direct edit to a derived copy with no canonical-source change is a blocker.
   - **Boundary safety** — grep the plan for paths reaching across a module boundary (`../` between packages). Report each as a blocker.
   - **Constitution honour** (plan + tasks → constitution) — for each non-negotiable touched, verify a task preserves it.
   - **Artifact conformance** — run `python3.13 .claude/skills/okf/scripts/validate_bundle.py specs/`. Any error is a blocker. Warnings are findings, except the expected one `no index.md for N concept(s)` per spec dir, which this bundle accepts by design.
   - **Checkpoint provenance** — `spec.md` carries a checkpoint-1 `verified` entry and `plan.md` a checkpoint-2 one; at T2, `tasks.md` carries checkpoint 3. A missing entry means that checkpoint never fired, whatever the conversation implies — a blocker, not a finding. A `human:` entry on a run nobody reviewed is a **fabricated review**: the most serious finding this phase can report.
   - **Map provenance** — every *Files to modify* row in the impact map has a footnote resolving to a `sources` entry. Unfootnoted rows are unverified claims; list each one.
   - **Bundle currency** — the change is listed in `specs/index.md` with its current phase, and `specs/log.md` has an entry for the latest phase.
   - **Carve-out check** — if the change turns out to qualify as a carve-out, say so and stop.
3. **Report** in three buckets:

   ```markdown
   ## analyze report — specs/NNN-name/

   ### ✅ Pass
   - All FRs covered by tasks.

   ### ⚠️ Findings
   - FR-3 has no corresponding AC.

   ### 🛑 Blockers
   - T2 reaches into another package via `../shared`.
   ```

## Stop condition

- Any 🛑 **blocker** → do not proceed to implement, autonomous or not. A blocker is the one thing this phase exists to stop, so stop and report it.
- Only ⚠️ **findings** → autonomous: fix what you can, list what you didn't and why, continue. Gated: state them, propose fixes, wait.
- All ✅ → "analyze clean — safe to implement", and continue.

Autonomous runs are where this phase earns its keep: it is the last mechanical check before code, and the only one left once the human checkpoints stop blocking. Never report it clean without running it.
