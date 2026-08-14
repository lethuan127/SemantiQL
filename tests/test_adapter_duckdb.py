"""The adapter is the only thing that talks to a database, and it stays thin."""

from __future__ import annotations

from semantiql.adapters.base import Adapter
from semantiql.adapters.duckdb import DuckDBAdapter


def test_satisfies_the_protocol_structurally(adapter: DuckDBAdapter) -> None:
    """N4: an adapter satisfies the seam without inheriting from it.

    Note the limit of this check: `isinstance` on a runtime_checkable Protocol compares
    member *names* only, so it would accept wrong signatures. mypy strict is what actually
    verifies the shape; this only pins the no-inheritance property.
    """
    assert isinstance(adapter, Adapter)
    assert Adapter not in DuckDBAdapter.__mro__


def test_reads_csv_without_a_database(adapter: DuckDBAdapter) -> None:
    relation = DuckDBAdapter.relation("examples/retail/orders.csv").sql(dialect="duckdb")
    names = adapter.columns(relation)
    assert names == ["order_id", "order_date", "channel", "region", "amount"]


def test_relation_dispatches_on_suffix() -> None:
    assert "READ_CSV_AUTO" in DuckDBAdapter.relation("a/b.csv").sql(dialect="duckdb").upper()
    assert "READ_PARQUET" in DuckDBAdapter.relation("a/b.parquet").sql(dialect="duckdb").upper()
    assert DuckDBAdapter.relation("public.orders").sql(dialect="duckdb") == "public.orders"


def test_relation_escapes_quotes_in_the_path() -> None:
    """A quote in a model `source` must be escaped, not close the literal."""
    rendered = DuckDBAdapter.relation("/tmp/a.csv') , read_csv_auto('/tmp/b.csv").sql(
        dialect="duckdb"
    )
    # The embedded quote is doubled, so the payload stays inside one literal.
    assert "''" in rendered, rendered


def test_execute_returns_names_and_rows(adapter: DuckDBAdapter) -> None:
    names, rows = adapter.execute("SELECT 1 AS one, 'x' AS letter")
    assert names == ["one", "letter"]
    assert rows == [(1, "x")]
