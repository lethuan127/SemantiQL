"""The CLI is the first thing a visitor touches, so its failure messages matter."""

from __future__ import annotations

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
