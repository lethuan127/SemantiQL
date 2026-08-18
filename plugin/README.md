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

[PluginEval](https://github.com/wshobson/agents) (MIT) scores the skill on ten dimensions across two
layers. Run it with thresholds:

```bash
claude plugin marketplace add wshobson/agents
claude plugin install plugin-eval@claude-code-workflows

uv run python scripts/eval_plugin.py                      # 3 runs, static>=0.95 judge>=0.90
uv run python scripts/eval_plugin.py --runs 5
```

**Not in `scripts/verify.sh`, deliberately.** It needs a third-party plugin installed and makes LLM
calls, so gating CI on it would break every fork PR and spend money per commit. It skips with an
install hint when PluginEval is absent.

### Where it stands

| Layer | Score | Target | Met |
|---|---|---|---|
| static | **0.9564**, identical on every run | > 0.95 | yes |
| judge | median **0.82**, range 0.667–0.895 across 12 runs | > 0.90 | no — see below |

Static breakdown, all deterministic:

| Dimension | Score |
|---|---|
| orchestration_wiring, progressive_disclosure, structural_completeness, harness_portability | 1.000 |
| token_efficiency | 0.966 |
| frontmatter_quality | 0.920 |
| ecosystem_coherence | 0.750 |

**The static gains came from real content**, not from satisfying regexes: worked examples, a
troubleshooting table of failures actually hit while building this, an input/output contract, a
"which verb when" comparison, `references/` for the refusal catalogue and field reference, and
`assets/` templates for starting a model. The skill grew 280 → ~430 lines and every section is
material a reader needs.

Two static points are left on the table on purpose. `frontmatter_quality` caps at 0.920 because the
remaining 0.05 requires the skill's `name` to **differ** from its directory, and `ecosystem_coherence`
caps at 0.750 because the remaining 0.25 requires a literal `skills/<other-skill>` path in the body —
the plugin ships one skill, so that reference would have to be invented.

### Why the judge target is not met, and what would meet it

Two structural facts, both read out of PluginEval's source rather than inferred:

**The judge reads only the first 3000 characters** of `SKILL.md`. That is why the opening now carries
the tool contract, the in-scope/refused table, the two non-negotiable limits and three worked
request→reply examples — everything a cold reader needs, before the detail. Finding this changed the
document for the better; it is the one scoring quirk that turned out to be sound advice.

**`scope_calibration` scores 0.75 in every single run and never moves.** Its rubric awards 1.0 to
"minimal surface area, maximum cohesion". This skill deliberately does two jobs — answering questions
*and* building the model — so 0.75 is the rubric correctly describing it. The judge score is a plain
mean of four dimensions, so **while both jobs live in one skill the ceiling is (1+1+1+0.75)/4 =
0.9375**, with `output_quality` the noisiest dimension between here and there.

**The honest route to > 0.90 is to split the skill in two** — `semantiql` for answering, and a
modelling skill for the discovery loop. Each becomes cohesive enough to score near 1.0 on scope, and
they would legitimately cross-reference each other, which also closes the `ecosystem_coherence` gap
without inventing anything. That is a restructure of shipped product with its own drift tests, manifest
and docs, so it belongs in its own spec rather than being smuggled in behind a score.

**The judge is noisy and one run is not a measurement.** On byte-identical content it has returned
judge scores from 0.667 to 0.895, with `output_quality` alone ranging 0.40–0.83 and
`triggering_accuracy` 0.75–1.00. `scripts/eval_plugin.py` therefore samples and reports the median and
the range; gating on a single run would be a coin toss dressed as a check.
