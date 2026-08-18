"""Rebuild the test workspace's fixture database. Idempotent — run it whenever you want a clean one.

    uv run --project .. python build.py

The data is deliberately *ambiguous*, because this workspace exists to test the discovery loop and a
tidy schema tests nothing. Five money columns so "revenue" has no obvious answer; one row per order
*line* with two multi-line orders so a plain row count is wrong; a `timestamptz` with a row 30
minutes before midnight UTC so the timezone answer visibly moves a month; an email so the PII
question has something to be about; a view offering a genuine alternative grain; and a table in a
non-default schema so enumeration has something to qualify.

Every total the README quotes is asserted at the bottom of this file, so the fixture and the
documentation cannot drift.
"""

from __future__ import annotations

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
DATABASE = HERE / "shop.duckdb"

ROWS = [
    # line, order, email,     placed_at (UTC),        channel, qty, unit, gross, disc, refund, net
    # fmt: off
    (1, 100, "ana@ex.com", "2026-07-01 10:00:00+00", "web", 2, 10.00, 20.00, 2.00, 0.00, 18.00),
    (2, 100, "ana@ex.com", "2026-07-01 10:00:00+00", "web", 1, 30.00, 30.00, 0.00, 30.00, 0.00),
    (3, 101, "bo@ex.com", "2026-07-31 23:30:00+00", "store", 3, 5.00, 15.00, 0.00, 0.00, 15.00),
    (4, 102, "cy@ex.com", "2026-08-05 09:00:00+00", "web", 1, 40.00, 40.00, 4.00, 0.00, 36.00),
    (5, 102, "cy@ex.com", "2026-08-05 09:00:00+00", "web", 2, 12.50, 25.00, 0.00, 25.00, 0.00),
    # fmt: on
]

CUSTOMERS = [
    ("ana@ex.com", "US", "2026-01-15", "pro"),
    ("bo@ex.com", "TH", "2026-03-02", "free"),
    ("cy@ex.com", "US", "2026-06-20", "pro"),
]


def build() -> None:
    DATABASE.unlink(missing_ok=True)
    con = duckdb.connect(str(DATABASE))
    con.execute("""
        CREATE TABLE order_lines (
            line_id          BIGINT,
            order_id         BIGINT,
            customer_email   VARCHAR,
            placed_at        TIMESTAMPTZ,
            channel          VARCHAR,
            quantity         INTEGER,
            unit_price       DECIMAL(10, 2),
            gross_amount     DECIMAL(10, 2),
            discount_amount  DECIMAL(10, 2),
            refund_amount    DECIMAL(10, 2),
            net_amount       DECIMAL(10, 2)
        )
    """)
    con.executemany("INSERT INTO order_lines VALUES (?,?,?,?,?,?,?,?,?,?,?)", ROWS)

    con.execute("""
        CREATE TABLE customers (
            customer_email  VARCHAR,
            country         VARCHAR,
            signed_up_at    DATE,
            plan            VARCHAR
        )
    """)
    con.executemany("INSERT INTO customers VALUES (?,?,?,?)", CUSTOMERS)

    # A real alternative grain, not a decoy: one row per order. Whether the model should be built on
    # this or on order_lines is a judgement call, which is the point.
    con.execute("""
        CREATE VIEW order_totals AS
        SELECT order_id,
               MIN(placed_at)   AS placed_at,
               MIN(channel)     AS channel,
               SUM(net_amount)  AS net_amount,
               COUNT(*)         AS line_count
        FROM order_lines
        GROUP BY order_id
    """)

    con.execute("CREATE SCHEMA staging")
    con.execute("CREATE TABLE staging.raw_events (payload VARCHAR)")

    _assert_the_readme_is_true(con)
    con.close()
    print(f"built {DATABASE.name}: 2 tables, 1 view, 1 extra schema, {len(ROWS)} order lines")


def _assert_the_readme_is_true(con: duckdb.DuckDBPyConnection) -> None:
    """The numbers in README.md, checked against the data that was just loaded.

    Hand-computed figures are what let a reader tell a right answer from a plausible one, so a
    fixture that quietly stopped matching them would remove the only ground truth in this workspace.
    """
    checks: list[tuple[str, str, object]] = [
        ("gross revenue", "SELECT SUM(gross_amount) FROM order_lines", 130.00),
        ("discounts", "SELECT SUM(discount_amount) FROM order_lines", 6.00),
        ("refunds", "SELECT SUM(refund_amount) FROM order_lines", 55.00),
        ("net revenue", "SELECT SUM(net_amount) FROM order_lines", 69.00),
        ("distinct orders", "SELECT COUNT(DISTINCT order_id) FROM order_lines", 3),
        ("order lines", "SELECT COUNT(*) FROM order_lines", 5),
        ("units", "SELECT SUM(quantity) FROM order_lines", 9),
        ("customers", "SELECT COUNT(DISTINCT customer_email) FROM order_lines", 3),
        (
            "web net",
            "SELECT SUM(net_amount) FROM order_lines WHERE channel = 'web'",
            54.00,
        ),
        (
            "store net",
            "SELECT SUM(net_amount) FROM order_lines WHERE channel = 'store'",
            15.00,
        ),
        # Both zones are named explicitly. A bare `placed_at::TIMESTAMP` buckets in whatever the
        # *session* timezone happens to be, which is how this assertion first failed: on a +07
        # machine it silently answered the Bangkok question. That is the hazard spec 011 exists for,
        # reproduced here by accident, and it is worth keeping in mind while reading whatever model
        # gets written against this fixture.
        (
            "net in July, UTC",
            "SELECT SUM(net_amount) FROM order_lines "
            "WHERE DATE_TRUNC('month', placed_at AT TIME ZONE 'UTC') = '2026-07-01'",
            33.00,
        ),
        (
            "net in July, Asia/Bangkok",
            "SELECT SUM(net_amount) FROM order_lines WHERE "
            "DATE_TRUNC('month', placed_at AT TIME ZONE 'Asia/Bangkok') = '2026-07-01'",
            18.00,
        ),
    ]
    for label, sql, expected in checks:
        (actual,) = con.execute(sql).fetchone() or (None,)
        assert float(actual) == float(expected), (  # type: ignore[arg-type]
            f"README says {label} is {expected}, fixture says {actual}"
        )


if __name__ == "__main__":
    build()
