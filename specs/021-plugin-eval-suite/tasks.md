---
type: Tasks
title: An eval suite for the plugin, over real ERP data — tasks
description: 8 tasks, 2 parallel — fixture first, because a grader written without the data is a guess.
resource: specs/021-plugin-eval-suite/tasks.md
tags: [sdd, tasks]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T15:39:47+00:00' }
sources:
  - id: plan
    resource: /021-plugin-eval-suite/plan.md
    title: The approved plan these tasks derive from
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T15:39:47+00:00', checkpoint: 3,
      basis: 'The fixture comes first even though the cases were drafted first, because a grader that names a figure must name a real one — the taxi graders could quote 53.9M against 79.5M only because the data had been loaded and the totals computed. Reviewing the drafted cases against real ERP columns is T4, and it is a review rather than an acceptance.' }
---

Derived from the approved plan.[^plan]

**Why the fixture comes before the cases**, even though the cases were drafted first: a grader that
says "price the choice" has to name the columns and figures that make the choice real. Written against
an imagined ERP schema it would be fiction, and fiction in a grader is worse than no grader — it fails
runs for the wrong reason.

# Phase 1 — The licensed fixture

- [x] **T1.** `fetch_salt.py`: read `HF_ACCESS_TOKEN` from the environment or `.env` **inside the
      script**, download SALT's parquet files, load them into their own `semantiql_salt` database.
  - **Files:** `.test-workspace/fetch_salt.py`
  - **Depends on:** —
  - **Verification:** the four tables land and row counts print. The token appears in no output, no
    argument list, and no file.
  - **Constitution check:** **never commit secrets.** The token is read by the script, not by me, and
    not passed on a command line where it would reach a shell history or a process listing.

- [x] **T2.** Compute the answer key: the candidate revenue definitions and their totals, the document
      versus item grain, the currency columns, and anything negative.
  - **Files:** `.test-workspace/examiner/SALT-ANSWERS.md`
  - **Depends on:** T1
  - **Verification:** every figure a grader quotes traces to a query in this file.
  - **Constitution check:** licence — the key holds aggregates, not rows, and the workspace is ignored.

# Phase 2 — The cases

- [x] **T3.** Review the three drafted `graders/criteria.md` against FR-2..FR-5 and against the real
      schema, replacing any invented column or figure with one from T2.
  - **Files:** `plugin/evals/*/graders/criteria.md`
  - **Depends on:** T2
  - **Verification:** each Must cites the spec that created it; each figure traces to the answer key.
  - **Constitution check:** N6 — the enrich grader must reward stopping when the request arrives
    mid-answer, and editing only when it was asked for deliberately.

- [x] **T4.** Rewrite the three `prompt.md` files for the ERP domain — sales documents and items, not
      taxi trips.
  - **Files:** `plugin/evals/*/prompt.md`
  - **Depends on:** T3
  - **Verification:** each prompt is something an analyst would actually type, and names no column the
    fixture lacks.
  - **Constitution check:** — .

- [x] **T5. [P]** Review the trigger corpus: all three phases represented, negatives genuinely
      off-domain, nothing that is a coin toss.
  - **Files:** `plugin/skills/semantiql/evals/trigger_eval.json`
  - **Depends on:** —
  - **Verification:** 30 cases, both polarities, and no case whose correct answer is arguable.
  - **Constitution check:** — .

# Phase 3 — Keeping it honest

- [x] **T6.** Corpus validation tests: layout, a grader per case, unique trigger cases, both
      polarities, and every CLI verb a grader names is one `cli.py` dispatches.
  - **Files:** `tests/interfaces/test_plugin.py`
  - **Depends on:** T3, T5
  - **Verification:** `uv run pytest tests/interfaces/test_plugin.py -q`, and the verb check watched
    failing against a deliberately wrong verb first.
  - **Constitution check:** offline and free, so it belongs in the gate — unlike running the evals.

- [x] **T7. [P]** `plugin/evals/README.md` and the `plugin/README.md` pointer: the layout, how to run
      it, and that the native runner is gated behind early access.
  - **Files:** `plugin/evals/README.md`, `plugin/README.md`
  - **Depends on:** T4
  - **Verification:** a reader with no access understands what the suite is for and what to do instead.
  - **Constitution check:** trust boundary — `plugin/` is shipped product.

- [x] **T8.** Try the native runner once more against the finished suite, and record the exact outcome.
  - **Files:** — (a recorded observation)
  - **Depends on:** T7
  - **Verification:** whatever it prints, verbatim, in `validation.md`. If access has arrived, run it and
    report the scores; if not, the suite's readiness is the claim and its running is not.
  - **Constitution check:** never record a check as run when it was not.

# Final gates

- [x] **TF. Final verify** — `./scripts/verify.sh` with Postgres up and down.
- [x] **TV. Validation pass** — walk `validation.md`, and confirm `git status` shows no `.env`, no
      parquet, and no SALT rows anywhere near the index.

[^plan]: The impact map approved at gate 2.
