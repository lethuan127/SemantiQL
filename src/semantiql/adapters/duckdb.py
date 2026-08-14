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

from semantiql.adapters.base import AdapterError


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

    def columns(self, relation: str) -> list[str]:
        try:
            cur = self._conn.execute(f"SELECT * FROM {relation} LIMIT 0")
        except duckdb.Error as exc:
            raise AdapterError(f"could not read {relation}: {exc}") from exc
        return [d[0] for d in cur.description or []]

    def execute(self, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        try:
            cur = self._conn.execute(sql)
        except duckdb.Error as exc:
            raise AdapterError(f"DuckDB rejected the query: {exc}") from exc
        names = [d[0] for d in cur.description or []]
        return names, [tuple(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()
