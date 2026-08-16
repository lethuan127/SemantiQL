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

import pytest

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


# --- Filtered answers (spec 004). Each expected figure was computed from the ten rows of
# examples/retail/orders.csv independently of the engine, so a filter that silently widened
# or narrowed the population fails here rather than looking plausible.

EXPECTED_FILTERED = {
    "SELECT revenue FROM orders WHERE channel = 'web'": 956.50,
    "SELECT revenue FROM orders WHERE order_date >= '2026-07-01' "
    "AND order_date < '2026-08-01'": 1491.74,
    "SELECT revenue FROM orders WHERE channel = 'web' AND order_date < '2026-08-01'": 826.50,
    "SELECT revenue FROM orders WHERE channel IN ('web', 'retail')": 1300.99,
    "SELECT revenue FROM orders WHERE region = 'north'": 690.74,
}


@pytest.mark.parametrize(("sql", "expected"), sorted(EXPECTED_FILTERED.items()))
def test_a_filtered_total_is_correct(
    sql: str, expected: float, model: SemanticModel, adapter: DuckDBAdapter
) -> None:
    result = _result(sql, model, adapter)
    assert round(float(result.rows[0][0]), 2) == expected


def test_a_negated_filter_excludes_rather_than_includes(
    model: SemanticModel, adapter: DuckDBAdapter
) -> None:
    """The inversion hazard, checked against arithmetic rather than against rendered SQL."""
    everything = _result("SELECT revenue FROM orders", model, adapter).rows[0][0]
    web = _result("SELECT revenue FROM orders WHERE channel = 'web'", model, adapter).rows[0][0]
    not_web = _result("SELECT revenue FROM orders WHERE channel <> 'web'", model, adapter).rows[0][
        0
    ]
    assert round(float(web) + float(not_web), 2) == round(float(everything), 2)
    assert round(float(not_web), 2) == 729.74


def test_a_filter_does_not_add_a_grouping(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    """Filtering on a dimension narrows the rows; only selecting one groups by it."""
    result = _result("SELECT revenue FROM orders WHERE channel = 'web'", model, adapter)
    assert result.columns == ["revenue"]
    assert len(result.rows) == 1


def test_ordering_ranks_the_answer(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    """Revenue by channel, ranked: web 956.50 > partner 385.25 > retail 344.49."""
    result = _result("SELECT revenue, channel FROM orders ORDER BY revenue DESC", model, adapter)
    channel = result.columns.index("channel")
    assert [row[channel] for row in result.rows] == ["web", "partner", "retail"]


def test_ascending_is_the_reverse_ranking(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    """A dropped DESC would look like a plausible answer, so assert the opposite order too."""
    result = _result("SELECT revenue, channel FROM orders ORDER BY revenue", model, adapter)
    channel = result.columns.index("channel")
    assert [row[channel] for row in result.rows] == ["retail", "partner", "web"]


def test_limit_bounds_the_answer(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    result = _result(
        "SELECT revenue, channel FROM orders ORDER BY revenue DESC LIMIT 1", model, adapter
    )
    assert len(result.rows) == 1
    assert result.rows[0][result.columns.index("channel")] == "web"


def test_offset_skips_the_top(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    result = _result(
        "SELECT revenue, channel FROM orders ORDER BY revenue DESC LIMIT 1 OFFSET 1",
        model,
        adapter,
    )
    assert result.rows[0][result.columns.index("channel")] == "partner"
