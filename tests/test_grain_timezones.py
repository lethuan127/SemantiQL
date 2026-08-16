"""A time grain must not depend on the database server's timezone (spec 011).

Everything here is checked without a database, because everything here is decided before one is
reached: the model validates at load, and the SQL is built from the model. The half that needs
two live engines is `tests/test_postgres_differential.py`.

The fault being prevented is worth restating, because the code reads as harmless otherwise.
`DATE_TRUNC` over a bare column buckets in the **database server's** timezone. Both engines do
it, so no differential test can catch it, and the person reading the number can see neither the
setting nor the difference. A row at `2026-07-01T02:00:00Z` lands in July on a server in UTC and
in June on one in `America/Chicago`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlglot import exp

from semantiql.engine.compile import compile_request
from semantiql.engine.validate import ValidRequest, validate
from semantiql.knowledge.loader import ModelError, load_model
from semantiql.knowledge.model import Dimension, SemanticModel

ORDERS = exp.to_table("orders")

_MODEL = """
version: 1
datasource:
  name: t
  dialect: {dialect}
tables:
  orders:
    source: orders
    dimensions:
      order_date:
        column: order_date
        type: date
{timezone}
    measures:
      revenue:
        column: amount
        agg: sum
"""


def _model(tmp_path: Path, timezone: str | None = None, dialect: str = "duckdb") -> SemanticModel:
    zone = f"        timezone: {timezone}\n" if timezone else ""
    path = tmp_path / "m.yml"
    path.write_text(_MODEL.format(dialect=dialect, timezone=zone))
    return load_model(path)


def _sql(model: SemanticModel, dialect: str = "duckdb") -> str:
    request = validate("SELECT revenue, DATE_TRUNC('month', order_date) FROM orders", model)
    assert isinstance(request, ValidRequest), request
    return compile_request(request, model, relation=ORDERS, dialect=dialect)


# --- The model field (AD-2, AD-3)


def test_a_valid_zone_loads(tmp_path: Path) -> None:
    model = _model(tmp_path, timezone="America/Chicago")
    assert model.tables["orders"].dimensions["order_date"].timezone == "America/Chicago"


def test_no_zone_is_the_default(tmp_path: Path) -> None:
    """Absent is the common case, and it must stay absent rather than defaulting to UTC.

    Defaulting would answer a question nobody asked: "revenue by month in UTC" is not the same
    question as "revenue by month where the business operates", and the answer would look
    perfectly reasonable either way.
    """
    assert _model(tmp_path).tables["orders"].dimensions["order_date"].timezone is None


def test_an_unknown_zone_is_refused_at_load(tmp_path: Path) -> None:
    """A typo is a model error, not a mystery at query time."""
    with pytest.raises(ModelError) as caught:
        _model(tmp_path, timezone="America/Chigago")
    assert "America/Chigago" in str(caught.value)
    assert "IANA" in str(caught.value)


def test_a_zone_on_a_non_date_dimension_is_refused() -> None:
    """A key that silently does nothing is how a model grows lies."""
    with pytest.raises(ValidationError) as caught:
        Dimension(column="channel", type="string", timezone="UTC")
    assert "only means something for a date dimension" in str(caught.value)


# --- The emitted SQL (AD-1, AD-5)


def test_without_a_zone_the_column_is_cast(tmp_path: Path) -> None:
    """The cast is what stops Postgres reaching for its timestamptz overload.

    On DuckDB it is a no-op, which is exactly why it looks deletable and is not: remove it and
    Postgres starts answering differently from DuckDB, and differently from itself on a host
    configured to another timezone.
    """
    assert "DATE_TRUNC('MONTH', CAST(order_date AS TIMESTAMP))" in _sql(_model(tmp_path))


def test_with_a_zone_the_column_is_converted(tmp_path: Path) -> None:
    compiled = _sql(_model(tmp_path, timezone="America/Chicago"))
    assert "AT TIME ZONE 'America/Chicago'" in compiled, compiled
    assert "CAST(order_date AS TIMESTAMP)" not in compiled, compiled


def test_the_two_shapes_are_mutually_exclusive(tmp_path: Path) -> None:
    """Never both. A cast then a conversion would truncate in a third, unnamed zone."""
    cast_only = _sql(_model(tmp_path))
    zoned_only = _sql(_model(tmp_path, timezone="UTC"))
    assert "AT TIME ZONE" not in cast_only
    assert "CAST(" not in zoned_only.split("FROM")[0].replace("SUM(amount)", "")


def test_the_group_by_repeats_whichever_shape_was_used(tmp_path: Path) -> None:
    """GROUP BY names the expression, not the alias — so it must carry the same conversion.

    If the projection converted and the grouping did not, the rows would be bucketed one way
    and labelled another. Every row would look plausible and the totals would be wrong.
    """
    for zone in (None, "America/Chicago"):
        compiled = _sql(_model(tmp_path, timezone=zone))
        projection, grouping = compiled.split("GROUP BY")
        shape = "AT TIME ZONE 'America/Chicago'" if zone else "CAST(order_date AS TIMESTAMP)"
        assert shape in projection, compiled
        assert shape in grouping, compiled


def test_a_zone_containing_a_quote_stays_a_value(tmp_path: Path) -> None:
    """The zone is built as a literal, never spliced into SQL text.

    An unknown zone is refused at load, so this is unreachable through the model today. It is
    asserted at the builder anyway: `relation()` and every filter literal hold the same
    property, and the one place that stops holding it is the one that gets exploited.
    """
    built = exp.AtTimeZone(this=exp.column("c"), zone=exp.Literal.string("x' OR '1"))
    assert built.sql(dialect="duckdb") == "c AT TIME ZONE 'x'' OR ''1'"


@pytest.mark.parametrize("dialect", ["duckdb", "postgres"])
def test_both_mvp_dialects_render_the_zoned_form(tmp_path: Path, dialect: str) -> None:
    """N4: one canonical statement, and neither MVP engine needs a special case."""
    model = _model(tmp_path, timezone="UTC", dialect=dialect)
    assert "AT TIME ZONE 'UTC'" in _sql(model, dialect=dialect)
