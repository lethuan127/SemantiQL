"""The `semantiql` command line.

Deliberately thin: parse arguments, call `engine.run.run`, print. Every path to the data
goes through that one function, so the CLI cannot become a way around validation.
"""

from __future__ import annotations

import argparse
import sys

from semantiql.adapters.base import AdapterError
from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.engine.run import Result, run
from semantiql.engine.validate import Refusal
from semantiql.knowledge.loader import ModelError, load_model

EXAMPLE_MODEL = "examples/retail/semantic_model.yml"


def _render(result: Result) -> str:
    widths = [len(c) for c in result.columns]
    for row in result.rows:
        widths = [max(w, len(str(v))) for w, v in zip(widths, row, strict=True)]
    lines = ["  ".join(c.ljust(w) for c, w in zip(result.columns, widths, strict=True))]
    lines.append("  ".join("-" * w for w in widths))
    for row in result.rows:
        lines.append("  ".join(str(v).ljust(w) for v, w in zip(row, widths, strict=True)))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="semantiql",
        description="Query a database through a semantic model.",
    )
    parser.add_argument(
        "sql", nargs="?", help="semantic SQL, e.g. 'SELECT revenue, channel FROM orders'"
    )
    parser.add_argument(
        "-m",
        "--model",
        default=EXAMPLE_MODEL,
        help=f"path to the semantic model YAML (default: {EXAMPLE_MODEL})",
    )
    parser.add_argument("--show-sql", action="store_true", help="print the generated physical SQL")
    # Exit codes: 0 ok · 1 refused (the request is not answerable) · 2 bad model · 3 datasource
    args = parser.parse_args(argv)

    if not args.sql:
        parser.print_help()
        return 0

    try:
        model = load_model(args.model)
    except ModelError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    adapter = DuckDBAdapter()
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
