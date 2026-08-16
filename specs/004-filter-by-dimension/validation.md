---
type: Validation
title: Filter a request by its dimensions — validation
description: Acceptance criteria traced to FR-1..FR-8.
resource: specs/004-filter-by-dimension/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T22:45:37+07:00' }
status: stable
---

Every `FR-N` in the spec needs an `AC-N` here, or analyze reports it as a gap.

# Acceptance criteria

- [x] **AC-1** (FR-1): a filtered request returns the filtered number, not the total.
  - **Proven by:** end-to-end assertions against figures computed independently from the
    ten-row corpus — `channel = 'web'` → 956.50, July → 1491.74, July and web → 826.50,
    `IN ('web','retail')` → 1300.99, `region = 'north'` → 690.74.
- [x] **AC-2** (FR-2): every predicate in the supported set compiles and runs; `NOT LIKE`
  keeps its negation and `NOT IN` / `NOT BETWEEN` / `IS NOT NULL` keep theirs.
  - **Proven by:** a parametrized compile test per form, plus an explicit assertion that
    `NOT LIKE` renders as `NOT LIKE` and never as `LIKE`.
- [x] **AC-3** (FR-3): filtering on a measure is refused naming `HAVING`; filtering on an
  unknown name is refused with a suggestion. Neither reaches the datasource.
  - **Proven by:** cases in the refusal suite, run through `run` with `ExplodingAdapter`.
- [x] **AC-4** (FR-4): a literal contradicting the dimension's `type` is refused before
  execution — text against `number`, a non-ISO string against `date`, `LIKE` against a
  non-`string` dimension, ordering against `boolean`.
  - **Proven by:** one refusal case per rule.
- [x] **AC-5** (FR-5): a function, arithmetic, a subquery, or a column-to-column comparison
  inside `WHERE` is refused.
  - **Proven by:** four cases in the refusal suite.
- [x] **AC-6** (FR-6): a hostile literal cannot change the query's structure.
  - **Proven by:** a compile test filtering on a value containing a quote and a parenthesis,
    asserting the parsed output still has exactly one predicate and one relation — the same
    shape as the existing relation-injection regression.
- [x] **AC-7** (FR-7): every request answerable before this change still validates.
  - **Proven by:** the existing protected-surface suite, unchanged and still green.
- [x] **AC-8** (FR-8): the documentation records filters as supported and `type:` as enforced.
  - **Proven by:** reading `docs/09-data-modeling.md` §3.4, §8, A.2, A.5, A.6 and `AGENTS.md`.

# Non-functional acceptance

- [x] The repo's verify gate is green: `./scripts/verify.sh`.
- [x] **N1** — every new refusal case asserts through `run` with `ExplodingAdapter`.
- [x] **N2** — no predicate is partly applied: a form the walker does not fully consume is
  refused, and the per-node argument check makes an unread flag a refusal rather than a drop.
- [x] **N4** — `grep -rnE "adapters(\.|[[:space:]]+import)" src/semantiql/engine/` still
  matches only `adapters.base`.
- [x] No existing check weakened; the refusal suites only grow.

# Manual verification

1. `uv run semantiql "SELECT revenue FROM orders WHERE channel = 'web'" --show-sql` — expect
   956.5 and a `WHERE channel = 'web'` in the emitted SQL.
2. `uv run semantiql "SELECT revenue, channel FROM orders WHERE order_date >= '2026-07-01' AND order_date < '2026-08-01'"`
   — expect the July split, totalling 1491.74.
3. `uv run semantiql "SELECT revenue FROM orders WHERE amount > 100"` — expect a refusal:
   `amount` is not a dimension.
4. `uv run semantiql "SELECT revenue FROM orders WHERE revenue > 100"` — expect a refusal
   naming `HAVING`.
