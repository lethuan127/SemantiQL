"""Every answer, asked twice: once through the engine, once in hand-written SQL.

A pinned figure at this scale is a number someone read out of the engine's own output, which
makes it a test against *change* rather than a test of correctness. The physical SQL below is
an independent statement of the same question, so a mistranslation fails the first time it
runs rather than the first time it changes.

A few grand totals are pinned as well, because a differential test passes when both sides are
wrong in the same way — a corpus that silently changed shape would slip through otherwise.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import duckdb
import pytest

from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.engine.run import Result, run
from semantiql.knowledge.model import SemanticModel

pytestmark = pytest.mark.e2e


def _rows(value: Any) -> list[tuple[Any, ...]]:
    """Normalise for comparison: DECIMAL and float are the same number here."""
    out = []
    for row in value:
        out.append(tuple(round(float(v), 6) if isinstance(v, Decimal | float) else v for v in row))
    return out


#: (semantic SQL, the same question written by hand against the physical view).
CASES: list[tuple[str, str]] = [
    # One measure, no grouping.
    (
        "SELECT net_revenue FROM sales",
        "SELECT SUM(net_amount) FROM sales",
    ),
    # Every aggregation the model can express.
    (
        "SELECT net_revenue, line_count, order_count, customer_count, average_quantity,"
        " first_order_date, last_order_date FROM sales",
        "SELECT SUM(net_amount), COUNT(order_id), COUNT(DISTINCT order_id),"
        " COUNT(DISTINCT customer_id), AVG(quantity), MIN(order_date), MAX(order_date)"
        " FROM sales",
    ),
    # Grouping by one dimension, then two.
    (
        "SELECT net_revenue, segment FROM sales ORDER BY segment",
        "SELECT SUM(net_amount), segment FROM sales GROUP BY segment ORDER BY segment",
    ),
    (
        "SELECT net_revenue, region, ship_mode FROM sales ORDER BY region, ship_mode",
        "SELECT SUM(net_amount), region, ship_mode FROM sales GROUP BY region, ship_mode"
        " ORDER BY region, ship_mode",
    ),
    # Filters: equality, IN, negation, range, LIKE, and a conjunction of them.
    (
        "SELECT net_revenue FROM sales WHERE region = 'EUROPE'",
        "SELECT SUM(net_amount) FROM sales WHERE region = 'EUROPE'",
    ),
    (
        "SELECT net_revenue, segment FROM sales WHERE segment IN ('BUILDING', 'MACHINERY')"
        " ORDER BY segment",
        "SELECT SUM(net_amount), segment FROM sales"
        " WHERE segment IN ('BUILDING', 'MACHINERY') GROUP BY segment ORDER BY segment",
    ),
    (
        "SELECT net_revenue FROM sales WHERE return_flag <> 'R'",
        "SELECT SUM(net_amount) FROM sales WHERE return_flag <> 'R'",
    ),
    (
        "SELECT net_revenue FROM sales WHERE ship_mode NOT LIKE 'AIR%'",
        "SELECT SUM(net_amount) FROM sales WHERE ship_mode NOT LIKE 'AIR%'",
    ),
    (
        "SELECT net_revenue, order_count FROM sales"
        " WHERE order_date >= '1995-01-01' AND order_date < '1996-01-01'",
        "SELECT SUM(net_amount), COUNT(DISTINCT order_id) FROM sales"
        " WHERE order_date >= DATE '1995-01-01' AND order_date < DATE '1996-01-01'",
    ),
    (
        "SELECT net_revenue FROM sales WHERE order_date BETWEEN '1994-01-01' AND '1994-12-31'"
        " AND region = 'ASIA' AND segment = 'AUTOMOBILE'",
        "SELECT SUM(net_amount) FROM sales"
        " WHERE order_date BETWEEN DATE '1994-01-01' AND DATE '1994-12-31'"
        " AND region = 'ASIA' AND segment = 'AUTOMOBILE'",
    ),
    # Time grains — the corpus spans seven years, so these actually mean something.
    (
        "SELECT net_revenue, DATE_TRUNC('year', order_date) FROM sales ORDER BY order_date_year",
        "SELECT SUM(net_amount), DATE_TRUNC('year', order_date) AS y FROM sales"
        " GROUP BY DATE_TRUNC('year', order_date) ORDER BY y",
    ),
    (
        "SELECT net_revenue, DATE_TRUNC('quarter', order_date) FROM sales"
        " WHERE order_date < '1993-01-01' ORDER BY order_date_quarter",
        "SELECT SUM(net_amount), DATE_TRUNC('quarter', order_date) AS q FROM sales"
        " WHERE order_date < DATE '1993-01-01' GROUP BY DATE_TRUNC('quarter', order_date)"
        " ORDER BY q",
    ),
    # Metrics — a ratio computed after grouping, and a difference.
    (
        "SELECT revenue_per_order, segment FROM sales ORDER BY segment",
        "SELECT SUM(net_amount) / NULLIF(COUNT(DISTINCT order_id), 0), segment FROM sales"
        " GROUP BY segment ORDER BY segment",
    ),
    (
        "SELECT discount_given, region FROM sales ORDER BY region",
        "SELECT SUM(gross_amount) - SUM(net_amount), region FROM sales"
        " GROUP BY region ORDER BY region",
    ),
    # Ordering and limits.
    (
        "SELECT net_revenue, nation FROM sales ORDER BY net_revenue DESC LIMIT 5",
        "SELECT SUM(net_amount) AS r, nation FROM sales GROUP BY nation ORDER BY r DESC LIMIT 5",
    ),
    (
        "SELECT net_revenue, nation FROM sales ORDER BY net_revenue DESC LIMIT 3 OFFSET 2",
        "SELECT SUM(net_amount) AS r, nation FROM sales GROUP BY nation ORDER BY r DESC"
        " LIMIT 3 OFFSET 2",
    ),
    # Everything at once: filter, grain, metric, several measures, order and limit.
    (
        "SELECT revenue_per_order, net_revenue, order_count,"
        " DATE_TRUNC('month', order_date) AS month FROM sales"
        " WHERE region = 'AMERICA' AND segment <> 'FURNITURE'"
        " AND order_date >= '1994-01-01' AND order_date < '1994-07-01'"
        " ORDER BY month LIMIT 4",
        "SELECT SUM(net_amount) / NULLIF(COUNT(DISTINCT order_id), 0), SUM(net_amount),"
        " COUNT(DISTINCT order_id), DATE_TRUNC('month', order_date) AS m FROM sales"
        " WHERE region = 'AMERICA' AND segment <> 'FURNITURE'"
        " AND order_date >= DATE '1994-01-01' AND order_date < DATE '1994-07-01'"
        " GROUP BY DATE_TRUNC('month', order_date) ORDER BY m LIMIT 4",
    ),
]


@pytest.mark.parametrize(("semantic", "physical"), CASES, ids=range(len(CASES)))
def test_the_engine_agrees_with_hand_written_sql(
    semantic: str,
    physical: str,
    e2e_model: SemanticModel,
    e2e_adapter: DuckDBAdapter,
    oracle: duckdb.DuckDBPyConnection,
) -> None:
    outcome = run(semantic, e2e_model, e2e_adapter)
    assert isinstance(outcome, Result), outcome
    expected = oracle.execute(physical).fetchall()
    assert _rows(outcome.rows) == _rows(expected), (
        f"semantic: {semantic}\nphysical: {physical}\nengine SQL: {outcome.sql}"
    )


def test_the_corpus_is_the_shape_the_cases_assume(
    oracle: duckdb.DuckDBPyConnection,
) -> None:
    """A differential test passes when both sides are wrong together — this pins the corpus.

    Only shape, not sums: the row count and date span are fixed by the scale factor, while the
    figures move with it, and the suite must stay honest at any scale.
    """
    shape = oracle.execute(
        "SELECT COUNT(*), MIN(order_date), MAX(order_date), COUNT(DISTINCT nation) FROM sales"
    ).fetchone()
    assert shape is not None
    rows, first, last, nations = shape
    assert rows > 50_000, f"corpus unexpectedly small: {rows}"
    assert first.year == 1992 and last.year == 1998, (first, last)
    assert nations == 25


def test_a_limit_actually_bounds_a_large_result(
    e2e_model: SemanticModel, e2e_adapter: DuckDBAdapter
) -> None:
    """On ten rows a LIMIT is indistinguishable from no limit. Here it is not."""
    unbounded = run("SELECT net_revenue, order_date FROM sales", e2e_model, e2e_adapter)
    bounded = run(
        "SELECT net_revenue, order_date FROM sales ORDER BY order_date LIMIT 10",
        e2e_model,
        e2e_adapter,
    )
    assert isinstance(unbounded, Result) and isinstance(bounded, Result)
    assert len(unbounded.rows) > 2000, len(unbounded.rows)
    assert len(bounded.rows) == 10
