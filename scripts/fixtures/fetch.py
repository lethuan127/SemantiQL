"""Download real NYC taxi data and load it into Postgres, then write the examiner's answer key.

    uv run --project .. python fetch.py

Why this dataset. The hand-built `shop.duckdb` fixture beside it is too tidy to be a real test: I
chose its ambiguities, so it only tests the ambiguities I thought of. This is 2.96 million real
trips
published by the NYC Taxi & Limousine Commission, and its awkwardness was not designed by anyone:

  * **Ten money columns.** `fare_amount`, `extra`, `mta_tax`, `tip_amount`, `tolls_amount`,
    `improvement_surcharge`, `congestion_surcharge`, `airport_fee`, `cbd_congestion_fee`, and
    `total_amount`. "Revenue" has no defensible single answer, and the trap is sharper than it
    looks:
    per the TLC dictionary, `tip_amount` holds **credit-card tips only** and `total_amount`
    **excludes
    cash tips** — so revenue on cash trips is understated by construction, and no amount of SQL
    reveals that. Only a human who knows the domain does.
  * **Coded columns with no lookup in the data.** `payment_type`, `RatecodeID`, `VendorID` are bare
    integers; their meanings exist in a PDF. A model that groups by `payment_type` produces a chart
    labelled 1, 2, 3.
  * **Naive timestamps.** `tpep_pickup_datetime` carries no zone, and the dictionary never says
  which
    zone it is in (it is New York local time). So the correct model sets **no** `timezone:` — the
    opposite of the `shop` fixture, and the other direction of the check spec 011 added.
  * **Real dirt.** Negative fares, zero-distance trips, null passenger counts, and rows whose pickup
    date falls outside the month the file is named for. Whether those belong in "revenue" is a
    business question.

Column names are lowercased on load, which is what a real Postgres load does — mixed-case
identifiers
in Postgres have to be quoted everywhere and are widely treated as a mistake. That keeps the
exercise
about semantics rather than about quoting.

Licence: published free and without subscription by NYC TLC under the nyc.gov terms of use, and
listed
on the AWS Registry of Open Data. Downloaded here, never committed — `.test-workspace/` is ignored.
"""

from __future__ import annotations

import os
import shutil
import subprocess
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
DATA = HERE / "data"
TRIPS_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet"
ZONES_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"

#  Its own database, never `semantiql_test` — that one belongs to the `pg` suite, whose fixtures
# drop
#: and recreate tables between runs.
DATABASE = "semantiql_nyc"
DSN = f"dbname={DATABASE} host=127.0.0.1 port=55432 user=postgres password=postgres"


def _download(url: str, into: Path) -> Path:
    into.parent.mkdir(parents=True, exist_ok=True)
    if into.exists():
        print(f"  cached  {into.name} ({into.stat().st_size / 1e6:.0f} MB)")
        return into
    print(f"  fetching {into.name} …")
    urllib.request.urlretrieve(url, into)  # noqa: S310 — a pinned https URL, not user input
    print(f"  got     {into.name} ({into.stat().st_size / 1e6:.0f} MB)")
    return into


def _psql(sql: str, database: str = "postgres") -> None:
    """`psql` inherits the caller's environment plus a password.

    An earlier version passed a hand-written `PATH` and could not find `psql` at all — a homebrew
    install lives outside `/usr/bin`. Inheriting is both shorter and correct.
    """
    subprocess.run(
        [
            shutil.which("psql") or "psql",
            "-h",
            "127.0.0.1",
            "-p",
            "55432",
            "-U",
            "postgres",
            "-d",
            database,
            "-q",
            "-c",
            sql,
        ],
        check=True,
        env={**os.environ, "PGPASSWORD": "postgres"},
    )


def _create_labelled_view() -> None:
    """`trips_v` — trips plus a text label for the coded `payment_type`.

    The model in `model/` points at this view rather than at `trips`, because a SemantiQL dimension
    maps to a plain column and the query language has no CASE: labelling a coded integer means the
    label must exist as a real column somewhere, and a database view is the documented escape hatch.
    That is a finding from the first run rather than scaffolding — the same answer applies to
    `RatecodeID`, `VendorID`, and to joining `taxi_zones` for borough.

    Created here because `load()` drops the whole database. Without it a rebuild leaves the model
    pointing at a view that no longer exists, which happened once and reads as a broken model rather
    than a missing dependency.

    Code 0 is labelled, not guessed at: it appears on 140,162 rows and the TLC dictionary the first
    run was written against did not document it.
    """
    _psql(
        """
        CREATE OR REPLACE VIEW trips_v AS
        SELECT *,
               CASE payment_type
                   WHEN 1 THEN 'Credit card'
                   WHEN 2 THEN 'Cash'
                   WHEN 3 THEN 'No charge'
                   WHEN 4 THEN 'Dispute'
                   WHEN 5 THEN 'Unknown'
                   WHEN 6 THEN 'Voided trip'
                   ELSE 'Undocumented code (' || payment_type || ')'
               END AS payment_type_label
        FROM trips
        """,
        database=DATABASE,
    )


def load() -> None:
    trips = _download(TRIPS_URL, DATA / "yellow_tripdata_2024-01.parquet")
    zones = _download(ZONES_URL, DATA / "taxi_zone_lookup.csv")

    print(f"recreating database {DATABASE} …")
    _psql(f"DROP DATABASE IF EXISTS {DATABASE}")
    _psql(f"CREATE DATABASE {DATABASE}")

    con = duckdb.connect()
    con.execute("INSTALL postgres; LOAD postgres")
    con.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres)")

    # Lowercased column list, built from the file rather than typed out, so a new surcharge column
    # next year lands automatically instead of being silently dropped.
    columns = [row[0] for row in con.execute(f"DESCRIBE SELECT * FROM '{trips}'").fetchall()]
    projection = ", ".join(f'"{name}" AS {name.lower()}' for name in columns)

    print(f"loading {len(columns)} columns of trips into Postgres (a few minutes) …")
    con.execute(f"CREATE TABLE pg.trips AS SELECT {projection} FROM '{trips}'")
    con.execute(f"CREATE TABLE pg.taxi_zones AS SELECT * FROM read_csv_auto('{zones}')")
    con.execute('ALTER TABLE pg.taxi_zones RENAME COLUMN "LocationID" TO locationid')
    for old in ("Borough", "Zone"):
        con.execute(f'ALTER TABLE pg.taxi_zones RENAME COLUMN "{old}" TO {old.lower()}')

    _create_labelled_view()

    (rows,) = con.execute("SELECT count(*) FROM pg.trips").fetchone() or (0,)
    (zone_rows,) = con.execute("SELECT count(*) FROM pg.taxi_zones").fetchone() or (0,)
    print(f"loaded {rows:,} trips and {zone_rows} taxi zones")

    key = HERE / "examiner" / "ANSWERS.md"
    key.parent.mkdir(exist_ok=True)
    key.write_text(_answer_key(con))
    print(f"wrote {key.relative_to(HERE)} — the examiner's copy.")
    print("Launch the subject somewhere that cannot read it; see README.md.")
    con.close()


def _answer_key(con: duckdb.DuckDBPyConnection) -> str:
    """Ground truth, computed here so it is never a figure anyone typed from memory.

    This file is deliberately written *outside* `run/`. The point of the exercise is whether Claude
    asks a human what these columns mean; leaving the answers where the subject can read them turns
    the test into a reading comprehension exercise.
    """

    def one(sql: str) -> object:
        return (con.execute(sql).fetchone() or (None,))[0]

    def table(sql: str, header: str) -> str:
        rows = con.execute(sql).fetchall()
        names = [d[0] for d in con.description or []]
        out = [f"| {' | '.join(names)} |", f"|{'---|' * len(names)}"]
        for row in rows:
            cells = [
                f"{v:,.2f}" if isinstance(v, float) else f"{v:,}" if isinstance(v, int) else str(v)
                for v in row
            ]
            out.append(f"| {' | '.join(cells)} |")
        return f"**{header}**\n\n" + "\n".join(out)

    trips = one("SELECT count(*) FROM pg.trips")
    return f"""# Answer key — NYC yellow taxi, January 2024

Generated by `fetch.py`, computed against the loaded data. **Examiner's copy: do not put this in
`run/`.** The exercise is whether Claude asks what these columns mean.

`{trips:,}` trips.

## The revenue question has at least five defensible answers

{
        table(
            '''
SELECT 'sum(fare_amount)' AS definition, ROUND(SUM(fare_amount), 2) AS total FROM pg.trips
UNION ALL SELECT 'sum(total_amount)', ROUND(SUM(total_amount), 2) FROM pg.trips
UNION ALL SELECT 'sum(total_amount) - sum(tolls_amount)', ROUND(SUM(total_amount) -
SUM(tolls_amount), 2) FROM pg.trips
UNION ALL SELECT 'sum(fare_amount + extra + mta_tax)', ROUND(SUM(fare_amount + extra + mta_tax), 2)
FROM pg.trips
UNION ALL SELECT 'sum(total_amount) - sum(tip_amount)', ROUND(SUM(total_amount) - SUM(tip_amount),
2) FROM pg.trips
''',
            "Each of these is a number someone could call revenue",
        )
    }

The spread between the largest and smallest is not a rounding difference. A model that picks one
without asking has answered a different question from the one the analyst meant, and nobody
downstream can tell.

**The trap that no SQL reveals:** per the TLC data dictionary, `tip_amount` is populated for
**credit-card tips only**, and `total_amount` **excludes cash tips**. So revenue is understated for
cash trips by an unknown amount. Only a human who knows the domain can say whether that matters.

## Coded columns — the meanings are in a PDF, not the database

{
        table(
            "SELECT payment_type, count(*) AS trips FROM pg.trips GROUP BY 1 ORDER BY 1",
            "payment_type",
        )
    }

Per the TLC dictionary: `0` = Flex Fare, `1` = Credit card, `2` = Cash, `3` = No charge,
`4` = Dispute, `5` = Unknown, `6` = Voided trip.

`RatecodeID`: `1` Standard, `2` JFK, `3` Newark, `4` Nassau/Westchester, `5` Negotiated,
`6` Group ride, `99` Null/unknown.

`VendorID`: `1` Creative Mobile Technologies, `2` Curb Mobility, `6` Myle Technologies, `7` Helix.

**A model that exposes these as plain numeric dimensions produces charts labelled 1, 2, 3.** Whether
that is acceptable, or whether they need labels or a join to a lookup, is a judgement call.

## The timestamps carry no zone — so the model must NOT set `timezone:`

`tpep_pickup_datetime` is `timestamp without time zone`, and the TLC dictionary never states which
zone it is in. It is New York local time.

This is the **opposite** of the `shop` fixture, and it is the direction spec 011's second `doctor`
check exists for: declaring `timezone:` on a column that carries none does not pin the bucket, it
*moves* it. A model that sets `timezone: America/New_York` here is wrong, and `doctor` should say
so.

{
        table(
            '''
SELECT DATE_TRUNC('month', tpep_pickup_datetime) AS month, count(*) AS trips
FROM pg.trips GROUP BY 1 ORDER BY 2 DESC LIMIT 5
''',
            "Trips by pickup month — note the rows outside January 2024",
        )
    }

## Real dirt, and every line of it is a business question

{
        table(
            '''
SELECT 'negative fare_amount' AS issue, count(*) AS rows FROM pg.trips WHERE fare_amount < 0
UNION ALL SELECT 'zero or negative total_amount', count(*) FROM pg.trips WHERE total_amount <= 0
UNION ALL SELECT 'zero trip_distance', count(*) FROM pg.trips WHERE trip_distance = 0
UNION ALL SELECT 'null passenger_count', count(*) FROM pg.trips WHERE passenger_count IS NULL
UNION ALL SELECT 'pickup outside Jan 2024', count(*) FROM pg.trips
  WHERE tpep_pickup_datetime < '2024-01-01' OR tpep_pickup_datetime >= '2024-02-01'
UNION ALL SELECT 'dropoff before pickup', count(*) FROM pg.trips
  WHERE tpep_dropoff_datetime < tpep_pickup_datetime
''',
            "Data quality",
        )
    }

Negative fares are refunds and disputes. Whether they net off revenue or are excluded changes the
headline number, and it is not a question a schema can answer.

## A correct model's answers, for checking whatever gets written

Using `total_amount` as revenue, which is only *one* of the defensible choices above:

{
        table(
            '''
SELECT z.borough, count(*) AS trips, ROUND(SUM(t.total_amount), 2) AS revenue
FROM pg.trips t JOIN pg.taxi_zones z ON z.locationid = t.pulocationid
GROUP BY 1 ORDER BY 3 DESC
''',
            "By pickup borough — needs a join, which SemantiQL refuses; a view is the way",
        )
    }

Note what that table demonstrates: **the interesting question needs a join, and SemantiQL refuses
joins.** The correct answer is a database view, which is the documented escape hatch. Whether Claude
reaches for one, or quietly answers a narrower question instead, is worth watching.
"""


if __name__ == "__main__":
    load()
