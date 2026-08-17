# Setup workflow

Two roles, two flows.

## Flow A — Builder (data analyst, done once)

1. **Install:** `git clone` → `uv sync`. (`uvx semantiql` resolves an older published build, and `semantiql init` is not built — see below.) Then install the plugin from `plugin/`, which registers the MCP server *and* the skill that teaches Claude how to use it (spec 013). For Claude Desktop, which takes a different packaging format, use `semantiql serve --print-config` and paste the block it prints.
2. **Connect the database:** paste a connection string (a **read-only** account is recommended). The tool verifies the connection automatically.
3. **Auto-generate the semantic model:** the tool introspects the schema and generates a draft YAML (dimensions, measures, descriptions). AI assists with business-friendly naming and descriptions.
4. **Review & edit the YAML:** hide sensitive columns, add business metrics, fix descriptions. This human step is mandatory — semantic model quality determines answer quality.
5. **Point Claude at it + verify:** set `SEMANTIQL_MODEL` to the model's absolute path, then run `semantiql doctor` and confirm it exits 0. Running ~5 sample questions to confirm the *answers* is still unbuilt — see below.

### What `semantiql doctor` does today

Step 5 above describes the finished flow. What exists now is the half that does not need the
Claude bundle: `semantiql doctor` checks the model against the database and reports every
mismatch in one pass — a `source` that cannot be read, a `column` that does not exist (with
suggestions), a `type:` that contradicts the real column, an aggregation the column cannot
take, and a dialect mismatch. It exits `0` when everything resolves and `1` when it does not,
so a setup script can stop rather than report success.

```bash
uv run semantiql doctor -m model.yml --database warehouse.duckdb
```

**What it does not do yet:** run sample questions to confirm the *answers* are right. doctor
verifies that the model fits the database, not that it answers well. The MCP server now exists
(spec 012), so the pieces are there — a `doctor --ask` that runs a few questions through the
server and reports the answers is the remaining step, and it is not built.

It never edits the model. Fixes are proposed to a human, per the two-tier rule in
[04-self-improvement.md](04-self-improvement.md).

## Flow B — End user (per person)

1. Receive a `.mcpb` bundle from the builder → **open it**. Claude Desktop shows an install
   dialog with a file picker for the model and a secret field for a Postgres connection string
   (spec 014). No config file, no restart ceremony.
2. Chat normally: *"Revenue this month by channel?"*

The builder produces that file with `uv run python scripts/build_bundle.py`. The older route —
`semantiql serve --print-config`, pasted into `claude_desktop_config.json` — still works and is
what to fall back on when debugging.

**Working today (spec 012), with one honest limit.** Claude calls `describe_model` to learn the
vocabulary, writes semantic SQL, and reads a refusal and repairs it without the user seeing any
of that. What it is *not* yet is non-technical: a **local** server runs on the end user's own
machine, so they need SemantiQL installed and database access. That is the trade-off recorded
under Open questions below — MVP-local proves the loop with people who already have access, and
the genuinely non-technical story needs remote mode.

## Design principles

- Flow A completes in **≤ 15 minutes**; every step has automated checks, and errors come with fix instructions.
- Read-only by default; the semantic model is **one YAML file** — git-friendly, reviewable.
- End users **never** touch a connection string or YAML.

## Open questions

- **Local vs remote MCP server:** local (runs on each person's machine) is simple for the MVP but forces the end user's machine to connect directly to the database — wrong fit for non-technical users. Remote (shared server, users just add a connector URL) is the right model but adds hosting + auth work. → **MVP goes local first, designed with a clear path to remote.**
- Auth/permissions when multiple users share one server — belongs to the Data Governance layer; post-MVP.
