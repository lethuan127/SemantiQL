"""The semantic model: the business-facing interface the AI writes against.

One YAML file is the source of truth (constitution N3), so every field here is validated
at load time. A malformed model fails loudly with a field-level message rather than
surfacing later as a wrong number — N2 applied to configuration.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from semantiql.knowledge.expression import ExpressionError, MetricExpr, parse_expression

Aggregation = Literal["sum", "count", "count_distinct", "min", "max", "avg"]


class _Strict(BaseModel):
    """Reject unknown keys, so a typo in the model is an error and not a silent default."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Dimension(_Strict):
    """A column you group or filter by."""

    column: str
    type: Literal["string", "date", "number", "boolean"] = "string"
    label: str | None = None
    description: str | None = None


class Measure(_Strict):
    """A number, and the one sanctioned way to aggregate it."""

    column: str
    agg: Aggregation
    label: str | None = None
    description: str | None = None


class Metric(_Strict):
    """A number derived from this table's measures — a ratio, a share, a difference.

    The expression is validated when the model loads, not when someone asks for it, so a typo
    in a metric nobody has queried yet is still an error you see immediately.
    """

    expression: str
    label: str | None = None
    description: str | None = None


class Table(_Strict):
    """A physical relation plus the semantics layered over it."""

    source: str
    dimensions: dict[str, Dimension] = Field(default_factory=dict)
    measures: dict[str, Measure] = Field(default_factory=dict)
    metrics: dict[str, Metric] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _names_must_not_overlap(self) -> Table:
        """A name defined twice resolves inconsistently.

        `entity()` would answer with whichever kind it checks first while the compiler builds
        the other, so the same name would mean two things depending on who asked. Reject it
        at load rather than let them disagree.
        """
        kinds: list[tuple[str, list[str]]] = [
            ("a dimension", list(self.dimensions)),
            ("a measure", list(self.measures)),
            ("a metric", list(self.metrics)),
        ]
        seen: dict[str, str] = {}
        for kind, names in kinds:
            for name in names:
                if name in seen:
                    raise ValueError(
                        f"{name} is defined as both {seen[name]} and {kind}; "
                        "each name must be exactly one of them"
                    )
                seen[name] = kind
        return self

    @model_validator(mode="after")
    def _metrics_must_resolve(self) -> Table:
        """Every metric expression parses, and every name in it is a measure of this table."""
        for name, metric in self.metrics.items():
            try:
                parse_expression(metric.expression, self.measures)
            except ExpressionError as exc:
                raise ValueError(f"metric {name!r}: {exc}") from exc
        return self

    def expression_for(self, name: str) -> MetricExpr:
        """The parsed form of a metric. Cannot fail — loading proved it."""
        return parse_expression(self.metrics[name].expression, self.measures)

    def entity(self, name: str) -> Dimension | Measure | Metric | None:
        return self.dimensions.get(name) or self.measures.get(name) or self.metrics.get(name)

    @property
    def entity_names(self) -> list[str]:
        return sorted([*self.dimensions, *self.measures, *self.metrics])

    @property
    def computed_names(self) -> list[str]:
        """Everything that produces a number: measures and metrics."""
        return sorted([*self.measures, *self.metrics])


class Datasource(_Strict):
    """Which engine executes, and therefore which dialect the SQL is transpiled to."""

    name: str
    dialect: Literal["duckdb", "postgres"] = "duckdb"


class SemanticModel(_Strict):
    """The whole model. Built only by `knowledge.loader`."""

    version: Literal[1] = 1
    datasource: Datasource
    tables: dict[str, Table]

    def table(self, name: str) -> Table | None:
        return self.tables.get(name)

    @property
    def table_names(self) -> list[str]:
        return sorted(self.tables)
