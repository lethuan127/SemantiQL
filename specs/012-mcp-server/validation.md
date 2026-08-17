---
type: Validation
title: MCP server — validation
description: Acceptance criteria traced to FR-1..FR-12, walked against a real stdio subprocess and a live Postgres.
resource: specs/012-mcp-server/validation.md
tags: [sdd, validation, mcp]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T01:55:00+07:00' }
status: stable
---

# Acceptance criteria

- **AC-1** (FR-1) — `semantiql serve` runs an MCP server over stdio, and a client speaking the
  real protocol to it as a subprocess completes `initialize` and lists tools.
- **AC-2** (FR-2) — `query` answers a semantic SQL question, and **nothing in `server.py`
  reaches an adapter except through `run`**. Proven by inspection of the module, not asserted.
- **AC-3** (FR-3) — `describe_model` returns tables with dimensions, measures and metrics,
  including `label` and `description`, and does **not** expose physical column names.
- **AC-4** (FR-4) — a refused question returns `refused: true` with its reason, as a normal
  result. It does not raise, and the reason survives intact — including a suggestion.
- **AC-5** (FR-5) — both tools carry `read_only_hint: true` and `destructive_hint: false`.
- **AC-6** (FR-6) — the server's `instructions` reach the client and name the dialect, the
  no-`GROUP BY` rule, and that a refusal is repairable.
- **AC-7** (FR-7) — the model is loaded and the adapter opened once per run, and released on
  shutdown. On Postgres the connection does not sit `idle in transaction` between answers.
- **AC-8** (FR-8) — an unloadable model exits 2 and an unreachable datasource exits 3, both
  before the server accepts a request.
- **AC-9** (FR-9) — an adapter failure mid-session is a failed call with its reason, distinct
  from a refusal, and the server stays up.
- **AC-10** (FR-10) — no tool body depends on sharing a process with its caller or on the local
  filesystem beyond loading the model at startup.
- **AC-11** (FR-11) — the server suite runs with no Claude Desktop, no subprocess, no database
  and no new dev dependency.
- **AC-12** (FR-12) — `serve --print-config` emits a valid `mcpServers` block with every path
  absolute; README, `docs/03`, `docs/07`, `docs/09` and `docs/10` record what shipped.

# Non-functional acceptance

- `./scripts/verify.sh` green with and without a Postgres reachable.
- No mypy override for `mcp` (OQ-1).
- `engine/` unchanged — the server is a caller.

# Results — walked 2026-08-18

Every AC met. Verified against a real stdio subprocess and PostgreSQL 17.10.

| AC | Outcome | Evidence |
|---|---|---|
| AC-1 | met | real subprocess handshake: `server: semantiql 0.0.2`, tools listed |
| AC-2 | met | `server.py` contains exactly one data call — `run(sql, model, adapter)`; grep for `adapter.` in the module finds only `adapter.close()` |
| AC-3 | met | `revenue` returns label `Revenue` and its description; `Entity` has **no** `column` field, asserted structurally |
| AC-4 | met | `refused: True, reason: "'profit' is not defined on table 'orders'."`; a typo returns the suggestion `channel` |
| AC-5 | met | `[('describe_model', True), ('query', True)]` over the wire |
| AC-6 | met | `initialize` returned non-empty instructions; content asserted for `refused`, `describe_model`, `GROUP BY` |
| AC-7 | met | opened by `_serve` before the loop, closed in `serve`'s `finally`; new test asserts the Postgres backend is `idle`, not `idle in transaction` |
| AC-8 | met | `_serve` returns 2 on `ModelError` and 3 on `AdapterError`, before `build_server` |
| AC-9 | met | `AdapterError` → `ToolFailure`, raised as a failed call; a refusal never raises |
| AC-10 | met | tools close over a model and an adapter passed in; `build_server` is transport-agnostic and the SDK's `run_streamable_http_async` needs no change here |
| AC-11 | met | 20 tests via `anyio.run`; `anyio` arrives transitively with `mcp` |
| AC-12 | met | config output is absolute for interpreter and model; five documents updated |

**Non-functional:** gate green both ways — 288 unit, 27 e2e, 58 pg, 0 OKF errors. **OQ-1
resolved: no mypy override needed**, so unlike `duckdb` this dependency adds no strict-mode
exemption. `engine/` untouched.

## Findings and judgement calls

1. **OQ-3 was hedged rather than resolved.** Whether Claude Desktop surfaces `instructions` to
   the model is a client behaviour this repo cannot assert. The handshake confirms the server
   *sends* them. So the essential rules are duplicated into the `query` tool's description, which
   clients do show — the hedge the plan called for.
2. **A cosmetic cross-engine difference in `query` output.** Cells are stringified, so DuckDB's
   float `956.5` prints as `"956.5"` where Postgres's `Decimal` prints `"956.50"`. Same value,
   different text. Stringifying is deliberate — JSON has no `Decimal`, and a float standing in
   for one is how money loses a penny — but the two engines are not textually identical. Not a
   wrong number; worth knowing before anyone asserts on the string.
3. **`--print-config` names `python -m semantiql` rather than the console script.** A new
   `__main__.py` exists for this. `sys.executable` is always an absolute interpreter path,
   whereas a console script's location depends on the install and on a PATH that Claude Desktop
   does not inherit.
4. **The two-tool surface is asserted, deliberately.** `test_exactly_two_tools_are_exposed`
   fails if a third is added. That is not pedantry: the surface *is* the enforcement boundary,
   and widening it should be a decision someone makes rather than a diff that slips by.

## Carried forward

- **Local only.** The end user needs SemantiQL installed and database access, so this is not yet
  the non-technical colleague. Recorded in `docs/03` and `docs/10` rather than glossed; remote
  mode is post-MVP by the constitution.
- **`rate_answer` is not built.** `docs/04-self-improvement.md` names it as the tool that feeds
  verified examples. That tier is a later spec, and N6 keeps it strictly separate from the model.
