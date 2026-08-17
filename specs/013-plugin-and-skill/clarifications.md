---
type: Clarifications
title: Plugin and skill — clarifications
description: 6 ambiguities resolved before planning, including the one that decides whether the plugin can find the Python environment at all.
resource: specs/013-plugin-and-skill/clarifications.md
tags: [sdd, clarifications, plugin]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T02:18:00+07:00' }
sources:
  - id: structure
    resource: specs/013-plugin-and-skill/clarifications.md
    title: Claude Code plugin structure reference, read at clarify time — manifest location, auto-discovery, CLAUDE_PLUGIN_ROOT
    last_modified: 2026-08-18
  - id: repo-skills
    resource: ../../.claude/skills
    title: Where this repo keeps its own agent tooling — okf and sdd, which are not shipped product
    last_modified: 2026-08-18
  - id: server
    resource: ../../src/semantiql/server.py
    title: INSTRUCTIONS, which the skill enriches rather than replaces
    last_modified: 2026-08-18
  - id: cli
    resource: ../../src/semantiql/cli.py
    title: The -m default, and the flags a plugin cannot pass by hand
    last_modified: 2026-08-18
status: stable
---

Decided **by the agent**, autonomously. Q2 is the one that decides whether the plugin works at
all, and it drove a small code change rather than a clever config trick.

## Q1: Where does the plugin live in the repo?

- (a) The repository root becomes the plugin
- (b) A dedicated `plugin/` directory
- (c) Inside `.claude/`

**Chosen: (b).** (c) is wrong on inspection: `.claude/skills/` already holds this repo's *own*
development tooling — `okf` and `sdd`, which exist to build SemantiQL and are not part of
it.[^repo-skills] Putting shipped product in the same tree would leave nobody able to tell which
is which. (a) would scatter `.claude-plugin/`, `.mcp.json` and `skills/` across a root that
already carries eleven top-level entries, and would make the plugin's boundary invisible.
`plugin/` is one directory whose contents are entirely the shipped artifact.

## Q2: How does the plugin's MCP server find a Python environment and a model?

- (a) `uvx semantiql serve` — resolve from PyPI
- (b) `uv run --directory <repo>` with the model path interpolated into the args
- (c) `uv run --directory ${CLAUDE_PLUGIN_ROOT}/..`, with the model from an environment variable

**Chosen: (c), and it required a code change rather than a config trick.** (a) is ruled out by
fact: the published package is behind this repository and predates both `doctor` and Postgres, so
`uvx semantiql serve` would install a version with no `serve` verb. (b) fails because the model
path is inherently per-user — it cannot be committed into a file the plugin ships.

`${CLAUDE_PLUGIN_ROOT}` is the documented way to reference paths inside a plugin, and because the
plugin ships *inside* this repository, `${CLAUDE_PLUGIN_ROOT}/..` is the checkout — which is
exactly what `uv run --directory` needs.[^structure]

For the model, the honest option was not to be clever about argument interpolation. **`serve` now
reads `SEMANTIQL_MODEL` when `-m` is not given**, falling back to the bundled example as
before.[^cli] That is one small, ordinarily-testable branch in the CLI, versus relying on
variable expansion inside a JSON array that this repository cannot test. The user sets one
environment variable; the plugin ships no per-user value at all (FR-8).

## Q3: Does the skill replace the server's `instructions`?

- (a) Yes — move the text out of `server.py`
- (b) No — `instructions` stays as the baseline and the skill enriches it

**Chosen: (b), which FR-5 requires.** A client can have the server without the skill: anyone
following the `--print-config` route, which Claude Desktop still needs. Gutting `instructions`
would silently make that path worse. So the essentials stay in Python[^server] and the skill carries what a
string cannot: worked examples, the refusal-repair workflow, progressive disclosure.

The cost is deliberate duplication of a few rules in two places, which is exactly why Q4 exists.

## Q4: How is the skill kept from contradicting the engine?

- (a) Review
- (b) A test asserting the skill's stated rules against the validator

**Chosen: (b).** The rules Claude is taught — which grains exist, what is refused — are prose in
one file and enforced in another. Prose drifts; nothing today would notice a skill that taught a
sixth grain, and the symptom would be Claude confidently writing SQL the engine refuses.

So the test parses the grains named in `SKILL.md` and asserts set equality with `_GRAINS`, and
runs each construct the skill calls refused through `validate` to confirm it is. This is the same
argument as the doc-versus-code check the repo already makes elsewhere: a claim about behaviour
belongs under test.

## Q5: Claude Code plugin, or a Claude Desktop bundle?

- (a) Claude Code plugin now
- (b) A Desktop bundle now
- (c) Both

**Chosen: (a), with the hand-pasted route kept.** The two surfaces take different packaging
formats, and this repository can verify neither by installing it. What it *can* verify is that the
manifest and server definition are well-formed and path-portable. So it ships the format it can
reason about, and `--print-config` stays supported for Desktop rather than being deprecated in
favour of something untested (FR-10). Spec 013 does not claim a one-click Desktop install.

## Q6: What goes in the plugin beyond the manifest, server definition and skill?

- (a) Just those three
- (b) Plus commands, hooks and agents

**Chosen: (a).** Auto-discovery means each extra component type is additive later at no cost, and
none of them is needed to test the shape. A `/semantiql-doctor` command is an obvious later
addition; adding it now would mean shipping surface with no requirement behind it.

[^structure]: Claude Code plugin structure reference, read at clarify time — `.claude-plugin/plugin.json`, component directories at plugin root, auto-discovery, and `${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths.
[^repo-skills]: `.claude/skills/` — `okf` and `sdd`, this repository's own development tooling.
[^server]: `src/semantiql/server.py` — `INSTRUCTIONS` and the tool descriptions.
[^cli]: `src/semantiql/cli.py` — the `-m` default and the `serve` verb.
