"""Load UCI Online Retail II — real UK retailer transactions — into its own Postgres database.

    uv run --project .. python fetch_retail.py

**Why this dataset and not SAP SALT.** SALT is authentic SAP ERP data and remains the better
*domain*
match, but it is gated: the token in `.env` is valid (Hugging Face `whoami` returns 200) and the
account
is still not on its authorized list, so every file request answers 403 with
*"you are not in the authorized list"*. Accepting those terms is the repository owner's call, not an
agent's, so `fetch_salt.py` sits ready beside this and this is what runs today.

Online Retail II is a fair trade rather than a consolation. It is **real** — a UK gift-ware
retailer's
transactions, 1,067,371 rows over 2009-12-01 to 2011-12-09 — it is **CC BY 4.0**, so attribution is
the
only condition, and it needs no account at all.

**What makes it a hard test of a semantic layer**, which is the whole reason a fixture exists:

* **There is no revenue column.** Revenue is `Quantity * Price`, and a SemantiQL measure maps to a
  single column. So revenue *cannot be modelled directly* — the correct answer is a database view,
  and
  a run that fudges it instead is exactly the failure the eval should catch. No invented fixture
  would
  have produced that problem so cleanly.
* **Credit notes.** An `Invoice` beginning `C` is a return, carrying negative `Quantity`. Whether
  returns net off revenue is a business decision. This is also what broke type inference on first
  read:
  the column looks numeric until row 180.
* **Naive timestamps.** `InvoiceDate` carries no zone, so a correct model sets **no** `timezone:` —
the
  opposite of the taxi fixture, and the direction spec 011's second `doctor` check exists for.
* **Missing customer ids**, so "how many customers" has more than one honest answer.
* **Two sheets**, one per year, so the grain question starts before the modelling does.

Attribution, as CC BY 4.0 requires: Chen, D. (2012). *Online Retail II*. UCI Machine Learning
Repository. https://doi.org/10.24432/C5CG6D

Nothing downloaded here is committed; `.test-workspace/` is ignored in its entirety.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
import zipfile
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
DATA = HERE / "data"
ARCHIVE = DATA / "online_retail_II.zip"
WORKBOOK = DATA / "online_retail_II.xlsx"
URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"

SHEETS = {"2009_2010": "Year 2009-2010", "2010_2011": "Year 2010-2011"}

#: Its own database. Never `semantiql_test`, which belongs to the `pg` suite.
DATABASE = "semantiql_retail"
DSN = f"dbname={DATABASE} host=127.0.0.1 port=55432 user=postgres password=postgres"


def _psql(sql: str, database: str = "postgres") -> None:
    subprocess.run(
        [
            shutil.which("psql") or "psql",
            *("-h", "127.0.0.1", "-p", "55432", "-U", "postgres", "-d", database, "-q", "-c", sql),
        ],
        check=True,
        env={**os.environ, "PGPASSWORD": "postgres"},
    )


def _download() -> None:
    if WORKBOOK.exists() and WORKBOOK.stat().st_size > 0:
        print(f"  cached   {WORKBOOK.name} ({WORKBOOK.stat().st_size / 1e6:.0f} MB)")
        return
    DATA.mkdir(parents=True, exist_ok=True)
    print("  fetching online_retail_II.zip (~46 MB) …")
    urllib.request.urlretrieve(URL, ARCHIVE)  # noqa: S310 — a pinned https URL
    with zipfile.ZipFile(ARCHIVE) as archive:
        archive.extractall(DATA)
    print(f"  got      {WORKBOOK.name} ({WORKBOOK.stat().st_size / 1e6:.0f} MB)")


def load() -> None:
    _download()

    print(f"recreating database {DATABASE} …")
    _psql(f"DROP DATABASE IF EXISTS {DATABASE}")
    _psql(f"CREATE DATABASE {DATABASE}")

    con = duckdb.connect()
    con.execute("INSTALL excel; LOAD excel")
    con.execute("INSTALL postgres; LOAD postgres")
    con.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres)")

    # `all_varchar` then cast explicitly, because `Invoice` looks numeric for 179 rows and then hits
    # `C489449` — a credit note. Letting the reader infer types fails there, and inferring from a
    # sample is how a loader silently drops every return in the file.
    reads = [
        f"SELECT '{label}' AS source_year, * "
        f"FROM read_xlsx('{WORKBOOK}', sheet = '{sheet}', all_varchar = true)"
        for label, sheet in SHEETS.items()
    ]
    union = " UNION ALL ".join(reads)
    print(f"  loading {len(SHEETS)} sheets into one relation …")
    con.execute(f"""
        CREATE TABLE pg.invoice_lines AS
        SELECT
            source_year,
            Invoice                      AS invoice,
            Invoice LIKE 'C%'            AS is_credit_note,
            StockCode                    AS stock_code,
            Description                  AS description,
            CAST(Quantity AS BIGINT)     AS quantity,
            -- `all_varchar` hands dates back as Excel serials ("40148.322916666664"), so the
            -- epoch conversion is explicit. Verified against the source's published span,
            -- 2009-12-01 to 2011-12-09; a wrong epoch would shift every row by years and still
            -- load without complaint.
            TIMESTAMP '1899-12-30'
                + INTERVAL (CAST(InvoiceDate AS DOUBLE) * 86400) SECOND AS invoice_date,
            CAST(Price AS DECIMAL(12, 4)) AS unit_price,
            "Customer ID"                AS customer_id,
            Country                      AS country
        FROM ({union})
    """)

    (rows,) = con.execute("SELECT count(*) FROM pg.invoice_lines").fetchone() or (0,)
    print(f"  loaded  invoice_lines: {rows:,} rows")

    _write_answer_key(con)
    con.close()
    print(f"\nready. Point SemantiQL at it with:\n  PGDATABASE={DATABASE}")


def _write_answer_key(con: duckdb.DuckDBPyConnection) -> None:
    """Ground truth, computed rather than typed, so a grader can quote a figure that is true."""

    def scalar(sql: str) -> object:
        return (con.execute(sql).fetchone() or (None,))[0]

    lines = scalar("SELECT count(*) FROM pg.invoice_lines")
    revenue = scalar("SELECT round(sum(quantity * unit_price), 2) FROM pg.invoice_lines")
    revenue_excl = scalar(
        "SELECT round(sum(quantity * unit_price), 2) FROM pg.invoice_lines WHERE NOT is_credit_note"
    )
    credits = scalar("SELECT count(*) FROM pg.invoice_lines WHERE is_credit_note")
    negatives = scalar("SELECT count(*) FROM pg.invoice_lines WHERE quantity < 0")
    no_customer = scalar("SELECT count(*) FROM pg.invoice_lines WHERE customer_id IS NULL")
    invoices = scalar("SELECT count(DISTINCT invoice) FROM pg.invoice_lines")
    customers = scalar("SELECT count(DISTINCT customer_id) FROM pg.invoice_lines")
    countries = scalar("SELECT count(DISTINCT country) FROM pg.invoice_lines")
    stock_codes = scalar("SELECT count(DISTINCT stock_code) FROM pg.invoice_lines")
    descriptions = scalar("SELECT count(DISTINCT description) FROM pg.invoice_lines")
    # `or` the empty pair: `fetchone()` is typed as optional, and mypy started checking these
    # scripts the moment they moved out of the ignored workspace — which found this (spec 022).
    span = con.execute(
        "SELECT min(invoice_date), max(invoice_date) FROM pg.invoice_lines"
    ).fetchone() or (None, None)

    key = HERE / "examiner" / "RETAIL-ANSWERS.md"
    key.parent.mkdir(exist_ok=True)
    key.write_text(f"""# Answer key — UCI Online Retail II

Computed by `fetch_retail.py` against the loaded data. **Examiner's copy — keep it out of any
directory
a run under evaluation can read.**

Chen, D. (2012). *Online Retail II*. UCI Machine Learning Repository. CC BY 4.0.
https://doi.org/10.24432/C5CG6D

| Fact | Value |
|---|---|
| invoice lines | {lines:,} |
| distinct invoices | {invoices:,} |
| distinct customers | {customers:,} |
| countries | {countries} |
| distinct stock codes | {stock_codes:,} |
| distinct descriptions | {descriptions:,} |
| date span | {span[0]} to {span[1]} |

## The revenue question, which has no column

There is **no revenue column**. Revenue is `quantity * unit_price`, and a
SemantiQL measure maps to a single column — so revenue cannot be modelled
directly. A database view is the correct answer, and a run that quietly models
`unit_price` with `agg: sum` instead has produced a meaningless number.

| Definition | Value |
|---|---|
| `sum(quantity * unit_price)`, all rows | {revenue:,} |
| the same, excluding credit notes | {revenue_excl:,} |

The gap between those two is the returns policy: a business decision, not a
derivation.

## The dirt, and what each row of it asks

| Issue | Rows | The question it forces |
|---|---|---|
| credit notes (`invoice` starts `C`) | {credits:,} | do returns net off revenue? |
| negative quantity | {negatives:,} | same question, seen from the other side |
| null `customer_id` | {no_customer:,} | is "how many customers" a count of known customers, or of
all lines? |

`invoice_date` is `timestamp without time zone` and the source states no zone, so
a correct model sets **no** `timezone:`. Declaring one moves the buckets rather
than pinning them, which is the direction spec 011's second `doctor` check exists
to catch.
""")
    print(f"  wrote   {key.relative_to(HERE)}")


if __name__ == "__main__":
    load()
