# The Claude Desktop bundle

One file a colleague opens to install SemantiQL — no config file to edit, no restart ceremony, and
the semantic model chosen in a dialog rather than typed into an environment variable.

## Build it

```bash
uv run python scripts/build_bundle.py
# → dist/semantiql-<version>.mcpb
```

Offline, and about 47 KB. The build is not committed — it is produced from source, because a
committed bundle is a second copy of the code that drifts from the first.

## Install it

Open the `.mcpb` file with Claude Desktop. It shows an install dialog:

| Field | What it is |
|---|---|
| **Semantic model** | a file picker for your model YAML — required |
| **Datasource** | `duckdb` or `postgres`, defaults to `duckdb` |
| **Postgres connection string** | optional, marked secret so the host stores it securely |
| **DuckDB database file** | optional, only if your model reads tables rather than files |

Run `semantiql doctor` on the model first. A model that disagrees with its database produces
confusing refusals in chat, and `doctor` names the disagreement precisely.

## Why the source is inside

MCPB installs dependencies from the bundle's own `pyproject.toml`, so SemantiQL has to come from
somewhere. The published package predates the `serve` verb, so depending on it would ship a bundle
that cannot start. Carrying the source works today and needs no release.

Once a release exists this gets smaller: `_dependencies()` in the build script declares a version
instead, and the source stops travelling. One function.

## What this is not

**It is still a local server.** It runs on the machine that installed it, so that machine needs to
reach your database. The bundle removes the setup ceremony; it does not remove the requirement for
database access. A colleague with no credentials needs a remote connector, which is a different
piece of work and deliberately post-MVP.

## The other two routes

| You are on | Use |
|---|---|
| Claude Desktop | this bundle |
| Claude Code | the plugin in [`../plugin/`](../plugin/README.md) — it also carries the skill |
| Anything else, or debugging | `semantiql serve --print-config` and paste the block |
