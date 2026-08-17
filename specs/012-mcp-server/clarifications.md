---
type: Clarifications
title: MCP server — clarifications
description: 8 ambiguities resolved before planning; five settled by probing the installed SDK and a live Postgres rather than by reading documentation.
resource: specs/012-mcp-server/clarifications.md
tags: [sdd, clarifications, mcp]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T01:05:00+07:00' }
sources:
  - id: probe
    resource: clarifications.md
    title: Live probe of mcp 2.0.0 and PostgreSQL 17.10 run at clarify time — output transcribed in Q3, Q5, Q6
    last_modified: 2026-08-18
  - id: spec-004
    resource: ../004-filter-by-dimension/spec.md
    title: Where the request contract was decided to stay SQL text rather than become structured
    last_modified: 2026-08-16
  - id: run
    resource: ../../src/semantiql/engine/run.py
    title: The chokepoint, and Refusal returned rather than raised
    last_modified: 2026-08-15
  - id: postgres-adapter
    resource: ../../src/semantiql/adapters/postgres.py
    title: The autocommit=False comment naming a server mode as the case to revisit
    last_modified: 2026-08-18
  - id: cli
    resource: ../../src/semantiql/cli.py
    title: _open_adapter and the existing flags a serve verb should reuse
    last_modified: 2026-08-18
status: stable
---

Every decision below was made **by the agent**, autonomously. Five were settled by running the
installed SDK or a live database rather than by reading docs, and two of those contradicted what
the documentation implied.

## Q1: Does the query tool take semantic SQL, or structured arguments?

- (a) A `sql` string — the LLM writes semantic SQL
- (b) Structured JSON — `{table, measures, dimensions, filters, grain, limit}`

**Chosen: (a) — decided by the agent from spec 004's recorded decision.** That spec settled
"request contract stays SQL text: grow the subset rather than move to a structured
request".[^spec-004] Nothing about the caller changing from a human to an LLM weakens it, and two
things strengthen it: an LLM is *better* at SQL than at filling a bespoke JSON schema, and (b)
would need its own validation path — a second way in, which is exactly what N1 forbids.

The deferred question was whether an LLM-facing caller changes the answer. Measured against what
the code already provides: `validate` accepts text and returns either a checked request or a
`Refusal` with a reason.[^run] Under (b) that reason would have to be re-expressed against JSON
field paths, and every refusal message in the codebase would need rewriting.

## Q2: Which tools?

- (a) `query` and `describe_model`
- (b) Those plus a `doctor` tool
- (c) `query` only

**Chosen: (a) — decided by the agent from the spec's scope section.** (c) fails immediately: with
no way to discover entity names, the LLM guesses, and every first question is a refusal. (b) is
rejected in the spec — checking a model is the analyst's job and the analyst has a CLI; putting
it in the chat invites a business user to debug a model they did not write.

`describe_model` is also what finally reads `label` and `description`, so the two tools together
close the gap the spec's Why section names.

## Q3: How does a refusal reach the client?

- (a) Raise, so the call is marked an error
- (b) Return a pydantic model carrying `refused` and `reason`

**Chosen: (b) — measured, and the documentation implied otherwise.**[^probe] A refusal is the
designed answer, not a failure — `run` returns it rather than raising, and the CLI prints it as a
distinct outcome from a crash. Marking it an error would tell Claude "the tool broke" when the
truthful message is "the question cannot be answered from this model, here is why".

The mechanism took probing. Returning a plain `dict` leaves `structured_content` **empty**, and
forcing `structured_output=True` on a `dict` return is an outright error:

```
InvalidSignature: return type <class 'dict'> is not serializable for structured output
```

A **pydantic return type** produces both an `output_schema` on the tool and populated
`structured_content` on the result, plus a JSON text fallback:

```
output props      : ['refused', 'reason', 'sql', 'columns', 'rows']
structured_content: {'refused': True, 'reason': "'profit' is not defined on table 'orders'", …}
```

pydantic is already a dependency, so this costs nothing. Also learned: v2 of the SDK renamed the
field to `input_schema`, not `inputSchema`.

## Q4: Where does the module live?

- (a) `src/semantiql/mcp/`
- (b) `src/semantiql/server.py`

**Chosen: (b) — decided by the agent from the code map's own logic.** A package named `mcp`
sitting next to a dependency named `mcp` is a trap: absolute imports resolve correctly, but every
reader has to work out which one a line means. More importantly the code map places callers —
`cli.py` — at the top level beside the layers rather than inside one, and a server is a caller.
It reaches data only through `run`, exactly as the CLI does.[^cli]

## Q5: One connection for the server's whole life, or one per request?

- (a) One, opened at startup (FR-7)
- (b) One per request
- (c) One, with the transaction closed after each answer

**Chosen: (c) — measured, and (a) as written would have been a real regression.**[^probe]
`adapters/postgres.py` says `autocommit=False` is what enforces read-only, and notes the cost —
an `idle in transaction` connection — as harmless "for a CLI that opens, asks and closes", with
an explicit instruction to revisit "if a server mode ever holds adapters open".[^postgres-adapter]
This is that server mode.

Measured against a live server:

```
fresh                     : idle
after a SELECT            : idle in transaction     <- pins a snapshot, blocks vacuum
after rollback()          : idle                    <- released
read_only after rollback  : still enforced (ReadOnlySqlTransaction)
still usable              : [(2,)]
```

So ending the transaction after fetching gives (a)'s single connection without the cost.
`rollback()` is semantically free here because the transaction is read-only — there is nothing to
undo — and read-only enforcement survives it, which was the thing worth checking rather than
assuming. (b) is rejected as a connection per question for no benefit.

**This is an adapter change**, so it is flagged: `adapters/postgres.py` gains an end-of-transaction
step. It improves the CLI path too, and changes no answer.

## Q6: How is the server tested without Claude Desktop?

- (a) In-process, calling `list_tools()` and `call_tool()` on the server object
- (b) Spawn the server as a subprocess and speak the protocol over stdio
- (c) A memory-stream client session

**Chosen: (a) — measured.**[^probe] It exercises what matters: registration, the generated input
schema, the annotations, and the tool body — while `anyio.run` drives the coroutines from an
ordinary sync test, so **no pytest plugin and no new dev dependency** (`anyio` arrives
transitively with `mcp`). Probed working:

```
tool  : query | readOnly: True
schema: {'sql': {'title': 'Sql', 'type': 'string'}} required: ['sql']
```

(b) is the most faithful and the most fragile — a subprocess, a handshake and a timeout in the
gate. (c) is available (`create_client_server_memory_streams` exists) and is the right escalation
if transport-level behaviour ever needs testing; it is not needed to test tools.

Also learned: bad arguments **raise** `mcp.server.mcpserver.exceptions.ToolError` from
`call_tool` rather than returning an error result, so tests assert on the exception.

## Q7: `mcp` or `mcp[cli]`?

- (a) Plain `mcp`
- (b) `mcp[cli]`, which adds `mcp dev` / `mcp run` / `mcp install`

**Chosen: (a) — decided by the agent from the constitution's small-dependency rule.** The `cli`
extra pulls `typer` and `python-dotenv` to provide developer conveniences this project does not
need: it has its own CLI and its own gate. Worth recording what the base package already costs,
since it is not small — `httpx2`, `jsonschema`, `pydantic` (already present), `pyjwt[crypto]`,
`uvicorn`, `sse-starlette`. `uvicorn` and `sse-starlette` exist for HTTP transports this spec does
not use; they arrive anyway, and that is the price of the SDK the constitution names.

## Q8: How does the analyst register the server with Claude Desktop?

- (a) Documentation only
- (b) A `--print-config` flag that emits the JSON block to paste

**Chosen: (b), and it amends FR-12 — decided by the agent from the ≤15-minute setup rule.** That
rule requires every step to carry fix instructions, and the step most likely to be got wrong is an
**absolute path** to a model file and an interpreter inside a hand-copied JSON block. Printing it,
already filled in, removes the one part a human cannot check by eye. It is a few lines and no new
dependency.

FR-12 previously said only that documentation covers registration. It now also requires the
command to emit a ready-to-paste configuration.

[^probe]: Live probe run at clarify time against `mcp` 2.0.0 in a throwaway venv and PostgreSQL
    17.10 on localhost; the transcripts in Q3, Q5 and Q6 are its output.
[^spec-004]: `specs/004-filter-by-dimension/spec.md` — the recorded decision that the request
    contract stays SQL text.
[^run]: `src/semantiql/engine/run.py` — the single path to the data, and `Refusal` returned
    rather than raised.
[^postgres-adapter]: `src/semantiql/adapters/postgres.py` — the `autocommit=False` comment naming
    a server mode as the case to revisit.
[^cli]: `src/semantiql/cli.py` — `_open_adapter`, and the CLI as a caller that reaches data only
    through `run`.
