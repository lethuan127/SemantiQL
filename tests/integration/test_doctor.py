"""`semantiql doctor` — the checks that find a model and a database disagreeing (spec 009).

Each case builds a deliberately broken model and asserts doctor names exactly that problem.
The engine's own tests prove what happens when a *request* does not fit the model; these prove
what happens when the *model* does not fit the database, which nothing checked before.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.doctor import check, problems
from semantiql.knowledge.loader import load_model

CSV = Path("examples/retail/orders.csv").resolve()

_HEALTHY = f"""
version: 1
datasource: {{name: retail, dialect: duckdb}}
tables:
  orders:
    source: {CSV}
    dimensions:
      channel: {{column: channel, type: string}}
      order_date: {{column: order_date, type: date}}
    measures:
      revenue: {{column: amount, agg: sum}}
      order_count: {{column: order_id, agg: count}}
"""


def _model(tmp_path: Path, yaml: str):  # type: ignore[no-untyped-def]
    path = tmp_path / "m.yml"
    path.write_text(yaml)
    return load_model(path)


@pytest.fixture
def duck() -> DuckDBAdapter:
    return DuckDBAdapter()


def test_a_healthy_model_reports_no_problems(tmp_path: Path, duck: DuckDBAdapter) -> None:
    findings = check(_model(tmp_path, _HEALTHY), duck)
    assert problems(findings) == []
    assert any("5 columns" in f.message for f in findings)


def test_a_missing_column_is_reported_with_a_suggestion(
    tmp_path: Path, duck: DuckDBAdapter
) -> None:
    yaml = _HEALTHY.replace("revenue: {column: amount", "revenue: {column: amont")
    found = problems(check(_model(tmp_path, yaml), duck))
    assert len(found) == 1
    assert "'amont'" in found[0].message
    assert "amount" in found[0].suggestions


def test_a_wrong_declared_type_is_reported(tmp_path: Path, duck: DuckDBAdapter) -> None:
    """The failure that motivated doctor: `type:` decides how filters behave."""
    yaml = _HEALTHY.replace(
        "order_date: {column: order_date, type: date}",
        "order_date: {column: order_date, type: string}",
    )
    found = problems(check(_model(tmp_path, yaml), duck))
    assert len(found) == 1
    assert "declared string" in found[0].message
    assert "DATE" in found[0].message


def test_an_impossible_aggregation_is_reported(tmp_path: Path, duck: DuckDBAdapter) -> None:
    yaml = _HEALTHY.replace(
        "revenue: {column: amount, agg: sum}", "revenue: {column: channel, agg: sum}"
    )
    found = problems(check(_model(tmp_path, yaml), duck))
    assert len(found) == 1
    assert "applies sum" in found[0].message


@pytest.mark.parametrize("agg", ["count", "count_distinct", "min", "max"])
def test_aggregations_that_apply_to_anything_are_not_reported(
    agg: str, tmp_path: Path, duck: DuckDBAdapter
) -> None:
    """Only `sum` and `avg` need arithmetic; flagging the others would be noise."""
    yaml = _HEALTHY.replace(
        "revenue: {column: amount, agg: sum}", f"revenue: {{column: channel, agg: {agg}}}"
    )
    assert problems(check(_model(tmp_path, yaml), duck)) == []


def test_an_unreadable_source_stops_that_tables_checks(tmp_path: Path, duck: DuckDBAdapter) -> None:
    """One clear problem beats a dozen 'column not found' lines under a missing table."""
    yaml = _HEALTHY.replace(str(CSV), "no_such_table")
    found = problems(check(_model(tmp_path, yaml), duck))
    assert len(found) == 1
    assert "cannot be read" in found[0].message


def test_a_dialect_mismatch_is_reported(tmp_path: Path, duck: DuckDBAdapter) -> None:
    yaml = _HEALTHY.replace("dialect: duckdb", "dialect: postgres")
    found = problems(check(_model(tmp_path, yaml), duck))
    assert any("postgres" in f.message for f in found)


def test_columns_match_case_insensitively(tmp_path: Path, duck: DuckDBAdapter) -> None:
    """DuckDB resolves identifiers case-insensitively, so doctor must not invent a problem."""
    yaml = _HEALTHY.replace("column: amount", "column: AMOUNT")
    assert problems(check(_model(tmp_path, yaml), duck)) == []


def test_several_problems_are_all_reported(tmp_path: Path, duck: DuckDBAdapter) -> None:
    """The point of the command: one pass, every mismatch, rather than one query at a time."""
    yaml = (
        _HEALTHY.replace("revenue: {column: amount", "revenue: {column: amont")
        .replace(
            "order_date: {column: order_date, type: date}",
            "order_date: {column: order_date, type: number}",
        )
        .replace(
            "order_count: {column: order_id, agg: count}", "order_count: {column: nope, agg: count}"
        )
    )
    assert len(problems(check(_model(tmp_path, yaml), duck))) == 3


# --- Grain timezones (spec 011). Checked in both directions, because both are wrong and the
# second one surprises people: declaring a zone over a naive column *moves* the buckets.

_ZONED = """
version: 1
datasource: {name: t, dialect: duckdb}
tables:
  events:
    source: events
    dimensions:
      happened_at: {column: happened_at, type: date%s}
    measures:
      n: {column: happened_at, agg: count}
"""


def _events(tmp_path: Path, timezone: str | None, column_type: str) -> tuple[Path, DuckDBAdapter]:
    """A one-column table of the given physical type, plus a model over it."""
    database = tmp_path / "events.duckdb"
    setup = duckdb.connect(str(database))
    setup.execute(f"CREATE TABLE events (happened_at {column_type})")
    setup.close()
    zone = f", timezone: {timezone}" if timezone else ""
    path = tmp_path / "zoned.yml"
    path.write_text(_ZONED % zone)
    return path, DuckDBAdapter(str(database))


def test_a_zoned_column_without_a_declaration_is_reported(tmp_path: Path) -> None:
    """Otherwise the grain buckets in the server's timezone and nobody can see it."""
    path, adapter = _events(tmp_path, timezone=None, column_type="TIMESTAMPTZ")
    try:
        reported = " ".join(f.message for f in problems(check(load_model(path), adapter)))
    finally:
        adapter.close()
    assert "server's timezone" in reported
    assert "Set `timezone:`" in reported


def test_a_declaration_over_a_naive_column_is_reported(tmp_path: Path) -> None:
    """The direction that surprises people: the declaration *moves* the buckets.

    `AT TIME ZONE` on a column with no zone does not pin anything — measured, it shifts the
    boundary on both engines. So a model author trying to do the right thing breaks their own
    numbers, and doctor has to say so.
    """
    path, adapter = _events(tmp_path, timezone="America/Chicago", column_type="TIMESTAMP")
    try:
        reported = " ".join(f.message for f in problems(check(load_model(path), adapter)))
    finally:
        adapter.close()
    assert "carries no zone" in reported
    assert "move the grain buckets" in reported


@pytest.mark.parametrize(
    ("timezone", "column_type"),
    [("UTC", "TIMESTAMPTZ"), (None, "TIMESTAMP"), (None, "DATE")],
)
def test_a_matching_declaration_is_silent(
    tmp_path: Path, timezone: str | None, column_type: str
) -> None:
    """All three agreeing combinations. A check that fires on a correct model is noise."""
    path, adapter = _events(tmp_path, timezone=timezone, column_type=column_type)
    try:
        assert problems(check(load_model(path), adapter)) == []
    finally:
        adapter.close()
