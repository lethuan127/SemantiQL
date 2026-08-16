"""Compile a validated request into physical SQL (constitution N4).

Two steps, deliberately separate:

1. Build SQL in **one canonical dialect** from the semantic model — measures become their
   sanctioned aggregation, dimensions become plain columns and the GROUP BY.
2. **Transpile** to the target dialect with sqlglot.

Keeping them apart is what makes a new datasource one adapter and no core change: step 1
never learns a dialect's spelling. Nothing here imports a concrete adapter — the caller
passes the dialect and the relation.

The relation arrives as a **sqlglot expression, not a string**. That is a safety property,
not a style choice: a string would be re-parsed by `from_()`, so an adapter's SQL would be
round-tripped through this module's parser, and any quote inside a model's `source` would
escape into the FROM clause. Expressions are built, never parsed, so neither can happen.

This module compiles only what `validate` admits: a single table, a projection list of
dimensions and measures, and nothing else. Every other clause is refused upstream — see
`validate.py` for why silently dropping one is the worst thing this engine could do.
"""

from __future__ import annotations

from datetime import date

import sqlglot
from sqlglot import exp

from semantiql.engine.validate import (
    BoolOp,
    FilterValue,
    Negation,
    Predicate,
    ValidRequest,
)
from semantiql.knowledge.model import Measure, SemanticModel, Table

CANONICAL_DIALECT = "duckdb"

_COMPARISON: dict[str, type[exp.Binary]] = {
    "=": exp.EQ,
    "<>": exp.NEQ,
    "<": exp.LT,
    "<=": exp.LTE,
    ">": exp.GT,
    ">=": exp.GTE,
}

_AGG: dict[str, type[exp.AggFunc]] = {
    "sum": exp.Sum,
    "count": exp.Count,
    "min": exp.Min,
    "max": exp.Max,
    "avg": exp.Avg,
}


def _literal(value: FilterValue) -> exp.Expr:
    """One filter value, built as an expression — never spliced into SQL as text.

    A date becomes an explicit `CAST(… AS DATE)` rather than a bare string: the model is meant
    to outlive a change of database (N3), and engines do not agree on when a string coerces to
    a date. Being explicit means DuckDB and Postgres compare the same two things.
    """
    if isinstance(value, bool):  # before int — bool is an int subclass
        return exp.true() if value else exp.false()
    if isinstance(value, date):
        return exp.cast(exp.Literal.string(value.isoformat()), "date")
    if isinstance(value, int | float):
        return exp.Literal.number(value)
    return exp.Literal.string(value)


def _predicate(predicate: Predicate, table: Table) -> exp.Expr:
    """Rebuild a validated filter over the table's physical columns.

    Every node here is constructed from the IR, so the caller's parsed text reaches the
    database in exactly one form: escaped literal values. A value containing a quote is data.
    """
    if isinstance(predicate, BoolOp):
        left, right = (_predicate(operand, table) for operand in predicate.operands)
        joined = exp.And if predicate.op == "and" else exp.Or
        return joined(this=exp.paren(left), expression=exp.paren(right))
    if isinstance(predicate, Negation):
        return exp.not_(exp.paren(_predicate(predicate.operand, table)))

    column = exp.column(table.dimensions[predicate.dimension].column)
    values = [_literal(value) for value in predicate.values]

    if predicate.operator == "is null":
        return exp.Is(this=column, expression=exp.null())
    if predicate.operator == "in":
        return exp.In(this=column, expressions=values)
    if predicate.operator == "between":
        return exp.Between(this=column, low=values[0], high=values[1])
    if predicate.operator == "like":
        return exp.Like(this=column, expression=values[0])
    return _COMPARISON[predicate.operator](this=column, expression=values[0])


def _aggregate(measure: Measure, alias: str) -> exp.Expr:
    """Render a measure as its one sanctioned aggregation."""
    column = exp.column(measure.column)
    agg: exp.Expr
    if measure.agg == "count_distinct":
        agg = exp.Count(this=exp.Distinct(expressions=[column]))
    else:
        agg = _AGG[measure.agg](this=column)
    return exp.alias_(agg, alias)


def compile_request(
    request: ValidRequest,
    model: SemanticModel,
    relation: exp.Expr,
    dialect: str,
) -> str:
    """Turn a validated request into SQL for `dialect`.

    `relation` is how the adapter addresses the model's `source` — a table expression, or a
    file-reader call for a CSV or Parquet path. Build it; never parse it.
    """
    table = model.tables[request.table]

    # Requested order is preserved: a caller indexing rows positionally should get the
    # columns it asked for, in the order it asked for them.
    projections: list[exp.Expr] = []
    for item in request.projections:
        if item.entity in table.measures:
            projections.append(_aggregate(table.measures[item.entity], item.output))
        else:
            dimension = table.dimensions[item.entity]
            projections.append(exp.alias_(exp.column(dimension.column), item.output))

    select = exp.select(*projections).from_(relation)

    if request.filter is not None:
        select = select.where(_predicate(request.filter, table))

    for name in request.dimensions:
        select = select.group_by(exp.column(table.dimensions[name].column))

    canonical = select.sql(dialect=CANONICAL_DIALECT)
    if dialect == CANONICAL_DIALECT:
        return canonical
    return sqlglot.transpile(canonical, read=CANONICAL_DIALECT, write=dialect)[0]
