---
type: Spec
title: A model can be a directory, and describing it stays cheap at scale
description: One YAML per table instead of one file for the warehouse, with collisions refused rather than merged — and describe_model returning a table list instead of every definition, so fifty tables do not flood the context.
resource: specs/015-model-directory/spec.md
tags: [sdd, spec, knowledge, mcp, scale]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T04:10:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: N2 and N3 — one YAML as source of truth, and a wrong number as the worst failure
    last_modified: 2026-08-18
  - id: loader
    resource: ../../src/semantiql/knowledge/loader.py
    title: load_model, the duplicate-key refusal, and per-file source resolution
    last_modified: 2026-08-15
  - id: server
    resource: ../../src/semantiql/server.py
    title: describe_model, which returns every entity of every table in one reply
    last_modified: 2026-08-18
  - id: adopting
    resource: ../../docs/10-adopting-semantiql.md
    title: The "pick one table, do not model your whole warehouse" advice this change outgrows
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T04:12:00+07:00', checkpoint: 1,
      basis: '12 FRs, each testable. The scale requirement is read as two halves rather than one: FR-1..FR-7 make a big model authorable, FR-8..FR-10 make it usable, and a model that loads but floods the context is not scalable. FR-3/FR-4/FR-7 are all refusals because every merge ambiguity is the same class of silent redefinition the loader already refuses within a file' }
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** It changes the semantic model's own shape — the constitution names the model schema a
trust-boundary artifact — plus the loader, the MCP tool surface's behaviour, the skill, and
`docs/NN-*.md`.

# What

**A model may be a directory.** One YAML per table, so a warehouse is a reviewable tree rather
than a two-thousand-line file:

```
model/
├── datasource.yml      version and datasource, declared once
├── orders.yml          tables: { orders: … }
├── customers.yml       tables: { customers: … }
└── billing/
    └── invoices.yml    tables: { invoices: … }
```

`-m model/` and `SEMANTIQL_MODEL=/path/model` both work. A single file keeps working exactly as
before.

**And describing it stays cheap.** `describe_model` today returns every dimension, measure and
metric of every table in one reply. That is right for one table and wrong for fifty: the reply
becomes thousands of tokens of definitions Claude did not ask for, most of them irrelevant to the
question. After this change it returns the *tables* — names, descriptions, entity counts — and
Claude asks for the one it needs.

# Why

**The current advice is a workaround for a missing feature.** `docs/10` tells an adopter *"Pick
one table or view… Do not try to model your whole warehouse."*[^adopting] That is honest advice
about a file, not about semantics — nothing in the engine cares how many tables a model has. The
limit is that one file holding a warehouse is unreviewable: a pull request touching one metric
shows a diff in a file nobody can read, and two people editing different tables conflict.

**A directory makes ownership and review work the way they already do for code.** One file per
table means a metric change is a small diff in an obvious place, `git log` per table is
meaningful, and `CODEOWNERS` can put the billing tables with the billing team. None of that is
possible in a single document.

**Merging is where a wrong number would come from, so merging is where the strictness goes.** The
loader already refuses duplicate keys *within* a file, because "a merge conflict or a careless
paste becomes a wrong number with no symptom".[^loader] Two files defining `orders`, or two
declaring a different `datasource`, is the same failure across files — and last-one-wins would be
exactly the silent redefinition that check exists to prevent.[^constitution]

**The context cost is the half that actually breaks.** A fifty-table model described in full is
not merely wasteful; it crowds out the conversation and makes Claude likelier to pick a
plausible-looking entity from a table nobody asked about.[^server] Scale is not just whether the
loader copes — it is whether the model can be *used* once it is big.

# User stories

- **As a model author**, I add a table by adding a file — so a review is a small diff and two
  people are not editing one document.
- **As a team lead**, I can put the billing tables under the billing team's ownership — so the
  people who know what a metric means are the ones who approve changes to it.
- **As a model author**, if two files define the same table I am told which two — so I never get a
  model that silently picked one.
- **As Claude**, I see which tables exist before I see every definition — so a fifty-table model
  costs one small reply, not thousands of tokens I did not need.
- **As an analyst with one table**, nothing changes: one file still works and describing it still
  answers in full.

# Functional requirements

- **FR-1** — `-m` and `SEMANTIQL_MODEL` accept a **directory** as well as a file. A single file
  behaves exactly as it does today.
- **FR-2** — Every `.yml` and `.yaml` under the directory, including subdirectories, contributes to
  one model, in a deterministic order.
- **FR-3** — `datasource` and `version` are declared **exactly once** across the directory. Zero or
  more than one is refused, naming the files involved.
- **FR-4** — A table defined in two files is **refused**, naming both files and the table. Never
  merged, never last-one-wins.
- **FR-5** — A relative file `source` resolves against **the file that declared it**, not the
  directory root — so a CSV can sit beside the YAML that describes it.
- **FR-6** — Every error names the file it came from. A directory of thirty files must not produce
  an error that could be about any of them.
- **FR-7** — A file that is not a valid contribution is an **error, not a skipped file**. A stray
  YAML that is silently ignored is a table someone thinks they modelled.
- **FR-8** — `describe_model` with no argument returns each table's name, description and entity
  counts — not every definition — **except** when the model has exactly one table, where it returns
  that table in full because there is nothing to choose.
- **FR-9** — `describe_model` accepts a table name and returns that table's dimensions, measures and
  metrics in full.
- **FR-10** — Asking for a table that does not exist is answered with the available names, not an
  empty reply.
- **FR-11** — The tool **count stays two**. This adds an argument, not a tool.
- **FR-12** — The skill tells Claude the two-step shape, and the docs describe the directory layout
  and when to prefer it.

# Non-functional requirements

- **N2 — a silently wrong number is the worst failure.** Every merge ambiguity is refused rather
  than resolved. This is the whole reason FR-3 and FR-4 are refusals.[^constitution]
- **N3 — the YAML is the source of truth.** A directory is still YAML in git, still reviewable and
  diffable; it is more so, not less. `knowledge/loader.py` remains the only reader.[^constitution]
- **N1** — unchanged. Nothing here touches validation or the path to data.
- **Backward compatibility** — every existing model, example and test must load unchanged. A
  feature that quietly changed how a single-file model behaves would be a bad trade for
  scalability.

# Out of scope

- **Cross-file references.** A metric may only name measures of its own table, as today. Tables
  remain independent.
- **Joins across files.** Still one table per query; a directory changes authoring, not the engine.
- **Includes, imports or templating.** Files contribute; they do not reference each other.
- **Watching for changes.** The model is read at startup. Reloading a running server is its own
  question.
- **`semantiql init` writing a directory.** Its own spec; it will be able to, and this makes that
  worth doing.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N3, and the trust-boundary list naming the semantic model schema.
[^loader]: `src/semantiql/knowledge/loader.py` — `load_model`, `_StrictLoader`'s duplicate-key refusal and why it exists, and `_resolve_sources`.
[^server]: `src/semantiql/server.py` — `describe_model` and the `ModelInfo` it returns.
[^adopting]: `docs/10-adopting-semantiql.md` — the one-table-at-a-time advice.
