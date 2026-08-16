---
type: Validation
title: semantiql doctor — validation
description: Acceptance criteria traced to FR-1..FR-9.
resource: specs/009-doctor/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T00:04:41+07:00' }
status: stable
---

# Acceptance criteria

- [x] **AC-1** (FR-1): an unloadable model is reported legibly and stops the run.
  - **Proven by:** a CLI test asserting exit 2 and the loader's message.
- [x] **AC-2** (FR-2): each source's readability and column count are reported.
  - **Proven by:** a doctor test over the bundled example, and one over a missing source.
- [x] **AC-3** (FR-3): a missing column is reported with a suggestion.
  - **Proven by:** a model whose measure reads `amont`, expecting a finding naming `amount`.
- [x] **AC-4** (FR-4): a declared type contradicting the column is reported.
  - **Proven by:** a model declaring `order_date` as `string`.
- [x] **AC-5** (FR-5): `sum` over a text column is reported.
  - **Proven by:** a model summing `channel`.
- [x] **AC-6** (FR-6): a dialect mismatch is reported.
  - **Proven by:** a model declaring postgres, checked with the DuckDB adapter.
- [x] **AC-7** (FR-7): exit codes 0/1/2/3 behave as specified.
  - **Proven by:** four CLI tests.
- [x] **AC-8** (FR-8): `--database` points the CLI at a DuckDB file.
  - **Proven by:** a test running doctor against a generated file-backed database.
- [x] **AC-9** (FR-9): the docs say what doctor does not yet do.
  - **Proven by:** reading `docs/03-setup-workflow.md`.

# Non-functional acceptance

- [x] The verify gate is green, both suites.
- [x] **N4** — `grep -rnE "adapters(\.|[[:space:]]+import)" src/semantiql/engine/` still matches
  only `adapters.base`; no DuckDB type name appears outside `adapters/`.
- [x] **N3** — doctor writes nothing; no test asserts a model file changed.
- [x] **N5** — `--database` opens read-only.

# Manual verification

1. `uv run semantiql doctor` — the bundled example reports healthy and exits 0.
2. Break a column name in a copy of the model, run doctor — exit 1, the problem named, a
   suggestion offered.
3. `uv run semantiql doctor -m tests/e2e/semantic_model.yml --database <corpus>` — the large
   model checks clean against the generated corpus.
