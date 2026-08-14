"""The semantic model: the business-facing interface the AI writes against.

One YAML file is the source of truth (constitution N3), so every field here is validated
at load time. A malformed model fails loudly with a field-level message rather than
surfacing later as a wrong number — N2 applied to configuration.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class Table(_Strict):
    """A physical relation plus the semantics layered over it."""

    source: str
    dimensions: dict[str, Dimension] = Field(default_factory=dict)
    measures: dict[str, Measure] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _names_must_not_overlap(self) -> Table:
        """A name defined as both a dimension and a measure resolves inconsistently.

        `entity()` would answer with the dimension while the compiler aggregates the
        measure, so the same name would mean two things depending on who asked. Reject it
        at load rather than let the two disagree.
        """
        clash = sorted(set(self.dimensions) & set(self.measures))
        if clash:
            raise ValueError(
                f"{', '.join(clash)} defined as both a dimension and a measure; "
                "each name must be one or the other"
            )
        return self

    def entity(self, name: str) -> Dimension | Measure | None:
        return self.dimensions.get(name) or self.measures.get(name)

    @property
    def entity_names(self) -> list[str]:
        return sorted([*self.dimensions, *self.measures])


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
