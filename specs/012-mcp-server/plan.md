---
type: Plan
title: MCP server — plan
description: One new module beside cli.py exposing two read-only tools over stdio, a serve verb reusing the CLI's adapter seam, and an end-of-transaction step so a long-lived connection stops pinning a snapshot.
resource: specs/012-mcp-server/plan.md
tags: [sdd, plan, mcp]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T01:15:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time — N1, N2, N5, local-first MCP, trust boundaries
    last_modified: 2026-08-18
  - id: clarifications
    resource: clarifications.md
    title: The 8 decisions this plan implements, five of them measured
    last_modified: 2026-08-18
  - id: run
    resource: ../../src/semantiql/engine/run.py
    title: run(sql, model, adapter) -> Result | Refusal; Result carries columns, rows and sql
    last_modified: 2026-08-15
  - id: cli
    resource: ../../src/semantiql/cli.py
    title: _open_adapter, the flag set, NOT_YET_IMPLEMENTED, and the exit-code contract
    last_modified: 2026-08-18
  - id: model
    resource: ../../src/semantiql/knowledge/model.py
    title: Dimension/Measure/Metric with label and description; Table.entity_names
    last_modified: 2026-08-18
  - id: postgres-adapter
    resource: ../../src/semantiql/adapters/postgres.py
    title: execute()'s cursor block, and the autocommit comment naming server mode
    last_modified: 2026-08-18
  - id: base
    resource: ../../src/semantiql/adapters/base.py
    title: The Adapter Protocol — no change needed; close() already declared
    last_modified: 2026-08-17
  - id: data-modeling
    resource: ../../docs/09-data-modeling.md
    title: The "label and description are written but never read" note, which this change falsifies
    last_modified: 2026-08-18
  - id: code-map
    resource: ../../docs/07-code-map.md
    title: Callers sit at the top level beside the layers; the src tree to extend
    last_modified: 2026-08-18
  - id: setup-workflow
    resource: ../../docs/03-setup-workflow.md
    title: Flow A step 5 and Flow B, both of which this makes real
    last_modified: 2026-08-17
  - id: adopting
    resource: ../../docs/10-adopting-semantiql.md
    title: The "cannot hand this to a non-technical colleague yet" warning this spec removes
    last_modified: 2026-08-18
  - id: readme
    resource: ../../README.md
    title: The roadmap table and the not-built-yet sentence
    last_modified: 2026-08-18
  - id: agents
    resource: ../../AGENTS.md
    title: The not-yet-built list and the supported-constructs paragraph; CLAUDE.md symlinks to it
    last_modified: 2026-08-18
  - id: mcp-client-docs
    resource: https://modelcontextprotocol.io/docs/develop/connect-local-servers
    title: Claude Desktop config shape and location, read at plan time to resolve OQ-2
  - id: pyproject
    resource: ../../pyproject.toml
    title: dependencies, keywords, the mypy override block, pytest markers
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T01:22:00+07:00', checkpoint: 2,
      basis: 'map derived from 11 file reads plus live probes of mcp 2.0.0 and PostgreSQL 17.10; all 9 existing-file rows footnoted after a self-audit caught 3 (README, AGENTS.md, docs/10) listed without a sources entry. AD-3 touches an adapter and says why the property belongs to the connection. OQ-2 resolved from the client docs; OQ-1 and OQ-3 stated, OQ-3 hedged in the design rather than left to chance' }
status: stable
---

# Constitution check

**N1 — validation before the data.** The `query` tool calls `engine.run.run` and nothing else. No
new path, no adapter reached directly. `AGENTS.md` names a shortcut to an adapter as the change
most likely to be rejected, and a server is precisely the component tempted to
add one.[^run] [^constitution]

**N2 — a silently wrong number is the worst failure.** Sharper here than anywhere prior: until now
a wrong figure would be read by an analyst who might notice, and from now on by someone who
cannot. The concrete control is Q3's decision — a refusal travels as a structured answer carrying
its reason, never flattened into a generic tool error.[^clarifications]

**N5 — read-only by default.** A long-lived connection is the case `adapters/postgres.py` warned
about. Q5 measured the fix: end the transaction after each answer, which keeps one connection,
releases the snapshot, and leaves read-only enforced.[^postgres-adapter] [^clarifications]

**N6 — two learning tiers, permanently separate.** Untouched. The server records nothing and
proposes no model change; verified examples are a later spec.

**N4** — untouched. No adapter learns about MCP, and `adapters/base.py` needs no change.[^base]

**Local only.** stdio, one model per run, no auth, no hosting — the constitution's MVP
scope.[^constitution] FR-10 is honoured by keeping tool bodies free of process-local assumptions;
the SDK already ships `run_streamable_http_async`, so remote is a transport swap.

**Trust-boundary artifacts** in scope, all planned: `pyproject.toml`, and `docs/NN-*.md` —
`03-setup-workflow.md`, `07-code-map.md`, `09-data-modeling.md`. The constitution is not touched.

# Approach

**One module, two tools, and no new way to reach data.**

`src/semantiql/server.py` builds an `MCPServer`, registers two read-only tools, and runs it over
stdio. Both tools close over a model and an adapter opened once at startup. The module is a
*caller*, sitting beside `cli.py` at the top level exactly as the code map places
callers.[^code-map] [^clarifications]

**`describe_model`** returns the model as data: per table, the dimensions, measures and metrics
with each one's `label` and `description`. This is the first consumer of those two fields, and it
is what lets Claude resolve "sales channel" to `channel` without guessing.[^model] [^data-modeling]

**`query`** takes a `sql` string, calls `run`, and returns one pydantic shape either way — the
answer with its columns, rows and the physical SQL, or `refused` with the reason. One return type
means the client never has to guess which shape it got.[^run]

**Startup is where failure belongs.** The model is loaded and the adapter opened before the
server accepts a request, so a bad model or an unreachable database exits with a message rather
than producing a server that answers every question with an error (FR-8).

**The CLI gains `serve`.** It reuses `_open_adapter` and the existing `--datasource` / `--dsn` /
`--database` flags, so a Postgres server is configured exactly as a Postgres query is, and
`serve` is removed from `NOT_YET_IMPLEMENTED` in the same change.[^cli]

**Tests drive the server in-process** — `list_tools()` and `call_tool()` under `anyio.run`, with no
subprocess, no GUI and no new dev dependency.[^clarifications]

# Architecture decisions

**AD-1 — one return model per tool, with `refused` as a field.** Not two types, not an exception.
A client that must branch on the *shape* of a result will eventually branch wrongly; a client
branching on a boolean field cannot. The model also generates the tool's `output_schema`, so the
contract is published rather than described.[^clarifications]

**AD-2 — the adapter is opened at startup and closed on shutdown, via the SDK's `lifespan`.**
`MCPServer.__init__` accepts a `lifespan` async context manager (probe-confirmed), which is the
SDK's own answer to "hold shared state for the server's life". Rejected: module-level globals,
which make the server untestable in-process because two tests would share one adapter.

**AD-3 — `execute` ends its transaction after fetching, in `adapters/postgres.py`.** Q5's measured
fix. It goes in the adapter rather than the server because the property being protected — this
connection does not hold a snapshot open — belongs to the connection, and a server that had to
remember to release it would be a rule rather than a guarantee. DuckDB needs no equivalent.

**AD-4 — the server's `instructions` teach the dialect.** `MCPServer` accepts `instructions`,
which the client shows the model. Spending it on *what semantic SQL is and what is refused* is the
cheapest accuracy work available: the alternative is Claude discovering the supported subset by
collecting refusals, which costs a round trip each (FR-6).

**AD-5 — `--print-config` emits the Claude Desktop JSON with absolute paths resolved.** Q8. The
model path and interpreter path are the two things a human copies wrongly, and they are the two
things the running process already knows.

**AD-6 — no `doctor` tool, and that is a product decision rather than an omission.** Recorded here
because it will be proposed: the chat surface belongs to someone who did not write the model, and
handing them a model-debugging tool invites them to try to fix it.

# Repository Impact Map

## Files to add

- `src/semantiql/server.py` — `build_server(model, adapter) -> MCPServer` plus `serve(...)`.
  Two `@tool`-registered functions, `ToolAnnotations(read_only_hint=True)` on both, pydantic
  return models, and the `instructions` text from AD-4. Kept split so tests build a server
  without running one.
- `tests/test_server.py` — tool registration, both input schemas, the annotations, an answered
  question, a refusal carrying its reason, a bad-argument `ToolError`, and that
  `describe_model` surfaces `label` and `description`. No database: DuckDB over the retail CSV.

## Files to modify

- `pyproject.toml` — add `mcp>=2,<3` to `dependencies`; add `"mcp"` to `keywords`. **No mypy
  override expected** — the SDK ships types; verify rather than assume.[^pyproject]
- `src/semantiql/cli.py` — add the `serve` verb routing to `server.serve`, add `--print-config`,
  and **remove `serve` from `NOT_YET_IMPLEMENTED`** if present (it currently lists only `init`).
  Reuse `_open_adapter` unchanged.[^cli]
- `src/semantiql/adapters/postgres.py` — AD-3, end the transaction after fetching in
  `execute`.[^postgres-adapter]
- `docs/09-data-modeling.md` — the note saying `label` and `description` are "written but never
  read" **becomes false** and must change in this same commit. It is the sharpest row here: leaving
  it would leave the docs asserting the opposite of the code. **Trust-boundary.**[^data-modeling]
- `docs/03-setup-workflow.md` — Flow A step 5 and Flow B stop being aspirational; the "what doctor
  does not do yet" note about sample questions needs revisiting. **Trust-boundary.**[^setup-workflow]
- `docs/07-code-map.md` — the src tree gains `server.py`, and the "where does my change go?" table
  gains a row for a new tool. **Trust-boundary.**[^code-map]
- `docs/10-adopting-semantiql.md` — its "you cannot hand this to a non-technical colleague yet"
  warning is the reason this spec exists; it needs the Claude Desktop path added.[^adopting]
- `README.md` — the roadmap marks the MCP server shipped, and the "not built yet" sentence drops
  it.[^readme]
- `AGENTS.md` — "Not yet built" drops the MCP server; the supported-surface paragraph gains the
  two tools. `CLAUDE.md` is a symlink and is **not** a second edit.[^agents]

## Files not touched, but adjacent

- `src/semantiql/engine/` — **no change**, and that is the N1 evidence. The server is a caller.
- `src/semantiql/adapters/base.py` — no change. `close()` is already on the Protocol (spec 010), so
  the lifespan can release the adapter without widening the seam again.[^base]
- `src/semantiql/doctor.py` — no change; AD-6 keeps it off the chat surface.
- `.github/workflows/ci.yml`, `compose.yaml` — no change. The server tests need no database.

# Open research questions

- **OQ-1 — does `mcp` need a mypy override?** The SDK is pydantic-based and should ship `py.typed`,
  as psycopg did. Unverified until `uv run mypy` runs against the real import; a needed override is
  a finding worth recording, not a silent addition.
- **OQ-2 — resolved at plan time.**[^mcp-client-docs] The block is
  `{"mcpServers": {"<name>": {"command": …, "args": [...], "env": {…}}}}`, living at
  `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS and
  `%APPDATA%\Claude\claude_desktop_config.json` on Windows. The documentation's own
  troubleshooting section names **relative paths** as a top cause of a server failing to appear,
  which is exactly what AD-5 exists to prevent — so `--print-config` resolves every path before
  printing.
- **OQ-3 — is `instructions` actually surfaced to the model by Claude Desktop?** It is in the
  protocol and the SDK accepts it. If a client ignores it, AD-4's accuracy argument weakens and the
  dialect guidance may need to move into the tool descriptions instead. Cheap to hedge: keep the
  essential rules in the `query` tool's description too.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N5, N6; the local-first MCP roadmap decision; the trust-boundary list naming the manifest and `docs/NN-*.md`.
[^clarifications]: `clarifications.md` — Q1..Q8; Q3, Q5 and Q6 measured against `mcp` 2.0.0 and PostgreSQL 17.10.
[^run]: `src/semantiql/engine/run.py` — `run(sql, model, adapter) -> Result | Refusal`, and `Result(columns, rows, sql)`.
[^cli]: `src/semantiql/cli.py` — `_open_adapter`, `NOT_YET_IMPLEMENTED`, and the documented exit codes.
[^model]: `src/semantiql/knowledge/model.py` — `Dimension`, `Measure`, `Metric`, each with `label` and `description`.
[^postgres-adapter]: `src/semantiql/adapters/postgres.py` — `execute`'s cursor block and the `autocommit=False` comment.
[^base]: `src/semantiql/adapters/base.py` — the Protocol, including `close()` added by spec 010.
[^data-modeling]: `docs/09-data-modeling.md` — the note that `label` and `description` are never read.
[^code-map]: `docs/07-code-map.md` — the `src/` tree and the "where does my change go?" table.
[^setup-workflow]: `docs/03-setup-workflow.md` — Flow A step 5, Flow B, and the doctor caveat.
[^adopting]: `docs/10-adopting-semantiql.md` — the "read this before you start" section warning that the chat interface does not exist yet.
[^readme]: `README.md` — the roadmap table and the sentence listing what is not built.
[^agents]: `AGENTS.md` — the "Not yet built" list and the supported-constructs paragraph; `ls -l CLAUDE.md` shows the symlink.
[^mcp-client-docs]: modelcontextprotocol.io, "Connect to local MCP servers" — the `mcpServers` block, its location per OS, and the absolute-path requirement, read at plan time.
[^pyproject]: `pyproject.toml` — `dependencies`, `keywords`, and the `duckdb` mypy override as precedent.
