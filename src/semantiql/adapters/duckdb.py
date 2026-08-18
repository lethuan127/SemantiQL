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

from semantiql.adapters.base import (
    CATEGORICAL_AT_MOST,
    AdapterError,
    Column,
    ColumnKind,
    ColumnProfile,
    RelationProfile,
)


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
    def _carries_timezone(cls, native_type: str) -> bool:
        """Does this DuckDB type store a zone? Only the TZ-suffixed timestamps do.

        `_kind` deliberately folds every `TIMESTAMP*` into `date` — for filtering they behave
        alike. Grains are the one place they do not, so this reads the same string again and
        answers the narrower question (spec 011).
        """
        upper = native_type.strip().upper()
        if upper.endswith("[]"):
            return False
        base = upper.split("(", 1)[0].strip()
        return base in {"TIMESTAMPTZ", "TIMESTAMP WITH TIME ZONE"}

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

    #: Relations DuckDB puts in its own default schema, which need no qualification. Anything
    #: else is returned as `schema.name` so it stays unambiguous when pasted into a model.
    _DEFAULT_SCHEMA = "main"

    def tables(self) -> list[str]:
        """Tables and views from the catalogue, sorted.

        A `read_csv_auto` source is **not** a catalogue object, so an in-memory connection reading
        CSV files reports nothing here. That is correct and it looks like a bug, which is why the
        CLI says so rather than printing an empty list.
        """
        query = (
            "SELECT table_schema, table_name FROM information_schema.tables "
            "ORDER BY table_schema, table_name"
        )
        try:
            rows = self._conn.execute(query).fetchall()
        except duckdb.Error as exc:  # pragma: no cover - catalogue is always readable
            raise AdapterError(f"could not list relations: {exc}") from exc
        # Sorted by the name as returned, not by schema — the catalogue's order puts `main.t`
        # before `staging.raw`, which reads as unsorted to anyone looking at the output.
        return sorted(
            str(name) if schema == self._DEFAULT_SCHEMA else f"{schema}.{name}"
            for schema, name in rows
        )

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
            Column(
                name=str(d[0]),
                native_type=str(d[1]),
                kind=self._kind(str(d[1])),
                carries_timezone=self._carries_timezone(str(d[1])),
            )
            for d in described
        ]

    def profile(self, source: str) -> RelationProfile:
        """One wide aggregate pass, then one grouped query per low-cardinality column.

        One pass rather than a query per column: the taxi table has nineteen columns and 2.96M rows,
        so per-column queries would be nineteen sequential scans for no benefit. Built from
        `relation()` for the same reason `columns()` is — a quote in `source` stays a value.
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
                # Rendered to text in the database because DuckDB cannot hand a `timestamptz`
                # back to Python without `pytz`, which is not a dependency here and is not worth
                # becoming one so a report can print a bound.
                #
                # Be clear about what this does *not* fix: a tz-carrying column still renders in the
                # **session's** timezone, so this bound is not a machine-independent instant. That
                # is
                # inherent to the type and it is why `columns()` reports `carries_timezone` as its
                # own bit — that flag, not a bound printed here, is what decides whether a dimension
                # needs `timezone:` (spec 011).
                selects.append(exp.cast(exp.func("min", reference), "VARCHAR"))
                selects.append(exp.cast(exp.func("max", reference), "VARCHAR"))
            elif column.kind == "number":
                selects.append(exp.func("min", reference))
                selects.append(exp.func("max", reference))
            if column.kind == "number":
                # Cast before summing, not after. `sum(x)::DECIMAL` on a DOUBLE column has already
                # accumulated float drift by the time the cast runs — measured on Postgres, where
                # the
                # same sum came back as 53882224.7599785 instead of 53882224.76.
                selects.append(exp.func("sum", exp.cast(reference, "DECIMAL(38,6)")))

        wide = exp.select(*selects).from_(relation).sql(dialect="duckdb")
        try:
            row = self._conn.execute(wide).fetchone() or ()
        except duckdb.Error as exc:
            raise AdapterError(f"could not profile {source!r}: {exc}") from exc

        rows = int(row[0] or 0)
        profiles: list[ColumnProfile] = []
        cursor = 1
        for column in described:
            non_null = int(row[cursor] or 0)
            distinct = int(row[cursor + 1] or 0)
            cursor += 2
            minimum = maximum = total = None
            if column.kind in {"number", "date"}:
                minimum, maximum = row[cursor], row[cursor + 1]
                cursor += 2
            if column.kind == "number":
                total = row[cursor]
                cursor += 1
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
        """Value and row count, most frequent first.

        Only reached for a column whose distinct count is already known to be small, so the GROUP BY
        cannot produce an unbounded result.
        """
        reference: exp.Expr = exp.column(column)
        counted = exp.func("count", exp.Star())
        grouped = reference
        if as_text:
            reference = exp.cast(reference, "VARCHAR")
        sql = (
            exp.select(reference, counted)
            .from_(relation)
            .group_by(grouped)
            .order_by(exp.Ordered(this=counted, desc=True))
            .limit(CATEGORICAL_AT_MOST)
            .sql(dialect="duckdb")
        )
        try:
            return tuple((value, int(count)) for value, count in self._conn.execute(sql).fetchall())
        except duckdb.Error as exc:
            raise AdapterError(f"could not profile {column!r}: {exc}") from exc

    def execute(self, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        try:
            cur = self._conn.execute(sql)
        except duckdb.Error as exc:
            raise AdapterError(f"DuckDB rejected the query: {exc}") from exc
        names = [d[0] for d in cur.description or []]
        return names, [tuple(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()
