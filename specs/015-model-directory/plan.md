---
type: Plan
title: Model directory — plan
description: Merge raw mappings with provenance so one validation pass still covers everything, refuse every ambiguity naming the files, and give describe_model an optional table argument with a one-table shortcut.
resource: specs/015-model-directory/plan.md
tags: [sdd, plan, knowledge, mcp]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T04:20:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time — N2, N3, trust boundaries
    last_modified: 2026-08-18
  - id: loader
    resource: ../../src/semantiql/knowledge/loader.py
    title: load_model, _StrictLoader, ModelError, and _resolve_sources(model, p.parent)
    last_modified: 2026-08-15
  - id: model
    resource: ../../src/semantiql/knowledge/model.py
    title: SemanticModel requires datasource and tables; Table._names_must_not_overlap
    last_modified: 2026-08-18
  - id: server
    resource: ../../src/semantiql/server.py
    title: describe_model, ModelInfo, TableInfo, Entity, and the read-only annotations
    last_modified: 2026-08-18
  - id: skill
    resource: ../../plugin/skills/semantiql/SKILL.md
    title: The "always start with describe_model" section the two-step shape changes
    last_modified: 2026-08-18
  - id: test-plugin
    resource: ../../tests/test_plugin.py
    title: The drift test, which asserts the skill's rules against the engine
    last_modified: 2026-08-18
  - id: adopting
    resource: ../../docs/10-adopting-semantiql.md
    title: Step 3's one-table advice, and where the directory layout belongs
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T04:24:00+07:00', checkpoint: 2,
      basis: 'map derived from 7 file reads; all 6 existing-file rows footnoted. AD-1 merges raw mappings rather than models so the single validation pass and every existing rule survive untouched — validating per file is impossible anyway, since a table file has no datasource. AD-4 states the one-table shortcut as a rule rather than a threshold, because a magic number would make the tool unpredictable' }
status: stable
---

# Constitution check

**N2 — every ambiguity is refused.** Two files defining one table, two declaring a datasource, a
file that contributes nothing: all errors naming the files. The loader already refuses duplicate
keys *within* a file for exactly this reason; this is the same rule one level up.[^loader]

**N3 — the YAML stays the source of truth**, and `knowledge/loader.py` stays its only reader. A
directory is more reviewable than one large file, not less.[^constitution]

**N1** — untouched. No change to validation or to the path to data.

**Trust-boundary artifacts** in scope: `docs/07-code-map.md`, `docs/09-data-modeling.md`,
`docs/10-adopting-semantiql.md`. `knowledge/model.py` is **read but not changed** — the merged
mapping is validated by the existing schema, so the model's shape is unchanged.

# Approach

**Merge raw mappings, then validate once.** `load_model` gains a directory branch that reads every
file into a dict, merges them, and hands the result to the existing
`SemanticModel.model_validate`. Every rule already written — required fields, name overlaps, metric
expressions, timezone checks — applies unchanged and in one place.[^model]

Validating each file separately is not an option even in principle: a table file has no
`datasource`, so it is not a `SemanticModel`. Merging first is what makes the existing schema reusable.

**Provenance travels with the merge**, because two things need it: an error must name the file it
came from (FR-6), and a relative `source` must resolve against its own file rather than the
directory root (FR-5). So the merge records which file contributed each table, and
`_resolve_sources` runs per contributing file instead of once.[^loader]

**`describe_model` gains an optional `table`.** No argument returns the tables — name, description,
entity counts. Naming one returns it in full. The exception is a model with exactly one table,
where the full form is returned immediately because there is nothing to choose and forcing a second
round trip would make the common case worse.[^server]

**The skill teaches the two-step shape**, and the existing drift test keeps it honest.[^skill] [^test-plugin]

# Architecture decisions

**AD-1 — merge dicts, not models.** Rejected: loading each file into a partial model and combining
them, which would need a second, looser schema — and a looser schema is a second place for the
model's rules to live and disagree.

**AD-2 — deterministic order, and every file must contribute.** Files are read in sorted path order
so errors and behaviour are reproducible. A file that parses but contributes no recognised key is an
**error**: silently skipping it means someone believes they modelled a table that is absent, and
the symptom is a refusal that looks like a bug in the engine (FR-7).

**AD-3 — `datasource` and `version` are declared exactly once, not merged.** Requiring identical
copies in every file would be friendlier to careless splitting and would mean thirty places to
change one dialect. One declaration is unambiguous, and two are refused naming both files.

**AD-4 — the one-table shortcut is a rule, not a threshold.** A size cut-off ("full detail under
five tables") would make the tool's reply shape unpredictable and untestable. "Exactly one table
returns full detail; two or more return the list" is one sentence, stated in the tool description,
and always the same.

**AD-5 — the counts in the list are the useful signal.** A table row carries its description plus
how many dimensions, measures and metrics it has. That is what tells Claude whether `orders` is the
table with the revenue measure, without sending the definitions.

# Repository Impact Map

## Files to modify

- `src/semantiql/knowledge/loader.py` — the directory branch, the merge with provenance, the three
  refusals, and per-file `_resolve_sources`. The only file that reads the model, and it stays
  so.[^loader]
- `src/semantiql/server.py` — `describe_model(table: str | None)`, a `TableSummary` shape for the
  list, and the one-table shortcut. Still two tools.[^server]
- `plugin/skills/semantiql/SKILL.md` — the two-step shape, and that a missing table name is answered
  with the available ones.[^skill]
- `tests/test_server.py` — the new argument, both shapes, the shortcut, the unknown-table reply.
- `tests/test_loader.py` — directory loading, and each refusal with its message.
- `docs/09-data-modeling.md` — the directory layout, and the rules about declaring `datasource` once.
  **Trust-boundary artifact.**
- `docs/10-adopting-semantiql.md` — Step 3's "one table" advice becomes "start with one table, grow
  into a directory".[^adopting]
- `docs/07-code-map.md` — the loader's row mentions directories. **Trust-boundary artifact.**
- `README.md`, `AGENTS.md` — a line each; `CLAUDE.md` is a symlink and **not** a second edit.

## Files to add

- `examples/warehouse/` — a small worked directory model, so the layout is demonstrated rather than
  only described, and so a test has something real to load.

## Files not touched, but adjacent

- ~~`src/semantiql/knowledge/model.py` — no change.~~ **Amended mid-implement: `Table` gains an
  optional `description`.** FR-8 promises the index carries each table's description, and `Table`
  had none — only its dimensions, measures and metrics did. Without it the index is names and
  counts, which is workable and materially worse at exactly the scale this spec exists for: a
  reader choosing between `orders`, `order_lines` and `orders_v2` needs a sentence, not a count.
  One optional field, no behaviour change, and the merged mapping is still validated by one schema
  — AD-1 survives. **Trust-boundary artifact**, so it is called out rather than slipped in.
- `src/semantiql/engine/` — no change. The engine never knew how many files a model came from.
- `src/semantiql/cli.py` — no change. `-m` is a path; `load_model` decides what kind.

# Open research questions

- **OQ-1 — should a directory be allowed to contain a file that declares nothing?** AD-2 says no.
  The alternative — ignoring files without a recognised key — would let a README.yml sit in the tree
  harmlessly, at the cost of also ignoring a typo'd `tabels:`. The strict reading is chosen and the
  error names the file; if it proves annoying in practice, allowing an explicit opt-out marker is a
  smaller change than loosening the rule.
- **OQ-2 — does `describe_model`'s reply shape changing break a client mid-conversation?** The tool's
  output schema gains a variant. A client that cached the old schema would see fields it does not
  expect. Local, single-session servers make this unlikely to matter; worth stating rather than
  assuming.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N3, and the trust-boundary list.
[^loader]: `src/semantiql/knowledge/loader.py` — `load_model`, `_StrictLoader`, `ModelError`, `_resolve_sources`.
[^model]: `src/semantiql/knowledge/model.py` — `SemanticModel`'s required fields and `Table`'s overlap check.
[^server]: `src/semantiql/server.py` — `describe_model`, `ModelInfo`, `TableInfo`, `Entity`.
[^skill]: `plugin/skills/semantiql/SKILL.md` — the describe-first section.
[^test-plugin]: `tests/test_plugin.py` — the skill-versus-engine drift test.
[^adopting]: `docs/10-adopting-semantiql.md` — Step 3.
