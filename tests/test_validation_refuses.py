"""FR-5 / constitution N1, N2 — the tests that matter most in this repo.

A plausible wrong number is the worst possible output, because the end user never sees SQL
and cannot catch it. So: an unresolvable request must be refused, and crucially the
database must never be touched on that path.
"""

from __future__ import annotations

import pytest
from sqlglot import exp

from semantiql.engine.run import run
from semantiql.engine.validate import Refusal, ValidRequest, validate
from semantiql.knowledge.model import SemanticModel


class ExplodingAdapter:
    """Satisfies Adapter structurally, and fails the test if anything reaches the data.

    This is the assertion that makes N1 real: not merely "a refusal came back", but
    "no query was executed".
    """

    @property
    def dialect(self) -> str:
        return "duckdb"

    def relation(self, source: str) -> exp.Expr:  # pragma: no cover
        raise AssertionError(f"a refused request resolved a relation: {source!r}")

    def columns(self, relation: str) -> list[str]:  # pragma: no cover
        raise AssertionError("validation must run before the adapter is consulted")

    def execute(self, sql: str) -> tuple[list[str], list[tuple[object, ...]]]:  # pragma: no cover
        raise AssertionError(f"a refused request reached the database: {sql!r}")


def test_unknown_measure_is_refused_and_never_executed(model: SemanticModel) -> None:
    outcome = run("SELECT profit FROM orders", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)
    assert "profit" in outcome.reason


def test_unknown_table_is_refused(model: SemanticModel) -> None:
    outcome = run("SELECT revenue FROM invoices", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)
    assert "invoices" in outcome.reason


def test_refusal_suggests_but_does_not_substitute(model: SemanticModel) -> None:
    """A near-miss gets a suggestion — and still refuses, rather than guessing for you."""
    outcome = validate("SELECT revenu, channel FROM orders", model)
    assert isinstance(outcome, Refusal)
    assert "revenue" in outcome.did_you_mean


def test_write_statements_are_refused(model: SemanticModel) -> None:
    """Read-only by default (N5) — enforced before the adapter, not by the adapter."""
    outcome = run("DELETE FROM orders", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)


def test_selecting_no_measure_is_refused(model: SemanticModel) -> None:
    """Dimensions alone compute nothing; refusing beats returning a bare column dump."""
    outcome = run("SELECT channel FROM orders", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)
    assert "no measure" in outcome.reason


def test_a_valid_request_passes_validation(model: SemanticModel) -> None:
    outcome = validate("SELECT revenue, channel FROM orders", model)
    assert isinstance(outcome, ValidRequest)
    assert outcome.measures == ("revenue",)
    assert outcome.dimensions == ("channel",)


# --- Clauses the compiler does not implement must be refused, not silently dropped.
#
# This is the regression suite for the worst defect this engine can have: `compile_request`
# rebuilds the query from the model, so any clause left unvalidated simply disappears and
# the caller receives a confidently wrong number. Every entry here was a silent wrong
# answer before the fix.


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT revenue FROM orders WHERE channel = 'web'",
        "SELECT revenue FROM orders WHERE amount > 1000000",
        "SELECT revenue, channel FROM orders HAVING SUM(amount) > 900",
        "SELECT revenue FROM orders LIMIT 1",
        "SELECT revenue FROM orders OFFSET 2",
        "SELECT revenue, channel FROM orders ORDER BY revenue DESC",
        "SELECT DISTINCT revenue FROM orders",
        "SELECT revenue, channel FROM orders GROUP BY channel",
        "WITH x AS (SELECT 1 AS revenue) SELECT revenue FROM orders",
        "SELECT revenue FROM (SELECT * FROM orders)",
        "SELECT revenue FROM orders JOIN other ON 1 = 1",
        "SELECT revenue FROM orders, other",
        "SELECT revenue FROM orders UNION SELECT revenue FROM orders",
    ],
)
def test_unsupported_clauses_are_refused_never_dropped(sql: str, model: SemanticModel) -> None:
    outcome = run(sql, model, ExplodingAdapter())
    assert isinstance(outcome, Refusal), f"silently accepted and would drop a clause: {sql}"


def test_the_refusal_names_the_clause(model: SemanticModel) -> None:
    """A refusal a user cannot act on is only half useful."""
    outcome = run("SELECT revenue FROM orders WHERE channel = 'web'", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)
    assert "WHERE" in outcome.reason


def test_dialect_mismatch_is_refused(model: SemanticModel) -> None:
    """A model written for one engine must not be run against another."""

    class Postgresish(ExplodingAdapter):
        @property
        def dialect(self) -> str:
            return "postgres"

    outcome = run("SELECT revenue FROM orders", model, Postgresish())
    assert isinstance(outcome, Refusal)
    assert "postgres" in outcome.reason


def test_case_insensitive_suggestion(model: SemanticModel) -> None:
    """LLM-written SQL is often upper-cased; a refusal should still help."""
    outcome = run("SELECT REVENUE FROM orders", model, ExplodingAdapter())
    assert isinstance(outcome, Refusal)
    assert "revenue" in outcome.did_you_mean
