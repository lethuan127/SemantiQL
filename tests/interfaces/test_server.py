"""The MCP server, driven in-process — no Claude Desktop, no subprocess, no database.

`anyio.run` drives the SDK's coroutines from ordinary sync tests, so this needs no pytest
plugin and no new dev dependency (`anyio` arrives with `mcp`). What it exercises is what the
client actually sees: which tools exist, the schemas generated from the type hints, the
annotations, and the answers.

Deliberately not a subprocess speaking the protocol over stdio. That is more faithful and far
more fragile — a handshake and a timeout in the gate — and it tests the SDK's transport rather
than this project's tools. `mcp.shared.memory` has the streams for it if transport behaviour
ever needs its own test.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

import anyio
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from semantiql.adapters.base import Adapter, AdapterError, Column
from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.knowledge.model import SemanticModel
from semantiql.server import INSTRUCTIONS, Entity, build_server

T = TypeVar("T")


def _run(coro: Callable[[], Awaitable[T]]) -> T:
    return anyio.run(coro)


@pytest.fixture
def server(model: SemanticModel, adapter: DuckDBAdapter) -> Any:
    """A real server over the retail example. `build_server` never starts anything."""
    return build_server(model, adapter)


def _call(server: Any, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """One tool call, returning the structured content the client would receive."""

    async def go() -> Any:
        return await server.call_tool(name, arguments or {})

    result = _run(go)
    assert result.structured_content is not None, (
        "structured_content is empty — the tool's return type is no longer a pydantic model, "
        "which is the only thing that populates it (spec 012, clarification Q3)"
    )
    content: dict[str, Any] = result.structured_content
    return content


def _tools(server: Any) -> dict[str, Any]:
    async def go() -> Any:
        return await server.list_tools()

    return {t.name: t for t in _run(go)}


# --- The surface a client sees


def test_exactly_two_tools_are_exposed(server: Any) -> None:
    """The size of this surface is a design property, not an accident.

    These two calls are the only things a client can do. A skill that told Claude to run the
    CLI in a shell would be easier and would also hand it a shell, from which the database is
    reachable by any route. Adding a tool here widens the boundary the whole project rests on,
    so the count is asserted rather than left to drift.
    """
    assert sorted(_tools(server)) == ["describe_model", "query"]


def test_both_tools_declare_themselves_read_only(server: Any) -> None:
    """N5, made visible to the client rather than merely true."""
    for name, tool in _tools(server).items():
        assert tool.annotations.read_only_hint is True, name
        assert tool.annotations.destructive_hint is False, name


def test_query_takes_one_required_string(server: Any) -> None:
    """The schema is generated from the type hint, so this pins the contract, not the syntax."""
    schema = _tools(server)["query"].input_schema
    assert list(schema["properties"]) == ["sql"]
    assert schema["properties"]["sql"]["type"] == "string"
    assert schema["required"] == ["sql"]


def test_describe_model_takes_one_optional_argument(server: Any) -> None:
    """It gained `table` in spec 015. Omitting it must stay valid — that is the common call."""
    schema = _tools(server)["describe_model"].input_schema
    assert list(schema.get("properties", {})) == ["table"]
    assert "table" not in schema.get("required", [])


def test_both_tools_publish_an_output_schema(server: Any) -> None:
    """What a plain `dict` return would not give us — the client can see the answer's shape."""
    for name, tool in _tools(server).items():
        assert tool.output_schema, f"{name} has no output schema"
        assert "properties" in tool.output_schema


def test_the_instructions_name_the_refusal_contract(server: Any) -> None:
    """The client is told a refusal is repairable before it ever sees one.

    Without this the model discovers the supported subset by collecting refusals, one round
    trip each — and, worse, may treat a refusal as a failure and apologise instead of retrying.
    """
    assert "refused" in INSTRUCTIONS
    assert "describe_model" in INSTRUCTIONS
    assert "GROUP BY" in INSTRUCTIONS, "the no-GROUP-BY rule is the most common mistake"


# --- describe_model


def test_describe_model_lists_the_tables_and_entities(server: Any) -> None:
    """Entities live under `detail` since spec 015; `tables` is the index.

    The retail model has one table, so detail arrives without asking — there is nothing to choose
    between and a second round trip would only cost a turn.
    """
    described = _call(server, "describe_model")
    assert described["dialect"] == "duckdb"
    assert [t["name"] for t in described["tables"]] == ["orders"]
    kinds = {e["kind"] for e in described["detail"][0]["entities"]}
    assert kinds == {"dimension", "measure", "metric"}


def test_describe_model_surfaces_labels_and_descriptions(server: Any) -> None:
    """The first thing in the project to read these two fields.

    They have been in the model schema, documented and written by every model author, with no
    consumer at all — `docs/09-data-modeling.md` said so in as many words. This is why they
    exist: they are how Claude maps "revenue" in a question onto `revenue` in the model.
    """
    entities = {e["name"]: e for e in _call(server, "describe_model")["detail"][0]["entities"]}
    assert entities["revenue"]["label"] == "Revenue"
    assert "sanctioned definition" in entities["revenue"]["description"]
    assert entities["channel"]["label"] == "Sales channel"


def test_describe_model_does_not_expose_physical_columns(server: Any) -> None:
    """`revenue` is `SUM(amount)`, and the client is told `revenue`, never the column.

    Exposing the underlying column would invite the model to write SQL against it, which is
    what the semantic layer exists to prevent.

    Asserted structurally rather than by searching the payload for "amount": a `description` is
    free text an author wrote, and the retail model's happens to say "Sum of order amounts".
    That is the author describing a measure, not the server leaking a field — so the test looks
    at the fields.
    """
    entities = _call(server, "describe_model")["detail"][0]["entities"]
    assert entities, "nothing to check"
    for entity in entities:
        assert "column" not in entity, entity
    # The declared shape, not just this payload — a future field called `column` fails here.
    assert "column" not in Entity.model_fields


def test_describe_model_never_touches_the_datasource(model: SemanticModel) -> None:
    """It reads the model. An adapter that is consulted at all fails this test."""

    class Exploding:
        @property
        def dialect(self) -> str:
            return "duckdb"

        def relation(self, source: str) -> Any:  # pragma: no cover
            raise AssertionError("describe_model resolved a relation")

        def columns(self, source: str) -> list[Column]:  # pragma: no cover
            raise AssertionError("describe_model read the schema")

        def execute(self, sql: str) -> Any:  # pragma: no cover
            raise AssertionError("describe_model reached the database")

        def close(self) -> None:
            pass

    exploding: Adapter = Exploding()
    assert _call(build_server(model, exploding), "describe_model")["tables"]


# --- query


def test_a_real_question_is_answered(server: Any) -> None:
    answer = _call(server, "query", {"sql": "SELECT revenue, channel FROM orders"})
    assert answer["refused"] is False
    assert answer["reason"] is None
    assert sorted(answer["columns"]) == ["channel", "revenue"]
    assert answer["row_count"] == 3
    channel = answer["columns"].index("channel")
    assert {row[channel] for row in answer["rows"]} == {"web", "retail", "partner"}


def test_the_answer_carries_the_sql_that_ran(server: Any) -> None:
    """So a human can check the work, and so Claude can quote it when asked how it got there."""
    answer = _call(server, "query", {"sql": "SELECT revenue, channel FROM orders"})
    assert answer["sql"] is not None
    assert "SUM(amount)" in answer["sql"]
    assert "GROUP BY" in answer["sql"]


def test_a_refusal_is_an_answer_and_not_an_error(server: Any) -> None:
    """The single most important behaviour in this module.

    A refusal reported as a failed call tells Claude "the tool broke", and Claude apologises to
    the user. Reported as an answer with a reason, Claude reads the reason and fixes its query.
    That difference is the whole repair half of check-and-repair.
    """
    answer = _call(server, "query", {"sql": "SELECT profit FROM orders"})
    assert answer["refused"] is True
    assert "profit" in answer["reason"]
    assert answer["rows"] == []
    assert answer["row_count"] == 0


def test_a_refusal_suggestion_survives_the_trip(server: Any) -> None:
    """The suggestion is what turns two round trips into one, so it must not be dropped."""
    answer = _call(server, "query", {"sql": "SELECT revenue, chanel FROM orders"})
    assert answer["refused"] is True
    assert "channel" in answer["reason"], answer["reason"]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT revenue FROM orders JOIN other ON 1=1",
        "SELECT DISTINCT revenue FROM orders",
        "SELECT revenue FROM orders HAVING revenue > 1",
        "DELETE FROM orders",
    ],
)
def test_unsupported_sql_is_refused_with_a_reason(server: Any, sql: str) -> None:
    """Refused, never silently dropped — and the reason reaches the client intact."""
    answer = _call(server, "query", {"sql": sql})
    assert answer["refused"] is True
    assert answer["reason"]


def test_a_missing_argument_raises_rather_than_answering(server: Any) -> None:
    """A malformed *call* is a real failure, unlike a well-formed question that cannot be met."""

    async def go() -> Any:
        return await server.call_tool("query", {})

    with pytest.raises(ToolError):
        _run(go)


def test_an_adapter_failure_is_a_failed_call_not_a_refusal(model: SemanticModel) -> None:
    """ "Your model has no profit" and "the database is down" must not look the same.

    One is repaired by rewriting the query; the other cannot be repaired by the model at all.
    Collapsing them would teach Claude to retry a query that will never work.
    """

    class Unreachable:
        @property
        def dialect(self) -> str:
            return "duckdb"

        def relation(self, source: str) -> Any:
            return DuckDBAdapter.relation(source)

        def columns(self, source: str) -> list[Column]:  # pragma: no cover
            return []

        def execute(self, sql: str) -> Any:
            raise AdapterError("connection reset by peer")

        def close(self) -> None:
            pass

    broken: Adapter = Unreachable()

    async def go() -> Any:
        return await build_server(model, broken).call_tool(
            "query", {"sql": "SELECT revenue FROM orders"}
        )

    with pytest.raises(ToolError, match="datasource could not answer"):
        _run(go)


# --- describe_model at scale (spec 015). A thirty-table model described in full would crowd out
# the conversation and make Claude likelier to pick a plausible entity from a table nobody asked
# about — so the index comes first and the definitions come on request.


@pytest.fixture
def big_server(tmp_path: Path) -> Any:
    """A two-table model, which is the smallest thing that has to be chosen between."""
    from semantiql.adapters.duckdb import DuckDBAdapter as _Duck
    from semantiql.knowledge.loader import load_model

    (tmp_path / "ds.yml").write_text("version: 1\ndatasource: {name: w, dialect: duckdb}\n")
    (tmp_path / "a.yml").write_text(
        "tables:\n  orders:\n    source: orders\n"
        "    description: One row per order line, not per order.\n"
        "    dimensions:\n      channel: {column: channel, type: string}\n"
        "    measures:\n      revenue: {column: amount, agg: sum}\n"
    )
    (tmp_path / "b.yml").write_text(
        "tables:\n  tickets:\n    source: tickets\n"
        "    measures:\n      n: {column: id, agg: count}\n"
    )
    return build_server(load_model(tmp_path), _Duck())


def test_one_table_is_described_in_full_immediately(server: Any) -> None:
    """Nothing to choose, so a second round trip would only cost a turn."""
    described = _call(server, "describe_model")
    assert [t["name"] for t in described["tables"]] == ["orders"]
    assert [d["name"] for d in described["detail"]] == ["orders"]
    assert described["next_step"] is None


def test_several_tables_return_an_index_not_every_definition(big_server: Any) -> None:
    """The scale property: one small reply regardless of how many tables exist."""
    described = _call(big_server, "describe_model")
    assert [t["name"] for t in described["tables"]] == ["orders", "tickets"]
    assert described["detail"] == [], "definitions must not be sent unasked"
    assert "describe_model" in (described["next_step"] or ""), "the reply must say what to do next"


def test_the_index_carries_what_is_needed_to_choose(big_server: Any) -> None:
    """Counts and a description — enough to pick a table, not enough to answer with."""
    orders = next(t for t in _call(big_server, "describe_model")["tables"] if t["name"] == "orders")
    assert orders["description"] == "One row per order line, not per order."
    assert (orders["dimensions"], orders["measures"], orders["metrics"]) == (1, 1, 0)


def test_naming_a_table_returns_its_definitions(big_server: Any) -> None:
    described = _call(big_server, "describe_model", {"table": "orders"})
    assert [d["name"] for d in described["detail"]] == ["orders"]
    assert {e["name"] for e in described["detail"][0]["entities"]} == {"channel", "revenue"}
    assert described["tables"], "the index stays present, so one shape covers both replies"


def test_an_unknown_table_is_answered_with_the_real_ones(big_server: Any) -> None:
    """The usual cause is a near-miss, and the fix is a retry rather than another round trip."""
    described = _call(big_server, "describe_model", {"table": "order"})
    assert described["detail"] == []
    assert "orders" in described["next_step"] and "tickets" in described["next_step"]


def test_the_tool_count_is_still_two(big_server: Any) -> None:
    """This added an argument, not a tool. The surface is the enforcement boundary."""
    assert sorted(_tools(big_server)) == ["describe_model", "query"]
    schema = _tools(big_server)["describe_model"].input_schema
    assert list(schema.get("properties", {})) == ["table"]
    assert "table" not in schema.get("required", []), "omitting it must stay valid"


def test_serve_releases_the_adapter_even_when_the_loop_fails(model: SemanticModel) -> None:
    """A server that crashes must not leave the connection open.

    For Postgres that connection holds a read-only transaction; leaking it on a crash means a
    snapshot pinned until the process is reaped. The `finally` in `serve` is what prevents it, and
    a `finally` nobody tests is a `finally` someone deletes.
    """
    from semantiql.server import serve

    closed: list[bool] = []

    class Counting:
        @property
        def dialect(self) -> str:
            return "duckdb"

        def relation(self, source: str) -> Any:  # pragma: no cover - never reached
            raise AssertionError

        def columns(self, source: str) -> list[Column]:  # pragma: no cover - never reached
            raise AssertionError

        def execute(self, sql: str) -> Any:  # pragma: no cover - never reached
            raise AssertionError

        def close(self) -> None:
            closed.append(True)

    adapter: Adapter = Counting()

    # stdio has no streams under pytest, so the transport raises — which is the point: the failure
    # is what has to leave the adapter closed.
    with pytest.raises(BaseException):  # noqa: B017 - anyio wraps whatever stdio raises
        serve(model, adapter)

    assert closed == [True], "serve must close the adapter on the way out, crash or not"
