---
type: Spec
title: A plugin that installs the server and teaches Claude how to use it
description: One install instead of hand-edited JSON, and a skill carrying the procedural knowledge that a single instructions string cannot hold — making Claude a described component of the architecture rather than an opaque box.
resource: specs/013-plugin-and-skill/spec.md
tags: [sdd, spec, plugin, skill, mcp]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T02:10:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables — MCP as the Claude-facing interface, local-first, N1/N2/N6
    last_modified: 2026-08-18
  - id: spec-012
    resource: ../012-mcp-server/spec.md
    title: The server this packages, and AD-4's instructions string that this supersedes
    last_modified: 2026-08-18
  - id: server
    resource: ../../src/semantiql/server.py
    title: INSTRUCTIONS, the two tools, and --print-config's hand-pasted JSON
    last_modified: 2026-08-18
  - id: architecture
    resource: ../../docs/02-architecture.md
    title: The four-layer diagram, whose top box is an undescribed "AI agent"
    last_modified: 2026-08-15
  - id: validate
    resource: ../../src/semantiql/engine/validate.py
    title: _GRAINS and the refusal set the skill must not contradict
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T02:12:00+07:00', checkpoint: 1,
      basis: '10 FRs, each testable. FR-6 exists because the skill and the validator state the same rules in two places and nothing checked they agree. FR-5 keeps the server usable without the plugin, so the Desktop route is not silently degraded. The N6 NFR names the specific way a skill could break the invariant — telling Claude to add a missing metric' }
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** A new top-level directory that other tooling resolves against, plus edits to
`docs/NN-*.md` — including `02-architecture.md`, the diagram every other document refers back
to. More than three files.

# What

Installing SemantiQL into Claude becomes one step instead of five, and Claude arrives already
knowing how to use it.

Today, spec 012 shipped the server and `--print-config` prints a JSON block for a human to paste
into an application config file, followed by a full restart. That is the most error-prone part of
setup and the one a person cannot check by eye.

After this change the repository ships a **plugin**: a manifest, the MCP server definition, and a
**skill**. Installing it registers the server and loads the skill together.

The skill is the more important half. The server currently teaches Claude the dialect through
one `instructions` string — useful, and the wrong shape for the job. A skill is markdown in git:
it can be long, it loads progressively, it is reviewable in a pull request, and it can be
corrected without touching Python or restarting anything.

# Why

**Three components, and one of them was undocumented.** `docs/02-architecture.md` draws four
layers under a box labelled *"AI agent (Claude via MCP, or any LLM)"* — opaque, as though what
Claude knows were not part of the system.[^architecture] It is. The working system is:

| Component | Holds | Where it lives |
|---|---|---|
| **Claude + skill** | how to work: which tool to call first, what to do with a refusal | `SKILL.md`, in git |
| **Knowledge** | what the business words mean | the semantic model YAML |
| **Execution** | what may actually be run | the MCP server's two tools |

The skill is not a convenience wrapper. It is the component that decides whether Claude calls
`describe_model` before guessing, and whether it treats a refusal as something to repair or
something to apologise for. That knowledge exists today as a string literal in `server.py`, which
is the wrong home for it.[^server] Spec 012 chose it knowingly and named the move to a skill as
the follow-up.[^spec-012]

**One `instructions` string cannot carry it.** It has no room for worked examples, cannot be
split so that rarely-needed guidance stays out of the context window, and changing it means
editing Python and restarting the server. A skill has all three properties by construction.

**And the guidance can silently contradict the validator.** The rules Claude is taught — which
grains exist, what is refused — are stated in prose today and enforced in
`engine/validate.py`.[^validate] Nothing checks that the two agree, so the prose can drift into
teaching Claude to write SQL the engine refuses. That is a testable property, and this change
should establish it.

**The install step is the one a human cannot verify.** Pasting JSON with absolute paths into an
application's config directory, then restarting — `--print-config` made the content correct but
kept the ceremony. A plugin removes the ceremony.

# User stories

- **As an analyst**, I install one plugin and both the tools and the guidance arrive together —
  so I am not comparing a JSON block against a documentation page.
- **As an analyst**, I fix a misleading instruction by editing markdown and opening a pull
  request — so how Claude behaves is reviewable like everything else.
- **As Claude**, the skill tells me to call `describe_model` first and to repair a refusal rather
  than apologise — so my first answer is more often right.
- **As a maintainer**, a test fails if the skill teaches a grain the validator refuses — so the
  guidance cannot drift away from the engine.
- **As a reader of the architecture doc**, I can see that what Claude knows is a component with a
  home in the repository, not an unexplained box at the top of a diagram.

# Functional requirements

- **FR-1** — The repository ships an installable plugin: a manifest, the MCP server definition,
  and at least one skill, laid out so the components are discovered automatically.
- **FR-2** — Installing the plugin registers the SemantiQL MCP server. No hand-edited application
  config file, and no absolute path written by a human.
- **FR-3** — Every path inside the plugin is expressed relative to the plugin's own root, so it
  works wherever it is installed.
- **FR-4** — A skill carries the procedural knowledge: call `describe_model` first; write the
  supported subset; a refusal is repairable and its reason names what to fix; never invent a
  measure or estimate a number the model cannot compute.
- **FR-5** — The server keeps working **without** the plugin. Its `instructions` remain the
  baseline for a client that has the server but not the skill, so the skill enriches rather than
  replaces.
- **FR-6** — A test fails if the skill's stated rules contradict the engine: the grains it names
  must be exactly the grains `validate` accepts, and the constructs it calls refused must be
  refused.
- **FR-7** — The plugin's manifest and server definition are valid and machine-checked, so a
  malformed one fails the gate rather than at install time.
- **FR-8** — Which model and which datasource remain the user's configuration, supplied without
  editing files inside the plugin.
- **FR-9** — `docs/02-architecture.md` describes the three components and where each lives,
  replacing the opaque agent box.
- **FR-10** — The setup workflow and the adoption guide are updated so the documented path is the
  plugin, with the hand-pasted route kept for clients that need it.

# Non-functional requirements

- **N1 / N2** — the plugin changes how the server is *installed and explained*, never what it
  will run. The tool surface stays two read-only calls, and a refusal keeps its
  reason.[^constitution]
- **N6 — two learning tiers, permanently separate.** The skill is instructions Claude *reads*; it
  must not become a mechanism for Claude to edit the semantic model. A skill that told Claude to
  add a metric on request would put the meaning tier under automatic change, which N6
  forbids.[^constitution]
- **Local only** — packaging, not hosting. No auth, no remote transport.[^constitution]
- **No new runtime dependency** — a manifest, a server definition and markdown. The plugin adds
  nothing to what `pip install semantiql` pulls.

# Out of scope

- **Publishing to a marketplace or registry.** The plugin lives in this repository and installs
  from it.
- **A packaged bundle for Claude Desktop.** Desktop takes a different packaging format from Claude
  Code, and which one to produce is a question this spec deliberately leaves open — FR-5 and
  FR-10 keep the hand-pasted route working so Desktop users are not stranded meanwhile.
- **Commands, agents or hooks in the plugin.** A manifest, a server definition and a skill are
  enough to test the shape. More components are additive later.
- **`semantiql init`.** Its own spec, and it is what the discovery half of the skill will drive.
- **Anything that lets Claude write to the semantic model.** N6, and it needs its own spec.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N6; MCP as the Claude-facing interface; the local-first MCP roadmap decision.
[^spec-012]: `specs/012-mcp-server/spec.md` — the server, its two tools, and the `instructions` string this supersedes as the primary carrier of guidance.
[^server]: `src/semantiql/server.py` — `INSTRUCTIONS`, the tool descriptions, and `--print-config`.
[^architecture]: `docs/02-architecture.md` — the four-layer diagram and its undescribed top box.
[^validate]: `src/semantiql/engine/validate.py` — `_GRAINS` and the refused-construct set.
