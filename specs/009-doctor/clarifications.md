---
type: Clarifications
title: semantiql doctor — clarifications
description: 5 ambiguities resolved before planning.
resource: specs/009-doctor/clarifications.md
tags: [sdd, clarifications]
generated: { by: claude-code/claude-opus-5, at: '2026-08-17T00:04:41+07:00' }
status: stable
---

## Q1: `Adapter.columns` takes a relation string and interpolates it. Keep or change?

- (a) Keep the signature and have doctor pass whatever text the source needs.
- (b) Change it to take the model's `source` and let the adapter build the query from its own
  `relation()`.
- **Chosen:** (b) — decided by the agent from the method's own body and from the seam's stated
  rule. `columns` currently builds `SELECT * FROM {relation} LIMIT 0` by **string
  interpolation**, which is the exact pattern `relation()` exists to avoid and which
  `tests/test_compile.py` has a regression test against. It also cannot serve a CSV source
  without the caller reconstructing `read_csv_auto('…')` by hand — pushing adapter knowledge
  into the caller. Taking `source` and going through `relation()` fixes both, and doctor being
  the first caller is why nobody noticed.

## Q2: Where does physical-type knowledge live?

- (a) Doctor maps `VARCHAR`/`BIGINT`/`DATE` to the model's four types.
- (b) The adapter classifies its own types, returning the model's vocabulary alongside the
  native name.
- **Chosen:** (b) — decided by the agent from N4. Type names are engine vocabulary: DuckDB says
  `VARCHAR`, Postgres says `character varying`, BigQuery says `STRING`. Putting that table in
  shared code means every new datasource edits shared code, which is the design smell the
  constitution names. The adapter returns `Column(name, native_type, kind)` where `kind` is one
  of the model's own four types or `other`, and `other` is reported as "cannot tell" rather
  than as a mismatch — an honest unknown beats a confident wrong answer.

## Q3: Does doctor need a way to point at a real database?

- (a) No — models over CSV and Parquet work with the in-memory default.
- (b) Yes — add `--database`.
- **Chosen:** (b) — decided by the agent from what doctor is for. A model whose `source` is a
  table name has nothing to resolve against in an empty in-memory database, so doctor would
  report every table missing and be useless for precisely the setup it is meant to verify. The
  option is small, it applies to querying as well, and it routes through the adapter's existing
  read-only file path.

## Q4: What does doctor do about problems it finds?

- (a) Offer `--fix` to rewrite the YAML.
- (b) Report only.
- **Chosen:** (b) — decided by the agent from N3 and N6. The model is the source of truth and
  the schema tier is always human-reviewed; a tool that edits definitions is the thing the
  constitution most explicitly forbids. Doctor suggests, exactly as a refusal's `did_you_mean`
  does, and a human makes the edit.

## Q5: The docs promise doctor runs sample questions. Is that in scope?

- (a) Yes — the docs say so.
- (b) No, and say so plainly.
- **Chosen:** (b) — decided by the agent from what exists. `docs/03-setup-workflow.md` step 5
  describes doctor confirming answers to about five sample questions as part of exporting the
  Claude bundle, and the bundle is the MCP server, which is unbuilt. Shipping the half that can
  be built is right; quietly redefining doctor as only that half is not, so FR-9 requires the
  gap to be documented rather than left for someone to discover.
