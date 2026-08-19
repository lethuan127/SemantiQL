"""The CLI is the first thing a visitor touches, so its failure messages matter."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from semantiql.cli import NOT_YET_IMPLEMENTED, main
from tests._support import REPO_ROOT


@pytest.mark.parametrize("verb", sorted(NOT_YET_IMPLEMENTED))
def test_promised_but_unbuilt_verbs_say_so(verb: str, capsys: pytest.CaptureFixture[str]) -> None:
    """`semantiql init` is advertised in the README; it must not be parsed as SQL.

    Before this, it reached the validator and came back with "Only SELECT is supported,
    and this is COLUMN" — the validation layer confusing a visitor about a command the
    project's own front page tells them to run.
    """
    code = main([verb])
    err = capsys.readouterr().err
    assert code == 2
    assert "not implemented yet" in err
    assert "SELECT" in err, "the message should show what does work"


def test_a_bare_word_is_not_explained_as_a_select_problem(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["hello"])
    err = capsys.readouterr().err
    assert code == 1
    assert "does not look like a query" in err


def test_no_argument_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "semantic SQL" in capsys.readouterr().out


def test_a_real_query_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["SELECT revenue, channel FROM orders", "-m", "examples/retail/semantic_model.yml"])
    out = capsys.readouterr().out
    assert code == 0
    assert "revenue" in out and "channel" in out


def test_a_missing_model_is_reported_not_raised(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["SELECT revenue FROM orders", "-m", "does/not/exist.yml"])
    assert code == 2
    assert "no semantic model" in capsys.readouterr().err


# --- `semantiql doctor` (spec 009). The exit code is the contract a setup script depends on.


def test_doctor_on_the_bundled_example_is_healthy(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["doctor", "-m", "examples/retail/semantic_model.yml"])
    out = capsys.readouterr().out
    assert code == 0
    assert "no problems found" in out
    assert "✓" in out


def test_doctor_reports_problems_and_exits_nonzero(
    tmp_path: pytest.TempPathFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    csv = Path("examples/retail/orders.csv").resolve()
    model = Path(str(tmp_path)) / "broken.yml"
    model.write_text(
        "version: 1\n"
        "datasource: {name: retail, dialect: duckdb}\n"
        "tables:\n"
        "  orders:\n"
        f"    source: {csv}\n"
        "    dimensions: {channel: {column: chanel, type: string}}\n"
        "    measures: {revenue: {column: amount, agg: sum}}\n"
    )
    code = main(["doctor", "-m", str(model)])
    captured = capsys.readouterr()
    assert code == 1
    assert "chanel" in captured.out
    assert "channel" in captured.out, "the suggestion should be offered"
    assert "1 problem" in captured.err


def test_doctor_reports_an_unloadable_model(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["doctor", "-m", "does/not/exist.yml"])
    assert code == 2
    assert "no semantic model" in capsys.readouterr().err


def test_doctor_is_no_longer_advertised_as_unbuilt() -> None:
    from semantiql.cli import NOT_YET_IMPLEMENTED

    assert "doctor" not in NOT_YET_IMPLEMENTED
    assert "init" in NOT_YET_IMPLEMENTED, "init is still a promise, and should still say so"


def test_a_query_can_target_a_database_file(tmp_path: pytest.TempPathFactory) -> None:
    """`--database` exists so doctor can check a model over real tables (FR-8)."""
    path = Path(str(tmp_path)) / "w.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("CREATE TABLE t (a INTEGER, b VARCHAR)")
    connection.execute("INSERT INTO t VALUES (2, 'x'), (3, 'y')")
    connection.close()

    model = Path(str(tmp_path)) / "m.yml"
    model.write_text(
        "version: 1\n"
        "datasource: {name: w, dialect: duckdb}\n"
        "tables:\n"
        "  t:\n"
        "    source: t\n"
        "    dimensions: {b: {column: b, type: string}}\n"
        "    measures: {total: {column: a, agg: sum}}\n"
    )
    assert main(["doctor", "-m", str(model), "--database", str(path)]) == 0
    assert main(["SELECT total FROM t", "-m", str(model), "--database", str(path)]) == 0


# --- Adapter selection (spec 010). The DuckDB path above must keep working untouched; these
# cover the flags that arrived with the second datasource.


def test_the_default_datasource_is_still_duckdb(capsys: pytest.CaptureFixture[str]) -> None:
    """Every documented example omits --datasource, so the default must not move."""
    assert main(["SELECT revenue, channel FROM orders"]) == 0
    assert "956.5" in capsys.readouterr().out


def test_a_postgres_flag_on_a_duckdb_run_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Silently ignoring --dsn would connect to DuckDB while the user believed otherwise.

    The answer would look perfectly fine, which is the failure mode N2 exists to refuse — so
    argparse rejects the combination instead.
    """
    with pytest.raises(SystemExit):
        main(["SELECT revenue FROM orders", "--dsn", "postgresql://localhost/db"])
    assert "Postgres-only" in capsys.readouterr().err


def test_a_duckdb_flag_on_a_postgres_run_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["SELECT revenue FROM orders", "--datasource", "postgres", "--database", "x.duckdb"])
    assert "DuckDB-only" in capsys.readouterr().err


def test_an_unreachable_postgres_exits_three_with_a_fix_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exit 3 is "the datasource is the problem", distinct from 1, "the request is".

    A first-time user hits this before anything else, so the message names what to check
    rather than only what failed.
    """
    code = main(
        [
            "SELECT revenue FROM orders",
            "-m",
            "examples/retail/semantic_model.postgres.yml",
            "--datasource",
            "postgres",
            "--dsn",
            "postgresql://postgres@127.0.0.1:59999/nope",
        ]
    )
    err = capsys.readouterr().err
    assert code == 3
    assert "could not connect to Postgres" in err
    assert "check the server is running" in err


# --- Where the model path comes from (spec 013). The plugin cannot ship a per-user path, so the
# environment is the smallest thing a user has to set.


def test_an_explicit_model_flag_wins(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEMANTIQL_MODEL", "/nonexistent/should-be-ignored.yml")
    assert main(["SELECT revenue FROM orders", "-m", "examples/retail/semantic_model.yml"]) == 0
    assert "1686.24" in capsys.readouterr().out


def test_the_environment_supplies_the_model_when_no_flag_is_given(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """How the plugin points the server at a model without committing a path."""
    monkeypatch.setenv("SEMANTIQL_MODEL", "examples/retail/semantic_model.yml")
    assert main(["SELECT revenue FROM orders"]) == 0
    assert "1686.24" in capsys.readouterr().out


def test_the_bundled_example_is_the_last_resort(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The README quickstart takes no arguments, so this default must not move."""
    monkeypatch.delenv("SEMANTIQL_MODEL", raising=False)
    assert main(["SELECT revenue FROM orders"]) == 0
    assert "1686.24" in capsys.readouterr().out


# --- Exit codes and output paths that had no test.
#
# The exit codes are a contract: a setup script distinguishes "the question was not answerable"
# from "your database is unreachable" by the number alone, and `doctor` gating a script depends on
# it. Untested, that contract is a comment.


def test_show_sql_prints_the_sql_that_ran(capsys: pytest.CaptureFixture[str]) -> None:
    """`--show-sql` is how a reviewer checks the work, so it has to actually print it."""
    assert main(["SELECT revenue, channel FROM orders", "--show-sql"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("--"), "the SQL is emitted as a comment line, before the table"
    assert "SUM(amount)" in out
    assert "GROUP BY" in out


def test_the_rendered_table_aligns_its_columns(capsys: pytest.CaptureFixture[str]) -> None:
    """A misaligned table is unreadable, and nothing else would notice."""
    assert main(["SELECT revenue, channel FROM orders"]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    header, rule, *rows = lines
    assert set(rule) <= {"-", " "}, "the second line is the rule under the header"
    assert len(rule) == len(header.rstrip()) or len(rule) >= len(header) - 2
    for row in rows:
        assert len(row.rstrip()) <= len(rule) + 2, f"row wider than the rule: {row!r}"


def test_an_unreachable_datasource_exits_three_from_a_query(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exit 3 means the datasource; 1 would mean the question. A script must be able to tell."""
    code = main(
        [
            "SELECT revenue FROM orders",
            "-m",
            "examples/retail/semantic_model.postgres.yml",
            "--datasource",
            "postgres",
            "--dsn",
            "postgresql://postgres@127.0.0.1:59999/nope",
        ]
    )
    assert code == 3
    assert "could not connect" in capsys.readouterr().err


def test_an_unreachable_datasource_exits_three_from_doctor(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "doctor",
            "-m",
            "examples/retail/semantic_model.postgres.yml",
            "--datasource",
            "postgres",
            "--dsn",
            "postgresql://postgres@127.0.0.1:59999/nope",
        ]
    )
    assert code == 3


def test_serve_exits_two_on_a_model_that_will_not_load(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Startup is where this belongs (spec 012, FR-8).

    A server that starts and refuses every question looks healthy to the client and broken to the
    user. Failing before the loop means a server that started can answer.
    """
    code = main(["serve", "-m", "/nonexistent/model.yml"])
    assert code == 2
    assert "error:" in capsys.readouterr().err


def test_serve_exits_three_on_an_unreachable_datasource(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "serve",
            "-m",
            "examples/retail/semantic_model.postgres.yml",
            "--datasource",
            "postgres",
            "--dsn",
            "postgresql://postgres@127.0.0.1:59999/nope",
        ]
    )
    assert code == 3


def test_print_config_carries_a_postgres_dsn(capsys: pytest.CaptureFixture[str]) -> None:
    """The Postgres branch of the connector block, which the DuckDB test does not reach."""
    code = main(
        [
            "serve",
            "-m",
            "examples/retail/semantic_model.postgres.yml",
            "--datasource",
            "postgres",
            "--dsn",
            "postgresql://ro@db/wh",
            "--print-config",
        ]
    )
    assert code == 0
    block = json.loads(capsys.readouterr().out)
    args = block["mcpServers"]["semantiql"]["args"]
    assert "--dsn" in args and "postgresql://ro@db/wh" in args
    assert "--datasource" in args and "postgres" in args


def test_print_config_resolves_a_duckdb_database_path(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Every path in the block is absolute, because a relative one is why a server never appears."""
    database = tmp_path / "w.duckdb"
    database.write_text("")
    assert main(["serve", "--database", str(database), "--print-config"]) == 0
    args = json.loads(capsys.readouterr().out)["mcpServers"]["semantiql"]["args"]
    assert str(database.resolve()) in args
    assert not any(a.startswith("./") or a == ".." for a in args)


def test_a_bad_datasource_in_the_environment_is_an_argument_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A variable is as capable of a typo as a flag, and argparse never sees it."""
    monkeypatch.setenv("SEMANTIQL_DATASOURCE", "postgrez")
    with pytest.raises(SystemExit):
        main(["SELECT revenue FROM orders"])


def test_the_package_runs_as_a_module() -> None:
    """`python -m semantiql` is what the Desktop bundle's connector block names.

    If `__main__.py` breaks, the bundle stops starting and nothing else in the suite notices.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "semantiql", "SELECT revenue FROM orders"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    assert "1686.24" in result.stdout


# --- `inspect` (spec 016): the verb that runs before a model exists.


@pytest.fixture
def warehouse_db(tmp_path: Path) -> Path:
    import duckdb

    database = tmp_path / "w.duckdb"
    setup = duckdb.connect(str(database))
    setup.execute(
        "CREATE TABLE orders (id BIGINT, placed_at TIMESTAMPTZ, channel VARCHAR,"
        "                     amount DECIMAL(10,2));"
        "INSERT INTO orders VALUES "
        "  (1, '2026-07-01 10:00:00+00', 'web',   20.00),"
        "  (2, '2026-07-02 10:00:00+00', 'store',  5.50);"
        "CREATE VIEW order_v AS SELECT * FROM orders;"
        "CREATE SCHEMA staging; CREATE TABLE staging.raw (blob VARCHAR)"
    )
    setup.close()
    return database


def test_inspect_needs_no_model(capsys: pytest.CaptureFixture[str], warehouse_db: Path) -> None:
    """The point of the verb, asserted.

    Everything else in this CLI takes a model and checks a claim about it. This takes a database and
    makes none — which is what lets it run before a model exists, which is when it is needed.
    `-m` is never passed here, and the bundled default must not be loaded either.
    """
    assert main(["inspect", "--database", str(warehouse_db)]) == 0
    out = capsys.readouterr().out
    assert "orders" in out
    assert "3 relations" in out


def test_inspect_lists_relations_then_columns_on_request(
    capsys: pytest.CaptureFixture[str], warehouse_db: Path
) -> None:
    """Two steps (FR-7). A five-hundred-table warehouse must not arrive in one reply."""
    assert main(["inspect", "--database", str(warehouse_db)]) == 0
    listing = capsys.readouterr().out
    assert "placed_at" not in listing, "the listing must not include columns"

    assert main(["inspect", "--database", str(warehouse_db), "--table", "orders"]) == 0
    detail = capsys.readouterr().out
    assert "placed_at" in detail


def test_inspect_json_gives_claude_what_it_needs_to_write_a_model(
    capsys: pytest.CaptureFixture[str], warehouse_db: Path
) -> None:
    """Each column carries the model's own type *and* the timezone flag.

    The native type tells a DBA what the database holds; `semantiql_type` is what goes in the YAML,
    and `carries_timezone` is what decides whether `timezone:` is needed. Writing a model from the
    native type alone would mean re-deriving a mapping the adapter already did.
    """
    assert main(["inspect", "--database", str(warehouse_db), "--table", "orders", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["source"] == "orders"
    by_name = {c["name"]: c for c in payload["columns"]}
    assert by_name["placed_at"]["semantiql_type"] == "date"
    assert by_name["placed_at"]["carries_timezone"] is True
    assert by_name["amount"]["semantiql_type"] == "number"
    assert by_name["channel"]["carries_timezone"] is False


def test_inspect_json_lists_relations_and_the_dialect(
    capsys: pytest.CaptureFixture[str], warehouse_db: Path
) -> None:
    assert main(["inspect", "--database", str(warehouse_db), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dialect"] == "duckdb"
    assert "staging.raw" in payload["relations"], "a non-default schema stays qualified"


def test_inspect_explains_an_empty_catalogue_rather_than_printing_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """In-memory DuckDB over files has no catalogue objects — correct, and it looks like a bug.

    Printing nothing would leave the reader concluding the command is broken. This is the one place
    a wall of explanation beats silence.
    """
    assert main(["inspect"]) == 0
    out = capsys.readouterr().out
    assert "No relations found" in out
    assert "not a catalogue object" in out


def test_inspect_on_an_unreachable_datasource_exits_three(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "inspect",
                "--datasource",
                "postgres",
                "--dsn",
                "postgresql://postgres@127.0.0.1:59999/nope",
            ]
        )
        == 3
    )


def test_inspect_on_a_relation_that_does_not_exist_exits_three(
    capsys: pytest.CaptureFixture[str], warehouse_db: Path
) -> None:
    """A typo'd relation name is a datasource error, not a silent empty result."""
    code = main(["inspect", "--database", str(warehouse_db), "--table", "nope"])
    assert code == 3
    assert "could not read" in capsys.readouterr().err


# --- `profile` (spec 020): the verb that replaced improvised psql.


def test_profile_needs_no_model(capsys: pytest.CaptureFixture[str], warehouse_db: Path) -> None:
    """Like `inspect`, and for the same reason: it runs before a model exists."""
    assert main(["profile", "--database", str(warehouse_db), "--table", "orders"]) == 0
    out = capsys.readouterr().out
    assert "orders:" in out
    assert "rows" in out


def test_profile_requires_a_table(capsys: pytest.CaptureFixture[str]) -> None:
    """Reading every row should take a deliberate argument, not happen because a flag was omitted.

    `inspect` defaults to listing everything because metadata is cheap. This does not, because on a
    five-hundred-table warehouse the default would be five hundred full scans.
    """
    assert main(["profile"]) == 2
    assert "--table" in capsys.readouterr().err


def test_profile_reports_the_sum_that_prices_a_definition(
    capsys: pytest.CaptureFixture[str], warehouse_db: Path
) -> None:
    """The figure the observed run used raw `psql` to get.

    `amount` holds 20.00 and 5.50 in this fixture, so the sum is what a model author would quote
    when
    asking which column counts as revenue.
    """
    assert main(["profile", "--database", str(warehouse_db), "--table", "orders", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    by_name = {c["name"]: c for c in payload["columns"]}
    assert payload["rows"] == 2
    assert float(by_name["amount"]["total"]) == pytest.approx(25.5)
    assert by_name["amount"]["nulls"] == 0


def test_profile_json_carries_the_distribution_of_a_coded_column(
    capsys: pytest.CaptureFixture[str], warehouse_db: Path
) -> None:
    """What makes a coded integer legible, and the reason the verb exists at all."""
    assert main(["profile", "--database", str(warehouse_db), "--table", "orders", "--json"]) == 0
    by_name = {c["name"]: c for c in json.loads(capsys.readouterr().out)["columns"]}
    assert by_name["channel"]["values"] is not None
    assert {value for value, _ in by_name["channel"]["values"]} == {"web", "store"}


def test_profile_on_an_unreachable_datasource_exits_three(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "profile",
            "--datasource",
            "postgres",
            "--dsn",
            "postgresql://postgres@127.0.0.1:59999/nope",
            "--table",
            "orders",
        ]
    )
    assert code == 3


# --- The two datasources added by spec 023, at the CLI seam.


@pytest.mark.parametrize("datasource", ["databricks", "sheets"])
def test_the_new_datasources_are_accepted_choices(
    capsys: pytest.CaptureFixture[str], datasource: str
) -> None:
    """Rejected by argparse would be indistinguishable from an adapter that failed to connect.

    Exit 3 is the adapter's own failure — a missing driver or credential — which is what should
    happen here, since neither optional extra is installed by default.
    """
    assert main(["inspect", "--datasource", datasource]) == 3
    error = capsys.readouterr().err
    assert "not a datasource" not in error, (
        f"{datasource} was rejected before an adapter was opened"
    )


def test_an_unknown_datasource_is_still_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """Widening the choices must not turn the list into anything-goes."""
    with pytest.raises(SystemExit):
        main(["inspect", "--datasource", "mongodb"])


@pytest.mark.parametrize(
    ("datasource", "expected"),
    [
        ("databricks", "extra databricks"),
        ("sheets", "extra sheets"),
    ],
)
def test_a_missing_optional_driver_names_the_extra(
    capsys: pytest.CaptureFixture[str], datasource: str, expected: str
) -> None:
    """The message a fresh clone gets, and it must be an instruction.

    Both drivers are optional so `uv sync` stays light. The cost of that choice is paid here, in
    the one place a user meets it, and it is paid with a command they can run.
    """
    assert main(["inspect", "--datasource", datasource]) == 3
    assert expected in capsys.readouterr().err
