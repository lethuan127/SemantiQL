"""The adapter is the only thing that talks to a database, and it stays thin."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

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
    """`columns` takes the model's `source` and builds the probe itself (spec 009).

    It used to take a relation string and interpolate it, which meant the caller had to
    reconstruct `read_csv_auto('…')` by hand — adapter knowledge outside the adapter — and
    which was the one place left in the codebase building SQL by string.
    """
    described = adapter.columns("examples/retail/orders.csv")
    assert [c.name for c in described] == [
        "order_id",
        "order_date",
        "channel",
        "region",
        "amount",
    ]


def test_classifies_its_own_types_into_the_models_vocabulary(adapter: DuckDBAdapter) -> None:
    """N4: the checker compares a column to `type:` without learning DuckDB's type names."""
    kinds = {c.name: c.kind for c in adapter.columns("examples/retail/orders.csv")}
    assert kinds == {
        "order_id": "number",
        "order_date": "date",
        "channel": "string",
        "region": "string",
        "amount": "number",
    }


def test_an_unclassifiable_type_is_other_not_a_guess(adapter: DuckDBAdapter) -> None:
    """`other` means "cannot tell", and doctor must read it as silence, not as a mismatch."""
    assert DuckDBAdapter._kind("STRUCT(a INTEGER)") == "other"
    assert DuckDBAdapter._kind("INTEGER[]") == "other"
    assert DuckDBAdapter._kind("DECIMAL(18,4)") == "number"
    assert DuckDBAdapter._kind("TIMESTAMP WITH TIME ZONE") == "date"


def test_describing_a_missing_source_is_an_adapter_error(adapter: DuckDBAdapter) -> None:
    from semantiql.adapters.base import AdapterError

    with pytest.raises(AdapterError, match="no_such_table"):
        adapter.columns("no_such_table")


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


def test_an_array_of_timestamps_carries_no_timezone() -> None:
    """`TIMESTAMPTZ[]` is a list, not an instant — so no grain applies to it.

    The array branch again (spec 009 found it in `_kind`, spec 010 in psycopg's registry). Saying
    a list of instants carries a zone would let doctor bless a grain over something that has no
    single point in time at all.
    """
    assert DuckDBAdapter._carries_timezone("TIMESTAMPTZ[]") is False
    assert DuckDBAdapter._carries_timezone("TIMESTAMP WITH TIME ZONE[]") is False
    assert DuckDBAdapter._carries_timezone("TIMESTAMPTZ") is True


# --- Enumeration (spec 016). Discovery cannot start without it.


def test_tables_lists_tables_and_views(tmp_path: Path) -> None:
    """Views are included, and that is deliberate.

    A view is the documented way to model a join, so a modeller discovering a database is *more*
    likely to want the views than the base tables. Omitting them would hide the useful half.
    """
    database = tmp_path / "w.duckdb"
    setup = duckdb.connect(str(database))
    setup.execute("CREATE TABLE orders (id INT); CREATE VIEW orders_v AS SELECT * FROM orders")
    setup.close()

    adapter = DuckDBAdapter(str(database))
    try:
        assert adapter.tables() == ["orders", "orders_v"]
    finally:
        adapter.close()


def test_a_relation_outside_the_default_schema_is_qualified(tmp_path: Path) -> None:
    """`main` needs no prefix; anything else does, or the name is ambiguous in a model."""
    database = tmp_path / "w.duckdb"
    setup = duckdb.connect(str(database))
    setup.execute("CREATE SCHEMA staging; CREATE TABLE staging.raw (a INT); CREATE TABLE t (a INT)")
    setup.close()

    adapter = DuckDBAdapter(str(database))
    try:
        assert adapter.tables() == ["staging.raw", "t"]
    finally:
        adapter.close()


def test_every_enumerated_name_can_be_described(tmp_path: Path) -> None:
    """The property that makes discovery compose: a listed name is a name `columns()` accepts.

    If enumeration returned something `columns()` could not take, discovery would produce a model
    whose `source:` values do not resolve — and the failure would land on the user, not here.
    """
    database = tmp_path / "w.duckdb"
    setup = duckdb.connect(str(database))
    setup.execute("CREATE SCHEMA s; CREATE TABLE s.a (x INT); CREATE TABLE b (y VARCHAR)")
    setup.close()

    adapter = DuckDBAdapter(str(database))
    try:
        for name in adapter.tables():
            assert adapter.columns(name), f"{name} was listed but cannot be described"
    finally:
        adapter.close()


def test_an_in_memory_connection_reading_files_lists_nothing() -> None:
    """A `read_csv_auto` source is not a catalogue object, so there is nothing to enumerate.

    Correct, and it looks like a bug — which is why the CLI explains it rather than printing an
    empty list. Pinned here so nobody "fixes" enumeration to invent entries for file reads.
    """
    adapter = DuckDBAdapter()
    try:
        assert adapter.tables() == []
    finally:
        adapter.close()
