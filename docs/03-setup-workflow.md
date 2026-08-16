# Setup workflow

Two roles, two flows.

## Flow A — Builder (data analyst, done once)

1. **Install & init:** `uvx semantiql init` — a CLI wizard that asks step by step; no docs required upfront. Until the first release is published, the working path is from source: `git clone` → `uv sync` → `uv run semantiql`.
2. **Connect the database:** paste a connection string (a **read-only** account is recommended). The tool verifies the connection automatically.
3. **Auto-generate the semantic model:** the tool introspects the schema and generates a draft YAML (dimensions, measures, descriptions). AI assists with business-friendly naming and descriptions.
4. **Review & edit the YAML:** hide sensitive columns, add business metrics, fix descriptions. This human step is mandatory — semantic model quality determines answer quality.
5. **Export the Claude connection + verify:** the tool produces a bundle for one-click install into Claude Desktop and runs ~5 sample questions to confirm correct answers.

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

**What it does not do yet:** run sample questions to confirm the *answers* are right. That
needs the MCP bundle from step 5, which is not built — so doctor currently verifies that the
model fits the database, not that the model answers well. The accuracy half arrives with the
MCP server.

It never edits the model. Fixes are proposed to a human, per the two-tier rule in
[04-self-improvement.md](04-self-improvement.md).

## Flow B — End user (non-technical, per person)

1. Receive the bundle/link from the builder → install into Claude Desktop (double-click).
2. Chat normally: *"Revenue this month by channel?"*

## Design principles

- Flow A completes in **≤ 15 minutes**; every step has automated checks, and errors come with fix instructions.
- Read-only by default; the semantic model is **one YAML file** — git-friendly, reviewable.
- End users **never** touch a connection string or YAML.

## Open questions

- **Local vs remote MCP server:** local (runs on each person's machine) is simple for the MVP but forces the end user's machine to connect directly to the database — wrong fit for non-technical users. Remote (shared server, users just add a connector URL) is the right model but adds hosting + auth work. → **MVP goes local first, designed with a clear path to remote.**
- Auth/permissions when multiple users share one server — belongs to the Data Governance layer; post-MVP.
