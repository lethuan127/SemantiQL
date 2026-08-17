---
type: Spec
title: A one-click bundle for Claude Desktop, with the source inside it
description: A relocatable .mcpb zip that installs by opening it and asks for the model with a file picker — replacing a hand-pasted JSON block and the assumption that the package sits next to a checkout.
resource: specs/014-desktop-bundle/spec.md
tags: [sdd, spec, mcpb, packaging, mcp]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T03:15:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables — local-first MCP, ≤15-minute setup, end users never touch a connection string
    last_modified: 2026-08-18
  - id: mcpb
    resource: https://github.com/modelcontextprotocol/mcpb
    title: MCPB — zip bundles with manifest.json, the uv server type, and user_config; read at spec time
  - id: spec-013
    resource: ../013-plugin-and-skill/spec.md
    title: The plugin whose path assumption this replaces for the relocatable case
    last_modified: 2026-08-18
  - id: cli
    resource: ../../src/semantiql/cli.py
    title: The SEMANTIQL_MODEL fallback and --print-config, the route this supersedes on Desktop
    last_modified: 2026-08-18
  - id: setup-workflow
    resource: ../../docs/03-setup-workflow.md
    title: Flow A's ≤15-minute rule and Flow B, and the open question this narrows
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T03:18:00+07:00', checkpoint: 1,
      basis: '11 FRs, each testable. Scope forced by a defect the user found in spec 013 rather than by ambition: a plugin that derives the checkout from its own location cannot be relocated, and a zip is by definition relocated. FR-3 states bundling the source as a step rather than a commitment, and FR-8 puts the bundle under the gate so it fails in CI rather than on a desktop' }
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** A new build artifact and build script, a new top-level directory, extended CLI
configuration, and edits to `docs/NN-*.md`. More than three files, and it changes what the project
ships.

# What

An analyst hands a colleague one file. The colleague opens it, Claude Desktop shows an install
dialog with a **file picker for the semantic model**, and they start asking questions.

```
semantiql-0.0.2.mcpb   →  double-click  →  ┌──────────────────────────────┐
                                           │ Install SemantiQL            │
                                           │                              │
                                           │ Semantic model    [ Browse ] │
                                           │ Datasource        duckdb   ▾ │
                                           │ Postgres DSN      ••••••     │
                                           │                              │
                                           │            [ Install ]       │
                                           └──────────────────────────────┘
```

Today the Desktop route is `semantiql serve --print-config`, which prints JSON for a human to
paste into an application config directory, followed by a full restart.[^cli] And spec 013's plugin
cannot take its place: it locates the Python by walking up from its own directory, which is only
the checkout while nobody moves it. **Unzip that plugin anywhere else and the server never
appears.**

A bundle has no such assumption. It carries SemantiQL's own source, declares its third-party
dependencies, and lets the host install them.

# Why

**The install step is the one the ≤15-minute rule keeps failing on.** The constitution requires
builder setup to complete in fifteen minutes with every step automatically checked and every error
carrying a fix instruction.[^constitution] Pasting JSON into `~/Library/Application Support/` is
none of those things: no check, no error, and the failure mode is a connector that silently does
not appear. `--print-config` made the *content* correct and left the ceremony intact.

**A file picker is the honest answer to "which model?".** Spec 013 settled on `SEMANTIQL_MODEL`
because a plugin has nowhere to ask. A bundle does: `user_config` supports a `file` type, so the
host asks and substitutes the answer.[^mcpb] Same for a Postgres DSN, which can be declared
`sensitive` and stored securely rather than living in a JSON file people paste into chat windows —
which matters, because the constitution says end users never touch a connection
string.[^constitution]

**The plugin's path assumption is a real defect, and this is where it gets fixed properly.**
Spec 013's `.mcp.json` derived the checkout from the plugin's own location.[^spec-013] That holds
for a developer who installed the plugin from inside a clone and breaks for everyone else, with no
error anyone can read. The plugin keeps an explicit variable for the developer case; the
relocatable case is a bundle, because a relocatable artifact cannot reference a checkout by
construction.

**The source goes inside, deliberately.** MCPB's `uv` server type resolves dependencies from a
bundled `pyproject.toml`, so `semantiql` itself has to come from somewhere.[^mcpb] The published
package predates the `serve` verb, so depending on it would ship a bundle that cannot start.
Carrying the source works today, needs no release, and is reversible: once a release exists the
bundle declares a version instead and gets smaller.

# User stories

- **As an analyst**, I build one file and send it to a colleague — so setting them up is not a
  screen-share.
- **As a colleague**, I open the file, choose my model in a dialog, and ask a question — so I never
  edit JSON or learn where an application keeps its config.
- **As a colleague with a Postgres warehouse**, my connection string is entered once into a field
  marked secret — so it is not sitting in a file I might paste somewhere.
- **As a maintainer**, the bundle is produced by a script the gate runs, so a broken bundle fails
  in CI rather than on someone's desktop.
- **As a maintainer**, I can point the bundle at a published release later by changing one
  dependency line — so bundling the source is a step, not a commitment.

# Functional requirements

- **FR-1** — A build script produces a single `.mcpb` file from the repository, with no manual
  steps and no per-machine paths inside it.
- **FR-2** — The bundle carries a `manifest.json` valid against MCPB's requirements for a `uv`
  server: manifest version, name, version, description, author, and a server entry point.
- **FR-3** — The bundle carries SemantiQL's own source and a `pyproject.toml` declaring its
  third-party dependencies, so the host can install and run it **without a checkout and without a
  published release**.
- **FR-4** — `user_config` asks for the **semantic model as a file**, required, so the model is
  chosen in a dialog rather than typed into a variable.
- **FR-5** — `user_config` asks for the datasource and, optionally, a Postgres DSN marked
  **sensitive**, and a DuckDB database file. Neither is required for the bundled example to work.
- **FR-6** — Those answers reach the server as configuration, and the server behaves identically to
  the same options given on the command line.
- **FR-7** — The bundle's version matches the package's, so a bundle can always be traced to the
  code that produced it.
- **FR-8** — The gate builds the bundle and checks it: valid manifest, an importable entry point,
  the source present, and **no absolute path anywhere inside**.
- **FR-9** — Building the bundle requires no network, so it works on a fresh clone offline.
- **FR-10** — The bundle is a build artifact, not a committed file: it is produced from source and
  ignored by git.
- **FR-11** — Documentation names the bundle as the Desktop route, keeps `--print-config` for
  anyone who wants it, and keeps the plugin as the Claude Code route — with the difference between
  them stated rather than implied.

# Non-functional requirements

- **N1 / N2** — packaging only. The tool surface stays two read-only calls and a refusal keeps its
  reason. Nothing about what may run changes.[^constitution]
- **N5 — read-only by default** — and now easier to honour, because a DSN entered into a
  `sensitive` field is what lets someone use a read-only account without pasting it
  anywhere.[^constitution]
- **Local only** — a bundle runs the server on the user's own machine. This is still not the remote
  connector the non-technical story eventually needs; it removes the setup ceremony, not the
  requirement for database access.[^setup-workflow]
- **≤15-minute setup** — this is the requirement the change exists to serve.[^constitution]

# Out of scope

- **Publishing a release.** FR-3 exists so the bundle works without one. Swapping bundled source
  for a version dependency is a later, smaller change.
- **A remote connector.** Requires an HTTPS endpoint, hosting and OAuth; post-MVP by the
  constitution, and a different product surface.
- **Signing or notarising the bundle.** Distribution hardening, not packaging.
- **Retiring `--print-config` or the plugin.** Both keep working; FR-11 documents when each
  applies.
- **A GUI for building the bundle.** A script the gate runs is enough.

[^constitution]: `.specify/memory/constitution.md` — the ≤15-minute setup rule, "end users never touch a connection string or YAML", local-first MCP, N1, N2, N5.
[^mcpb]: MCPB, github.com/modelcontextprotocol/mcpb — `.mcpb` zips, `manifest.json`, the `uv` server type where the host installs dependencies from `pyproject.toml`, and `user_config` with `file`/`string`/`sensitive` types. Read at spec time.
[^spec-013]: `specs/013-plugin-and-skill/spec.md` — the plugin, and the `.mcp.json` path assumption this supersedes for the relocatable case.
[^cli]: `src/semantiql/cli.py` — the `SEMANTIQL_MODEL` fallback and `--print-config`.
[^setup-workflow]: `docs/03-setup-workflow.md` — Flow A's fifteen-minute rule, Flow B, and the local-versus-remote open question.
