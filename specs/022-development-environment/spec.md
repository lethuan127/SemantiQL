---
type: Spec
title: A new machine can reproduce the development rig
description: Seven fixture and harness scripts were gitignored, so a fresh clone lacked them; they move to scripts/fixtures/ and the machine setup is documented.
resource: specs/022-development-environment/spec.md
tags: [sdd, spec]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T16:19:55+00:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-17
  - id: gitignore
    resource: ../.gitignore
    title: The rule that hid the scripts — .test-workspace/ ignored in its entirety
    last_modified: 2026-08-18
  - id: contributing
    resource: ../CONTRIBUTING.md
    title: The Setup section a new machine reads today, and what it omits
    last_modified: 2026-08-17
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T16:19:55+00:00', checkpoint: 1,
      basis: 'The gap was measured, not supposed: seven .py/.sh/.sql files sit under .test-workspace/, which .gitignore excludes entirely, so .claude-plugin/marketplace.json
.claude/agents/sdd-coach.md
.claude/skills/okf/SKILL.md
.claude/skills/okf/reference/attestation.md
.claude/skills/okf/reference/authoring.md
.claude/skills/okf/reference/consuming.md
.claude/skills/okf/reference/format.md
.claude/skills/okf/reference/profiles.md
.claude/skills/okf/scripts/validate_bundle.py
.claude/skills/sdd/SKILL.md
.claude/skills/sdd/reference/analyze.md
.claude/skills/sdd/reference/clarify.md
.claude/skills/sdd/reference/constitution.md
.claude/skills/sdd/reference/implement.md
.claude/skills/sdd/reference/plan.md
.claude/skills/sdd/reference/specify.md
.claude/skills/sdd/reference/tasks.md
.coverage
.githooks/commit-msg
.githooks/pre-commit
.github/ISSUE_TEMPLATE/bug.yml
.github/ISSUE_TEMPLATE/feature.yml
.github/PULL_REQUEST_TEMPLATE.md
.github/dependabot.yml
.github/workflows/ci.yml
.github/workflows/publish.yml
.gitignore
.specify/memory/constitution.md
AGENTS.md
CHANGELOG.md
CLAUDE.md
CODE_OF_CONDUCT.md
CONTRIBUTING.md
LICENSE
README.md
SECURITY.md
bundle/README.md
bundle/server.py
compose.yaml
docs/01-product.md
docs/02-architecture.md
docs/03-setup-workflow.md
docs/04-self-improvement.md
docs/05-datasources.md
docs/06-research-notes.md
docs/07-code-map.md
docs/08-positioning.md
docs/09-data-modeling.md
docs/10-adopting-semantiql.md
docs/11-plugin-eval.md
docs/README.md
examples/retail/orders.csv
examples/retail/semantic_model.postgres.yml
examples/retail/semantic_model.yml
examples/warehouse/datasource.yml
examples/warehouse/sales/orders.yml
examples/warehouse/support/tickets.csv
examples/warehouse/support/tickets.yml
plugin/.claude-plugin/plugin.json
plugin/.mcp.json
plugin/README.md
plugin/evals/01-build-the-model/case.yaml
plugin/evals/02-ask-a-business-question/case.yaml
plugin/evals/03-enrich-the-model/case.yaml
plugin/evals/README.md
plugin/skills/semantiql/SKILL.md
plugin/skills/semantiql/assets/datasource.template.yml
plugin/skills/semantiql/assets/table.template.yml
plugin/skills/semantiql/evals/trigger_eval.json
plugin/skills/semantiql/references/model-fields.md
plugin/skills/semantiql/references/refusals.md
pyproject.toml
scripts/build_bundle.py
scripts/eval_plugin.py
scripts/install-hooks.sh
scripts/lint_commit_msg.py
scripts/verify.sh
specs/001-init-project-scaffold/clarifications.md
specs/001-init-project-scaffold/plan.md
specs/001-init-project-scaffold/spec.md
specs/001-init-project-scaffold/tasks.md
specs/001-init-project-scaffold/validation.md
specs/003-refuse-unimplemented-constructs/clarifications.md
specs/003-refuse-unimplemented-constructs/plan.md
specs/003-refuse-unimplemented-constructs/spec.md
specs/003-refuse-unimplemented-constructs/tasks.md
specs/003-refuse-unimplemented-constructs/validation.md
specs/004-filter-by-dimension/clarifications.md
specs/004-filter-by-dimension/plan.md
specs/004-filter-by-dimension/spec.md
specs/004-filter-by-dimension/tasks.md
specs/004-filter-by-dimension/validation.md
specs/005-order-and-limit/clarifications.md
specs/005-order-and-limit/plan.md
specs/005-order-and-limit/spec.md
specs/005-order-and-limit/tasks.md
specs/005-order-and-limit/validation.md
specs/006-derived-metrics/clarifications.md
specs/006-derived-metrics/plan.md
specs/006-derived-metrics/spec.md
specs/006-derived-metrics/tasks.md
specs/006-derived-metrics/validation.md
specs/007-time-grains/clarifications.md
specs/007-time-grains/plan.md
specs/007-time-grains/spec.md
specs/007-time-grains/tasks.md
specs/007-time-grains/validation.md
specs/008-e2e-suite/clarifications.md
specs/008-e2e-suite/plan.md
specs/008-e2e-suite/spec.md
specs/008-e2e-suite/tasks.md
specs/008-e2e-suite/validation.md
specs/009-doctor/clarifications.md
specs/009-doctor/plan.md
specs/009-doctor/spec.md
specs/009-doctor/tasks.md
specs/009-doctor/validation.md
specs/010-postgres-adapter/clarifications.md
specs/010-postgres-adapter/plan.md
specs/010-postgres-adapter/spec.md
specs/010-postgres-adapter/tasks.md
specs/010-postgres-adapter/validation.md
specs/011-time-grain-timezones/clarifications.md
specs/011-time-grain-timezones/plan.md
specs/011-time-grain-timezones/spec.md
specs/011-time-grain-timezones/tasks.md
specs/011-time-grain-timezones/validation.md
specs/012-mcp-server/clarifications.md
specs/012-mcp-server/plan.md
specs/012-mcp-server/spec.md
specs/012-mcp-server/tasks.md
specs/012-mcp-server/validation.md
specs/013-plugin-and-skill/clarifications.md
specs/013-plugin-and-skill/plan.md
specs/013-plugin-and-skill/spec.md
specs/013-plugin-and-skill/tasks.md
specs/013-plugin-and-skill/validation.md
specs/014-desktop-bundle/plan.md
specs/014-desktop-bundle/spec.md
specs/014-desktop-bundle/tasks.md
specs/014-desktop-bundle/validation.md
specs/015-model-directory/plan.md
specs/015-model-directory/spec.md
specs/015-model-directory/tasks.md
specs/015-model-directory/validation.md
specs/016-schema-discovery/plan.md
specs/016-schema-discovery/spec.md
specs/016-schema-discovery/tasks.md
specs/016-schema-discovery/validation.md
specs/017-plugin-marketplace/plan.md
specs/017-plugin-marketplace/spec.md
specs/017-plugin-marketplace/tasks.md
specs/017-plugin-marketplace/validation.md
specs/018-skill-runnable-commands/plan.md
specs/018-skill-runnable-commands/spec.md
specs/018-skill-runnable-commands/tasks.md
specs/018-skill-runnable-commands/validation.md
specs/019-order-by-a-selected-grain/plan.md
specs/019-order-by-a-selected-grain/spec.md
specs/019-order-by-a-selected-grain/tasks.md
specs/019-order-by-a-selected-grain/validation.md
specs/020-profile-through-semantiql/plan.md
specs/020-profile-through-semantiql/spec.md
specs/020-profile-through-semantiql/tasks.md
specs/020-profile-through-semantiql/validation.md
specs/021-plugin-eval-suite/plan.md
specs/021-plugin-eval-suite/spec.md
specs/021-plugin-eval-suite/tasks.md
specs/021-plugin-eval-suite/validation.md
specs/_template/clarifications.md
specs/_template/index.md
specs/_template/plan.md
specs/_template/spec.md
specs/_template/tasks.md
specs/_template/validation.md
specs/index.md
specs/log.md
src/semantiql/__init__.py
src/semantiql/__main__.py
src/semantiql/adapters/__init__.py
src/semantiql/adapters/base.py
src/semantiql/adapters/duckdb.py
src/semantiql/adapters/postgres.py
src/semantiql/cli.py
src/semantiql/doctor.py
src/semantiql/engine/__init__.py
src/semantiql/engine/compile.py
src/semantiql/engine/run.py
src/semantiql/engine/validate.py
src/semantiql/knowledge/__init__.py
src/semantiql/knowledge/expression.py
src/semantiql/knowledge/loader.py
src/semantiql/knowledge/model.py
src/semantiql/server.py
tests/__init__.py
tests/_support.py
tests/adapters/__init__.py
tests/adapters/test_duckdb_adapter.py
tests/adapters/test_postgres_adapter.py
tests/conftest.py
tests/e2e/__init__.py
tests/e2e/conftest.py
tests/e2e/semantic_model.postgres.yml
tests/e2e/semantic_model.yml
tests/e2e/test_differential.py
tests/e2e/test_edge_semantics.py
tests/e2e/test_postgres_parity.py
tests/engine/__init__.py
tests/engine/test_compile.py
tests/engine/test_validate.py
tests/integration/__init__.py
tests/integration/test_doctor.py
tests/integration/test_grain_timezones.py
tests/integration/test_postgres_differential.py
tests/integration/test_retail_answers.py
tests/interfaces/__init__.py
tests/interfaces/test_bundle.py
tests/interfaces/test_cli.py
tests/interfaces/test_plugin.py
tests/interfaces/test_server.py
tests/knowledge/__init__.py
tests/knowledge/test_expression.py
tests/knowledge/test_loader.py
tests/tooling/__init__.py
tests/tooling/test_commit_msg_lint.py
uv.lock shows none of them and a fresh clone has none. Every tool named in the requirements was installed during this session and is missing from CONTRIBUTING, which is how the omission was found — by having done it.' }
sdd_phase: shipped
sdd_tier: T2
---

**T2.** Adds a `docs/NN-*.md` — a trust-boundary artifact — and moves seven files into a committed
location. Neither is T1.

# What

A new machine can clone this repository and reproduce everything the development rig does: load the
fixtures, run a discovery run under debug logging, grade a transcript, and score the plugin.

**Today it cannot, in two separate ways.**

**The scripts do not exist on a fresh clone.** `build.py`, `fetch.py`, `fetch_retail.py`,
`fetch_salt.py`, `judge.py`, `run-debug.sh` and `seed.sql` all live under `.test-workspace/`, and
`.gitignore` excludes that directory in its entirety.[^gitignore] Each of those files says, in its own
docstring, that *the script is the artefact and the data is output* — and then the script is ignored
along with the data. `git ls-files` lists none of them.

**The tools they need are undocumented.** `CONTRIBUTING.md`'s Setup section covers `uv sync` and
Docker.[^contributing] It does not mention that the fixtures shell out to `psql`, that the interactive
eval harness needs `tmux`, that scoring the plugin needs a third-party plugin installed from a
marketplace, or that three DuckDB extensions are fetched at first use and therefore need network.

# Why

**The claim each script makes about itself is false today.** "Fetch on demand, never commit the data"
is the right design for a 46 MB licensed workbook. It becomes wrong when the fetcher is ignored too,
because then nothing is preserved and the reproducibility the design was for is lost. The distinction
the `.gitignore` rule needs to draw is between *code* and *output*, and it currently draws it between
*one directory* and *everything else*.

**The cost is silent and lands on someone else.** Nothing fails on this machine. It fails on the next
one, as a missing file with no history, and the person hitting it has no way to know the script ever
existed. That is the shape of failure this project spends most of its effort refusing elsewhere.

**Every requirement below was learned by installing it.** `tmux` was installed mid-session to get a
TTY for an eval run; `psql` came from a Homebrew keg the fixtures then depended on; PluginEval arrived
from a marketplace; DuckDB's `httpfs`, `postgres` and `excel` extensions were each fetched on first
use. None of that is in `CONTRIBUTING.md`, which is exactly the documentation gap a session that
actually did the work is best placed to close.

# User stories

- **As a contributor on a new machine**, I follow one document and end with a working rig — or a clear
  statement of which optional piece I am missing and what it costs me.
- **As a contributor with no Docker**, I learn that before I hit a failing test rather than after.
- **As a maintainer**, a script that matters is in git, so it survives a clone.

# Functional requirements

- **FR-1** — The seven scripts live in a committed directory, `scripts/fixtures/`.
- **FR-2** — They keep working from there: data, answer keys and logs still land in `.test-workspace/`,
  which stays ignored.
- **FR-3** — `.gitignore` distinguishes code from output, so a future script cannot be hidden by
  living in the wrong folder.
- **FR-4** — A document lists every dependency: what it is for, how to install it, and **what breaks
  without it**, split into required and optional.
- **FR-5** — It states which parts are gated or blocked and therefore cannot be reproduced at all:
  `claude plugin eval` (early access) and SAP SALT (not on the authorized list).
- **FR-6** — It records the DuckDB extensions fetched at runtime, because they make a first run need
  network and that is invisible until it fails offline.
- **FR-7** — `CONTRIBUTING.md` points at it from its Setup section.
- **FR-8** — A test asserts the fixture scripts are tracked by git, so the flaw cannot return.

# Non-functional requirements

- **No data is committed** — the licensed workbook, the taxi parquet, the answer keys and the run logs
  stay ignored. This change moves code only.[^constitution]
- **No new project dependency.** Everything named is an external tool or an already-used DuckDB
  extension; `pyproject.toml` does not change.[^constitution]
- **The gate stays green offline.** Nothing in `scripts/verify.sh` may start needing `psql`, `tmux`,
  Docker or a network fetch.[^constitution]
- **Trust boundary** — a new `docs/NN-*.md`, called out as such.[^constitution]

# Out of scope

- **Making the fixtures part of the test suite.** They download hundreds of megabytes and need a
  database; the gate must not.
- **Vendoring any dataset.** Licences and size both forbid it, and fetch-on-demand is the design being
  repaired rather than replaced.
- **Automating the tool installation.** A script that installs Homebrew packages on someone's machine
  is a bigger claim than a document that tells them what to install.

[^constitution]: `.specify/memory/constitution.md` — never commit data or secrets, dependency discipline, CI staying offline and secret-free, and the trust-boundary artifact list.
[^gitignore]: `.gitignore` — the `.test-workspace/` rule, and `git ls-files` returning none of the seven scripts.
[^contributing]: `CONTRIBUTING.md` — the Setup section, which covers `uv sync` and `docker compose` and nothing else.
