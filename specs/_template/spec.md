---
type: Spec
title: <descriptive, not generic>
description: <one line — this is what specs/index.md shows>
resource: specs/NNN-short-kebab-name/spec.md
tags: [sdd, spec]
generated: { by: claude-code/claude-opus-5, at: '2026-01-01T09:00:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-01-01
status: draft
sdd_phase: drafting
sdd_tier: <T1 | T2>
---

**<T1 | T2>.** <one line: which conditions hold, or which failed>

# What

<One paragraph of user-visible behaviour. No tech, no architecture, no implementation.>

<One sentence on what happens today, so the gap is concrete.>

# Why

<The concrete problem, with a real user scenario — a named role hitting a named wall.>

# User stories

- **As a <role>**, I <action> — so <outcome>.
- **As a <role>**, I <action> — so <outcome>.

# Functional requirements

- **FR-1** — <testable statement of behaviour>
- **FR-2** — <testable statement of behaviour>

# Non-functional requirements

- **<N-n> (<invariant name>)** — <how this change is constrained by it>.[^constitution]

# Out of scope

<What is tempting to pull in here, and which spec it belongs to instead.>

[^constitution]: `.specify/memory/constitution.md` — <which sections bear on this change>.
