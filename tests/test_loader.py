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
