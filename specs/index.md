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
* [005-order-and-limit/](005-order-and-limit/) - T2, shipped - ORDER BY over projected names plus LIMIT/OFFSET, and the first real transpile assertion
* [006-derived-metrics/](006-derived-metrics/) - T2, shipped - metrics derived from measures, with a closed expression grammar and a guarded divisor
* [007-time-grains/](007-time-grains/) - T2, shipped - DATE_TRUNC over date dimensions, with the year-collapsing forms refused
* [008-e2e-suite/](008-e2e-suite/) - T2, shipped (checkpoint 3 skipped) - an end-to-end suite over a locally generated TPC-H corpus, checked against hand-written SQL
* [009-doctor/](009-doctor/) - T2, shipped - a health check that finds where the model and the real schema disagree
* [010-postgres-adapter/](010-postgres-adapter/) - T2, shipped - a Postgres adapter that proves N4 with a second engine, and the differential suite that shows the same model answers the same on both
* [011-time-grain-timezones/](011-time-grain-timezones/) - T2, shipped - a time grain must not depend on the database server's timezone; found by 010's differential suite
* [012-mcp-server/](012-mcp-server/) - T2, shipped - a local MCP server over stdio, so Claude writes the semantic SQL, reads refusals, and repairs
* [013-plugin-and-skill/](013-plugin-and-skill/) - T2, shipped - a plugin bundling the MCP server and a skill, and the architecture doc that finally describes what Claude knows
* [014-desktop-bundle/](014-desktop-bundle/) - T2, shipped - a relocatable .mcpb bundle that installs by opening it and asks for the model with a file picker
* [015-model-directory/](015-model-directory/) - T2, shipped - a model may be a directory of YAML files, and describe_model returns a table list so scale does not flood the context
* [016-schema-discovery/](016-schema-discovery/) - T2, shipped - Claude inspects the database and writes the model itself; the adapter seam gains enumeration
* [_template/](_template/) - blank artifact templates, not change records; their concepts inflate the trust and status counts above
