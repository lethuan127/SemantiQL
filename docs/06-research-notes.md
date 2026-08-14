# Research notes

## Prior art to study

Cube, dbt Semantic Layer, MetricFlow, Malloy, MCP database servers — map the landscape and articulate SemantiQL's differentiators (validation layer + self-improving examples tier; see [02-architecture.md](02-architecture.md) and [04-self-improvement.md](04-self-improvement.md)).

## Key benchmark (drives the architecture)

Allemang & Sequeda, [arXiv:2405.11706](https://arxiv.org/abs/2405.11706) (verified against the original paper):

- LLM over raw SQL: **~16%** accuracy
- plus knowledge graph: **~54%**
- plus ontology-based query checking: **~72%**

→ The validation layer creates the most value, not the generation layer.

## The three meanings of "semantic layer / ontology"

From M. Geraci, ["Everybody Ships an Ontology Now. Nobody Agrees What the Word Means"](https://www.linkedin.com/pulse/everybody-ships-ontology-now-nobody-agrees-what-word-means-geraci-2lenf/) (LinkedIn, 2026-07-01):

1. Formal RDF/OWL ontologies with reasoners.
2. SQL-native virtual models over warehouse tables.
3. Governed metric layers (metrics + dimensions) — this meaning is winning on adoption (Snowflake, Databricks, Fabric, Looker).

SemantiQL sits in the (2)–(3) space.

## Standards

**Open Semantic Interchange (OSI)** — metrics/dimensions interchange standard by Snowflake, dbt Labs, Salesforce, et al.; spec v1.0 released January 2026. Study it so the semantic model YAML can be compatible.

## Local LLMs for SQL generation (researched 2026-07-04, for MacBook M1 16GB)

- **Qwen3-8B (Q4, ~5GB)** — primary pick: better SQL than Qwen2.5-Coder-7B; thinking mode helps with multi-join queries. Run: `ollama run qwen3:8b`.
- **Qwen3-14B (Q4, ~9GB)** — higher quality but close to the RAM ceiling; keep context ≤ 16K.
- **Qwen3-Coder-30B-A3B (MoE)** — near-30B quality at ~8B speed, but needs ~18–20GB; not for 16GB machines.
- More important than model choice: **always include the schema (DDL) in the prompt**; study how **Vanna AI** uses RAG over schema + example queries — directly relevant to the Semantic Knowledge layer.
