"""Postgres adapter — the second datasource, and the one that tests N4.

DuckDB was here first, so every seam in `adapters/base.py` was designed with exactly one
implementation in front of it. This module is what turns "adding a datasource needs no core
changes" from a claim into an observation: if `engine/` had to change to accommodate it, N4
would be wrong (spec 010).

On read-only (constitution N5), the guarantee here is **stronger** than DuckDB's and it is
worth saying why rather than leaving the two looking equivalent. DuckDB cannot open an
in-memory database read-only at all, so on the CLI's default path N5 rests entirely on
`engine.validate` refusing non-SELECT statements. Postgres has no such gap: the connection is
put into read-only mode before any statement runs, so the server itself rejects a write even
if something upstream let one through. Both layers are still wanted; only one of them exists
on both engines.

Connection details never come from the semantic model (N3). They come from `--dsn`, or — when
that is empty — from libpq's own environment (`PGHOST`, `PGUSER`, `PGPASSWORD`, `.pgpass`),
which is what every other Postgres tool on the machine already reads. That is also how a
password stays out of shell history and out of `ps` output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg
from psycopg import postgres as pg_catalog
from sqlglot import exp

from semantiql.adapters.base import AdapterError, Column, ColumnKind

#: Sources this adapter cannot honour. DuckDB reads these paths directly; Postgres has no
#: notion of a file source at all, so passing one through as a table name would surface as
#: `relation "orders.csv" does not exist` — sending the reader after a missing table when the
#: real problem is the engine. Refusing by name is the N2 answer (spec 010, clarification Q6).
_FILE_SUFFIXES = frozenset({".csv", ".parquet"})


class PostgresAdapter:
    """Satisfies `Adapter`. Structural typing — no base class needed."""

    def __init__(self, conninfo: str = "") -> None:
        """Open a read-only connection. An empty `conninfo` defers to libpq's environment."""
        try:
            # `autocommit` stays False, and that is load-bearing rather than a default nobody
            # revisited: `read_only` sets the *transaction* characteristics, so under
            # autocommit it is silently ignored and writes go through. Measured, not assumed —
            # `CREATE TABLE` succeeds on an autocommit connection with `read_only = True` set.
            # `test_a_write_is_rejected_by_the_server` in the pg suite pins this.
            #
            # The cost is that the connection sits `idle in transaction` between queries, which
            # on a long-lived connection would pin a snapshot and block vacuum. It does not
            # here: one CLI invocation opens, asks, and closes. Revisit if a server mode ever
            # holds adapters open — and if it does, keep N5 by other means rather than by
            # turning autocommit on.
            self._conn: psycopg.Connection[tuple[Any, ...]] = psycopg.connect(conninfo)
        except psycopg.Error as exc:
            raise AdapterError(
                f"could not connect to Postgres: {exc}\n"
                "  check the server is running, and that the DSN names a reachable host, "
                "database and user — or set PGHOST/PGUSER/PGDATABASE"
            ) from exc
        try:
            # Before any statement runs, so there is no window in which a write is accepted.
            self._conn.read_only = True
        except psycopg.Error as exc:  # pragma: no cover - the server refused a session setting
            self._conn.close()
            raise AdapterError(f"could not put the connection into read-only mode: {exc}") from exc

    @property
    def dialect(self) -> str:
        return "postgres"

    @staticmethod
    def relation(source: str) -> exp.Expr:
        """How a model `source` becomes something Postgres can select from.

        Every source is a table or view name. Only the file suffixes DuckDB *does* support are
        singled out, so a schema-qualified `analytics.orders` is unaffected — its suffix is
        `.orders`, which is not in the set.
        """
        if Path(source).suffix.lower() in _FILE_SUFFIXES:
            raise AdapterError(
                f"{source!r} is a file source, which Postgres cannot read — it has no "
                "equivalent of DuckDB's read_csv_auto/read_parquet.\n"
                "  load the file into a table and point the model's `source` at the table name"
            )
        return exp.to_table(source)

    #: Postgres type names — psycopg's short spelling, not the SQL one — mapped to the semantic
    #: model's vocabulary. Keyed on the short name (`varchar`, `int4`, `timestamptz`) because it
    #: is one stable token; the SQL spelling (`character varying`, `timestamp without time
    #: zone`) is what a DBA reads and is kept as `native_type` instead.
    _KINDS: dict[str, ColumnKind] = {
        "bool": "boolean",
        "date": "date",
        "timestamp": "date",
        "timestamptz": "date",
        "int2": "number",
        "int4": "number",
        "int8": "number",
        "numeric": "number",
        "float4": "number",
        "float8": "number",
        "money": "number",
        "varchar": "string",
        "bpchar": "string",
        "char": "string",
        "text": "string",
        "name": "string",
        "uuid": "string",
    }

    @classmethod
    def _kind(cls, oid: int) -> ColumnKind:
        """Classify one Postgres type by OID, answering `other` rather than guessing.

        Two traps, both of which produce a confident wrong answer if you skip them.

        The registry **accepts an array OID and returns the element type**, with nothing on the
        result saying so: `types.get(1007)` — `integer[]` — answers `int4`. Classifying that as
        `number` would let doctor bless a model asking Postgres to `SUM` an array. It is the
        same bug spec 009 found in DuckDB's `INTEGER[]`, arriving by a route no DuckDB test can
        see. The tell is that the info carries its own `oid`: when it differs from the one asked
        for, the question was about the array form.

        An unregistered OID answers `None`, which is an honest unknown and maps to `other` —
        silence, which `doctor` treats as "the adapter does not know" rather than as a mismatch.
        """
        info = pg_catalog.types.get(oid)
        if info is None or info.oid != oid:
            return "other"
        return cls._KINDS.get(info.name, "other")

    @classmethod
    def _native_type(cls, oid: int) -> str:
        """The type as a DBA would write it, with the array form spelled out."""
        info = pg_catalog.types.get(oid)
        if info is None:
            return f"oid {oid}"
        return f"{info.regtype}[]" if info.oid != oid else info.regtype

    def columns(self, source: str) -> list[Column]:
        """Describe `source` without reading a row of it.

        The probe is built from `relation()` rather than interpolated, so a `source` containing
        a quote stays a value rather than closing the identifier (spec 009) — and a file source
        is refused here for the same reason it is refused at query time.
        """
        probe = exp.select(exp.Star()).from_(self.relation(source)).limit(0).sql(dialect="postgres")
        try:
            with self._conn.cursor() as cur:
                cur.execute(probe)
                described = cur.description or []
                return [
                    Column(
                        name=d.name,
                        native_type=self._native_type(d.type_code),
                        kind=self._kind(d.type_code),
                    )
                    for d in described
                ]
        except psycopg.Error as exc:
            self._conn.rollback()
            raise AdapterError(f"could not read {source!r}: {exc}") from exc

    def execute(self, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql)
                names = [d.name for d in cur.description or []]
                return names, [tuple(r) for r in cur.fetchall()]
        except psycopg.Error as exc:
            # Postgres leaves the transaction aborted after an error, so every later statement
            # on this connection would fail with a message about the *transaction* rather than
            # about the query that broke. Roll back so the real error is the one reported.
            self._conn.rollback()
            raise AdapterError(f"Postgres rejected the query: {exc}") from exc

    def close(self) -> None:
        self._conn.close()
