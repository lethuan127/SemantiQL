# Setup workflow

Two roles, two flows.

## Flow A — Builder (data analyst, done once)

1. **Install & init:** `uvx semantiql init` — a CLI wizard that asks step by step; no docs required upfront. Until the first release is published, the working path is from source: `git clone` → `uv sync` → `uv run semantiql`.
2. **Connect the database:** paste a connection string (a **read-only** account is recommended). The tool verifies the connection automatically.
3. **Auto-generate the semantic model:** the tool introspects the schema and generates a draft YAML (dimensions, measures, descriptions). AI assists with business-friendly naming and descriptions.
4. **Review & edit the YAML:** hide sensitive columns, add business metrics, fix descriptions. This human step is mandatory — semantic model quality determines answer quality.
5. **Export the Claude connection + verify:** the tool produces a bundle for one-click install into Claude Desktop and runs ~5 sample questions to confirm correct answers (`semantiql doctor`).

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
