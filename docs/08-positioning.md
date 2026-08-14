# Positioning — what SemantiQL is trying to do differently

For an engineer deciding whether the approach is sound before spending time on it.

## How to read this document

**Every claim here is about SemantiQL's own intent, not about how another product behaves
today.** That restriction is deliberate. The projects named below are actively developed,
their capabilities move, and an unsourced assertion about someone else's tool ages into a
misrepresentation. [06-research-notes.md](06-research-notes.md) lists the landscape as prior
art still to be studied properly; until that study exists and is cited, this file states
what SemantiQL aims at and leaves the comparison for the reader to make.

If you know one of these tools well and something below misrepresents it, that is worth an
issue — it will be treated as a bug in this file.

## The bet

One published result drives the whole design. Allemang & Sequeda
([arXiv:2405.11706](https://arxiv.org/abs/2405.11706), figures verified against the paper
and recorded in [06-research-notes.md](06-research-notes.md)) measured an LLM answering
questions over enterprise SQL:

| Setup | Accuracy |
|---|---|
| LLM over the raw SQL schema | ~16% |
| plus a knowledge layer | ~54% |
| plus ontology-based query checking | ~72% |

The knowledge layer roughly triples accuracy. **Checking the query adds nearly as much
again** — and checking is the cheaper half to build.

So SemantiQL's bet is that the *validation* layer, not the generation layer, is where the
remaining accuracy lives, and it is built around that: a query whose every identifier
cannot be resolved against the semantic model is **refused rather than executed**. The
refusal is the feature. See [02-architecture.md](02-architecture.md).

## Two intents that follow from it

**1. Refusing beats answering.** The end user is non-technical, never sees SQL, and
therefore cannot catch a wrong number. A plausible wrong figure is worse than no figure,
because it gets pasted into a deck. Concretely, in this repo: `engine/run.py` is the only
path to the data, and `Adapter.execute` accepts nothing that has not been validated — so
the guarantee is structural rather than a matter of care. `tests/test_validation_refuses.py`
asserts not merely that a refusal came back but that **the database was never touched**.

**2. The model should improve with use, without its definitions drifting.** Two separate
tiers ([04-self-improvement.md](04-self-improvement.md)): confirmed question/query pairs
accumulate automatically as verified examples, while **metric definitions are only ever
changed by a human reviewing a diff**. A layer that silently retunes what "revenue" means
is a layer nobody can trust. This tier is designed, not yet built.

## Where SemantiQL sits, in its own words

The term "semantic layer" currently covers at least three different things — formal RDF/OWL
ontologies with reasoners; SQL-native virtual models over warehouse tables; and governed
metric layers. That taxonomy, and its source, are recorded in
[06-research-notes.md](06-research-notes.md). SemantiQL aims at the second and third: a
SQL-native model of dimensions, measures and metrics, in one reviewable YAML file, with an
engine that validates before it executes.

Projects worth comparing it against yourself: **Cube**, the **dbt Semantic Layer**,
**MetricFlow**, **Malloy**, and the various **MCP database servers**. What to look at, if
you want to form your own view:

- Is a query *checked* against the model before it runs, and what happens when it cannot be?
- Is the model one reviewable file in version control, or state in a service?
- Does the model survive changing databases?
- Does the layer get more accurate with use, and if so can it change a metric definition
  without a human?

Those four questions are the axes SemantiQL is designed around, which is exactly why they
are the fair ones to judge it on — and why you should ask them of SemantiQL too.

## What SemantiQL does not do

- **No NoSQL**, permanently ([05-datasources.md](05-datasources.md)).
- **No BI layer.** No dashboards, no charts, no scheduled reports.
- **No transformation or modelling.** It reads what exists; it is not a dbt replacement.
- **No writes.** Read-only by default, and nothing in the query path needs write access.

## Honest status

Pre-release. The MVP is DuckDB plus Postgres, a semantic model YAML, the validating engine,
and an MCP server for Claude ([README](../README.md) has the roadmap). **The accuracy
benchmark against raw-table querying is not built yet** — until it is, the 16/54/72 figures
above are someone else's result on someone else's corpus, and evidence for the design
rather than evidence about this implementation. Treat the claim as a hypothesis under test.
