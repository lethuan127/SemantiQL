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

from decimal import Decimal
from pathlib import Path
from typing import Any

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
]

#: `DATE_TRUNC` is deliberately **not** in the list above. It is the one construct the two
#: engines do not agree on, and it gets its own test rather than a quietly relaxed comparison.
#: See `test_date_trunc_buckets_agree_but_postgres_attaches_a_timezone`.
DATE_TRUNC_REQUEST = "SELECT revenue, DATE_TRUNC('month', order_date) FROM orders"

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


def test_date_trunc_buckets_agree_but_postgres_attaches_a_timezone(
    model: SemanticModel,
    postgres_model: SemanticModel,
    adapter: DuckDBAdapter,
    postgres_adapter: PostgresAdapter,
) -> None:
    """The first real divergence the differential suite found. Pinned, not smoothed over.

    The two engines receive **byte-identical SQL** — sqlglot transpiles `DATE_TRUNC('MONTH', x)`
    to itself, so nothing in SemantiQL causes this. Postgres resolves `date_trunc(text, date)`
    to its `timestamptz` overload, so the result carries the **server's** timezone; DuckDB
    returns a naive timestamp:

        DuckDB     2026-07-01 00:00:00
        Postgres   2026-07-01 00:00:00+07:00      (+07:00 = whatever the server is set to)

    What is *not* wrong: no row is misplaced. The column is a `date`, so every value is
    midnight and truncating to month lands on the 1st either way. Revenue per bucket matches
    exactly, which is what the user actually reads. That is why this is a pinned difference
    rather than a blocked release.

    What *is* wrong, and why it needs its own spec: the value depends on a server setting
    SemantiQL never declares, never validates, and the user never sees. Two servers holding the
    same data answer differently. And on a `timestamptz` column — which the model may legally
    declare `type: date` — the same overload would bucket rows near a month boundary by the
    server's timezone, which is a genuinely wrong number rather than a cosmetic one.

    Fixing it means changing how `compile.py` emits the truncation, and spec 010's FR-9 forbids
    touching `engine/` — the whole point of this change is that a second datasource needs no
    core edit. So it is reported as a finding and carried forward, exactly as `plan.md`'s OQ-1
    said a transpile failure would be.

    This test locks in today's behaviour: the buckets and the money must agree, and Postgres is
    expected to be timezone-aware. If either half changes, someone finds out here.
    """
    duck = _answer(DATE_TRUNC_REQUEST, model, adapter)
    post = _answer(DATE_TRUNC_REQUEST, postgres_model, postgres_adapter)

    assert duck.columns == post.columns
    bucket = duck.columns.index("order_date_month")
    revenue = duck.columns.index("revenue")

    # The answer a user sees: which month, and how much. These must match exactly.
    by_month_duck = {row[bucket].date(): _comparable(row[revenue]) for row in duck.rows}
    by_month_post = {row[bucket].date(): _comparable(row[revenue]) for row in post.rows}
    assert by_month_duck == by_month_post

    # The divergence itself, asserted rather than tolerated.
    assert all(row[bucket].tzinfo is None for row in duck.rows), "DuckDB went timezone-aware"
    assert all(row[bucket].tzinfo is not None for row in post.rows), (
        "Postgres stopped attaching a timezone — the finding this test pins may be resolved; "
        "check whether the follow-up spec landed"
    )


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
