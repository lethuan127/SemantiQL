---
type: Spec
title: The skill must teach commands that actually run
description: The discovery loop taught bare `semantiql inspect`, which is not on PATH from a checkout; two independent Claude runs hit it and had to recover.
resource: specs/018-skill-runnable-commands/spec.md
tags: [sdd, spec]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T12:01:42+00:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-17
  - id: skill
    resource: ../plugin/skills/semantiql/SKILL.md
    title: The discovery loop; three fenced command lines, all bare
    last_modified: 2026-08-18
  - id: observed
    resource: ../specs/016-schema-discovery/validation.md
    title: Manual step 4, which this is the result of finally running
    last_modified: 2026-08-18
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T12:01:42+00:00', checkpoint: 1,
      basis: 'Not inferred from reading the skill — observed twice, in two independent Claude Code processes given the same task against the same fixture. Both failed on the taught command and recovered by different routes, which is what rules out coincidence. The same runs also cleared the earlier suspicion that the skill under-asks: given a TTY it asks first and writes nothing, so this spec fixes only the command form.' }
sdd_phase: shipped
sdd_tier: T2
---

**T2.** `plugin/skills/semantiql/SKILL.md` is a trust-boundary artifact, so the T1 ladder does not
apply however small the diff is.

# What

Every command the skill tells Claude to run is a command that runs.

**Today three of them are not.** The discovery loop teaches:

```bash
semantiql inspect --datasource postgres --json
semantiql inspect --table orders --json
semantiql doctor -m model/
```

`semantiql` is on `PATH` only if it was installed as a tool. The documented setup is a **git
checkout plus `uv sync`**, which puts the executable in the project's own virtualenv, so the taught
command fails — inside the checkout as well as outside it:

```
semantiql not found
(eval):1: command not found: semantiql
```

Every command in `docs/` uses `uv run semantiql …`. The skill is the one place that does not, and the
skill is the only one of the two that Claude reads.[^skill]

# Why

Observed, twice, rather than reasoned about.[^observed] Spec 016 recorded its manual step 4 as **not
run**: whether a real Claude, handed a real database, asks the judgement questions instead of
inventing an aggregation. Running it needed a separate Claude process, which is what finally happened.

Two independent runs against the same deliberately ambiguous fixture — eleven columns, five of them
money, one row per order *line*, a `timestamptz` — both hit the same wall and recovered differently:

- **Run 1 (headless)** ran `which semantiql; semantiql --help`, got nothing, then spent **five more
  tool calls** listing the repository, the plugin directory and finally `.venv/bin` before finding
  the executable.
- **Run 2 (interactive)** went straight from the failure to grepping `pyproject.toml` for the
  console-script name and trying `uv run semantiql --help`.

Both recovered, because a capable model works around a broken instruction. That is precisely why it
survived: the symptom is wasted turns and a plausible-looking transcript, not an error anyone sees.
On a weaker model, or with tool permissions scoped tightly enough that hunting through the repository
is not allowed, the loop stops instead — and it stops at step 1 of the flow the setup workflow now
sends every new builder into.

The general failure is the one spec 017 fixed a fortnight of specs late: **a documented command that
nobody executed**. There it was `marketplace add`; here it is the skill's own examples. The lesson
this spec draws is that a command in a shipped instruction is executable content and needs a check,
not a review.

# User stories

- **As Claude following the discovery loop**, the first command I run works — so I spend the
  conversation on the model instead of on locating a binary.
- **As an analyst watching**, I see `inspect` run, not six exploratory commands — so the tool looks
  like it was tested.
- **As a maintainer**, the gate fails if the skill ever teaches a command the CLI does not provide.

# Functional requirements

- **FR-1** — Every command in the skill's fenced blocks is invocable given only the documented setup:
  a checkout, `uv sync`, and `SEMANTIQL_HOME` exported as `plugin/README.md` already requires.
- **FR-2** — The skill states how to resolve the invocation, and that the bare form is correct when
  SemantiQL was installed as a tool rather than cloned.
- **FR-3** — The skill says what to do when `SEMANTIQL_HOME` is unset: ask, rather than guess at a
  path.
- **FR-4** — A test fails if any fenced command line in the skill begins with bare `semantiql`.
- **FR-5** — A test asserts every `semantiql <verb>` the skill names is a verb the CLI dispatches, so
  the skill cannot teach a subcommand that does not exist.
- **FR-6** — The skill notes that a shell variable does not survive between tool calls, so the
  invocation is written out in full each time rather than assigned once.

# Non-functional requirements

- **N6** — the skill is under human review, and this change touches only *how to invoke*, never what
  a number means. The two non-negotiable limits are untouched.[^constitution]
- **Trust boundary** — `plugin/skills/semantiql/SKILL.md` is named in the constitution's
  trust-boundary list; editing it is called out, not routine.[^constitution]
- **No new dependency.** `uv` is already required by every documented command.
- **N1–N5, N7** — untouched. No engine, adapter, model or query path is involved.

# Out of scope

- **Putting `semantiql` on `PATH`** — packaging a released tool so `uvx semantiql` works is a
  release decision, and the README already records that the published package predates `serve`.
- **Spec 016's manual step 4 verdict.** Now run, and it passed: given a TTY the skill asks both
  judgement questions *before* writing any YAML, each with the numeric consequence attached. Recording
  that belongs in 016's validation file, not here.
- **The headless behaviour difference.** Under `claude -p` there is nothing to ask, so the same skill
  chooses and discloses instead. Worth its own note; not this change.
- **Row-level profiling.** Both runs read rows to work out the grain, which 016 put out of scope. It
  is how they caught the order-line trap, so it is a spec question, not a bug to patch here.

[^constitution]: `.specify/memory/constitution.md` — the trust-boundary artifact list and N6.
[^skill]: `plugin/skills/semantiql/SKILL.md` — the three fenced command lines, extracted programmatically.
[^observed]: Two `claude` processes run against a purpose-built ambiguous DuckDB fixture; transcripts captured as stream-json and as tmux pane output.
