#!/usr/bin/env bash
# Point git at the versioned hooks in .githooks/.
#
# Git does not run hooks from a tracked directory by default — .git/hooks/ is local and
# never cloned — so this one command is what makes the repo's hooks apply to you.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true
echo "✓ hooks enabled (core.hooksPath = .githooks)"
echo "    pre-commit  → ./scripts/verify.sh"
echo "    commit-msg  → Conventional Commits lint"
echo "  disable with: git config --unset core.hooksPath"
