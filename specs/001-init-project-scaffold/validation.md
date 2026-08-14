---
type: Validation
title: Initialize the SemantiQL repo — validation
description: Acceptance criteria traced to FR-1..FR-15, each naming what proves it.
resource: specs/001-init-project-scaffold/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-15T01:13:42+07:00' }
status: stable
---

Skeleton drafted at plan time; ticked during implement. Every `FR-N` in the spec has an `AC-N` here — analyze
reports any that does not.

# Acceptance criteria

## Working repo

- [x] **AC-1** (FR-1): From a clean clone, the documented sequence reaches a working environment, and an
      unsupported Python version fails naming the version found, the version needed, and the fix.
  - **Proven by:** a fresh directory, `uv sync` + the example query, timed at **3s**; and `uv run --python 3.10`
        rejected with `resolved to Python 3.10.20, which is incompatible with the project's Python requirement:
        \`>=3.11\``. *Caveat:* that message names the version found and the version needed but not the fix — the
        fix instruction lives in `CONTRIBUTING.md` and the README, not in the error itself.
- [x] **AC-2** (FR-2): `./scripts/verify.sh` exits 0 on a clean checkout, and exits non-zero naming the failed
      step when any single check is broken.
  - **Proven by:** a clean run; then temporarily breaking formatting, a type, and a test in turn.
- [x] **AC-3** (FR-3): The example runs with no network, no database install, and no credentials.
  - **Proven by:** running the example; confirming the only data read is `examples/retail/orders.csv`.
- [x] **AC-4** (FR-4): The example answers one question about the sample data, and the answer is correct.
  - **Proven by:** `tests/test_example_end_to_end.py`, asserting the value against a hand-computed figure.
- [x] **AC-5** (FR-5): An unvalidatable request returns a refusal, not a guess.
  - **Proven by:** `tests/test_validation_refuses.py` — asserts the refusal *and* that no adapter call occurred.
- [~] **AC-6** (FR-6): CI runs the same script as local, and completes on a pull request from a fork.
  - **PARTIAL — the fork half is unverified.** Statically confirmed: the workflow invokes `scripts/verify.sh`,
        declares `permissions: contents: read`, and contains zero `secrets.` references. The actual fork-PR run
        cannot be observed until a remote exists, which this spec puts out of scope. Do not tick on push.
- [x] **AC-7** (FR-7): A newcomer can find AC-1..AC-6 from the repo alone.
  - **Proven by:** a walk from `README.md` to `CONTRIBUTING.md` reaching setup, verify, and the example with no
        outside knowledge.

## Publishable repo

- [~] **AC-8** (FR-8): `SECURITY.md` names GitHub private reporting, no email, 5-business-day ack, 30-day fix
      or timeline, and asks reporters not to open a public issue.
  - **PARTIAL.** The file states the channel, the 5-business-day window and no email. Enabling GitHub's private
        vulnerability reporting is a repo setting that needs a remote — carry it to the publish checklist.
- [x] **AC-9** (FR-9): `CODE_OF_CONDUCT.md` is the Contributor Covenant verbatim with a personal reporting
      address — `levanthuan127@gmail.com`, supplied by the maintainer.
  - **Proven by:** `diff` against the upstream 2.1 source returned exactly one differing line (line 39, the
        reporting contact). No placeholder was ever written.
- [x] **AC-10** (FR-10): `CONTRIBUTING.md` carries setup with versions, all-checks and single-test commands,
      mergeable-PR criteria, weekly-triage-no-SLA, and what is out of scope.
  - **Proven by:** running every command it lists, from a clean clone.
- [x] **AC-11** (FR-11): The README's first screen answers what / does it work / is it maintained, and its SLA
      wording matches `CONTRIBUTING.md` exactly.
  - **Proven by:** reading the first screen; a diff of the two SLA sentences.
- [~] **AC-12** (FR-12): Issue forms and the PR template ask only what is needed to reproduce or review.
  - **PARTIAL.** Both forms declare `validations: required: true` on every field asked for. GitHub renders and
        enforces them only on a real repo, so the enforcement half needs a remote.
- [x] **AC-13** (FR-13): No published command is stale — no `npx semantiql` survives, and every command shown
      runs as written.
  - **Proven by:** `grep -rn "npx semantiql" README.md docs/` returning nothing; executing each published
        command.

## Comprehensible repo

- [x] **AC-14** (FR-14): Each of the four layers maps to its module, the adapter seam is named, and the
      unimplemented layer is stated as unimplemented rather than omitted.
  - **Proven by:** `docs/07-code-map.md` checked against the actual tree; every path it names **as existing**
        exists. *Amended during implement:* the original wording said "every path it names", which failed on
        `src/semantiql/governance/` — the deliberately-unbuilt layer, named as a future location. Naming it is
        the requirement, so the criterion was wrong, not the doc.
- [x] **AC-15** (FR-15): Differences from Cube, dbt Semantic Layer, MetricFlow and Malloy are stated, each
      claim either sourced or marked as SemantiQL's intent.
  - **Proven by:** every comparative sentence carrying a citation or an explicit intent framing — no unsourced
        assertion about another product's behaviour.

# Non-functional acceptance

- [x] `./scripts/verify.sh` green, output reported verbatim.
- [~] **N1 / N2:** *Corrected after code review.* Two distinct claims, and the original tick conflated them.
      **Through `run()`: now holds** — every clause the compiler cannot honour is refused, proven by 13
      parametrised cases in `tests/test_validation_refuses.py` that were each a silent wrong number before.
      **As an absolute statement about all code paths: does not hold** — `DuckDBAdapter().execute(sql)` reaches
      the database directly, and the repo's own adapter test does so. Enforced by convention and review, not by
      the type system; a validated-SQL type would make it structural.
- [x] **N3:** no semantic-model values are embedded in Python; `knowledge/loader.py` is the only YAML reader.
- [~] **N4:** *Corrected after code review.* No concrete-adapter import under `engine/` — but the original
      grep (`grep -rn "adapters\."`) misses `from semantiql.adapters import duckdb`; it is now
      `grep -rnE "adapters(\.|[[:space:]]+import)"`. Behaviourally the claim is weaker than stated: DuckDB is
      hard-coded as the parse dialect and `CANONICAL_DIALECT`, and transpiling is a **verified no-op** for
      every SQL shape the engine currently emits (7 dialects, byte-identical — see the tripwire test in
      `tests/test_compile.py`). Import-independence holds; dialect-independence is untested.
- [~] **N5:** *Corrected after code review.* A **file-backed** connection is opened `read_only=True`; an
      **in-memory** one cannot be (DuckDB: `Cannot launch in-memory database in read-only mode!`), and
      in-memory is the CLI default. On that path read-only is enforced by `validate` refusing every
      non-SELECT, not by the connection. The original tick asserted the connection unconditionally, which was
      false for the only path the repo actually runs.
- [x] **N7:** the resolved dependency tree contains no NoSQL client.
- [x] `pyproject.toml`'s SPDX id matches `LICENSE`.
- [x] Setup completes in ≤ 5 minutes on a normal machine, timed and recorded.
- [x] Every response-time promise in the repo is one the maintainer accepted at clarify — no invented windows.
- [x] The OKF bundle validates with 0 errors.

# Manual verification

1. Clone into a fresh directory, follow the README quickstart verbatim, and time it. Anything ambiguous is an
   FR-1 defect, not a user error.
2. Run `./scripts/verify.sh` and read the output as a stranger would — does a failure tell you what to fix?
3. Run the example. Check the number by hand against `orders.csv`.
4. Ask for something the model cannot answer. Confirm a refusal with a reason, not a plausible number.
5. Open the repo as if evaluating it: does the first screen say what it is, whether it works, and whether it is
   maintained — without scrolling?
