"""The loader is the only reader of the model, so its failures must be legible."""

from __future__ import annotations

from pathlib import Path

import pytest

from semantiql.knowledge.loader import ModelError, load_model
from semantiql.knowledge.model import SemanticModel


def test_loads_the_example(model: SemanticModel) -> None:
    assert model.datasource.dialect == "duckdb"
    assert model.table_names == ["orders"]
    orders = model.table("orders")
    assert orders is not None
    assert set(orders.dimensions) == {"channel", "region", "order_date"}
    assert orders.measures["revenue"].agg == "sum"
    assert orders.measures["revenue"].column == "amount"


def test_missing_file_names_the_path(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yml"
    with pytest.raises(ModelError, match=str(missing)):
        load_model(missing)


def test_unparseable_yaml_is_reported(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yml"
    bad.write_text("tables: [unclosed\n")
    with pytest.raises(ModelError, match="not parseable YAML"):
        load_model(bad)


def test_unknown_key_is_rejected_not_ignored(tmp_path: Path) -> None:
    """A typo in the model must fail loudly — a silently ignored key is a wrong number later."""
    m = tmp_path / "m.yml"
    m.write_text(
        "version: 1\n"
        "datasource: {name: t, dialect: duckdb}\n"
        "tables:\n"
        "  orders:\n"
        "    source: x.csv\n"
        "    measures:\n"
        "      revenue: {column: amount, aggregation: sum}\n"  # 'aggregation' is not 'agg'
    )
    with pytest.raises(ModelError) as exc:
        load_model(m)
    assert "aggregation" in str(exc.value)


def test_bad_aggregation_is_rejected(tmp_path: Path) -> None:
    m = tmp_path / "m.yml"
    m.write_text(
        "version: 1\n"
        "datasource: {name: t, dialect: duckdb}\n"
        "tables: {orders: {source: x.csv, measures: {revenue: {column: amount, agg: median}}}}\n"
    )
    with pytest.raises(ModelError, match="agg"):
        load_model(m)


# --- Metrics (spec 006). The expression is checked when the model loads, so a typo in a
# metric nobody has queried yet is still an error you see immediately.

_HEAD = (
    "version: 1\n"
    "datasource: {name: t, dialect: duckdb}\n"
    "tables:\n"
    "  orders:\n"
    "    source: x.csv\n"
    "    dimensions: {channel: {column: channel}}\n"
    "    measures:\n"
    "      revenue: {column: amount, agg: sum}\n"
    "      order_count: {column: order_id, agg: count}\n"
)


def _with_metric(tmp_path: Path, body: str) -> Path:
    m = tmp_path / "m.yml"
    m.write_text(_HEAD + "    metrics:\n" + body)
    return m


def test_a_metric_loads(tmp_path: Path) -> None:
    model = load_model(_with_metric(tmp_path, "      rpo: {expression: revenue / order_count}\n"))
    orders = model.table("orders")
    assert orders is not None
    assert orders.metrics["rpo"].expression == "revenue / order_count"
    assert "rpo" in orders.entity_names


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("revenue / nope", "not a measure"),
        ("channel / revenue", "not a measure"),  # a dimension is not a measure
        ("SUM(amount)", "aggregate"),
        ("UPPER(revenue)", "function"),
        ("revenue / 0", "divides by zero"),
        ("revenue >", "not a valid expression"),
    ],
)
def test_a_metric_expression_is_checked_at_load(
    expression: str, expected: str, tmp_path: Path
) -> None:
    path = _with_metric(tmp_path, f"      bad: {{expression: '{expression}'}}\n")
    with pytest.raises(ModelError) as exc:
        load_model(path)
    assert expected in str(exc.value), exc.value


def test_a_metric_may_not_reference_another_metric(tmp_path: Path) -> None:
    """Measures only — so there are no cycles to detect, and the refusal says why."""
    path = _with_metric(
        tmp_path,
        "      rpo: {expression: revenue / order_count}\n      doubled: {expression: rpo * 2}\n",
    )
    with pytest.raises(ModelError, match="not a measure"):
        load_model(path)


@pytest.mark.parametrize(
    "clash",
    [
        "    metrics: {revenue: {expression: revenue}}\n",
        "    metrics: {channel: {expression: revenue}}\n",
    ],
)
def test_a_name_is_at_most_one_kind(clash: str, tmp_path: Path) -> None:
    m = tmp_path / "m.yml"
    m.write_text(_HEAD + clash)
    with pytest.raises(ModelError, match="exactly one"):
        load_model(m)
