"""The commit-message linter is real logic, so it gets real tests.

It lives in `scripts/` rather than `src/` because it is development tooling and has no
business shipping in the wheel — so it is loaded by path here.
"""

from __future__ import annotations

import importlib.util
from types import ModuleType

import pytest

from tests._support import REPO_ROOT  # noqa: E402


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "lint_commit_msg", REPO_ROOT / "scripts" / "lint_commit_msg.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lint_commit_msg = _load()


@pytest.mark.parametrize(
    "message",
    [
        "feat: add the postgres adapter",
        "fix(engine): refuse WHERE instead of dropping it",
        "docs: correct the read-only claim",
        "chore(ci)!: drop python 3.11",
        "refactor(knowledge/loader): reject duplicate keys",
        "init: semantiql, a semantic layer for AI over SQL",
        "feat: add a thing\n\nWith a body explaining why.\n",
    ],
)
def test_accepts_conventional_subjects(message: str) -> None:
    assert lint_commit_msg.lint(message) == []


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("updated some stuff", "subject must be"),
        ("Feat: capitalised type", "subject must be"),
        ("feat: ends with a period.", "full stop"),
        ("feat: ab", "too short"),
        ("nope(scope): unknown type", "not a known type"),
        ("feat: subject\nbody with no blank line", "blank line"),
        ("", "empty"),
        ("   \n\n", "empty"),
    ],
)
def test_rejects_with_a_useful_reason(message: str, expected: str) -> None:
    problems = lint_commit_msg.lint(message)
    assert problems, f"should have been rejected: {message!r}"
    assert any(expected in p for p in problems), problems


def test_rejects_an_overlong_subject() -> None:
    message = "feat: " + "x" * lint_commit_msg.MAX_SUBJECT
    problems = lint_commit_msg.lint(message)
    assert any("characters" in p for p in problems), problems


@pytest.mark.parametrize(
    "message",
    [
        "Merge branch 'main' into feature",
        'Revert "feat: add the thing"',
        "fixup! feat: add the thing",
        "Initial commit",
    ],
)
def test_exempts_messages_git_or_tooling_generates(message: str) -> None:
    """Rejecting a merge commit would block the merge, which helps nobody."""
    assert lint_commit_msg.lint(message) == []


def test_ignores_git_commentary_and_the_scissors_line() -> None:
    """The message file carries `#` commentary and a verbose-diff section; neither is content."""
    message = (
        "feat: add a thing\n"
        "# Please enter the commit message for your changes.\n"
        "# On branch main\n"
        "# ------------------------ >8 ------------------------\n"
        "diff --git a/x b/x\n"
        "+this is not the commit message\n"
    )
    assert lint_commit_msg.lint(message) == []


def test_the_repos_own_recent_history_would_pass() -> None:
    """A linter that rejects the project's existing style is the wrong linter."""
    for subject in (
        "chore: add SDD + OKF skills, constitution, and artifact templates",
        "docs: add design docs (product, architecture, setup, self-improvement)",
    ):
        assert lint_commit_msg.lint(subject) == [], subject
