"""The Google Sheets adapter (spec 023).

**Nothing here has touched a real spreadsheet.** There is no service-account credential on this
machine, and the Google client is an optional extra that is not installed by default. What is *not*
verified is the fetch: `spreadsheets.values.get`, the auth, and how a real sheet's quirks arrive.

Almost everything else is verified, and that is a property of the design rather than luck. The
adapter
takes `rows=` so cell values can be injected, and after the fetch it is ordinary DuckDB — which is
the
whole argument for borrowing a query engine instead of writing one. If this adapter interpreted SQL
itself, this file would be a long list of untested branches.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from semantiql.adapters.base import AdapterError
from semantiql.adapters.sheets import SheetsAdapter

BUDGET = [
    ["team", "spend", "approved_at", "active"],
    ["Platform", "12500.50", "2026-01-15", "true"],
    ["Growth", "8200.00", "2026-02-01", "false"],
    ["Platform", "3100.25", "2026-03-10", "true"],
]


@pytest.fixture
def sheet() -> Iterator[SheetsAdapter]:
    adapter = SheetsAdapter(rows={"Budget 2026": BUDGET})
    yield adapter
    adapter.close()


def test_the_dialect_is_duckdb_because_duckdb_is_the_engine(sheet: SheetsAdapter) -> None:
    """Not a claim that Sheets speaks SQL.

    The dialect names the SQL the adapter will be *handed*, and it will be handed DuckDB's because
    DuckDB executes it. Naming a `sheets` dialect sqlglot has never heard of would break
    transpilation
    for nothing.
    """
    assert sheet.dialect == "duckdb"


def test_types_are_inferred_from_text_the_way_a_csv_is(sheet: SheetsAdapter) -> None:
    """The API returns strings, so inference is the only option — and it is DuckDB's own.

    Worth asserting because it is the adapter's most surprising behaviour: a column of numerals
    becomes
    numeric, and a date becomes a `DATE`, without anyone declaring it. The failure mode is the
    same one
    a `.csv` source has — one stray word makes the whole column text — and `doctor` is what
    catches it.
    """
    kinds = {c.name: c.kind for c in sheet.columns("Budget 2026")}
    assert kinds == {
        "team": "string",
        "spend": "number",
        "approved_at": "date",
        "active": "boolean",
    }


def test_no_column_claims_to_carry_a_timezone(sheet: SheetsAdapter) -> None:
    """A spreadsheet has no zone-aware type, so a model over one must never set `timezone:`.

    Declaring one on a naive column moves the buckets rather than pinning them, which is the
    direction
    spec 011's second `doctor` check exists to catch.
    """
    assert not any(c.carries_timezone for c in sheet.columns("Budget 2026"))


def test_a_query_runs_and_aggregates_correctly(sheet: SheetsAdapter) -> None:
    """The reason for borrowing DuckDB, in one assertion.

    12500.50 + 3100.25 = 15600.75. A hand-rolled aggregation layer would have to get this right, and
    every other case, and agree with DuckDB about every `NULL` — and its first disagreement would
    be a
    wrong number rather than an error (N2).
    """
    relation = sheet.relation("Budget 2026").sql()
    names, rows = sheet.execute(
        f"SELECT team, SUM(spend) AS total FROM {relation} GROUP BY team ORDER BY total DESC"
    )
    assert names == ["team", "total"]
    assert rows == [("Platform", 15600.75), ("Growth", 8200.0)]


def test_profile_reports_what_is_in_the_sheet(sheet: SheetsAdapter) -> None:
    """`profile` works for free, because it only ever talks to the Protocol."""
    profile = sheet.profile("Budget 2026")
    assert profile.source == "Budget 2026", (
        "the caller's own name should come back, not the internal one"
    )
    assert profile.rows == 3
    by_name = {c.name: c for c in profile.columns}
    assert float(str(by_name["spend"].total)) == pytest.approx(23800.75)
    assert by_name["team"].values is not None
    assert dict(by_name["team"].values) == {"Platform": 2, "Growth": 1}


def test_a_worksheet_title_becomes_a_usable_table_name(sheet: SheetsAdapter) -> None:
    """Titles carry spaces and punctuation, so they are not identifiers.

    The mapping is deliberately dull, and reversible enough to recognise in an error message.
    """
    assert sheet.relation("Budget 2026").sql() == "sheet_budget_2026"


def test_an_empty_worksheet_is_refused_with_the_reason() -> None:
    """No header row means no columns, and a model over it would resolve nothing.

    Refusing here beats producing a table with no columns, which would fail later as a confusing
    `doctor` result about a source that "has 0 columns".
    """
    with pytest.raises(AdapterError, match="empty"):
        SheetsAdapter(rows={"Blank": []})


def test_a_worksheet_with_no_header_is_refused() -> None:
    with pytest.raises(AdapterError, match="header"):
        SheetsAdapter(rows={"Odd": [["", "", ""], ["a", "b", "c"]]})


def test_a_short_row_is_padded_rather_than_dropped() -> None:
    """Spreadsheets omit trailing empty cells, so a short row is normal rather than corrupt.

    Dropping the row would silently lose data; failing on it would make the adapter unusable on real
    sheets, where the last column is often blank.
    """
    adapter = SheetsAdapter(rows={"S": [["a", "b", "c"], ["1", "2"], ["3", "4", "5"]]})
    try:
        _, rows = adapter.execute("SELECT count(*) FROM sheet_s")
        assert rows == [(2,)]
    finally:
        adapter.close()


def test_a_cell_containing_a_comma_survives() -> None:
    """Values reach DuckDB's reader as CSV, so escaping is this adapter's problem.

    An unescaped comma would shift every later column by one, which is the kind of corruption that
    produces a plausible wrong number rather than an error.
    """
    adapter = SheetsAdapter(rows={"S": [["name", "n"], ["Smith, John", "7"]]})
    try:
        _, rows = adapter.execute("SELECT name, n FROM sheet_s")
        assert rows == [("Smith, John", 7)]
    finally:
        adapter.close()


def test_tables_lists_the_loaded_worksheets(sheet: SheetsAdapter) -> None:
    assert sheet.tables() == ["Budget 2026"]


def test_an_unknown_worksheet_is_refused_naming_what_exists(sheet: SheetsAdapter) -> None:
    with pytest.raises(AdapterError) as caught:
        sheet.columns("Nope")
    assert "Budget 2026" in str(caught.value)


def test_a_missing_credential_is_refused_by_name() -> None:
    """Only reachable with the extra installed — the driver check comes first, deliberately."""
    pytest.importorskip("googleapiclient.discovery", reason="the sheets extra is not installed")
    with pytest.raises(AdapterError) as caught:
        SheetsAdapter(spreadsheet_id="abc123")
    assert "SEMANTIQL_SHEET_CREDENTIALS" in str(caught.value)


def test_a_missing_driver_says_how_to_install_it() -> None:
    """The failure a fresh clone gets, and it must be an instruction rather than a traceback."""
    import importlib.util

    if importlib.util.find_spec("googleapiclient") is not None:
        pytest.skip("the sheets extra is installed, so this path cannot be reached")
    with pytest.raises(AdapterError) as caught:
        SheetsAdapter(spreadsheet_id="abc", credentials_file="creds.json")
    assert "uv sync --extra sheets" in str(caught.value)


def test_the_read_only_scope_is_the_one_requested() -> None:
    """The narrowest grant that works, as the default rather than something to know to ask for."""
    from semantiql.adapters.sheets import SCOPE

    assert SCOPE.endswith(".readonly")
