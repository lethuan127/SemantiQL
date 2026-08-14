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

import sqlglot
from sqlglot import exp

from semantiql.engine.validate import ValidRequest
from semantiql.knowledge.model import Measure, SemanticModel

CANONICAL_DIALECT = "duckdb"

_AGG: dict[str, type[exp.AggFunc]] = {
    "sum": exp.Sum,
    "count": exp.Count,
    "min": exp.Min,
    "max": exp.Max,
    "avg": exp.Avg,
}


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

    for name in request.dimensions:
        select = select.group_by(exp.column(table.dimensions[name].column))

    canonical = select.sql(dialect=CANONICAL_DIALECT)
    if dialect == CANONICAL_DIALECT:
        return canonical
    return sqlglot.transpile(canonical, read=CANONICAL_DIALECT, write=dialect)[0]
