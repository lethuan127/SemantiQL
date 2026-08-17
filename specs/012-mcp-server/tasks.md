---
type: Tasks
title: MCP server — tasks
description: 11 tasks plus two gate tasks — dependency, the module and its two tools, the serve verb, in-process tests, the adapter's end-of-transaction step, then the docs that currently assert the opposite.
resource: specs/012-mcp-server/tasks.md
tags: [sdd, tasks, mcp]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T01:30:00+07:00' }
sources:
  - id: plan
    resource: plan.md
    title: The approved plan, AD-1..AD-6, the impact map and OQ-1..OQ-3
    last_modified: 2026-08-18
  - id: clarifications
    resource: clarifications.md
    title: The measured decisions each task implements
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T01:32:00+07:00', checkpoint: 3,
      basis: '13 tasks in dependency order; 2 [P] groups checked file-by-file and disjoint, CLAUDE.md excluded by name as a symlink. T1 carries OQ-1 as a finding-not-a-fix. T7 requires a test asserting the backend state, since nothing else would catch that regression. T9 is flagged as the sharpest row: docs/09 currently asserts the opposite of what the code will do' }
status: stable
---

11 tasks plus two gate tasks, derived from the impact map.[^plan] Two `[P]` groups, both checked
for file overlap.

# Phase 1 — dependency

## ✅ T1. Add the SDK

- **Files:** `pyproject.toml`
- **Do:** add `mcp>=2,<3` to `dependencies`; add `"mcp"` to `keywords`. Plain `mcp`, **not**
  `mcp[cli]` (Q7).[^clarifications]
- **Verification:** `uv sync && uv run mypy` clean. **OQ-1:** if mypy demands an override, that is
  a finding to record in the report, not a line to add quietly.

# Phase 2 — the server

## ✅ T2. The return models

- **Files:** `src/semantiql/server.py` (new)
- **Depends on:** T1
- **Do:** AD-1 — one pydantic model per tool. `Answer` carries `refused: bool`, `reason: str | None`,
  `sql: str | None`, `columns`, `rows`. A pydantic return type is what populates
  `structured_content` and generates `output_schema`; a plain `dict` does neither and forcing it
  raises `InvalidSignature` (Q3, measured).[^clarifications]
- **Verification:** covered by T6.

## ✅ T3. `describe_model`

- **Files:** `src/semantiql/server.py`
- **Depends on:** T2
- **Do:** return each table's dimensions, measures and metrics **including `label` and
  `description`** — the first consumer of those fields. Read-only annotation. Rows must be
  JSON-safe.
- **Verification:** T6 asserts a label and a description reach the caller.
- **Constitution check:** N1 — reads the model only; never touches the adapter.

## ✅ T4. `query`

- **Files:** `src/semantiql/server.py`
- **Depends on:** T2
- **Do:** take `sql: str`, call `engine.run.run`, and map `Result` → answer / `Refusal` →
  `refused` + reason. Read-only annotation. **Nothing else may reach the adapter.** Wrap
  `AdapterError` so one bad question fails the call and leaves the server up (FR-9).
- **Verification:** T6 covers answer, refusal and adapter-error paths.
- **Constitution check:** N1 and N2 — the single path to data, and a refusal that keeps its reason.

## ✅ T5. `build_server` and `serve`

- **Files:** `src/semantiql/server.py`
- **Depends on:** T3, T4
- **Do:** `build_server(model, adapter) -> MCPServer` registers the tools and sets `instructions`
  (AD-4: what semantic SQL is, and what is refused — keep the essential rules in the `query`
  description too, hedging OQ-3). `serve(...)` loads the model, opens the adapter, and runs stdio,
  releasing the adapter on shutdown (AD-2). Splitting the two is what lets tests build without
  running.
- **Verification:** `uv run mypy` clean; T6 builds a server without starting one.

# Phase 3 — the caller and the adapter

## ✅ T6. `[P]` In-process tests

- **Files:** `tests/test_server.py` (new)
- **Depends on:** T5
- **Do:** `anyio.run` driving `list_tools()` and `call_tool()` (Q6). Cover: both tools registered
  and read-only; the generated input schema; an answered question; a refusal carrying its reason
  **and not raising**; a bad argument raising `ToolError`; `describe_model` surfacing `label` and
  `description`. DuckDB over the retail CSV — no database, no subprocess, no GUI.
- **Verification:** `uv run pytest tests/test_server.py` green with nothing installed.

## ✅ T7. `[P]` End the transaction after fetching

- **Files:** `src/semantiql/adapters/postgres.py`
- **Depends on:** T1
- **Do:** AD-3 — after fetching results, end the read-only transaction so the connection returns
  to `idle` instead of `idle in transaction`. Comment *why*: a server holding this open pins a
  snapshot and blocks vacuum, and `rollback` is free here because the transaction is read-only.
  Measured: read-only enforcement survives it and the connection stays usable.[^clarifications]
- **Verification:** existing `pg` suite green; add a test asserting the backend state is `idle`
  after a query, which is the only thing that would catch a regression.

> **`[P]` group 1 — T6 and T7 are disjoint:** {`tests/test_server.py`} · {`adapters/postgres.py`}.
> Neither reads the other; T7's own test lands in the existing Postgres suite.

## ✅ T8. The `serve` verb and `--print-config`

- **Files:** `src/semantiql/cli.py`
- **Depends on:** T5
- **Do:** route `serve` to `server.serve`, reusing `_open_adapter` and the existing flags. Add
  `--print-config`, emitting the `mcpServers` block with **every path resolved absolute** — the
  client docs name relative paths as a top cause of a server failing to appear (OQ-2).
- **Verification:** existing CLI tests pass unmodified; `--print-config` output parses as JSON and
  contains no relative path.

# Phase 4 — the docs that currently say the opposite

## ✅ T9. `[P]` The two claims this falsifies

- **Files:** `docs/09-data-modeling.md`, `docs/03-setup-workflow.md`
- **Depends on:** T6
- **Do:** `09` states that `label` and `description` are "written but never read" — **now false**,
  and the sharpest row in the map: leaving it would have the docs asserting the opposite of the
  code. `03`'s Flow A step 5 and Flow B stop being aspirational, and its note that doctor cannot
  yet run sample questions needs revisiting. **Both trust-boundary artifacts.**
- **Verification:** neither file claims anything the code contradicts.

## ✅ T10. `[P]` Code map and adoption guide

- **Files:** `docs/07-code-map.md`, `docs/10-adopting-semantiql.md`
- **Depends on:** T6
- **Do:** the `src/` tree gains `server.py` as a caller beside `cli.py`, and the change-location
  table gains a row for a new tool. `10`'s "you cannot hand this to a non-technical colleague yet"
  warning is the reason this spec exists — replace it with the Claude Desktop path.
  **`07` is trust-boundary.**
- **Verification:** the code map's tree matches `ls src/semantiql/`.

## ✅ T11. `[P]` README and agent brief

- **Files:** `README.md`, `AGENTS.md`
- **Depends on:** T6
- **Do:** the roadmap marks the MCP server shipped and the not-built sentence drops it; `AGENTS.md`
  drops it from "Not yet built" and records the two tools. **Do not edit `CLAUDE.md`** — symlink.
- **Verification:** `git status` shows `AGENTS.md` changed and `CLAUDE.md` not.

> **`[P]` group 2 — T9, T10, T11 touch three disjoint sets:** {`09`, `03`} · {`07`, `10`} ·
> {`README.md`, `AGENTS.md`}. No file appears twice; `CLAUDE.md` excluded by name as a symlink.

## ✅ TF. Final verify

- **Files:** —
- **Depends on:** T1–T11
- **Do:** `./scripts/verify.sh`, with and without a Postgres reachable.
- **Verification:** green both ways.

## ✅ TV. Validation pass

- **Files:** `validation.md`
- **Depends on:** TF
- **Do:** walk every AC. **FR-2 is the one to prove rather than tick**: show that nothing in
  `server.py` reaches an adapter except through `run`.
- **Verification:** every AC met, or recorded as not met with why.

[^plan]: `plan.md` — the impact map, AD-1..AD-6, and OQ-1..OQ-3.
[^clarifications]: `clarifications.md` — Q1..Q8; Q3, Q5 and Q6 measured.
