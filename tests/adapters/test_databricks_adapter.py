"""The Databricks adapter (spec 023).

**Nothing here has touched a real workspace.** No Databricks credentials exist on this machine, and
the
driver is an optional extra that is not installed by default, so the live tests skip. That is stated
plainly rather than left for someone to infer from a green run: what is verified below is the *pure*
half — the type mapping, the relation building, and the messages a missing driver or credential
produces — and the half that talks to a warehouse is unverified.

The pure half is not trivial, which is why it earns tests. Spark's type names are its own,
`TIMESTAMP` and `TIMESTAMP_NTZ` mean the opposite of what their lengths suggest, and a file path
has to
be refused by name rather than passed through to become a missing-table error.
"""

from __future__ import annotations

import pytest

from semantiql.adapters.base import AdapterError
from semantiql.adapters.databricks import DatabricksAdapter


@pytest.mark.parametrize(
    ("native", "kind"),
    [
        ("STRING", "string"),
        ("VARCHAR(64)", "string"),
        ("BIGINT", "number"),
        ("INT", "number"),
        ("DOUBLE", "number"),
        ("DECIMAL(38,6)", "number"),
        ("BOOLEAN", "boolean"),
        ("DATE", "date"),
        ("TIMESTAMP", "date"),
        ("TIMESTAMP_NTZ", "date"),
        ("MAP<STRING,INT>", "other"),
        ("STRUCT<a:INT>", "other"),
        ("ARRAY<STRING>", "other"),
        ("BINARY", "other"),
        ("SOMETHING_NEW", "other"),
    ],
)
def test_spark_types_map_into_the_models_vocabulary(native: str, kind: str) -> None:
    """Translation is the adapter's job (N4), so nothing above here learns Spark's spelling.

    The last case matters most: an unknown type returns `other`, which callers must read as silence
    rather than as a mismatch. An honest unknown beats a confident wrong answer.
    """
    assert DatabricksAdapter._kind(native) == kind


def test_timestamp_carries_a_zone_and_timestamp_ntz_does_not() -> None:
    """The inversion worth a test.

    In Spark, `TIMESTAMP` *is* zone-aware and `TIMESTAMP_NTZ` is the naive one — the opposite of
    what
    the longer name suggests to anyone arriving from Postgres. Getting this backwards would put a
    `timezone:` on a naive column, which moves the buckets rather than pinning them (spec 011).
    """
    assert DatabricksAdapter._carries_timezone("TIMESTAMP") is True
    assert DatabricksAdapter._carries_timezone("timestamp") is True
    assert DatabricksAdapter._carries_timezone("TIMESTAMP_NTZ") is False
    assert DatabricksAdapter._carries_timezone("DATE") is False
    assert DatabricksAdapter._carries_timezone("STRING") is False


def test_a_missing_credential_is_refused_by_name() -> None:
    """ "Connection failed" sends the reader to the network; a name sends them to their shell."""
    pytest.importorskip("databricks.sql", reason="the databricks extra is not installed")
    with pytest.raises(AdapterError) as caught:
        DatabricksAdapter(server_hostname="example.cloud.databricks.com")
    message = str(caught.value)
    assert "DATABRICKS_HTTP_PATH" in message
    assert "DATABRICKS_TOKEN" in message


def test_a_missing_driver_says_how_to_install_it() -> None:
    """The failure a fresh clone gets, and it must not be a traceback.

    The driver is imported inside `__init__` precisely so that importing the module stays free. If
    this
    ever raises `ModuleNotFoundError` instead, someone has moved the import to the top of the file
    and
    every MCP server without the extra now fails at startup.
    """
    import importlib.util

    if importlib.util.find_spec("databricks") is not None:
        pytest.skip("the databricks extra is installed, so this path cannot be reached")
    with pytest.raises(AdapterError) as caught:
        DatabricksAdapter(server_hostname="h", http_path="p", access_token="t")
    assert "uv sync --extra databricks" in str(caught.value)


def test_a_file_source_is_refused_rather_than_passed_through() -> None:
    """Databricks has no file sources, and the reason to refuse by name is the error it replaces.

    Passed through, `orders.csv` becomes "table or view not found", which sends the reader looking
    for
    a missing table when the real problem is that this engine cannot read files at all (the same
    reasoning as the Postgres adapter's).
    """
    adapter = DatabricksAdapter.__new__(DatabricksAdapter)  # no connection needed for this path
    for source in ("orders.csv", "/tmp/data.parquet"):
        with pytest.raises(AdapterError, match="file"):
            adapter.relation(source)


def test_a_table_source_becomes_a_table_expression() -> None:
    """Built, not interpolated: a quote in `source` cannot inject relations into the FROM."""
    adapter = DatabricksAdapter.__new__(DatabricksAdapter)
    assert adapter.relation("orders").sql(dialect="databricks") == "orders"
    assert adapter.relation("main.sales.orders").sql(dialect="databricks") == "main.sales.orders"


def test_the_dialect_is_databricks_so_the_engine_transpiles() -> None:
    """N4 in one assertion: the adapter names a dialect and sqlglot does the rest."""
    adapter = DatabricksAdapter.__new__(DatabricksAdapter)
    assert adapter.dialect == "databricks"


def test_the_engine_emits_valid_databricks_sql_for_a_time_grain() -> None:
    """What makes this adapter thin, checked rather than assumed.

    If sqlglot did not already speak this dialect, a grain would need special-casing in `compile.py`
    and N4 would be broken by the second warehouse.
    """
    import sqlglot

    (out,) = sqlglot.transpile(
        "SELECT SUM(amount) AS revenue, DATE_TRUNC('MONTH', CAST(order_date AS TIMESTAMP)) "
        "FROM orders GROUP BY 2",
        read="duckdb",
        write="databricks",
    )
    assert "TIMESTAMP_NTZ" in out, "the grain's cast did not survive transpilation"
    assert "DATE_TRUNC" in out
