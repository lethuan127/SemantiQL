# SDD artifact templates

Copy one into `specs/NNN-short-kebab-name/` as each phase creates its artifact, then replace every `<...>`
placeholder. Fields the validator syntax-checks — `generated.by`, `at`, `last_modified` — carry realistic
example values instead of placeholders, so a half-filled template still parses; replace them too.

* [spec.md](spec.md) - written by specify; carries the gate-1 approval
* [clarifications.md](clarifications.md) - written by clarify; no gate
* [plan.md](plan.md) - written by plan; carries the gate-2 approval and the impact map's sources
* [tasks.md](tasks.md) - written by tasks; carries the gate-3 approval, T2 only
* [validation.md](validation.md) - skeleton from plan, ticked during implement; no gate

## These are a derived copy

The **canonical source** is the section list inside each phase file at
`.claude/skills/sdd/reference/<phase>.md`. These templates only render those lists as fillable files.

Changing a template without changing its phase file makes the two disagree, and the phase file wins. Edit the
phase file first, then re-sync the template in the same change — the analyze phase's canonicality check
exists to catch that drift.

## They count as concepts

This directory sits inside the `specs/` OKF bundle, so the validator reads each template as a real concept
document. That is why they carry full frontmatter: a template without it fails conformance outright, and a
conformance error blocks both analyze and implement.

The cost is that five permanently-unverified placeholder concepts sit in the bundle's trust and status
counts. When reading `trust: N unverified`, subtract these five — the real figure is for
`specs/NNN-*/` only.

This file is `index.md` rather than `README.md` on purpose: `index.md` is an OKF reserved filename, exempt
from the frontmatter requirement, and listing the templates here is also what stops the directory warning
that a concept no index lists is invisible.
