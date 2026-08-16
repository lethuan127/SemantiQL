"""The same questions, at TPC-H scale, on both engines — and they must agree.

`tests/test_postgres_differential.py` already compares the two engines on ten rows. Ten rows
cannot contain the faults this suite exists for: a wrong `GROUP BY` that only shows up across
many groups, a date predicate that only breaks across several years, an aggregation that only
loses precision at scale. Those are exactly the places two dialects drift apart.

So this is the ten-row differential suite's argument applied to the corpus that can actually
hold a counterexample: every case is answered by DuckDB over the generated TPC-H corpus and by
Postgres over a copy of that same corpus, and the two must match.

**What this suite does not do**, stated so nobody reads more into a green run than is there: it
compares the engines to each other, not to an independent oracle. Two engines wrong the same way
would pass. `test_differential.py` in this same package is what supplies the independent answer,
checking the engine against hand-written physical SQL — these two suites are worth something
together and much less apart.

Two skips, and they are kept distinguishable on purpose: no `dbgen` means no corpus at all, and
no `SEMANTIQL_TEST_DSN` means no Postgres to copy it into. Spec 010 declined to build this suite
partly because two silences are how a suite quietly stops running; the answer is that each skip
names itself rather than that the suite does not exist.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.adapters.postgres import PostgresAdapter
from semantiql.engine.run import Result, run
from semantiql.knowledge.model import SemanticModel

pytestmark = [pytest.mark.e2e, pytest.mark.pg]

#: Semantic SQL both engines must answer identically. Chosen for the things that only appear at
#: scale: many groups, a multi-year date range, ordering over a large result, and a metric whose
#: divisor varies per group.
CASES = [
    "SELECT net_revenue FROM sales",
    "SELECT order_count FROM sales",
    "SELECT net_revenue, region FROM sales",
    "SELECT net_revenue, nation FROM sales",
    "SELECT net_revenue, segment, region FROM sales",
    "SELECT net_revenue, ship_mode FROM sales",
    "SELECT line_count, order_count, return_flag FROM sales",
    "SELECT customer_count, region FROM sales",
    "SELECT average_quantity, segment FROM sales",
    "SELECT first_order_date, last_order_date FROM sales",
    "SELECT net_revenue FROM sales WHERE region = 'EUROPE'",
    "SELECT net_revenue FROM sales WHERE order_date >= '1995-01-01' AND order_date < '1996-01-01'",
    "SELECT net_revenue, region FROM sales WHERE segment IN ('BUILDING', 'MACHINERY')",
    "SELECT net_revenue, nation FROM sales ORDER BY net_revenue DESC LIMIT 10",
    "SELECT revenue_per_order, region FROM sales",
    # Grains. These were `xfail(strict=True)` when this suite was written: Postgres returned a
    # timezone-aware value from byte-identical SQL, so the two engines disagreed. Spec 011 put
    # a cast in `compile.py`, the strict xfail turned into a hard failure exactly as designed,
    # and the cases moved here.
    "SELECT net_revenue, DATE_TRUNC('year', order_date) FROM sales",
    "SELECT net_revenue, DATE_TRUNC('quarter', order_date) FROM sales",
    "SELECT net_revenue, DATE_TRUNC('month', order_date) FROM sales",
]

#: The edge table's cases: nulls, a boolean, and a group whose metric divisor is zero. These are
#: where two engines are most entitled to disagree, so they are asked explicitly.
EDGE_CASES = [
    "SELECT total, label FROM edge",
    "SELECT row_count, label_count, distinct_labels FROM edge",
    "SELECT amount_per_refund, label FROM edge",
    "SELECT total FROM edge WHERE flagged = true",
    "SELECT total FROM edge WHERE label <> 'busy'",
]


def _cell(value: Any) -> Any:
    """Compare what a number *means*, not how each driver spells it.

    DuckDB returns `float` where Postgres returns `Decimal`, and both are right. Rounding to six
    places compares the value while staying far finer than any dialect fault worth catching — a
    real disagreement at TPC-H scale is pennies at minimum, usually whole rows.

    `None` stays `None`: a null that became a zero is precisely the kind of drift this suite is
    looking for, so it must never compare equal to one.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float | Decimal):
        return round(float(value), 6)
    return str(value)


def _answer(sql: str, model: SemanticModel, adapter: Any) -> Result:
    outcome = run(sql, model, adapter)
    assert isinstance(outcome, Result), f"{adapter.dialect} refused {sql!r}: {outcome}"
    return outcome


def _sort_key(row: tuple[Any, ...]) -> tuple[tuple[int, str], ...]:
    """Order rows for comparison without letting a NULL crash the sort.

    Neither engine promises row order without `ORDER BY`, so the rows have to be sorted before
    they can be compared — and the edge table exists precisely because it contains nulls, which
    Python refuses to order against numbers. Sorting on `(is_not_null, repr)` keeps nulls
    together and is total over mixed types, while leaving `_cell` to decide equality.
    """
    return tuple((0, "") if v is None else (1, str(v)) for v in row)


def _compare(sql: str, duck: Result, post: Result) -> None:
    assert duck.columns == post.columns, f"column names differ for {sql!r}"

    duck_rows = sorted((tuple(_cell(v) for v in row) for row in duck.rows), key=_sort_key)
    post_rows = sorted((tuple(_cell(v) for v in row) for row in post.rows), key=_sort_key)

    assert len(duck_rows) == len(post_rows), (
        f"row count differs for {sql!r}: duckdb {len(duck_rows)}, postgres {len(post_rows)}"
    )
    assert duck_rows == post_rows, f"values differ for {sql!r}"


@pytest.mark.parametrize("sql", CASES)
def test_both_engines_agree_at_scale(
    sql: str,
    e2e_model: SemanticModel,
    pg_e2e_model: SemanticModel,
    e2e_adapter: DuckDBAdapter,
    pg_e2e_adapter: PostgresAdapter,
) -> None:
    _compare(sql, _answer(sql, e2e_model, e2e_adapter), _answer(sql, pg_e2e_model, pg_e2e_adapter))


@pytest.mark.parametrize("sql", EDGE_CASES)
def test_both_engines_agree_on_the_edge_cases(
    sql: str,
    e2e_model: SemanticModel,
    pg_e2e_model: SemanticModel,
    e2e_adapter: DuckDBAdapter,
    pg_e2e_adapter: PostgresAdapter,
) -> None:
    """Nulls, booleans and a zero divisor — TPC-H contains none of them."""
    _compare(sql, _answer(sql, e2e_model, e2e_adapter), _answer(sql, pg_e2e_model, pg_e2e_adapter))


def test_the_corpora_are_the_same_size(
    e2e_model: SemanticModel,
    pg_e2e_model: SemanticModel,
    e2e_adapter: DuckDBAdapter,
    pg_e2e_adapter: PostgresAdapter,
) -> None:
    """The guard under every comparison above.

    Two engines agreeing on a total means nothing if one of them holds fewer rows, and a
    truncated `COPY` is a plausible failure that would otherwise read as "the engine is fine".
    `pg_corpus` asserts this at load time; stating it as a test puts the assumption where a
    reader of the suite will actually see it.
    """
    for sql in ("SELECT line_count FROM sales", "SELECT row_count FROM edge"):
        duck = _answer(sql, e2e_model, e2e_adapter)
        post = _answer(sql, pg_e2e_model, pg_e2e_adapter)
        assert duck.rows[0][0] == post.rows[0][0], f"corpora differ in size: {sql!r}"
        assert duck.rows[0][0] > 0, "the corpus is empty, so nothing below proves anything"
