"""The `semantiql` command line.

Deliberately thin: parse arguments, call `engine.run.run`, print. Every path to the data
goes through that one function, so the CLI cannot become a way around validation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from semantiql import __version__
from semantiql.adapters.base import Adapter, AdapterError, RelationProfile
from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.adapters.postgres import PostgresAdapter
from semantiql.doctor import Finding, check, problems
from semantiql.engine.run import Result, run
from semantiql.engine.validate import Refusal
from semantiql.knowledge.loader import ModelError, load_model
from semantiql.server import serve

EXAMPLE_MODEL = "examples/retail/semantic_model.yml"

#: Where `-m` looks before falling back to the bundled example. It exists for the plugin: which
#: model to serve is inherently per-user, so it cannot be committed into a file the plugin ships,
#: and a client that launches the server does not offer a place to type a flag. One environment
#: variable is the smallest thing the user has to set (spec 013).
MODEL_ENV = "SEMANTIQL_MODEL"

#: The rest of the connection, for the same reason. A Desktop bundle collects these in an install
#: dialog and hands them over as environment variables, so every option that has a flag also has a
#: variable (spec 014). Reading them here rather than in the bundle's entry point keeps the
#: branching in code the ordinary suite covers — the entry point is three lines with nothing to
#: get wrong.
DATASOURCE_ENV = "SEMANTIQL_DATASOURCE"
DSN_ENV = "SEMANTIQL_DSN"
DATABASE_ENV = "SEMANTIQL_DATABASE"

#: Databricks and Google Sheets (spec 023). Each datasource reads its own variables, and the
#: Databricks ones keep the driver's own names, so anyone who has already configured a Databricks
#: CLI has them set.
DBX_HOST_ENV = "DATABRICKS_SERVER_HOSTNAME"
DBX_HTTP_PATH_ENV = "DATABRICKS_HTTP_PATH"
DBX_TOKEN_ENV = "DATABRICKS_TOKEN"
DBX_CATALOG_ENV = "DATABRICKS_CATALOG"
DBX_SCHEMA_ENV = "DATABRICKS_SCHEMA"
SHEET_ID_ENV = "SEMANTIQL_SHEET_ID"
SHEET_CREDENTIALS_ENV = "SEMANTIQL_SHEET_CREDENTIALS"

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
    if args.datasource == "databricks":
        from semantiql.adapters.databricks import DatabricksAdapter

        return DatabricksAdapter(
            server_hostname=args.dbx_host or os.environ.get(DBX_HOST_ENV, ""),
            http_path=args.dbx_http_path or os.environ.get(DBX_HTTP_PATH_ENV, ""),
            access_token=args.dbx_token or os.environ.get(DBX_TOKEN_ENV, ""),
            catalog=args.dbx_catalog or os.environ.get(DBX_CATALOG_ENV, ""),
            schema=args.dbx_schema or os.environ.get(DBX_SCHEMA_ENV, ""),
        )
    if args.datasource == "sheets":
        from semantiql.adapters.sheets import SheetsAdapter

        return SheetsAdapter(
            spreadsheet_id=args.sheet_id or os.environ.get(SHEET_ID_ENV, ""),
            credentials_file=args.sheet_credentials or os.environ.get(SHEET_CREDENTIALS_ENV, ""),
        )
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


def _datasource_given(argv: list[str] | None) -> bool:
    """Was `--datasource` passed explicitly?

    `argparse` cannot tell a default from a flag that happened to match it, and the environment
    must not silently override something the user typed. Inspecting the argument list is blunt and
    it is the only thing that distinguishes the two.
    """
    if argv is None:
        argv = sys.argv[1:]
    return any(a == "--datasource" or a.startswith("--datasource=") for a in argv)


def _inspect(args: argparse.Namespace) -> int:
    """Report what is in the datasource. The one command that needs no semantic model.

    That is the point rather than an accident: this is what runs *before* a model exists, so that
    Claude — or a person — can see the real tables and columns and write one. Everything else in
    this CLI takes a model and checks a claim about it; this takes a database and makes no claims.

    Two steps by design (spec 016, FR-7). Naming no table lists the relations; naming one reports
    its columns. A five-hundred-table warehouse must not arrive in a single reply, and the columns
    of five hundred tables certainly must not.

    It reads the catalogue and never a row, so it is further from the data than any other verb —
    and on Postgres it sees exactly what the connected role is permitted to see, which means a
    read-only account with narrow grants produces a correspondingly narrow list.
    """
    try:
        adapter = _open_adapter(args)
    except AdapterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    try:
        if args.table:
            payload: dict[str, object] = {
                "source": args.table,
                "columns": [
                    {
                        "name": column.name,
                        "native_type": column.native_type,
                        # What to write in the model, as opposed to what the database calls it.
                        "semantiql_type": column.kind,
                        "carries_timezone": column.carries_timezone,
                    }
                    for column in adapter.columns(args.table)
                ],
            }
        else:
            payload = {"dialect": adapter.dialect, "relations": adapter.tables()}
    except AdapterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    finally:
        adapter.close()

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    print(_render_inspection(payload))
    return 0


def _profile(args: argparse.Namespace) -> int:
    """Report what is *in* a relation. Needs no model, and reads rows — which `inspect` does not.

    The two verbs are separate on purpose. `inspect` answers "what columns exist", which is
    metadata;
    this answers "what is in them", which reads every row. Those are different claims to make on
    someone's database and folding them together would hide the bigger one behind the smaller.

    It exists because the alternative was observed and is worse. A discovery run over 2.96M real
    taxi
    trips used `inspect` correctly for metadata and then **raw `psql`** for every figure it showed
    the
    analyst — twelve calls, including a join and a `CREATE OR REPLACE VIEW`. Those figures decided
    what "revenue" would mean in the model. They were right, but nothing made them right, and a
    plausible wrong number arriving at that moment is the failure this project exists to prevent
    (spec 020).

    `--table` is required rather than defaulting to everything: reading rows should take a
    deliberate
    argument, not happen because a flag was omitted.
    """
    if not args.table:
        print(
            "error: profile needs --table <relation>. It reads every row, so it does not "
            "default to the whole datasource — run `semantiql inspect` first to see what exists.",
            file=sys.stderr,
        )
        return 2

    try:
        adapter = _open_adapter(args)
    except AdapterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    try:
        profile = adapter.profile(args.table)
    except AdapterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    finally:
        adapter.close()

    payload: dict[str, object] = {
        "source": profile.source,
        "rows": profile.rows,
        "columns": [
            {
                "name": column.name,
                "nulls": column.nulls,
                "distinct": column.distinct,
                "minimum": None if column.minimum is None else str(column.minimum),
                "maximum": None if column.maximum is None else str(column.maximum),
                "total": None if column.total is None else str(column.total),
                "values": None
                if column.values is None
                else [[None if v is None else str(v), n] for v, n in column.values],
            }
            for column in profile.columns
        ],
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    print(_render_profile(profile))
    return 0


def _render_profile(profile: RelationProfile) -> str:
    """The human form. One line per column, and the value distribution indented under it.

    Numbers are rendered as text exactly as the database returned them — no reformatting, because a
    figure that is about to become a business definition should be the database's answer rather than
    this file's opinion of it.
    """
    lines = [f"{profile.source}:  {profile.rows:,} rows", ""]
    width = max((len(c.name) for c in profile.columns), default=0)
    for column in profile.columns:
        facts = [f"nulls {column.nulls:,}", f"distinct {column.distinct:,}"]
        if column.total is not None:
            facts.append(f"sum {column.total}")
        if column.minimum is not None:
            facts.append(f"min {column.minimum}")
        if column.maximum is not None:
            facts.append(f"max {column.maximum}")
        lines.append(f"  {column.name:<{width}}  {'  '.join(facts)}")
        if column.values:
            shown = "  ".join(f"{value}({count:,})" for value, count in column.values[:8])
            more = " …" if len(column.values) > 8 else ""
            lines.append(f"  {'':<{width}}  values: {shown}{more}")
    if not profile.columns:
        lines.append("  no columns")
    return "\n".join(lines)


def _render_inspection(payload: dict[str, object]) -> str:
    """The human form. Claude passes `--json`; an analyst reading a terminal gets a table."""
    if "relations" in payload:
        relations = payload["relations"]
        assert isinstance(relations, list)
        if not relations:
            # An empty catalogue almost always means a DuckDB model over CSV or Parquet files,
            # which are reads rather than catalogue objects. Saying so beats printing nothing and
            # letting the reader conclude the command is broken.
            return (
                "No relations found.\n\n"
                "If this is DuckDB reading CSV or Parquet files directly, that is expected — a "
                "file read is not a catalogue object, so there is nothing to list. Point "
                "`--database` at a DuckDB file, or set a model `source:` to the file path.",
            )[0]
        lines = [f"{len(relations)} relation{'' if len(relations) == 1 else 's'}:"]
        lines += [f"  {name}" for name in relations]
        lines.append("")
        lines.append("Next: semantiql inspect --table <name>   (add --json for machine output)")
        return "\n".join(lines)

    columns = payload["columns"]
    assert isinstance(columns, list)
    if not columns:
        return f"{payload['source']} has no columns."
    width = max(len(str(c["name"])) for c in columns)
    native = max(len(str(c["native_type"])) for c in columns)
    lines = [f"{payload['source']}:"]
    for column in columns:
        assert isinstance(column, dict)
        zone = "  carries a timezone" if column["carries_timezone"] else ""
        lines.append(
            f"  {str(column['name']).ljust(width)}  "
            f"{str(column['native_type']).ljust(native)}  "
            f"-> type: {column['semantiql_type']}{zone}"
        )
    return "\n".join(lines)


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
        "'inspect', 'doctor', 'serve'",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=None,
        help=f"path to the semantic model YAML (default: ${MODEL_ENV} if set, "
        f"otherwise {EXAMPLE_MODEL})",
    )
    parser.add_argument("--show-sql", action="store_true", help="print the generated physical SQL")
    parser.add_argument(
        "--datasource",
        choices=["duckdb", "postgres", "databricks", "sheets"],
        default="duckdb",
        help="which datasource to open (default: duckdb). databricks and sheets each need their "
        "optional extra installed: `uv sync --extra databricks` or `--extra sheets`",
    )
    parser.add_argument(
        "--dbx-host",
        default=None,
        help=f"Databricks workspace hostname (default: ${DBX_HOST_ENV}). Databricks only",
    )
    parser.add_argument(
        "--dbx-http-path",
        default=None,
        help=f"Databricks SQL warehouse HTTP path (default: ${DBX_HTTP_PATH_ENV}). Databricks only",
    )
    parser.add_argument(
        "--dbx-token",
        default=None,
        help=f"Databricks access token (default: ${DBX_TOKEN_ENV}). Prefer the environment "
        "variable: a token on a command line reaches shell history and every process listing",
    )
    parser.add_argument(
        "--dbx-catalog",
        default=None,
        help=f"Unity Catalog catalog (default: ${DBX_CATALOG_ENV}). Databricks only",
    )
    parser.add_argument(
        "--dbx-schema",
        default=None,
        help=f"Databricks schema (default: ${DBX_SCHEMA_ENV}, else 'default'). Databricks only",
    )
    parser.add_argument(
        "--sheet-id",
        default=None,
        help=f"Google spreadsheet id (default: ${SHEET_ID_ENV}). Sheets only",
    )
    parser.add_argument(
        "--sheet-credentials",
        default=None,
        help=f"path to a service-account JSON file (default: ${SHEET_CREDENTIALS_ENV}). The "
        "read-only spreadsheets scope is enough. Sheets only",
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
        "--table",
        default=None,
        help="with 'inspect': report this relation's columns instead of listing relations",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="with 'inspect': emit JSON instead of a table, for a program to read",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="with 'serve': print the Claude Desktop connector block instead of running, with "
        "every path resolved absolute",
    )
    # Exit codes: 0 ok · 1 refused (the request is not answerable) · 2 bad model · 3 datasource
    args = parser.parse_args(argv)

    # An explicit flag always wins; then the environment; then the bundled example, so the
    # README quickstart keeps working with no arguments at all. Empty strings count as unset:
    # a host substituting an optional field the user left blank yields "", not absence.
    if args.model is None:
        args.model = os.environ.get(MODEL_ENV) or EXAMPLE_MODEL
    if args.dsn is None:
        args.dsn = os.environ.get(DSN_ENV) or None
    if args.database is None:
        args.database = os.environ.get(DATABASE_ENV) or None
    if not _datasource_given(argv):
        args.datasource = os.environ.get(DATASOURCE_ENV) or args.datasource
        if args.datasource not in ("duckdb", "postgres"):
            parser.error(
                f"{DATASOURCE_ENV}={args.datasource!r} is not a datasource; "
                "use 'duckdb' or 'postgres'"
            )

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

    if verb == "inspect":
        return _inspect(args)

    if verb == "profile":
        return _profile(args)

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
