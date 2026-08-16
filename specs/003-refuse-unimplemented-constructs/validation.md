---
type: Validation
title: Refuse every construct the compiler cannot honour, wherever it appears — validation
description: Acceptance criteria traced to FR-1..FR-6.
resource: specs/003-refuse-unimplemented-constructs/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-15T23:15:31+07:00' }
status: stable
---

Every `FR-N` in the spec needs an `AC-N` here, or analyze reports it as a gap.

# Acceptance criteria

- [x] **AC-1** (FR-1): `SELECT revenue FROM orders TABLESAMPLE (10 PERCENT)` returns a
  `Refusal`, and no adapter method is called.
  - **Proven by:** the case in the parametrized suite in `tests/test_validation_refuses.py`,
    which runs through `run` with `ExplodingAdapter` — every adapter method raises, so a
    request that reached the datasource fails the test rather than passing it.
- [x] **AC-2** (FR-2): the same holds for `PIVOT` and for `UNPIVOT`.
  - **Proven by:** two more cases in the same parametrized suite.
- [x] **AC-3** (FR-3): refusal is the default. A construct that appears in neither label map
  is still refused — the decision reads the allowlists, never the labels.
  - **Proven by:** a test that a construct absent from `_CLAUSE_LABELS` / `_NODE_LABELS` is
    refused; plus code inspection that no refusal branch is conditional on a label lookup.
    Strengthened by T8: `FROM ONLY orders` and `WITH ORDINALITY` are refused as unknown
    *arguments*, a representation the first implementation did not see at all.
- [x] **AC-4** (FR-4): each refusal names the construct that caused it.
  - **Proven by:** an assertion that the `TABLESAMPLE` refusal contains `TABLESAMPLE`, next
    to the existing `WHERE` assertion.
- [x] **AC-5** (FR-5): all nine protected forms still validate to a `ValidRequest` —
  bare name, alias, quoted identifier, qualified entity, table alias, schema prefix,
  catalog+schema prefix, trailing semicolon, comment.
  - **Proven by:** a new parametrized test over those nine forms, plus the unchanged
    end-to-end assertions in `tests/test_example_end_to_end.py`.
- [x] **AC-6** (FR-6): the published coverage map records these constructs as refused.
  - **Proven by:** reading Appendix A.2 and A.6 of `docs/09-data-modeling.md` — no ⚠️ rows
    remain, and A.6 describes the default-refuse rule instead of the gap.

# Non-functional acceptance

- [x] The repo's verify gate is green: `./scripts/verify.sh`.
- [x] **N1** — every new refusal test asserts through `run` with `ExplodingAdapter`, so it
  proves the datasource was never reached, not merely that a refusal came back.
- [x] **N2** — no construct is accepted-and-ignored after the change; the ⚠️ category is empty.
- [x] **N4** — `grep -rnE "adapters(\.|[[:space:]]+import)" src/semantiql/engine/` still
  matches only `adapters.base`.
- [x] No check was weakened to make anything pass; the refusal suite only grows.

# Manual verification

1. `uv run semantiql "SELECT revenue FROM orders TABLESAMPLE (10 PERCENT)"` — expect
   `refused: TABLESAMPLE is not supported yet…` on stderr and exit code 1, where today it
   prints a full-table number and exits 0.
2. `uv run semantiql "SELECT revenue FROM orders PIVOT (SUM(amount) FOR channel IN ('web'))"`
   — expect a refusal naming PIVOT.
3. `uv run semantiql "SELECT revenue, channel FROM orders" --show-sql` — expect the same SQL
   and the same three rows as before the change.
