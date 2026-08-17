"""The MCP server — the interface SemantiQL was designed for (spec 012).

Semantic SQL was never meant for a person to type. The whole architecture assumes an LLM
writes it, gets told when it is wrong, and fixes it; until this module existed there was no
LLM in the loop, so the language had no author and the engine was finished for someone who
could not reach it.

Two tools, and the fact that there are only two is the point. A skill telling Claude to run
`semantiql` in a shell would work, and would also hand the model a shell — from which it could
reach the database by any route it liked. The tool surface **is** the enforcement boundary:
these two calls are the only things a client can do, and one of them cannot touch data at all.

`query` reaches data through `engine.run.run` and nothing else, exactly as the CLI does. No
second path (N1).

A refusal comes back as a **normal answer** carrying its reason, never as a failed call. That
is not politeness — `Refusal` is the designed outcome, and the reason is what lets Claude
repair its own query instead of apologising to the user. Reporting it as an error would tell
the client "the tool broke" when the truth is "that question cannot be answered from this
model, and here is why".

Local stdio only, deliberately (constitution). The SDK also ships
`run_streamable_http_async`, so going remote later is a transport change rather than a
rewrite — which is why nothing below assumes it shares a process with its caller.
"""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from semantiql.adapters.base import Adapter, AdapterError
from semantiql.engine.run import Result, run
from semantiql.engine.validate import Refusal
from semantiql.knowledge.model import SemanticModel

#: What the client is told before it writes anything. Spent on the dialect and on what is
#: refused, because the alternative is Claude discovering the supported subset by collecting
#: refusals — one round trip each. Spec 013 moves the longer form into a skill, where it can
#: be markdown in git rather than one string; the essentials stay here so the server is useful
#: on its own.
INSTRUCTIONS = """\
SemantiQL answers questions about a business database through a semantic model.

Call `describe_model` first. It lists the tables, and for each one the dimensions (things to
group or filter by), measures (numbers) and metrics (numbers derived from measures), with
their labels and descriptions. Use those names — they are the only ones that exist.

Then call `query` with semantic SQL:

    SELECT <measures and dimensions> FROM <table>
    [WHERE <dimension> <op> <literal> ...]
    [ORDER BY <a name you selected> [DESC]] [LIMIT n]

Write no GROUP BY — naming a measure and a dimension together implies it. A time grain is
`DATE_TRUNC('month', <date dimension>)`; grains are year, quarter, month, week, day.

One table per query. No JOIN, no HAVING, no DISTINCT, no subqueries, no window functions —
these are refused rather than ignored.

A refusal is a normal reply with `refused: true` and a reason. Read the reason and fix the
query: it names the entity that does not exist, and often suggests the right one. Do not
invent a measure or metric that `describe_model` did not list, and never estimate a number
the model cannot compute — say it is not defined and stop.\
"""


class Entity(BaseModel):
    """One dimension, measure or metric, as the client sees it."""

    name: str
    kind: str
    type: str | None = Field(default=None, description="A dimension's declared type.")
    aggregation: str | None = Field(default=None, description="How a measure is aggregated.")
    expression: str | None = Field(default=None, description="What a metric is derived from.")
    label: str | None = None
    description: str | None = None


class TableSummary(BaseModel):
    """One line of the index: enough to choose a table, not enough to answer with.

    The counts are deliberate. They tell Claude whether `orders` is the table carrying the revenue
    measure without sending the measures, which is the whole trick that keeps a thirty-table model
    describable in one small reply.
    """

    name: str
    description: str | None = None
    dimensions: int
    measures: int
    metrics: int


class TableInfo(BaseModel):
    """One table's semantics. Physical column names are deliberately absent.

    The client asks in business vocabulary and gets answers in it; showing the underlying
    columns would invite it to write SQL against them, which is the thing the semantic layer
    exists to stop.
    """

    name: str
    entities: list[Entity]


class ModelInfo(BaseModel):
    """What `describe_model` returns — one shape whether or not detail was asked for.

    `tables` is always the full index; `detail` carries entities for the table that was asked for,
    or for the only table there is. A client branching on which *fields* are present would
    eventually branch wrongly, so both are always there and `detail` is simply empty when there is
    nothing to show — with `next_step` saying what to do about it.
    """

    datasource: str
    dialect: str
    tables: list[TableSummary] = Field(description="Every table, as an index.")
    detail: list[TableInfo] = Field(
        default_factory=list, description="Full entities for the requested table, if any."
    )
    next_step: str | None = Field(
        default=None, description="What to call next when detail is empty."
    )


class Answer(BaseModel):
    """What `query` returns — for a refusal as much as for an answer.

    One shape either way, on purpose. A client that has to branch on the *shape* of a result
    will eventually branch wrongly; a client branching on `refused` cannot. The pydantic type
    is also what publishes this as the tool's output schema — a plain `dict` return leaves
    structured content empty (measured, spec 012 clarification Q3).
    """

    refused: bool = Field(description="True when the question cannot be answered from the model.")
    reason: str | None = Field(
        default=None,
        description="Why it was refused, and often what to use instead. Read this and retry.",
    )
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    sql: str | None = Field(
        default=None, description="The physical SQL that ran, so the work can be checked."
    )


def _entities(table: Any) -> list[Entity]:
    """Flatten one table's dimensions, measures and metrics into one list."""
    out: list[Entity] = []
    for name, dimension in sorted(table.dimensions.items()):
        out.append(
            Entity(
                name=name,
                kind="dimension",
                type=dimension.type,
                label=dimension.label,
                description=dimension.description,
            )
        )
    for name, measure in sorted(table.measures.items()):
        out.append(
            Entity(
                name=name,
                kind="measure",
                aggregation=measure.agg,
                label=measure.label,
                description=measure.description,
            )
        )
    for name, metric in sorted(table.metrics.items()):
        out.append(
            Entity(
                name=name,
                kind="metric",
                expression=metric.expression,
                label=metric.label,
                description=metric.description,
            )
        )
    return out


def build_server(model: SemanticModel, adapter: Adapter, *, version: str = "0.0.2") -> MCPServer:
    """Register the tools over an already-open model and adapter.

    Separate from `serve` so tests can build a server without starting one — and so neither
    tool closes over module state, which would make two tests share one adapter.
    """
    mcp: MCPServer = MCPServer(
        name="semantiql",
        title="SemantiQL",
        version=version,
        instructions=INSTRUCTIONS,
    )
    read_only = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True)

    @mcp.tool(annotations=read_only)
    def describe_model(table: str | None = None) -> ModelInfo:
        """List what can be asked. Call this before `query`.

        With no argument you get every table as an index — name, description, and how many
        dimensions, measures and metrics each has. Pass a table name to get that table's
        dimensions, measures and metrics in full.

        The exception: a model with exactly one table returns it in full immediately, because
        there is nothing to choose between.

        The names returned are the only ones that exist. Anything else is refused.
        """
        index = [
            TableSummary(
                name=name,
                description=model.tables[name].description,
                dimensions=len(model.tables[name].dimensions),
                measures=len(model.tables[name].measures),
                metrics=len(model.tables[name].metrics),
            )
            for name in model.table_names
        ]
        info = ModelInfo(
            datasource=model.datasource.name, dialect=model.datasource.dialect, tables=index
        )

        if table is not None:
            if table not in model.tables:
                # Answering with the available names rather than an empty reply: the usual cause is
                # a near-miss, and the fix is one retry rather than another round trip to find out
                # what exists.
                info.next_step = (
                    f"There is no table {table!r}. Available: "
                    f"{', '.join(model.table_names)}. Call describe_model with one of those."
                )
                return info
            wanted = [table]
        elif len(model.table_names) == 1:
            # Nothing to choose, so choosing would only cost a round trip.
            wanted = model.table_names
        else:
            info.next_step = (
                "Call describe_model again with `table` set to the one you need, to see its "
                "dimensions, measures and metrics."
            )
            return info

        info.detail = [
            TableInfo(name=name, entities=_entities(model.tables[name])) for name in wanted
        ]
        return info

    @mcp.tool(annotations=read_only)
    def query(sql: str) -> Answer:
        """Answer a question written as semantic SQL, or explain why it cannot be answered.

        `SELECT <measures and dimensions> FROM <table>` with optional `WHERE` over dimensions,
        `ORDER BY` a selected name, and `LIMIT`. Never write `GROUP BY`. One table only; no
        JOIN, HAVING, DISTINCT or subqueries.

        A refusal is not a failure: it comes back with `refused: true` and a reason naming what
        does not exist. Read it and retry rather than guessing, and never estimate a number the
        model cannot compute.
        """
        try:
            outcome = run(sql, model, adapter)
        except AdapterError as exc:
            # The database refused or could not be reached. A failed call, not a refusal —
            # nothing is wrong with the question. The server stays up either way (FR-9).
            raise ToolFailure(f"the datasource could not answer: {exc}") from exc

        if isinstance(outcome, Refusal):
            return Answer(refused=True, reason=str(outcome))

        return _answer(outcome)

    return mcp


class ToolFailure(Exception):
    """A call that genuinely failed, as distinct from a question that was refused.

    Kept separate from `Refusal` all the way to the client. Collapsing the two would teach
    Claude that "not defined in your model" and "the database is unreachable" deserve the same
    response, and they do not: one is repaired by rewriting the query, the other cannot be
    repaired by the model at all.
    """


def _answer(result: Result) -> Answer:
    """A successful `Result`, as the client sees it.

    Cells are stringified. JSON has no `Decimal` and no `date`, and letting a float stand in
    for a decimal is how money loses a penny on the way out — so the exact printed value
    travels instead, and the client formats it.
    """
    return Answer(
        refused=False,
        columns=list(result.columns),
        rows=[[None if cell is None else str(cell) for cell in row] for row in result.rows],
        row_count=len(result.rows),
        sql=result.sql,
    )


def serve(model: SemanticModel, adapter: Adapter, *, version: str = "0.0.2") -> None:
    """Run the server on stdio until the client disconnects, then release the adapter.

    The model is loaded and the adapter opened by the caller, before this is reached, so a
    broken model or an unreachable database fails at startup rather than producing a server
    that looks healthy and refuses every question (FR-8).
    """
    try:
        build_server(model, adapter, version=version).run(transport="stdio")
    finally:
        adapter.close()
