---
type: Spec
title: Claude discovers the database and writes the model itself
description: A schema-inspection command Claude runs from a shell, so it reads the real tables and columns and writes the model YAML with filesystem tools — replacing the one step of setup that is still hand-written.
resource: specs/016-schema-discovery/spec.md
tags: [sdd, spec, discovery, skill, adapters]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T05:10:00+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: The ≤15-minute setup rule, N3, N4, N6, and the trust-boundary list
    last_modified: 2026-08-18
  - id: setup-workflow
    resource: ../../docs/03-setup-workflow.md
    title: Step A3, the only hand-written step left in Flow A
    last_modified: 2026-08-18
  - id: base
    resource: ../../src/semantiql/adapters/base.py
    title: The Adapter Protocol — columns(source) needs a source you already know; nothing enumerates
    last_modified: 2026-08-18
  - id: doctor
    resource: ../../src/semantiql/doctor.py
    title: The only current consumer of columns(), and the loop that checks what gets written
    last_modified: 2026-08-18
  - id: skill
    resource: ../../plugin/skills/semantiql/SKILL.md
    title: The skill that will orchestrate discovery
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T05:12:00+07:00', checkpoint: 1,
      basis: '11 FRs, each testable. Scope corrected after the user pointed out that an earlier doc described hand-writing the model as the flow rather than as the gap. FR-10 states the server surface stays two tools, because the client already has a shell and a filesystem — a discovery tool on the server would widen the enforcement boundary for a job it does not need to do. The N6 NFR states why a conversation is not automatic change, and FR-9 puts the limit in the skill' }
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** It widens the `Adapter` Protocol — the datasource seam every adapter resolves against — adds
a CLI verb, changes the skill, and edits `docs/NN-*.md`.

# What

An analyst points Claude at a database and gets a reviewed semantic model back, without writing
YAML.

```
Analyst:  Build me a model for this warehouse.

Claude:   [bash] semantiql inspect --datasource postgres --json
          → 14 tables

          Fourteen tables. These four look like the core: orders, order_lines,
          customers, subscriptions. Start there?

Analyst:  yes, and skip anything with PII

Claude:   [bash] semantiql inspect --table orders --json
          → id, placed_at (timestamptz), channel, region, amount_cents, customer_id

          `placed_at` carries a timezone — which zone do you report months in?

Analyst:  UTC

Claude:   [Write] model/datasource.yml
          [Write] model/orders.yml
          [bash]  semantiql doctor -m model/     → 1 problem
          [Edit]  model/orders.yml
          [bash]  semantiql doctor -m model/     → no problems found
```

Claude wrote the files. It used a shell to see the real schema and its own filesystem tools to
write YAML — no new server capability, and the analyst answered the questions only a human can.

Today none of this is possible: **nothing in SemantiQL can list the tables in a database.**
`columns(source)` requires a source you already know, so discovery cannot start.[^base]

# Why

**A3 is the last hand-written step in setup, and the most expensive.**
`docs/03-setup-workflow.md` walks eight steps and seven of them are commands. A3 is "write the
YAML", and it is where the fifteen-minute promise goes.[^setup-workflow] [^constitution]

**The tedious part and the judgement part are different work, and only one needs a human.** Every
column, its type, whether it carries a timezone — mechanical, and exactly what an adapter already
reports. Which aggregation is *the* sanctioned revenue, what a row actually is, which columns are
sensitive — judgement, and not derivable from a schema at any level of cleverness. Splitting them
is what makes this worth doing: Claude does the first, the analyst answers the second, and the
result is reviewed by construction because it happened in a conversation. `doctor` closes the
loop: Claude writes, `doctor` checks against the real schema, Claude fixes.[^doctor]

**It needs no new server capability, and that matters.** Claude Code already has a shell and
filesystem tools. So discovery is a CLI command Claude runs and files Claude writes — the MCP
server's surface stays two read-only tools, and the enforcement boundary that spec 013 established
is untouched.[^skill] A discovery tool on the server would have widened it for a job the client can
already do.

**A directory model is what makes the writing clean.** One YAML per table is a natural thing to
write file by file, reviewable per table, and it means adding a table later is a new file rather
than a regeneration.

**N6 is not in tension here, and the reason is worth stating.** The invariant forbids *automatic*
change to what a number means. This is a human in a conversation, deciding, with the result landing
as files they accept — human-reviewed by construction. What would violate N6 is Claude editing a
model mid-question to answer one; that stays refused.[^constitution]

# User stories

- **As an analyst**, I point Claude at my warehouse and answer questions about my business instead
  of typing YAML — so setup is a conversation, not an afternoon.
- **As an analyst**, Claude asks me which aggregation counts as revenue rather than guessing — so
  the definitions are mine.
- **As an analyst**, I see every file before it is committed, because they are files in my working
  tree — so nothing is authoritative that I did not read.
- **As Claude**, I can list the tables and then read one table's columns — so I do not have to send
  a 500-table schema through the conversation to start.
- **As a maintainer**, the server's tool surface does not grow to make this work.

# Functional requirements

- **FR-1** — An `Adapter` can **enumerate** the relations of its datasource: tables and views, in a
  form `columns()` accepts.
- **FR-2** — Both shipped adapters implement it. Views are included, because a view is the
  documented way to model a join.
- **FR-3** — Relations outside the default schema are returned so that they remain usable
  unambiguously; system schemas are excluded.
- **FR-4** — A `semantiql inspect` command lists the relations of a datasource, and with a relation
  named, reports its columns with the type SemantiQL will use and whether it carries a timezone.
- **FR-5** — `inspect` requires **no semantic model**. It is what runs before one exists.
- **FR-6** — `inspect` offers machine-readable output, so Claude parses it rather than scraping a
  table.
- **FR-7** — Two steps by default: relations first, columns on request. A 500-table warehouse must
  not arrive in one reply.
- **FR-8** — The skill instructs Claude to inspect, propose, **ask about the judgement calls**, write
  the files, run `doctor`, and fix what it reports — with the analyst present throughout.
- **FR-9** — The skill instructs Claude never to invent a measure's aggregation or a metric's
  definition without asking, and never to change a model to answer a question.
- **FR-10** — The MCP server's tool surface is **unchanged**: two read-only tools.
- **FR-11** — Documentation replaces A3's "write the YAML" with the discovery flow, and keeps
  hand-writing documented for anyone without Claude.

# Non-functional requirements

- **N4 (one adapter, no core changes)** — this widens the seam a **third** time, after `close()` and
  `carries_timezone`. Called out rather than absorbed: each widening is a finding about the seam,
  and three of them is a pattern worth noticing.[^constitution]
- **N5 (read-only)** — enumeration reads catalogue metadata. No rows, no writes.
- **N6** — see Why. A conversation with a human is not automatic change; the skill says so
  explicitly and a test asserts it does.[^constitution]
- **N1 / N2** — untouched. `inspect` reads metadata, never data; it is not a query path.

# Out of scope

- **`semantiql init`** — the mechanical, dimensions-only draft with no Claude involved. A different
  thing, still worth building for scripted setup, and not needed for this.
- **Claude writing a model without a human present.** The analyst answers the judgement questions;
  an unattended run is not this feature.
- **Detecting sensitive columns.** The analyst says which; guessing at PII is exactly the confident
  wrong answer this project refuses.
- **Row-level profiling** — distinct counts, ranges, sample values. Useful for naming, and it reads
  rows, which is a bigger claim than metadata.

  **Reversed by spec 020, and how it was reversed is the lesson.** This exclusion lived only here.
  The skill never carried it, so when a run needed numbers to price a judgement question it reached
  for raw `psql` — twelve calls, including a join and a `CREATE OR REPLACE VIEW`. It got the right
  figures by luck rather than by construction. **An exclusion that is not in the skill is not an
  exclusion**, and the correct answer turned out not to be a firmer prohibition but a sanctioned
  path: `semantiql profile`, plus a rule against raw SQL that has a test.
- **Relationship or join inference.** One table per query; a view is the escape hatch.

[^constitution]: `.specify/memory/constitution.md` — the ≤15-minute setup rule, N1, N2, N4, N5, N6, and the trust-boundary list.
[^setup-workflow]: `docs/03-setup-workflow.md` — Flow A, step A3.
[^base]: `src/semantiql/adapters/base.py` — the Protocol; `columns(source)` and the absence of enumeration.
[^doctor]: `src/semantiql/doctor.py` — the existing consumer of `columns()`, and the loop that checks what Claude writes.
[^skill]: `plugin/skills/semantiql/SKILL.md` — the skill, and the two-tool surface it works against.
