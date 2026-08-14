---
type: Spec
title: Initialize the SemantiQL repo
description: A clone reaches a working dev environment, one verify command checks it, one example runs on bundled data with no database, and a stranger can contribute without asking a question.
resource: specs/001-init-project-scaffold/spec.md
tags: [sdd, spec, scaffold, tooling, open-source]
generated: { by: claude-code/claude-opus-5, at: '2026-08-15T00:26:10+07:00' }
verified:
  - { by: human:thuan.le, at: '2026-08-15T01:04:59+07:00', checkpoint: 1, approval: 'approved' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time (status draft, pending approval)
    last_modified: 2026-08-15
  - id: readme
    resource: ../README.md
    title: Project README — the zero-setup DuckDB clone promise and the MVP roadmap
    last_modified: 2026-08-14
  - id: setup-workflow
    resource: ../docs/03-setup-workflow.md
    title: Setup workflow — automated checks and fix-instruction design principles
    last_modified: 2026-08-14
  - id: covenant
    resource: https://www.contributor-covenant.org
    title: Contributor Covenant — the code of conduct to adopt verbatim
  - id: clarifications
    resource: /001-init-project-scaffold/clarifications.md
    title: Clarify-phase decisions — runtime, security channel, conduct contact, review turnaround
    last_modified: 2026-08-15
status: stable
sdd_phase: shipped
sdd_tier: T2
---

**T2.** Four T1 conditions fail at once: new top-level directories, a project manifest other tools resolve
against, the first external dependencies, and the creation of trust-boundary artifacts.

**Deliberately one spec, not three.** Splitting into working (FR-1–7), publishable (FR-8–13), and
comprehensible (FR-14–15) was considered and declined on 2026-08-15. The setup sequence, the checks CI runs,
and the quickstart the README shows are literally the same commands; specifying them separately would mean
writing them three times and letting them drift — the failure this repo's whole verify-gate design exists to
prevent. The cost is accepted: one impact map covering everything at gate 2, and a long implement in which
gate 3's task ordering and the scope-drift detector carry more weight than usual.

# What

Someone who clones SemantiQL can, by following one documented sequence:

1. Reach a working development environment.
2. Run a single command that checks the project and tells them plainly whether it is healthy.
3. Run one example end to end against sample data that ships with the repo — no database to install, no
   connection string, no credentials.

And someone who arrives from the outside — not the author — can tell what the project is, whether it works,
whether it is maintained, how to contribute, and how to report a vulnerability privately. They can do all of
that from the repo itself, without asking a question.

Today a clone yields documentation and nothing else: nothing to install, nothing to run, no way to tell
whether a change broke anything, and no route for a stranger to contribute or to report a security problem.

# Why

The project is design-complete and code-empty. Six design docs describe a four-layer system, and the README
promises that "anyone cloning the repo can run it immediately".[^readme] Right now that promise is unmet,
and every future change is blocked behind the same missing groundwork.

The concrete scenario: a data analyst reads the README, wants to see whether SemantiQL answers a question
correctly over their own CSV, clones the repo — and finds there is nothing to run. They leave. The same wall
blocks contributors: with no verify command, nobody can tell a working change from a broken one, and code
review has nothing to stand on.

The open-source artifacts belong in this same change rather than a later one. The setup commands a
`CONTRIBUTING.md` documents, the checks CI runs, and the quickstart the README shows are all *the same
commands* this change creates — writing them separately means inventing them twice and letting them drift.
The one that cannot wait at all is a private security channel: without it, the first vulnerability report
arrives as a public issue with a working exploit in it.

This spec covers groundwork only. It is the change that makes every later change reviewable, and the repo
publishable.

# User stories

- **As a contributor**, I clone the repo, follow the documented setup, and get a working environment — so I
  can make a change and know whether I broke something.
- **As a data analyst evaluating the project**, I clone the repo and run the bundled example within minutes,
  without installing a database — so I can decide whether SemantiQL is worth my time.
- **As an engineer evaluating the approach**, I learn how SemantiQL works and how it differs from Cube, the
  dbt Semantic Layer, MetricFlow, and Malloy — without reading the source — so I can judge whether the idea
  is sound before spending a day on it.
- **As an engineer reading the code for the first time**, I can map each of the four architectural layers to
  the module that implements it — so I know where a change belongs instead of guessing.
- **As an engineer adding a datasource**, I find the adapter seam and what the core guarantees around it —
  so I can add MySQL without touching the core, and N4 stays a fact rather than an aspiration.
- **As a reviewer**, I run one command and see a pass or a fail — so a pull request is judged on evidence
  rather than on reading.
- **As an outside contributor**, I learn from the repo what a mergeable change looks like, how long review
  takes, and what will be declined — so I don't spend a day on a PR nobody wanted.
- **As a security researcher**, I find a private channel and use it — so a vulnerability does not become a
  public zero-day.
- **As the maintainer**, every push runs the same checks a contributor runs locally — so "works on my
  machine" stops being a review argument.

# Functional requirements

## Working repo

- **FR-1** — A documented setup sequence takes a clean clone to a working development environment. It states
  the required runtime versions, and when one is unmet it fails with a message naming the version found, the
  version needed, and how to fix it.[^setup-workflow]
- **FR-2** — One verify command runs the project's checks (formatting, static analysis, tests). It exits
  non-zero on any failure, exits zero on a clean checkout, and names which check failed.
- **FR-3** — Sample data ships in the repo, and the bundled example reads it without any external database,
  service, credential, or network access.
- **FR-4** — One example runs end to end and produces a correct, human-readable answer to one question about
  the sample data.
- **FR-5** — The example's path from question to answer passes through the validation step. A request that
  cannot be validated returns a refusal, not a guess — demonstrable by a test that asserts the refusal.
- **FR-6** — Automated checks run on every push and pull request, and are the same ones FR-2 runs locally, so
  the two cannot disagree. **They run to completion on a pull request from a fork**, which means the whole
  set works with no repository secrets and a read-only token.
- **FR-7** — A contributor can discover FR-1 through FR-6 from the repo itself, without being told.

## Publishable repo

- **FR-8** — `SECURITY.md` routes vulnerabilities through GitHub's private reporting only — no published
  email — asks reporters not to open a public issue, and commits to acknowledgement within **5 business
  days** and a fix or timeline within **30 days**.[^clarifications]
- **FR-9** — `CODE_OF_CONDUCT.md` adopts the Contributor Covenant verbatim,[^covenant] customised only with a
  personal reporting address unconnected to either employer. **The address is not yet supplied**, and this
  requirement does not ship until it is — a conduct channel nobody reads is worse than none.[^clarifications]
- **FR-10** — `CONTRIBUTING.md` takes someone with no context from a clean clone to a mergeable pull request:
  setup with runtime versions, how to run all the checks and how to run a single test, what makes a PR
  mergeable, and what will not be accepted. It states review as **best-effort, triaged weekly, no SLA**, and
  asks that a large change start as an issue.[^clarifications]
- **FR-11** — The README's first screen answers, in order: what this is, whether it works, and whether it is
  maintained — the last naming the maintainer and stating **weekly triage, no SLA**, matching FR-10 exactly
  so the two cannot drift.[^clarifications]
- **FR-12** — Structured issue forms and a pull-request template ask for exactly what is needed to reproduce
  or review, and no more.
- **FR-13** — Every install and setup command published in `README.md` and `docs/` is the command that
  actually works. The existing `npx semantiql init` predates the runtime decision and must not survive this
  change. `docs/NN-*.md` is a trust-boundary artifact, so implement pauses and confirms the diff before
  editing it.[^constitution]

## Comprehensible repo

- **FR-14** — A documented orientation path takes an engineer from "what is this" to "where does my change
  go": each of the four architectural layers maps to the module implementing it, and the datasource adapter
  seam is named explicitly, with what the core guarantees either side of it.[^constitution]
- **FR-15** — The repo states how SemantiQL differs from the prior art it names — Cube, the dbt Semantic
  Layer, MetricFlow, Malloy — in terms an evaluating engineer can check. Every comparative claim is either
  sourced or stated as the project's intent rather than as fact about someone else's product.

# Non-functional requirements

- **N1 + N2 (validation over generation; a silently wrong number is the worst failure)** — the skeleton must
  not create any path where a request reaches the data without passing validation. FR-5 exists to hold this
  invariant from the first commit, when it is cheap, rather than retrofitting it later.[^constitution]
- **N3 (one YAML file is the source of truth)** — the example's semantic model is a YAML file read from
  disk, not values embedded in code.[^constitution]
- **N4 (canonical dialect, then transpile; one adapter per datasource, no core changes)** — the skeleton
  must leave a seam where a second datasource plugs in without changing the core. Whether it does is
  testable by the next datasource spec, so the plan must name the seam explicitly.[^constitution]
- **N5 (read-only by default)** — nothing in the setup or the example requires write access to any data
  source.[^constitution]
- **N7 (no NoSQL)** — no NoSQL client enters the dependency set.[^constitution]
- **Trust boundary** — this change creates the project manifest and dependency lockfile, which the
  constitution names as trust-boundary artifacts from the moment they exist. Every later change touching
  them is T2 by definition.[^constitution]
- **Setup speed** — the FR-1 sequence completes in ≤ 5 minutes on a normal machine, consistent with the
  ≤ 15-minute end-to-end builder flow the design docs commit to.[^setup-workflow]
- **No promise the maintainer cannot keep** — every response-time commitment in FR-8, FR-10, and FR-11 must
  be one that is actually met. An unmet promise in a support statement or a code of conduct is worse than
  its absence.
- **Licence consistency** — the SPDX identifier in the project manifest matches `LICENSE`, because registries
  and scanners read the manifest field rather than the file.

# Out of scope

Deferred to their own specs, each tempting to pull in here:

- The real semantic SQL engine, and semantic-to-raw SQL translation beyond what FR-4 needs to run once.
- The MCP server and the Claude integration.
- The Postgres adapter. FR-3 requires only the bundled, no-install path.
- The accuracy benchmark against raw-table querying.
- Schema introspection and semantic-model auto-generation (`semantiql init`).
- Publishing to any package registry, and cutting a release or a `CHANGELOG.md`.
- The self-improvement loop — verified examples, gap detection, YAML change proposals.
- Seeding `good first issue` tickets — worth doing, but it needs code to point at.

**Publishing was out of scope for this spec**, and was carried out separately on 2026-08-15 at the
maintainer's direction, after a pre-push audit found no secrets, no credential-shaped history and no
machine-local paths in tracked files. Publishing is a one-way door: once a repository is public, every commit
in its history has been distributed and no later edit takes that back — which is why the audit ran against
the final tree rather than an earlier one.

# Open questions

Clarify ran on 2026-08-15 and resolved all four; see [clarifications.md](clarifications.md).[^clarifications]

The **runtime** is Python with uv, single runtime, recorded in the constitution's tech-stack
section.[^constitution] It stays out of this spec because a spec carries no tech; the user-visible consequence
is FR-13.

**One value is still outstanding**, and it gates a single requirement rather than the plan: the personal
reporting address FR-9 needs. Planning proceeds; the FR-9 implement task stops until the address exists.

[^constitution]: `.specify/memory/constitution.md` — non-negotiables N1–N7, trust-boundary artifacts, and the open tech-stack decision. Draft status at spec time.
[^readme]: `README.md` — the DuckDB "zero-setup demo … anyone cloning the repo can run it immediately" claim and the MVP roadmap row.
[^setup-workflow]: `docs/03-setup-workflow.md` — "every step has automated checks, and errors come with fix instructions", and the ≤ 15-minute builder flow.
[^covenant]: The Contributor Covenant, adopted verbatim with only the reporting contact customised.
[^clarifications]: `clarifications.md` — the four clarify-phase decisions, made by the maintainer on 2026-08-15.
