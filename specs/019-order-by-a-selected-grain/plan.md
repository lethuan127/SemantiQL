---
type: Plan
title: Order by a time grain the request already selects — plan
description: Resolve an ORDER BY DateTrunc against the projections it already carries, and give every refusal branch the orderable names.
resource: specs/019-order-by-a-selected-grain/plan.md
tags: [sdd, plan]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T13:42:14+00:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-17
  - id: ordering
    resource: ../src/semantiql/engine/validate.py
    title: _ordering — three branches, the outputs map, and _grain/_projections upstream
    last_modified: 2026-08-18
  - id: projection
    resource: ../src/semantiql/engine/validate.py
    title: Projection carries entity, output and grain — the grain is already recorded
    last_modified: 2026-08-18
  - id: compile
    resource: ../src/semantiql/engine/compile.py
    title: Read to confirm ordering is emitted from OrderKey.output and needs no change
    last_modified: 2026-08-18
  - id: order-tests
    resource: ../tests/engine/test_validate.py
    title: The existing ORDER BY cases this extends
    last_modified: 2026-08-18
  - id: refusal-tests
    resource: ../tests/engine/test_validation_refuses.py
    title: ExplodingAdapter — the pattern for proving the database was never reached
    last_modified: 2026-08-18
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T13:42:14+00:00', checkpoint: 2,
      basis: 'Six rows, all footnoted to files read. The decisive read was that Projection already records grain, so matching an ORDER BY DateTrunc against the select list needs no new state and no compiler change — confirmed by reading how compile.py consumes OrderKey.output. _grain was read closely enough to find that it raises rather than returns, which changes where the new call has to sit.' }
---

# Constitution check

**N1 / N2 — validation is the point, and a wrong number is worse than none.** This accepts a query
that was refused, so it is the direction that needs care. What makes it safe: an accepted
`ORDER BY DATE_TRUNC(...)` must match a projection the request already carries, and it resolves to
that projection's **output column** — the identical `OrderKey` the alias spelling produces. The SQL
that reaches the database is byte-identical to what the alias form already emits, so no new construct
becomes reachable.[^compile]

**The allowlist rule.** No new node type is consumed and nothing new is emitted, so `_SELECT_ARGS`
and `_FROM_NODE_ARGS` are unchanged. The rule is that the allowlist grows *with* a compiler change;
there is no compiler change.[^constitution]

**Trust boundary.** `engine/validate.py`. Stated explicitly.[^constitution]

**Refusal paths get tests, including that the database was never reached** — `ExplodingAdapter` is
the existing pattern.[^refusal-tests]

# Approach

`Projection` already carries `grain`, so the select list already knows that `pickup_datetime` was
projected at `month` under the output name `pickup_datetime_month`.[^projection] The ORDER BY item is
the same shape of node. So this is a lookup, not new machinery: build a second map keyed by
`(dimension, grain)` alongside the existing name map, and consult it when the ORDER BY target is a
`DateTrunc`/`TimestampTrunc`.[^ordering]

Three outcomes, and the middle one matters most:

| ORDER BY | Selected | Result |
|---|---|---|
| `DATE_TRUNC('month', d)` | `d` at `month` | accepted, orders by `d_month` |
| `DATE_TRUNC('day', d)` | `d` at `month` | refused, **naming the grain that is selected** |
| `DATE_TRUNC('month', d)` | `d` not projected at any grain | refused, listing the orderable names |

The second is the one to get right, because it is where the existing rule bites: ordering rows by a
day boundary the reader cannot see is the same defect as ordering by an unselected column, and saying
"month is what you selected" is the repair instruction.

One wrinkle found while reading rather than assumed: `_grain` **raises** `SemanticSyntaxError` for a
malformed grain rather than returning a refusal, and it is currently only ever called from
`_projections`, which sits inside the `try` that converts those raises into refusals.[^ordering]
`_ordering` is called from outside that block, so calling `_grain` there directly would let an
exception escape as a crash instead of a refusal. The call therefore has to be guarded locally, and a
test covers `ORDER BY DATE_TRUNC('fortnight', d)`.

For FR-5, the silent branch gains the same "Order by one of: …" sentence the position branch already
carries. That sentence is factored into one helper so a fourth branch cannot be added silent.

# Architecture decisions

1. **Match on `(dimension, grain)`, not on rendered SQL.** Comparing `item.sql()` strings would make
   `DATE_TRUNC('month', d)` and `date_trunc('MONTH', d)` different keys, and would silently start
   depending on sqlglot's formatting. Rejected.

2. **Resolve to the projection's output name.** The alternative — carrying the expression through to
   `compile.py` and re-emitting it in ORDER BY — needs a compiler change, emits SQL that is not
   currently emitted, and would then owe the allowlist an entry. Rejected on the grounds that the
   cheap version is also the safer one.[^compile]

3. **A different grain is refused, not silently re-pointed.** Accepting `ORDER BY DATE_TRUNC('day', d)`
   over a monthly series by quietly ordering on the month would answer a question nobody asked, in
   the row order specifically. Refusing it with the selected grain named is both honest and
   repairable.

4. **The message helper takes the orderable names, not the projections.** Keeps the sentence in one
   place and makes the silent-branch bug un-reintroducible by construction.

# Repository Impact Map

## Files to modify

- `src/semantiql/engine/validate.py` — `_ordering`: a `(entity, grain)` map beside `outputs`; a
  `DateTrunc`/`TimestampTrunc` branch before the `exp.Column` check; a guarded `_grain` call; and one
  helper carrying the "Order by one of: …" sentence, used by every refusal branch. **Trust-boundary
  artifact.**[^ordering] [^projection]
- `tests/engine/test_validate.py` — the accepted forms, both refusals, `DESC`/`NULLS`, the malformed
  grain, and that the alias form still works.[^order-tests]
- `tests/engine/test_validation_refuses.py` — the wrong-grain refusal never reaches the
  database.[^refusal-tests]
- `tests/integration/` — one end-to-end assertion that a monthly series comes back in month order,
  because the unit tests prove the `OrderKey` and not the row order.

## Files not touched, and one of them is the point

- `src/semantiql/engine/compile.py` — **unchanged, deliberately.** If this file needed editing, AD-2
  was wrong and the change is bigger than specced.[^compile]
- `src/semantiql/knowledge/` — no model change. A grain is not a declared entity.
- `plugin/skills/semantiql/SKILL.md` — the skill teaches `ORDER BY <name>`, which stays true. Whether
  to teach the expression form is a separate question: the alias form is shorter, and the skill's
  grain list is already pinned by a drift test.
- `docs/09-data-modeling.md` — describes the model, not the query surface.

# Open research questions

- **Should the skill teach the expression form now that it works?** Argument against: the alias is
  shorter and already taught, and every sentence added to a skill is context spent in every session.
  Argument for: it is what a model writes unprompted, as this spec's own evidence shows. Left open
  rather than decided here — it is a documentation judgement, and this change makes either choice
  safe.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, the allowlist rule, the trust-boundary list, and the refusal-path testing rule.
[^ordering]: `src/semantiql/engine/validate.py` — `_ordering`, its `outputs` map and three refusal branches; `_grain` raising `SemanticSyntaxError`.
[^projection]: `src/semantiql/engine/validate.py` — `Projection(entity, output, grain)` and the `f"{name}_{grain}"` alias in `_projections`.
[^compile]: `src/semantiql/engine/compile.py` — ordering emitted from `OrderKey.output`, which is why this needs no compiler change.
[^order-tests]: `tests/engine/test_validate.py` — the existing ORDER BY cases.
[^refusal-tests]: `tests/engine/test_validation_refuses.py` — `ExplodingAdapter`.
