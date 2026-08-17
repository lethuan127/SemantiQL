---
type: Plan
title: Desktop bundle — plan
description: A build script that assembles manifest, a deps-only pyproject, a three-line entry point and a copy of the source into dist/*.mcpb, plus env fallbacks so user_config answers reach the server through tested code.
resource: specs/014-desktop-bundle/plan.md
tags: [sdd, plan, mcpb, packaging]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T03:25:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time — ≤15 minutes, no connection strings for end users
    last_modified: 2026-08-18
  - id: mcpb
    resource: plan.md
    title: MCPB manifest schema read at spec time — manifest_version 0.4, server.type uv, mcp_config substitution, user_config types
  - id: cli
    resource: ../../src/semantiql/cli.py
    title: MODEL_ENV, _open_adapter, _serve, and the flags the bundle must reach through
    last_modified: 2026-08-18
  - id: server
    resource: ../../src/semantiql/server.py
    title: serve(model, adapter) — what the entry point ultimately calls
    last_modified: 2026-08-18
  - id: pyproject
    resource: ../../pyproject.toml
    title: The dependency list the bundle's pyproject mirrors, and the version it inherits
    last_modified: 2026-08-18
  - id: verify
    resource: ../../scripts/verify.sh
    title: The gate a bundle build step joins
    last_modified: 2026-08-18
  - id: gitignore
    resource: ../../.gitignore
    title: Where dist/ is excluded, so the bundle stays a build artifact
    last_modified: 2026-08-15
  - id: plugin-readme
    resource: ../../plugin/README.md
    title: The Claude Code route, which this sits beside rather than replaces
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T03:28:00+07:00', checkpoint: 2,
      basis: 'map derived from 7 file reads plus the MCPB manifest schema; all 6 existing-file rows footnoted. AD-2 puts the configuration reading in the CLI rather than the entry point, so it is covered by ordinary tests instead of a file only a bundle exercises. AD-4 states plainly what the gate cannot prove — a Desktop install — and what it checks instead' }
status: stable
---

# Constitution check

**N1 / N2** — packaging only. Two read-only tools, refusals keep their reasons, `run` stays the one
path to data.[^constitution]

**N5** — improved rather than merely preserved: a DSN entered into a `sensitive` field is what makes
using a read-only account convenient enough to actually do.[^constitution]

**≤15-minute setup, and "end users never touch a connection string or YAML"** — the requirements
this exists to serve. A file picker and a secret field are how the second one becomes literally
true on Desktop.[^constitution]

**Local only.** A bundle still runs the server on the user's machine; it removes ceremony, not the
need for database access. Said plainly in the docs rather than implied.

**Trust-boundary artifacts** in scope: `docs/03-setup-workflow.md`, `docs/07-code-map.md`, and the
project manifest is *read* but not changed. A new top-level `bundle/` directory is added.

# Approach

**A build script, not a committed artifact.** `scripts/build_bundle.py` assembles a staging tree and
zips it to `dist/semantiql-<version>.mcpb`. Nothing generated is committed (FR-10), and the version
comes from the installed package metadata so it cannot drift (FR-7).[^pyproject]

The staging tree:

```
manifest.json      generated: version substituted, user_config declared
pyproject.toml     generated: third-party deps only, copied from the real one
src/server.py      committed template — three lines
src/semantiql/     copied from the repo at build time
```

**The entry point is deliberately trivial.** It puts its own directory on `sys.path` and calls
`semantiql.cli.main(["serve"])`. Every decision — which adapter, which model — is made by code that
the ordinary test suite already covers.[^cli] [^server]

**Configuration arrives as environment variables, mapped by the host.** `mcp_config.env` substitutes
`${user_config.KEY}` into variables, which is MCPB's documented mechanism.[^mcpb] The CLI grows
fallbacks for datasource, DSN and database mirroring the `SEMANTIQL_MODEL` one it already has.

# Architecture decisions

**AD-1 — the source is copied at build time, never committed twice.** A second copy of
`src/semantiql/` in git would drift the first time either changed, and reviewers would have no way
to tell which was authoritative. The build script copies; the repository has one copy.

**AD-2 — configuration is read by the CLI, not by the entry point.** The tempting shape is an entry
point that reads environment variables and assembles arguments. That puts branching logic in the one
file no ordinary test exercises. Instead `cli.py` gains `SEMANTIQL_DATASOURCE`, `SEMANTIQL_DSN` and
`SEMANTIQL_DATABASE` fallbacks beside `SEMANTIQL_MODEL`, each covered by a normal test, and the entry
point becomes three lines with nothing to get wrong.[^cli]

**AD-3 — the bundle's `pyproject.toml` lists third-party dependencies only.** It is generated from
the real one so the two cannot disagree about versions, with `semantiql` itself absent because the
source is present. When a release exists, this is the single line that changes.[^pyproject]

**AD-4 — what the gate can and cannot prove.** It cannot install a bundle into Claude Desktop, so
FR-1's *"installs by opening it"* is not provable here. What is: the build runs offline, the manifest
is valid and complete, the entry point imports and reaches `serve`, the source is present, the
version matches, and **no absolute path appears anywhere inside**. The install itself is one manual
step in `validation.md`, not a tick.

**AD-5 — `datasource` is a string with a documented default, not an enum.** MCPB's `user_config`
types are string, number, boolean, file and directory — there is no enum.[^mcpb] So the field is a
string defaulting to `duckdb`, and a wrong value produces the CLI's existing argument error rather
than a silent fallback.

# Repository Impact Map

## Files to add

- `scripts/build_bundle.py` — assembles the staging tree and writes `dist/semantiql-<version>.mcpb`.
  Offline, deterministic, and the single source of the manifest.
- `bundle/server.py` — the committed entry point. Three lines: `sys.path`, import, `main(["serve"])`.
- `bundle/README.md` — what the bundle is, how to build it, how to install it.
- `tests/test_bundle.py` — builds the bundle in a temporary directory and checks AD-4's list.

## Files to modify

- `src/semantiql/cli.py` — AD-2, three more environment fallbacks beside `MODEL_ENV`.[^cli]
- `scripts/verify.sh` — a build-the-bundle step, so a broken bundle fails in CI.[^verify]
- `.gitignore` — `dist/` excluded, so the artifact is never committed (FR-10).[^gitignore]
- `docs/03-setup-workflow.md` — Flow B leads with the bundle; the paste route stays named.
  **Trust-boundary artifact.**[^setup-workflow]
- `docs/07-code-map.md` — the outside-`src/` tree gains `bundle/` and the build script.
  **Trust-boundary artifact.**[^code-map]
- `docs/10-adopting-semantiql.md` — Step 7's Desktop half becomes the bundle.
- `plugin/README.md` — its Desktop paragraph points at the bundle rather than calling it
  unbuilt.[^plugin-readme]
- `README.md` — the Claude section names all three routes and when each applies.
- `AGENTS.md` — the layout note gains `bundle/`; `CLAUDE.md` is a symlink and **not** a second edit.

## Files not touched, but adjacent

- `src/semantiql/server.py` — no change. The bundle is a way to launch it.
- `src/semantiql/engine/` — no change.
- `plugin/.mcp.json` — no change here. Its explicit `SEMANTIQL_HOME` is the right shape for the
  developer case now that the relocatable case has its own artifact.

# Open research questions

- **OQ-1 — does `mcp_config` coexist with `server.type: "uv"`?** The schema calls `mcp_config`
  optional for `uv` because the host manages execution, but `${user_config.KEY}` substitution is
  documented *in* `mcp_config`. Supplying it explicitly is the plan's reading. If a host rejects it,
  the fallback is to declare the variables in `user_config` and have the user set them — worse, and
  still working.
- **OQ-2 — will `uv` resolve the bundled `pyproject.toml` offline on a user's machine?** The build
  is offline; the *install* is not, because the host fetches dependencies. Worth stating so nobody
  promises an air-gapped install.
- **OQ-3 — is `psycopg[binary]` available as a wheel everywhere the bundle might land?** It is the
  reason DuckDB-only users still download a Postgres driver. Splitting it behind an extra would make
  the bundle smaller and is a separate change.

[^constitution]: `.specify/memory/constitution.md` — the ≤15-minute rule, end users and connection strings, N1, N2, N5.
[^mcpb]: MCPB manifest schema — `manifest_version` 0.4, `server.type: "uv"`, `${__dirname}` and `${user_config.KEY}` substitution in `mcp_config`, and the `user_config` type list.
[^cli]: `src/semantiql/cli.py` — `MODEL_ENV`, `_open_adapter`, `_serve`, and `main`'s argument handling.
[^server]: `src/semantiql/server.py` — `serve(model, adapter)`.
[^pyproject]: `pyproject.toml` — the dependency list and the version the bundle inherits.
[^verify]: `scripts/verify.sh` — the gate's steps.
[^gitignore]: `.gitignore` — where build output is excluded.
[^setup-workflow]: `docs/03-setup-workflow.md` — Flow A and Flow B.
[^code-map]: `docs/07-code-map.md` — the outside-`src/` tree.
[^plugin-readme]: `plugin/README.md` — the Claude Code route and its Desktop paragraph.
