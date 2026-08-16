---
okf_version: "0.2"
---

# Specs

SDD change records — one directory per change, in number order. Each holds a `Spec`, and as the lifecycle
progresses, `Clarifications`, `Plan`, `Tasks`, and `Validation` concepts.

Types in use: `Spec`, `Clarifications`, `Plan`, `Tasks`, `Validation`.

Trust tiers are derived from each artifact's `verified` entries, which record the SDD gate approvals — an
artifact with no `verified` entry has not passed its gate. The repo's non-negotiables live outside this
bundle, at [.specify/memory/constitution.md](../.specify/memory/constitution.md).

* [001-init-project-scaffold/](001-init-project-scaffold/) - T2, shipped (FR-9 blocked), checkpoint 1 human-approved - initialize the repo: dev environment, verify gate, one runnable end-to-end example, and the artifacts a stranger needs to contribute
* [003-refuse-unimplemented-constructs/](003-refuse-unimplemented-constructs/) - T2, shipped - close the silent-drop gap — TABLESAMPLE and PIVOT are accepted and dropped today; make refusal the default for anything unimplemented
* [004-filter-by-dimension/](004-filter-by-dimension/) - T2, shipped - support WHERE over model dimensions with typed literals, rebuilt from the model
* [_template/](_template/) - blank artifact templates, not change records; their concepts inflate the trust and status counts above
