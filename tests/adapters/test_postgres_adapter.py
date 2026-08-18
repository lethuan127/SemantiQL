"""The Postgres adapter, checked without a Postgres.

`_kind`, `_native_type` and `relation` are pure — they consult psycopg's static type registry
and the model's `source` string, never a connection. So the classification rules and the
file-source refusal are tested here, in the ordinary unit run, and only the parts that
genuinely need a server live in the `pg`-marked differential suite.
"""

from __future__ import annotations

import pytest

from semantiql.adapters.base import Adapter, AdapterError
from semantiql.adapters.postgres import PostgresAdapter

# Postgres OIDs, taken from the catalogue rather than remembered. `pg_type.oid` is stable
# across versions for the built-in types, which is why psycopg can ship them as a static table.
BOOL, TEXT, VARCHAR, BPCHAR, NAME, UUID = 16, 25, 1043, 1042, 19, 2950
DATE, TIMESTAMP, TIMESTAMPTZ, TIME, INTERVAL = 1082, 1114, 1184, 1083, 1186
INT2, INT4, INT8, NUMERIC, FLOAT4, FLOAT8, MONEY = 21, 23, 20, 1700, 700, 701, 790
JSON, JSONB, BYTEA, POINT = 114, 3802, 17, 600
INT4_ARRAY, VARCHAR_ARRAY, DATE_ARRAY, NUMERIC_ARRAY = 1007, 1015, 1182, 1231


@pytest.fixture
def unconnected() -> PostgresAdapter:
    """An adapter that never opened a connection.

    `__new__` skips `__init__`, which is the only part that needs a server. Everything checked
    in this module is pure, so this is the honest way to say "no database was involved" rather
    than mocking one and hoping the mock is faithful.
    """
    return PostgresAdapter.__new__(PostgresAdapter)


def test_satisfies_the_protocol_structurally(unconnected: PostgresAdapter) -> None:
    """N4: an adapter satisfies the seam without inheriting from it.

    Same limit as the DuckDB copy of this test: `isinstance` on a `runtime_checkable` Protocol
    compares member *names* only, so it would accept wrong signatures. mypy strict is what
    verifies the shape. This pins the no-inheritance property, and — since spec 010 added
    `close()` to the Protocol — that the adapter is closable.
    """
    assert isinstance(unconnected, Adapter)
    assert Adapter not in PostgresAdapter.__mro__


def test_dialect_is_postgres(unconnected: PostgresAdapter) -> None:
    assert unconnected.dialect == "postgres"


@pytest.mark.parametrize(
    ("oid", "expected"),
    [
        (BOOL, "boolean"),
        (DATE, "date"),
        (TIMESTAMP, "date"),
        (TIMESTAMPTZ, "date"),
        (INT2, "number"),
        (INT4, "number"),
        (INT8, "number"),
        (NUMERIC, "number"),
        (FLOAT4, "number"),
        (FLOAT8, "number"),
        (MONEY, "number"),
        (TEXT, "string"),
        (VARCHAR, "string"),
        (BPCHAR, "string"),
        (NAME, "string"),
        (UUID, "string"),
    ],
)
def test_maps_each_known_type(oid: int, expected: str) -> None:
    assert PostgresAdapter._kind(oid) == expected


@pytest.mark.parametrize("oid", [JSON, JSONB, BYTEA, POINT, INTERVAL, TIME])
def test_unmappable_types_answer_other(oid: int) -> None:
    """`other` is the honest unknown `base.py` asks for — silence, not a guess.

    `interval` and `time` are the interesting entries: both are temporal, and neither is a
    date. Calling them `date` would let a `DATE_TRUNC` through that Postgres will reject, and
    calling `interval` a number would let a `SUM` through that means nothing.
    """
    assert PostgresAdapter._kind(oid) == "other"


def test_unregistered_oid_answers_other() -> None:
    """A user-defined type has an OID psycopg has never heard of. That is not a failure."""
    assert PostgresAdapter._kind(999_999) == "other"


@pytest.mark.parametrize(
    ("array_oid", "element_oid"),
    [(INT4_ARRAY, INT4), (VARCHAR_ARRAY, VARCHAR), (DATE_ARRAY, DATE), (NUMERIC_ARRAY, NUMERIC)],
)
def test_arrays_are_other_not_their_element_kind(array_oid: int, element_oid: int) -> None:
    """The trap this test exists for, stated so nobody simplifies it away.

    `psycopg.postgres.types.get()` accepts an **array** OID and returns the **element** type,
    with nothing on the result saying so. A naive `types.get(oid).name` therefore reports
    `integer[]` as a number, and `doctor` would bless a model asking Postgres to `SUM` an
    array. It is the same defect spec 009 found in DuckDB's `INTEGER[]`, arriving by a route no
    DuckDB test can reach.

    The assertion is deliberately two-sided: the element type still classifies normally, so a
    fix that returned `other` for everything would fail here too.
    """
    assert PostgresAdapter._kind(array_oid) == "other"
    assert PostgresAdapter._kind(element_oid) != "other"


def test_native_type_reads_the_way_a_dba_writes_it() -> None:
    """`native_type` is for the human reading the error, so it uses SQL's spelling."""
    assert PostgresAdapter._native_type(VARCHAR) == "character varying"
    assert PostgresAdapter._native_type(TIMESTAMP) == "timestamp without time zone"
    assert PostgresAdapter._native_type(FLOAT8) == "double precision"
    assert PostgresAdapter._native_type(INT4_ARRAY) == "integer[]"
    assert PostgresAdapter._native_type(999_999) == "oid 999999"


def test_a_plain_table_name_becomes_a_table() -> None:
    assert PostgresAdapter.relation("orders").sql(dialect="postgres") == "orders"


def test_a_schema_qualified_name_survives() -> None:
    """`.orders` is a suffix too — the file check must not eat a qualified name."""
    assert (
        PostgresAdapter.relation("analytics.orders").sql(dialect="postgres") == "analytics.orders"
    )


@pytest.mark.parametrize("source", ["orders.csv", "data/orders.CSV", "orders.parquet"])
def test_a_file_source_is_refused_by_name(source: str) -> None:
    """Refusing beats passing it through (spec 010, clarification Q6).

    Passed through, Postgres answers `relation "orders.csv" does not exist`, and the reader
    goes looking for a missing table. The real problem is that the engine has no file sources
    at all, so the message says that and says what to do instead.
    """
    with pytest.raises(AdapterError) as caught:
        PostgresAdapter.relation(source)
    assert "file source" in str(caught.value)
    assert "load the file into a table" in str(caught.value)


def _dsn_for_observer() -> str:
    """The DSN from the environment, not from the live connection.

    psycopg redacts the password from `conn.info.dsn`, so reconnecting with it works only against a
    password-free server. That exact mistake broke CI for five commits.
    """
    import os

    dsn = os.environ.get("SEMANTIQL_TEST_DSN")
    assert dsn, "the pg marker guarantees this is set"
    return dsn


@pytest.mark.pg
def test_enumeration_excludes_the_system_schemas(postgres_adapter: PostgresAdapter) -> None:
    """Without the exclusion, a few hundred catalogue relations bury the user's tables."""
    listed = postgres_adapter.tables()
    assert listed, "the corpus fixture creates tables, so something must be listed"
    assert not [name for name in listed if name.startswith(("pg_catalog.", "information_schema."))]
    assert "orders" in listed, "public relations are returned unqualified"


@pytest.mark.pg
def test_every_enumerated_name_can_be_described(postgres_adapter: PostgresAdapter) -> None:
    """A listed name must be a name `columns()` accepts, or discovery writes a broken model."""
    for name in postgres_adapter.tables():
        assert postgres_adapter.columns(name) is not None


@pytest.mark.pg
def test_enumeration_leaves_no_open_transaction(postgres_adapter: PostgresAdapter) -> None:
    """Same hazard as `execute` (spec 012): a long-lived server must not pin a snapshot.

    Enumeration runs its own query, so it needs its own end-of-transaction — and nothing else
    would notice, because the returned list is correct either way.
    """
    import psycopg

    pid = postgres_adapter._conn.info.backend_pid
    postgres_adapter.tables()

    observer = psycopg.connect(_dsn_for_observer())
    observer.autocommit = True
    try:
        row = observer.execute(
            "SELECT state FROM pg_stat_activity WHERE pid = %s", (pid,)
        ).fetchone()
    finally:
        observer.close()
    assert row is not None and row[0] == "idle", f"backend is {row and row[0]!r} after tables()"
