# Architecture — 4 layers

```
┌─────────────────────────────────────────────┐
│  AI agent (Claude via MCP, or any LLM)      │
│  asks in semantic SQL                       │
└──────────────────┬──────────────────────────┘
                   ▼
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
