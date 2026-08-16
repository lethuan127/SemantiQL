---
type: Plan
title: Refuse every construct the compiler cannot honour, wherever it appears — plan
description: Invert the clause check from an enumerated denylist to an allowlist of what the compiler consumes, at both the select level and inside the FROM subtree.
resource: specs/003-refuse-unimplemented-constructs/plan.md
tags: [sdd, plan, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-15T23:15:31+07:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-15
  - id: validate
    resource: ../src/semantiql/engine/validate.py
    title: The current denylist loop, its ordering, and every refusal message it emits
    last_modified: 2026-08-15
  - id: compile
    resource: ../src/semantiql/engine/compile.py
    title: What the compiler actually consumes from a validated request — projections and the relation only
    last_modified: 2026-08-15
  - id: run
    resource: ../src/semantiql/engine/run.py
    title: The chokepoint order — validate, then compile, then execute
    last_modified: 2026-08-15
  - id: refusal-tests
    resource: ../tests/test_validation_refuses.py
    title: The ExplodingAdapter pattern and the parametrized silent-drop suite the regressions join
    last_modified: 2026-08-15
  - id: ast-probe
    resource: ../src/semantiql/engine/validate.py
    title: AST probe run at plan time over sqlglot 30.17.0 — truthy select args and FROM-subtree node types for every accepted and refused form
    last_modified: 2026-08-15
  - id: coverage-map
    resource: ../docs/09-data-modeling.md
    title: Appendix A — the published SQL coverage map, which records both constructs as accepted-and-dropped
    last_modified: 2026-08-15
  - id: agents-brief
    resource: ../AGENTS.md
    title: The agent brief, which instructs contributors to edit `_UNSUPPORTED_CLAUSES` by name
    last_modified: 2026-08-15
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-15T23:15:31+07:00', checkpoint: 2,
      basis: 'map derived from 6 file reads plus an AST probe over sqlglot 30.17.0 covering 9 protected and 7 refused forms; all 4 existing-file rows footnoted to a source read at plan time; 0 open questions outstanding' }
status: stable
---

# Constitution check

- **N1 — validation over generation.** The change adds refusals and removes none. The new
  checks run inside `validate`, before `run` resolves a relation or reaches an adapter, so a
  refused request still never touches the datasource.[^constitution][^run]
- **N2 — a silently wrong number is the worst failure.** This is the invariant the change
  restores. Two constructs are accepted and discarded today; after this change any construct
  the compiler does not consume is refused by default.[^constitution][^validate]
- **N3 — the YAML is the source of truth.** Untouched; no model value moves into Python.[^constitution]
- **N4 — canonical dialect, then transpile.** Untouched. `validate.py` keeps parsing with
  `read="duckdb"`, and no adapter import is added, so the existing grep stays clean.[^constitution][^validate]
- **N5 — read-only.** Strengthened marginally: the statement-type refusal is unchanged, and
  the new default-refuse cannot admit a write path.[^constitution]
- **N6, N7** — not touched.
- **Trust boundary.** `engine/validate.py` is where N1 and N2 live, and `docs/09-data-modeling.md`
  is a `docs/NN-*.md` design doc. Both are trust-boundary artifacts, which is why this runs at
  T2 with regression tests rather than as a patch.[^constitution]

No invariant needs amending.

# Approach

The check inverts. Today `validate` walks a tuple of known-bad clause names against
`parsed.args`; the compiler consumes far less than SQL can express, so that list must
enumerate an open-ended set and it stops matching whenever sqlglot moves a node.[^validate]

Instead, state what the engine consumes and refuse the rest. `compile_request` reads exactly
two things from a validated request: the projection list, and the table it selects
from.[^compile] So an answerable request is exactly:

- a `SELECT` whose only truthy arguments are its projections and its `FROM`, and
- a `FROM` subtree containing only the table, its name parts, and an optional alias — where
  every node in that subtree also carries only the arguments its type is allowed to carry
  (see architecture decision 5, added during implement).

An AST probe over sqlglot 30.17.0, run at plan time across every form FR-5 protects and every
form that must be refused, gives the two allowlists directly:[^ast-probe]

| | Accepted forms produce | Offenders add |
|---|---|---|
| truthy `Select` args | `expressions`, `from_` — and nothing else, across all 9 protected forms | `where`, `distinct`, `joins`, `limit`, … |
| `FROM`-subtree node types | `From`, `Table`, `Identifier`, `TableAlias` | `TableSample`, `Pivot`, `Literal`, `Var`, `Column`, `In`, `Sum` |

That is the whole fix: two frozensets, and a walk of the FROM subtree. `TABLESAMPLE` and
`PIVOT`/`UNPIVOT` are caught not because they are named but because they are **not on the
list** — which is what makes the class closed rather than the two instances patched.

Two details the code must keep:

- **Argument-name spelling.** sqlglot spells the FROM argument `from_` in 30.17.0, and the
  existing code already defends against that suffix moving between versions.[^validate] The
  allowlist compares on a normalised name with one trailing underscore stripped, so both
  spellings match permanently.
- **Message quality.** FR-4 requires the refusal to name the construct. The enumerated tuple
  becomes a label lookup used only for wording — `where` → `WHERE`, `TableSample` →
  `TABLESAMPLE` — with a derived fallback for anything unlisted, so an unknown construct is
  still refused and still named.

Check order is preserved so every existing refusal message stays attached to the same input:
statement type → select-argument allowlist → FROM shape and single-table → **new FROM-subtree
allowlist** → model resolution → projections.[^validate]

# Architecture decisions

1. **Allowlist, not denylist.** The set of constructs the engine implements is small, known,
   and changes only when someone implements one; the set it does not implement is everything
   else SQL can express. Enumerate the small side. Adding a feature now means *adding* to an
   allowlist in the same change that adds the compiler support — the same discipline the
   denylist asked for, but failing closed instead of open.
2. **Two allowlists, not one tree walk.** A single type-allowlist over the whole parsed tree
   would also work, but it would take over the projection-list checks and replace their
   specific message (`each selected item must be a plain dimension or measure name…`) with a
   generic one. Splitting select-args from the FROM subtree leaves `_projections` owning the
   projection message.
3. **The label map is presentation only.** No refusal decision reads it. A construct missing
   from it is refused with a name derived from the parsed node, so an incomplete map degrades
   wording, never safety — the opposite of today, where an incomplete list degrades safety.
4. **Scope stops at the FROM subtree and the select args.** The ignored column qualifier
   (Q3) is left as-is and reported as a follow-up.
5. **Amended during implement — the FROM check is by argument, not only by node type.** A
   node-type walk alone is insufficient, because `walk()` yields only expression nodes and
   sqlglot stores some constructs as **scalar** arguments on the table: `FROM ONLY orders`
   sets `only=True` and `WITH ORDINALITY` sets `ordinality=True`. Neither is an expression,
   so neither appears in the walk, and both were still accepted and dropped after the first
   implementation — `ONLY` materially changes the row set on Postgres. `_FROM_NODES` is
   therefore replaced by `_FROM_NODE_ARGS`, a mapping from each allowed node type to the
   arguments it may carry; an unknown *type* and an unknown *argument on a known type* are
   both refused. This is the same lesson the spec already records, one level further in: the
   first fix generalised over position, this one generalises over representation.

# Repository Impact Map

**Files to modify**

- `src/semantiql/engine/validate.py` — replace `_UNSUPPORTED_CLAUSES` (line 38) with
  `_SELECT_ARGS` and `_FROM_NODE_ARGS` allowlists (`_FROM_NODES` per decision 5) plus
  `_CLAUSE_LABELS` / `_NODE_LABELS` for
  wording; replace the loop at line 150 with the select-argument check; add the FROM-subtree
  walk between the single-table check (line 166) and `model.table(...)` (line 169); rewrite
  the module docstring, which currently describes the enumerate-the-bad approach and lists
  the clauses by name.[^validate]
- `tests/test_validation_refuses.py` — add `TABLESAMPLE`, `PIVOT` and `UNPIVOT` cases to the
  parametrized `test_unsupported_clauses_are_refused_never_dropped` suite (line 86), which
  already runs through `run` with `ExplodingAdapter` and therefore asserts the datasource was
  never reached; add a test that the refusal names the construct for a table-level one; add a
  parametrized test that all nine FR-5 forms still validate.[^refusal-tests]
- `docs/09-data-modeling.md` — Appendix A.2: the `TABLESAMPLE` and `PIVOT`/`UNPIVOT` rows move
  from ⚠️ to ❌; A.6 is rewritten from "two entries do not fire" to how default-refuse works;
  the `_UNSUPPORTED_CLAUSES` references at lines 344 and 369 are renamed.[^coverage-map]
  **This is a `docs/NN-*.md` trust-boundary file.**
- `AGENTS.md` — line 64 instructs contributors to remove a clause from `_UNSUPPORTED_CLAUSES`
  when implementing it; that constant no longer exists, so the instruction becomes "add it to
  the allowlist in the same change".[^agents-brief] `CLAUDE.md` is a symlink to this file and
  needs no separate edit.

**Files to add**

- None. The change is entirely inside existing modules.

**Files not touched, but adjacent**

- `src/semantiql/engine/compile.py` — its docstring already says it compiles only what
  `validate` admits, which stays true and becomes more true.[^compile]
- `src/semantiql/engine/run.py` — the chokepoint order is unchanged.[^run]
- `src/semantiql/knowledge/*`, `src/semantiql/adapters/*`, `src/semantiql/cli.py` — no change;
  refusal handling and exit codes are untouched.
- `docs/07-code-map.md` — describes `validate.py` as "resolve every identifier against the
  model, or refuse", which remains accurate.

# Open research questions

None outstanding. The one question that could have changed the file list — whether the
allowlist tightens currently-accepted forms — was resolved from evidence in Q2, and the AST
probe confirms all nine protected forms produce only allowlisted arguments and node
types.[^ast-probe]

[^constitution]: `.specify/memory/constitution.md` — N1–N7 and the trust-boundary artifacts section.
[^validate]: `src/semantiql/engine/validate.py` — `_UNSUPPORTED_CLAUSES` at line 38, the loop at line 150 with its both-spellings comment, the FROM checks at lines 158–174, and the message text each emits.
[^compile]: `src/semantiql/engine/compile.py` — `compile_request` reads `request.projections` and the passed relation, nothing else.
[^run]: `src/semantiql/engine/run.py` — `run` validates before it resolves a relation or calls `execute`.
[^refusal-tests]: `tests/test_validation_refuses.py` — `ExplodingAdapter` and the parametrized suite at line 86.
[^ast-probe]: AST probe over sqlglot 30.17.0 run at plan time: 9 accepted forms yielded truthy select args `{expressions, from_}` and FROM-subtree types `{From, Identifier, Table, TableAlias}`; the offenders each added an extra arg or node type.
[^coverage-map]: `docs/09-data-modeling.md` — Appendix A.2 rows and A.6, plus the `_UNSUPPORTED_CLAUSES` mentions at lines 344 and 369.
[^agents-brief]: `AGENTS.md` — the invariants section, line 64.
