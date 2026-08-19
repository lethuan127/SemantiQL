"""Databricks — the third datasource, and the second real test of N4 (spec 023).

**Brought forward by an owner decision.** The constitution's roadmap places Databricks in v3. That
was
raised before any code was written, along with the rule that a new connector is never a routine
change,
and the decision to bring it forward behind an **optional dependency group** is the repository
owner's.
It is recorded here so the roadmap's history reads as a decision rather than a drift.

**Why this adapter is thin.** N4 says the engine emits one canonical dialect and transpiles to the
target. sqlglot already speaks `databricks` — a time grain comes out as
`DATE_TRUNC('MONTH', CAST(x AS TIMESTAMP_NTZ))`, which is valid Spark SQL — so nothing in `engine/`
changes and this file is connect, introspect, run.

**Read-only.** There is no write path here, and the driver exposes no read-only session flag of the
kind
`psycopg` has. So the guarantee comes from `validate` refusing every non-`SELECT` before anything
reaches `execute` — the same honest position as an in-memory DuckDB, and worth stating rather than
implying a stronger one.

**The driver is imported inside `__init__`.** `pip install semantiql` does not carry it, so
importing
this module must stay free; a missing driver becomes an install instruction rather than a traceback
in
somebody's MCP server.
"""

from __future__ import annotations

import contextlib
from typing import Any

from sqlglot import exp

from semantiql.adapters.base import (
    CATEGORICAL_AT_MOST,
    AdapterError,
    Column,
    ColumnKind,
    ColumnProfile,
    RelationProfile,
)

#: Sources this adapter cannot honour, refused by name. DuckDB reads these paths directly;
#: Databricks
#: has no notion of a local file source, so passing one through would surface as a missing-table
#: error
#: and send the reader after the wrong problem — the same reasoning as the Postgres adapter's.
_FILE_SUFFIXES = frozenset({".csv", ".parquet"})

#: Spark's type names, lower-cased, mapped into the model's four-word vocabulary. Translation is the
#: adapter's job (N4) so nothing above here learns a dialect's spelling.
_KINDS: dict[str, ColumnKind] = {
    "string": "string",
    "varchar": "string",
    "char": "string",
    "binary": "other",
    "boolean": "boolean",
    "byte": "number",
    "tinyint": "number",
    "short": "number",
    "smallint": "number",
    "int": "number",
    "integer": "number",
    "long": "number",
    "bigint": "number",
    "float": "number",
    "real": "number",
    "double": "number",
    "decimal": "number",
    "numeric": "number",
    "date": "date",
    "timestamp": "date",
    "timestamp_ntz": "date",
    "interval": "other",
    "array": "other",
    "map": "other",
    "struct": "other",
    "variant": "other",
    "void": "other",
}

#: The default schema, left unqualified when a relation is displayed — `main` on DuckDB, `public` on
#: Postgres, `default` here.
_DEFAULT_SCHEMA = "default"


class DatabricksAdapter:
    """A read-only Databricks SQL warehouse connection."""

    def __init__(
        self,
        server_hostname: str = "",
        http_path: str = "",
        access_token: str = "",
        catalog: str = "",
        schema: str = "",
    ) -> None:
        try:
            from databricks import sql as databricks_sql
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on an optional extra
            raise AdapterError(
                "the Databricks driver is not installed. It is an optional extra, so that a "
                "clone stays light:\n  uv sync --extra databricks\n"
                "or  pip install 'semantiql[databricks]'"
            ) from exc

        missing = [
            name
            for name, value in (
                ("--dbx-host / DATABRICKS_SERVER_HOSTNAME", server_hostname),
                ("--dbx-http-path / DATABRICKS_HTTP_PATH", http_path),
                ("--dbx-token / DATABRICKS_TOKEN", access_token),
            )
            if not value
        ]
        if missing:
            # Named, because "connection failed" sends the reader to the network when the real
            # problem is an unset variable.
            raise AdapterError("Databricks needs " + ", ".join(missing))

        self._catalog = catalog
        self._schema = schema or _DEFAULT_SCHEMA
        try:
            self._conn = databricks_sql.connect(
                server_hostname=server_hostname,
                http_path=http_path,
                access_token=access_token,
                **({"catalog": catalog} if catalog else {}),
                **({"schema": schema} if schema else {}),
            )
        except Exception as exc:  # the driver raises its own hierarchy
            raise AdapterError(f"could not connect to Databricks: {exc}") from exc

    @property
    def dialect(self) -> str:
        """`databricks`, so the engine transpiles rather than special-casing (N4)."""
        return "databricks"

    def relation(self, source: str) -> exp.Expr:
        """A model `source` as something selectable.

        Built as a table expression rather than interpolated, so a quote in `source` is escaped by
        sqlglot instead of closing an identifier and injecting relations into the FROM clause.
        """
        suffix = source[source.rfind(".") :].lower() if "." in source else ""
        if suffix in _FILE_SUFFIXES:
            raise AdapterError(
                f"{source!r} looks like a file path, and Databricks has no file sources. "
                "Register it as a table or view in Unity Catalog first."
            )
        return exp.to_table(source)

    def tables(self) -> list[str]:
        """Every relation a model could name, as displayed names.

        `information_schema` rather than `SHOW TABLES`, so the schema arrives in the same query and
        this stays one code path shared in shape with the Postgres adapter.
        """
        sql = (
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema NOT IN ('information_schema') ORDER BY table_schema, table_name"
        )
        names = [
            name if schema == self._schema else f"{schema}.{name}"
            for schema, name in self._query(sql)
        ]
        # Sorted by what is *displayed*: sorting by schema first prints a list that looks unsorted
        # to
        # someone who only sees the qualified name (the lesson from spec 016).
        return sorted(names)

    def columns(self, source: str) -> list[Column]:
        """Describe `source` without reading a row of it."""
        probe = (
            exp.select(exp.Star()).from_(self.relation(source)).limit(0).sql(dialect="databricks")
        )
        described: list[Column] = []
        try:
            with self._conn.cursor() as cur:
                cur.execute(probe)
                for description in cur.description or []:
                    native = str(description[1] or "")
                    described.append(
                        Column(
                            name=str(description[0]),
                            native_type=native,
                            kind=self._kind(native),
                            carries_timezone=self._carries_timezone(native),
                        )
                    )
        except Exception as exc:
            raise AdapterError(f"could not read {source!r}: {exc}") from exc
        return described

    def profile(self, source: str) -> RelationProfile:
        """What is in `source` — one wide aggregate pass, then a distribution per coded column.

        Same contract as the other adapters, and the same reason it exists: the questions a semantic
        model turns on cannot be answered from types (spec 020).
        """
        described = self.columns(source)
        if not described:
            return RelationProfile(source=source, rows=0, columns=())

        relation = self.relation(source)
        selects: list[exp.Expr] = [exp.func("count", exp.Star())]
        for column in described:
            reference = exp.column(column.name)
            selects.append(exp.func("count", reference))
            selects.append(exp.Count(this=exp.Distinct(expressions=[reference])))
            if column.kind == "date":
                # Text, so the driver's own conversion cannot move an instant on the way back. Still
                # the session's zone for a zone-carrying column — `carries_timezone` is the field
                # that
                # decides `timezone:`, not a bound printed here.
                selects.append(exp.cast(exp.func("min", reference), "STRING"))
                selects.append(exp.cast(exp.func("max", reference), "STRING"))
            elif column.kind == "number":
                selects.append(exp.func("min", reference))
                selects.append(exp.func("max", reference))
                # Cast before summing, not after: on a float column the drift has already happened
                # by
                # the time an outer cast runs (measured on Postgres, spec 020).
                selects.append(exp.func("sum", exp.cast(reference, "DECIMAL(38,6)")))

        wide = exp.select(*selects).from_(relation).sql(dialect="databricks")
        rows_result = self._query(wide)
        row: tuple[Any, ...] = rows_result[0] if rows_result else ()
        rows = int(row[0] or 0) if row else 0

        profiles: list[ColumnProfile] = []
        cursor = 1
        for column in described:
            non_null = int(row[cursor] or 0) if row else 0
            distinct = int(row[cursor + 1] or 0) if row else 0
            cursor += 2
            minimum = maximum = total = None
            if column.kind == "date":
                minimum, maximum = row[cursor], row[cursor + 1]
                cursor += 2
            elif column.kind == "number":
                minimum, maximum, total = row[cursor], row[cursor + 1], row[cursor + 2]
                cursor += 3
            profiles.append(
                ColumnProfile(
                    name=column.name,
                    nulls=rows - non_null,
                    distinct=distinct,
                    minimum=minimum,
                    maximum=maximum,
                    total=total,
                    values=self._distribution(relation, column.name, column.kind == "date")
                    if 0 < distinct <= CATEGORICAL_AT_MOST
                    else None,
                )
            )
        return RelationProfile(source=source, rows=rows, columns=tuple(profiles))

    def _distribution(
        self, relation: exp.Expr, column: str, as_text: bool = False
    ) -> tuple[tuple[object, int], ...]:
        """Value and row count, most frequent first. Bounded by the caller's cardinality check."""
        grouped: exp.Expr = exp.column(column)
        shown: exp.Expr = exp.cast(grouped, "STRING") if as_text else grouped
        counted = exp.func("count", exp.Star())
        sql = (
            exp.select(shown, counted)
            .from_(relation)
            .group_by(grouped)
            .order_by(exp.Ordered(this=counted, desc=True))
            .limit(CATEGORICAL_AT_MOST)
            .sql(dialect="databricks")
        )
        return tuple((value, int(count)) for value, count in self._query(sql))

    def execute(self, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Run already-validated, already-transpiled SQL."""
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql)
                names = [str(d[0]) for d in cur.description or []]
                rows = [tuple(r) for r in cur.fetchall()]
                return names, rows
        except Exception as exc:
            raise AdapterError(f"Databricks rejected the query: {exc}") from exc

    def close(self) -> None:
        # Closing an already-broken connection is not a failure worth surfacing: the caller is
        # on its way out, and raising here would replace a real error with a teardown one.
        with contextlib.suppress(Exception):
            self._conn.close()

    def _query(self, sql: str) -> list[tuple[Any, ...]]:
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql)
                return [tuple(r) for r in cur.fetchall()]
        except Exception as exc:
            raise AdapterError(f"Databricks rejected the query: {exc}") from exc

    @staticmethod
    def _kind(native_type: str) -> ColumnKind:
        """Spark's type name in the model's vocabulary, or `other` for an honest unknown."""
        base = native_type.strip().lower().split("(")[0].split("<")[0].strip()
        return _KINDS.get(base, "other")

    @staticmethod
    def _carries_timezone(native_type: str) -> bool:
        """Whether the column stores an instant with a zone.

        Spark's `TIMESTAMP` is zone-aware and `TIMESTAMP_NTZ` is not, which is the opposite way
        round
        from what the longer name suggests — so this is worth a function rather than an inline
        guess.
        """
        base = native_type.strip().lower().split("(")[0].strip()
        return base == "timestamp"
