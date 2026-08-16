---
type: Clarifications
title: Order and limit a request — clarifications
description: 4 ambiguities resolved before planning.
resource: specs/005-order-and-limit/clarifications.md
tags: [sdd, clarifications]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:16:47+07:00' }
status: stable
---

## Q1: What may a request order by?

- (a) Anything the model defines on the table, adding the aggregate to the `ORDER BY` when a
  measure is named that the request does not select.
- (b) Only names the request already projects, matched on the entity name or the output alias.
- **Chosen:** (b) — decided by the agent from N2 and from how the projection list already
  works. Option (a) is what SQL permits, but it means a number influences the answer's shape
  without appearing in it, and the reader cannot see why the rows are in that order. Ordering
  by what is on screen is also the rule a non-technical user would assume. Positional ordinals
  (`ORDER BY 1`) are refused with the same reasoning: the name is available and unambiguous.

## Q2: `NULLS FIRST` / `NULLS LAST` — honour, or refuse?

- (a) Refuse any explicit null placement, since the engines differ.
- (b) Honour what sqlglot records.
- **Chosen:** (b) — decided by the agent from an AST probe at clarify time. `nulls_first` is
  `True` only when `NULLS FIRST` is written; plain ordering and an explicit `NULLS LAST` both
  record `False`, which is also how both MVP engines behave by default for `ASC`. So carrying
  the flag through reproduces the request faithfully on DuckDB and Postgres, and the one case
  the parser normalises away — `NULLS LAST` — normalises to the behaviour it asked for. The
  documentation states the rule rather than leaving a reader to discover it.

## Q3: What is a valid `LIMIT`?

- (a) Any expression the engine would accept.
- (b) A non-negative whole-number literal, and nothing else.
- **Chosen:** (b) — decided by the agent from FR-4 and from the compile-side rebuild. `LIMIT
  1+1` parses as an `Add`, and rebuilding arbitrary arithmetic would drag expression support
  into the compiler through a side door — the thing the model deliberately does not have.
  A whole number covers every reason a report has a limit.

## Q4: Does `LIMIT ALL` count as a dropped clause?

- (a) Refuse it, on the principle that nothing is silently discarded.
- (b) Let it through as "no limit".
- **Chosen:** (b) — decided by the agent from what the clause means. sqlglot parses `LIMIT
  ALL` by recording no limit at all, and `LIMIT ALL` *is* "every row", so the resulting query
  answers exactly the question asked. This is the one case where dropping a clause changes
  nothing about the number, and refusing it would be pedantry rather than safety. Noted here
  so a later reader can see it was considered rather than missed.
