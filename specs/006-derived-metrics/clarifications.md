---
type: Clarifications
title: Derived metrics in the semantic model — clarifications
description: 4 ambiguities resolved before planning.
resource: specs/006-derived-metrics/clarifications.md
tags: [sdd, clarifications]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:26:51+07:00' }
status: stable
---

## Q1: How is a metric written — an expression string, or a structured form?

- (a) Structured YAML: `{ numerator: revenue, denominator: order_count }`, or an operator tree.
- (b) An expression string: `revenue / order_count`, parsed under a closed grammar.
- **Chosen:** (b) — decided by the agent from N3 and from what the YAML is *for*. The model is
  meant to be reviewable in a diff by an analyst, and `(revenue - cost) / revenue` reads as the
  definition it is, where the structured form of the same thing is three nested mappings that
  a reviewer must reassemble mentally. The safety objection to parsing a string is real but
  does not apply with the same force here: the expression comes from a file in git, not from a
  caller, and it is parsed once at load under an allowlist grammar — the same discipline the
  predicate walker already uses. A string that does not fit the grammar fails the load.

## Q2: What happens when the divisor is zero?

- (a) Leave it to the engine.
- (b) Guard every division so a zero divisor yields NULL.
- **Chosen:** (b) — decided by the agent from a probe at clarify time, which makes (a)
  untenable. DuckDB evaluates `1/0` to **`inf`** and returns it as a value; Postgres raises
  `division by zero`. So an unguarded ratio gives a meaningless number on the MVP's first
  engine and an error on its second, from the same model — a direct contradiction of N3's
  promise that the model survives a change of database, and of N2, since `inf` in a report
  looks like a figure. Wrapping the divisor so that zero becomes NULL gives the same answer on
  both engines, and "no value" is the honest report of a ratio with nothing to divide by.

## Q3: May a metric reference another metric?

- (a) Yes, resolving recursively with cycle detection.
- (b) No — measures only.
- **Chosen:** (b) — decided by the agent from the spec's Out of scope and from cost. Nesting
  needs cycle detection, a resolution order, and an error message for each failure mode, none
  of which buys anything the first version needs; `(revenue - cost) / revenue` names measures
  directly and reads perfectly well. Refused with a message that says metrics compose from
  measures, so the limitation is discoverable rather than mysterious.

## Q4: Where is the expression validated?

- (a) At query time, in the engine, when a metric is selected.
- (b) At load time, in the knowledge layer, for every metric the file declares.
- **Chosen:** (b) — decided by the agent from `knowledge/model.py`'s own stated contract: "A
  malformed model fails loudly with a field-level message rather than surfacing later as a
  wrong number." Option (a) means a typo in a metric nobody has queried yet sits undetected
  until someone asks for it, which is precisely the failure that docstring rejects. Loading
  therefore parses every expression and resolves every name against the table's measures, and
  the parsed form is what the compiler builds from.
