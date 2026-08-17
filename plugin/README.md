# The SemantiQL plugin

Installs two things together: the **MCP server**, which is the only way Claude can reach your
database, and a **skill**, which teaches Claude how to use it.

They are separate for a reason. The server decides *what may be executed* — two read-only tools,
and nothing else. The skill decides *how to work* — call `describe_model` first, repair a refusal
rather than apologise for it, and never invent a number the model does not define. One is an
enforcement boundary, the other is procedural knowledge, and only the second should be editable by
opening a pull request.

## Install

From a checkout of this repository:

```bash
git clone https://github.com/lethuan127/semantiql && cd semantiql && uv sync
```

Then add the plugin from the `plugin/` directory of that checkout. The server definition locates
the Python environment through the plugin's own root, so it works wherever the plugin is installed
— nothing here contains a path from anyone's machine.

## Point it at your model

One environment variable, set before Claude starts:

```bash
export SEMANTIQL_MODEL=/absolute/path/to/your/model.yml
```

Which model to serve is inherently yours, so it is the one thing the plugin cannot ship. Without
it the bundled ten-row retail example is served — handy for trying the tools, and obviously not
your data.

For Postgres, credentials come from libpq's own environment (`PGHOST`, `PGUSER`, `~/.pgpass`),
exactly as `psql` reads them. Nothing in this plugin holds a password.

**Check the model before you rely on it:**

```bash
uv run semantiql doctor -m "$SEMANTIQL_MODEL"
```

`doctor` exits non-zero when the model and the database disagree. A model that fails here will
produce confusing refusals in chat, so it is worth clearing first.

## What Claude can do

| Tool | Does | Reaches the database |
|---|---|---|
| `describe_model` | lists tables, dimensions, measures, metrics, with labels and descriptions | no |
| `query` | answers one semantic SQL question, or refuses with a reason | yes, read-only |

That is the entire surface. There is no shell, no arbitrary SQL, and no write path — which is the
property that makes "only validated queries reach the data" structural rather than a rule someone
remembers.

## Claude Desktop

Claude Desktop uses a different packaging format from Claude Code, so this plugin does not install
there. The supported route is still the connector block:

```bash
uv run semantiql serve -m /path/to/model.yml --print-config
```

That prints the `mcpServers` JSON with every path already absolute, to paste into
`claude_desktop_config.json`. The server is identical; only the skill is missing, and the server
carries the essential guidance in its own instructions so it remains usable without it.
