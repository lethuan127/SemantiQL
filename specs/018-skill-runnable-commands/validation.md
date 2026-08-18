---
type: Validation
title: The skill must teach commands that actually run — validation
description: Acceptance criteria traced to FR-1..FR-6.
resource: specs/018-skill-runnable-commands/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T12:08:09+00:00' }
status: stable
---

# Acceptance criteria

- [x] **AC-1** (FR-1): Every command in the skill's fenced blocks runs given a checkout, `uv sync`,
      and `SEMANTIQL_HOME`.
  - **Proven by:** each one **executed** against the ambiguous fixture, not reviewed —
    `semantiql --help` (exit 0), `inspect --json`, `inspect --table order_lines --json`, and
    `doctor -m shop_model.yml`, which printed `✓ 2 dimensions, 8 measures and 1 metric all resolve`.
    Running them is what caught the two defects below; reading them would not have.
- [x] **AC-2** (FR-2): The skill states both invocations and when each applies.
  - **Proven by:** the "First, work out how to run the CLI" section, and
    `test_the_skill_says_how_to_resolve_the_invocation`.
- [x] **AC-3** (FR-3): The skill says to **ask** when `$SEMANTIQL_HOME` is unset.
  - **Proven by:** *"Ask where the SemantiQL checkout is; do not guess at a path or go hunting through
    the filesystem."* Consistent with the project's refusal habit: an unknown value is asked for, not
    inferred.
- [x] **AC-4** (FR-4): A test fails on a bare `semantiql <verb>` line.
  - **Proven by:** `test_the_skill_never_teaches_a_bare_semantiql_command`. **Watched failing first**
    against the unmodified skill, where it named all three offending lines; then
    **mutation-checked** by reintroducing the bare `doctor` line, which failed the suite again, and
    restoring it, which returned it to green. A check never seen failing is not known to detect
    anything.
- [x] **AC-5** (FR-5): A test asserts every verb the skill names is one the CLI dispatches.
  - **Proven by:** `test_every_verb_the_skill_names_is_a_verb_the_cli_dispatches`, reading the verb
    set out of `cli.py` rather than restating it, so there is no third copy to drift.
- [x] **AC-6** (FR-6): The skill warns that a shell variable does not persist between tool calls.
  - **Proven by:** *"Each Bash call is its own shell, so assigning it to a variable once looks tidy
    and then silently expands to nothing on the next call."* Asserted by
    `test_the_skill_says_how_to_resolve_the_invocation`. Worth stating because the failure presents
    as a broken CLI rather than a broken variable.

# Two defects this spec introduced and then removed

Recorded because they are the argument for `tasks.md`'s ordering, and because both are the very
defect this spec exists to fix, reappearing inside the fix.

- [x] **`semantiql --version` does not exist.** The probe written to detect broken commands was a
      broken command. `--help` exits 0.
      `test_the_probe_command_is_one_the_cli_accepts` now checks the probe against the real parser.
- [x] **`uv run --directory` breaks every relative path.** It *moves* into the checkout, so
      `--database ./shop.duckdb` resolved against SemantiQL's own tree and reported
      `database does not exist` for a file that did. `uv run --project` discovers without moving.
      Measured both ways; `test_the_skill_uses_uv_project_not_uv_directory` pins it.

# Non-functional acceptance

- [x] The verify gate is green, and green again with `claude` off `PATH`, so spec 017's skip step is
      still honest.
- [x] **N6 untouched.** The two non-negotiable limits and their tests are unchanged; this change
      concerns invocation, never meaning.
- [x] **Trust boundary.** `plugin/skills/semantiql/SKILL.md` is on the constitution's list and the
      edit is called out as such rather than treated as a docs tidy.
- [x] **No new dependency.** `uv` was already required by every documented command.
- [x] **Spec 016's record corrected.** Its manual step 4 said "has not been run". It has now been run
      twice and passed, and the entry says what each harness could and could not show. A stale
      not-run entry understates what is verified about exactly the loop this spec repairs.

# Manual verification

1. From a directory that is **not** the checkout, with `SEMANTIQL_HOME` exported, run the skill's
   `inspect` line against a `.duckdb` file by relative path. Expect relations, and specifically **not**
   `database does not exist` — that error means `--directory` has crept back in.
2. Unset `SEMANTIQL_HOME` and ask Claude to build a model. Expect it to ask where the checkout is.
3. `uv run pytest tests/interfaces/test_plugin.py -q` — expect 36 passed.

**Steps 1 and 3 were run.** Step 2 was not: it needs a fresh interactive session with the variable
unset, and the two runs that produced this spec both had it set. What is testable — that the skill
contains the instruction — is AC-3.
