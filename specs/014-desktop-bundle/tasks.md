---
type: Tasks
title: Desktop bundle — tasks
description: 9 tasks plus two gate tasks — env fallbacks, the entry point, the build script, the tests including a regression for the version bug, then the docs and the gate.
resource: specs/014-desktop-bundle/tasks.md
tags: [sdd, tasks, mcpb]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T03:40:00+07:00' }
sources:
  - id: plan
    resource: plan.md
    title: The approved plan, AD-1..AD-5, the impact map and OQ-1..OQ-3
    last_modified: 2026-08-18
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T03:42:00+07:00', checkpoint: 3,
      basis: '11 tasks in dependency order; one [P] group checked disjoint. T1 precedes the entry point so the entry point can stay three lines. T5 is where a shipping bug was found rather than assumed — the bundle crashed on import on any machine without the distribution installed — and it carries the regression test' }
status: stable
---

11 tasks. T5 is the one that mattered: it found a bug that would have shipped.

## ✅ T1. Environment fallbacks for the rest of the connection

- **Files:** `src/semantiql/cli.py`
- **Do:** `SEMANTIQL_DATASOURCE`, `SEMANTIQL_DSN`, `SEMANTIQL_DATABASE` beside `MODEL_ENV` (AD-2).
  An explicit flag always wins; an empty string counts as unset, because a host substituting a
  blank optional field yields `""` rather than absence.
- **Verification:** mypy clean; covered by T6.

## ✅ T2. The entry point

- **Files:** `bundle/server.py` (new)
- **Depends on:** T1
- **Do:** `sys.path`, import, `main(["serve"])`. Three lines, because this is the one file no
  ordinary test exercises — every decision belongs in `cli.py` (AD-2).
- **Verification:** lints; exercised by T5.

## ✅ T3. The build script

- **Files:** `scripts/build_bundle.py` (new)
- **Depends on:** T2
- **Do:** generate `manifest.json` (version substituted, `user_config` declared) and a deps-only
  `pyproject.toml` read from the real one; copy the entry point and the package; zip to
  `dist/semantiql-<version>.mcpb`. Offline. Source copied, never committed (AD-1, AD-3).
- **Verification:** it builds and the zip contains what T6 asserts.

## ✅ T4. Keep the artifact out of git

- **Files:** `.gitignore`
- **Depends on:** T3
- **Do:** ignore `dist/`. FR-10 — a committed bundle is a second copy of the code that drifts.
- **Verification:** `git status` after a build shows nothing new.

## ✅ T5. Prove it runs where it will actually run

- **Files:** none — a measurement
- **Depends on:** T3
- **Do:** extract the bundle to a directory unrelated to the checkout, into a venv with **only** the
  declared dependencies and **no `semantiql` distribution**, and drive it over stdio.
- **✅ Result: it failed, and the bug would have shipped.** `__init__.py` read the version from
  `importlib.metadata`, which raises inside a bundle because the package is on `sys.path` and never
  installed — so the import aborted on every machine that had not already installed SemantiQL,
  which is every machine a bundle is for. Invisible locally: a checkout always has the distribution.
  The first attempt at this test *passed* only because the ambient venv was contaminated.
  Fixed with a build stamp the script writes and `__init__` falls back to; re-verified working.

## ✅ T6. `[P]` The bundle tests

- **Files:** `tests/test_bundle.py` (new)
- **Depends on:** T5
- **Do:** build into a temp directory and check AD-4's list, plus a **regression test for T5's bug**
  that simulates the missing distribution rather than needing a clean machine. Also: every
  `user_config` key reaches an environment variable the CLI reads — a field that is collected and
  never consumed looks like configuration and does nothing.
- **Verification:** green, and red if the version fallback is removed.

## ✅ T7. `[P]` The bundle README

- **Files:** `bundle/README.md` (new)
- **Depends on:** T3
- **Do:** build, install, the dialog's fields, why the source is inside, and what this is *not* —
  still a local server needing database access.
- **Verification:** a reader can build and install without another file.

> **`[P]` group — T6 and T7 are disjoint:** {`tests/test_bundle.py`} · {`bundle/README.md`}.

## ✅ T8. Put the build under the gate

- **Files:** `scripts/verify.sh`
- **Depends on:** T3
- **Do:** a build step, so a broken bundle fails in CI rather than on a desktop (FR-8).
- **Verification:** the gate builds it and passes; no network needed.

## ✅ T9. The workflow docs

- **Files:** `docs/03-setup-workflow.md`, `docs/10-adopting-semantiql.md`
- **Depends on:** T7
- **Do:** Flow B leads with opening a bundle; `docs/10` Step 7's Desktop half becomes the bundle,
  keeping `--print-config` named as the fallback. **`03` is trust-boundary.**
- **Verification:** neither describes a step that no longer applies.

## ✅ T10. Code map, plugin README, README, agent brief

- **Files:** `docs/07-code-map.md`, `plugin/README.md`, `README.md`, `AGENTS.md`
- **Depends on:** T9
- **Do:** the tree gains `bundle/` and the build script; the plugin's Desktop paragraph points at a
  built thing rather than calling it unbuilt; the README shows all three routes. **Do not edit
  `CLAUDE.md`.** **`07` is trust-boundary.**
- **Verification:** `git status` shows `AGENTS.md` changed and `CLAUDE.md` not.

## ✅ TF. Final verify

- **Depends on:** T1–T10
- **Do:** `./scripts/verify.sh`, with and without a Postgres reachable.

## ✅ TV. Validation pass

- **Depends on:** TF
- **Do:** walk every AC, keeping the distinction between what the gate proved and the Desktop
  install, which needs a human once.

[^plan]: `plan.md` — the impact map, AD-1..AD-5, and OQ-1..OQ-3.
