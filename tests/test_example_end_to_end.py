"""FR-4 — the example produces a correct answer, checked against hand computation.

Expected values were computed independently from examples/retail/orders.csv:

    web      956.50 over 5 orders
    retail   344.49 over 3 orders
    partner  385.25 over 2 orders
    total   1686.24 over 10 orders

A test asserting "some number came back" would pass while the number was wrong, which is
precisely the failure this project exists to prevent.
"""

from __future__ import annotations

from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.engine.run import Result, run
from semantiql.knowledge.model import SemanticModel

EXPECTED_BY_CHANNEL = {"web": 956.50, "retail": 344.49, "partner": 385.25}


def _result(sql: str, model: SemanticModel, adapter: DuckDBAdapter) -> Result:
    outcome = run(sql, model, adapter)
    assert isinstance(outcome, Result), outcome
    return outcome


def test_total_revenue_is_correct(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    result = _result("SELECT revenue FROM orders", model, adapter)
    assert result.rows[0][0] == round(sum(EXPECTED_BY_CHANNEL.values()), 2)


def test_revenue_by_channel_is_correct(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    result = _result("SELECT revenue, channel FROM orders", model, adapter)
    channel_i = result.columns.index("channel")
    revenue_i = result.columns.index("revenue")
    got = {str(row[channel_i]): round(float(row[revenue_i]), 2) for row in result.rows}
    assert got == EXPECTED_BY_CHANNEL


def test_order_count_by_channel_is_correct(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    result = _result("SELECT order_count, channel FROM orders", model, adapter)
    channel_i = result.columns.index("channel")
    count_i = result.columns.index("order_count")
    got = {row[channel_i]: row[count_i] for row in result.rows}
    assert got == {"web": 5, "retail": 3, "partner": 2}


def test_result_carries_the_sql_it_ran(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    """A reader must be able to check the work, so the physical SQL comes back too."""
    result = _result("SELECT revenue, channel FROM orders", model, adapter)
    assert "SUM" in result.sql.upper()
    assert "GROUP BY" in result.sql.upper()
