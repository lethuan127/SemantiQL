#!/usr/bin/env python3
"""Lint a commit message against Conventional Commits.

Dependency-free on purpose. The obvious tool here is `commitlint`, but it is a Node
package, and this repo committed to a single Python runtime — adding Node so contributors
can write commit messages would be a poor trade. Standard library only.

Usage:
    python3 scripts/lint_commit_msg.py <path-to-commit-message-file>

Exit codes: 0 clean, 1 rejected, 2 bad usage.

The rules are deliberately few. A linter that rejects half of a maintainer's commits gets
disabled within a week, so this checks the things that make history *readable* — a type, a
scope of change, a subject you can scan in a log — and nothing about taste.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: Conventional Commits types. `chore` is the catch-all; prefer a specific one.
TYPES = (
    "feat",  # a user-visible capability
    "fix",  # a user-visible defect repaired
    "docs",  # documentation only
    "refactor",  # neither fixes a bug nor adds a feature
    "perf",  # a performance change
    "test",  # tests only
    "build",  # build system, dependencies, packaging
    "ci",  # CI configuration
    "chore",  # anything else — tooling, housekeeping
    "revert",  # reverts a previous commit
    "init",  # the root commit of a repository or a squashed history
)

MAX_SUBJECT = 72

#: type(optional-scope)optional-!: description
_SUBJECT = re.compile(
    r"^(?P<type>[a-z]+)"
    r"(?:\((?P<scope>[a-z0-9][a-z0-9._/-]*)\))?"
    r"(?P<breaking>!)?"
    r": (?P<description>.+)$"
)

#: Messages git generates or that tooling rewrites later — never rejected.
_EXEMPT = (
    "merge ",
    "revert ",
    "fixup!",
    "squash!",
    "amend!",
    "initial commit",
)


def _strip_comments(raw: str) -> str:
    """Drop the commentary git appends to the message file.

    Order matters: the scissors line is itself a `#` comment, so it must be found *before*
    comments are removed. Doing it the other way round deletes the marker and lets the
    verbose diff below it be read as the commit body.
    """
    lines = raw.splitlines()

    # Everything after a `# ----- >8 -----` scissors line is a diff, not the message.
    for i, line in enumerate(lines):
        if line.startswith("#") and ">8" in line:
            lines = lines[:i]
            break

    return "\n".join(ln for ln in lines if not ln.startswith("#")).strip("\n")


def lint(message: str) -> list[str]:
    """Return a list of problems. Empty means the message is fine."""
    text = _strip_comments(message)
    if not text.strip():
        return ["the commit message is empty"]

    lines = text.splitlines()
    subject = lines[0].rstrip()

    if subject.lower().startswith(_EXEMPT):
        return []

    problems: list[str] = []
    match = _SUBJECT.match(subject)

    if match is None:
        problems.append(
            f"subject must be '<type>(<scope>): <description>', got {subject!r}\n"
            f"    valid types: {', '.join(TYPES)}"
        )
        return problems  # nothing else is checkable without a parse

    if match["type"] not in TYPES:
        problems.append(f"{match['type']!r} is not a known type — use one of: {', '.join(TYPES)}")

    description = match["description"]
    if description != description.strip():
        problems.append("description has leading or trailing whitespace")
    if description.endswith("."):
        problems.append("description should not end with a full stop")
    if len(description) < 3:
        problems.append("description is too short to be useful")
    if len(subject) > MAX_SUBJECT:
        problems.append(f"subject is {len(subject)} characters; keep it to {MAX_SUBJECT}")

    if len(lines) > 1 and lines[1].strip():
        problems.append("leave a blank line between the subject and the body")

    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <commit-message-file>", file=sys.stderr)
        return 2

    path = Path(argv[1])
    try:
        message = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 2

    problems = lint(message)
    if not problems:
        return 0

    print("\ncommit message rejected:\n", file=sys.stderr)
    for problem in problems:
        print(f"  • {problem}", file=sys.stderr)
    print(
        "\n  format:  <type>(<scope>): <description>\n"
        "  example: fix(engine): refuse WHERE instead of dropping it\n"
        "\n  bypass with --no-verify if you must.\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
