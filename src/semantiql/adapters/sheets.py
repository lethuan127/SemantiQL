"""Google Sheets — a datasource with no query engine of its own (spec 023).

Every other adapter hands transpiled SQL to a database and gets rows back. Sheets cannot do that:
its
API returns cell ranges. There were two ways out and only one keeps the engine honest.

**The rejected way** was to interpret the SQL here — filter, group and aggregate in Python. That is
a
second query implementation, and the first time it disagreed with DuckDB about a `NULL` inside an
average, the result would be a wrong number rather than an error. N2 settles it.

**The chosen way** is to *borrow* DuckDB. The adapter fetches the worksheet once, loads it into an
in-memory DuckDB relation, and executes the canonical SQL against that. So `dialect` is
**`duckdb`** —
not a pretence that Sheets speaks SQL, but a statement of which engine will run the query. Nothing
is
reimplemented, `compile.py` never learns this datasource exists, and `doctor` and `profile` work for
free because they only ever talk to the Protocol.

**The honest limit: the whole range is fetched when the adapter opens.** That is right for a
spreadsheet, which is small by construction, and wrong for anything large. It is why this is a
Sheets
adapter and not a warehouse one, and it is documented rather than optimised.

**Types are inferred from text**, because that is all the API returns. DuckDB applies the same
inference
it already uses for a CSV, so a `source` here behaves like a `.csv` source — including the failure
mode
where one stray word in a numeric column makes the whole column text. `doctor` is what catches that.

**Read-only** twice over: this adapter has no write path, and the Sheets scope requested is the
read-only one. As everywhere else, the guarantee also rests on `validate` refusing every
non-`SELECT`.
"""

from __future__ import annotations

from typing import Any

import duckdb
from sqlglot import exp

from semantiql.adapters.base import AdapterError, Column, RelationProfile
from semantiql.adapters.duckdb import DuckDBAdapter

#: The OAuth scope. Read-only, and named here so the narrowest possible grant is the default rather
#: than something a reader has to know to ask for.
SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"

#: How much of a worksheet to ask for. Sheets requires a range; this covers a spreadsheet-sized
#: sheet
#: and bounds a runaway one.
_RANGE = "A1:ZZ50000"


class SheetsAdapter:
    """A read-only Google Sheets connection that executes through an in-memory DuckDB.

    `source` names a worksheet — the tab's title — and its columns come from the first row.
    """

    def __init__(
        self,
        spreadsheet_id: str = "",
        credentials_file: str = "",
        rows: dict[str, list[list[str]]] | None = None,
    ) -> None:
        """Open the spreadsheet, or accept `rows` directly.

        `rows` exists for tests, and it is the reason most of this adapter is testable without a
        Google
        account: everything after the fetch is ordinary DuckDB. It maps a worksheet title to its
        cell
        rows, header first.
        """
        self._duck = DuckDBAdapter()
        self._loaded: set[str] = set()

        if rows is not None:
            for title, values in rows.items():
                self._load(title, values)
            self._service = None
            self._spreadsheet_id = ""
            return

        # The driver first, then the credentials. A missing extra is the more fundamental blocker —
        # no amount of correct configuration helps without it — and checking it first keeps this
        # adapter's failure order the same as the Databricks one's.
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on an optional extra
            raise AdapterError(
                "the Google Sheets client is not installed. It is an optional extra, so that a "
                "clone stays light:\n  uv sync --extra sheets\n"
                "or  pip install 'semantiql[sheets]'"
            ) from exc

        missing = [
            name
            for name, value in (
                ("--sheet-id / SEMANTIQL_SHEET_ID", spreadsheet_id),
                ("--sheet-credentials / SEMANTIQL_SHEET_CREDENTIALS", credentials_file),
            )
            if not value
        ]
        if missing:
            # Named, because "authentication failed" sends the reader to Google when the real
            # problem is an unset variable.
            raise AdapterError("Google Sheets needs " + ", ".join(missing))

        try:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_file, scopes=[SCOPE]
            )
            self._service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        except Exception as exc:
            raise AdapterError(f"could not authenticate to Google Sheets: {exc}") from exc
        self._spreadsheet_id = spreadsheet_id

    @property
    def dialect(self) -> str:
        """`duckdb`, because DuckDB is the engine this adapter borrows.

        Not a claim that Sheets speaks SQL. The dialect names the SQL the adapter will be *handed*,
        and
        it will be handed DuckDB SQL because DuckDB is what executes it.
        """
        return "duckdb"

    def relation(self, source: str) -> exp.Expr:
        """The worksheet as a selectable relation, fetching it on first use."""
        self._ensure(source)
        return exp.to_table(self._table_name(source))

    def tables(self) -> list[str]:
        """Every worksheet in the spreadsheet.

        This is the one member that must talk to the API even when nothing has been queried, because
        the whole point of `inspect` is to run before a model exists.
        """
        if self._service is None:
            return sorted(self._loaded)
        try:
            meta = (
                self._service.spreadsheets()
                .get(spreadsheetId=self._spreadsheet_id, fields="sheets.properties.title")
                .execute()
            )
        except Exception as exc:
            raise AdapterError(f"could not list worksheets: {exc}") from exc
        return sorted(str(s["properties"]["title"]) for s in meta.get("sheets", []))

    def columns(self, source: str) -> list[Column]:
        """Describe the worksheet's columns, as DuckDB inferred them from the text."""
        self._ensure(source)
        return self._duck.columns(self._table_name(source))

    def profile(self, source: str) -> RelationProfile:
        """What is in the worksheet. Delegated, and then relabelled with the caller's own name."""
        self._ensure(source)
        profiled = self._duck.profile(self._table_name(source))
        return RelationProfile(source=source, rows=profiled.rows, columns=profiled.columns)

    def execute(self, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Run already-validated, already-transpiled SQL against the loaded sheet."""
        return self._duck.execute(sql)

    def close(self) -> None:
        self._duck.close()

    @staticmethod
    def _table_name(source: str) -> str:
        """A worksheet title as a DuckDB table name.

        Titles can contain spaces and punctuation, so they are not usable as identifiers directly.
        The
        mapping is deliberately dull and reversible enough to recognise in an error message.
        """
        return "sheet_" + "".join(c if c.isalnum() else "_" for c in source).strip("_").lower()

    def _ensure(self, source: str) -> None:
        """Fetch and load a worksheet once."""
        if source in self._loaded:
            return
        if self._service is None:
            raise AdapterError(
                f"worksheet {source!r} was not loaded. Known worksheets: "
                f"{', '.join(sorted(self._loaded)) or 'none'}"
            )
        try:
            response = (
                self._service.spreadsheets()
                .values()
                .get(spreadsheetId=self._spreadsheet_id, range=f"'{source}'!{_RANGE}")
                .execute()
            )
        except Exception as exc:
            raise AdapterError(f"could not read worksheet {source!r}: {exc}") from exc
        self._load(source, [[str(cell) for cell in row] for row in response.get("values", [])])

    def _load(self, source: str, values: list[list[str]]) -> None:
        """Load cell rows into DuckDB, letting it infer types the way it would for a CSV.

        Written as CSV text and read back through DuckDB's own reader rather than assembled with
        `INSERT`s: the reader is where the type inference lives, so this gets the same behaviour a
        `.csv` source already gets, including how it treats blanks as NULL.
        """
        if not values:
            raise AdapterError(f"worksheet {source!r} is empty — there is no header row to model")
        header, *body = values
        if not any(name.strip() for name in header):
            raise AdapterError(f"worksheet {source!r} has no usable header row")

        width = len(header)
        lines = [",".join(self._escape(name) for name in header)]
        for row in body:
            padded = list(row[:width]) + [""] * (width - len(row))
            lines.append(",".join(self._escape(cell) for cell in padded))

        table = self._table_name(source)
        try:
            self._duck._conn.execute(
                f'CREATE OR REPLACE TABLE "{table}" AS '
                "SELECT * FROM read_csv_auto(?, all_varchar = false, header = true)",
                ["\n".join(lines)],
            )
        except duckdb.Error:
            # `read_csv_auto` over a literal string is not universally supported; fall back to a
            # temporary file, which is the same reader and therefore the same inference.
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "sheet.csv"
                path.write_text("\n".join(lines))
                try:
                    self._duck._conn.execute(
                        f'CREATE OR REPLACE TABLE "{table}" AS '
                        f"SELECT * FROM read_csv_auto('{path}', header = true)"
                    )
                except duckdb.Error as exc:
                    raise AdapterError(f"could not load worksheet {source!r}: {exc}") from exc
        self._loaded.add(source)

    @staticmethod
    def _escape(cell: str) -> str:
        """One CSV field. Quotes doubled, and anything with a comma or newline quoted."""
        text = cell.replace('"', '""')
        return f'"{text}"' if any(c in cell for c in ',"\n\r') else text
