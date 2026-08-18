---
type: Tasks
title: The skill must teach commands that actually run — tasks
description: 5 tasks, 1 parallel — write the test first, because the bug is a passing-looking transcript.
resource: specs/018-skill-runnable-commands/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T12:03:05+00:00' }
sources:
  - id: plan
    resource: /018-skill-runnable-commands/plan.md
    title: The approved plan these tasks derive from
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T12:03:05+00:00', checkpoint: 3,
      basis: 'The test comes before the fix here, which is not this repository default. Justified: the defect is invisible in review — the skill reads perfectly — and both observed runs recovered from it, so the only way to know the check works is to watch it fail against the current file first.' }
---

Derived from the approved plan.[^plan]

**Why the test comes first.** Every other spec here writes the fix and then the test. This one
inverts it, because the defect survived review twice: the skill reads correctly, and a capable model
works around it. A check that has not been seen failing against the current file is not known to
detect anything.

# Phase 1 — The check

- [x] **T1.** Write both drift tests and **watch them fail** against the skill as it stands.
  - **Files:** `tests/interfaces/test_plugin.py`
  - **Depends on:** —
  - **Verification:** `uv run pytest tests/interfaces/test_plugin.py -q` reports the bare-command
    test failing and naming the offending lines. A test that passes here is testing nothing.
  - **Constitution check:** — .

# Phase 2 — The fix

- [x] **T2.** Add the invocation preamble to the discovery loop: the two forms, when each applies,
      what to do when `$SEMANTIQL_HOME` is unset, and why the invocation is written out each time
      rather than assigned to a variable.
  - **Files:** `plugin/skills/semantiql/SKILL.md`
  - **Depends on:** T1
  - **Verification:** the preamble names both forms and the unset case.
  - **Constitution check:** **trust-boundary artifact.** N6 untouched — this is invocation, not
    meaning, and the two non-negotiable limits keep their existing tests.

- [x] **T3.** Rewrite the three command lines, and drop the hard-coded `--datasource postgres` from
      the `inspect` example.
  - **Files:** `plugin/skills/semantiql/SKILL.md`
  - **Depends on:** T2
  - **Verification:** T1's tests now pass, and each rewritten command was **run** against the
    ambiguous fixture rather than assumed to work.
  - **Constitution check:** — .

# Phase 3 — Reconcile the record

- [x] **T4. [P]** Spec 016's manual step 4 is recorded as **not run**. It has now been run, twice,
      and passed. Correct that entry and state what each harness could and could not show.
  - **Files:** `specs/016-schema-discovery/validation.md`
  - **Depends on:** T3
  - **Verification:** the entry says who ran it, on what fixture, and that the interactive run asked
    both questions before writing any YAML.
  - **Constitution check:** never record a check as passed that did not pass — and the headless run's
    limitation is stated rather than smoothed over.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh`, and once with `claude` off `PATH` so 017's skip
      step is still honest.
- [x] **TV. Validation pass** — walk `validation.md`, ticking each AC and naming what proves it.

[^plan]: The impact map approved at gate 2.
