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


# --- A model spread over a directory (spec 015). Every ambiguity is refused, because a merge that
# silently picks a definition is the same failure the duplicate-key check exists to prevent.

from tests._support import WAREHOUSE  # noqa: E402


def _dir_model(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return tmp_path


_DATASOURCE = "version: 1\ndatasource: {name: w, dialect: duckdb}\n"
_ORDERS = (
    "tables:\n  orders:\n    source: orders\n    measures:\n      n: {column: id, agg: count}\n"
)
_TICKETS = (
    "tables:\n  tickets:\n    source: tickets\n    measures:\n      n: {column: id, agg: count}\n"
)


def test_a_directory_loads_as_one_model(tmp_path: Path) -> None:
    path = _dir_model(tmp_path, {"ds.yml": _DATASOURCE, "a.yml": _ORDERS, "b.yml": _TICKETS})
    model = load_model(path)
    assert model.table_names == ["orders", "tickets"]
    assert model.datasource.name == "w"


def test_subdirectories_contribute_too(tmp_path: Path) -> None:
    """A warehouse groups tables by team or schema, so the tree has to be walked."""
    path = _dir_model(
        tmp_path, {"ds.yml": _DATASOURCE, "sales/a.yml": _ORDERS, "support/b.yml": _TICKETS}
    )
    assert load_model(path).table_names == ["orders", "tickets"]


def test_a_table_defined_twice_is_refused_naming_both_files(tmp_path: Path) -> None:
    """The whole reason the merge is strict.

    Last-one-wins here is exactly the silent redefinition `_StrictLoader` refuses inside a file: a
    metric changes meaning and nothing says so. Both filenames appear because in a tree of thirty
    an error that could be about any of them is barely an error.
    """
    path = _dir_model(tmp_path, {"ds.yml": _DATASOURCE, "a.yml": _ORDERS, "b.yml": _ORDERS})
    with pytest.raises(ModelError) as caught:
        load_model(path)
    message = str(caught.value)
    assert "orders" in message
    assert "a.yml" in message and "b.yml" in message


def test_two_datasource_declarations_are_refused(tmp_path: Path) -> None:
    """Two cannot both be authoritative, so neither is accepted."""
    path = _dir_model(tmp_path, {"one.yml": _DATASOURCE + _ORDERS, "two.yml": _DATASOURCE})
    with pytest.raises(ModelError, match="declared in both"):
        load_model(path)


def test_a_directory_with_no_datasource_is_refused(tmp_path: Path) -> None:
    path = _dir_model(tmp_path, {"a.yml": _ORDERS})
    with pytest.raises(ModelError, match="declares `datasource`"):
        load_model(path)


def test_a_file_that_contributes_nothing_is_an_error(tmp_path: Path) -> None:
    """Skipping it would leave someone believing they had modelled a table that is absent."""
    path = _dir_model(tmp_path, {"ds.yml": _DATASOURCE, "a.yml": _ORDERS, "notes.yml": "{}\n"})
    with pytest.raises(ModelError, match="contributes nothing"):
        load_model(path)


def test_an_unrecognised_key_is_an_error_naming_it(tmp_path: Path) -> None:
    """A typo'd `tabels:` must not read as a file with nothing in it."""
    path = _dir_model(tmp_path, {"ds.yml": _DATASOURCE, "a.yml": "tabels:\n  orders: {}\n"})
    with pytest.raises(ModelError) as caught:
        load_model(path)
    assert "tabels" in str(caught.value)


def test_an_empty_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ModelError, match="no .* files"):
        load_model(_dir_model(tmp_path, {}))


def test_a_relative_source_resolves_against_its_own_file(tmp_path: Path) -> None:
    """FR-5 — the data should be able to sit beside the YAML describing it, anywhere in the tree.

    Resolving against the directory root instead would break the moment anyone grouped tables into
    subdirectories, which is the reason to use a directory at all.
    """
    path = _dir_model(
        tmp_path,
        {
            "ds.yml": _DATASOURCE,
            "sales/orders.yml": (
                "tables:\n  orders:\n    source: rows.csv\n"
                "    measures:\n      n: {column: id, agg: count}\n"
            ),
        },
    )
    (path / "sales" / "rows.csv").write_text("id\n1\n")
    resolved = load_model(path).tables["orders"].source
    assert resolved == str((path / "sales" / "rows.csv").resolve())


def test_the_bundled_warehouse_example_loads() -> None:
    """The example is documentation; if it stops loading the documentation is wrong."""
    model = load_model(WAREHOUSE)
    assert model.table_names == ["orders", "tickets"]
    # `orders` declares its source one directory up; the resolved path must be the retail CSV,
    # which is what proves per-file resolution works across a real tree rather than a fixture.
    assert model.tables["orders"].source.endswith("examples/retail/orders.csv")
    assert model.tables["tickets"].source.endswith("examples/warehouse/support/tickets.csv")


# --- The guards the loader documents at length and nothing tested.


def test_a_duplicate_key_is_refused(tmp_path: Path) -> None:
    """The check `_StrictLoader` exists for, finally under test.

    PyYAML resolves a repeated key last-wins *before* pydantic sees the data, so `extra="forbid"`
    cannot catch it. In a file that defines what revenue means, a merge conflict or a careless paste
    silently redefining a measure is exactly the wrong-number-with-no-symptom this project refuses.

    Its own docstring says so. It had no test.
    """
    path = tmp_path / "dup.yml"
    path.write_text(
        "version: 1\n"
        "datasource: {name: t, dialect: duckdb}\n"
        "tables:\n"
        "  orders:\n"
        "    source: orders\n"
        "    measures:\n"
        "      revenue: {column: amount, agg: sum}\n"
        "      revenue: {column: net, agg: avg}\n"  # the same name, twice
    )
    with pytest.raises(ModelError) as caught:
        load_model(path)
    message = str(caught.value)
    assert "revenue" in message
    assert "exactly once" in message
    assert "line" in message, "the message must locate it — a big model needs the line number"


def test_a_duplicate_table_key_is_refused(tmp_path: Path) -> None:
    """Same guard, one level up: two `orders:` blocks in one file."""
    path = tmp_path / "dup.yml"
    path.write_text(
        "version: 1\n"
        "datasource: {name: t, dialect: duckdb}\n"
        "tables:\n"
        "  orders: {source: a, measures: {n: {column: x, agg: count}}}\n"
        "  orders: {source: b, measures: {n: {column: y, agg: count}}}\n"
    )
    with pytest.raises(ModelError, match="orders"):
        load_model(path)


@pytest.mark.parametrize("content", ["- a\n- b\n", "just a string\n", "42\n"])
def test_a_file_that_is_not_a_mapping_is_refused(tmp_path: Path, content: str) -> None:
    """A list where a mapping belongs is a different file, not a model with defaults."""
    path = tmp_path / "wrong.yml"
    path.write_text(content)
    with pytest.raises(ModelError, match="mapping at the top level"):
        load_model(path)


def test_tables_must_be_a_mapping(tmp_path: Path) -> None:
    """`tables:` as a list is the shape someone writes first, so the error names it."""
    path = tmp_path / "wrong.yml"
    path.write_text("version: 1\ndatasource: {name: t, dialect: duckdb}\ntables:\n  - orders\n")
    with pytest.raises(ModelError, match="`tables` must be a mapping"):
        load_model(path)


def test_unparseable_yaml_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "broken.yml"
    path.write_text("version: 1\n  bad: indentation\n:::\n")
    with pytest.raises(ModelError) as caught:
        load_model(path)
    assert "broken.yml" in str(caught.value)


def test_a_missing_path_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ModelError, match="no semantic model at"):
        load_model(tmp_path / "absent.yml")
