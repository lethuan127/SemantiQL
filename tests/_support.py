"""Shared helpers for locating things in the repository.

Every test that needs a repository path takes it from here rather than counting `..` from its own
location. Counting is what made a test break the moment its file moved one directory deeper — and
the failure looked like a missing fixture rather than a moved file.
"""

from __future__ import annotations

from pathlib import Path


def _find_repo_root() -> Path:
    """Walk up until the project manifest appears.

    Move-proof by construction: the answer depends on the repository's shape rather than on how
    deep this file happens to sit.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("could not find pyproject.toml above tests/_support.py")


REPO_ROOT = _find_repo_root()
EXAMPLES = REPO_ROOT / "examples"
RETAIL = EXAMPLES / "retail"
WAREHOUSE = EXAMPLES / "warehouse"
PLUGIN = REPO_ROOT / "plugin"
SCRIPTS = REPO_ROOT / "scripts"
