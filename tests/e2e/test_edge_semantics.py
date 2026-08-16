"""What the large corpus provably cannot test, and the guarantee only a file can show.

A probe of the denormalised TPC-H view found zero nulls and no boolean column, so on its own
it exercises the easy half: every count agrees, no `<>` drops a row, and no divisor is ever
missing. The `edge` table exists for the other half — the traps `docs/09-data-modeling.md`
warns about — and for N5's file-backed read-only path, which the in-memory CLI cannot
demonstrate and nothing else in the repo tests.

Its six rows:

    label   flagged  amount  refunds
    busy    true     100.00  2
    busy    false     50.00  1
    busy    true      25.00  NULL
    quiet   true      10.00  NULL
    quiet   false      5.00  NULL
    NULL    NULL       1.00  NULL
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from semantiql.adapters.base import AdapterError
from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.engine.run import Result, run
from semantiql.knowledge.model import SemanticModel

pytestmark = pytest.mark.e2e


def _one(sql: str, model: SemanticModel, adapter: DuckDBAdapter) -> Result:
    outcome = run(sql, model, adapter)
    assert isinstance(outcome, Result), outcome
    return outcome


def test_count_ignores_nulls_and_count_distinct_ignores_them_too(
    e2e_model: SemanticModel, e2e_adapter: DuckDBAdapter
) -> None:
    """The trap the docs name: `count` counts non-null values, not rows."""
    result = _one(
        "SELECT row_count, label_count, distinct_labels FROM edge", e2e_model, e2e_adapter
    )
    rows, labels, distinct = result.rows[0]
    assert rows == 6, "amount is never null, so this is the row count"
    assert labels == 5, "one label is null, so count sees five"
    assert distinct == 2, "busy and quiet — nulls are not a value"


def test_a_negated_filter_drops_null_rows(
    e2e_model: SemanticModel, e2e_adapter: DuckDBAdapter
) -> None:
    """`<> 'busy'` excludes the null-labelled row as well, exactly as SQL specifies.

    The engine applies what was written rather than second-guessing it, and the documentation
    teaches the rule. This asserts the behaviour the docs promise.
    """
    everything = _one("SELECT row_count FROM edge", e2e_model, e2e_adapter).rows[0][0]
    busy = _one("SELECT row_count FROM edge WHERE label = 'busy'", e2e_model, e2e_adapter)
    not_busy = _one("SELECT row_count FROM edge WHERE label <> 'busy'", e2e_model, e2e_adapter)
    assert everything == 6
    assert busy.rows[0][0] == 3
    assert not_busy.rows[0][0] == 2, "the null-labelled row matches neither side"
    assert busy.rows[0][0] + not_busy.rows[0][0] < everything


def test_a_boolean_dimension_groups_and_filters(
    e2e_model: SemanticModel, e2e_adapter: DuckDBAdapter
) -> None:
    result = _one("SELECT total FROM edge WHERE flagged = TRUE", e2e_model, e2e_adapter)
    assert float(result.rows[0][0]) == 135.00


def test_a_metric_with_no_divisor_reports_no_value(
    e2e_model: SemanticModel, e2e_adapter: DuckDBAdapter
) -> None:
    """Every quiet row has a null refund count, so the divisor is missing entirely.

    Unguarded this is where DuckDB would answer `inf` and Postgres would raise. The guard makes
    both report nothing, which is the honest answer.
    """
    result = _one(
        "SELECT amount_per_refund, label FROM edge WHERE label = 'quiet'",
        e2e_model,
        e2e_adapter,
    )
    assert result.rows[0][0] is None


def test_a_metric_with_a_divisor_still_divides(
    e2e_model: SemanticModel, e2e_adapter: DuckDBAdapter
) -> None:
    """The guard must not turn every ratio into nothing."""
    result = _one(
        "SELECT amount_per_refund, label FROM edge WHERE label = 'busy'",
        e2e_model,
        e2e_adapter,
    )
    assert round(float(result.rows[0][0]), 4) == round(175.00 / 3, 4)


def test_the_file_backed_connection_is_read_only(corpus: Path) -> None:
    """N5, on the path where the connection enforces it rather than validation.

    The CLI's default is in-memory, and DuckDB refuses to open an in-memory database read-only,
    so this guarantee has never had a test. Here the adapter opens a file, and DuckDB itself
    rejects the write — before `validate` would have.
    """
    adapter = DuckDBAdapter(str(corpus))
    try:
        with pytest.raises(AdapterError) as exc:
            adapter.execute("CREATE TABLE intruder (a INTEGER)")
        assert "read-only" in str(exc.value).lower() or "cannot execute" in str(exc.value).lower()
    finally:
        adapter.close()


def test_the_adapter_can_introspect_the_corpus(corpus: Path) -> None:
    """`Adapter.columns` has no caller in the engine yet; this keeps it honest until it does."""
    adapter = DuckDBAdapter(str(corpus))
    try:
        assert adapter.columns("edge") == ["label", "flagged", "amount", "refunds"]
    finally:
        adapter.close()


def test_the_oracle_and_the_engine_agree_on_the_edge_table(
    e2e_model: SemanticModel, e2e_adapter: DuckDBAdapter, oracle: duckdb.DuckDBPyConnection
) -> None:
    engine = _one(
        "SELECT total, label_count, label FROM edge ORDER BY label", e2e_model, e2e_adapter
    )
    expected = oracle.execute(
        "SELECT SUM(amount), COUNT(label), label FROM edge GROUP BY label ORDER BY label"
    ).fetchall()
    assert [
        tuple(float(v) if isinstance(v, (int, float)) else v for v in r) for r in engine.rows
    ] == [tuple(float(v) if isinstance(v, (int, float)) else v for v in r) for r in expected]
