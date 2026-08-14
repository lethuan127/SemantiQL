---
type: Tasks
title: <spec title> — tasks
description: <N> tasks, <M> parallel, ordered scaffold before wiring.
resource: specs/NNN-short-kebab-name/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-01-01T09:00:00+07:00' }
sources:
  - id: plan
    resource: /NNN-short-kebab-name/plan.md
    title: The approved plan these tasks derive from
status: draft
---

Derived from the approved plan.[^plan]

`[P]` marks tasks that touch disjoint files and share no mutable state. Two tasks editing the same manifest
are **not** `[P]`. Order: scaffold → content → wiring → reconcile derived copies → validate.

# Phase 1 — <scaffold>

- [ ] **T1.** <task>
  - **Files:** `<exact path>`
  - **Depends on:** <task id, or —>
  - **Verification:** <a specific, checkable command or observation>
  - **Constitution check:** <which invariant this must preserve, or —>

- [ ] **T2. [P]** <task>
  - **Files:** `<exact path>`
  - **Depends on:** T1
  - **Verification:** <command or observation>
  - **Constitution check:** <invariant, or —>

# Phase 2 — <wire up>

- [ ] **T3.** <task>
  - **Files:** `<exact path>`
  - **Depends on:** T2
  - **Verification:** <command or observation>
  - **Constitution check:** <invariant, or —>

# Final gates

- [ ] **TF. Final verify** — run the repo's verify gate; report output verbatim.
- [ ] **TV. Validation pass** — walk `validation.md`, ticking each AC and naming what proves it.

[^plan]: The impact map approved at gate 2.
