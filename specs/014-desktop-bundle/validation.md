---
type: Validation
title: Desktop bundle — validation
description: Acceptance criteria traced to FR-1..FR-11, with the shipping bug T5 found recorded, and the Desktop install kept as a manual step rather than a tick.
resource: specs/014-desktop-bundle/validation.md
tags: [sdd, validation, mcpb]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T03:50:00+07:00' }
status: stable
---

# Results — walked 2026-08-18

| AC | FR | Outcome | Evidence |
|---|---|---|---|
| AC-1 | 1 | met | `scripts/build_bundle.py` produces one `.mcpb`, offline; the gate runs it |
| AC-2 | 2 | met | `manifest_version` 0.4, `server.type: uv`, entry point, name/version/description/author |
| AC-3 | 3 | met | the source is in the zip and `pyproject.toml` declares six deps without `semantiql`. **Verified by running it**: extracted to an unrelated directory, in a venv with no `semantiql` distribution, driven over stdio — both tools, an answer and a refusal |
| AC-4 | 4 | met | `user_config.model` is `type: file`, `required: true` |
| AC-5 | 5 | met | `dsn` is `sensitive: true`, not required; `datasource` defaults to `duckdb`; `database` optional |
| AC-6 | 6 | met | every `user_config` key maps to an env var the CLI reads, asserted rather than assumed |
| AC-7 | 7 | met | manifest version equals `metadata.version("semantiql")`; the filename carries it |
| AC-8 | 8 | met | 13 tests; no build-machine path anywhere; no `__pycache__`; rebuild is identical |
| AC-9 | 9 | met | the build is file copying and JSON — no network. The **install** is not offline; the host fetches dependencies then, and the docs say so |
| AC-10 | 10 | met | `dist/` ignored; `git status` is clean after a build |
| AC-11 | 11 | met | `docs/03`, `docs/10`, `README`, `plugin/README`, `bundle/README` name all three routes and when each applies |

**Non-functional:** gate green both ways — 324 unit, 27 e2e, 58 pg, a bundle build step, 0 OKF
errors. Bundle is 47 KB.

## The bug T5 found, which would have shipped

`__init__.py` read the version from `importlib.metadata`. Inside a bundle the package sits on
`sys.path` and is **never installed as a distribution**, so the lookup raises `PackageNotFoundError`
and the import aborted — on every machine that had not already installed SemantiQL, which is every
machine a bundle exists for.

It was invisible in development, because a checkout always has the distribution present. Worse: the
**first attempt at T5 passed**, because the venv running the test had SemantiQL installed and the
extracted code resolved against *that* metadata. Only a genuinely clean venv exposed it.

Fixed with a `_version.txt` stamp the build script writes and `__init__` falls back to — generated,
so git keeps one source of truth for the version. `test_the_version_survives_without_an_installed_distribution`
simulates the missing distribution so no clean machine is needed to catch a regression.

**The lesson worth keeping:** a test that verifies a *relocatable* artifact must not run in an
environment that already contains what the artifact carries.

## What the gate cannot prove

**Opening the bundle in Claude Desktop.** The gate builds it, checks it, and runs it over stdio, but
cannot install it into an application. Two questions remain open:

- **OQ-1 — does `mcp_config` coexist with `server.type: "uv"`?** The schema calls it optional for
  `uv` because the host manages execution, while documenting `${user_config.KEY}` substitution
  *inside* `mcp_config`. Supplying it explicitly is this plan's reading. If a host rejects it, the
  fallback is to have the user set the variables themselves — worse, and still working.
- **OQ-3 — `psycopg[binary]` is downloaded even by DuckDB-only users.** It is why the install pulls a
  Postgres driver nobody may need. Splitting it behind an extra is a separate change.

**The manual confirmation**, once:

1. `uv run python scripts/build_bundle.py`
2. Open `dist/semantiql-<version>.mcpb` with Claude Desktop.
3. Confirm the dialog shows a **file picker** for the model and a masked field for the DSN.
4. Choose a model that `semantiql doctor` passes, install, and ask a question it can answer.
5. Ask for something the model does not define — expect an explanation, not an error.
6. If step 2 or 3 fails, check OQ-1 first by removing `mcp_config` from the manifest and letting the
   host manage execution. That isolates substitution from everything else.

## Carried forward

- **Still a local server.** The installing machine needs database access. The bundle removes setup
  ceremony, not that requirement. A colleague with no credentials needs a remote connector — post-MVP.
- **A release would simplify this.** `_dependencies()` becomes one version line and the source stops
  travelling. Publishing is irreversible, so it stays the maintainer's decision.
