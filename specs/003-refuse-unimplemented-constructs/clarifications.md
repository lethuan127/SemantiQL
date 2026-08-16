---
type: Clarifications
title: Refuse every construct the compiler cannot honour, wherever it appears — clarifications
description: 4 ambiguities resolved before planning.
resource: specs/003-refuse-unimplemented-constructs/clarifications.md
tags: [sdd, clarifications]
generated: { by: claude-code/claude-opus-5, at: '2026-08-15T23:15:31+07:00' }
status: stable
---

## Q1: Should the fix extend the known-bad list, or invert it?

- (a) Add the two missing table-level constructs to `_UNSUPPORTED_CLAUSES` and check the
  table node as well as the select node.
- (b) Invert the check: state what the engine *can* answer, and refuse everything else by
  default, wherever it appears.
- **Chosen:** (b) — decided by the agent from the evidence in the defect itself. Both
  constructs were **already listed by name** in `_UNSUPPORTED_CLAUSES` and still did not
  fire, so the list was not the thing that failed — the enumerate-the-bad shape was. sqlglot
  parses all of SQL and the compiler implements a small subset of it, so a denylist has to
  enumerate an open set and silently rots on every parser change. FR-3 asks for
  default-refuse. Option (a) fixes two symptoms and leaves the class open.

## Q2: Does inverting the check tighten anything that is answered today?

- (a) Accept exactly what the compiler consumes, and refuse the rest — including a table
  alias, a catalog/schema prefix, and a column qualifier, all of which are currently parsed
  and then ignored.
- (b) Keep every request that is answered today answered, and change only the constructs that
  are currently accepted-and-dropped.
- **Chosen:** (b) — decided by the agent from FR-5, which lists those exact forms as
  behaviour that must not change. LLM-written SQL commonly qualifies columns and aliases
  tables, and refusing that would trade a silent-wrong-number bug for a wave of new refusals
  on requests the engine answers correctly. The allowlist therefore admits the *decorative*
  arguments the compiler safely ignores, and refuses the *semantic* ones it would drop.

## Q3: Is an ignored column qualifier the same defect?

- (a) Yes — treat `SELECT bogus.revenue FROM orders` as a silent drop and refuse it in this
  change.
- (b) No — it is a distinct, lesser issue: no computation is discarded, the entity still
  resolves against the one table in the request, and the answer is the one the model defines.
- **Chosen:** (b) — decided by the agent from the spec's Out of scope section and from the
  difference in consequence. A dropped `TABLESAMPLE` changes the number; an ignored qualifier
  does not. It is worth its own decision later — flagged in the run report as a follow-up, not
  folded in here where it would silently widen FR-5.

## Q4: Where does the check live, and do the per-construct messages survive?

- (a) A new module for request validation rules.
- (b) Inside `engine/validate.py`, keeping the existing label map so refusals still name the
  construct in the caller's vocabulary.
- **Chosen:** (b) — decided by the agent from the code map, which assigns "a request should be
  refused that currently isn't" to `engine/validate.py`, and from FR-4, which requires the
  refusal to name what caused it. A new module would add a top-level surface for one function
  and split the refusal logic across two files. Known constructs keep their current wording;
  anything unrecognised is named from the parsed node itself.
