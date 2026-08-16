"""Validation — the layer that earns the project (constitution N1, N2).

The published evidence behind SemantiQL is that an LLM over a raw schema is right about
16% of the time, a knowledge layer takes it to ~54%, and *checking the query* takes it to
~72%. The check is worth more than the generator, so this module is deliberately strict:

**Anything this engine cannot faithfully compile is refused.** Not approximated, not
silently dropped, not passed to the database to see what happens. That covers two kinds of
thing:

1. Identifiers that do not resolve in the semantic model.
2. Every construct the compiler does not implement — `WHERE`, `HAVING`, `ORDER BY`, `LIMIT`,
   `DISTINCT`, CTEs, subqueries, joins, `TABLESAMPLE`, `PIVOT`, and anything else SQL can
   express.

The second is the one that bites. `compile_request` rebuilds a query from the model rather
than rewriting the user's AST, so any construct left unvalidated would simply *vanish* and
the caller would get a confidently wrong number — `SELECT revenue FROM orders WHERE channel =
'web'` answering with total revenue. A wrong number nobody can detect is precisely the
failure this project exists to prevent, so an unsupported construct is a refusal, and it
stays one until the compiler genuinely implements it.

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
from difflib import get_close_matches

import sqlglot
from sqlglot import exp

from semantiql.knowledge.model import SemanticModel

#: The only SELECT arguments this engine consumes: the projection list, and the FROM.
#: `compile_request` reads nothing else, so any other argument present in the request is a
#: construct that would be dropped. Adding an entry here without teaching the compiler to
#: honour it reopens the silent-drop hole this allowlist closes.
_SELECT_ARGS: frozenset[str] = frozenset({"expressions", "from"})

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
}

#: A backstop for a node type reached through an allowed argument name — the one route the
#: argument check above cannot cover. Same rule as everywhere here: absence refuses, the map
#: only supplies the word.
_NODE_LABELS: dict[type[exp.Expr], str] = {
    exp.TableSample: "TABLESAMPLE",
    exp.Pivot: "PIVOT (and UNPIVOT)",
}


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


@dataclass(frozen=True)
class ValidRequest:
    """A request proven to resolve against the model, ready to compile.

    `projections` preserves the order the caller asked for, so result columns come back in
    the order they were requested rather than an order the compiler found convenient.
    """

    table: str
    projections: tuple[Projection, ...]
    measures: tuple[str, ...]
    dimensions: tuple[str, ...]


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


def _suggest(name: str, candidates: list[str]) -> list[str]:
    """Close matches, case-insensitively — LLM-written SQL is often upper-cased."""
    folded = {c.lower(): c for c in candidates}
    hits = get_close_matches(name.lower(), list(folded), n=3, cutoff=0.5)
    return [folded[h] for h in hits]


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
        if item.entity in table.measures:
            measures.append(item.entity)
        else:
            dimensions.append(item.entity)

    if not measures:
        return Refusal(
            "The request selects no measure, so there is no number to compute. "
            f"Measures on {table_name!r}: {', '.join(sorted(table.measures)) or 'none'}."
        )

    return ValidRequest(
        table=table_name,
        projections=tuple(projections),
        measures=tuple(measures),
        dimensions=tuple(dimensions),
    )
