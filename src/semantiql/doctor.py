"""Check a semantic model against the database it describes.

Nothing else does. The engine resolves a request against the *model* and refuses what does not
fit; whether the model itself fits the database is discovered one query at a time, as an
adapter error naming a physical column the author then has to map back to the YAML.

That got worse as the model gained power. `type:` was documentation until filters arrived;
it now decides which literals a filter accepts and whether a date is cast, so a dimension
typed `string` over a real `DATE` column refuses `order_date >= '2026-07-01'` with a message
about quoting — sending the author to fix a query that was already correct.

Doctor reads schema metadata and reports. It does not query data, it is not a second path to
it, and it never edits the model: the YAML is the source of truth (N3) and a suggestion here
carries exactly the authority a refusal's `did_you_mean` does — a hint for a human, applied by
a human.

Deliberately outside `engine/`. The engine has one job and one chokepoint; a checker living
next to it would blur that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches

from semantiql.adapters.base import Adapter, AdapterError, Column, ColumnKind
from semantiql.knowledge.model import Measure, SemanticModel

#: Aggregations that need arithmetic. `count`, `count_distinct`, `min` and `max` apply to
#: anything, so only these two can be wrong about their column.
_NUMERIC_AGGS = frozenset({"sum", "avg"})


@dataclass(frozen=True)
class Finding:
    """One thing doctor noticed, as data rather than as a printed line.

    The CLI decides what a tick looks like; a test asserts on `level` and `table` and never has
    to parse prose.
    """

    level: str
    """`ok` or `problem`."""

    table: str | None
    message: str
    suggestions: list[str] = field(default_factory=list)

    @property
    def is_problem(self) -> bool:
        return self.level == "problem"

    def __str__(self) -> str:
        if self.suggestions:
            return f"{self.message}  (did you mean: {', '.join(self.suggestions)}?)"
        return self.message


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _suggest(name: str, candidates: list[str]) -> list[str]:
    """Close matches, case-insensitively — the same courtesy a refusal extends."""
    folded = {candidate.lower(): candidate for candidate in candidates}
    hits = get_close_matches(name.lower(), list(folded), n=3, cutoff=0.5)
    return [folded[hit] for hit in hits]


def _find(columns: list[Column], name: str) -> Column | None:
    """Locate a column case-insensitively, because DuckDB resolves identifiers that way."""
    wanted = name.lower()
    for column in columns:
        if column.name.lower() == wanted:
            return column
    return None


def _check_entity(
    kind: str,
    entity_name: str,
    column_name: str,
    columns: list[Column],
    table_name: str,
) -> Finding | None:
    """The check both dimensions and measures need: does the column exist at all?"""
    if _find(columns, column_name) is not None:
        return None
    return Finding(
        level="problem",
        table=table_name,
        message=f"{kind} {entity_name!r} reads column {column_name!r}, which does not exist",
        suggestions=_suggest(column_name, [c.name for c in columns]),
    )


def _check_declared_type(
    entity_name: str, declared: str, column: Column, table_name: str
) -> Finding | None:
    """Compare the model's `type:` with what the column really is.

    `other` is silence: an adapter that cannot classify a type has told us it does not know,
    and inventing a mismatch from that would be worse than saying nothing.
    """
    if column.kind == "other" or column.kind == declared:
        return None
    return Finding(
        level="problem",
        table=table_name,
        message=(
            f"dimension {entity_name!r} is declared {declared}, but column "
            f"{column.name!r} is {column.native_type} — filters on it will be typed wrongly"
        ),
    )


def _check_aggregation(
    measure_name: str, measure: Measure, column: Column, table_name: str
) -> Finding | None:
    """`sum` and `avg` need arithmetic; the rest apply to anything."""
    if measure.agg not in _NUMERIC_AGGS:
        return None
    if column.kind in {"number", "other"}:
        return None
    return Finding(
        level="problem",
        table=table_name,
        message=(
            f"measure {measure_name!r} applies {measure.agg} to column {column.name!r}, "
            f"which is {column.native_type} — the database will reject that when asked"
        ),
    )


def check(model: SemanticModel, adapter: Adapter) -> list[Finding]:
    """Every way this model and this datasource disagree, in the order a reader wants them."""
    findings: list[Finding] = []

    if model.datasource.dialect != adapter.dialect:
        findings.append(
            Finding(
                level="problem",
                table=None,
                message=(
                    f"the model declares dialect {model.datasource.dialect!r} but the adapter "
                    f"in use is {adapter.dialect!r}; every request would be refused"
                ),
            )
        )
    else:
        findings.append(
            Finding(
                level="ok",
                table=None,
                message=f"datasource {model.datasource.name!r} speaks {adapter.dialect}",
            )
        )

    for table_name in model.table_names:
        table = model.tables[table_name]
        try:
            columns = adapter.columns(table.source)
        except AdapterError as exc:
            # Nothing below is checkable, and a dozen "column not found" lines under a missing
            # table teach nothing about the one thing that is wrong.
            findings.append(
                Finding(
                    level="problem",
                    table=table_name,
                    message=f"source {table.source!r} cannot be read: {exc}",
                )
            )
            continue

        findings.append(
            Finding(
                level="ok",
                table=table_name,
                message=f"source {table.source!r} has {len(columns)} columns",
            )
        )

        problems = 0
        for name, dimension in table.dimensions.items():
            missing = _check_entity("dimension", name, dimension.column, columns, table_name)
            if missing is not None:
                findings.append(missing)
                problems += 1
                continue
            column = _find(columns, dimension.column)
            assert column is not None  # _check_entity returned None, so it is there
            mistyped = _check_declared_type(name, dimension.type, column, table_name)
            if mistyped is not None:
                findings.append(mistyped)
                problems += 1

        for name, measure in table.measures.items():
            missing = _check_entity("measure", name, measure.column, columns, table_name)
            if missing is not None:
                findings.append(missing)
                problems += 1
                continue
            column = _find(columns, measure.column)
            assert column is not None
            unusable = _check_aggregation(name, measure, column, table_name)
            if unusable is not None:
                findings.append(unusable)
                problems += 1

        if problems == 0:
            findings.append(
                Finding(
                    level="ok",
                    table=table_name,
                    message=(
                        f"{_plural(len(table.dimensions), 'dimension')}, "
                        f"{_plural(len(table.measures), 'measure')} and "
                        f"{_plural(len(table.metrics), 'metric')} all resolve"
                    ),
                )
            )

    return findings


def problems(findings: list[Finding]) -> list[Finding]:
    return [finding for finding in findings if finding.is_problem]


__all__ = ["Column", "ColumnKind", "Finding", "check", "problems"]
