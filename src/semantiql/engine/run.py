"""The one entry point from a question to an answer.

This module is a **chokepoint, not a convention**: `run` validates before it compiles and
compiles before it executes, and the adapter API accepts only already-validated SQL. There
is no second path to the data, which is how constitution N1 is held structurally rather
than by everyone remembering to be careful.

If you are adding a way to query — a new CLI verb, an MCP tool, a notebook helper — route
it through `run`. A helper that reaches an adapter directly reintroduces exactly the
failure this design exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from semantiql.adapters.base import Adapter
from semantiql.engine.compile import compile_request
from semantiql.engine.validate import Refusal, validate
from semantiql.knowledge.model import SemanticModel


@dataclass(frozen=True)
class Result:
    """A successful answer, plus the SQL that produced it so a reader can check the work."""

    columns: list[str]
    rows: list[tuple[Any, ...]]
    sql: str


def run(sql: str, model: SemanticModel, adapter: Adapter) -> Result | Refusal:
    """Answer a semantic SQL request, or refuse it. Never guesses."""
    # The model declares which engine it was written for. Executing it on a different one
    # would silently apply another dialect's semantics to the same text, so a mismatch is
    # a refusal rather than a warning.
    if model.datasource.dialect != adapter.dialect:
        return Refusal(
            f"The semantic model declares datasource dialect {model.datasource.dialect!r}, "
            f"but the adapter in use is {adapter.dialect!r}. Refusing rather than running "
            "one engine's SQL against another."
        )

    validated = validate(sql, model)
    if isinstance(validated, Refusal):
        return validated

    relation = adapter.relation(model.tables[validated.table].source)

    physical = compile_request(
        validated,
        model,
        relation=relation,
        dialect=adapter.dialect,
    )
    columns, rows = adapter.execute(physical)
    return Result(columns=columns, rows=rows, sql=physical)
