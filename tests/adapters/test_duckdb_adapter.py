"""The adapter is the only thing that talks to a database, and it stays thin."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from semantiql.adapters.base import Adapter, ColumnProfile
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


# --- profile (spec 020): reading rows, which `columns()` deliberately does not.


def _profiled(tmp_path: Path) -> tuple[int, dict[str, ColumnProfile]]:
    import duckdb as ddb

    database = tmp_path / "p.duckdb"
    setup = ddb.connect(str(database))
    setup.execute(
        "CREATE TABLE t (id BIGINT, code BIGINT, amount DECIMAL(10,2),"
        "                label VARCHAR, seen_at TIMESTAMPTZ)"
    )
    setup.execute(
        "INSERT INTO t VALUES "
        "(1, 1, 10.00, 'a', '2026-01-01 00:00:00+00'),"
        "(2, 1, 20.00, 'b', '2026-02-01 00:00:00+00'),"
        "(3, 2, 30.00, NULL, '2026-03-01 00:00:00+00')"
    )
    setup.close()
    adapter = DuckDBAdapter(database=str(database))
    try:
        profile = adapter.profile("t")
    finally:
        adapter.close()
    return profile.rows, {c.name: c for c in profile.columns}


def test_profile_counts_rows_nulls_and_distinct_values(tmp_path: Path) -> None:
    rows, by_name = _profiled(tmp_path)
    assert rows == 3
    assert by_name["label"].nulls == 1
    assert by_name["label"].distinct == 2, "distinct must not count the null"
    assert by_name["id"].nulls == 0


def test_profile_sums_a_numeric_column_exactly(tmp_path: Path) -> None:
    """The sum is the field that prices a revenue question, so float drift is not acceptable.

    Casting each value before summing rather than the total afterwards: on real data
    `sum(fare_amount)::numeric` gave 53882224.7599785 where `sum(fare_amount::numeric)` gave
    53882224.76. A figure about to become a business definition should not arrive with noise on it.
    """
    amount = _profiled(tmp_path)[1]["amount"]
    assert float(str(amount.total)) == 60.0
    assert float(str(amount.minimum)) == 10.0
    assert float(str(amount.maximum)) == 30.0


def test_profile_reports_the_distribution_of_a_coded_column(tmp_path: Path) -> None:
    """The reason this verb exists.

    `code` is `BIGINT`, so every type-driven heuristic calls it a number. It is a category, and only
    its cardinality reveals that. A model built without this groups by it and produces a chart
    labelled 1, 2.
    """
    code = _profiled(tmp_path)[1]["code"]
    assert code.values is not None
    assert dict(code.values) == {1: 2, 2: 1}


def test_profile_leaves_a_high_cardinality_column_without_a_distribution(tmp_path: Path) -> None:
    """Bounded output. Three ids is under the threshold, so use a column that is not."""
    import duckdb as ddb

    database = tmp_path / "wide.duckdb"
    setup = ddb.connect(str(database))
    setup.execute("CREATE TABLE t AS SELECT i AS id FROM range(0, 100) AS r(i)")
    setup.close()
    adapter = DuckDBAdapter(database=str(database))
    try:
        (column,) = adapter.profile("t").columns
    finally:
        adapter.close()
    assert column.distinct == 100
    assert column.values is None, "100 distinct values must not all be listed"


def test_profile_reports_a_timestamp_bound_as_text(tmp_path: Path) -> None:
    """Rendered in the database, because DuckDB cannot return a `timestamptz` without `pytz`.

    Found by running it. The bound is still in the session's timezone — inherent to the type, and
    why
    `columns()` reports `carries_timezone` separately as the thing that decides `timezone:`.
    """
    seen_at = _profiled(tmp_path)[1]["seen_at"]
    assert isinstance(seen_at.minimum, str)
    assert "2026-01-01" in seen_at.minimum or "2025-12-31" in seen_at.minimum


def test_profile_of_an_empty_relation_says_so(tmp_path: Path) -> None:
    import duckdb as ddb

    database = tmp_path / "empty.duckdb"
    setup = ddb.connect(str(database))
    setup.execute("CREATE TABLE t (id BIGINT)")
    setup.close()
    adapter = DuckDBAdapter(database=str(database))
    try:
        profile = adapter.profile("t")
    finally:
        adapter.close()
    assert profile.rows == 0
    (column,) = profile.columns
    assert column.distinct == 0
    assert column.values is None, "an empty column has no distribution to show"


def test_profile_quotes_a_column_whose_name_is_reserved(tmp_path: Path) -> None:
    """Suggested by this file's own fixture failing: `at` is reserved in DuckDB.

    The fixture's DDL broke, not `profile` — but a real warehouse does contain a column called
    `order` or `select`, and the aggregate SQL is built here rather than taken from a caller, so the
    quoting is this adapter's responsibility. Asserted rather than assumed.
    """
    import duckdb as ddb

    database = tmp_path / "reserved.duckdb"
    setup = ddb.connect(str(database))
    setup.execute('CREATE TABLE t ("order" BIGINT, "select" VARCHAR)')
    setup.execute("INSERT INTO t VALUES (1, 'x'), (2, 'y')")
    setup.close()
    adapter = DuckDBAdapter(database=str(database))
    try:
        profile = adapter.profile("t")
    finally:
        adapter.close()
    by_name = {c.name: c for c in profile.columns}
    assert by_name["order"].distinct == 2
    assert by_name["select"].distinct == 2
