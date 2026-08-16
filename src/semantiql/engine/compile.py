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
from semantiql.knowledge.expression import BinOp, MetricExpr, Neg, Num, Ref
from semantiql.knowledge.model import Dimension, Measure, SemanticModel, Table

CANONICAL_DIALECT = "duckdb"

_ARITHMETIC: dict[str, type[exp.Binary]] = {
    "+": exp.Add,
    "-": exp.Sub,
    "*": exp.Mul,
}

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


def _metric(node: MetricExpr, table: Table) -> exp.Expr:
    """Build a metric from the aggregations of the measures it names.

    The substitution order is what makes the number right. Each `Ref` becomes that measure's
    sanctioned aggregation, so `revenue / order_count` compiles to `SUM(amount) /
    COUNT(order_id)` — one division, applied *after* the grouping, over each group's own
    parts. Dividing row by row and averaging the results is a different and wrong number, and
    nothing in the answer would show which one you got.

    Every divisor is wrapped in `NULLIF(…, 0)`, and that is not defensive tidying. DuckDB
    evaluates `1/0` to `inf` and hands it back as a value; Postgres raises. Unguarded, the
    same model would report a meaningless figure on one engine and fail on the other. NULL is
    the honest answer for a ratio with nothing to divide by.
    """
    if isinstance(node, Ref):
        measure = table.measures[node.measure]
        return _aggregation(measure)
    if isinstance(node, Num):
        return exp.Literal.number(node.value)
    if isinstance(node, Neg):
        return exp.Neg(this=_grouped(node.operand, table))

    left = _grouped(node.left, table)
    right = _grouped(node.right, table)
    if node.op == "/":
        return exp.Div(this=left, expression=exp.func("NULLIF", right, exp.Literal.number(0)))
    return _ARITHMETIC[node.op](this=left, expression=right)


def _grouped(node: MetricExpr, table: Table) -> exp.Expr:
    """An operand, parenthesised only where precedence could change the number.

    A leaf needs no parentheses and reads better without them, and the emitted SQL is meant to
    be read — `--show-sql` exists so a reviewer can check the work.
    """
    built = _metric(node, table)
    return exp.paren(built) if isinstance(node, BinOp | Neg) else built


def _aggregation(measure: Measure) -> exp.Expr:
    """A measure's sanctioned aggregation, unaliased."""
    column = exp.column(measure.column)
    if measure.agg == "count_distinct":
        return exp.Count(this=exp.Distinct(expressions=[column]))
    return _AGG[measure.agg](this=column)


def _aggregate(measure: Measure, alias: str) -> exp.Expr:
    """Render a measure as its one sanctioned aggregation, aliased for the caller."""
    return exp.alias_(_aggregation(measure), alias)


def _truncand(dimension: Dimension) -> exp.Expr:
    """What `DATE_TRUNC` is applied to. Never the bare column — that is the whole point.

    Truncating a bare column makes the answer depend on the **database server's timezone**, and
    both engines do it, so a differential test cannot catch it (spec 011). A row at
    `2026-07-01T02:00:00Z` buckets into July on a server in UTC and into June on one in
    `America/Chicago`. The user sees neither the setting nor the difference.

    Two shapes, and which one is correct depends entirely on whether the column carries a zone:

    - **No `timezone:` declared** — the column is a `date` or a naive `timestamp`, so there is
      no zone to honour and none should be invented. `CAST(… AS TIMESTAMP)` pins it. On DuckDB
      that is a no-op; on Postgres it is load-bearing, because `date_trunc(text, date)` resolves
      to the `timestamptz` overload and drags the session timezone in. Delete the cast and
      Postgres starts answering differently from DuckDB, and differently from itself on another
      host.

    - **`timezone:` declared** — the column carries a zone, and the model says which zone the
      buckets belong to. `AT TIME ZONE` converts once, explicitly, to that zone.

    Applying the wrong shape is not a missed optimisation, it is the bug: measured, `AT TIME
    ZONE` over a naive column *moves the bucket* on both engines, and over a `date` the two
    engines disagree because they resolve the implicit cast in opposite directions. Nothing here
    can tell the physical type — `type: date` covers all three — so `doctor` checks the
    declaration against the real column, in both directions.
    """
    column = exp.column(dimension.column)
    if dimension.timezone is None:
        return exp.cast(column, "TIMESTAMP")
    return exp.AtTimeZone(this=column, zone=exp.Literal.string(dimension.timezone))


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
    #: The grouping keys, built alongside the projections so a grain is carried into both.
    #: GROUP BY repeats the expression rather than naming the output alias: ordering by an
    #: alias is portable, grouping by one is not.
    grouping: list[exp.Expr] = []
    for item in request.projections:
        if item.entity in table.metrics:
            built = _metric(table.expression_for(item.entity), table)
            projections.append(exp.alias_(built, item.output))
        elif item.entity in table.measures:
            projections.append(_aggregate(table.measures[item.entity], item.output))
        else:
            dimension = table.dimensions[item.entity]
            built = exp.column(dimension.column)
            if item.grain is not None:
                built = exp.TimestampTrunc(this=_truncand(dimension), unit=exp.var(item.grain))
            grouping.append(built)
            projections.append(exp.alias_(built, item.output))

    select = exp.select(*projections).from_(relation)

    if request.filter is not None:
        select = select.where(_predicate(request.filter, table))

    for group_key in grouping:
        select = select.group_by(group_key)

    # Ordering names the *output* column — `ORDER BY revenue`, the word the caller used —
    # rather than repeating `SUM(amount)`. Both MVP engines accept it, and the emitted SQL
    # still reads like the request that produced it.
    for key in request.order:
        select = select.order_by(
            exp.Ordered(
                this=exp.column(key.output),
                desc=key.desc,
                nulls_first=key.nulls_first,
            )
        )

    if request.limit is not None:
        select = select.limit(request.limit)
    if request.offset is not None:
        select = select.offset(request.offset)

    canonical = select.sql(dialect=CANONICAL_DIALECT)
    if dialect == CANONICAL_DIALECT:
        return canonical
    return sqlglot.transpile(canonical, read=CANONICAL_DIALECT, write=dialect)[0]
