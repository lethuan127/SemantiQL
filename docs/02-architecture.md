# Architecture

## Three components

Start here, because the four layers below sit inside the third one. A working SemantiQL is three
things, and it is worth naming them separately because they answer three different questions and
they live in three different places.

```
┌───────────────────────────────┐   ┌───────────────────────────────┐
│ 1. Claude + skill             │   │ 2. Knowledge                  │
│                               │   │                               │
│ HOW to work: call             │   │ WHAT the words mean:          │
│ describe_model first, write   │──▶│ dimensions, measures,         │
│ the supported subset, repair  │   │ metrics — one agreed          │
│ a refusal, and stop at a      │   │ definition each               │
│ definition that is missing    │   │                               │
│                               │   │                               │
│ plugin/skills/semantiql/      │   │ the semantic model YAML       │
│ SKILL.md — in git             │   │ — in git                      │
└───────────────────────────────┘   └───────────────────────────────┘
                │  two read-only tools              │  resolves against
                ▼                                   ▼
┌───────────────────────────────────────────────────────────────────┐
│ 3. Execution — what may actually be run                           │
│                                                                   │
│ describe_model · query            src/semantiql/server.py         │
│ ───────────────────────────────────────────────────────────────── │
│ the four layers below                                             │
└───────────────────────────────────────────────────────────────────┘
```

**Why the first one is a component and not a footnote.** It decides whether Claude looks up the
vocabulary before guessing, and whether a refusal becomes a repaired query or an apology. That is
behaviour, it is version-controlled, and it is reviewable in a pull request — so it belongs in the
architecture rather than being assumed. It used to be a string literal inside `server.py`; spec 013
gave it a file.

**Why the third one is deliberately small.** Two read-only tools, and nothing else. A skill telling
Claude to run the CLI in a shell would have been easier to build and would also have handed it a
shell, from which the database is reachable by any route. The tool surface *is* the enforcement
boundary — which is why widening it is a decision rather than a convenience.

**Where the boundary between 1 and 2 is absolute.** The skill may teach Claude anything about *how
to ask*. It may never let Claude change what a number *means* while answering a question. A missing
metric is reported and the conversation stops; adding it is a reviewed change to a file in git (N6).
Blur that line and "revenue means one thing here" stops being true.

### Two modes, and why they get different tool surfaces

Claude does two different jobs here, and conflating them is how the boundary above would quietly
break.

| | **Building** the model | **Asking** a question |
|---|---|---|
| Who is there | the analyst, in the conversation | anyone, often alone |
| Where | Claude Code, in a checkout | Claude Desktop, over the MCP server |
| Tools | a shell and file writes — `semantiql inspect`, `doctor`, editing YAML | `describe_model` and `query`, and nothing else |
| May component 2 change | yes, that is the task | **no** |
| What stops a wrong definition | the analyst reads the diff, and `doctor` proves it matches the database | it cannot arise: there is no path to the file |

**Building deliberately has the shell that asking deliberately lacks.** Spec 016 gave the skill a
discovery loop: read the catalogue with `inspect`, ask the analyst the handful of things a schema
cannot answer, write one YAML per table, loop on `doctor`. That is a change to a definition — and it
is fine, because the human who owns the definition asked for it and is reading the result. The same
capability reached from a question would be the exact failure N6 forbids, which is why the *asking*
surface is two read-only tools with no file access and no shell, structurally rather than by
instruction.

So the rule is not "Claude never writes the model". It is **Claude never writes the model as a side
effect of answering**. The skill says so in those words, and a test asserts the sentence is still
there.

## The four layers, inside execution

```
┌─────────────────────────────────────────────┐
│  1. Semantic Knowledge                      │
├─────────────────────────────────────────────┤
│  2. SQL Engine                              │
├─────────────────────────────────────────────┤
│  3. Data Governance                         │
├─────────────────────────────────────────────┤
│  4. Database                                │
└─────────────────────────────────────────────┘
```

## 1. Semantic Knowledge

The business-friendly interface: **dimensions, measures, metrics, virtual views**. The AI works against this layer instead of raw tables.

- Defined in **one YAML file** — goes into git, reviewable, diffable.
- **Database-agnostic** — switching databases does not require rewriting the model (unlike raw SQL).

## 2. SQL Engine

Translates semantic SQL into physical (raw) SQL that runs on the actual database.

- Generates SQL in one canonical dialect, then transpiles to the target dialect via **sqlglot**.
- Includes the **validation layer**: every query is checked against the semantic model before execution; queries that can't be verified are blocked or repaired.

## 3. Data Governance

Labels, descriptions, access control, caching.

## 4. Database

The data source: raw data and data modeling. MVP targets DuckDB and Postgres (see [05-datasources.md](05-datasources.md)).

## Why validation is the centerpiece

From Allemang & Sequeda ([arXiv:2405.11706](https://arxiv.org/abs/2405.11706), verified against the original paper):

| Setup | Accuracy |
|---|---|
| LLM over raw SQL schema | ~16% |
| + knowledge graph | ~54% |
| + ontology-based query checking | ~72% |

**The validation layer (check + repair) creates the most value — not the generation layer.** This shapes both the architecture and the MVP benchmark.

## Where SemantiQL sits in the "semantic layer" landscape

The term currently has three meanings (see [06-research-notes.md](06-research-notes.md)): (1) formal RDF/OWL ontologies with reasoners, (2) SQL-native virtual models over warehouse tables, (3) governed metric layers. SemantiQL is in the (2)–(3) space.
