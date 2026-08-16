"""Two engines, one model, one answer — or the suite goes red.

This is the N2 control for spec 010. Every other test in this repo asks whether *an* engine is
right; these ask whether the two engines **agree**, which is the failure a non-technical user
cannot possibly catch. A dialect bug that makes Postgres return 1686.24 where DuckDB returns
1686.20 produces no error, no warning, and a wrong figure in someone's deck.

Each request is answered three ways and all three must match:

  1. DuckDB, reading `orders.csv` directly.
  2. Postgres, reading a table loaded from that same CSV.
  3. The hand-computed totals in `tests/test_example_end_to_end.py`, which were worked out from
     the ten rows independently of any engine.

Three matters more than two. Two engines that agree with each other and disagree with the CSV
are both wrong, and a pairwise-only comparison would call that a pass.

Skips, never fails, when no Postgres is reachable — see `postgres_dsn` in `conftest.py`.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest

from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.adapters.postgres import PostgresAdapter
from semantiql.doctor import check, problems
from semantiql.engine.run import Result, run
from semantiql.knowledge.loader import load_model
from semantiql.knowledge.model import SemanticModel

pytestmark = pytest.mark.pg

#: The requests both engines must answer identically. Deliberately spans every construct the
#: compiler can emit — aggregation, GROUP BY, WHERE with each literal type, ORDER BY, LIMIT,
#: DATE_TRUNC, and a derived metric with its guarded divisor — because a transpile bug lives in
#: exactly one of them and nowhere else.
REQUESTS = [
    "SELECT revenue FROM orders",
    "SELECT revenue, channel FROM orders",
    "SELECT order_count, channel FROM orders",
    "SELECT average_order_value, region FROM orders",
    "SELECT revenue FROM orders WHERE channel = 'web'",
    "SELECT revenue FROM orders WHERE channel IN ('web', 'retail')",
    "SELECT revenue FROM orders WHERE region = 'north'",
    "SELECT revenue FROM orders WHERE order_date >= '2026-07-01' AND order_date < '2026-08-01'",
    "SELECT revenue, channel FROM orders ORDER BY revenue DESC",
    "SELECT revenue, channel FROM orders ORDER BY revenue DESC LIMIT 2",
    "SELECT revenue_per_order, channel FROM orders",
    # All five grains, not just month (spec 011, FR-3). Before 011 these disagreed — Postgres
    # returned a timezone-aware value from byte-identical SQL — and `month` was pinned in a
    # separate test recording the divergence. The cast in `compile.py` removed it, so they are
    # ordinary cases again.
    "SELECT revenue, DATE_TRUNC('year', order_date) FROM orders",
    "SELECT revenue, DATE_TRUNC('quarter', order_date) FROM orders",
    "SELECT revenue, DATE_TRUNC('month', order_date) FROM orders",
    "SELECT revenue, DATE_TRUNC('week', order_date) FROM orders",
    "SELECT revenue, DATE_TRUNC('day', order_date) FROM orders",
]

#: Hand-computed from the ten rows of examples/retail/orders.csv, matching the figures in
#: tests/test_example_end_to_end.py. Repeated rather than imported so that changing one file
#: cannot silently move the other's goalposts.
EXPECTED_TOTAL = Decimal("1686.24")
EXPECTED_BY_CHANNEL = {
    "web": Decimal("956.50"),
    "retail": Decimal("344.49"),
    "partner": Decimal("385.25"),
}


def _comparable(value: Any) -> Any:
    """Reduce a cell to what it *means*, so representation differences are not failures.

    DuckDB hands back a `float` where Postgres hands back a `Decimal`, and both are correct.
    Comparing them raw would fail on every monetary column and teach whoever hit it that this
    suite is noise. Comparing them as `Decimal` quantized to the cent compares the *number*,
    which is the only thing the user ever sees — and still fails on a real disagreement, since
    a cent is far finer than any dialect bug worth catching.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float | Decimal):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    return str(value)


def _rows(result: Result) -> set[tuple[Any, ...]]:
    """Row order is not part of the answer unless ORDER BY made it so — see the ordered test."""
    return {tuple(_comparable(v) for v in row) for row in result.rows}


def _answer(sql: str, model: SemanticModel, adapter: Any) -> Result:
    outcome = run(sql, model, adapter)
    assert isinstance(outcome, Result), f"{adapter.dialect} refused {sql!r}: {outcome}"
    return outcome


@pytest.mark.parametrize("sql", REQUESTS)
def test_both_engines_return_the_same_answer(
    sql: str,
    model: SemanticModel,
    postgres_model: SemanticModel,
    adapter: DuckDBAdapter,
    postgres_adapter: PostgresAdapter,
) -> None:
    duck = _answer(sql, model, adapter)
    post = _answer(sql, postgres_model, postgres_adapter)

    assert duck.columns == post.columns, f"column names differ for {sql!r}"
    assert _rows(duck) == _rows(post), f"values differ for {sql!r}"


def test_the_two_engines_emit_different_sql() -> None:
    """The guard on the test above: identical answers only mean something if the SQL differed.

    If both adapters somehow compiled to the same string, every assertion here would pass while
    testing nothing. `LIMIT` is the cheapest tell — DuckDB and Postgres both spell it `LIMIT`,
    so this asserts on the *relation* instead, where DuckDB reads a CSV and Postgres cannot.
    """
    duck = DuckDBAdapter.relation("orders.csv").sql(dialect="duckdb")
    post = PostgresAdapter.relation("orders").sql(dialect="postgres")
    assert duck != post
    assert "READ_CSV_AUTO" in duck.upper()


def test_grains_now_return_the_same_naive_value(
    model: SemanticModel,
    postgres_model: SemanticModel,
    adapter: DuckDBAdapter,
    postgres_adapter: PostgresAdapter,
) -> None:
    """What replaced the pinned divergence (spec 011, FR-9).

    This test used to assert the opposite: that Postgres returned a timezone-aware value where
    DuckDB returned a naive one, from byte-identical SQL. That was pinned rather than fixed
    because fixing it meant changing `compile.py`, which spec 010 had forbidden itself.

    `compile.py` now casts the column before truncating, which stops Postgres reaching for its
    `timestamptz` overload. So the assertion inverts: **both engines must return a naive
    value**, and if either starts carrying a zone again the cast has been lost.
    """
    sql = "SELECT revenue, DATE_TRUNC('month', order_date) FROM orders"
    duck = _answer(sql, model, adapter)
    post = _answer(sql, postgres_model, postgres_adapter)

    bucket = duck.columns.index("order_date_month")
    assert all(row[bucket].tzinfo is None for row in duck.rows), duck.rows
    assert all(row[bucket].tzinfo is None for row in post.rows), (
        "Postgres is timezone-aware again — the CAST in compile.py's _truncand has been lost"
    )
    assert {r[bucket] for r in duck.rows} == {r[bucket] for r in post.rows}


def test_ordering_survives_the_transpile(
    postgres_model: SemanticModel, postgres_adapter: PostgresAdapter
) -> None:
    """`_rows` compares as a set, so ordering needs its own assertion or it is untested."""
    result = _answer(
        "SELECT revenue, channel FROM orders ORDER BY revenue DESC",
        postgres_model,
        postgres_adapter,
    )
    revenue = result.columns.index("revenue")
    values = [Decimal(str(row[revenue])) for row in result.rows]
    assert values == sorted(values, reverse=True)


def test_postgres_agrees_with_the_hand_computed_total(
    postgres_model: SemanticModel, postgres_adapter: PostgresAdapter
) -> None:
    """The third answer. Two engines agreeing on a wrong number is still a wrong number."""
    result = _answer("SELECT revenue FROM orders", postgres_model, postgres_adapter)
    assert _comparable(result.rows[0][0]) == EXPECTED_TOTAL


def test_postgres_agrees_with_the_hand_computed_channels(
    postgres_model: SemanticModel, postgres_adapter: PostgresAdapter
) -> None:
    result = _answer("SELECT revenue, channel FROM orders", postgres_model, postgres_adapter)
    channel = result.columns.index("channel")
    revenue = result.columns.index("revenue")
    got = {str(row[channel]): _comparable(row[revenue]) for row in result.rows}
    assert got == EXPECTED_BY_CHANNEL


def test_the_result_carries_postgres_sql(
    postgres_model: SemanticModel, postgres_adapter: PostgresAdapter
) -> None:
    """A reader checks the work by reading the SQL, so it must be the SQL that actually ran."""
    result = _answer("SELECT revenue, channel FROM orders", postgres_model, postgres_adapter)
    assert "SUM" in result.sql.upper()
    assert "read_csv_auto" not in result.sql


def test_a_model_declaring_the_wrong_engine_is_refused(
    model: SemanticModel, postgres_adapter: PostgresAdapter
) -> None:
    """The check that clarification Q3 kept alive by not inferring the adapter from the model.

    `model` declares `dialect: duckdb`; the adapter is Postgres. Running one engine's SQL on
    another is refused rather than attempted, and — the part that matters — the database is
    never reached.
    """
    outcome = run("SELECT revenue FROM orders", model, postgres_adapter)
    assert not isinstance(outcome, Result)
    assert "duckdb" in str(outcome) and "postgres" in str(outcome)


# --- doctor over Postgres (FR-5). The same three finding kinds the DuckDB run produces.


def test_doctor_finds_nothing_wrong_with_a_correct_model(
    postgres_model: SemanticModel, postgres_adapter: PostgresAdapter
) -> None:
    findings = check(postgres_model, postgres_adapter)
    assert problems(findings) == []


def _broken_model(tmp_path: Path, source: str, date_column: str) -> SemanticModel:
    """A deliberately wrong model, written as YAML and read by the real loader.

    Built as a file rather than by mutating a loaded model, because `SemanticModel` is frozen —
    and that is a feature, not an obstacle: nothing should be able to edit the source of truth
    at runtime (N3). Going through `load_model` also means these fixtures are exactly as valid
    as any model a user would write.
    """
    path = tmp_path / "broken.yml"
    path.write_text(
        "version: 1\n"
        "datasource:\n"
        "  name: retail\n"
        "  dialect: postgres\n"
        "tables:\n"
        "  orders:\n"
        f"    source: {source}\n"
        "    dimensions:\n"
        "      channel:\n"
        "        column: channel\n"
        "        type: string\n"
        "      order_date:\n"
        f"        column: {date_column}\n"
        "        type: date\n"
        "    measures:\n"
        "      revenue:\n"
        "        column: amount\n"
        "        agg: sum\n"
    )
    return load_model(path)


def test_doctor_reports_a_missing_column(tmp_path: Path, postgres_adapter: PostgresAdapter) -> None:
    """A typo'd column name is found before a query hits it."""
    broken = _broken_model(tmp_path, source="orders", date_column="order_dat")
    reported = " ".join(str(f) for f in problems(check(broken, postgres_adapter)))
    assert "order_dat" in reported


def test_doctor_reports_a_declared_type_that_the_column_contradicts(
    tmp_path: Path, postgres_adapter: PostgresAdapter
) -> None:
    """The finding that only exists because the adapter translates Postgres's spelling.

    The column is `text`; the model says `date`. Doctor never learns the word `text` — the
    adapter reports `kind="string"` and the comparison happens in the model's own vocabulary,
    which is the translation N4 assigns to the adapter.
    """
    broken = _broken_model(tmp_path, source="orders_mistyped", date_column="order_date")
    reported = " ".join(str(f) for f in problems(check(broken, postgres_adapter)))
    assert "order_date" in reported
    assert "text" in reported


def test_doctor_reports_an_aggregation_over_a_non_numeric_column(
    tmp_path: Path, postgres_adapter: PostgresAdapter
) -> None:
    """`SUM` over a text column: Postgres would reject it, so doctor says so first."""
    broken = _broken_model(tmp_path, source="orders_mistyped", date_column="order_date")
    reported = " ".join(str(f) for f in problems(check(broken, postgres_adapter)))
    assert "revenue" in reported


def test_a_csv_source_is_refused_rather_than_missing(
    postgres_adapter: PostgresAdapter, model: SemanticModel
) -> None:
    """FR-13 end to end: the message names the file source, not a missing relation."""
    from semantiql.adapters.base import AdapterError

    with pytest.raises(AdapterError) as caught:
        postgres_adapter.columns(model.tables["orders"].source)
    assert "file source" in str(caught.value)
    assert "does not exist" not in str(caught.value)


def test_a_write_is_rejected_by_the_server(postgres_adapter: PostgresAdapter) -> None:
    """N5, enforced by Postgres rather than only by `validate` refusing non-SELECTs.

    This is the one place the read-only guarantee is stronger than DuckDB's, so it gets a test
    that goes all the way to the server instead of trusting the flag was set.

    It also guards a trap worth stating: `read_only` sets *transaction* characteristics, so on
    an `autocommit=True` connection it is silently ignored and this write would succeed. That
    was measured while building the adapter, and a future "let's avoid idle-in-transaction by
    turning on autocommit" would reintroduce it. This test is what says no.

    `execute` is called directly on purpose — the only place in the suite that does. `run`
    would refuse a non-SELECT long before the adapter saw it, which is the wrong layer to be
    testing here.
    """
    from semantiql.adapters.base import AdapterError

    with pytest.raises(AdapterError) as caught:
        postgres_adapter.execute("CREATE TABLE semantiql_should_never_exist (x int)")
    assert "read-only" in str(caught.value)


# --- The server-timezone sweep (spec 011, AD-6).


_ZONED_MODEL = """
version: 1
datasource: {name: t, dialect: postgres}
tables:
  events:
    source: events
    dimensions:
      happened_at: {column: happened_at, type: date%s}
    measures:
      n: {column: happened_at, agg: count}
"""


def _dsn_in(dsn: str, timezone: str) -> str:
    """The same DSN, with the session timezone set through libpq's own `options`.

    Deliberately not `adapter.execute("SET TIME ZONE …")`. `execute` is documented as taking
    already-validated SQL, and `validate` refuses every non-SELECT — a test that reaches around
    that to issue a `SET` would be the first caller in the repo to treat the adapter as a
    general SQL pipe, which is exactly the shortcut `run` exists to prevent. Putting it in the
    connection string means the adapter opens already in that timezone and nothing is bypassed.
    """
    separator = "&" if "?" in dsn else "?"
    return f"{dsn}{separator}options=-c%20timezone%3D{quote(timezone)}"


@pytest.fixture
def zoned_events(postgres_dsn: str) -> Iterator[str]:
    """One row two hours past a UTC month boundary — the row a westward server misfiles."""
    import psycopg

    with psycopg.connect(postgres_dsn) as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS events")
        cur.execute("CREATE TABLE events (happened_at timestamptz)")
        cur.execute("INSERT INTO events VALUES ('2026-07-01T02:00:00+00')")
        conn.commit()
    yield postgres_dsn


@pytest.mark.parametrize("server_timezone", ["UTC", "America/Chicago", "Asia/Tokyo"])
def test_a_declared_zone_survives_the_servers_own_timezone(
    tmp_path: Path, zoned_events: str, server_timezone: str
) -> None:
    """**The only test in this repo that can catch this class of fault.**

    Every other control here compares two engines, and this fault is invisible to that: DuckDB
    and Postgres bucket a timezone-carrying column identically, and both bucket it in the
    *session's* timezone. They agree, and they are both wrong. What varies is not the engine,
    it is the machine — so this varies the machine.

    Without the declared zone the bucket moves to June on a server in `America/Chicago`. With
    it, all three servers answer July, because the model said which zone the month belongs to.
    """
    path = tmp_path / "zoned.yml"
    path.write_text(_ZONED_MODEL % ", timezone: UTC")
    model = load_model(path)

    adapter = PostgresAdapter(_dsn_in(zoned_events, server_timezone))
    try:
        result = _answer("SELECT n, DATE_TRUNC('month', happened_at) FROM events", model, adapter)
    finally:
        adapter.close()

    bucket = result.columns.index("happened_at_month")
    assert str(result.rows[0][bucket])[:10] == "2026-07-01", (
        f"the month boundary moved on a server set to {server_timezone} — "
        "the declared zone is not reaching the SQL"
    )


def test_without_a_declaration_the_bucket_is_at_the_servers_mercy(
    tmp_path: Path, zoned_events: str
) -> None:
    """The fault itself, asserted — so the sweep above is measuring something real.

    A test that only proves the fix works can pass on a database where the fault never
    reproduced. This reproduces it: same row, same grain, no `timezone:`, and the bucket lands
    in a different month depending on nothing but the server's configuration.

    It is `doctor`'s job to stop a model reaching this state (spec 011, AD-3), and this is what
    doctor is protecting against.
    """
    path = tmp_path / "naive.yml"
    path.write_text(_ZONED_MODEL % "")
    model = load_model(path)

    seen = set()
    for server_timezone in ("UTC", "America/Chicago"):
        adapter = PostgresAdapter(_dsn_in(zoned_events, server_timezone))
        try:
            result = _answer(
                "SELECT n, DATE_TRUNC('month', happened_at) FROM events", model, adapter
            )
        finally:
            adapter.close()
        seen.add(str(result.rows[0][result.columns.index("happened_at_month")])[:10])

    assert seen == {"2026-07-01", "2026-06-01"}, (
        f"expected the bucket to move with the server timezone, got {seen} — if this stops "
        "reproducing, the sweep above no longer proves the declared zone is doing the work"
    )
