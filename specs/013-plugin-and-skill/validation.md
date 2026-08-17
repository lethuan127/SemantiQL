---
type: Validation
title: Plugin and skill — validation
description: Acceptance criteria traced to FR-1..FR-10, separating what the gate proved from the one thing only installing the plugin can confirm.
resource: specs/013-plugin-and-skill/validation.md
tags: [sdd, validation, plugin]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T02:55:00+07:00' }
status: stable
---

# Acceptance criteria

- **AC-1** (FR-1) — `plugin/` carries a manifest at `.claude-plugin/plugin.json`, a `.mcp.json`,
  and a skill at `skills/semantiql/SKILL.md`, with component directories at the plugin root.
- **AC-2** (FR-2) — the server definition launches `semantiql serve`, and **installing it actually
  registers the server**.
- **AC-3** (FR-3) — no absolute path appears anywhere under `plugin/`; the checkout is located
  through `${CLAUDE_PLUGIN_ROOT}`.
- **AC-4** (FR-4) — the skill tells Claude to call `describe_model` first, states the supported
  subset, explains refusal-repair, and says to stop at a missing definition.
- **AC-5** (FR-5) — the server's `INSTRUCTIONS` are unchanged, so the `--print-config` route is not
  degraded.
- **AC-6** (FR-6) — a test fails if the skill's grains differ from `_GRAINS`, or if a construct it
  calls refused is accepted.
- **AC-7** (FR-7) — manifest and server definition are valid JSON with required fields, checked by
  the gate.
- **AC-8** (FR-8) — the plugin contains no model path and no credential; `SEMANTIQL_MODEL` supplies
  the model.
- **AC-9** (FR-9) — `docs/02-architecture.md` names the three components and where each lives.
- **AC-10** (FR-10) — `docs/03` and `docs/10` lead with the plugin and keep the hand-pasted route.

# Results — walked 2026-08-18

| AC | Outcome | Evidence |
|---|---|---|
| AC-1 | met | `test_the_plugin_has_the_three_files_a_client_looks_for`, plus a test that `skills/` is **not** under `.claude-plugin/`, where it would silently not load |
| AC-2 | **partly met — see below** | the definition is asserted to launch `semantiql serve`; the install itself is unverified |
| AC-3 | met | `test_no_path_inside_the_plugin_comes_from_anyones_machine` scans every `.json` and `.md` under `plugin/` |
| AC-4 | met | asserted on the skill's text, including `**Stop.**` and "do not define it yourself" |
| AC-5 | met | `git diff` shows `server.py` unchanged |
| AC-6 | met | grains parsed from `SKILL.md` and compared with `_GRAINS`; 5 grains validated individually; 6 refused constructs each run through `validate` |
| AC-7 | met | both files parse; name, version, description, license, repository asserted |
| AC-8 | met | `test_the_plugin_ships_no_model_path_or_credential`; three CLI tests cover flag / env / default |
| AC-9 | met | three components, with the file for each; the diagram is generated so its borders align |
| AC-10 | met | `docs/03` Flow A step 1 and step 5; `docs/10` Step 7 has both routes |

**Non-functional:** gate green both ways. No new runtime dependency — the plugin is JSON and
markdown.

## What the gate cannot prove

**AC-2 is the honest gap, and it is recorded rather than rounded up.** This repository cannot
install a plugin into a Claude client, so *"installing it registers the server"* is asserted only as
far as "the definition names the right command". Two things behind it remain unconfirmed:

- **OQ-1 — does `${CLAUDE_PLUGIN_ROOT}/..` resolve inside `.mcp.json` args?** The variable is
  documented for MCP server arguments; the `/..` suffix is this plan's own construction. If a client
  normalises or rejects it, the fallback is a `SEMANTIQL_HOME` variable beside `SEMANTIQL_MODEL`.
- **OQ-2 — does a plugin-launched server inherit the user's environment?** `SEMANTIQL_MODEL` depends
  on it. The hedge, if not, is an `env` block in the manifest.

**The manual confirmation**, once, by a human with a Claude Code client:

1. Install the plugin from `plugin/` in a checkout.
2. `export SEMANTIQL_MODEL=<absolute path to a model>` before starting the client.
3. Confirm a **semantiql** server appears with `describe_model` and `query`, both read-only.
4. Ask a question that the model answers, and one it does not — the second should come back as an
   explanation, not an error.
5. If step 3 fails, check OQ-1 first: substitute an absolute `--directory` by hand and see whether
   the server starts. That isolates path resolution from everything else.

## Carried forward

- **Claude Desktop has no one-click install.** Different packaging format; `--print-config` remains
  the supported route and is documented as such rather than deprecated.
- **The skill has no discovery half yet.** Driving `semantiql init` conversationally is what spec
  014 is for; this skill covers asking, not modelling.
