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


# --- Metrics (spec 006). Each ratio is computed from the corpus independently, because the
# failure this guards against — a ratio taken at the wrong grain — produces a plausible
# number rather than an error.

EXPECTED_RATIO_BY_CHANNEL = {"web": 191.30, "retail": 114.83, "partner": 192.625}


def test_a_metric_is_computed_per_group(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    """Each channel's own revenue over its own count — not an average of row-level ratios."""
    result = _result("SELECT revenue_per_order, channel FROM orders", model, adapter)
    channel = result.columns.index("channel")
    ratio = result.columns.index("revenue_per_order")
    got = {str(row[channel]): round(float(row[ratio]), 4) for row in result.rows}
    assert got == EXPECTED_RATIO_BY_CHANNEL


def test_a_metric_agrees_with_its_parts(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    """The definition is revenue / order_count, so the answer must equal exactly that."""
    parts = _result("SELECT revenue, order_count FROM orders", model, adapter).rows[0]
    ratio = _result("SELECT revenue_per_order FROM orders", model, adapter).rows[0][0]
    assert round(float(ratio), 6) == round(float(parts[0]) / float(parts[1]), 6)


def test_an_empty_denominator_yields_no_value_not_infinity(
    model: SemanticModel, adapter: DuckDBAdapter
) -> None:
    """Unguarded, DuckDB would answer `inf` here and Postgres would raise (spec 006, Q2)."""
    result = _result(
        "SELECT revenue_per_order FROM orders WHERE channel = 'nothing at all'", model, adapter
    )
    assert result.rows[0][0] is None


def test_a_metric_can_be_ordered_by(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    result = _result(
        "SELECT revenue_per_order, channel FROM orders ORDER BY revenue_per_order DESC LIMIT 1",
        model,
        adapter,
    )
    assert result.rows[0][result.columns.index("channel")] == "partner"


def test_a_monthly_grain_splits_the_corpus(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    """July 1491.74 and August 194.50, computed from the ten rows independently."""
    result = _result("SELECT revenue, DATE_TRUNC('month', order_date) FROM orders", model, adapter)
    month = result.columns.index("order_date_month")
    revenue = result.columns.index("revenue")
    got = {str(row[month])[:7]: round(float(row[revenue]), 2) for row in result.rows}
    assert got == {"2026-07": 1491.74, "2026-08": 194.50}


def test_a_yearly_grain_keeps_the_total(model: SemanticModel, adapter: DuckDBAdapter) -> None:
    """Every row is 2026, so the yearly grain must reproduce the grand total exactly."""
    result = _result("SELECT revenue, DATE_TRUNC('year', order_date) FROM orders", model, adapter)
    assert len(result.rows) == 1
    assert round(float(result.rows[0][result.columns.index("revenue")]), 2) == 1686.24
