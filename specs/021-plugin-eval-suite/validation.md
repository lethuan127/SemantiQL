---
type: Validation
title: An eval suite for the plugin, over real ERP data — validation
description: Acceptance criteria traced to FR-1..FR-10, with the two externally blocked items named.
resource: specs/021-plugin-eval-suite/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T15:53:46+00:00' }
status: stable
---

# Acceptance criteria

- [x] **AC-1** (FR-1): Three cases under `plugin/evals/`, each `prompt.md` plus `graders/criteria.md`.
  - **Proven by:** `test_every_phase_has_a_case_and_a_grader`. The filename is `prompt.md` because the
    shipped CLI binary contains that literal **56 times** and `case.yaml` 23 times, while `case.md`
    appears **zero** times — checked directly against the binary rather than assumed.
- [x] **AC-2** (FR-2): Every grader states Must, Must-not, and how to score, with each rule traced to a
      shipped spec.
  - **Proven by:** `test_each_grader_states_musts_and_how_to_score` and
    `test_the_graders_cite_the_specs_that_created_their_rules`, the latter requiring specs 011, 016,
    018, 020 and N6 to appear.
- [x] **AC-3..AC-5** (FR-3..FR-5): the build, ask and enrich graders carry the rules the specs
      established, priced against the real corpus.
  - **Proven by:** reading them. The build grader turns on **there being no revenue column**; the ask
    grader turns on **reporting the gap** for a product category the data lacks; the enrich grader
    turns on saying **past numbers move**, and on asking which of two readings of "net of returns" is
    meant — they differ by ~1.5M on this data.
- [x] **AC-6** (FR-6): A trigger corpus in the official shape, all three phases, with negatives.
  - **Proven by:** `test_the_trigger_corpus_has_both_polarities` and
    `test_the_trigger_corpus_covers_all_three_phases` — 31 cases, 21 positive, 10 negative, no
    duplicates.
- [~] **AC-7** (FR-7): A loader that reads the token itself and never leaks it.
  - **Built, and its failure path is what got exercised.** `.test-workspace/fetch_salt.py` reads
    `HF_ACCESS_TOKEN` from the environment or `.env` **inside the script**; the value was never printed,
    never a command-line argument, never written anywhere, and never seen by the agent — the repo's own
    permissions deny reading `.env`, which is what made that design mandatory rather than merely tidy.
    **The download is blocked upstream**: see below.
- [x] **AC-8** (FR-8): No dataset is committed.
  - **Proven by:** `.gitignore` covers `.test-workspace/` entirely and `.env`/`.env.*` besides;
    `git status` shows no parquet, no xlsx, and nothing env-shaped.
- [x] **AC-9** (FR-9): Tests keep the corpus valid.
  - **Proven by:** six tests in `tests/interfaces/test_plugin.py`, including
    `test_every_cli_verb_a_grader_names_is_one_the_cli_dispatches` — the one that stops the corpus
    drifting away from the product and demanding a verb that does not exist.
- [x] **AC-10** (FR-10): Documentation states the gate and what to do instead.
  - **Proven by:** `plugin/evals/README.md` and the pointer in `plugin/README.md`.

# What is blocked, and by what

- **The native runner.** `claude plugin eval ./plugin --ablation with-without` answers
  **`\`plugin eval\` is currently in early access`** — tried again against the finished suite, which
  was T8, and recorded verbatim. The gate is an account entitlement in a compiled binary; there is no
  local flag, and routing around an access control was never on the table. **So no eval has been
  scored.** The suite's readiness is the claim; its passing is not.
- **SAP SALT.** The token in `.env` is valid — Hugging Face `whoami` returns 200 for user
  `lethuan127` with a fine-grained token — and `SAP/SALT` reads `gated: auto`. A file request returns
  **403** with the dataset's own words: *"Access to dataset SAP/SALT is restricted and you are not in
  the authorized list."* Accepting those terms is the owner's decision. One click, then
  `fetch_salt.py` runs.

# Non-functional acceptance

- [x] **Never commit secrets.** The token was never read by the agent, never echoed, never passed as an
      argument, and `.env` remains ignored and untracked.
- [x] **Licence discipline.** Online Retail II is CC BY 4.0 and attributed in the loader, the answer key
      and `plugin/evals/README.md`. Nothing downloaded is committed.
- [x] **CI stays free and offline.** Corpus *validation* is a pytest and runs in the gate; *running* the
      evals is neither free nor offline and is not a gate step.
- [x] **N6.** The enrich grader rewards editing only when the change was asked for deliberately, and
      rewards stopping when the same request arrives mid-answer.
- [x] The verify gate is green with Postgres up and with it down.

# Manual verification

1. `uv run python .test-workspace/fetch_retail.py` — expect 1,067,371 rows and a regenerated answer
   key. **Run**, twice, including from cold.
2. `uv run python .test-workspace/fetch_salt.py` — expect the 403 message naming the authorized list.
   **Run.**
3. `claude plugin eval ./plugin` — expect the early-access line. **Run.**
4. Read a grader and check every figure in it against `examiner/RETAIL-ANSWERS.md`. **Run** for the
   build grader; the ask and enrich graders quote the same two totals.

# A defect in my own process, recorded

The trigger corpus was written once, confirmed by reading it back, and then **found missing** later in
the same session — not in any commit, not in a stray path, and I cannot account for it. It was rewritten
from scratch. Worth knowing because it is the second time this session that work outside a commit went
missing or was silently clobbered, and the lesson is the boring one: an artefact that matters belongs in
a commit before the next thing starts.
