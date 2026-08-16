"""Validation — the layer that earns the project (constitution N1, N2).

The published evidence behind SemantiQL is that an LLM over a raw schema is right about
16% of the time, a knowledge layer takes it to ~54%, and *checking the query* takes it to
~72%. The check is worth more than the generator, so this module is deliberately strict:

**Anything this engine cannot faithfully compile is refused.** Not approximated, not
silently dropped, not passed to the database to see what happens. That covers two kinds of
thing:

1. Identifiers that do not resolve in the semantic model.
2. Every construct the compiler does not implement — `HAVING`, `DISTINCT`, CTEs, subqueries,
   joins, `TABLESAMPLE`, `PIVOT`, and anything else SQL can express. `WHERE` (spec 004) and
   `ORDER BY` / `LIMIT` / `OFFSET` (spec 005) are implemented, each restricted to what the
   compiler can rebuild faithfully.

The second is the one that bites. `compile_request` rebuilds a query from the model rather
than rewriting the user's AST, so any construct left unvalidated would simply *vanish* and
the caller would get a confidently wrong number — `SELECT revenue FROM orders WHERE channel =
'web'` answering with total revenue, or a dropped `LIMIT 5` answering with forty rows. A
wrong number nobody can detect is precisely the failure this project exists to prevent, so an
unsupported construct is a refusal, and it stays one until the compiler genuinely implements
it.

**So the check is an allowlist, and that shape is load-bearing.** It used to be the
inverse — a list of known-bad clause names checked against the parsed statement — and that
failed exactly as an open-ended denylist must. sqlglot parses all of SQL; this engine
implements a sliver of it; so the list had to enumerate everything else, forever. It did not
survive contact with the parser: `TABLESAMPLE` and `PIVOT` were both *listed by name* and
still slipped through, because sqlglot attaches them to the table inside the FROM rather than
to the SELECT, and the loop only read the SELECT's own arguments. Both were accepted and
discarded, which is the precise failure mode the list existed to prevent (spec 003).

Stating the small side instead — the arguments `compile_request` actually consumes, and the
node types a bare `FROM <table>` is allowed to contain — fails closed. A construct nobody
anticipated, in a position nobody anticipated, is refused because it is *absent from the
allowlist*, not because someone remembered to forbid it. Implementing a construct therefore
means adding it to the allowlist **in the same change that teaches the compiler to honour
it** — never before.

`Refusal` carries `did_you_mean` so a refusal is useful, but a suggestion is never applied
automatically — that would reintroduce guessing through the back door.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from difflib import get_close_matches

import sqlglot
from sqlglot import exp

from semantiql.knowledge.model import Dimension, SemanticModel, Table

#: The only SELECT arguments this engine consumes: the projection list, the FROM, and the
#: filter. `compile_request` reads nothing else, so any other argument present in the request
#: is a construct that would be dropped. Adding an entry here without teaching the compiler to
#: honour it reopens the silent-drop hole this allowlist closes — `where` is here because
#: spec 004 taught the compiler to build a predicate, not to make room for one.
_SELECT_ARGS: frozenset[str] = frozenset(
    {"expressions", "from", "where", "order", "limit", "offset"}
)

#: The arguments an ORDER BY key may carry. `with_fill` (ClickHouse) is absent, so it refuses.
_ORDERED_ARGS: frozenset[str] = frozenset({"this", "desc", "nulls_first"})

#: What a `FROM <one model table>` may contain: each allowed node type, and the arguments
#: that node type may carry. `Table` holds its name parts as `Identifier`s plus an optional
#: `TableAlias`; the compiler ignores the alias and the catalog/schema parts safely, because
#: it rebuilds the relation from the model's `source`. Anything else under the FROM — a
#: sample, a pivot, a join's payload — changes the answer, so it is refused.
#:
#: The arguments are listed, not just the types, because sqlglot stores some constructs as a
#: **scalar** rather than a node: `FROM ONLY orders` is `only=True` on the table, and
#: `WITH ORDINALITY` is `ordinality=True`. Neither appears when walking expressions, so a
#: type-only allowlist would let both through — and `ONLY` changes which rows exist on
#: Postgres. Checking arguments closes that, and closes it for the next such construct too.
_FROM_NODE_ARGS: dict[type[exp.Expr], frozenset[str]] = {
    exp.From: frozenset({"this"}),
    exp.Table: frozenset({"this", "db", "catalog", "alias"}),
    exp.TableAlias: frozenset({"this"}),
    exp.Identifier: frozenset({"this", "quoted"}),
}

#: Wording only. A construct missing from these maps is still refused — it is named from the
#: parsed request instead. That is the whole point of the inversion: an incomplete map costs
#: a nice message, never a wrong number.
_CLAUSE_LABELS: dict[str, str] = {
    "where": "WHERE",
    "having": "HAVING",
    "group": "GROUP BY",
    "order": "ORDER BY",
    "sort": "SORT BY",
    "cluster": "CLUSTER BY",
    "distribute": "DISTRIBUTE BY",
    "limit": "LIMIT",
    "offset": "OFFSET",
    "distinct": "DISTINCT",
    "qualify": "QUALIFY",
    "windows": "WINDOW",
    "with": "WITH",
    "joins": "JOIN",
    "laterals": "LATERAL",
    "locks": "locking clause",
    "sample": "TABLESAMPLE",
    "pivots": "PIVOT (and UNPIVOT)",
    # sqlglot files `channel IN (SELECT …)` under `query`, which no builder here reads.
    "query": "a subquery",
}

#: A backstop for a node type reached through an allowed argument name — the one route the
#: argument check above cannot cover. Same rule as everywhere here: absence refuses, the map
#: only supplies the word.
_NODE_LABELS: dict[type[exp.Expr], str] = {
    exp.TableSample: "TABLESAMPLE",
    exp.Pivot: "PIVOT (and UNPIVOT)",
    exp.Subquery: "a subquery",
    exp.Select: "a subquery",
    exp.Case: "CASE",
}

#: Predicate nodes a filter may contain, and the arguments each may carry. The same rule as
#: `_FROM_NODE_ARGS`, applied inside the WHERE — and it earns its keep twice here. sqlglot
#: puts `channel IN (SELECT …)` under an argument named `query`, which is absent below, and it
#: represents `NOT LIKE` as `Like(negate=True)`: a bare flag whose loss would turn a request
#: for "not web" into an answer about web. Listing the arguments means the builder either
#: reads that flag or the request is refused; it cannot quietly invert.
_PREDICATE_ARGS: dict[type[exp.Expr], frozenset[str]] = {
    exp.And: frozenset({"this", "expression"}),
    exp.Or: frozenset({"this", "expression"}),
    exp.Not: frozenset({"this"}),
    exp.Paren: frozenset({"this"}),
    exp.EQ: frozenset({"this", "expression"}),
    exp.NEQ: frozenset({"this", "expression"}),
    exp.LT: frozenset({"this", "expression"}),
    exp.LTE: frozenset({"this", "expression"}),
    exp.GT: frozenset({"this", "expression"}),
    exp.GTE: frozenset({"this", "expression"}),
    exp.In: frozenset({"this", "expressions"}),
    exp.Between: frozenset({"this", "low", "high"}),
    exp.Like: frozenset({"this", "expression", "negate"}),
    exp.Is: frozenset({"this", "expression"}),
}

#: Comparison node → the operator recorded in the IR.
_OPERATORS: dict[type[exp.Expr], str] = {
    exp.EQ: "=",
    exp.NEQ: "<>",
    exp.LT: "<",
    exp.LTE: "<=",
    exp.GT: ">",
    exp.GTE: ">=",
}

#: Operators that order their values, so they say nothing on a boolean dimension.
_ORDERING: frozenset[str] = frozenset({"<", "<=", ">", ">=", "between"})


def _bare(arg: str) -> str:
    """The argument name without sqlglot's keyword-collision suffix.

    sqlglot suffixes argument names that collide with a Python keyword — `from_`, `with_` —
    and which spelling is in use has moved between versions. Comparing on the bare name means
    the allowlist cannot silently stop matching after an upgrade.
    """
    return arg[:-1] if arg.endswith("_") else arg


def _unsupported(label: str) -> Refusal:
    return Refusal(
        f"{label} is not supported yet, and this engine would silently ignore it "
        "rather than apply it — so the request is refused instead of answered with "
        "a number that looks right."
    )


@dataclass(frozen=True)
class Refusal:
    """Why a request was not run. The absence of a number, stated plainly."""

    reason: str
    did_you_mean: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.did_you_mean:
            return f"{self.reason} Did you mean: {', '.join(self.did_you_mean)}?"
        return self.reason


@dataclass(frozen=True)
class Projection:
    """One selected item: the model entity, and the name the caller wants it back under."""

    entity: str
    output: str


#: A filter value, already parsed out of the request and type-checked against the dimension
#: it is compared to. A Python value, never a sqlglot node — see `Comparison`.
FilterValue = str | int | float | bool | date


@dataclass(frozen=True)
class Comparison:
    """One predicate: a model dimension, an operator, and typed literal values.

    The dimension is named as the *model* knows it, and the values are Python values. Nothing
    the caller wrote survives into this object, which is what lets the compiler rebuild the
    predicate rather than carry it — the same discipline the projection list already follows.
    """

    dimension: str
    operator: str
    values: tuple[FilterValue, ...] = ()


@dataclass(frozen=True)
class BoolOp:
    """`AND` or `OR` over two predicates."""

    op: str
    operands: tuple[Predicate, ...]


@dataclass(frozen=True)
class Negation:
    """`NOT`, however it was spelled — a `NOT` keyword, `NOT IN`, or `LIKE`'s negate flag."""

    operand: Predicate


Predicate = Comparison | BoolOp | Negation


@dataclass(frozen=True)
class OrderKey:
    """One `ORDER BY` key, named as the result column the caller will see.

    `nulls_first` is carried rather than dropped: sqlglot records it as `True` only where the
    request wrote `NULLS FIRST`, so passing it through reproduces the request, and the
    unwritten case is left to the engine's default — which is what `NULLS LAST` asks for on
    both MVP engines anyway.
    """

    output: str
    desc: bool = False
    nulls_first: bool = False


@dataclass(frozen=True)
class ValidRequest:
    """A request proven to resolve against the model, ready to compile.

    `projections` preserves the order the caller asked for, so result columns come back in
    the order they were requested rather than an order the compiler found convenient.

    `filter` is the request's `WHERE`, resolved to model names and typed values, or `None`.
    """

    table: str
    projections: tuple[Projection, ...]
    measures: tuple[str, ...]
    dimensions: tuple[str, ...]
    filter: Predicate | None = None
    order: tuple[OrderKey, ...] = ()
    limit: int | None = None
    offset: int | None = None


class SemanticSyntaxError(Exception):
    """The request was not parseable as semantic SQL."""


def _projections(select: exp.Select) -> list[Projection]:
    """The identifiers a SELECT projects, in order, with any alias preserved."""
    out: list[Projection] = []
    for projection in select.expressions:
        if isinstance(projection, exp.Column):
            out.append(Projection(entity=projection.name, output=projection.name))
        elif isinstance(projection, exp.Alias) and isinstance(projection.this, exp.Column):
            out.append(Projection(entity=projection.this.name, output=projection.alias))
        else:
            raise SemanticSyntaxError(
                "each selected item must be a plain dimension or measure name, optionally "
                f"aliased, but got {projection.sql()!r}"
            )
    return out


def _predicate_label(node: exp.Expr) -> str:
    """How a refusal names something that has no business being in a filter."""
    if type(node) in _NODE_LABELS:
        return _NODE_LABELS[type(node)]
    if isinstance(node, exp.Func):
        return "a function"
    if isinstance(node, exp.Binary | exp.Unary):
        return "arithmetic"
    return type(node).__name__.upper()


def _filtered_dimension(node: exp.Expr, table: Table, table_name: str) -> str | Refusal:
    """The model dimension a predicate addresses, or why it does not address one."""
    if not isinstance(node, exp.Column):
        return Refusal(
            "A filter compares a dimension to a literal value, and the dimension goes on the "
            f"left — but the left side here is {_predicate_label(node)}."
        )
    name = node.name
    if name in table.measures or name in table.metrics:
        kind = "measure" if name in table.measures else "metric"
        return Refusal(
            f"{name!r} is a {kind}, so filtering on it would need HAVING, which is not "
            "supported. Filter on a dimension instead; a "
            f"{kind} is what the request computes."
        )
    if name not in table.dimensions:
        return Refusal(
            f"{name!r} is not defined on table {table_name!r}.",
            _suggest(name, table.entity_names),
        )
    return name


def _filter_value(
    node: exp.Expr, dimension: Dimension, name: str, operator: str
) -> FilterValue | Refusal:
    """One literal, checked against the dimension's declared type.

    This is the first code in the engine to read `type:`. Letting the database decide instead
    would mean a modelling error surfaced as an adapter error at best, and as a silent
    coercion at worst — engines do not agree on what comparing text to a number means.
    """
    kind = dimension.type
    if operator in _ORDERING and kind == "boolean":
        return Refusal(f"{name!r} is a boolean dimension, so {operator!r} says nothing about it.")
    if operator in {"like"} and kind != "string":
        return Refusal(f"LIKE needs a string dimension, and {name!r} is declared {kind}.")

    if kind == "boolean":
        if not isinstance(node, exp.Boolean):
            return Refusal(f"{name!r} is a boolean dimension; compare it to TRUE or FALSE.")
        return bool(node.this)
    if isinstance(node, exp.Boolean):
        return Refusal(f"{name!r} is declared {kind}, so TRUE/FALSE is not a value it can take.")
    if not isinstance(node, exp.Literal):
        return Refusal(
            f"A filter on {name!r} must compare it to a literal value, "
            f"not {_predicate_label(node)}."
        )

    text = str(node.this)
    if kind == "number":
        if node.args.get("is_string"):
            return Refusal(f"{name!r} is a number dimension, but {text!r} is quoted text.")
        return int(text) if text.lstrip("-").isdigit() else float(text)
    if not node.args.get("is_string"):
        return Refusal(f"{name!r} is a {kind} dimension, so {text} must be quoted.")
    if kind == "date":
        try:
            return date.fromisoformat(text)
        except ValueError:
            return Refusal(
                f"{name!r} is a date dimension, and {text!r} is not an ISO date "
                "(YYYY-MM-DD). Refusing rather than guessing which date was meant."
            )
    return text


def _filter(node: exp.Expr, table: Table, table_name: str) -> Predicate | Refusal:
    """Resolve one predicate into the IR, or refuse it.

    Allowlist-driven throughout, in both directions: the node type must be one this engine
    builds, and every argument on it must be one the builder reads.
    """
    if isinstance(node, exp.Paren):
        return _filter(node.this, table, table_name)

    allowed = _PREDICATE_ARGS.get(type(node))
    if allowed is None:
        return _unsupported(f"{_predicate_label(node)} in a filter")
    for arg, value in node.args.items():
        if value and arg not in allowed:
            return _unsupported(f"{_CLAUSE_LABELS.get(_bare(arg), _bare(arg).upper())} in a filter")

    if isinstance(node, exp.And | exp.Or):
        left = _filter(node.this, table, table_name)
        if isinstance(left, Refusal):
            return left
        right = _filter(node.args["expression"], table, table_name)
        if isinstance(right, Refusal):
            return right
        return BoolOp("and" if isinstance(node, exp.And) else "or", (left, right))

    if isinstance(node, exp.Not):
        inner = _filter(node.this, table, table_name)
        return inner if isinstance(inner, Refusal) else Negation(inner)

    name = _filtered_dimension(node.this, table, table_name)
    if isinstance(name, Refusal):
        return name
    dimension = table.dimensions[name]

    if isinstance(node, exp.Is):
        if not isinstance(node.args.get("expression"), exp.Null):
            return _unsupported("IS <value> in a filter")
        return Comparison(name, "is null")

    operands: list[exp.Expr]
    if isinstance(node, exp.In):
        operator = "in"
        operands = list(node.args.get("expressions") or [])
        if not operands:
            return Refusal(f"IN needs at least one value to compare {name!r} against.")
    elif isinstance(node, exp.Between):
        operator = "between"
        operands = [node.args["low"], node.args["high"]]
    elif isinstance(node, exp.Like):
        operator = "like"
        operands = [node.args["expression"]]
    else:
        operator = _OPERATORS[type(node)]
        operands = [node.args["expression"]]

    values: list[FilterValue] = []
    for operand in operands:
        value = _filter_value(operand, dimension, name, operator)
        if isinstance(value, Refusal):
            return value
        values.append(value)

    comparison = Comparison(name, operator, tuple(values))
    # `NOT LIKE` is a flag on the node, not a wrapper. Read it here or invert the meaning.
    if isinstance(node, exp.Like) and node.args.get("negate"):
        return Negation(comparison)
    return comparison


def _suggest(name: str, candidates: list[str]) -> list[str]:
    """Close matches, case-insensitively — LLM-written SQL is often upper-cased."""
    folded = {c.lower(): c for c in candidates}
    hits = get_close_matches(name.lower(), list(folded), n=3, cutoff=0.5)
    return [folded[h] for h in hits]


def _ordering(order: exp.Order, projections: list[Projection]) -> tuple[OrderKey, ...] | Refusal:
    """Resolve `ORDER BY` against what the request selects.

    Ordering by something the request does not project is refused, even though SQL allows it:
    a number that decides the order of the rows without appearing in them leaves a reader
    unable to see why the answer is arranged as it is. That rule also disposes of ordinals and
    aggregates without needing a case for either — neither is a name the request selects.
    """
    #: Both spellings resolve to the column the caller will see: `revenue AS total` can be
    #: ordered by either `revenue` or `total`.
    outputs = {p.output: p.output for p in projections} | {p.entity: p.output for p in projections}

    keys: list[OrderKey] = []
    for item in order.expressions:
        if not isinstance(item, exp.Ordered):
            return _unsupported(f"{_predicate_label(item)} in ORDER BY")
        for arg, value in item.args.items():
            if value and arg not in _ORDERED_ARGS:
                label = _CLAUSE_LABELS.get(_bare(arg), _bare(arg).upper())
                return _unsupported(f"{label} in ORDER BY")

        target = item.this
        if isinstance(target, exp.Literal):
            return Refusal(
                "ORDER BY takes the name of something this request selects, not a position. "
                f"Order by one of: {', '.join(sorted(set(outputs.values())))}."
            )
        if not isinstance(target, exp.Column):
            return Refusal(
                f"ORDER BY takes the name of something this request selects, and "
                f"{_predicate_label(target)} is not one."
            )
        if target.name not in outputs:
            return Refusal(
                f"{target.name!r} is not selected by this request, so it cannot decide the "
                "order of rows that do not show it.",
                _suggest(target.name, sorted(set(outputs))),
            )
        keys.append(
            OrderKey(
                output=outputs[target.name],
                desc=bool(item.args.get("desc")),
                nulls_first=bool(item.args.get("nulls_first")),
            )
        )
    return tuple(keys)


def _row_count(node: exp.Expr, label: str) -> int | Refusal:
    """The whole number behind a `LIMIT` or an `OFFSET`.

    Anything else — `LIMIT 1 + 1`, `LIMIT -1`, a quoted value — is refused rather than
    rebuilt: honouring an expression here would smuggle expression support into the compiler
    through a clause, and the model deliberately has none.
    """
    value = node.args.get("expression")
    if not isinstance(value, exp.Literal) or value.args.get("is_string"):
        return Refusal(f"{label} takes a whole number written directly, and this is not one.")
    text = str(value.this)
    if not text.isdigit():
        return Refusal(f"{label} takes a non-negative whole number, and {text!r} is not one.")
    return int(text)


def validate(sql: str, model: SemanticModel) -> ValidRequest | Refusal:
    """Check `sql` against `model`. Returns a `ValidRequest` or a `Refusal` — never a guess."""
    try:
        parsed = sqlglot.parse_one(sql, read="duckdb")
    except sqlglot.ParseError as exc:
        return Refusal(f"That is not parseable as semantic SQL: {exc}.")

    if isinstance(parsed, exp.Union | exp.Except | exp.Intersect):
        return Refusal("Set operations (UNION, EXCEPT, INTERSECT) are not supported.")
    if isinstance(parsed, exp.Column):
        # sqlglot parses a bare word as a column reference. Telling someone who typed
        # "hello" that only SELECT is supported explains nothing.
        return Refusal(
            f"{sql.strip()!r} does not look like a query. Semantic SQL looks like "
            "'SELECT <measure>, <dimension> FROM <table>'."
        )
    if not isinstance(parsed, exp.Select):
        return Refusal(
            f"Only SELECT is supported, and this is {type(parsed).__name__.upper()}; "
            "the semantic layer is read-only."
        )

    # Refuse before resolving identifiers: a dropped construct is a wrong number, which is
    # worse than an unresolved name, and the caller should hear about it first.
    for arg, value in parsed.args.items():
        if value and _bare(arg) not in _SELECT_ARGS:
            return _unsupported(_CLAUSE_LABELS.get(_bare(arg), _bare(arg).upper()))

    from_node = parsed.find(exp.From)
    if from_node is None:
        return Refusal("The request names no table.")
    if not isinstance(from_node.this, exp.Table):
        return Refusal("The FROM target must be a single table in the semantic model.")

    tables = list(parsed.find_all(exp.Table))
    if len(tables) > 1:
        return Refusal("Only a single semantic table is supported per request.")

    # The same allowlist rule, one level down. sqlglot hangs `TABLESAMPLE` and `PIVOT` off
    # the table rather than off the SELECT, so a check that only read the SELECT's arguments
    # missed them however carefully they were enumerated. Walking the subtree makes the rule
    # location-independent, and checking each node's arguments makes it representation-
    # independent: a construct is refused for being absent from `_FROM_NODE_ARGS`, whether it
    # arrives as a node or as a bare flag, and without anyone having remembered it.
    for node in from_node.walk():
        allowed = _FROM_NODE_ARGS.get(type(node))
        if allowed is None:
            return _unsupported(_NODE_LABELS.get(type(node), type(node).__name__.upper()))
        for arg, value in node.args.items():
            if value and arg not in allowed:
                return _unsupported(_CLAUSE_LABELS.get(_bare(arg), _bare(arg).upper()))

    table_name = from_node.this.name
    table = model.table(table_name)
    if table is None:
        return Refusal(
            f"{table_name!r} is not a table in the semantic model.",
            _suggest(table_name, model.table_names),
        )

    try:
        projections = _projections(parsed)
    except SemanticSyntaxError as exc:
        return Refusal(str(exc) + ".")

    if not projections:
        return Refusal("The request selects nothing.")

    measures: list[str] = []
    dimensions: list[str] = []
    for item in projections:
        if table.entity(item.entity) is None:
            return Refusal(
                f"{item.entity!r} is not defined on table {table_name!r}.",
                _suggest(item.entity, table.entity_names),
            )
        # A metric computes a number the same way a measure does, so it counts as one here
        # and is likewise not a grouping key.
        if item.entity in table.measures or item.entity in table.metrics:
            measures.append(item.entity)
        else:
            dimensions.append(item.entity)

    if not measures:
        return Refusal(
            "The request selects no measure, so there is no number to compute. "
            f"Measures on {table_name!r}: {', '.join(table.computed_names) or 'none'}."
        )

    where = parsed.args.get("where") or parsed.args.get("where_")
    predicate: Predicate | None = None
    if where is not None:
        resolved = _filter(where.this, table, table_name)
        if isinstance(resolved, Refusal):
            return resolved
        predicate = resolved

    order_node = parsed.args.get("order")
    keys: tuple[OrderKey, ...] = ()
    if order_node is not None:
        ordering = _ordering(order_node, projections)
        if isinstance(ordering, Refusal):
            return ordering
        keys = ordering

    counts: dict[str, int | None] = {"limit": None, "offset": None}
    for arg, label in (("limit", "LIMIT"), ("offset", "OFFSET")):
        clause: exp.Expr | None = parsed.args.get(arg)
        if clause is None:
            continue
        count = _row_count(clause, label)
        if isinstance(count, Refusal):
            return count
        counts[arg] = count

    return ValidRequest(
        table=table_name,
        projections=tuple(projections),
        measures=tuple(measures),
        dimensions=tuple(dimensions),
        filter=predicate,
        order=keys,
        limit=counts["limit"],
        offset=counts["offset"],
    )
