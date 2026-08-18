"""FR-5 / constitution N1, N2 — the tests that matter most in this repo.

A plausible wrong number is the worst possible output, because the end user never sees SQL
and cannot catch it. So: an unresolvable request must be refused, and crucially the
database must never be touched on that path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlglot import exp

from semantiql.adapters.base import Column
from semantiql.engine.run import run
from semantiql.engine.validate import _CLAUSE_LABELS, Refusal, ValidRequest, validate
from semantiql.knowledge.loader import load_model
from semantiql.knowledge.model import SemanticModel


class ExplodingAdapter:
    """Satisfies Adapter structurally, and fails the test if anything reaches the data.

    This is the assertion that makes N1 real: not merely "a refusal came back", but
    "no query was executed".
    """

    @property
    def dialect(self) -> str:
        return "duckdb"

    def relation(self, source: str) -> exp.Expr:  # pragma: no cover
        raise AssertionError(f"a refused request resolved a relation: {source!r}")

    def tables(self) -> list[str]:  # pragma: no cover
        raise AssertionError("a refused request enumerated the datasource")

    def columns(self, source: str) -> list[Column]:  # pragma: no cover
        raise AssertionError("validation must run before the adapter is consulted")

    def execute(self, sql: str) -> tuple[list[str], list[tuple[object, ...]]]:  # pragma: no cover
        raise AssertionError(f"a refused request reached the database: {sql!r}")

    def close(self) -> None:
        """Nothing is held open, so this no-ops — and it must not explode.

        Unlike the three above, closing is not evidence that a refused request reached the
        data: the CLI closes in a `finally`, so a *correctly* refused request still closes.
        """


def test_unknown_measure_is_refused_and_never_executed(model: SemanticModel) -> None:
    outcome = run("SELECT profit FROM orders", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)
    assert "profit" in outcome.reason


def test_unknown_table_is_refused(model: SemanticModel) -> None:
    outcome = run("SELECT revenue FROM invoices", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)
    assert "invoices" in outcome.reason


def test_refusal_suggests_but_does_not_substitute(model: SemanticModel) -> None:
    """A near-miss gets a suggestion — and still refuses, rather than guessing for you."""
    outcome = validate("SELECT revenu, channel FROM orders", model)
    assert isinstance(outcome, Refusal)
    assert "revenue" in outcome.did_you_mean


def test_write_statements_are_refused(model: SemanticModel) -> None:
    """Read-only by default (N5) — enforced before the adapter, not by the adapter."""
    outcome = run("DELETE FROM orders", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)


def test_selecting_no_measure_is_refused(model: SemanticModel) -> None:
    """Dimensions alone compute nothing; refusing beats returning a bare column dump."""
    outcome = run("SELECT channel FROM orders", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)
    assert "no measure" in outcome.reason


def test_a_valid_request_passes_validation(model: SemanticModel) -> None:
    outcome = validate("SELECT revenue, channel FROM orders", model)
    assert isinstance(outcome, ValidRequest)
    assert outcome.measures == ("revenue",)
    assert outcome.dimensions == ("channel",)


# --- Clauses the compiler does not implement must be refused, not silently dropped.
#
# This is the regression suite for the worst defect this engine can have: `compile_request`
# rebuilds the query from the model, so any clause left unvalidated simply disappears and
# the caller receives a confidently wrong number. Every entry here was a silent wrong
# answer before the fix.


@pytest.mark.parametrize(
    "sql",
    [
        # `WHERE` left this list in spec 004, which taught the compiler to build a predicate.
        # What a filter may contain is now its own suite, further down.
        "SELECT revenue, channel FROM orders HAVING SUM(amount) > 900",
        # `ORDER BY`, `LIMIT` and `OFFSET` left this list in spec 005, which taught the
        # compiler to build them. What they may contain is its own suite, further down.
        "SELECT DISTINCT revenue FROM orders",
        "SELECT revenue, channel FROM orders GROUP BY channel",
        "WITH x AS (SELECT 1 AS revenue) SELECT revenue FROM orders",
        "SELECT revenue FROM (SELECT * FROM orders)",
        "SELECT revenue FROM orders JOIN other ON 1 = 1",
        "SELECT revenue FROM orders, other",
        "SELECT revenue FROM orders UNION SELECT revenue FROM orders",
        # Attached to the table rather than to the SELECT. These two were listed by name in
        # the old denylist and still slipped through, because it only read the SELECT's own
        # arguments — both were accepted and the clause discarded (spec 003).
        "SELECT revenue FROM orders TABLESAMPLE (10 PERCENT)",
        "SELECT revenue FROM orders PIVOT (SUM(amount) FOR channel IN ('web'))",
        "SELECT revenue FROM orders UNPIVOT (v FOR k IN (amount))",
        # Stored as a bare flag on the table rather than as a node, so walking expressions
        # does not see them. `ONLY` excludes inheriting child tables on Postgres, so dropping
        # it changes which rows exist.
        "SELECT revenue FROM ONLY orders",
        "SELECT revenue FROM orders WITH ORDINALITY",
    ],
)
def test_unsupported_clauses_are_refused_never_dropped(sql: str, model: SemanticModel) -> None:
    outcome = run(sql, model, ExplodingAdapter())
    assert isinstance(outcome, Refusal), f"silently accepted and would drop a clause: {sql}"


def test_the_refusal_names_the_clause(model: SemanticModel) -> None:
    """A refusal a user cannot act on is only half useful."""
    outcome = run(
        "SELECT revenue, channel FROM orders HAVING SUM(amount) > 900", model, ExplodingAdapter()
    )
    assert isinstance(outcome, Refusal)
    assert "HAVING" in outcome.reason


def test_the_refusal_names_a_table_level_clause(model: SemanticModel) -> None:
    outcome = run("SELECT revenue FROM orders TABLESAMPLE (10 PERCENT)", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)
    assert "TABLESAMPLE" in outcome.reason


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT revenue INTO t FROM orders",
        "SELECT revenue FROM orders START WITH 1 = 1 CONNECT BY 1 = 1",
    ],
)
def test_a_construct_nobody_enumerated_is_still_refused(sql: str, model: SemanticModel) -> None:
    """The point of the allowlist: refusal must not depend on having anticipated the clause.

    `INTO` appears in no label map, so the refusal is decided by its absence from
    `_SELECT_ARGS` and named from the parsed request. If refusing ever starts depending on a
    lookup, this test is what notices.
    """
    assert "into" not in _CLAUSE_LABELS, "the test needs a construct that is deliberately unlisted"
    outcome = run(sql, model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)


# --- The surface that must keep working. A refusal is the designed answer for what this
# engine cannot honour — but tightening the allowlist onto requests it *can* honour would
# trade one silent failure for a wave of loud ones, so FR-5 pins the accepted forms.


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT revenue FROM orders",
        "SELECT revenue AS total FROM orders",
        'SELECT "revenue" FROM "orders"',
        "SELECT orders.revenue FROM orders",
        "SELECT revenue FROM orders AS o",
        "SELECT revenue FROM main.orders",
        "SELECT revenue FROM cat.main.orders AS o",
        "SELECT revenue FROM orders;",
        "SELECT revenue -- a trailing comment\nFROM orders",
        "select revenue, channel from orders",
        "SELECT ALL revenue FROM orders",
    ],
)
def test_the_answerable_surface_is_unchanged(sql: str, model: SemanticModel) -> None:
    assert isinstance(validate(sql, model), ValidRequest), f"regressed an answerable request: {sql}"


def test_dialect_mismatch_is_refused(model: SemanticModel) -> None:
    """A model written for one engine must not be run against another."""

    class Postgresish(ExplodingAdapter):
        @property
        def dialect(self) -> str:
            return "postgres"

    outcome = run("SELECT revenue FROM orders", model, Postgresish())
    assert isinstance(outcome, Refusal)
    assert "postgres" in outcome.reason


def test_case_insensitive_suggestion(model: SemanticModel) -> None:
    """LLM-written SQL is often upper-cased; a refusal should still help."""
    outcome = run("SELECT REVENUE FROM orders", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)
    assert "revenue" in outcome.did_you_mean


# --- Filters (spec 004). A filter is applied exactly as written or refused: the population a
# number is computed over is as load-bearing as the aggregation, and a partly-applied WHERE
# would be a wrong number with no symptom.


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        # Not a dimension.
        ("SELECT revenue FROM orders WHERE revenue > 100", "HAVING"),
        ("SELECT revenue FROM orders WHERE amount > 100", "not defined"),
        # Not a literal comparison.
        ("SELECT revenue FROM orders WHERE UPPER(channel) = 'WEB'", "a function"),
        ("SELECT revenue FROM orders WHERE channel = region", "literal value"),
        ("SELECT revenue FROM orders WHERE channel IN (SELECT 1)", "subquery"),
        ("SELECT revenue FROM orders WHERE channel = 'a' AND 1 = 1", "left side"),
        # Type mismatches, caught against the dimension's declared `type`.
        ("SELECT revenue FROM orders WHERE order_date >= 'yesterday'", "ISO date"),
        ("SELECT revenue FROM orders WHERE order_date LIKE '2026%'", "LIKE needs a string"),
        ("SELECT revenue FROM orders WHERE channel = 5", "must be quoted"),
        ("SELECT revenue FROM orders WHERE channel = TRUE", "TRUE/FALSE"),
    ],
)
def test_a_filter_it_cannot_honour_is_refused(
    sql: str, expected: str, model: SemanticModel
) -> None:
    outcome = run(sql, model, ExplodingAdapter())
    assert isinstance(outcome, Refusal), f"accepted a filter it cannot honour: {sql}"
    assert expected in outcome.reason, f"{expected!r} not in {outcome.reason!r}"


def test_a_misspelled_filter_dimension_suggests(model: SemanticModel) -> None:
    outcome = run("SELECT revenue FROM orders WHERE chanel = 'web'", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)
    assert "channel" in outcome.did_you_mean


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT revenue FROM orders WHERE channel = 'web'",
        "SELECT revenue FROM orders WHERE channel <> 'web'",
        "SELECT revenue FROM orders WHERE channel IN ('web', 'retail')",
        "SELECT revenue FROM orders WHERE channel NOT IN ('web')",
        "SELECT revenue FROM orders WHERE channel LIKE 'we%'",
        "SELECT revenue FROM orders WHERE channel NOT LIKE 'we%'",
        "SELECT revenue FROM orders WHERE channel IS NULL",
        "SELECT revenue FROM orders WHERE channel IS NOT NULL",
        "SELECT revenue FROM orders WHERE order_date >= '2026-07-01'",
        "SELECT revenue FROM orders WHERE order_date BETWEEN '2026-07-01' AND '2026-07-31'",
        "SELECT revenue FROM orders WHERE order_date NOT BETWEEN '2026-07-01' AND '2026-07-31'",
        "SELECT revenue FROM orders WHERE channel = 'web' AND region = 'north'",
        "SELECT revenue FROM orders WHERE channel = 'web' OR region = 'north'",
        "SELECT revenue FROM orders WHERE (channel = 'web' OR channel = 'partner') "
        "AND region = 'north'",
        "SELECT revenue FROM orders WHERE NOT channel = 'web'",
        "SELECT revenue, channel FROM orders WHERE order_date < '2026-08-01'",
    ],
)
def test_every_supported_predicate_validates(sql: str, model: SemanticModel) -> None:
    assert isinstance(validate(sql, model), ValidRequest), f"refused a supported filter: {sql}"


# --- Ordering and limits (spec 005). Both decide what a reader actually sees, so a dropped
# DESC or LIMIT is a wrong answer in the same way a dropped filter is.


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT revenue, channel FROM orders ORDER BY 1", "not a position"),
        ("SELECT revenue, channel FROM orders ORDER BY SUM(amount)", "a function is not one"),
        ("SELECT revenue, channel FROM orders ORDER BY region", "not selected by this request"),
        ("SELECT revenue FROM orders LIMIT 1 + 1", "whole number"),
        ("SELECT revenue FROM orders LIMIT -1", "whole number"),
        ("SELECT revenue FROM orders LIMIT '5'", "whole number"),
        ("SELECT revenue FROM orders OFFSET 1 + 1", "whole number"),
    ],
)
def test_an_ordering_or_limit_it_cannot_honour_is_refused(
    sql: str, expected: str, model: SemanticModel
) -> None:
    outcome = run(sql, model, ExplodingAdapter())
    assert isinstance(outcome, Refusal), f"accepted an ordering it cannot honour: {sql}"
    assert expected in outcome.reason, f"{expected!r} not in {outcome.reason!r}"


def test_ordering_by_an_unselected_name_suggests_one_that_works(model: SemanticModel) -> None:
    outcome = run("SELECT revenue, channel FROM orders ORDER BY revenu", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)
    assert "revenue" in outcome.did_you_mean


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT revenue, channel FROM orders ORDER BY revenue",
        "SELECT revenue, channel FROM orders ORDER BY revenue DESC",
        "SELECT revenue, channel FROM orders ORDER BY revenue ASC NULLS FIRST",
        "SELECT revenue AS total, channel FROM orders ORDER BY total DESC",
        "SELECT revenue AS total, channel FROM orders ORDER BY revenue DESC",
        "SELECT revenue, channel FROM orders ORDER BY channel, revenue DESC",
        "SELECT revenue FROM orders LIMIT 5",
        "SELECT revenue FROM orders LIMIT 0",
        "SELECT revenue FROM orders LIMIT 5 OFFSET 2",
        "SELECT revenue, channel FROM orders WHERE channel <> 'web' ORDER BY revenue DESC LIMIT 1",
    ],
)
def test_every_supported_ordering_validates(sql: str, model: SemanticModel) -> None:
    assert isinstance(validate(sql, model), ValidRequest), f"refused a supported ordering: {sql}"


def test_filtering_on_a_metric_is_refused(model: SemanticModel) -> None:
    """Same reasoning as a measure: that is HAVING, and HAVING is not supported."""
    outcome = run(
        "SELECT revenue FROM orders WHERE revenue_per_order > 1", model, ExplodingAdapter()
    )
    assert isinstance(outcome, Refusal)
    assert "HAVING" in outcome.reason
    assert "metric" in outcome.reason


def test_a_metric_alone_computes_a_number(model: SemanticModel) -> None:
    """A request selecting only a metric is answerable — it computes something."""
    assert isinstance(validate("SELECT revenue_per_order FROM orders", model), ValidRequest)


# --- Time grains (spec 007). The hazard is a spelling that looks right and collapses years.


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT revenue, MONTH(order_date) FROM orders", "DATE_TRUNC"),
        ("SELECT revenue, YEAR(order_date) FROM orders", "DATE_TRUNC"),
        ("SELECT revenue, EXTRACT(MONTH FROM order_date) FROM orders", "DATE_TRUNC"),
        ("SELECT revenue, DATE_TRUNC('fortnight', order_date) FROM orders", "not a grain"),
        ("SELECT revenue, DATE_TRUNC('month', channel) FROM orders", "not date"),
        ("SELECT revenue, DATE_TRUNC('month', revenue) FROM orders", "not a dimension"),
        (
            "SELECT revenue, DATE_TRUNC('month', DATE_TRUNC('year', order_date)) FROM orders",
            "applied directly",
        ),
    ],
)
def test_a_grain_it_cannot_honour_is_refused(sql: str, expected: str, model: SemanticModel) -> None:
    outcome = run(sql, model, ExplodingAdapter())
    assert isinstance(outcome, Refusal), f"accepted a grain it cannot honour: {sql}"
    assert expected in outcome.reason, f"{expected!r} not in {outcome.reason!r}"


def test_the_extract_refusal_explains_the_collapse(model: SemanticModel) -> None:
    """A refusal that only declines sends the caller hunting for a typo."""
    outcome = run("SELECT revenue, MONTH(order_date) FROM orders", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)
    assert "collapse" in outcome.reason


@pytest.mark.parametrize("grain", ["year", "quarter", "month", "week", "day"])
def test_every_grain_validates(grain: str, model: SemanticModel) -> None:
    sql = f"SELECT revenue, DATE_TRUNC('{grain}', order_date) FROM orders"
    request = validate(sql, model)
    assert isinstance(request, ValidRequest), request
    assert request.projections[1].grain == grain
    assert request.projections[1].output == f"order_date_{grain}"


# --- Refusal paths that had no test (coverage measured after spec 015).
#
# Every line below was an unexercised branch in `validate`. That is the worst place in this project
# to leave uncovered: a refusal that quietly stops firing does not raise, it *accepts* — and an
# accepted construct the compiler cannot honour is dropped, so the answer is to a different
# question. These are the checks that keep that from happening, so they get tests.

_BOOLEAN_MODEL = """
version: 1
datasource: {name: t, dialect: duckdb}
tables:
  flags:
    source: flags
    dimensions:
      active: {column: active, type: boolean}
      name: {column: name, type: string}
    measures:
      n: {column: name, agg: count}
"""


@pytest.fixture
def boolean_model(tmp_path: Path) -> SemanticModel:
    """The retail example has no boolean dimension, and boolean filters have their own rules."""
    path = tmp_path / "flags.yml"
    path.write_text(_BOOLEAN_MODEL)
    return load_model(path)


def _refusal(sql: str, model: SemanticModel) -> str:
    outcome = validate(sql, model)
    assert isinstance(outcome, Refusal), f"expected a refusal, got {outcome}"
    return str(outcome)


@pytest.mark.parametrize("operator", [">", "<", ">=", "<=", "LIKE"])
def test_ordering_a_boolean_is_refused(operator: str, boolean_model: SemanticModel) -> None:
    """`active > FALSE` parses and means nothing.

    Left to the database it would answer — booleans order in SQL — so the number would be real and
    the question meaningless. Refused with a reason rather than answered.
    """
    reason = _refusal(f"SELECT n FROM flags WHERE active {operator} FALSE", boolean_model)
    assert "boolean" in reason


def test_comparing_a_boolean_to_a_non_boolean_is_refused(boolean_model: SemanticModel) -> None:
    reason = _refusal("SELECT n FROM flags WHERE active = 'yes'", boolean_model)
    assert "TRUE or FALSE" in reason


def test_in_with_no_values_is_refused(model: SemanticModel) -> None:
    """`IN ()` is a filter that can never match, which is far likelier to be a mistake."""
    reason = _refusal("SELECT revenue FROM orders WHERE channel IN ()", model)
    assert "at least one value" in reason


def test_is_null_and_is_not_null_are_both_supported(model: SemanticModel) -> None:
    """Written expecting a refusal; measuring said otherwise, so the test records what is true.

    `IS NOT NULL` is `Negation(Comparison(is null))` — the compiler rebuilds both, so both are
    accepted. Worth pinning: `IS NOT NULL` on a nullable column is the filter most likely to be
    quietly dropped, and dropping it widens the population without changing the shape of the answer.
    """
    for sql in (
        "SELECT revenue FROM orders WHERE channel IS NULL",
        "SELECT revenue FROM orders WHERE channel IS NOT NULL",
    ):
        assert not isinstance(validate(sql, model), Refusal), sql


def test_is_a_value_other_than_null_is_refused(model: SemanticModel) -> None:
    """`IS TRUE` is not the `IS NULL` the compiler implements, so it is refused rather than read
    as one."""
    reason = _refusal("SELECT revenue FROM orders WHERE channel IS TRUE", model)
    assert "IS <value>" in reason


def test_a_request_with_no_table_is_refused(model: SemanticModel) -> None:
    reason = _refusal("SELECT revenue", model)
    assert "no table" in reason


def test_a_second_table_is_refused_as_a_join(model: SemanticModel) -> None:
    """`FROM a, b` is a join written with a comma, and it is caught as one.

    Asserted on the behaviour rather than on the message I assumed: the refusal names JOIN, which
    is the truthful description of what a comma in FROM is.
    """
    reason = _refusal("SELECT revenue FROM orders, orders", model)
    assert "JOIN" in reason


def test_a_subquery_as_the_from_target_is_refused(model: SemanticModel) -> None:
    """The FROM target resolves to a table in the model, or nothing does."""
    reason = _refusal("SELECT revenue FROM (SELECT 1)", model)
    assert "single table in the semantic model" in reason


def test_a_set_operation_is_refused(model: SemanticModel) -> None:
    """UNION would compose two requests the compiler validated separately, and it rebuilds one."""
    reason = _refusal("SELECT revenue FROM orders UNION SELECT revenue FROM orders", model)
    assert "Set operations" in reason


def test_selecting_nothing_is_refused(model: SemanticModel) -> None:
    reason = _refusal("SELECT FROM orders", model)
    assert reason


def test_unparseable_text_is_refused_rather_than_raised(model: SemanticModel) -> None:
    """A caller sending nonsense gets a refusal, not a traceback.

    The MCP server turns a refusal into an answer Claude can repair and an exception into a failed
    call, so which one this is decides whether a typo ends the conversation.
    """
    reason = _refusal("SELECT revenue FROM orders WHERE )(", model)
    assert reason


@pytest.mark.parametrize(
    "clause",
    [
        "ORDER BY UPPER(channel)",
        "ORDER BY 1",
        "ORDER BY revenue + 1",
    ],
)
def test_an_expression_in_order_by_is_refused(clause: str, model: SemanticModel) -> None:
    """Ordering names something the request selected. An expression is not a name."""
    reason = _refusal(f"SELECT revenue, channel FROM orders {clause}", model)
    assert reason


@pytest.mark.parametrize("limit", ["'ten'", "1.5", "-1", "channel"])
def test_a_limit_that_is_not_a_whole_number_is_refused(limit: str, model: SemanticModel) -> None:
    reason = _refusal(f"SELECT revenue FROM orders LIMIT {limit}", model)
    assert reason


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO orders VALUES (1)",
        "UPDATE orders SET amount = 1",
        "CREATE TABLE x (a int)",
        "DROP TABLE orders",
        "WITH x AS (SELECT 1) SELECT revenue FROM orders",
    ],
)
def test_statements_that_are_not_a_select_are_refused(sql: str, model: SemanticModel) -> None:
    """N5's other half: read-only holds because nothing but a SELECT gets past here."""
    assert isinstance(validate(sql, model), Refusal)
