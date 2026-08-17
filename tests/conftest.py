"""Shared fixtures. The example model is the test corpus — if it breaks, the demo breaks."""

from __future__ import annotations

import csv
import os
from collections.abc import Iterator

import psycopg
import pytest

from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.adapters.postgres import PostgresAdapter
from semantiql.knowledge.loader import load_model
from semantiql.knowledge.model import SemanticModel
from tests._support import RETAIL

EXAMPLE = RETAIL / "semantic_model.yml"
EXAMPLE_PG = RETAIL / "semantic_model.postgres.yml"
ORDERS_CSV = RETAIL / "orders.csv"

#: How the Postgres suite is pointed at a database. Nothing in the repo can bundle one, so
#: absent this the whole `pg` suite skips with a stated reason rather than failing — which is
#: what keeps a fresh clone runnable with no database installed (spec 010, FR-11).
DSN_ENV = "SEMANTIQL_TEST_DSN"

_SKIP_REASON = (
    f"no Postgres to test against — set {DSN_ENV} to a connection string, e.g.\n"
    "    docker run --rm -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:17\n"
    f"    {DSN_ENV}=postgresql://postgres:postgres@localhost/postgres uv run pytest -m pg"
)

#: The corpus, mirroring `orders.csv` column for column. Types are chosen to be the *natural*
#: Postgres spelling of what the CSV holds, not to match DuckDB's inferred types — the point of
#: the differential suite is that two different physical type systems produce one answer.
_ORDERS_DDL = """
DROP TABLE IF EXISTS orders;
CREATE TABLE orders (
    order_id   integer,
    order_date date,
    channel    varchar(32),
    region     varchar(32),
    amount     numeric(10, 2)
)
"""

#: A second table that is deliberately wrong, so `doctor` has something to find. Every column
#: is text: `order_date` is a date stored as text, and `amount` is a number stored as text.
_MISTYPED_DDL = """
DROP TABLE IF EXISTS orders_mistyped;
CREATE TABLE orders_mistyped (
    order_id   text,
    order_date text,
    channel    text,
    amount     text
)
"""


@pytest.fixture(scope="session")
def model() -> SemanticModel:
    return load_model(EXAMPLE)


@pytest.fixture
def adapter() -> DuckDBAdapter:
    return DuckDBAdapter()


@pytest.fixture(scope="session")
def postgres_model() -> SemanticModel:
    """The Postgres sibling model — same semantics, table sources, `dialect: postgres`."""
    return load_model(EXAMPLE_PG)


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    """The DSN, or a skip naming exactly how to get one.

    Both failure modes skip rather than fail: the variable being unset (a laptop with no
    database) and the variable being set but unreachable (a container that did not come up).
    A red suite in either case would punish someone for the repo's own choice not to bundle a
    database, and `verify.sh` runs this step by default.
    """
    dsn = os.environ.get(DSN_ENV)
    if not dsn:
        pytest.skip(_SKIP_REASON)
    try:
        psycopg.connect(dsn).close()
    except psycopg.Error as exc:
        pytest.skip(f"{DSN_ENV} is set but Postgres is unreachable: {exc}")
    return dsn


@pytest.fixture(scope="session")
def postgres_corpus(postgres_dsn: str) -> Iterator[str]:
    """Load the retail corpus into Postgres once, from the same CSV DuckDB reads.

    Setup writes, so it uses psycopg directly rather than `PostgresAdapter` — the adapter opens
    read-only on purpose, and a test fixture that needed it to be writable would be evidence
    that N5 was not real.
    """
    with psycopg.connect(postgres_dsn) as conn, conn.cursor() as cur:
        cur.execute(_ORDERS_DDL)
        cur.execute(_MISTYPED_DDL)
        with ORDERS_CSV.open(newline="") as handle:
            for row in csv.DictReader(handle):
                cur.execute(
                    "INSERT INTO orders (order_id, order_date, channel, region, amount)"
                    " VALUES (%s, %s, %s, %s, %s)",
                    (
                        row["order_id"],
                        row["order_date"],
                        row["channel"],
                        row["region"],
                        row["amount"],
                    ),
                )
                cur.execute(
                    "INSERT INTO orders_mistyped (order_id, order_date, channel, amount)"
                    " VALUES (%s, %s, %s, %s)",
                    (row["order_id"], row["order_date"], row["channel"], row["amount"]),
                )
        conn.commit()
    yield postgres_dsn


@pytest.fixture
def postgres_adapter(postgres_corpus: str) -> Iterator[PostgresAdapter]:
    """A read-only adapter over the loaded corpus, closed after each test."""
    opened = PostgresAdapter(postgres_corpus)
    try:
        yield opened
    finally:
        opened.close()
