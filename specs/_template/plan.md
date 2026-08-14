---
type: Plan
title: <spec title> — plan
description: <one line on the approach>
resource: specs/NNN-short-kebab-name/plan.md
tags: [sdd, plan]
generated: { by: claude-code/claude-opus-5, at: '2026-01-01T09:00:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-01-01
  # one entry per file or search actually read; id must match the footnote that cites it
  - id: <source-id>
    resource: <repo-relative path, ../ prefixed if outside specs/>
    title: <what it established>
    last_modified: 2026-01-01
status: draft
---

<!-- T1 → impact-map-only mode: keep Constitution check + Repository Impact Map, delete Approach,
     Architecture decisions, and Open research questions. Gate 2 still fires. -->

# Constitution check

<For each invariant the change touches: name it, and say how the plan preserves it.>[^constitution]

<An invariant that would have to be amended → stop and open specs/NNN-constitution-update-<topic>/ first.>

# Approach

<Modules and interfaces, data flow, the seams tests run at, external dependencies, config, migration.
Prefer existing seams to new ones; propose any new seam as high as possible.>

# Architecture decisions

1. **<decision>** — <what was chosen, what was rejected, why.>

# Repository Impact Map

Derived from real `Grep` / `Glob` / `Read`, never from guessing. **Every row about an existing file carries
a footnote** to its `sources` entry — an unfootnoted row is an unverified claim, and that is what gate 2
catches.

## Files to modify

- `<path>` — <what changes, and the exact symbols / keys / frontmatter fields affected>.[^<source-id>]

## Files to add

- `<path>` — <purpose, shape>. <No footnote: nothing has been read yet.>

## Files not touched, but adjacent

- `<path>` — <why it is close but out of scope, so the user can correct you>.

<Where a change has a canonical source and derived copies, name both plus the re-sync step.>

# Open research questions

- <question> → resolves to a clarifications.md entry, a constitution amendment, or a stated confidence note.

[^constitution]: `.specify/memory/constitution.md` — <which invariants>.
[^<source-id>]: <the file as read at plan time>.
