---
type: Spec
title: Order and limit a request
description: ORDER BY over projected names plus LIMIT/OFFSET, making "top 5 by revenue" expressible — and finally exercising the transpile step
resource: specs/005-order-and-limit/spec.md
tags: [sdd, spec, validation, compile]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:16:47+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-15
  - id: filters
    resource: ../specs/004-filter-by-dimension/spec.md
    title: The filter spec whose allowlist-extension pattern this follows
    last_modified: 2026-08-16
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-16T23:16:47+07:00', checkpoint: 1,
      basis: '8 FRs, each testable; FR-8 converts an existing tripwire test into a real assertion, which the test itself asks for in its docstring; NFRs bind to N1, N2 and N4' }
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** The change edits the query-validation layer, a trust-boundary artifact by name, and
adds the first construct whose SQL differs between dialects.

# What

A request may say which order its rows come back in, and how many of them: `SELECT revenue,
channel FROM orders WHERE order_date >= '2026-07-01' ORDER BY revenue DESC LIMIT 5`.

Ordering is by something the request already selects, named as it was named. Limits and
offsets are plain non-negative whole numbers. Anything else — an ordinal, an expression, a
name that is not in the projection list — is refused.

Today `ORDER BY`, `LIMIT` and `OFFSET` are all refused, so "the top five channels" cannot be
asked for; the caller receives every row and has to sort them itself.

# Why

"Top N" is how a report is read. A ranked list of five channels is a report; the same five
channels in arbitrary order, with the other forty rows attached, is a data dump that a
non-technical user has to interpret.

There is a second reason, specific to this project's interface. The MVP consumer is an LLM
with a context window, and every unbounded result is spent tokens. A `LIMIT` is the only
thing that bounds a request's output, and without it the engine cannot answer a broad
question cheaply at all.

This change also makes constitution N4 testable for the first time. `LIMIT` is the first
construct SemantiQL emits whose SQL differs by dialect — `SELECT TOP 5` on T-SQL against
`LIMIT 5` on DuckDB and Postgres. Until now the transpile step was wired but unexercised,
and `tests/test_compile.py` says so in a tripwire test written to fail on exactly this day.

# User stories

- **As a business user**, I ask for the top five channels and get five rows, ranked — so the
  answer is the report rather than the raw material for one.
- **As an agent with a context budget**, I can bound a result — so a broad question does not
  cost the whole window.
- **As a contributor**, the transpile step is covered by a test that would fail if it were
  deleted — so N4's claim is verified for behaviour, not just for imports.

# Functional requirements

- **FR-1** — A request may carry `ORDER BY` over one or more names it projects, each
  optionally `ASC` or `DESC`, and the rows come back in that order.
- **FR-2** — `NULLS FIRST` is honoured where written. Where it is not written, null placement
  follows the target engine's default, and the documentation says so.
- **FR-3** — Ordering by anything the request does not project is refused: a positional
  ordinal (`ORDER BY 1`), an aggregate or expression, or a name absent from the projection
  list.
- **FR-4** — A request may carry `LIMIT` and `OFFSET`, each a non-negative whole-number
  literal. An expression, a negative number, or a non-integer is refused.
- **FR-5** — Every refusal in this change is decided before the datasource is reached.
- **FR-6** — Every request answerable before this change is still answered, unchanged.
- **FR-7** — The documentation records ordering and limits as supported, including the null
  placement rule.
- **FR-8** — The transpile tripwire in `tests/test_compile.py` is replaced by an assertion
  that a limited request renders differently on T-SQL than on DuckDB, as that test's own
  docstring instructs.

# Non-functional requirements

- **N1 (validation over generation)** — refusals are tested with the adapter that raises if
  called.[^constitution]
- **N2 (a silently wrong number is the worst failure)** — ordering and limiting change which
  rows a reader sees, so a dropped `DESC` or a dropped `LIMIT` is a wrong answer in the same
  way a dropped filter is. Every argument on an ordering node is read or refused, following
  the rule established in spec 004.[^filters]
- **N4 (canonical dialect, then transpile)** — the canonical SQL keeps DuckDB's spelling and
  sqlglot renders the target; no dialect branching enters `compile.py`.[^constitution]

# Out of scope

- **Ordering by something not selected**, which SQL permits and this engine refuses.
- **`FETCH FIRST … ROWS ONLY`**, `TOP` written by the caller, and `LIMIT ALL`.
- **Measure filters / `HAVING`**, time grains, and derived metrics.

[^constitution]: `.specify/memory/constitution.md` — N1, N2, N4 and the trust-boundary section.
[^filters]: `specs/004-filter-by-dimension/spec.md` — the predicate allowlist and its rule that
    every argument is read or the request is refused.
