---
type: Tasks
title: Model directory — tasks
description: 9 tasks plus two gate tasks — the loader merge with its four refusals, describe_model's index, the worked example, then the skill and docs.
resource: specs/015-model-directory/tasks.md
tags: [sdd, tasks, knowledge, mcp]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T04:35:00+07:00' }
sources:
  - id: plan
    resource: plan.md
    title: The approved plan, AD-1..AD-5, the impact map and OQ-1..OQ-2
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T04:36:00+07:00', checkpoint: 3,
      basis: '11 tasks in dependency order; one [P] group checked disjoint. T1 merges raw mappings so one validation pass still covers everything. T6 is the amendment: Table gained a description because FR-8 promised one and the model had none — recorded in the plan before the code. T8 updates four existing tests to a contract that changed by design rather than loosening them' }
status: stable
---

## ✅ T1. The directory branch and the merge

- **Files:** `src/semantiql/knowledge/loader.py`
- **Do:** AD-1 — read every `.yml`/`.yaml` under the directory in sorted order, merge the raw
  mappings, validate **once** with the existing schema. Track which file declared each table.
- **Verification:** the bundled single-file example still loads unchanged.

## ✅ T2. The four refusals

- **Files:** `src/semantiql/knowledge/loader.py`
- **Depends on:** T1
- **Do:** refuse a table defined twice, `datasource`/`version` declared twice, no `datasource` at
  all, and a file that contributes nothing or declares an unrecognised key. **Every message names
  the file** — in a tree of thirty, an error that could be about any of them is barely an error.
- **Verification:** covered by T4.

## ✅ T3. Per-file source resolution

- **Files:** `src/semantiql/knowledge/loader.py`
- **Depends on:** T1
- **Do:** FR-5 — `_resolve_sources` takes the provenance map and resolves each relative `source`
  against its own declaring file. Resolving against the directory root would break the moment
  anyone grouped tables into subdirectories, which is the reason to use a directory.
- **Verification:** T4 asserts a CSV beside its YAML in a subdirectory.

## ✅ T4. `[P]` Loader tests

- **Files:** `tests/test_loader.py`
- **Depends on:** T2, T3
- **Do:** directory loading, subdirectories, each of the four refusals with its message, per-file
  resolution, and the bundled warehouse example.
- **Verification:** 10 new cases green; existing loader tests unchanged.

## ✅ T5. `[P]` The worked example

- **Files:** `examples/warehouse/**` (new)
- **Depends on:** T3
- **Do:** `datasource.yml` plus two tables in subdirectories, one sourcing a CSV a directory up and
  one beside its own YAML — so the layout is demonstrated, not only described.
- **Verification:** `semantiql doctor -m examples/warehouse` exits 0.

> **`[P]` group — T4 and T5 are disjoint:** {`tests/test_loader.py`} · {`examples/warehouse/`}.

## ✅ T6. `Table.description`

- **Files:** `src/semantiql/knowledge/model.py`
- **Depends on:** T1
- **Do:** an optional `description`. **Amendment**: the plan said this file would not change, and
  FR-8 promised the index carries a description the model had no field for. Recorded in `plan.md`
  before the code, not after. **Trust-boundary artifact.**
- **Verification:** every existing model still loads; the field is optional.

## ✅ T7. `describe_model(table=None)`

- **Files:** `src/semantiql/server.py`
- **Depends on:** T6
- **Do:** FR-8..FR-11 — an index of `TableSummary` always, `detail` for the named table, the
  one-table shortcut (AD-4), and an unknown name answered with the real ones. One shape either way,
  with `next_step` saying what to do. **Still two tools.**
- **Verification:** covered by T8.

## ✅ T8. Server tests, including four that had to change

- **Files:** `tests/test_server.py`
- **Depends on:** T7
- **Do:** both shapes, the shortcut, the index's counts, the unknown-table reply, and the tool
  count. **Four existing tests broke** because entities moved from `tables` to `detail` — the
  contract changed by design, so they were updated to it rather than loosened.
- **Verification:** 26 green.

## ✅ T9. The skill

- **Files:** `plugin/skills/semantiql/SKILL.md`
- **Depends on:** T7
- **Do:** the two-step shape with a worked call, why it exists, and that an unknown name is
  answered with the real ones. The drift test must stay green.
- **Verification:** `tests/test_plugin.py` green.

## ✅ T10. Docs

- **Files:** `docs/09-data-modeling.md`, `docs/10-adopting-semantiql.md`, `docs/07-code-map.md`,
  `README.md`, `AGENTS.md`
- **Depends on:** T9
- **Do:** `09` gains the layout and the four rules as a table; `10`'s one-table advice becomes
  grow-into-a-directory; the code map notes the loader reads either. **Do not edit `CLAUDE.md`.**
  **`07` and `09` are trust-boundary.**
- **Verification:** no document describes a rule the loader does not enforce.

## ✅ TF. Final verify · ✅ TV. Validation pass

- `./scripts/verify.sh` both ways, then walk every AC.

[^plan]: `plan.md` — the impact map, AD-1..AD-5, OQ-1..OQ-2.
