---
type: Spec
title: Refuse every construct the compiler cannot honour, wherever it appears
description: Close the silent-drop gap — TABLESAMPLE and PIVOT are accepted and dropped today; make refusal the default for anything unimplemented
resource: specs/003-refuse-unimplemented-constructs/spec.md
tags: [sdd, spec, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-15T23:15:31+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-15
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-15T23:15:31+07:00', checkpoint: 1,
      basis: '6 FRs, each testable against the existing refusal suite; FR-1/FR-2 reproduced by running the two queries through validate before writing the spec; NFRs name N1, N2 and the trust-boundary section they are bound by' }
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** The change edits the query-validation layer, which the constitution names as a trust-boundary artifact — T1 is unavailable regardless of file count.

# What

A request that carries any construct the engine does not implement is refused, and the
database is never reached. That holds no matter where the construct sits inside the request —
attached to the statement, or attached to the table it selects from.

Today two constructs slip through. `SELECT revenue FROM orders TABLESAMPLE (10 PERCENT)` and
`SELECT revenue FROM orders PIVOT (SUM(amount) FOR channel IN ('web'))` are both accepted,
the clause is discarded, and the caller receives a number computed over the whole table as
if they had never written it.

# Why

The engine rebuilds every request from the semantic model rather than rewriting what the
caller wrote. So a construct that validation fails to catch does not cause an error — it
**vanishes**, and the answer looks exactly like a correct one.

A concrete scenario: an analyst asks Claude for a sampled estimate over a large table to keep
a report fast. Claude emits `TABLESAMPLE`. SemantiQL returns the full-table figure with no
warning, and it is presented as the sample. The end user never sees SQL, so nobody can catch
it — the exact failure this project exists to prevent.

The deeper problem is the shape of the check, not the two missing entries. Refusal is driven
by a list of known-bad constructs. sqlglot parses all of SQL; the compiler implements a small
fraction of it; so the list must enumerate an open-ended set, and it silently stops matching
whenever the parser attaches something in a new place. These two entries are already listed
by name and still do not fire.

# User stories

- **As a non-technical end user**, I never receive a number that quietly ignores part of what
  was asked — so a figure I paste into a deck means what it says.
- **As an analyst building a model**, a request the engine cannot honour comes back as a
  refusal naming the construct — so I can rewrite the question instead of trusting a wrong
  total.
- **As a contributor upgrading sqlglot**, a construct the parser starts representing
  differently is refused by default rather than silently accepted — so the upgrade cannot
  quietly widen what the engine answers.

# Functional requirements

- **FR-1** — A request carrying `TABLESAMPLE` is refused, and the datasource is never reached.
- **FR-2** — A request carrying `PIVOT` or `UNPIVOT` is refused, and the datasource is never
  reached.
- **FR-3** — Refusal is the **default outcome** for any construct the engine does not
  implement, wherever it appears in the request. A construct is answerable only if it is
  explicitly known to be answerable; anything else is refused without needing to be
  enumerated in advance.
- **FR-4** — Every refusal names the construct that caused it, so the caller can act on it.
- **FR-5** — Every request answerable before this change is still answered, unchanged: bare
  and aliased entity names, quoted identifiers, a qualified entity name, a table alias, a
  catalog/schema prefix, a trailing semicolon, and comments.
- **FR-6** — The published SQL coverage map stops describing these constructs as accepted,
  and records the outcome that now holds.

# Non-functional requirements

- **N1 (validation over generation)** — the refusal must be decided before the adapter is
  consulted; a test asserts the datasource was never touched, not merely that a refusal came
  back.[^constitution]
- **N2 (a silently wrong number is the worst failure)** — this change exists to remove a live
  instance of it; no part of it may introduce a construct that is accepted and ignored.[^constitution]
- **Trust boundary** — the query-validation layer is where N1 and N2 live or die, so the
  change ships with regression tests in the existing refusal suite and no check is weakened
  to make anything pass.[^constitution]

# Out of scope

- **Implementing** any of these constructs. `TABLESAMPLE`, `PIVOT`, `WHERE`, `ORDER BY` and
  the rest stay unsupported; this spec only makes the refusal true.
- **The request-contract decision** — whether the canonical request stays SQL text or becomes
  a structured object. That is the larger design choice and belongs in its own spec; this
  change must not prejudge it.
- **Report features** — filters, ordering, limits, time grains, derived metrics, joins.

[^constitution]: `.specify/memory/constitution.md` — non-negotiables N1 and N2, and the
    trust-boundary artifacts section naming the query-validation layer.
