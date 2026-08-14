"""Validation — the layer that earns the project (constitution N1, N2).

The published evidence behind SemantiQL is that an LLM over a raw schema is right about
16% of the time, a knowledge layer takes it to ~54%, and *checking the query* takes it to
~72%. The check is worth more than the generator, so this module is deliberately strict:

**Anything this engine cannot faithfully compile is refused.** Not approximated, not
silently dropped, not passed to the database to see what happens. That covers two kinds of
thing:

1. Identifiers that do not resolve in the semantic model.
2. Clauses the compiler does not implement — `WHERE`, `HAVING`, `ORDER BY`, `LIMIT`,
   `DISTINCT`, CTEs, subqueries, joins.

The second is the one that bites. `compile_request` rebuilds a query from the model rather
than rewriting the user's AST, so any clause left unvalidated would simply *vanish* and the
caller would get a confidently wrong number — `SELECT revenue FROM orders WHERE channel =
'web'` answering with total revenue. A wrong number nobody can detect is precisely the
failure this project exists to prevent, so an unsupported clause is a refusal, and it stays
one until the compiler genuinely implements it.

`Refusal` carries `did_you_mean` so a refusal is useful, but a suggestion is never applied
automatically — that would reintroduce guessing through the back door.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches

import sqlglot
from sqlglot import exp

from semantiql.knowledge.model import SemanticModel

#: Select arguments the compiler does not implement. Present in the request → refuse.
#: Keep this list exhaustive rather than convenient: an unlisted clause is a silent drop.
_UNSUPPORTED_CLAUSES: tuple[tuple[str, str], ...] = (
    ("where", "WHERE"),
    ("having", "HAVING"),
    ("group", "GROUP BY"),
    ("order", "ORDER BY"),
    ("sort", "SORT BY"),
    ("cluster", "CLUSTER BY"),
    ("distribute", "DISTRIBUTE BY"),
    ("limit", "LIMIT"),
    ("offset", "OFFSET"),
    ("distinct", "DISTINCT"),
    ("qualify", "QUALIFY"),
    ("windows", "WINDOW"),
    ("with", "WITH"),
    ("joins", "JOIN"),
    ("laterals", "LATERAL"),
    ("pivots", "PIVOT"),
    ("locks", "locking clause"),
    ("sample", "TABLESAMPLE"),
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

    # Refuse before resolving identifiers: a dropped clause is a wrong number, which is
    # worse than an unresolved name, and the caller should hear about it first.
    #
    # Both spellings are checked because sqlglot suffixes arg names that collide with
    # Python keywords — `with_`, `from_` — and the suffix has moved between versions.
    # Matching only one spelling is how a clause silently stops being validated.
    for arg, label in _UNSUPPORTED_CLAUSES:
        if parsed.args.get(arg) or parsed.args.get(f"{arg}_"):
            return Refusal(
                f"{label} is not supported yet, and this engine would silently ignore it "
                "rather than apply it — so the request is refused instead of answered with "
                "a number that looks right."
            )

    from_node = parsed.find(exp.From)
    if from_node is None:
        return Refusal("The request names no table.")
    if not isinstance(from_node.this, exp.Table):
        return Refusal("The FROM target must be a single table in the semantic model.")

    tables = list(parsed.find_all(exp.Table))
    if len(tables) > 1:
        return Refusal("Only a single semantic table is supported per request.")

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
