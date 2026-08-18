---
type: Tasks
title: Make the shipped plugin installable, and check that it is — tasks
description: 9 tasks, 3 parallel — manifest, then a real install, then the checks and the prose.
resource: specs/017-plugin-marketplace/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T10:11:24+00:00' }
sources:
  - id: plan
    resource: /017-plugin-marketplace/plan.md
    title: The approved plan these tasks derive from
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T10:11:24+00:00', checkpoint: 3,
      basis: 'Ordering puts the real install (T2) immediately after the manifest and before any prose, because the commands the documentation will quote have to be the commands that were run — this spec exists because a documented step was never executed. T2 mutates local Claude Code configuration, so it carries its own cleanup and is the one task that cannot be verified by the gate.' }
---

Derived from the approved plan.[^plan]

`[P]` marks tasks that touch disjoint files and share no mutable state.

**Why this order.** The whole spec exists because a documented instruction was never run. So the
install is task 2, before a word of prose is written, and every command that reaches the
documentation is copied from a terminal rather than composed.

# Phase 1 — The manifest, and proof it works

- [x] **T1.** Add `.claude-plugin/marketplace.json` at the repository root: `name`, `owner`,
      `description`, and one `plugins[]` entry with `source: ./plugin`, no `version`.
  - **Files:** `.claude-plugin/marketplace.json`
  - **Depends on:** —
  - **Verification:** `claude plugin validate . --strict` passes.
  - **Constitution check:** shipped product, not `.claude/` tooling. The names differ by a hyphen,
    which is why T8 puts the distinction in writing.

- [x] **T2.** Actually install it. `claude plugin marketplace add` against this checkout, then
      `claude plugin install semantiql@semantiql`, then confirm the skill and the MCP server both
      arrived. Capture every command and its output; remove the marketplace afterwards so the
      machine is left as it was found.
  - **Files:** — (local Claude Code configuration, reverted)
  - **Depends on:** T1
  - **Verification:** the install succeeds and `claude plugin list` shows `semantiql`. This is the
    one task the gate cannot check, and the only one that proves FR-2 and FR-3.
  - **Constitution check:** ≤15-minute setup — if this takes two commands, A1 can promise two.

# Phase 2 — The checks

- [x] **T3.** Add the gate step: `claude plugin validate` `--strict` over the marketplace and the
      plugin, guarded on `command -v claude`, **printing** its skip reason.
  - **Files:** `scripts/verify.sh`
  - **Depends on:** T1
  - **Verification:** run the gate twice — normally, and with `claude` masked off `PATH` — and see
    a green pass with a visible skip line in the second.
  - **Constitution check:** CI stays secret-free and needs no Claude Code. A silent skip would be
    the invisible-failure pattern this project refuses.

- [x] **T4. [P]** Tests: the manifest parses, names `semantiql`, its `source` resolves to a
      directory containing a matching `plugin.json`, and the two descriptions agree.
  - **Files:** `tests/interfaces/test_plugin.py`
  - **Depends on:** T1
  - **Verification:** `uv run pytest tests/interfaces/test_plugin.py -q`
  - **Constitution check:** — . The pointer check is the part `claude plugin validate` cannot do,
    and therefore the part worth writing.

# Phase 3 — The prose that was wrong

- [x] **T5.** Rewrite A1's install line as the two commands, with output as captured in T2.
  - **Files:** `docs/03-setup-workflow.md`
  - **Depends on:** T2
  - **Verification:** no sentence remains that asks the reader to "add the plugin directory".
  - **Constitution check:** **trust-boundary artifact** — `docs/NN-*.md`. Stated explicitly, as
    required, rather than treated as a routine edit.

- [x] **T6. [P]** Same for the plugin's own README, plus a short paragraph on what a marketplace is.
  - **Files:** `plugin/README.md`
  - **Depends on:** T2
  - **Verification:** `grep -rn "add the plugin from that checkout" plugin/ docs/` returns nothing.
  - **Constitution check:** — .

- [x] **T7. [P]** Code map: add the new top-level directory, and **fix the stale claim** that
      `.mcp.json` uses \${CLAUDE_PLUGIN_ROOT} when it uses \${SEMANTIQL_HOME}.
  - **Files:** `docs/07-code-map.md`
  - **Depends on:** T1
  - **Verification:** the `plugin/` entry matches what `plugin/.mcp.json` actually contains.
  - **Constitution check:** trust-boundary artifact. This is the recorded addition beyond the
    spec — the map was teaching the mistake spec 014 was spent correcting.

- [x] **T8.** Brief: the shipped-product sentence gains `.claude-plugin/`, and the install commands
      go where an agent will find them instead of reinventing the vague instruction.
  - **Files:** `AGENTS.md`
  - **Depends on:** T5
  - **Verification:** the sentence names all three shipped directories and still contrasts `.claude/`.
  - **Constitution check:** `AGENTS.md` is the single agent brief and `CLAUDE.md` symlinks to it —
    one edit, not two.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh` with Postgres up and with it down, and once more
      with `claude` off `PATH`, so all three skip paths are proven rather than assumed.
- [x] **TV. Validation pass** — walk `validation.md`, ticking each AC and naming what proves it.

[^plan]: The impact map approved at gate 2.
