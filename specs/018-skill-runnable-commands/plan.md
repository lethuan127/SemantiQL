---
type: Plan
title: The skill must teach commands that actually run — plan
description: Write the working invocation into the skill's examples, and make the gate parse them.
resource: specs/018-skill-runnable-commands/plan.md
tags: [sdd, plan]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T12:02:24+00:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-17
  - id: skill-blocks
    resource: ../plugin/skills/semantiql/SKILL.md
    title: Nine fenced blocks; exactly three lines mention semantiql, all bare
    last_modified: 2026-08-18
  - id: cli-dispatch
    resource: ../src/semantiql/cli.py
    title: Verb dispatch — doctor, inspect, serve; anything else is parsed as a query
    last_modified: 2026-08-18
  - id: mcp-json
    resource: ../plugin/.mcp.json
    title: Launches via \$SEMANTIQL_HOME, which is why that variable is the one to lean on
    last_modified: 2026-08-17
  - id: plugin-readme
    resource: ../plugin/README.md
    title: Requires SEMANTIQL_HOME to be exported before Claude starts
    last_modified: 2026-08-18
  - id: plugin-tests
    resource: ../tests/interfaces/test_plugin.py
    title: The existing drift tests, including the grain parser these new tests mirror
    last_modified: 2026-08-18
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T12:02:24+00:00', checkpoint: 2,
      basis: 'Five rows, every one footnoted to a file read. The command lines were extracted with a script rather than eyeballed, which is the same extraction the new test performs — so the test and the map cannot disagree about what the skill currently says. \$SEMANTIQL_HOME was chosen because .mcp.json and plugin/README.md already require it; inventing a second discovery mechanism was rejected.' }
---

# Constitution check

**Trust boundary.** `plugin/skills/semantiql/SKILL.md` is on the constitution's list. This edit is
therefore called out explicitly rather than treated as a docs tidy — even though it changes only how
a command is spelled.[^constitution]

**N6.** The two non-negotiable limits — never invent an aggregation or a formula, never change a model
to answer a question — are not touched, and the drift tests that pin them stay as they are. Nothing
here affects what a number means.[^constitution]

**No new dependency.** `uv` is already the documented way to run everything in this repository.

# Approach

Write the working invocation into the examples themselves. The skill's three command lines become

```bash
uv run --directory "$SEMANTIQL_HOME" semantiql inspect --json
```

and a short preamble explains the two forms and when each applies.[^skill-blocks]

`$SEMANTIQL_HOME` rather than a new mechanism, because `plugin/.mcp.json` already launches the
server through it and `plugin/README.md` already requires it to be exported before Claude
starts.[^mcp-json] [^plugin-readme] Leaning on the variable the install already sets means there is one
thing to get right, not two.

The preamble has to say one non-obvious thing: **a shell variable does not survive between tool
calls.** Each Bash call is its own shell, so "assign `SQ=…` once and reuse it" silently degrades to an
empty command on the second call. Writing the invocation out each time is verbose and correct.

Testing mirrors the grain parser already in this file: extract the skill's fenced blocks and assert
things about them, so prose and behaviour cannot drift.[^plugin-tests] Two assertions, and the second
is the one with teeth — every `semantiql <verb>` the skill names must be a verb `cli.py`
dispatches.[^cli-dispatch] That catches a class the first does not: a correctly-invoked command for a
subcommand that does not exist.

**Amendment, recorded after T3 ran the commands.** The approach above was written with
`uv run --directory "$SEMANTIQL_HOME"`, and running it broke two ways that reading it did not reveal:

- **`--directory` changes the working directory**, so every relative path in the skill's own examples
  — `-m model/`, `--database ./shop.duckdb` — resolved against the *checkout* instead of the user's
  project. `uv run --project "$SEMANTIQL_HOME"` discovers the project without moving, which is what
  the examples need. Measured both ways against the fixture.
- **`semantiql --version` does not exist.** The probe I wrote to fix broken commands was itself a
  broken command; `--help` exits 0 and is the working equivalent.

Two more of the same defect, found the same way. Which is the argument for the ordering in
`tasks.md`: T3's verification says the commands were *run*, and had it said "reviewed" this spec would
have shipped its own bug.

# Architecture decisions

1. **The examples carry the long form; the bare form is a documented alternative.** Rejected: keeping
   the bare form with a note to substitute. That is what exists now, minus the note, and the note is
   exactly what a model skims. The command a reader copies has to be the command that works.

2. **The verb test reads `cli.py`'s dispatch, not a hard-coded list.** A list in the test is a third
   place for the verb set to drift. Rejected as adding the problem it means to solve.

3. **`inspect`'s example drops `--datasource postgres`.** The current example hard-codes Postgres in
   a loop that runs against either engine, which quietly teaches that the flag is mandatory. It is
   not, and the DuckDB default is what a first-time user has.

# Repository Impact Map

## Files to modify

- `plugin/skills/semantiql/SKILL.md` — the discovery loop: a new preamble before step 1 on resolving
  the invocation, and the three fenced command lines rewritten. **Trust-boundary artifact.**[^skill-blocks]
- `tests/interfaces/test_plugin.py` — FR-4 and FR-5, extracting fenced blocks the same way the grain
  test does.[^plugin-tests]
- `specs/016-schema-discovery/validation.md` — manual step 4 is recorded there as **not run**, and it
  has now been run and passed. Correcting that is part of this change, because leaving it stale would
  understate what is verified about the very loop this spec repairs.[^observed]

## Files not touched, but adjacent

- `docs/03-setup-workflow.md` and `docs/10-adopting-semantiql.md` — already use `uv run semantiql`
  throughout. The skill was the outlier, so the documents need no change.
- `plugin/.mcp.json`, `plugin/README.md` — read, unchanged. They already establish
  `$SEMANTIQL_HOME`.[^mcp-json] [^plugin-readme]
- `src/semantiql/cli.py` — read for its verb set, unchanged.[^cli-dispatch]

[^constitution]: `.specify/memory/constitution.md` — trust-boundary artifact list, N6.
[^skill-blocks]: `plugin/skills/semantiql/SKILL.md` — nine fenced blocks; exactly three lines mention `semantiql`, extracted with a script.
[^cli-dispatch]: `src/semantiql/cli.py` — `verb == "doctor" | "inspect" | "serve"`, everything else treated as a query.
[^mcp-json]: `plugin/.mcp.json` — `uv run --directory \${SEMANTIQL_HOME} semantiql serve`.
[^plugin-readme]: `plugin/README.md` — the Install section's `export SEMANTIQL_HOME=$PWD`.
[^plugin-tests]: `tests/interfaces/test_plugin.py` — the grain parser, and the marketplace tests added by spec 017.
[^observed]: `specs/016-schema-discovery/validation.md` — manual step 4, recorded as not run.
