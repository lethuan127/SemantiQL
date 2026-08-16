"""The CLI is the first thing a visitor touches, so its failure messages matter."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from semantiql.cli import NOT_YET_IMPLEMENTED, main


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
