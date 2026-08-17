"""The Desktop bundle — built into a temporary directory and inspected (spec 014).

Cheap structural checks, plus one regression test that matters more than the rest.

**The bug this file exists to prevent.** The bundle carries `semantiql` as *source* and never
installs it as a distribution, so `importlib.metadata.version("semantiql")` raises inside it.
Before the fallback existed, importing SemantiQL from a bundle failed outright — and the failure
was invisible in development, because a checkout always has the distribution present. It appeared
only on a machine that had never installed SemantiQL, which is every machine a bundle is for.

`test_the_version_survives_without_an_installed_distribution` reproduces that condition without
needing a clean machine.

**What this file cannot check:** that Claude Desktop installs the bundle and shows the dialog. That
needs the application, so it is a manual step in `specs/014-desktop-bundle/validation.md` rather
than something the gate pretends to prove.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from importlib import metadata
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
BUILDER = REPO / "scripts" / "build_bundle.py"


@pytest.fixture(scope="module")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the bundle once, into a temporary directory rather than `dist/`."""
    destination = tmp_path_factory.mktemp("bundle")
    subprocess.run(
        [sys.executable, str(BUILDER), "--out", str(destination)], check=True, capture_output=True
    )
    built = list(destination.glob("*.mcpb"))
    assert len(built) == 1, f"expected one bundle, got {built}"
    return built[0]


@pytest.fixture(scope="module")
def contents(bundle: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(bundle) as zipped:
        return {name: zipped.read(name) for name in zipped.namelist()}


@pytest.fixture(scope="module")
def manifest(contents: dict[str, bytes]) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(contents["manifest.json"])
    return parsed


# --- It builds, and what it contains


def test_the_bundle_is_one_zip_named_for_its_version(bundle: Path) -> None:
    assert bundle.suffix == ".mcpb"
    assert metadata.version("semantiql") in bundle.name, (
        "a bundle whose name does not carry its version cannot be traced to the code that built it"
    )


def test_it_carries_the_source_so_it_needs_no_release(contents: dict[str, bytes]) -> None:
    """FR-3. The published package predates `serve`, so depending on it would ship a dead bundle."""
    assert "src/semantiql/__init__.py" in contents
    assert "src/semantiql/server.py" in contents
    assert "src/semantiql/engine/run.py" in contents
    assert "src/server.py" in contents, "the entry point the manifest names"


def test_it_declares_its_dependencies_but_not_itself(contents: dict[str, bytes]) -> None:
    declared = contents["pyproject.toml"].decode()
    for dependency in ("sqlglot", "duckdb", "psycopg", "pydantic", "pyyaml", "mcp"):
        assert dependency in declared, f"{dependency} must be installable by the host"
    assert '\n  "semantiql' not in declared, (
        "semantiql must not be a dependency — its source is in the bundle (FR-3)"
    )


def test_no_compiled_artefacts_are_shipped(contents: dict[str, bytes]) -> None:
    """`__pycache__` bloats the zip and can embed build-machine paths inside `.pyc` files."""
    assert not [name for name in contents if "__pycache__" in name or name.endswith(".pyc")]


def test_nothing_inside_names_a_path_from_the_build_machine(contents: dict[str, bytes]) -> None:
    """The property the plugin lacked, and the reason this artifact exists.

    A bundle is unzipped somewhere nobody chose, so anything resolved at build time against the
    builder's filesystem is wrong on arrival — and wrong silently.
    """
    for name, blob in contents.items():
        if not name.endswith((".json", ".toml", ".py", ".txt")):
            continue
        found = re.findall(r"(/Users/[^\s\"']+|/home/[^\s\"']+|[A-Z]:\\\\[^\s\"']+)", blob.decode())
        assert not found, f"{name} contains a build-machine path: {found[:2]}"


# --- The manifest, which is the install dialog


def test_the_manifest_declares_a_uv_server(manifest: dict[str, Any]) -> None:
    assert manifest["manifest_version"] == "0.4", "uv servers require 0.4 or later"
    assert manifest["server"]["type"] == "uv"
    assert manifest["server"]["entry_point"] == "src/server.py"
    for field in ("name", "version", "description", "author"):
        assert manifest.get(field), f"manifest is missing {field}"


def test_the_version_matches_the_package(manifest: dict[str, Any]) -> None:
    """FR-7 — otherwise a bundle cannot be traced back to the code inside it."""
    assert manifest["version"] == metadata.version("semantiql")


def test_the_model_is_asked_for_with_a_file_picker(manifest: dict[str, Any]) -> None:
    """FR-4, and the whole reason a bundle beats a pasted JSON block.

    Spec 013 had to use an environment variable because a plugin has nowhere to ask. Here the host
    asks, so the most error-prone step in setup becomes a dialog.
    """
    model = manifest["user_config"]["model"]
    assert model["type"] == "file"
    assert model["required"] is True


def test_a_connection_string_is_marked_secret(manifest: dict[str, Any]) -> None:
    """The constitution says end users never touch a connection string.

    A `sensitive` field is how that stops being aspirational: the host masks it and stores it
    securely, instead of it living in a JSON file people paste into chat windows.
    """
    dsn = manifest["user_config"]["dsn"]
    assert dsn["sensitive"] is True
    assert dsn["required"] is False, "DuckDB users must not be forced to supply one"


def test_every_answer_reaches_the_server(manifest: dict[str, Any]) -> None:
    """Each `user_config` key is substituted into an environment variable the CLI reads.

    A field the user fills in that nothing consumes is worse than no field at all — it looks like
    configuration and does nothing.
    """
    from semantiql.cli import DATABASE_ENV, DATASOURCE_ENV, DSN_ENV, MODEL_ENV

    env = manifest["server"]["mcp_config"]["env"]
    assert set(env) == {MODEL_ENV, DATASOURCE_ENV, DSN_ENV, DATABASE_ENV}
    for key in manifest["user_config"]:
        assert any(f"${{user_config.{key}}}" == value for value in env.values()), (
            f"user_config.{key} is collected but never passed to the server"
        )


def test_the_advertised_tools_are_the_ones_that_exist(manifest: dict[str, Any]) -> None:
    """The manifest lists tools for the install dialog; a stale list misleads before install."""
    assert {tool["name"] for tool in manifest["tools"]} == {"describe_model", "query"}


# --- The regression test


def test_the_version_survives_without_an_installed_distribution(
    contents: dict[str, bytes], tmp_path: Path
) -> None:
    """Reproduces the bug that only appeared on machines without SemantiQL installed.

    The bundle puts its source on `sys.path` and never installs a distribution, so
    `importlib.metadata.version("semantiql")` raises `PackageNotFoundError`. That used to abort the
    import, meaning the bundle worked on every developer's machine and no user's.

    Simulated by importing the *extracted* package under a name the metadata lookup cannot resolve,
    which is exactly the condition inside a bundle.
    """
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    for name, blob in contents.items():
        target = extracted / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)

    assert (extracted / "src" / "semantiql" / "_version.txt").is_file(), (
        "the build stamp is what the fallback reads; without it a bundle reports 0+unknown"
    )

    probe = (
        "import importlib.metadata as m, sys;"
        "real = m.version;"
        # Make the lookup fail for semantiql only, exactly as it does inside a bundle.
        "m.version = lambda n: (_ for _ in ()).throw(m.PackageNotFoundError(n))"
        " if n == 'semantiql' else real(n);"
        f"sys.path.insert(0, {str(extracted / 'src')!r});"
        "import semantiql;"
        "print(semantiql.__version__)"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert result.returncode == 0, f"import failed without a distribution:\n{result.stderr}"
    assert result.stdout.strip() == metadata.version("semantiql")


def test_building_twice_gives_the_same_bundle(tmp_path: Path) -> None:
    """Deterministic enough that a rebuild is not a diff nobody can explain."""
    first, second = tmp_path / "a", tmp_path / "b"
    for out in (first, second):
        subprocess.run(
            [sys.executable, str(BUILDER), "--out", str(out)], check=True, capture_output=True
        )
    names = [sorted(zipfile.ZipFile(next(d.glob("*.mcpb"))).namelist()) for d in (first, second)]
    assert names[0] == names[1]
