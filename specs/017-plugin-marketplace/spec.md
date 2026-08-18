---
type: Spec
title: Make the shipped plugin installable, and check that it is
description: The plugin had no marketplace manifest, so the documented install could not be followed; a gate step now proves it stays installable.
resource: specs/017-plugin-marketplace/spec.md
tags: [sdd, spec]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T10:08:36+00:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-17
  - id: setup-workflow
    resource: ../docs/03-setup-workflow.md
    title: Flow A step A1, which told the reader to add the plugin directory
    last_modified: 2026-08-18
  - id: plugin-readme
    resource: ../plugin/README.md
    title: The plugin's own install section, carrying the same unfollowable line
    last_modified: 2026-08-17
  - id: measured
    resource: ../plugin/.claude-plugin/plugin.json
    title: The plugin manifest — present, valid, and unreachable
    last_modified: 2026-08-17
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T10:09:00+00:00', checkpoint: 1,
      basis: 'Every claim about the failure was executed, not inferred: the marketplace-add error is quoted verbatim, and plugin validate --strict was run to establish the plugin is valid and merely unreachable. The manifest schema was read from two independent working marketplaces on this machine rather than from memory. FR-8 mirrors the pg step because the constitution makes a gate that needs an optional tool a defect, not a strictness.' }
sdd_phase: shipped
sdd_tier: T2
---

**T2.** Two conditions fail: it adds a **new top-level directory** (`.claude-plugin/`), and it edits
`docs/03-setup-workflow.md`, which the constitution names a trust-boundary artifact.

# What

A builder can install the SemantiQL plugin into Claude Code by following the documented commands,
and the repository's own gate fails if that stops being true.

**Today they cannot.** Both `docs/03-setup-workflow.md` A1 and `plugin/README.md` say to "add the
plugin from that checkout's `plugin/` directory", which is not an operation Claude Code has. Run the
nearest real command and it fails:[^measured]

```
$ claude plugin marketplace add ./plugin
✘ Failed to add marketplace: Marketplace file not found at
  .../semantiql/plugin/.claude-plugin/marketplace.json
```

Claude Code installs a plugin from a **marketplace** — a directory carrying
`.claude-plugin/marketplace.json` that names each plugin and where it lives. This repository has
never had one. The plugin manifest itself is valid and passes `claude plugin validate --strict`; it
is simply unreachable.

# Why

Spec 016 made the plugin load-bearing rather than a convenience. A3 of the setup workflow now tells
the analyst to work in Claude Code so that Claude can run `semantiql inspect` and write the semantic
model with file tools. **That is the on-ramp for the whole product**, and it begins with a step that
cannot be performed.

The failure mode is the one this project is most concerned with, applied to its own documentation: a
sentence that reads as an instruction, is not actionable, and gives the reader no way to tell which
of the two it is. A builder hits it in the first five minutes of a fifteen-minute budget, has no
error message to search for — because they never got as far as a command — and concludes the plugin
does not exist.

Worse, nothing in the repository could have caught it. `tests/test_plugin.py` asserts a great deal
about the skill's *contents* and nothing about whether the plugin can be **installed**. The manifest
was valid in isolation, which is exactly why the gap survived four specs: every check that existed
looked inside the plugin, and the missing thing was outside it.

# User stories

- **As a data analyst following the setup workflow**, I run two commands and have the plugin
  installed — so A3's discovery loop is reachable instead of theoretical.
- **As a builder who prefers to read the manifest**, I see one file naming the plugin and its
  location — so I know what is being installed before I install it.
- **As a maintainer**, I have the gate fail when the plugin or the marketplace manifest stops being
  valid — so the install path cannot rot silently between releases.
- **As someone on a machine with no Claude Code**, I run the gate and see the plugin step **skip
  with a stated reason** — so a missing optional tool is not a red build.

# Functional requirements

- **FR-1** — A marketplace manifest exists at the repository root and names the `semantiql` plugin
  with its source directory.
- **FR-2** — `claude plugin marketplace add <checkout>` succeeds against a clean checkout.
- **FR-3** — `claude plugin install semantiql@<marketplace>` then succeeds, and the plugin's skill
  and MCP server are both present in what it installs.
- **FR-4** — The marketplace entry's description and the plugin manifest's agree, so a reader is not
  shown two different accounts of what the plugin does.
- **FR-5** — `docs/03-setup-workflow.md` A1 gives the two real commands in place of the
  unfollowable sentence, with output as captured from a real run.[^setup-workflow]
- **FR-6** — `plugin/README.md` gives the same commands, and explains what a marketplace is, since
  a reader arriving there is being asked to add something they did not know they needed.[^plugin-readme]
- **FR-7** — The verify gate validates both manifests with `claude plugin validate --strict`.
- **FR-8** — That gate step **skips with a stated reason** when the `claude` CLI is absent, and the
  gate still passes. CI must not depend on it.
- **FR-9** — A test asserts the marketplace manifest parses, names the plugin, and that its declared
  source resolves to a directory containing that plugin's manifest — the dangling-pointer case a
  schema check alone would pass.
- **FR-10** — A test asserts FR-4's agreement, so the two descriptions cannot drift.

# Non-functional requirements

- **Shipped product vs. own tooling** — the new `.claude-plugin/` at the root is *shipped product*,
  alongside `plugin/` and `bundle/`, and must not be confused with `.claude/`, which is this
  repository's own tooling. `AGENTS.md` states that separation and now has a third directory to
  place.[^constitution]
- **Setup in ≤ 15 minutes, every step automatically checked** — this is the constitution's own
  promise about Flow A, and the step in question was neither performable nor checked.[^constitution]
- **CI stays secret-free and dependency-light** — FR-8 is what keeps FR-7 from turning the gate into
  something that needs Claude Code installed. The `pg` step is the precedent: it skips with a
  stated reason and the gate still passes.[^constitution]
- **N1–N7 are untouched.** No query path, no adapter, no model, no engine change. This is packaging.

# Out of scope

- **Publishing the marketplace anywhere.** Adding it by local path is what the setup workflow needs.
  A hosted or GitHub-sourced marketplace is a release decision, and `claude plugin marketplace add`
  already accepts a GitHub repo when that day comes, with no manifest change.
- **Versioning or release tagging of the plugin.** `claude plugin tag` exists and validates that a
  plugin manifest and its marketplace entry agree about the version; the marketplace entry
  deliberately carries **no** version here, so there is no second place for one to drift. Tagging is
  its own change.
- **Installing the plugin during the gate.** Validation is a manifest check; an install mutates the
  developer's own Claude Code configuration, which a test suite has no business doing.
- **The Desktop bundle.** `.mcpb` is a different distribution channel and already works (spec 014).

[^constitution]: `.specify/memory/constitution.md` — the ≤15-minute setup rule with every step checked, the trust-boundary artifact list, the secret-free CI requirement, and the shipped-product/own-tooling separation.
[^setup-workflow]: `docs/03-setup-workflow.md` — Flow A, step A1, as rewritten by spec 016.
[^plugin-readme]: `plugin/README.md` — the Install section, carrying the same sentence since spec 013.
[^measured]: Measured, not assumed: `claude plugin marketplace add ./plugin` was run against this checkout and produced the error quoted. `claude plugin validate ./plugin --strict` passes, which is what establishes the plugin itself is sound and only unreachable.
