# tasks phase

Produce `tasks.md` from the approved `plan.md`.

## Steps

0. **Tier check.** Read `sdd_tier` from `spec.md` frontmatter.
   - **T1 with ≤3 implementation steps** → append an **Inline tasks** section to the end of `plan.md` instead, each bullet carrying the same fields as a full task. Create no `tasks.md`. Set `sdd_phase: tasking` and exit. Checkpoint 3 doesn't fire at T1, so no checkpoint-3 `verified` entry is written — `plan.md`'s checkpoint-2 entry stays the last one on record.
   - **T1 with >3 implementation steps** → a soft-escalation candidate. Autonomous: escalate to T2, note it in the report, and produce a real `tasks.md`. Gated: warn first and let the user re-evaluate the tier.
   - **T2** → the full procedure below.
1. **Identify the active spec dir**, and verify `plan.md` exists and was approved.
2. **Read** the constitution, `spec.md`, `plan.md`, `validation.md`.
3. **Write `tasks.md`** under `type: Tasks` frontmatter (same shape as `plan.md`'s, `status: draft`, plus a `sources` entry pointing at the approved `plan.md` the tasks derive from), with:
   - **Phases** grouping the work — scaffold, author, wire up, reconcile derived copies, validate.
   - **Numbered tasks** within each phase, as checkboxes.
   - **`[P]` parallel markers**, only where tasks touch disjoint files and share no mutable state. Two tasks editing the same manifest are not `[P]`.
   - **Per-task fields:** Files (exact paths), Depends on, Verification (a specific, checkable command or observation), Constitution check.

   Cite the `plan` source with a `[^plan]` footnote where the task list states what it derives from — an uncited `sources` entry warns in validation.
4. **Order by dependency** — scaffold before content, content before wiring, wiring before reconciliation, reconciliation before validation.
5. **Add the final gate tasks:** `TF. Final verify` (run the repo's verify gate) and `TV. Validation pass` (walk `validation.md`).
6. **Set `sdd_phase: tasking`** in `spec.md`, and append `* **Update**: Task list drafted [NNN](/NNN-short-kebab-name/tasks.md)` to `specs/log.md`.

## Checkpoint 3

Print the task list with phases, dependencies, and `[P]` markers visible, highlighting any `[P]` group worth a second look.

**Autonomous** — record the attestation and continue into analyze:

```yaml
verified:
  - { by: claude-code/<model>, at: '<now>', checkpoint: 3,
      basis: '<N> tasks in dependency order; <M> [P] groups verified disjoint; every task has a checkable verification' }
```

Only claim `[P]` groups are disjoint if you checked their file lists for overlap. Two tasks touching one manifest are not parallel, and on an autonomous run that mistake surfaces as a corrupted file rather than a review comment.

**Gated** — stop and wait, then record the human entry:

```yaml
verified:
  - { by: human:<id>, at: '<now>', checkpoint: 3, approval: '<their exact words>' }
```
