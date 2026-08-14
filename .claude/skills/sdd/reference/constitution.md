# constitution phase

Read the repo's non-negotiables, or propose an edit to them. The constitution lives at `.specify/memory/constitution.md`, and no spec, plan, or implementation may violate it.

## Read — the default action

Summarise the whole constitution, then name which sections (mission, non-negotiables, taxonomy, tech stack, roadmap, governance) bear on the user's current open files and recent edits.

## Propose an edit

Never edit the constitution unilaterally. Propose, then wait.

1. **Identify the section** the change touches.
2. **If it touches a non-negotiable**, declare that this needs its own `specs/NNN-constitution-update-<topic>/` spec, run through the full lifecycle at T2.
3. **If it's lower-stakes** — a roadmap entry, a tech-stack note — draft the diff inline, present it, and wait for explicit approval before applying.

## Missing constitution

Report it and wait: "no constitution found at `.specify/memory/constitution.md` — recommend scaffolding one before continuing." Scaffold one here, or let the user waive it for this change. Never substitute another repo's constitution.

A scaffolded constitution covers: mission, non-negotiables (the invariants), taxonomy (where each kind of thing lives), tech stack, roadmap, governance (how the constitution itself changes), and the repo's **trust-boundary artifacts** — the files other work resolves against, which the tier ladder keys on.

Give it OKF frontmatter too — `type: Constitution`, plus `generated`, `status: stable`, and a `sources` entry per document the invariants were drawn from. It sits at `.specify/memory/constitution.md`, outside the `specs/` bundle, so a validator run rooted at `specs/` never reaches it; the frontmatter is there because every spec cites this file as a source and a reader needs to know how current it is. This is the one SDD artifact where `stale_after` may earn its place — set it when the constitution encodes a roadmap or a tech-stack choice that has a known horizon, and omit it when the invariants are settled.

## Stop condition

After reading or proposing, stop.
