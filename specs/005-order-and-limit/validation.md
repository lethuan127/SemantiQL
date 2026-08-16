---
type: Validation
title: Order and limit a request — validation
description: Acceptance criteria traced to FR-1..FR-8.
resource: specs/005-order-and-limit/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-16T23:16:47+07:00' }
status: stable
---

Every `FR-N` in the spec needs an `AC-N` here, or analyze reports it as a gap.

# Acceptance criteria

- [x] **AC-1** (FR-1): an ordered request returns rows in that order.
  - **Proven by:** an end-to-end assertion that channels ordered by revenue descending are
    `web, partner, retail` — a different order from the unordered result.
- [x] **AC-2** (FR-2): `NULLS FIRST` is honoured; otherwise the engine default applies.
  - **Proven by:** a compile assertion that `NULLS FIRST` survives the rebuild, and the
    documented rule for the unwritten case.
- [x] **AC-3** (FR-3): an ordinal, an aggregate, or an unprojected name is refused.
  - **Proven by:** three cases in the refusal suite, via `ExplodingAdapter`.
- [x] **AC-4** (FR-4): `LIMIT`/`OFFSET` accept whole numbers and refuse anything else.
  - **Proven by:** an end-to-end `LIMIT 1` returning one row, and refusals for `LIMIT 1+1`
    and a negative limit.
- [x] **AC-5** (FR-5): none of the above reaches the datasource.
  - **Proven by:** every refusal case runs through `run` with `ExplodingAdapter`.
- [x] **AC-6** (FR-6): the protected surface still validates.
  - **Proven by:** the existing suite, unchanged.
- [x] **AC-7** (FR-7): the documentation records ordering, limits, and null placement.
  - **Proven by:** reading `docs/09-data-modeling.md` §8 and A.2, and `AGENTS.md`.
- [x] **AC-8** (FR-8): the transpile step is covered by an assertion that would fail if it
  were removed.
  - **Proven by:** a test asserting a limited request renders `TOP` on T-SQL and `LIMIT` on
    DuckDB, replacing the tripwire.

# Non-functional acceptance

- [x] The repo's verify gate is green: `./scripts/verify.sh`.
- [x] **N2** — every `Ordered` argument is read or refused; `WITH FILL` is refused.
- [x] **N4** — no dialect branching in `compile.py`; the grep still matches only `adapters.base`.
- [x] No existing check weakened. The tripwire is replaced by a stronger assertion, as its own
  docstring instructs, not deleted.

# Manual verification

1. `uv run semantiql "SELECT revenue, channel FROM orders ORDER BY revenue DESC LIMIT 2" --show-sql`
   — expect web then partner, two rows, and an `ORDER BY … DESC LIMIT 2` in the SQL.
2. `uv run semantiql "SELECT revenue, channel FROM orders ORDER BY 1"` — expect a refusal
   naming the position.
3. `uv run semantiql "SELECT revenue FROM orders LIMIT -1"` — expect a refusal.
