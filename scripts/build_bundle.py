"""Build the Claude Desktop bundle — `dist/semantiql-<version>.mcpb` (spec 014).

A `.mcpb` is a zip a user opens to install a local MCP server in one click, with the host
collecting configuration in a dialog rather than the user editing JSON.

Three things about this script are decisions rather than mechanics.

**The source is copied, never committed twice.** A second copy of `src/semantiql/` in git would
drift the moment either changed, and a reviewer would have no way to tell which was authoritative.
It is carried because MCPB resolves dependencies from the bundle's own `pyproject.toml`, and the
published `semantiql` predates the `serve` verb — depending on it would ship a bundle that cannot
start. When a release exists, `_dependencies()` is the one place that changes.

**The manifest is generated, not committed.** Its version has to match the package's, and two files
holding one version is how they disagree.

**No network.** Everything here is file copying and JSON, so a fresh clone builds offline. The
*install* is not offline — the host fetches dependencies then — which is worth not promising.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tomllib
import zipfile
from importlib import metadata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "src" / "semantiql"
ENTRY_POINT = REPO / "bundle" / "server.py"
PYPROJECT = REPO / "pyproject.toml"

#: Spelled indirectly so this script can emit a docstring without fighting its own quoting.
THREEQ = chr(34) * 3


#: Everything the bundle needs that is not SemantiQL itself. Read from the real manifest so the two
#: cannot disagree about versions — a bundle pinned differently from the package it carries would
#: be a genuinely confusing bug to chase.
def _dependencies() -> list[str]:
    declared: list[str] = tomllib.loads(PYPROJECT.read_text())["project"]["dependencies"]
    # `semantiql` is absent on purpose: the source travels in the bundle. Swap this whole function
    # for `[f"semantiql=={version}"]` once a release with `serve` is published.
    return declared


def _manifest(version: str) -> dict[str, object]:
    """The install dialog, essentially.

    `user_config` is why a bundle beats a pasted JSON block: the model becomes a file picker and a
    Postgres DSN becomes a field marked secret. The constitution says end users never touch a
    connection string — a `sensitive` field is how that becomes literally true rather than
    aspirational.
    """
    return {
        "manifest_version": "0.4",
        "name": "semantiql",
        "display_name": "SemantiQL",
        "version": version,
        "description": (
            "Ask questions about your database in plain language, through a reviewed semantic "
            "model that refuses rather than guesses."
        ),
        "long_description": (
            "SemantiQL sits between Claude and your SQL database. Claude writes semantic SQL "
            "against a business model you control — dimensions, measures, metrics — and SemantiQL "
            "validates it before anything runs. A question the model cannot answer is refused with "
            "a reason, never answered with a plausible guess."
        ),
        "author": {"name": "Thuan Le"},
        "repository": {"type": "git", "url": "https://github.com/lethuan127/semantiql"},
        "license": "MIT",
        "keywords": ["semantic-layer", "sql", "duckdb", "postgres", "analytics"],
        "server": {
            "type": "uv",
            "entry_point": "src/server.py",
            "mcp_config": {
                "command": "uv",
                "args": ["run", "${__dirname}/src/server.py"],
                # The host substitutes the install dialog's answers into these. Every option that
                # has a command-line flag has a variable, and `cli.py` reads them — so the entry
                # point stays trivial and the behaviour is covered by ordinary tests.
                "env": {
                    "SEMANTIQL_MODEL": "${user_config.model}",
                    "SEMANTIQL_DATASOURCE": "${user_config.datasource}",
                    "SEMANTIQL_DSN": "${user_config.dsn}",
                    "SEMANTIQL_DATABASE": "${user_config.database}",
                },
            },
        },
        "user_config": {
            "model": {
                "type": "file",
                "title": "Semantic model",
                "description": (
                    "Your semantic model YAML — the file that defines what revenue, orders and "
                    "the rest mean. Run `semantiql doctor` on it first."
                ),
                "required": True,
            },
            "datasource": {
                "type": "string",
                "title": "Datasource",
                "description": "Which engine the model runs against: duckdb or postgres.",
                "default": "duckdb",
                "required": False,
            },
            "dsn": {
                "type": "string",
                "title": "Postgres connection string",
                "description": (
                    "For Postgres only, e.g. postgresql://readonly@host/db. Use a read-only "
                    "account. Leave blank to use libpq's environment and ~/.pgpass instead."
                ),
                "sensitive": True,
                "required": False,
            },
            "database": {
                "type": "file",
                "title": "DuckDB database file",
                "description": (
                    "For DuckDB only, and only if your model reads tables rather than CSV or "
                    "Parquet files. Leave blank otherwise."
                ),
                "required": False,
            },
        },
        "tools": [
            {
                "name": "describe_model",
                "description": "List the tables, dimensions, measures and metrics available.",
            },
            {
                "name": "query",
                "description": "Answer a question written as semantic SQL, or explain the refusal.",
            },
        ],
        "compatibility": {"platforms": ["darwin", "win32", "linux"]},
    }


def _bundle_pyproject(version: str) -> str:
    deps = "\n".join(f'  "{d}",' for d in _dependencies())
    return (
        "# Generated by scripts/build_bundle.py — do not edit.\n"
        "#\n"
        "# The host installs these with uv when the bundle is opened. `semantiql` is absent\n"
        "# because its source travels in the bundle: the published package predates the `serve`\n"
        "# verb, so depending on it would ship something that cannot start.\n"
        "[project]\n"
        'name = "semantiql-bundle"\n'
        f'version = "{version}"\n'
        'description = "Claude Desktop bundle for SemantiQL"\n'
        'requires-python = ">=3.11"\n'
        "dependencies = [\n"
        f"{deps}\n"
        "]\n"
    )


def build(destination: Path, version: str | None = None) -> Path:
    """Assemble the bundle and return the path to it."""
    version = version or metadata.version("semantiql")
    staging = destination / f"semantiql-{version}"
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "src").mkdir(parents=True)

    (staging / "manifest.json").write_text(json.dumps(_manifest(version), indent=2) + "\n")
    (staging / "pyproject.toml").write_text(_bundle_pyproject(version))
    shutil.copy2(ENTRY_POINT, staging / "src" / "server.py")
    # `__pycache__` would bloat the zip and can carry absolute paths in compiled artefacts, which
    # the gate's no-absolute-paths check would then trip over for a reason nobody could act on.
    shutil.copytree(
        PACKAGE,
        staging / "src" / "semantiql",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    # The bundle carries the package as source and never installs it, so `importlib.metadata`
    # finds no distribution and `__init__` falls back to this stamp. Generated rather than
    # committed, so git keeps one source of truth for the version while the bundle still reports
    # the one it was built from. Without it, importing SemantiQL raised PackageNotFoundError on
    # any machine that did not already have it installed — invisible in development, because a
    # checkout always has the distribution present.
    (staging / "src" / "semantiql" / "_version.txt").write_text(version + "\n")

    archive = destination / f"semantiql-{version}.mcpb"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(staging))
    shutil.rmtree(staging)
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Claude Desktop bundle.")
    parser.add_argument(
        "-o",
        "--out",
        default=str(REPO / "dist"),
        help="directory to write the bundle into (default: dist/)",
    )
    args = parser.parse_args()
    destination = Path(args.out)
    destination.mkdir(parents=True, exist_ok=True)
    archive = build(destination)
    size = archive.stat().st_size / 1024
    print(f"{archive}  ({size:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
