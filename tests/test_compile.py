"""Compilation turns model semantics into SQL, and transpiles without relearning dialects."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import sqlglot
from sqlglot import exp

from semantiql.engine.compile import compile_request
from semantiql.engine.validate import Refusal, ValidRequest, validate
from semantiql.knowledge.loader import load_model
from semantiql.knowledge.model import SemanticModel

ORDERS = exp.to_table("orders")


def _valid(sql: str, model: SemanticModel) -> ValidRequest:
    request = validate(sql, model)
    assert isinstance(request, ValidRequest), request
    return request


def _distinct_model() -> SemanticModel:
    """A tiny model with a count_distinct measure, for dialect-rendering checks."""
    m = Path(tempfile.mkdtemp()) / "m.yml"
    m.write_text(
        "version: 1\n"
        "datasource: {name: t, dialect: duckdb}\n"
        "tables:\n"
        "  orders:\n"
        "    source: orders\n"
        "    measures: {buyers: {column: order_id, agg: count_distinct}}\n"
    )
    return load_model(m)


def test_measure_becomes_its_sanctioned_aggregation(model: SemanticModel) -> None:
    sql = compile_request(
        _valid("SELECT revenue FROM orders", model), model, relation=ORDERS, dialect="duckdb"
    )
    assert "SUM(AMOUNT) AS REVENUE" in sql.upper().replace('"', "")


def test_dimension_drives_group_by(model: SemanticModel) -> None:
    sql = compile_request(
        _valid("SELECT revenue, channel FROM orders", model),
        model,
        relation=ORDERS,
        dialect="duckdb",
    ).upper()
    assert "GROUP BY" in sql
    assert "CHANNEL" in sql


def test_transpiling_is_currently_a_no_op_for_everything_we_emit(model: SemanticModel) -> None:
    """A tripwire, and an honest record of a limitation.

    The SQL this engine emits today — aliased columns, one aggregate, a GROUP BY — is
    spelled identically in every dialect sqlglot knows. So the transpile step is wired but
    *unexercised*: deleting `sqlglot.transpile` from `compile_request` would not change any
    output, and no test could catch it. The previous test here pretended otherwise by
    asserting on `COUNT(...)` and `GROUP BY`, which are dialect-invariant.

    This test asserts the true state instead. **It is meant to fail** the moment the engine
    starts emitting something dialect-specific (a date truncation, a string function, a
    LIMIT). When it does, replace it with a real assertion that the target rendering
    differs — that is the point at which constitution N4's transpiling claim becomes
    testable.
    """
    request = _valid("SELECT revenue, order_date FROM orders", model)
    rendered = {
        d: compile_request(request, model, relation=ORDERS, dialect=d)
        for d in ("duckdb", "postgres", "tsql", "spark", "mysql", "bigquery", "snowflake")
    }
    assert len(set(rendered.values())) == 1, (
        "a dialect now renders differently — good. Replace this tripwire with a real "
        f"transpile assertion: {rendered}"
    )


def test_count_distinct_is_rendered_distinctly() -> None:
    other = _distinct_model()
    sql = compile_request(
        _valid("SELECT buyers FROM orders", other), other, relation=ORDERS, dialect="duckdb"
    )
    assert "DISTINCT" in sql.upper()


def test_requested_column_order_is_preserved(model: SemanticModel) -> None:
    """A caller indexing rows positionally must get the columns it asked for, in order."""
    sql = compile_request(
        _valid("SELECT revenue, channel FROM orders", model),
        model,
        relation=ORDERS,
        dialect="duckdb",
    ).upper()
    assert sql.index("REVENUE") < sql.index("CHANNEL")


def test_alias_is_honoured_not_discarded(model: SemanticModel) -> None:
    """`SELECT revenue AS total` used to come back as `revenue`, silently."""
    sql = compile_request(
        _valid("SELECT revenue AS total FROM orders", model),
        model,
        relation=ORDERS,
        dialect="duckdb",
    )
    assert "AS total" in sql.replace('"', "")


def test_relation_is_never_reparsed(model: SemanticModel) -> None:
    """A model `source` containing a quote must not escape into the FROM clause.

    Regression for an injection: when the relation was passed as a string, `from_()`
    re-parsed it, so a crafted `source` could add relations the model never declared.
    """
    from semantiql.adapters.duckdb import DuckDBAdapter

    hostile = "/tmp/a.csv') , read_csv_auto('/tmp/secret.csv"
    relation = DuckDBAdapter.relation(hostile)
    sql = compile_request(
        _valid("SELECT revenue FROM orders", model), model, relation=relation, dialect="duckdb"
    )
    # Count real call nodes, not text occurrences: the payload contains the *text*
    # "read_csv_auto" inside the escaped literal, so a substring count would read 2.
    parsed = sqlglot.parse_one(sql, read="duckdb")
    calls = [n for n in parsed.find_all(exp.Anonymous) if n.name.lower() == "read_csv_auto"]
    assert len(calls) == 1, f"injection produced {len(calls)} reader calls: {sql}"
    assert "secret.csv" in sql  # present, but inert, inside the literal


# --- Filters (spec 004). The predicate is rebuilt from the model, so these tests check the
# two things a rebuild can get wrong: losing a negation, and letting a value become syntax.


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT revenue FROM orders WHERE channel = 'web'", "channel = 'web'"),
        ("SELECT revenue FROM orders WHERE channel <> 'web'", "channel <> 'web'"),
        ("SELECT revenue FROM orders WHERE channel IN ('web', 'retail')", "IN ('web', 'retail')"),
        ("SELECT revenue FROM orders WHERE channel LIKE 'we%'", "channel LIKE 'we%'"),
        ("SELECT revenue FROM orders WHERE channel IS NULL", "channel IS NULL"),
        (
            "SELECT revenue FROM orders WHERE order_date BETWEEN '2026-07-01' AND '2026-07-31'",
            "BETWEEN CAST('2026-07-01' AS DATE) AND CAST('2026-07-31' AS DATE)",
        ),
    ],
)
def test_each_predicate_renders(sql: str, expected: str, model: SemanticModel) -> None:
    compiled = compile_request(_valid(sql, model), model, relation=ORDERS, dialect="duckdb")
    assert expected in compiled, compiled


def test_a_negation_carried_as_a_flag_survives_the_rebuild(model: SemanticModel) -> None:
    """`NOT LIKE` is `Like(negate=True)` — a flag, not a wrapper.

    Rebuilding the node without reading it would emit `LIKE`, answering a question about web
    orders when the caller excluded them. Nothing else in the output would look wrong.
    """
    compiled = compile_request(
        _valid("SELECT revenue FROM orders WHERE channel NOT LIKE 'we%'", model),
        model,
        relation=ORDERS,
        dialect="duckdb",
    )
    assert "NOT" in compiled.upper(), compiled


def test_a_date_filter_is_cast_not_coerced(model: SemanticModel) -> None:
    """Engines disagree on implicit string-to-date coercion, so the cast is explicit (N3)."""
    compiled = compile_request(
        _valid("SELECT revenue FROM orders WHERE order_date >= '2026-07-01'", model),
        model,
        relation=ORDERS,
        dialect="duckdb",
    )
    assert "CAST('2026-07-01' AS DATE)" in compiled, compiled


def test_a_hostile_filter_value_cannot_add_structure(model: SemanticModel) -> None:
    """The relation-injection lesson, applied to values a caller supplies.

    Every literal is built as an expression, never spliced as text, so a quote inside a filter
    value is escaped and stays data.
    """
    hostile = "web' OR 1=1 --"
    quoted = hostile.replace("'", "''")
    compiled = compile_request(
        _valid(f"SELECT revenue FROM orders WHERE channel = '{quoted}'", model),
        model,
        relation=ORDERS,
        dialect="duckdb",
    )
    parsed = sqlglot.parse_one(compiled, read="duckdb")
    where = parsed.args["where"]
    assert isinstance(where.this, exp.EQ), f"the value changed the predicate's shape: {compiled}"
    assert where.this.expression.this == hostile, compiled
    assert not list(parsed.find_all(exp.Or)), f"injected an OR: {compiled}"


def test_an_unescaped_quote_is_refused_rather_than_executed(model: SemanticModel) -> None:
    """The other half: text that breaks out of its literal never becomes a second predicate.

    Written unescaped, `channel = 'web' OR 1=1 --` parses as a real `OR` whose right side is
    not a dimension comparison, so validation refuses it. Neither route reaches the database
    with a predicate the model did not authorise.
    """
    outcome = validate("SELECT revenue FROM orders WHERE channel = 'web' OR 1=1 --", model)
    assert isinstance(outcome, Refusal), outcome
