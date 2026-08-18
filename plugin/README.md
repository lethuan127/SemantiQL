# The SemantiQL plugin

Installs two things together: the **MCP server**, which is the only way Claude can reach your
database, and a **skill**, which teaches Claude how to use it.

They are separate for a reason. The server decides *what may be executed* — two read-only tools,
and nothing else. The skill decides *how to work* — call `describe_model` first, repair a refusal
rather than apologise for it, and never invent a number the model does not define. One is an
enforcement boundary, the other is procedural knowledge, and only the second should be editable by
opening a pull request.

## Install

**This plugin is for Claude Code, and it needs a checkout to run against.** It carries
configuration and markdown, not a Python environment, so it has to be told where SemantiQL itself
lives. Two variables, set before Claude starts:

```bash
git clone https://github.com/lethuan127/semantiql && cd semantiql && uv sync

export SEMANTIQL_HOME=$PWD                              # where SemantiQL is installed
export SEMANTIQL_MODEL=/absolute/path/to/your/model.yml  # which model to serve
```

Then install it. Two commands, from the checkout root:

```bash
claude plugin marketplace add "$PWD"      # the repo root, NOT plugin/
claude plugin install semantiql@semantiql
```

**Why the first command exists.** Claude Code does not install a plugin from a plugin directory. It
installs from a **marketplace**: a directory carrying `.claude-plugin/marketplace.json`, which lists
the plugins it offers and where each one lives. The SemantiQL repository is that marketplace, and it
lists exactly one plugin — this directory. Point `marketplace add` at `plugin/` instead and it fails
with `Marketplace file not found`, which is the error this README used to walk people into.

Use the default scope. `--scope local` also works and writes an absolute path to your checkout into
`.claude/settings.local.json`, inside the repository.

**Why `SEMANTIQL_HOME` and not something automatic.** An earlier version of this file derived the
checkout from the plugin's own location, assuming the plugin is always installed *from inside* the
repository. Copy the plugin anywhere else — or unzip it — and that assumption silently points at a
directory with no SemantiQL in it, and the server never appears. An explicit variable is worse to
type and impossible to be quietly wrong about.

If you want a single-file install with no checkout and no variables, that is a **bundle**, not a
plugin — see below.

## Point it at your model

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

Claude Desktop installs a **bundle** — a `.mcpb` zip you open, which prompts for the model file
rather than asking you to set variables. It is built and documented in
[`../bundle/README.md`](../bundle/README.md), and it is what to use on Desktop: unlike this plugin
it carries the source, so it needs no checkout and no `SEMANTIQL_HOME`.

The older route also still works:

```bash
uv run semantiql serve -m /path/to/model.yml --print-config
```

That prints the `mcpServers` JSON with every path already absolute, to paste into
`claude_desktop_config.json`. The server is identical; only the skill is missing, and the server
carries the essential guidance in its own instructions so it remains usable without it.


## Scoring the skill

[PluginEval](https://github.com/wshobson/agents) (MIT) scores a skill on ten dimensions. It is a
**developer tool, not a gate**: it needs a third-party plugin installed and makes LLM calls, so it
stays out of `scripts/verify.sh` and out of CI.

```bash
claude plugin marketplace add wshobson/agents
claude plugin install plugin-eval@claude-code-workflows

P=~/.claude/plugins/cache/claude-code-workflows/plugin-eval/0.1.1
cd "$P" && uv run --extra llm plugin-eval score \
  /path/to/semantiql/plugin/skills/semantiql --depth standard
```

**Result as of spec 020: 73.0/100, Silver, and no anti-patterns detected** at either the static or
judge layer. Token efficiency scored 0.962 (A) and triggering accuracy 0.801 (B-) under the LLM judge.

### Four dimensions we deliberately do not chase

The remaining gap is mostly convention-scoring, and closing it would mean gaming a regex rather than
improving the skill. Recorded here so it is a decision rather than an oversight, and so nobody
re-litigates it from the number alone. Read from the tool's own source, not inferred:

| Dimension | What it actually rewards | Why we leave it |
|---|---|---|
| Progressive disclosure 0.60 | 281 lines is inside its **ideal** 200–600 band, which caps at 0.60; the rest needs `references/` and `assets/` directories | We would be adding directories we have no content for |
| Ecosystem coherence 0.50 | baseline 0.50, +0.25 for cross-references to other skills, +0.25 for containing "related" / "see also" / "companion" | The plugin ships one skill. It is standalone, and the phrase is a regex match, not a fact |
| Frontmatter, name portion | +0.15 only when the skill's `name` **differs** from its directory | They match, which is the convention everywhere else |
| Frontmatter, "pushiness" | the literal words "proactively", "automatically", "always use"; and ≥3 comma-separated "when …ing" clauses | Keyword stuffing. It changes whether a regex fires, not whether the skill does |

`AGENTS.md` forbids weakening a check to make it pass. Inflating a metric without improving the thing
it measures is the same trade in the other direction, so the number stays at 73.

**The one signal worth returning to** is Output Quality, which the LLM judge scored 0.620 (D-). Unlike
the four above, that is a judgement about the skill's substance rather than its shape — but the tool
reports no reason, so acting on it needs the judge's transcript, which `--depth deep` may expose.
