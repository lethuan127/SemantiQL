"""The metric expression grammar — a closed grammar with, until now, no direct tests.

Metrics were reachable only through a loaded model, which meant the grammar's own refusals were
covered incidentally or not at all. That is the wrong place to leave them: this parser decides what
a business metric *is*, and something it accepts by accident becomes SQL nobody sanctioned.

The grammar is deliberately small. Everything outside it is refused, and each refusal below names
what would otherwise have slipped through.
"""

from __future__ import annotations

import pytest

from semantiql.knowledge.expression import (
    BinOp,
    ExpressionError,
    Neg,
    Num,
    Ref,
    parse_expression,
)
from semantiql.knowledge.model import Measure

MEASURES = {
    "revenue": Measure(column="amount", agg="sum"),
    "orders": Measure(column="id", agg="count"),
}


def _parse(text: str) -> object:
    return parse_expression(text, MEASURES)


# --- What the grammar admits


def test_a_measure_reference_parses() -> None:
    parsed = _parse("revenue")
    assert isinstance(parsed, Ref)
    assert parsed.measure == "revenue"


@pytest.mark.parametrize("operator", ["+", "-", "*", "/"])
def test_each_arithmetic_operator_parses(operator: str) -> None:
    parsed = _parse(f"revenue {operator} orders")
    assert isinstance(parsed, BinOp)
    assert parsed.op == operator


def test_a_number_parses() -> None:
    parsed = _parse("revenue / 100")
    assert isinstance(parsed, BinOp)
    assert isinstance(parsed.right, Num)
    assert parsed.right.value == 100


def test_unary_minus_parses() -> None:
    """Untested until now, and it compiles to real SQL — `exp.Neg` in the compiler."""
    parsed = _parse("-revenue")
    assert isinstance(parsed, Neg)
    assert isinstance(parsed.operand, Ref)


def test_parentheses_group_without_appearing_in_the_tree() -> None:
    """`(a + b) * c` must bind differently from `a + b * c`, or a metric is quietly wrong."""
    grouped = _parse("(revenue + orders) * 2")
    assert isinstance(grouped, BinOp)
    assert grouped.op == "*"
    assert isinstance(grouped.left, BinOp)
    assert grouped.left.op == "+"

    ungrouped = _parse("revenue + orders * 2")
    assert isinstance(ungrouped, BinOp)
    assert ungrouped.op == "+", "precedence must not be flattened"


def test_nesting_is_allowed() -> None:
    parsed = _parse("(revenue - orders) / (revenue + 1)")
    assert isinstance(parsed, BinOp)
    assert parsed.op == "/"


# --- What it refuses, and why each one matters


def test_an_unknown_name_is_refused_naming_it() -> None:
    """A metric referring to a measure that does not exist would compile to invalid SQL.

    Caught at load rather than at query time, so a typo in a metric nobody has asked for yet is
    still an error you see immediately.
    """
    with pytest.raises(ExpressionError) as caught:
        _parse("revenue / profit")
    assert "profit" in str(caught.value)


def test_a_dimension_is_not_a_measure() -> None:
    """Only measures may appear. A dimension has no aggregation, so there is nothing to divide."""
    with pytest.raises(ExpressionError, match="channel"):
        parse_expression("revenue / channel", MEASURES)


@pytest.mark.parametrize(
    "expression",
    [
        "SUM(amount)",  # an aggregation, which the measure already carries
        "revenue > orders",  # a comparison — a metric is a number, not a condition
        "revenue AND orders",
        "CASE WHEN revenue > 0 THEN 1 ELSE 0 END",
        "COALESCE(revenue, 0)",
        "revenue % orders",  # modulo is outside the four operators
        "revenue::text",
        "(SELECT 1)",
    ],
)
def test_everything_outside_the_grammar_is_refused(expression: str) -> None:
    """The grammar is closed on purpose.

    An aggregate inside a metric would double-aggregate; a comparison would produce a boolean where
    a number is expected; a function call would be a dialect's spelling leaking into the model. All
    refused rather than passed through to be discovered as a wrong number.
    """
    with pytest.raises(ExpressionError):
        _parse(expression)


@pytest.mark.parametrize("expression", ["", "   ", "revenue +", "* orders", "((revenue"])
def test_malformed_text_is_refused(expression: str) -> None:
    with pytest.raises(ExpressionError):
        _parse(expression)


def test_the_error_names_the_offending_expression() -> None:
    """A model with thirty metrics needs the message to say which one, and what in it."""
    with pytest.raises(ExpressionError) as caught:
        _parse("COALESCE(revenue, 0)")
    message = str(caught.value)
    assert message, "an empty message is no better than no error"
