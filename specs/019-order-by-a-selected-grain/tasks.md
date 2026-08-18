---
type: Tasks
title: Order by a time grain the request already selects — tasks
description: 7 tasks, 2 parallel — reproduce first, then the silent branch, then the capability.
resource: specs/019-order-by-a-selected-grain/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T13:42:45+00:00' }
sources:
  - id: plan
    resource: /019-order-by-a-selected-grain/plan.md
    title: The approved plan these tasks derive from
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T13:42:45+00:00', checkpoint: 3,
      basis: 'The message fix (T2) lands before the capability (T3) on purpose: it is the actual defect, it is what would have prevented the wrong report, and it must be correct even for the queries that stay refused. Sequencing it second would let the capability mask it, since the case that motivated this spec would then never reach a refusal at all.' }
---

Derived from the approved plan.[^plan]

# Phase 1 — Reproduce

- [x] **T1.** Write the failing tests: the expression form refused, the message naming nothing, and
      the alias form working. **Watch them fail.**
  - **Files:** `tests/engine/test_validate.py`
  - **Depends on:** —
  - **Verification:** the refusal-message assertion fails against `main`; the alias assertion passes,
    which is what proves the capability was present and only unreachable.
  - **Constitution check:** — .

# Phase 2 — The defect: a refusal that cannot be repaired

- [x] **T2.** Give every ORDER BY refusal the orderable names, via one helper so a future branch
      cannot be added silent.
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** T1
  - **Verification:** all three existing branches carry the names; the function branch no longer
    ends at *"is not one."*
  - **Constitution check:** **trust-boundary artifact.** This is the half that matters for N2 — the
    observed harm was a *worse answer delivered confidently*, caused by a message a capable reader
    could only read as "not supported".

# Phase 3 — The capability

- [x] **T3.** Accept `ORDER BY DATE_TRUNC('<grain>', <dimension>)` when the request selects that
      dimension at that grain, resolving to the projection's output name.
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** T2
  - **Verification:** the query from the spec runs; `compile.py` is untouched and the emitted SQL is
    identical to the alias spelling's.
  - **Constitution check:** N1 — an accepted ORDER BY resolves to a column the request already
    projects, so nothing new reaches the database.

- [x] **T4.** Refuse a **different** grain, naming the grain that is selected; refuse a dimension the
      request does not project.
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** T3
  - **Verification:** both messages name the repair. Ordering by a boundary the reader cannot see
    stays refused — the existing rule, not a new one.
  - **Constitution check:** N2 — this is the branch where being permissive would reorder rows by
    something invisible.

- [x] **T5.** Guard the `_grain` call. It **raises** rather than returning a refusal, and `_ordering`
      sits outside the `try` that converts those raises.
  - **Files:** `src/semantiql/engine/validate.py`
  - **Depends on:** T3
  - **Verification:** `ORDER BY DATE_TRUNC('fortnight', order_date)` is refused, not a traceback.
  - **Constitution check:** a crash is not a refusal. An unhandled exception on the query path is the
    one outcome that is neither an answer nor a stated reason.

# Phase 4 — Prove it end to end

- [x] **T6. [P]** The wrong-grain refusal never reaches the database.
  - **Files:** `tests/engine/test_validation_refuses.py`
  - **Depends on:** T4
  - **Verification:** `ExplodingAdapter` is not called.
  - **Constitution check:** the repo's rule for validation changes, followed.

- [x] **T7. [P]** A monthly series actually comes back in month order.
  - **Files:** `tests/integration/`
  - **Depends on:** T3
  - **Verification:** row order asserted against real output. The unit tests prove the `OrderKey`;
    only this proves the rows.
  - **Constitution check:** — .

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh` with Postgres up and down, so both engines are
      covered and the skips stay honest.
- [x] **TV. Validation pass** — walk `validation.md`; and re-run the original query against the
      2.96M-row NYC database, which is where this started.

[^plan]: The impact map approved at gate 2.
