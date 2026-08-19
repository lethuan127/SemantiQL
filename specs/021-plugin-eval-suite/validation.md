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


# Amendment — the case format, and a defect it uncovered

Recorded after shipping, because it changed a shipped artefact.

**The cases are now one `case.yaml` each**, at the repository owner's direction, replacing
`prompt.md` + `graders/criteria.md`. Both are shapes the CLI reads. `case.md` was asked for first and is
**not** read by this version — the binary contains `case.yaml` 23 times and `case.md` zero times — which
was reported rather than shipped quietly.

**The defect that discovery uncovered:** the original `graders/criteria.md` files carried **no
frontmatter**, and the binary's validator says
`grader .md: frontmatter missing type` with `type:` required to be one of
`regex | tool_order | tool_used | file_exists | llm | baseline`. **The graders as first shipped would have
been rejected outright.** Nothing in this repository could have caught that, because the runner is gated
and the tests only checked that the files existed and said certain things. They now assert a valid
`type:` on every grader, and that check was watched failing against a deliberately invalid type.

The schema — with its four genuinely unresolved edges, including the grader rubric field name — is
written up in `docs/11-plugin-eval.md`, a **trust-boundary document** added by this amendment.


# Second amendment — the full schema, and the cases it invalidated

Asked what else `execution` carries, I went back to the binary and found **the Zod schema itself**, not
just its error strings: the CLI embeds its own minified JavaScript, so the definition is readable with
every field, default and bound. `docs/11-plugin-eval.md` is rewritten from it, and most of what that
document previously listed as "not established" is now fact.

**`execution` has seven fields**, not the one I had documented: `prompt`, `max_turns` (default 10, max
200), `timeout_seconds` (default 300, max 3600), `model`, `allowed_tools`, `append_system_prompt`,
`env`.

**The cases as shipped were invalid**, in three ways, and each would have failed the whole case:

1. **Every grader requires a `name`.** Mine had none. The validator also refuses
   `duplicate grader name "X"`.
2. **`llm` spells its target `focus`; `regex` spells it `target`.** I used `target` on an `llm` grader.
   Every grader schema is `.strict()`, so that is a hard rejection, not a tolerated extra.
3. **`timeout_seconds` defaults to 300**, and these cases inspect a real database. The guide embedded
   beside the schema is blunt — *"an under-set timeout reads as a 0 score, not a timeout"* — so the
   suite would have scored zero and looked like a capability failure.

Fixed, and now enforced: `test_no_grader_carries_a_key_the_strict_schema_rejects` was watched failing
against exactly the `focus`→`target` slip that had shipped.

**The graders also changed shape, on the guide's own advice.** Its stated hierarchy is verifiable
first, `llm` last — *"use llm only when ①-② can't capture it"*. The rules from spec 020 are facts, so
they are now `regex` graders with `match: not_contains` and `arm: both`, plus a `tool_used` check that
the skill loaded at all. Asking a judge whether a run used `psql` was turning a fact into an opinion.

**None of this could have been found by running it** — the runner is still gated. It came from reading
the binary, which is worth recording as the technique rather than the incident.
