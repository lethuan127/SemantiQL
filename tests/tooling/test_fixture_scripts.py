"""The fixture and harness scripts are in git.

This file exists because they were not, and nothing noticed. `build.py`, `fetch.py`,
`fetch_retail.py`, `fetch_salt.py`, `judge.py`, `run-debug.sh` and `seed.sql` all lived under
`.test-workspace/`, which `.gitignore` excludes entirely — so a fresh clone had none of them.

Each of those scripts says in its own docstring that *the script is the artefact and the data is
output*. That is the right design for a 46 MB licensed workbook, and it goes false the moment the
fetcher is ignored too: nothing is preserved, and the reproducibility it existed for is gone.

It was invisible locally, which is the point. Everything worked on the machine that wrote them, and
the failure was reserved for the next one: a missing file with no history, and no way to know it had
ever existed. That is the shape of failure this project spends its effort refusing elsewhere.

`git ls-files` is the only check that would have caught it, so that is what these tests run.
"""

from __future__ import annotations

import ast
import subprocess

import pytest

from tests._support import REPO_ROOT

FIXTURES = REPO_ROOT / "scripts" / "fixtures"

#: Named individually rather than globbed. A glob over a directory that had been silently emptied
#: would pass with zero files, which is exactly the failure being guarded against.
EXPECTED = (
    "build.py",
    "fetch.py",
    "fetch_retail.py",
    "fetch_salt.py",
    "judge.py",
    "run-debug.sh",
    "seed.sql",
)


def _tracked() -> set[str]:
    """What git actually has, which is the only authority on what a clone would carry."""
    done = subprocess.run(
        ["git", "ls-files", "scripts/fixtures"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {line.rsplit("/", 1)[-1] for line in done.stdout.split() if line}


@pytest.mark.parametrize("name", EXPECTED)
def test_each_fixture_script_is_tracked_by_git(name: str) -> None:
    """On disk is not enough: the previous version of these files was on disk and ignored."""
    assert (FIXTURES / name).is_file(), f"{name} is missing from {FIXTURES}"
    assert name in _tracked(), (
        f"{name} exists but git does not track it — a fresh clone would not have it. "
        "under an ignored path, move it; if it is genuinely output, it does not belong here."
    )


def test_no_fixture_output_is_tracked() -> None:
    """The other half of the rule: code in, data out.

    A loader that started writing its download beside itself would put a 46 MB workbook under a
    tracked path, which is the mirror image of the original flaw.
    """
    heavy = {name for name in _tracked() if name.endswith((".parquet", ".xlsx", ".zip", ".duckdb"))}
    assert not heavy, f"fixture *data* is tracked: {sorted(heavy)}"


@pytest.mark.parametrize("name", [n for n in EXPECTED if n.endswith(".py")])
def test_each_python_fixture_script_parses(name: str) -> None:
    """Cheap, and it earns its place: these are edited by hand and run rarely.

    A syntax error in a loader nobody has run this month is otherwise found by the person who needed
    the fixture, at the moment they needed it.
    """
    ast.parse((FIXTURES / name).read_text())


def test_each_python_fixture_script_writes_only_into_the_ignored_workspace() -> None:
    """They must resolve their own output location, not assume where they live.

    They were moved out of `.test-workspace/`; had the output paths stayed relative to the
    script, the downloads would now land in tracked `scripts/fixtures/data/`. The root walk is
    what makes the move safe, so it is asserted rather than trusted.
    """
    for name in (n for n in EXPECTED if n.endswith(".py")):
        source = (FIXTURES / name).read_text()
        if "_workspace()" not in source:
            continue
        assert "pyproject.toml" in source, (
            f"{name} builds its output path without walking to the repository root, so where it "
            "writes depends on where the file sits"
        )
        assert '".test-workspace"' in source, f"{name} does not name the ignored workspace"
