---
type: Spec
title: semantiql doctor — check the model against the database
description: A health check that finds where the semantic model and the real schema disagree, before a query does
resource: specs/009-doctor/spec.md
tags: [sdd, spec, cli, adapters]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T00:04:41+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-15
  - id: setup-workflow
    resource: ../docs/03-setup-workflow.md
    title: Where doctor is promised — step 5 of the builder flow, and the 15-minute rule
    last_modified: 2026-08-15
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-17T00:04:41+07:00', checkpoint: 1,
      basis: '9 FRs, each testable; scope is set by what the codebase can check today rather than by the docs full promise, and FR-9 records the part that must wait for the MCP bundle' }
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** The change alters the adapter Protocol — the datasource seam every future adapter
resolves against — and adds a CLI verb.

# What

`semantiql doctor` reads a semantic model, connects to the datasource, and reports every place
the two disagree:

```
$ semantiql doctor -m model.yml --database warehouse.duckdb
orders
  ✓ source 'orders' has 12 columns
  ✗ measure 'revenue' reads column 'amount', which does not exist  (did you mean: net_amount?)
  ✗ dimension 'order_date' is declared date, but the column is VARCHAR
  ✓ 4 dimensions, 3 measures, 1 metric otherwise resolve

1 table checked, 2 problems found.
```

Exit code 0 when everything resolves, non-zero when it does not, so it can gate a setup script.

Today nothing checks a model against reality. A wrong `column` surfaces as a DuckDB binder
error on the first query that touches it; a wrong `type:` does not surface at all until a
filter on it is refused for the wrong reason. `Adapter.columns` exists for exactly this and has
never had a caller.

# Why

Every feature since filters has made the model matter more. `type:` used to be documentation;
it now decides which filter literals are accepted and whether a date is cast. A dimension typed
`string` that is really a `DATE` will refuse `order_date >= '2026-07-01'` with a message about
quoting — sending the author to fix a query that was already correct.

The builder flow is the concrete case. An analyst has fifteen minutes to get from a database to
a working model, and the current failure mode is a stack of adapter errors discovered one query
at a time, each naming a physical column the analyst has to map back to the YAML themselves.
One command that lists every mismatch at once, with suggestions, is the difference between
fifteen minutes and an afternoon.

# User stories

- **As an analyst setting up a model**, I run one command and see every mismatch at once — so
  I fix them in one pass instead of discovering them one query at a time.
- **As an analyst who renamed a column upstream**, doctor tells me which model entries broke
  and what the column is probably called now.
- **As a setup script**, I get a non-zero exit code when the model does not fit the database,
  so I can stop before telling someone the setup worked.

# Functional requirements

- **FR-1** — `semantiql doctor` loads the model, reports a load failure legibly, and stops.
- **FR-2** — It reports whether each table's `source` can be read at all, and how many columns
  it has.
- **FR-3** — It reports every dimension and measure whose `column` does not exist in that
  source, with close-match suggestions.
- **FR-4** — It reports every dimension whose declared `type` contradicts the physical column,
  because that field now decides how filters behave.
- **FR-5** — It reports every measure whose aggregation cannot apply to its column — `sum` or
  `avg` over text — since that fails only when someone finally asks.
- **FR-6** — It reports a mismatch between the model's declared dialect and the adapter in use.
- **FR-7** — Exit codes: `0` when everything resolves, `1` when problems are found, `2` when
  the model cannot be loaded, `3` when the datasource cannot be reached.
- **FR-8** — A `--database` option lets the CLI point at a DuckDB file rather than the
  in-memory default, so doctor and queries can both address a real database.
- **FR-9** — The documentation states what doctor does **not** yet do: the builder flow also
  promises it runs sample questions to confirm answers, which needs the unbuilt MCP bundle.

# Non-functional requirements

- **N5 (read-only)** — doctor only reads. A file-backed database is opened read-only, which is
  the guarantee the connection itself enforces.[^constitution]
- **N4 (one adapter, no core changes)** — the type knowledge doctor needs is engine-specific,
  so the **adapter** classifies its own column types into the model's vocabulary. No dialect
  knowledge moves into shared code.[^constitution]
- **N3 (the YAML is the source of truth)** — doctor reports; it never edits the model. A
  suggestion is a suggestion, exactly as a refusal's `did_you_mean` is.[^constitution]
- **The 15-minute rule** — the builder flow requires every step to be automatically checked
  with errors carrying fix instructions; doctor is that check.[^setup-workflow]

# Out of scope

- **Fixing anything.** No `--fix`, no writing YAML. Proposing a diff is the self-improvement
  loop's job and is human-reviewed by N6.
- **Sample questions** (FR-9), which need the MCP bundle.
- **`semantiql init`**, the generator that writes a first model — a separate, larger spec.
- **Checking metric expressions**, already validated when the model loads.

[^constitution]: `.specify/memory/constitution.md` — N3, N4, N5.
[^setup-workflow]: `docs/03-setup-workflow.md` — builder flow step 5, and the design principle
    that every step is automatically checked with fix instructions.
