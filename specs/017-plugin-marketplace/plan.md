---
type: Plan
title: Make the shipped plugin installable, and check that it is — plan
description: One root marketplace manifest, two documented commands, and a gate step that skips when Claude Code is absent.
resource: specs/017-plugin-marketplace/plan.md
tags: [sdd, plan]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T10:10:33+00:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at plan time
    last_modified: 2026-08-17
  - id: plugin-manifest
    resource: ../plugin/.claude-plugin/plugin.json
    title: The plugin's name, version, description and keywords — read to build the marketplace entry
    last_modified: 2026-08-17
  - id: mcp-json
    resource: ../plugin/.mcp.json
    title: Read to confirm what the plugin launches; it uses \$SEMANTIQL_HOME, not \$CLAUDE_PLUGIN_ROOT
    last_modified: 2026-08-17
  - id: setup-a1
    resource: ../docs/03-setup-workflow.md
    title: Step A1, which carries the unfollowable sentence
    last_modified: 2026-08-18
  - id: plugin-readme
    resource: ../plugin/README.md
    title: The Install section, line 25
    last_modified: 2026-08-17
  - id: verify
    resource: ../scripts/verify.sh
    title: The gate — read for its step/fail helpers and the two existing conditional-step patterns
    last_modified: 2026-08-17
  - id: plugin-tests
    resource: ../tests/interfaces/test_plugin.py
    title: The existing drift tests, and the SKILL/manifest paths they resolve
    last_modified: 2026-08-18
  - id: code-map
    resource: ../docs/07-code-map.md
    title: The outside-src listing; its plugin/ entry is stale about \$CLAUDE_PLUGIN_ROOT
    last_modified: 2026-08-18
  - id: agents-brief
    resource: ../AGENTS.md
    title: Line 245, the shipped-product versus own-tooling separation
    last_modified: 2026-08-18
  - id: cli-surface
    resource: ../specs/017-plugin-marketplace/spec.md
    title: The measured Claude Code CLI surface, recorded in the spec's footnote
    last_modified: 2026-08-18
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T10:10:33+00:00', checkpoint: 2,
      basis: 'Every row derived from a file read or a command run; all eleven rows footnoted. The manifest shape was taken from two independent working marketplaces on this machine, not from memory. Mapping turned up a defect the spec had not named — the code map describes .mcp.json as using \$CLAUDE_PLUGIN_ROOT when it uses \$SEMANTIQL_HOME — so it is in the map as a recorded addition rather than a silent extra edit.' }
---

# Constitution check

**Setup in ≤ 15 minutes, every step automatically checked, every error carrying a fix.** This change
exists because A1 met none of the three: not performable, not checked, and producing no error at all
because the reader never reached a command. FR-2/FR-3 make it performable, FR-7 makes it checked, and
the rewritten prose names the marketplace concept so a failure is interpretable.[^constitution]

**CI stays secret-free and runs on fork PRs.** FR-7 introduces the gate's first dependency on a tool
outside `uv`. FR-8 contains it: the step is guarded on `command -v claude` and prints why it skipped.
The `pg` step is the precedent the constitution already blesses — it skips with a stated reason and
the gate still passes, deliberately and load-bearingly.[^verify]

**Shipped product versus this repo's own tooling.** `.claude-plugin/` at the root is shipped product
and sits beside `plugin/` and `bundle/`; `.claude/` remains this repository's tooling. The two
directory names differ by a hyphen and a word, which is a genuine trap, so the brief and the code map
both get the distinction in writing.[^agents-brief][^code-map]

**N1–N7 untouched.** No query path, no adapter, no engine, no model. Nothing here can produce a
number, so nothing here can produce a wrong one.

**No new external dependency.** The Claude Code CLI is not added to the dependency set; it is
detected and used when present. The constitution requires an issue before a new dependency, and this
deliberately is not one.

# Approach

One file does the work. `.claude-plugin/marketplace.json` at the repository root turns the checkout
into a marketplace containing one plugin whose `source` is `./plugin`. Nothing inside `plugin/`
changes — it already validates `--strict` — so this is purely the missing outer wrapper.

Root, not somewhere tidier, because `claude plugin marketplace add` resolves
`<source>/.claude-plugin/marketplace.json` and the source a reader has is the checkout they just
cloned.[^cli-surface] Putting the marketplace inside `plugin/` would mean the marketplace and the
plugin claim the same directory, and the reader would type a path one level deeper than the thing they
cloned for no reason they could infer.

The gate gains a step that runs `claude plugin validate --strict` over both manifests. Strict is the
right setting for a gate — it fails on unrecognised fields and missing metadata that the runtime
tolerates — and the plugin already passes it, so the step starts green and stays honest rather than
starting with an exemption.[^cli-surface]

Testing splits along what each mechanism can actually see. `claude plugin validate` checks manifest
*shape*. It cannot check that `source: ./plugin` points at anything, so the pytest side checks the
*pointer*: the path resolves, the directory exists, and it contains a `plugin.json` whose `name`
matches the entry. That is the failure a rename or a directory move would cause, and the one a schema
validator passes cheerfully.

# Architecture decisions

1. **The marketplace lives at the repository root, not inside `plugin/`.** Chosen so the path a
   reader types is the checkout they cloned. Rejected: a nested marketplace, which reads as though
   the plugin contains itself, and a separate `marketplace/` directory, which adds a top-level
   directory that holds one file and explains nothing.

2. **The marketplace entry carries no `version`.** `plugin.json` already has one, and
   `claude plugin tag` exists precisely because a version in both places can disagree.[^cli-surface]
   One version, one file. Rejected: mirroring the version for readability, which buys a nicer listing
   and a drift test to maintain forever.

3. **The description is duplicated, and a test pins it.** Unlike the version, the description *must*
   appear in the marketplace entry — it is what a browsing user reads before installing, and an entry
   without one is what `--strict` complains about. So the duplication is forced, and the response is
   to make drift fail loudly (FR-10) rather than to pretend the second copy is independent.[^plugin-manifest]

4. **The gate step is guarded on `command -v claude`, and prints its skip reason.** Rejected: making
   it unconditional, which breaks every CI job and every contributor without Claude Code, for a check
   on two static JSON files. Also rejected: the silent `if [ -f ... ]` shape the OKF step uses — a
   check that vanishes without saying so is indistinguishable from a check that passed, which is the
   same class of invisible failure this project refuses elsewhere.[^verify]

5. **The documented commands use the default scope, not `--scope local`.** Found by running T2
   rather than by reasoning: `--scope local` writes
   `{"extraKnownMarketplaces": {"semantiql": {"source": {"path": "/Users/…/semantiql"}}}}` into
   `.claude/settings.local.json` — a file **inside the repository**, carrying an **absolute path to
   the installer's own machine**. It is git-ignored here only by this developer's *global*
   gitignore, so a contributor without that rule would follow A1 and commit their home directory.
   The default (`user`) scope writes to `~/.claude/settings.json` and leaves the checkout byte-for-byte
   clean, which was confirmed with `git status` after installing. **Amendment, recorded:** the spec
   said "the two commands" without settling scope, and the wrong choice would have shipped a
   documented step that dirties the reader's working tree.

6. **`.claude/settings.local.json` is added to the repo's `.gitignore` anyway.** Defence in depth for
   decision 5: a reader who reaches for `--scope local` or `--scope project` should not be able to
   leak an absolute path through a step this repository told them to take. **Amendment, recorded:**
   one file beyond the spec's impact map, caused by what T2 measured.

7. **The gate does not install the plugin.** Installing mutates the developer's own Claude Code
   configuration. A gate that reaches outside the repository to prove something about the repository
   has bought its confidence with someone else's state.

# Repository Impact Map

## Files to add

- `.claude-plugin/marketplace.json` — new, and a new **top-level directory**. Keys: `name`,
  `owner`, `description`, and `plugins[]` with one entry carrying `name: semantiql`,
  `source: ./plugin`, `description`, `category`, `keywords`. Shape taken from two working
  marketplaces on this machine; `owner` appears in both, so it is not optional in practice.[^plugin-manifest]

## Files to modify

- `docs/03-setup-workflow.md` — step A1. Replace *"add this checkout's `plugin/` directory"* with
  the two commands and their real output. **Trust-boundary artifact**, called out as required.[^setup-a1]
- `plugin/README.md` — the Install section's line 25, same sentence, plus a short paragraph on what
  a marketplace is, since a reader here is being asked to add a concept they have not met.[^plugin-readme]
- `scripts/verify.sh` — one new step after the desktop bundle, guarded and printing its skip
  reason, using the file's existing `step`/`fail` helpers.[^verify]
- `tests/interfaces/test_plugin.py` — FR-9 and FR-10: the manifest parses, names the plugin, its
  source resolves to a directory holding a matching `plugin.json`, and the two descriptions agree.
  This file already resolves plugin paths via a module-level constant, so the new tests reuse it
  rather than introducing a second way to find the same directory.[^plugin-tests]
- `.gitignore` — add `.claude/settings.local.json`. **Recorded amendment**, see decision 6: the
  install writes an absolute machine path there, and the repo's own ignore file did not cover it
  (only this developer's global one did).
- `AGENTS.md` — line 245's shipped-product sentence gains `.claude-plugin/`, and the working rules
  gain the install commands so an agent does not reinvent the vague instruction.[^agents-brief]
- `docs/07-code-map.md` — the outside-`src/` listing gains the new directory. **Recorded addition
  beyond the spec:** the same listing's `plugin/` entry says `.mcp.json` launches the server "via
  \${CLAUDE_PLUGIN_ROOT} so it is portable", which is false — the file uses \${SEMANTIQL_HOME}, and the
  switch away from \${CLAUDE_PLUGIN_ROOT} was the correction that produced spec 014. Left alone, the
  code map would keep teaching the exact mistake two specs were spent fixing.[^code-map][^mcp-json]

## Files not touched, but adjacent

- `plugin/.claude-plugin/plugin.json` — read, unchanged. It already passes `--strict`; the gap was
  never inside it.[^plugin-manifest]
- `plugin/.mcp.json` — read only to confirm what the code map claims about it.[^mcp-json]
- `.github/workflows/ci.yml` — deliberately unchanged. FR-8 means CI needs no Claude Code, so the
  workflow needs no new step and no new tool.
- `scripts/build_bundle.py` and `bundle/` — the other distribution channel, unaffected.

# Open research questions

- **Should the marketplace be published so `claude plugin marketplace add lethuan127/semantiql`
  works from a GitHub source?** It would drop the clone from the install path for anyone who only
  wants to ask questions. Out of scope here and cheap later: `add` already accepts a GitHub repo, so
  publishing needs no manifest change.[^cli-surface] Flagged rather than resolved, since it is a
  release decision.

[^constitution]: `.specify/memory/constitution.md` — the ≤15-minute checked-setup rule, the trust-boundary list, secret-free CI, and the dependency-addition rule.
[^plugin-manifest]: `plugin/.claude-plugin/plugin.json` — name `semantiql`, version 0.0.2, description, keywords; and `claude plugin validate ./plugin --strict` passing.
[^mcp-json]: `plugin/.mcp.json` — launches `uv run --directory \${SEMANTIQL_HOME} semantiql serve`.
[^setup-a1]: `docs/03-setup-workflow.md` — step A1 as rewritten by spec 016.
[^plugin-readme]: `plugin/README.md` — the Install section, line 25.
[^verify]: `scripts/verify.sh` — the `step`/`fail` helpers, the `pg` step's stated-reason skip, and the OKF step's silent `if [ -f ... ]` guard.
[^plugin-tests]: `tests/interfaces/test_plugin.py` — the existing drift tests and the constant they resolve paths through.
[^code-map]: `docs/07-code-map.md` — the "Everything outside `src/`" listing and its `plugin/` entry.
[^agents-brief]: `AGENTS.md` — line 245.
[^cli-surface]: Measured on this machine: `claude plugin --help`, `claude plugin marketplace add --help` (accepts "a URL, path, or GitHub repo"), `claude plugin validate --help` (`--strict` "treat warnings as errors … use in CI"), and `claude plugin tag --help` (validates that plugin.json and any enclosing marketplace entry agree).
