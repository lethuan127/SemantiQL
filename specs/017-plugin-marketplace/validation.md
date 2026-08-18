---
type: Validation
title: Make the shipped plugin installable, and check that it is — validation
description: Acceptance criteria traced to FR-1..FR-10.
resource: specs/017-plugin-marketplace/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T10:16:38+00:00' }
status: stable
---

# Acceptance criteria

- [x] **AC-1** (FR-1): `.claude-plugin/marketplace.json` exists at the repository root and names the
      `semantiql` plugin with `source: ./plugin`.
  - **Proven by:** `test_a_marketplace_manifest_exists`, `test_the_marketplace_names_the_plugin`,
    and `claude plugin validate . --strict` in the gate.
- [x] **AC-2** (FR-2): `claude plugin marketplace add` succeeds against this checkout.
  - **Proven by:** run, output quoted in `docs/03-setup-workflow.md` A1:
    `✔ Successfully added marketplace: semantiql (declared in user settings)`. The same command
    against `./plugin` was also run and fails with `Marketplace file not found` — which is what
    establishes that the old instruction was unfollowable rather than merely unclear.
- [x] **AC-3** (FR-3): `claude plugin install semantiql@semantiql` succeeds, and both the skill and
      the MCP server are present.
  - **Proven by:** run. `claude plugin details semantiql@semantiql` reports `Skills (1) semantiql`
    and `MCP servers (1) semantiql`; `claude plugin list` shows it enabled at version 0.0.2. Both
    halves matter and for different flows — A3 needs the skill, B2 needs the server.
- [x] **AC-4** (FR-4): The marketplace entry's description and the plugin manifest's are identical.
  - **Proven by:** `test_the_two_descriptions_agree`. Forced duplication, so pinned rather than
    trusted. The **version** is deliberately not duplicated, which
    `test_the_marketplace_entry_carries_no_version` locks in.
- [x] **AC-5** (FR-5): A1 gives the two real commands with captured output.
  - **Proven by:** `docs/03-setup-workflow.md` A1, and
    `grep -rn "add this checkout" docs/ plugin/` returning nothing. Trust-boundary artifact, edited
    deliberately.
- [x] **AC-6** (FR-6): `plugin/README.md` gives the same commands and explains what a marketplace
      is, including the error a reader gets for pointing `add` at `plugin/`.
  - **Proven by:** the rewritten Install section.
- [x] **AC-7** (FR-7): The gate validates both manifests with `--strict`.
  - **Proven by:** the `plugin manifests (claude plugin validate)` step in `scripts/verify.sh`;
    observed passing on both files.
- [x] **AC-8** (FR-8): That step skips with a **printed** reason when `claude` is absent, and the
      gate still passes.
  - **Proven by:** the gate run under a `PATH` carrying `uv` but not `claude`, which printed
    `skipped: no 'claude' on PATH — Claude Code is not a dependency of this repo` and ended
    `✓ verify passed`. Constructed deliberately: the first attempt dropped `~/.local/bin`, which
    removed `uv` too and failed earlier in the gate, proving nothing about this step.
- [x] **AC-9** (FR-9): A test asserts the manifest parses, names the plugin, and that `source`
      resolves to a directory holding a matching `plugin.json`.
  - **Proven by:** `test_the_marketplace_source_resolves_to_the_plugin`. **This test caught its own
    author**: the first version resolved `source` against the manifest's parent directory rather
    than the marketplace root and failed. The install had already succeeded, so the test was wrong
    and the manifest right — the resolution base is now stated in the docstring, because it is an
    easy thing to get backwards.
- [x] **AC-10** (FR-10): The description agreement is tested.
  - **Proven by:** `test_the_two_descriptions_agree`, and
    `test_the_marketplace_holds_no_absolute_path` alongside it.

# Non-functional acceptance

- [x] The verify gate is green **three ways**: with Postgres up, with Postgres down, and with
      `claude` off `PATH`.
- [x] **CI needs no Claude Code.** `.github/workflows/ci.yml` is unchanged, and
      `grep -c "secrets\." .github/workflows/ci.yml` is still 0.
- [x] **Shipped product versus own tooling** is stated in both `AGENTS.md` and
      `docs/07-code-map.md`, naming all three shipped directories and contrasting `.claude/`.
- [x] **No new dependency.** The `claude` CLI is detected, never required; `pyproject.toml` is
      untouched.
- [x] **N1–N7 untouched.** No engine, adapter, model or query-path file was modified.
- [x] **No absolute path is committed.** `.claude/settings.local.json` is now in `.gitignore` —
      added because the installer writes this developer's home directory into it, and the repo's own
      ignore file did not cover it (only a global one did). `test_the_marketplace_holds_no_absolute_path`
      guards the manifest itself.

# Manual verification

1. From a clean checkout, run the two commands in A1. Expect both to succeed.
2. `claude plugin details semantiql@semantiql` — expect `Skills (1)` and `MCP servers (1)`.
3. `claude plugin marketplace add ./plugin` — expect `Marketplace file not found`. This is the
   error the old instruction produced, and confirming it still appears is what keeps the
   explanation in A1 and `plugin/README.md` true rather than historical.
4. `git status` after installing — expect a clean tree. If `.claude/settings.local.json` appears,
   the reader used `--scope local`; the `.gitignore` entry is what stops that becoming a commit.

**Steps 1–4 were all run on this machine and their output is quoted above or in A1.** The plugin was
left installed at user scope; nothing was written inside the repository.
