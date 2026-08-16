"""DuckDB adapter — the MVP datasource, and the one that needs no installation.

DuckDB reads CSV and Parquet directly, which is what makes the bundled example run with
no database, no credentials and no network (FR-3).

On read-only (constitution N5), stated precisely because the guarantee is narrower than it
looks: a **file-backed** database is opened `read_only=True`, but DuckDB refuses to open an
**in-memory** database read-only at all (`Cannot launch in-memory database in read-only
mode!`), and in-memory is the default the CLI uses. So on the default path the read-only
property is enforced by `engine.validate` refusing every non-SELECT statement, not by the
connection. Both matter; neither alone is the whole story.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
from sqlglot import exp

from semantiql.adapters.base import AdapterError, Column, ColumnKind


class DuckDBAdapter:
    """Satisfies `Adapter`. Structural typing — no base class needed."""

    def __init__(self, database: str = ":memory:") -> None:
        try:
            self._conn = duckdb.connect(database, read_only=database != ":memory:")
        except duckdb.Error as exc:  # pragma: no cover - environment-dependent
            raise AdapterError(f"could not open DuckDB at {database}: {exc}") from exc

    @property
    def dialect(self) -> str:
        return "duckdb"

    @staticmethod
    def relation(source: str) -> exp.Expr:
        """How a model `source` becomes something DuckDB can select from.

        A path to a CSV or Parquet file becomes a reader call; anything else is treated as
        an existing table or view name.

        The path is passed as a **string literal expression**, so a `source` containing a
        quote is escaped by sqlglot rather than closing the literal and injecting relations
        into the FROM clause.
        """
        suffix = Path(source).suffix.lower()
        if suffix == ".csv":
            return exp.func("read_csv_auto", exp.Literal.string(source))
        if suffix == ".parquet":
            return exp.func("read_parquet", exp.Literal.string(source))
        return exp.to_table(source)

    #: DuckDB's type names, mapped to the semantic model's vocabulary. Matched on the *base*
    #: type — the name with its parameters and array suffix removed — rather than by prefix,
    #: because prefixes lie: `INTERVAL` starts with `INT` without being a number, and
    #: `INTEGER[]` is a list of numbers rather than one. Both were classified wrongly by a
    #: prefix match until a test said so.
    _KINDS: dict[str, ColumnKind] = {
        "BOOLEAN": "boolean",
        "BOOL": "boolean",
        "LOGICAL": "boolean",
        "DATE": "date",
        "DATETIME": "date",
        "TINYINT": "number",
        "SMALLINT": "number",
        "INTEGER": "number",
        "BIGINT": "number",
        "HUGEINT": "number",
        "INT": "number",
        "INT1": "number",
        "INT2": "number",
        "INT4": "number",
        "INT8": "number",
        "UTINYINT": "number",
        "USMALLINT": "number",
        "UINTEGER": "number",
        "UBIGINT": "number",
        "DECIMAL": "number",
        "NUMERIC": "number",
        "REAL": "number",
        "DOUBLE": "number",
        "FLOAT": "number",
        "FLOAT4": "number",
        "FLOAT8": "number",
        "VARCHAR": "string",
        "CHAR": "string",
        "BPCHAR": "string",
        "TEXT": "string",
        "STRING": "string",
        "UUID": "string",
    }

    @classmethod
    def _kind(cls, native_type: str) -> ColumnKind:
        """Classify one DuckDB type, answering `other` rather than guessing."""
        upper = native_type.strip().upper()
        if upper.endswith("[]"):
            # A list of numbers is not a number: `sum` over it fails, and calling it one would
            # let doctor bless a model the database will reject.
            return "other"
        base = upper.split("(", 1)[0].strip()
        if base.startswith("TIMESTAMP"):  # TIMESTAMP, TIMESTAMP WITH TIME ZONE, TIMESTAMP_NS
            return "date"
        return cls._KINDS.get(base, "other")

    def columns(self, source: str) -> list[Column]:
        """Describe `source` without reading a row of it.

        The probe is built from `relation()` rather than interpolated, so a `source` containing
        a quote stays a value — the same property the FROM clause has, for the same reason —
        and a CSV path is described as readily as a table name.
        """
        probe = exp.select(exp.Star()).from_(self.relation(source)).limit(0).sql(dialect="duckdb")
        try:
            cur = self._conn.execute(probe)
        except duckdb.Error as exc:
            raise AdapterError(f"could not read {source!r}: {exc}") from exc
        described = cur.description or []
        return [
            Column(name=str(d[0]), native_type=str(d[1]), kind=self._kind(str(d[1])))
            for d in described
        ]

    def execute(self, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        try:
            cur = self._conn.execute(sql)
        except duckdb.Error as exc:
            raise AdapterError(f"DuckDB rejected the query: {exc}") from exc
        names = [d[0] for d in cur.description or []]
        return names, [tuple(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()
