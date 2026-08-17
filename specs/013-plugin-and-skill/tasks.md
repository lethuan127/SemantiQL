---
type: Tasks
title: Plugin and skill — tasks
description: 9 tasks plus two gate tasks — the model fallback, the plugin's three files, the drift test, then the architecture doc and the workflow.
resource: specs/013-plugin-and-skill/tasks.md
tags: [sdd, tasks, plugin]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T02:32:00+07:00' }
sources:
  - id: plan
    resource: plan.md
    title: The approved plan, AD-1..AD-4, the impact map and OQ-1..OQ-3
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T02:34:00+07:00', checkpoint: 3,
      basis: '11 tasks in dependency order; one [P] group checked disjoint. T1 comes first because the plugin cannot ship a per-user model path and the fallback is what removes the need. T4 is the drift test and is the only automated check of FR-6. T9 records what the gate cannot prove — plugin installation — as a manual step rather than leaving it implied' }
status: stable
---

11 tasks, derived from the impact map.[^plan] The gate cannot install a plugin, so T9 records the
one manual confirmation rather than letting it look automated.

## ✅ T1. `SEMANTIQL_MODEL` fallback

- **Files:** `src/semantiql/cli.py`, `tests/test_cli.py`
- **Do:** `-m` falls back to `$SEMANTIQL_MODEL`, then to the bundled example. This is what lets
  the plugin ship no per-user path (Q2).
- **Verification:** a test for each of the three cases — flag given, env set, neither.

## ✅ T2. The manifest and server definition

- **Files:** `plugin/.claude-plugin/plugin.json`, `plugin/.mcp.json` (both new)
- **Depends on:** T1
- **Do:** manifest with name `semantiql`, version, description, license, repository. Server
  definition launching `uv run --directory ${CLAUDE_PLUGIN_ROOT}/.. semantiql serve`.
  **No absolute paths anywhere.**
- **Verification:** both parse as JSON; T5 asserts the required fields and path portability.

## ✅ T3. The skill

- **Files:** `plugin/skills/semantiql/SKILL.md` (new)
- **Depends on:** T2
- **Do:** frontmatter with `name` and a `description` saying what *and when*. Body: call
  `describe_model` first; the supported subset with a worked example; refusal-repair; and AD-1 —
  **report a missing definition and stop**, with the reason (N6).
- **Verification:** T4 and T5.

## ✅ T4. The drift test

- **Files:** `tests/test_plugin.py` (new)
- **Depends on:** T3
- **Do:** FR-6 — parse the grains named in `SKILL.md` and assert set equality with `_GRAINS`; run
  each construct the skill calls refused through `validate` and assert it is refused. Parse rather
  than restate, so the skill stays the single statement (AD-2).
- **Verification:** the test fails if a grain is added to the skill and not the engine.

## ✅ T5. `[P]` Plugin conformance test

- **Files:** `tests/test_plugin.py`
- **Depends on:** T2
- **Do:** manifest and server definition are valid JSON with required fields; `SKILL.md` has
  `name` and `description`; **no absolute path anywhere under `plugin/`**; the server definition
  references `${CLAUDE_PLUGIN_ROOT}`.
- **Verification:** green, and fails if a path is hardcoded.

## ✅ T6. `[P]` Plugin README

- **Files:** `plugin/README.md` (new)
- **Depends on:** T2
- **Do:** what it is, how to install from a checkout, the one environment variable, and that the
  `--print-config` route remains for Claude Desktop.
- **Verification:** a reader can install it without opening another file.

> **`[P]` group — T5 and T6 are disjoint:** {`tests/test_plugin.py`} · {`plugin/README.md`}. T4
> also writes the test file, so T5 follows T4 rather than running beside it.

## ✅ T7. The architecture doc

- **Files:** `docs/02-architecture.md`
- **Depends on:** T3
- **Do:** AD-4 — replace the opaque agent box with the three components and where each lives.
  **Trust-boundary artifact**, and the one the user asked for explicitly.
- **Verification:** a reader can name all three components and find each one's file.

## ✅ T8. The user workflow

- **Files:** `docs/03-setup-workflow.md`, `docs/10-adopting-semantiql.md`
- **Depends on:** T7
- **Do:** Flow A leads with installing the plugin; `--print-config` stays as the Desktop path.
  `docs/10` Step 7 the same. **`03` is trust-boundary.**
- **Verification:** neither document describes a step that no longer exists.

## ✅ T9. Manual-install record

- **Files:** `specs/013-plugin-and-skill/validation.md`
- **Depends on:** T5
- **Do:** AD-3 — write down that FR-1 and FR-2 are **not** provable by the gate, what is checked
  instead, and the exact manual steps that would confirm the install. Do not mark them met.
- **Verification:** validation.md distinguishes verified from unverified.

## ✅ T10. Code map, README, agent brief

- **Files:** `docs/07-code-map.md`, `README.md`, `AGENTS.md`
- **Depends on:** T8
- **Do:** the outside-`src/` tree gains `plugin/`; the README's Claude section mentions it;
  `AGENTS.md` gains the layout note and the N6 warning about skills that would edit the model.
  **Do not edit `CLAUDE.md`** — symlink. **`07` is trust-boundary.**
- **Verification:** `git status` shows `AGENTS.md` changed and `CLAUDE.md` not.

## ✅ TF. Final verify

- **Depends on:** T1–T10
- **Do:** `./scripts/verify.sh`, with and without a Postgres reachable.
- **Verification:** green both ways.

## ✅ TV. Validation pass

- **Depends on:** TF
- **Do:** walk every AC, keeping T9's distinction: what the gate proved, and what needs a human to
  install the plugin once.

[^plan]: `plan.md` — the impact map, AD-1..AD-4, and OQ-1..OQ-3.
