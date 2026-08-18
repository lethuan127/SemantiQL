"""Load SAP's SALT dataset — real S/4HANA sales data — into its own Postgres database.

    uv run --project .. python fetch_salt.py

**The token is never handled by anything but this script.** It is read from `HF_ACCESS_TOKEN` in the
environment, or failing that from `.env` in the repository root, and used only as an Authorization
header. It is not printed, not passed as a command-line argument — where it would land in a shell
history and in every process listing on the machine — and not written anywhere. The repository's own
tool permissions deny reading `.env`, which is the right boundary rather than an obstacle: a secret
nobody reads cannot be leaked into a transcript.

**Licence: CC-BY-NC-SA-4.0.** Non-commercial, share-alike, and gated behind an acceptance the
repository owner made. That is why this script is the artefact and the data is output: nothing it
downloads is committed, and `.test-workspace/` is ignored in its entirety.

**Why this dataset.** The taxi fixture beside it is real but not a sales domain. SALT is authentic
ERP
data, and an ERP schema is where the questions a semantic layer exists for are *native* rather than
contrived: net against gross against tax, document against item grain, several currencies, credit
memos
carried as negatives, and column names a human still has to sanction.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import duckdb


def _workspace() -> Path:
    """`<repo>/.test-workspace` — where output goes, and the only ignored place it may go.

    Derived by walking up to the repository root, not by hopping relative to this
    file. These scripts used to *live* in `.test-workspace/`, so they were
    git-ignored along with their output — nothing was preserved, and the
    fetch-on-demand design lost the reproducibility it existed for (spec 022).
    Moving them out is only safe if the output paths move too: a relative hop
    would have started writing a 46 MB workbook into a tracked directory.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            workspace = parent / ".test-workspace"
            workspace.mkdir(exist_ok=True)
            return workspace
    raise SystemExit("could not find the repository root (no pyproject.toml above this file)")


HERE = _workspace()
REPO = HERE.parent  # the repository root, since HERE is <repo>/.test-workspace
DATA = HERE / "data" / "salt"

#: The canonical repository. `sap-ai-research/SALT` redirects here.
BASE = "https://huggingface.co/datasets/SAP/SALT/resolve/main"
TABLES = {
    "sales_documents": "I_SalesDocument_train.parquet",
    "sales_document_items": "I_SalesDocumentItem_train.parquet",
    "customers": "I_Customer.parquet",
    "addresses": "I_AddrOrgNamePostalAddress.parquet",
}

#: Its own database, never `semantiql_test` — that belongs to the `pg` suite, whose fixtures
#: drop and recreate tables between runs. Sharing it once already buried a fixture among them.
DATABASE = "semantiql_salt"
DSN = f"dbname={DATABASE} host=127.0.0.1 port=55432 user=postgres password=postgres"


def _token() -> str:
    """The Hugging Face token, from the environment or from `.env`, without ever revealing it."""
    token = os.environ.get("HF_ACCESS_TOKEN") or os.environ.get("HF_TOKEN")
    if token:
        return token.strip()

    env = REPO / ".env"
    if env.is_file():
        for line in env.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() in {"HF_ACCESS_TOKEN", "HF_TOKEN"}:
                return value.strip().strip("'\"")
    raise SystemExit(
        "no HF_ACCESS_TOKEN found in the environment or in .env.\n"
        "SALT is a gated dataset: accept its licence at\n"
        "  https://huggingface.co/datasets/SAP/SALT\n"
        "then put HF_ACCESS_TOKEN=<token> in .env (which is git-ignored)."
    )


def _download(filename: str, token: str) -> Path:
    into = DATA / filename
    if into.exists() and into.stat().st_size > 0:
        print(f"  cached   {filename} ({into.stat().st_size / 1e6:.1f} MB)")
        return into
    into.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(  # noqa: S310 — a pinned https URL
        f"{BASE}/{filename}", headers={"Authorization": f"Bearer {token}"}
    )
    print(f"  fetching {filename} …")
    try:
        with urllib.request.urlopen(request) as response, into.open("wb") as out:  # noqa: S310
            shutil.copyfileobj(response, out)
    except urllib.error.HTTPError as exc:
        into.unlink(missing_ok=True)
        if exc.code in (401, 403):
            raise SystemExit(
                f"{exc.code} for {filename}. The token is valid but this account is not on "
                "SALT's authorized list. Accept the terms at\n"
                "  https://huggingface.co/datasets/SAP/SALT\n"
                "with the same account the token belongs to, then re-run."
            ) from exc
        raise
    print(f"  got      {filename} ({into.stat().st_size / 1e6:.1f} MB)")
    return into


def _psql(sql: str, database: str = "postgres") -> None:
    subprocess.run(
        [
            shutil.which("psql") or "psql",
            *("-h", "127.0.0.1", "-p", "55432", "-U", "postgres", "-d", database, "-q", "-c", sql),
        ],
        check=True,
        env={**os.environ, "PGPASSWORD": "postgres"},
    )


def load() -> None:
    token = _token()
    print(f"downloading SALT into {DATA.relative_to(HERE)} (licensed, never committed)")
    files = {name: _download(filename, token) for name, filename in TABLES.items()}

    print(f"recreating database {DATABASE} …")
    _psql(f"DROP DATABASE IF EXISTS {DATABASE}")
    _psql(f"CREATE DATABASE {DATABASE}")

    con = duckdb.connect()
    con.execute("INSTALL postgres; LOAD postgres")
    con.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres)")

    for table, path in files.items():
        # Column names are lowercased, which is what a real Postgres load does — mixed-case
        # identifiers have to be quoted everywhere and are widely treated as a mistake. ERP column
        # names are long and CamelCase, so this matters more here than it did for the taxi fixture.
        columns = [row[0] for row in con.execute(f"DESCRIBE SELECT * FROM '{path}'").fetchall()]
        projection = ", ".join(f'"{name}" AS {name.lower()}' for name in columns)
        print(f"  loading {table} ({len(columns)} columns) …")
        con.execute(f"CREATE TABLE pg.{table} AS SELECT {projection} FROM '{path}'")
        (rows,) = con.execute(f"SELECT count(*) FROM pg.{table}").fetchone() or (0,)
        print(f"  loaded  {table}: {rows:,} rows")

    con.close()
    print(f"\nready. Point SemantiQL at it with:\n  PGDATABASE={DATABASE}")


if __name__ == "__main__":
    load()
