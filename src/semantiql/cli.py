"""The `semantiql` command line.

Deliberately thin: parse arguments, call `engine.run.run`, print. Every path to the data
goes through that one function, so the CLI cannot become a way around validation.
"""

from __future__ import annotations

import argparse
import sys

from semantiql.adapters.base import AdapterError
from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.doctor import Finding, check, problems
from semantiql.engine.run import Result, run
from semantiql.engine.validate import Refusal
from semantiql.knowledge.loader import ModelError, load_model

EXAMPLE_MODEL = "examples/retail/semantic_model.yml"

#: Verbs the docs and roadmap promise but that are not built yet. Without this, `semantiql
#: init` is parsed as SQL and answered with "Only SELECT is supported, and this is COLUMN"
#: — a confusing message from the validation layer about a command the README advertises.
NOT_YET_IMPLEMENTED = {
    "init": "the guided setup wizard that generates a semantic model from your database",
}


def _render(result: Result) -> str:
    widths = [len(c) for c in result.columns]
    for row in result.rows:
        widths = [max(w, len(str(v))) for w, v in zip(widths, row, strict=True)]
    lines = ["  ".join(c.ljust(w) for c, w in zip(result.columns, widths, strict=True))]
    lines.append("  ".join("-" * w for w in widths))
    for row in result.rows:
        lines.append("  ".join(str(v).ljust(w) for v, w in zip(row, widths, strict=True)))
    return "\n".join(lines)


def _render_findings(findings: list[Finding]) -> str:
    """Group by table, so a reader sees one heading and its problems beneath it."""
    lines: list[str] = []
    current: str | None = ""
    for finding in findings:
        if finding.table != current:
            current = finding.table
            if current is not None:
                lines.append(current)
        mark = "✗" if finding.is_problem else "✓"
        indent = "  " if finding.table is not None else ""
        lines.append(f"{indent}{mark} {finding}")
    return "\n".join(lines)


def _doctor(model_path: str, database: str) -> int:
    """Report where the model and the database disagree. Never edits either."""
    try:
        model = load_model(model_path)
    except ModelError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        adapter = DuckDBAdapter(database)
    except AdapterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    try:
        findings = check(model, adapter)
    finally:
        adapter.close()

    print(_render_findings(findings))
    failed = problems(findings)
    tables = len(model.table_names)
    noun = "table" if tables == 1 else "tables"
    if failed:
        print(
            f"\n{tables} {noun} checked, {len(failed)} "
            f"{'problem' if len(failed) == 1 else 'problems'} found.",
            file=sys.stderr,
        )
        return 1
    print(f"\n{tables} {noun} checked, no problems found.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="semantiql",
        description="Query a database through a semantic model.",
    )
    parser.add_argument(
        "sql",
        nargs="?",
        help="semantic SQL, e.g. 'SELECT revenue, channel FROM orders' — or the verb 'doctor'",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=EXAMPLE_MODEL,
        help=f"path to the semantic model YAML (default: {EXAMPLE_MODEL})",
    )
    parser.add_argument("--show-sql", action="store_true", help="print the generated physical SQL")
    parser.add_argument(
        "--database",
        default=":memory:",
        help="DuckDB database file to query (default: in-memory, which reads CSV and Parquet "
        "sources directly)",
    )
    # Exit codes: 0 ok · 1 refused (the request is not answerable) · 2 bad model · 3 datasource
    args = parser.parse_args(argv)

    if not args.sql:
        parser.print_help()
        return 0

    verb = args.sql.strip().lower()
    if verb == "doctor":
        return _doctor(args.model, args.database)

    if verb in NOT_YET_IMPLEMENTED:
        print(
            f"semantiql {verb} is not implemented yet — {NOT_YET_IMPLEMENTED[verb]}.\n\n"
            "It is on the roadmap. What works today is querying an existing semantic model:\n\n"
            f'    semantiql "SELECT revenue, channel FROM orders" -m {EXAMPLE_MODEL}\n\n'
            "See the Quickstart in README.md.",
            file=sys.stderr,
        )
        return 2

    try:
        model = load_model(args.model)
    except ModelError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    adapter = DuckDBAdapter(args.database)
    try:
        outcome = run(args.sql, model, adapter)
    except AdapterError as exc:
        # The datasource could not be reached or rejected the SQL. Distinct from a refusal:
        # nothing is wrong with the request, something is wrong with the data or the setup.
        print(f"error: {exc}", file=sys.stderr)
        return 3
    finally:
        adapter.close()

    if isinstance(outcome, Refusal):
        # A refusal is the designed answer, not a crash — but it is not a success either,
        # so it exits non-zero and prints to stderr.
        print(f"refused: {outcome}", file=sys.stderr)
        return 1

    if args.show_sql:
        print(f"-- {outcome.sql}")
    print(_render(outcome))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
