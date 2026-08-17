"""The `semantiql` command line.

Deliberately thin: parse arguments, call `engine.run.run`, print. Every path to the data
goes through that one function, so the CLI cannot become a way around validation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from semantiql import __version__
from semantiql.adapters.base import Adapter, AdapterError
from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.adapters.postgres import PostgresAdapter
from semantiql.doctor import Finding, check, problems
from semantiql.engine.run import Result, run
from semantiql.engine.validate import Refusal
from semantiql.knowledge.loader import ModelError, load_model
from semantiql.server import serve

EXAMPLE_MODEL = "examples/retail/semantic_model.yml"

DEFAULT_DUCKDB = ":memory:"

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


def _open_adapter(args: argparse.Namespace) -> Adapter:
    """The one place a concrete adapter is chosen.

    Both entry points below come through here, so a third datasource is one branch rather than
    a second construction site that can drift from the first. It opens a connection and nothing
    else — every path to the *data* still goes through `engine.run.run` (N1).

    The adapter is named explicitly rather than inferred from `model.datasource.dialect`, and
    that is deliberate: `run` refuses when the model's dialect and the adapter's disagree, and
    inferring one from the other would make that refusal unreachable. Under inference, "this
    model was written for DuckDB but I meant to query Postgres" silently opens DuckDB; here it
    is a loud refusal (spec 010, clarification Q3).
    """
    if args.datasource == "postgres":
        return PostgresAdapter(args.dsn or "")
    return DuckDBAdapter(args.database or DEFAULT_DUCKDB)


def _doctor(model_path: str, args: argparse.Namespace) -> int:
    """Report where the model and the database disagree. Never edits either."""
    try:
        model = load_model(model_path)
    except ModelError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        adapter = _open_adapter(args)
    except AdapterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    try:
        findings = check(model, adapter)
    finally:
        adapter.close()

    # Flushed before the summary below, which goes to stderr. Without this the two streams
    # buffer differently the moment stdout is a pipe — block-buffered stdout, unbuffered
    # stderr — and the summary line lands *above* the findings it summarises. Invisible in a
    # terminal, wrong in `semantiql doctor | tee setup.log`, which is exactly where a setup
    # script reads it.
    print(_render_findings(findings), flush=True)
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


def _connector_config(args: argparse.Namespace) -> dict[str, object]:
    """The `mcpServers` block for Claude Desktop, with every path already absolute.

    Absolute paths are not tidiness. The MCP client documentation names relative paths as a
    leading cause of a server that simply never appears, and Claude Desktop launches the
    process without the user's shell or PATH — so a bare `semantiql` or a relative model path
    resolves against something nobody chose. Both are the values this process already knows,
    so it fills them in rather than asking a human to.

    A password is deliberately absent. Postgres credentials travel through libpq's own
    environment and `~/.pgpass`, which is how they stay out of a JSON file that gets pasted
    into chat windows.
    """
    invocation = [sys.executable, "-m", "semantiql", "serve"]
    invocation += ["-m", str(Path(args.model).resolve())]
    invocation += ["--datasource", args.datasource]
    if args.datasource == "postgres":
        if args.dsn:
            invocation += ["--dsn", args.dsn]
    elif args.database:
        invocation += ["--database", str(Path(args.database).resolve())]

    return {
        "mcpServers": {
            "semantiql": {
                "command": invocation[0],
                "args": invocation[1:],
            }
        }
    }


def _serve(args: argparse.Namespace) -> int:
    """Run the MCP server. Fails at startup rather than answering every question with an error.

    Both failures a first-time user hits — an unloadable model and an unreachable datasource —
    happen here, before the server accepts anything, and exit with the same codes the query
    path uses. A server that starts successfully can answer.
    """
    try:
        model = load_model(args.model)
    except ModelError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        adapter = _open_adapter(args)
    except AdapterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    # `serve` closes the adapter itself, on the way out of the stdio loop.
    serve(model, adapter, version=__version__)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="semantiql",
        description="Query a database through a semantic model.",
    )
    parser.add_argument(
        "sql",
        nargs="?",
        help="semantic SQL, e.g. 'SELECT revenue, channel FROM orders' — or a verb: "
        "'doctor', 'serve'",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=EXAMPLE_MODEL,
        help=f"path to the semantic model YAML (default: {EXAMPLE_MODEL})",
    )
    parser.add_argument("--show-sql", action="store_true", help="print the generated physical SQL")
    parser.add_argument(
        "--datasource",
        choices=["duckdb", "postgres"],
        default="duckdb",
        help="which datasource to open (default: duckdb)",
    )
    parser.add_argument(
        "--database",
        default=None,
        help=f"DuckDB database file to query (default: {DEFAULT_DUCKDB}, which reads CSV and "
        "Parquet sources directly). DuckDB only",
    )
    parser.add_argument(
        "--dsn",
        default=None,
        help="Postgres connection string, e.g. postgresql://user@host/db. Postgres only; "
        "omit it to use libpq's environment (PGHOST, PGUSER, .pgpass), which keeps a password "
        "out of your shell history",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="with 'serve': print the Claude Desktop connector block instead of running, with "
        "every path resolved absolute",
    )
    # Exit codes: 0 ok · 1 refused (the request is not answerable) · 2 bad model · 3 datasource
    args = parser.parse_args(argv)

    # A flag meant for the other engine is an error rather than a silent no-op: quietly
    # ignoring `--dsn` would connect to DuckDB while the user believed they had reached
    # Postgres, and the answer would look fine.
    if args.datasource == "postgres" and args.database is not None:
        parser.error("--database is DuckDB-only; use --dsn with --datasource postgres")
    if args.datasource == "duckdb" and args.dsn is not None:
        parser.error("--dsn is Postgres-only; use --database with --datasource duckdb")

    if not args.sql:
        parser.print_help()
        return 0

    verb = args.sql.strip().lower()
    if verb == "doctor":
        return _doctor(args.model, args)

    if verb == "serve":
        if args.print_config:
            print(json.dumps(_connector_config(args), indent=2))
            return 0
        return _serve(args)

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

    try:
        adapter = _open_adapter(args)
    except AdapterError as exc:
        # Opening the datasource is a separate failure from querying it, and it is the one a
        # first-time user hits — so it gets the same exit code and its own message.
        print(f"error: {exc}", file=sys.stderr)
        return 3

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
