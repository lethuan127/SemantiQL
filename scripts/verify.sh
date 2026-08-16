#!/usr/bin/env bash
# The verify gate. One command, so a contributor and CI cannot disagree about what
# "healthy" means (FR-2, FR-6). Nothing here needs a secret or the network, which is what
# lets it run to completion on a pull request from a fork.
#
# Exits non-zero on the first failure, naming the step that failed.

set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  cat >&2 <<'EOF'
error: uv is not installed, and this project uses it for dependencies and the venv.

  install: curl -LsSf https://astral.sh/uv/install.sh | sh
           (or: brew install uv)
EOF
  exit 127
fi

step() { printf '\n\033[1m▸ %s\033[0m\n' "$1"; }
fail() { printf '\n\033[31m✗ verify failed at: %s\033[0m\n' "$1" >&2; exit 1; }

step "sync dependencies"
uv sync --quiet || fail "uv sync"

step "format check (ruff)"
uv run ruff format --check . || fail "ruff format --check  — run 'uv run ruff format .' to fix"

step "lint (ruff)"
uv run ruff check . || fail "ruff check  — run 'uv run ruff check --fix .' to fix what is safe"

step "types (mypy)"
uv run mypy || fail "mypy"

step "tests (pytest)"
uv run pytest -m "not e2e" || fail "pytest"

# The end-to-end suite builds a TPC-H corpus and checks the engine against hand-written SQL.
# It is a separate step so its cost, and any skip reason, are visible rather than buried in
# the unit run. Building the corpus needs DuckDB's tpch extension, fetched once from DuckDB's
# repository — with no network on a first run the suite skips and this step still passes,
# because the README promises a clone that runs without one.
step "end-to-end (pytest -m e2e)"
uv run pytest -m e2e || fail "end-to-end tests"

# The change records under specs/ are an OKF bundle; conformance errors are failures.
# Absent Python yaml this validator degrades rather than lying, so it runs under uv too.
if [ -f .claude/skills/okf/scripts/validate_bundle.py ] && [ -d specs ]; then
  step "change records (OKF conformance)"
  uv run python .claude/skills/okf/scripts/validate_bundle.py specs/ || fail "OKF bundle validation"
fi

printf '\n\033[32m✓ verify passed\033[0m\n'
