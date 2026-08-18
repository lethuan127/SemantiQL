---
type: Plan
title: An eval suite for the plugin, over real ERP data — plan
description: Native evals/ cases graded from shipped rules, a fetch-on-demand SALT fixture that never touches git, and offline validation in the gate.
resource: specs/021-plugin-eval-suite/plan.md
tags: [sdd, plan]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T15:39:10+00:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-17
  - id: cli-help
    resource: ../plugin/README.md
    title: claude plugin eval --help, transcribed — the evals/**/prompt.md + graders/*.md layout
    last_modified: 2026-08-18
  - id: official-corpora
    resource: ../plugin/skills/semantiql/evals/trigger_eval.json
    title: The two official corpus shapes, copied from math-olympiad and skill-creator
    last_modified: 2026-08-18
  - id: fetch-nyc
    resource: ../.test-workspace/fetch.py
    title: The existing loader this one mirrors — download, own database, answer key
    last_modified: 2026-08-18
  - id: plugin-tests
    resource: ../tests/interfaces/test_plugin.py
    title: Where corpus validation goes, beside the existing drift tests
    last_modified: 2026-08-18
  - id: gitignore
    resource: ../.gitignore
    title: .env and .env.* already ignored; nothing env-shaped is tracked
    last_modified: 2026-08-18
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T15:39:10+00:00', checkpoint: 2,
      basis: 'Six rows, all footnoted. Two facts were established by running rather than reading: `.env` is covered by .gitignore and no env-shaped file is tracked, and the Read tool is denied on .env by the user own permissions — which is what settles AD-3, the script reading the token itself rather than the token being handed to me. The eval layout came from the shipped CLI help and two official plugins on disk.' }
---

# Constitution check

**Never commit secrets.** The token is in `.env`, which `.gitignore` already covers, and nothing
env-shaped is tracked.[^gitignore] The design constraint that follows is AD-3: the fetch script reads
the token itself. It is never echoed, never a command-line argument (where it would land in a shell
history and in any process listing), and never written to a file the repository can see.[^constitution]

**CI stays secret-free and dependency-light.** Running the evals needs a token, a licensed dataset, a
database and paid model calls, so it cannot be a gate step. **Validating the corpus needs none of
those**, so that part does go in the gate — which is the half that actually prevents rot.[^constitution]

**N6.** The enrich case is where a grader could teach the wrong lesson. Its criteria reward editing
*only* when the change was deliberately requested, and reward stopping when the same request arrives
mid-answer.[^constitution]

**Trust boundary.** `plugin/` is shipped product. This adds a directory to it and does not change
`SKILL.md`; if that changes, it is called out separately.

**Licence.** SALT is CC-BY-NC-SA-4.0 — non-commercial, share-alike. Fetch-on-demand is what keeps the
repository clear of it, and the licence is named wherever the fixture is described.

# Approach

**The cases are the deliverable, and they are prose.** A grader is a markdown file of Must and Must-not
statements, each traceable to a shipped spec. That is the native format's own design: the runner reads
`prompt.md`, runs the agent, and asks a judge to grade against `graders/*.md`.[^cli-help] It means the
suite is useful before it is runnable, because the criteria are the clearest statement anyone has of
what correct behaviour is.

**Two corpora, both official shapes.** `plugin/evals/<case>/` for behaviour, and
`plugin/skills/semantiql/evals/trigger_eval.json` for triggering — a flat `{query, should_trigger}`
list, which is what `math-olympiad` ships and where a skill-level trigger corpus belongs.[^official-corpora]

**The fixture mirrors the loader that already works.** `fetch_salt.py` follows `fetch.py`: download to
an ignored directory, load its **own** database, then compute an answer key.[^fetch-nyc] SALT's four
tables arrive as parquet, so DuckDB reads them and copies them into Postgres exactly as the taxi loader
does — no new dependency, and the same `ATTACH` path already proven on 2.96M rows.

**Validation goes where the drift tests are.** `tests/interfaces/test_plugin.py` already asserts things
about the skill's text; corpus validation is the same kind of check and belongs beside it rather than in
a new file nobody remembers.[^plugin-tests]

# Architecture decisions

1. **Author to the native layout even though the runner is gated.** Rejected: waiting for access, which
   leaves the rules unwritten and the next regression uncaught; and rejected: inventing a bespoke
   format, which would have to be migrated later and would not benefit from ablation when access lands.

2. **Graders cite the spec that created each rule.** A rule with no provenance gets softened by whoever
   finds it inconvenient. "No raw `psql` (spec 020)" is arguable against; "no raw SQL" alone is not
   defensible when someone needs a number in a hurry.

3. **The script reads `.env`; the token never reaches me or a command line.** The user's own permissions
   deny reading `.env`, and that is the right boundary rather than an obstacle: a token I never see
   cannot be leaked into a transcript, a log, or an artefact. Rejected: asking for the value to be
   exported into the session, which would put it in this conversation verbatim.

4. **SALT gets its own Postgres database, `semantiql_salt`.** Rejected: reusing `semantiql_test`, which
   belongs to the `pg` suite — already tried once with the taxi fixture, and it buried the fixture among
   the suite's tables and pointed a `DROP SCHEMA … CASCADE` at someone else's data.

5. **Corpus validation is offline and in the gate; running the evals is neither.** The split is what
   makes this maintainable: the free half runs on every commit, and the expensive half is a deliberate
   command.

6. **The trigger corpus carries negatives.** A corpus of only positives measures nothing — a skill whose
   description matched everything would score perfectly. Ten of the thirty cases must **not** trigger.

# Repository Impact Map

## Files to add

- `plugin/evals/{01-build-the-model,02-ask-a-business-question,03-enrich-the-model}/prompt.md` and
  `graders/criteria.md` — six files, the native layout. **A draft of these was written before this
  lifecycle was invoked**; the implement phase reviews them against FR-2..FR-5 rather than treating
  them as done.[^cli-help]
- `plugin/skills/semantiql/evals/trigger_eval.json` — 30 cases, 20 positive and 10 negative, spanning
  all three phases. Also drafted early, same treatment.[^official-corpora]
- `plugin/evals/README.md` — the layout, how to run it, and that the native runner is gated.
- `.test-workspace/fetch_salt.py` — the licensed fixture loader. Lives in the ignored workspace because
  it is a development rig, not shipped product.[^fetch-nyc]

## Files to modify

- `tests/interfaces/test_plugin.py` — FR-9: the corpus is well-formed, ids unique, both polarities
  present, every case has a grader, every CLI verb a grader names exists.[^plugin-tests]
- `plugin/README.md` — FR-10: point at the suite, and state the gate.
- `scripts/verify.sh` — **only** if the corpus validation needs a step of its own; it does not, because
  it is a pytest and the suite already runs.

## Files not touched

- `plugin/skills/semantiql/SKILL.md` — no change. The graders describe what the skill already says; if
  writing them reveals the skill is missing a rule, that is a finding to report, not a silent edit.
- `src/semantiql/` — nothing here is a product change.
- `.env` — read by the script at runtime, never modified, never read by me.

# Open research questions

- **Where do `--tag` and `--case` metadata live in the native format?** `--help` documents both filters,
  and the `prompt.md` shape has no obvious place for tags — they are probably a `case.yaml` field, and I
  have no example of that file. Directory names are chosen so `--case '01-*'` works regardless. Flagged
  rather than guessed: inventing frontmatter the runner may reject would make the suite fail on the day
  it first runs.

[^constitution]: `.specify/memory/constitution.md` — never commit secrets, CI secret-free, N6, trust boundaries.
[^cli-help]: `claude plugin eval --help`, transcribed in `plugin/README.md`: cases are `evals/**/prompt.md` with `graders/*.md`.
[^official-corpora]: `math-olympiad/skills/math-olympiad/evals/trigger_eval.json` and `skill-creator/skills/skill-creator/references/schemas.md`.
[^fetch-nyc]: `.test-workspace/fetch.py` — download, own database, generated answer key.
[^plugin-tests]: `tests/interfaces/test_plugin.py` — the existing skill drift tests.
[^gitignore]: `.gitignore` lines 17-18 (`.env`, `.env.*`), and `git ls-files` showing nothing env-shaped tracked.
