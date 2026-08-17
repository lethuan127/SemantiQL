---
type: Spec
title: A local MCP server, so Claude can ask the questions
description: The interface the whole product was designed for — Claude writes semantic SQL, reads a refusal, and repairs. Today the only way in is a CLI that takes SQL, which serves nobody the product is for.
resource: specs/012-mcp-server/spec.md
tags: [sdd, spec, mcp, interface]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T00:49:05+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time — MCP named in the tech stack, local named in the roadmap
    last_modified: 2026-08-18
  - id: product
    resource: ../docs/01-product.md
    title: Primary users, and the interface decision that names Claude Desktop as the MVP surface
    last_modified: 2026-08-15
  - id: setup-workflow
    resource: ../docs/03-setup-workflow.md
    title: Flow B, the end-user flow this unblocks; and step 5's sample questions, still unbuilt
    last_modified: 2026-08-17
  - id: run
    resource: ../src/semantiql/engine/run.py
    title: The chokepoint every path to data goes through, and the Refusal it returns
    last_modified: 2026-08-15
  - id: data-modeling
    resource: ../docs/09-data-modeling.md
    title: Where label and description are documented as written-but-never-read
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T00:49:05+07:00', checkpoint: 1,
      basis: '12 FRs, each testable. Scope set by what the repo already half-built rather than by ambition — FR-3 names label/description, which docs/09 records as written-but-never-read, and FR-4 follows run.py already returning Refusal rather than raising. FR-10 states the path-to-remote as a constraint on implementations rather than an aspiration. The NFR on N5 flags that a long-running server is the exact case adapters/postgres.py warns about' }
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** A new external dependency, a new top-level module, and edits to the project manifest and
`docs/NN-*.md` — three trust-boundary artifacts. Also the first component that is a
**long-running process** rather than a one-shot command, which changes assumptions the adapters
were written under.

# What

An analyst runs one command to register SemantiQL with Claude Desktop. After that, a colleague
who has never seen SQL asks a question in English and gets a correct answer, or a clear
explanation of why the question cannot be answered.

```
Colleague:  What was revenue by channel last month?

Claude:     [calls describe_model]  → learns `revenue`, `channel`, `order_date` exist
            [calls query]           → SELECT revenue, channel FROM orders
                                       WHERE order_date >= '2026-07-01' AND order_date < '2026-08-01'

            Revenue by channel for July:
            web 826.50 · retail 264.49 · partner 385.25

Colleague:  And profit?

Claude:     [calls query]  → SELECT profit, channel FROM orders
                          ← refused: 'profit' is not defined on table 'orders'

            Your semantic model doesn't define profit — only revenue, order_count and
            average_order_value. Ask your data team to add it if you need it.
```

Today the only interface is a command line that takes semantic SQL. That serves the *builder*
perfectly well and serves **none of the people the product is for**.[^product]

# Why

**Semantic SQL was never meant for a human to write.** The repo's own one-line summary is that
SemantiQL sits between an LLM and a database and *the model* writes semantic SQL. Without an MCP
server there is no LLM in the loop, so the language has no author and the interface has no user.
The engine is finished for someone who cannot reach it.

**Half the accuracy argument is currently unrealised.** The founding evidence is 16% for an LLM
over a raw schema, ~54% adding a knowledge layer, **~72% adding query checking** — and that last
step is check *and repair*.[^constitution] `Refusal` already carries a reason precisely so it can
be acted on, and `run` already returns it instead of raising.[^run] But a human reading
`'profit' is not defined on table 'orders'` has to go open the YAML; an LLM reads it and retries
in the same turn. The check exists and the repair loop has no participant, so the project is
holding 54% and leaving 72% on the table.

**There is already shipped surface with no consumer.** `label` and `description` are in the model
schema, documented, and written by every model author — and `docs/09-data-modeling.md` states
plainly that nothing reads them, because the MCP server that will present the model to Claude is
not built.[^data-modeling] Same for the setup flow: step 5 promises sample questions that confirm
the *answers* are right, and that half waits on this.[^setup-workflow]

**It is the prerequisite for the benchmark, not a parallel task.** The other unbuilt MVP item is
the accuracy benchmark against raw-table querying. You cannot measure "an LLM with a semantic
layer beats an LLM with a raw schema" while no LLM can use the semantic layer.

**Scope is local, deliberately, and that has an honest cost.** The constitution puts the MVP
server on the local machine with a clear path to remote.[^constitution] `docs/03-setup-workflow.md`
records why that is second-best: local *"forces the end user's machine to connect directly to the
database — wrong fit for non-technical users."*[^setup-workflow] So MVP-local proves the loop with
people who already have database access. It does not yet deliver the colleague-with-no-credentials
story, and this spec does not claim otherwise.

# User stories

- **As a business user**, I ask "revenue by channel last month?" in Claude and get the number my
  company agrees on — so I never learn SQL or wait for an analyst.
- **As a business user**, when I ask for something the model does not define, I am told that
  plainly — so I never paste a confidently wrong figure into a deck.
- **As Claude**, I can discover what a model offers before guessing at names, and I can read why
  a request was refused and fix it myself — so a near-miss becomes a correct answer rather than
  an apology.
- **As an analyst**, I register SemantiQL with Claude Desktop in one command and hand the chat to
  a colleague — so my semantic model becomes something people use rather than a file I maintain.
- **As a maintainer**, the server is a thin wrapper over `run` with no second path to the data —
  so the guarantees three prior specs established still hold when the caller is an LLM.

# Functional requirements

- **FR-1** — A `semantiql serve` command runs an MCP server over **stdio**, the transport Claude
  Desktop launches a local server with.
- **FR-2** — A **query** tool accepts semantic SQL and returns the answer. It reaches the data
  only through `engine.run.run` — no second path, no bypass.
- **FR-3** — A **describe-model** tool returns the tables, dimensions, measures and metrics
  available, including each one's `label` and `description`, so Claude can resolve business
  vocabulary without guessing. This is the first consumer of those fields.
- **FR-4** — A refusal is returned as **a normal, structured answer carrying its reason** — not
  as a protocol error. A refusal is the designed outcome, and the reason is what makes repair
  possible.
- **FR-5** — Every tool is annotated **read-only**, so a client can see that nothing here mutates
  anything.
- **FR-6** — The server tells the client, in its own instructions, what dialect to write and what
  is refused — so Claude does not have to discover the supported subset by trial and error.
- **FR-7** — The model is loaded and the datasource opened **once per server run**, not per
  request, and released when the server stops.
- **FR-8** — A model that fails to load, or a datasource that cannot be reached, fails at
  **startup** with a message naming the cause. A server that cannot answer anything must not
  appear healthy.
- **FR-9** — An adapter error mid-session is reported to the client as a failed call with its
  reason, and the server **stays up**. One bad question does not end the conversation.
- **FR-10** — Switching to a remote transport later is a **transport change, not a rewrite**: no
  tool implementation may depend on being in the same process as the caller, or on the local
  filesystem beyond loading the model at startup.
- **FR-11** — The server is tested without Claude Desktop, by driving it in-process, so the
  suite has no manual step and no GUI dependency.
- **FR-12** — Registering with Claude Desktop is not a copy-by-hand step: the command **emits a
  ready-to-paste configuration** with absolute paths already filled in, and the docs explain where
  it goes. The README roadmap and `docs/` record the MCP server as shipped. *(Extended during
  clarify: the flag was added because an absolute path inside a hand-copied JSON block is the one
  setup step a human cannot check by eye.)*[^clarifications]

# Non-functional requirements

- **N1 (validation over generation)** — the server is a caller like any other. It routes through
  `run`, and `AGENTS.md` is explicit that a new way to query which reaches an adapter directly is
  the change most likely to be rejected.[^constitution]
- **N2 (a silently wrong number is the worst failure)** — sharper here than anywhere. Until now a
  wrong number would be read by an analyst who might notice; from now on it is read by someone who
  cannot. Every refusal must survive the trip to the client intact rather than being flattened
  into "something went wrong".[^constitution]
- **N5 (read-only by default)** — and newly load-bearing. `adapters/postgres.py` documents that
  `autocommit=False` is what enforces read-only, at the cost of an `idle in transaction`
  connection between queries — noted as harmless for a CLI that opens, asks and closes. **A
  long-running server is exactly the case that comment says to revisit**, and FR-7 puts the
  connection in that position.[^constitution]
- **Local only** — no hosting, no multi-user auth, no access control. Those belong to layer 3 and
  are out of MVP scope by the constitution; FR-10 keeps the door open without walking
  through it.[^constitution]
- **Small dependency set** — the constitution names MCP with the official Python SDK, so the
  dependency is pre-approved in kind. Its transitive weight is a plan question.[^constitution]

# Out of scope

- **Remote or shared hosting, and auth.** FR-10 preserves the path; this spec does not take it.
- **Access control per user or per column.** Layer 3, deliberately unimplemented.
- **The accuracy benchmark.** Unblocked by this, not included in it.
- **Verified-example learning.** The examples tier of the self-improvement model may update
  automatically, but it is its own spec and N6 keeps it strictly separate from the YAML tier.
- **A `doctor` tool.** Checking a model is a setup activity for the analyst, who has a CLI. Adding
  it to the chat surface invites an end user to debug a model they did not write.
- **Multi-model serving.** One model per server run. Several models means naming and routing
  decisions with no requirement behind them yet.

[^clarifications]: `clarifications.md` — 8 ambiguities resolved before planning; five measured
    against the installed SDK or a live database.
[^constitution]: `.specify/memory/constitution.md` — N1, N2, N5, N6; the tech-stack row naming MCP
    and the official Python SDK; the roadmap's local-first MCP decision; and the trust-boundary list.
[^product]: `docs/01-product.md` — primary users (analysts *and* non-technical business users who
    never see SQL), and the interface decision naming Claude Desktop as the MVP surface.
[^setup-workflow]: `docs/03-setup-workflow.md` — Flow B, step 5's unbuilt sample questions, and the
    recorded local-versus-remote trade-off.
[^run]: `src/semantiql/engine/run.py` — the single path to the data, and `Refusal` returned rather
    than raised.
[^data-modeling]: `docs/09-data-modeling.md` — `label` and `description` documented as written but
    never read, pending this server.
