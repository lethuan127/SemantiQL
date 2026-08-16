"""Metric expressions — the one place layer 1 parses anything.

A metric is a number defined from other numbers: `revenue / order_count`, `(revenue - cost) /
revenue`. This module turns that text into a small tree the compiler can build SQL from, and
refuses everything else.

**Parsing text is normally what this codebase will not do**, so the difference is worth being
explicit about. Elsewhere the text comes from a caller and is never trusted; here it comes
from the semantic model file, which lives in git and is reviewed in a diff (N3). It is parsed
**once, when the model loads**, under a closed grammar, into an IR containing only measure
names and numbers. The compiler then builds every SQL node itself, exactly as it does for
projections and predicates — no fragment of this text reaches the database.

The grammar is deliberately tiny: measure names, numbers, `+ - * /`, unary minus, and
parentheses. No functions, no aggregations, no column references. A metric that needs
`SUM(...)` is asking to choose an aggregation, and choosing an aggregation is the measure
layer's job — one sanctioned definition per number, in one place.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import sqlglot
from sqlglot import exp


class ExpressionError(ValueError):
    """A metric expression that cannot be honoured. Raised at load, never at query time."""


@dataclass(frozen=True)
class Ref:
    """A reference to a measure on the same table."""

    measure: str


@dataclass(frozen=True)
class Num:
    """A numeric constant."""

    value: float


@dataclass(frozen=True)
class BinOp:
    """`+`, `-`, `*` or `/` over two operands."""

    op: str
    left: MetricExpr
    right: MetricExpr


@dataclass(frozen=True)
class Neg:
    """Unary minus."""

    operand: MetricExpr


MetricExpr = Ref | Num | BinOp | Neg

#: sqlglot node → operator. The allowlist: a node absent from here is refused, so a function,
#: an aggregate, a comparison or a subquery cannot appear however it is spelled.
_BINARY: dict[type[exp.Expr], str] = {
    exp.Add: "+",
    exp.Sub: "-",
    exp.Mul: "*",
    exp.Div: "/",
}


def _describe(node: exp.Expr) -> str:
    """How a refusal names something the grammar does not allow."""
    if isinstance(node, exp.AggFunc):
        return (
            f"the aggregate {type(node).__name__.upper()}(...) — a metric combines measures, "
            "and choosing an aggregation is a measure's job"
        )
    if isinstance(node, exp.Func):
        return f"the function {type(node).__name__.upper()}(...)"
    return f"{node.sql()!r}"


def parse_expression(text: str, measures: Iterable[str]) -> MetricExpr:
    """Parse a metric expression, resolving every name against `measures`.

    Raises `ExpressionError` with a message naming what was wrong — this runs at load, so the
    message is the only thing the model's author will see.
    """
    known = set(measures)
    try:
        parsed = sqlglot.parse_one(text, read="duckdb")
    except sqlglot.ParseError as exc:
        raise ExpressionError(f"{text!r} is not a valid expression: {exc}") from exc
    return _convert(parsed, known, text)


def _convert(node: exp.Expr, measures: set[str], text: str) -> MetricExpr:
    if isinstance(node, exp.Paren):
        return _convert(node.this, measures, text)

    if isinstance(node, exp.Neg):
        return Neg(_convert(node.this, measures, text))

    operator = _BINARY.get(type(node))
    if operator is not None:
        left = _convert(node.this, measures, text)
        right = _convert(node.args["expression"], measures, text)
        if operator == "/" and isinstance(right, Num) and right.value == 0:
            raise ExpressionError(
                f"{text!r} divides by zero, which can never produce a number. "
                "A zero divisor that arrives from the data is handled; one written into the "
                "model is a mistake."
            )
        return BinOp(operator, left, right)

    if isinstance(node, exp.Column):
        name = node.name
        if name not in measures:
            known = ", ".join(sorted(measures)) or "none"
            raise ExpressionError(
                f"{name!r} is not a measure on this table, so a metric cannot be built from "
                f"it. Metrics combine measures; available here: {known}."
            )
        return Ref(name)

    if isinstance(node, exp.Literal) and not node.args.get("is_string"):
        return Num(float(node.this))

    raise ExpressionError(
        f"{text!r} contains {_describe(node)}, which a metric expression may not use. "
        "Allowed: measure names, numbers, + - * /, unary minus, and parentheses."
    )
