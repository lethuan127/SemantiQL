---
type: Plan
title: Plugin and skill — plan
description: A plugin/ directory carrying a manifest, an MCP server definition using CLAUDE_PLUGIN_ROOT, and a skill — plus a SEMANTIQL_MODEL fallback so no per-user path is committed, and a test that pins the skill to the validator.
resource: specs/013-plugin-and-skill/plan.md
tags: [sdd, plan, plugin, skill]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T02:25:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time — N1, N2, N6, trust boundaries
    last_modified: 2026-08-18
  - id: clarifications
    resource: clarifications.md
    title: The 6 decisions this plan implements
    last_modified: 2026-08-18
  - id: structure
    resource: plan.md
    title: Claude Code plugin structure reference, read at clarify time
    last_modified: 2026-08-18
  - id: server
    resource: ../../src/semantiql/server.py
    title: INSTRUCTIONS and the two tool descriptions the skill must agree with
    last_modified: 2026-08-18
  - id: cli
    resource: ../../src/semantiql/cli.py
    title: EXAMPLE_MODEL, the -m default, and the serve verb
    last_modified: 2026-08-18
  - id: validate
    resource: ../../src/semantiql/engine/validate.py
    title: _GRAINS at 161 and the refused-construct set the skill is pinned to
    last_modified: 2026-08-18
  - id: architecture
    resource: ../../docs/02-architecture.md
    title: The four-layer diagram whose top box this replaces
    last_modified: 2026-08-15
  - id: setup-workflow
    resource: ../../docs/03-setup-workflow.md
    title: Flow A step 1 and step 5, which the plugin shortens
    last_modified: 2026-08-18
  - id: adopting
    resource: ../../docs/10-adopting-semantiql.md
    title: Step 7, which documents the hand-pasted route
    last_modified: 2026-08-18
  - id: code-map
    resource: ../../docs/07-code-map.md
    title: The outside-src tree the plugin directory joins
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T02:28:00+07:00', checkpoint: 2,
      basis: 'map derived from 8 file reads plus the plugin-structure reference; all 6 existing-file rows footnoted. Q2 drove a code change rather than a config trick, because argument interpolation inside a JSON array is not something this repo can test. AD-3 states plainly what cannot be verified here — plugin installation itself — and what is verified instead' }
status: stable
---

# Constitution check

**N1 / N2** — nothing about what runs changes. The tool surface stays two read-only calls, and a
refusal keeps its reason; this changes only how the server is installed and how Claude is taught
to use it.[^constitution]

**N6 — the tier separation is the live risk here.** A skill is instructions Claude reads, and it
would be easy to write one that says "if a metric is missing, add it". That would put the meaning
tier under automatic change, which N6 forbids outright. So the skill explicitly tells Claude to
report a missing definition and stop.[^constitution]

**Local only.** Packaging, not hosting.[^constitution]

**Trust-boundary artifacts** in scope, all planned: `docs/02-architecture.md`,
`docs/03-setup-workflow.md`, `docs/07-code-map.md`. The constitution is not touched. **A new
top-level directory** (`plugin/`) is added, which the constitution's taxonomy will eventually want
a row for — proposed in the report rather than edited unilaterally.

# Approach

**`plugin/` is the whole shipped artifact**, separate from `.claude/`, which holds this repo's own
development tooling and is not product.[^clarifications]

```
plugin/
  .claude-plugin/plugin.json      manifest: name, version, description
  .mcp.json                       how to launch the server
  skills/semantiql/SKILL.md       how to use it
  README.md                       what this is and how to install it
```

**The server definition uses the plugin's own root.** `${CLAUDE_PLUGIN_ROOT}` is the documented
way to reference intra-plugin paths, and because the plugin ships inside this repository,
`${CLAUDE_PLUGIN_ROOT}/..` is the checkout — precisely what `uv run --directory`
needs.[^structure]

**The model path is never committed.** `serve` gains a `SEMANTIQL_MODEL` fallback, so the plugin
ships no per-user value and the user sets one environment variable.[^cli] [^clarifications]

**`INSTRUCTIONS` stays.** The skill enriches; it does not replace. Anyone on the
`--print-config` route has the server without the skill, and gutting the string would quietly
degrade them.[^server]

**The skill is pinned to the engine by a test.** Prose that teaches a grain the validator refuses
is a silent failure, so the grains named in `SKILL.md` are asserted equal to `_GRAINS`, and each
construct the skill calls refused is run through `validate`.[^validate]

# Architecture decisions

**AD-1 — the skill tells Claude to stop at a missing definition, in as many words.** The N6 risk
is not hypothetical: the helpful behaviour is to invent `profit_margin` when asked, and the
helpful behaviour is the one that puts an unsanctioned number in a board deck. The skill says
report it and stop, and says why.

**AD-2 — the drift test parses the skill rather than duplicating its rules.** A test that restated
the grains would just be a third copy to drift. It reads the list out of `SKILL.md` and compares
with the validator's set, so the skill remains the single statement and the test is the
comparison.

**AD-3 — what this change cannot verify, stated rather than implied.** This repository cannot
install a plugin into a Claude client and confirm the server starts, so **FR-1 and FR-2 are not
provable by the gate**. What is provable and will be tested: the manifest and server definition are
valid JSON with the required fields; no absolute path appears anywhere in the plugin; the
`${CLAUDE_PLUGIN_ROOT}` reference is present; `SKILL.md` has the frontmatter a skill requires; and
the `SEMANTIQL_MODEL` fallback works. The install itself needs one manual confirmation, recorded
in `validation.md` as a manual step rather than claimed as passing.

**AD-4 — `docs/02-architecture.md` gains the three components above the four layers.** The
diagram's top box is currently *"AI agent (Claude via MCP, or any LLM)"*, which treats what Claude
knows as outside the system. It is a component with a home in the repo, and after this change it
has a file.[^architecture]

# Repository Impact Map

## Files to add

- `plugin/.claude-plugin/plugin.json` — name `semantiql`, version, description, license,
  repository, keywords.
- `plugin/.mcp.json` — one server, `uv run --directory ${CLAUDE_PLUGIN_ROOT}/.. semantiql serve`.
- `plugin/skills/semantiql/SKILL.md` — frontmatter plus the procedural knowledge: call
  `describe_model` first, the supported subset, refusal-repair, and AD-1's stop-at-missing rule.
- `plugin/README.md` — what the plugin is, how to install it, and the one environment variable.
- `tests/test_plugin.py` — the checks AD-3 lists, plus the skill-versus-validator drift test.

## Files to modify

- `src/semantiql/cli.py` — `-m` falls back to `SEMANTIQL_MODEL` before the bundled example, so the
  plugin needs no committed path.[^cli]
- `docs/02-architecture.md` — AD-4, the three components. **Trust-boundary artifact.**[^architecture]
- `docs/03-setup-workflow.md` — Flow A becomes install-the-plugin; the hand-pasted route stays as
  the Desktop path. **Trust-boundary artifact.**[^setup-workflow]
- `docs/07-code-map.md` — the outside-`src/` tree gains `plugin/`. **Trust-boundary
  artifact.**[^code-map]
- `docs/10-adopting-semantiql.md` — Step 7 leads with the plugin and keeps `--print-config` for
  Desktop.[^adopting]
- `README.md` — the Claude section mentions the plugin.
- `AGENTS.md` — the layout note gains `plugin/`, and the N6 warning about skills that would edit
  the model. `CLAUDE.md` is a symlink and is **not** a second edit.

## Files not touched, but adjacent

- `src/semantiql/server.py` — **no change.** `INSTRUCTIONS` stays as the baseline (FR-5).
- `src/semantiql/engine/` — no change. Nothing about packaging reaches the engine.
- `.claude/skills/` — untouched, and deliberately distinct from `plugin/skills/`.

# Open research questions

- **OQ-1 — does `${CLAUDE_PLUGIN_ROOT}/..` resolve as expected inside `.mcp.json` args?** The
  reference documents the variable for MCP server command arguments; the `/..` suffix is this
  plan's own construction. If a client normalises or rejects it, the fallback is a `SEMANTIQL_HOME`
  environment variable alongside `SEMANTIQL_MODEL`. Confirmed only by installing, so it is a manual
  validation step.
- **OQ-2 — does a plugin-launched server inherit the user's environment?** `SEMANTIQL_MODEL` depends
  on it. The manifest can also carry an `env` block, which is the hedge if inheritance is not
  reliable.
- **OQ-3 — should the skill live in the plugin only, or also be usable standalone?** Shipping it
  only inside `plugin/` keeps one copy. Someone wanting the skill without the server would have to
  copy it, which seems right — the skill's instructions are useless without the tools.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N6, and the trust-boundary list naming `docs/NN-*.md`.
[^clarifications]: `clarifications.md` — Q1..Q6; Q2 is the one that drove a code change.
[^structure]: Claude Code plugin structure reference — manifest location, component auto-discovery, and `${CLAUDE_PLUGIN_ROOT}`.
[^server]: `src/semantiql/server.py` — `INSTRUCTIONS` and the tool descriptions.
[^cli]: `src/semantiql/cli.py` — `EXAMPLE_MODEL`, the `-m` default, and the `serve` verb.
[^validate]: `src/semantiql/engine/validate.py` — `_GRAINS` at line 161 and the refused-construct set.
[^architecture]: `docs/02-architecture.md` — the four-layer diagram and its top box.
[^setup-workflow]: `docs/03-setup-workflow.md` — Flow A and Flow B.
[^adopting]: `docs/10-adopting-semantiql.md` — Step 7.
[^code-map]: `docs/07-code-map.md` — the outside-`src/` tree.
