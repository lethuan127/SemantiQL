"""The plugin, and the one thing about it that can silently rot.

Most of this file is conformance: the manifest parses, the paths are portable, the skill has the
frontmatter a skill needs. Cheap checks that turn an install-time failure into a gate failure.

The test that earns its keep is `test_the_skill_names_exactly_the_grains_the_engine_accepts`. The
skill teaches Claude which grains exist and what is refused; `engine/validate.py` enforces it.
Those are two statements of one rule in two files, and prose drifts. Nothing else in this
repository would notice a skill that taught a sixth grain — the symptom would be Claude
confidently writing SQL the engine refuses, which reads like a model problem rather than a
documentation one.

**What this file cannot check:** that installing the plugin actually starts the server. That needs
a Claude client, so it is a manual step recorded in `specs/013-plugin-and-skill/validation.md`
rather than something the gate pretends to prove.

The marketplace tests below cover the gap that let the plugin sit uninstallable for four specs
(spec 017). `claude plugin validate` checks each manifest's *shape* and the gate runs it; what it
cannot check is whether `source: ./plugin` points at anything, so that is what these assert.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from semantiql.engine.validate import Refusal, validate
from semantiql.knowledge.model import SemanticModel
from tests._support import PLUGIN, REPO_ROOT  # noqa: E402

MANIFEST = PLUGIN / ".claude-plugin" / "plugin.json"
MCP_CONFIG = PLUGIN / ".mcp.json"
SKILL = PLUGIN / "skills" / "semantiql" / "SKILL.md"


def _json(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text())
    return loaded


def _frontmatter(path: Path) -> dict[str, str]:
    """The skill's YAML frontmatter, parsed without pulling in a YAML dependency here.

    Only flat `key: value` pairs, which is all a skill's frontmatter is allowed to contain.
    """
    text = path.read_text()
    assert text.startswith("---\n"), "SKILL.md must open with a frontmatter block"
    block = text.split("---\n", 2)[1]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


# --- Layout and manifest


def test_the_plugin_has_the_three_files_a_client_looks_for() -> None:
    """Auto-discovery is by location, so a file in the wrong place simply never loads."""
    assert MANIFEST.is_file(), "manifest must be at .claude-plugin/plugin.json"
    assert MCP_CONFIG.is_file(), ".mcp.json must be at the plugin root"
    assert SKILL.is_file(), "each skill needs skills/<name>/SKILL.md"


def test_component_directories_are_at_the_plugin_root() -> None:
    """`skills/` inside `.claude-plugin/` is a silent no-op, so its location is asserted."""
    assert (PLUGIN / "skills").is_dir()
    assert not (PLUGIN / ".claude-plugin" / "skills").exists()


def test_the_manifest_carries_the_fields_a_reader_needs() -> None:
    manifest = _json(MANIFEST)
    assert manifest["name"] == "semantiql"
    assert re.fullmatch(r"[a-z0-9-]+", manifest["name"]), "kebab-case only"
    for field in ("version", "description", "license", "repository"):
        assert manifest.get(field), f"manifest is missing {field}"


def test_the_server_definition_launches_semantiql_serve() -> None:
    servers = _json(MCP_CONFIG)["mcpServers"]
    assert list(servers) == ["semantiql"]
    args = servers["semantiql"]["args"]
    assert "serve" in args
    assert "semantiql" in args


def test_no_path_inside_the_plugin_comes_from_anyones_machine() -> None:
    """The whole reason the checkout is referenced through a variable.

    A hardcoded path works on the machine it was written on and nowhere else, and the failure is
    a server that never appears rather than an error anyone can read.

    It was briefly `${CLAUDE_PLUGIN_ROOT}/..`, which derived the checkout from the plugin's own
    location — correct only while the plugin is installed *from inside* the repository. Copy it
    anywhere else and it silently points at a directory with no SemantiQL in it. An explicit
    variable is worse to type and impossible to be quietly wrong about; the relocatable case is
    served by the bundle instead (spec 014).
    """
    servers = _json(MCP_CONFIG)["mcpServers"]
    assert any("${SEMANTIQL_HOME}" in a for a in servers["semantiql"]["args"]), (
        "the checkout must be located through ${SEMANTIQL_HOME}, not a literal path"
    )
    for path in PLUGIN.rglob("*"):
        if path.is_dir() or path.suffix not in {".json", ".md"}:
            continue
        for absolute in re.findall(r'"(/[A-Za-z0-9_./-]{4,})"', path.read_text()):
            pytest.fail(f"{path.name} contains an absolute path: {absolute}")


def test_the_plugin_ships_no_model_path_or_credential() -> None:
    """Which model to serve is per-user, so it must not be committed (FR-8)."""
    combined = MANIFEST.read_text() + MCP_CONFIG.read_text()
    assert "SEMANTIQL_MODEL" not in combined, (
        "the model path belongs in the user's environment, not in the plugin"
    )
    for secret in ("password", "PGPASSWORD", "postgresql://"):
        assert secret not in combined, f"{secret} must never appear in a committed plugin file"


# --- The skill


def test_the_skill_frontmatter_says_what_and_when() -> None:
    """A description that omits *when* is a skill Claude never triggers."""
    fields = _frontmatter(SKILL)
    assert fields["name"] == "semantiql"
    description = fields["description"]
    assert len(description) <= 1024
    assert "Use when" in description or "Use whenever" in description, (
        "the description must say when to trigger, not only what the skill does"
    )
    assert "describe_model" in description and "query" in description


# --- The drift test: the skill against the engine


def _grains_named_in_skill() -> set[str]:
    """The grain list the skill teaches, read out of the prose rather than restated here.

    Restating them would create a third copy to drift. This finds the sentence that lists them
    and parses it, so `SKILL.md` stays the single statement and this is only the comparison.
    """
    match = re.search(r"^Grains: (.+?)\. Nothing else\.$", SKILL.read_text(), re.M)
    assert match, "could not find the 'Grains: ...' sentence in SKILL.md — has it been reworded?"
    return set(re.findall(r"`(\w+)`", match.group(1)))


def test_the_skill_names_exactly_the_grains_the_engine_accepts(model: SemanticModel) -> None:
    """The check this file exists for.

    Teach Claude a grain the engine refuses and every query using it comes back refused, which
    reads as a broken model rather than a documentation bug. Teach one fewer and a capability
    quietly goes unused. Set equality catches both directions.
    """
    from semantiql.engine.validate import _GRAINS

    assert _grains_named_in_skill() == set(_GRAINS)


@pytest.mark.parametrize("grain", sorted(_grains_named_in_skill()))
def test_every_grain_the_skill_teaches_is_accepted(grain: str, model: SemanticModel) -> None:
    """Set equality is not quite enough — this proves each one actually validates."""
    outcome = validate(f"SELECT revenue, DATE_TRUNC('{grain}', order_date) FROM orders", model)
    assert not isinstance(outcome, Refusal), (
        f"skill teaches {grain!r} but it was refused: {outcome}"
    )


@pytest.mark.parametrize(
    ("construct", "sql"),
    [
        ("JOIN", "SELECT revenue FROM orders JOIN other ON 1=1"),
        ("HAVING", "SELECT revenue FROM orders HAVING revenue > 1"),
        ("DISTINCT", "SELECT DISTINCT revenue FROM orders"),
        ("subqueries", "SELECT revenue FROM (SELECT * FROM orders)"),
        ("TABLESAMPLE", "SELECT revenue FROM orders TABLESAMPLE (10 PERCENT)"),
        ("MONTH(", "SELECT revenue, MONTH(order_date) FROM orders"),
    ],
)
def test_everything_the_skill_calls_refused_really_is(
    construct: str, sql: str, model: SemanticModel
) -> None:
    """The other half of the drift check.

    The skill tells Claude not to bother with these. If one were quietly to start working, the
    skill would be steering Claude away from a supported feature — a smaller failure than the
    reverse, and still a documentation bug.
    """
    assert construct in SKILL.read_text(), f"{construct} is no longer mentioned in SKILL.md"
    assert isinstance(validate(sql, model), Refusal), f"{construct} was accepted"


def test_the_skill_tells_claude_to_stop_at_a_missing_definition(model: SemanticModel) -> None:
    """N6, in the file that would be the easiest place to break it.

    The helpful behaviour, when someone asks for a metric that does not exist, is to work it out
    from other columns. That is exactly how an unsanctioned number reaches a report looking
    authoritative. The skill has to say stop, and it has to say why — so this asserts both.
    """
    text = SKILL.read_text()
    assert "**Stop.**" in text
    assert "do not define it yourself" in text
    assert "reviewed change to" in text, (
        "the skill must say where a definition legitimately changes"
    )


# --- The discovery workflow (spec 016), and the limits N6 puts on it.


def test_the_skill_tells_claude_to_write_the_model_itself() -> None:
    """The correction that prompted spec 016.

    An earlier document described hand-writing the YAML as the flow. Claude has a shell and file
    tools, so the flow is that Claude inspects and writes — and the skill has to say so, or Claude
    will politely ask the user to do it instead.
    """
    text = SKILL.read_text()
    assert "semantiql inspect" in text
    assert "**you** write the YAML" in text
    assert "Do not ask the user to hand-write it" in text


def test_the_skill_puts_the_judgement_calls_to_the_human() -> None:
    """The split that makes discovery safe: mechanical work automated, judgement asked about.

    Which aggregation counts as revenue, what a row is, which columns are sensitive, and which
    timezone months belong to are not derivable from a schema at any level of cleverness.
    """
    text = SKILL.read_text()
    for question in (
        "Which aggregation is the sanctioned one?",
        "What is a row?",
        "Which columns are sensitive?",
        "which timezone do months belong to?",
    ):
        assert question in text, f"the skill must ask: {question}"
    assert "Do not guess at PII" in text


def test_the_skill_forbids_changing_a_model_to_answer_a_question() -> None:
    """N6, at the one place the new capability could break it.

    Discovery is a task the user asked for with them present — a reviewed change. Editing a model
    mid-question to make it answerable is automatic change to what a number means, which the
    constitution forbids outright. The skill now does both things, so the line has to be explicit.
    """
    text = SKILL.read_text()
    assert "Never change a model to answer a question" in text
    assert "Never invent a measure's aggregation" in text


def test_the_skill_tells_claude_to_run_doctor_until_it_passes() -> None:
    """Writing the files is half of it; the loop is what makes the result trustworthy."""
    text = SKILL.read_text()
    assert "semantiql doctor" in text
    assert "until it exits 0" in text


def test_the_skill_does_not_promise_a_tool_the_server_lacks() -> None:
    """Discovery uses a shell, not a third MCP tool. The surface stays two (FR-10).

    A skill telling Claude to call an `inspect` *tool* would fail silently in Claude Desktop, where
    there is no shell — so the skill must name the command, not a tool.
    """
    text = SKILL.read_text()
    assert "inspect" in text
    for invented in ("inspect_schema", "describe_datasource", "list_tables"):
        assert invented not in text, f"the skill names a tool that does not exist: {invented}"


# --- The marketplace (spec 017): the wrapper that makes the plugin reachable at all.

MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"


def _marketplace() -> dict[str, Any]:
    return json.loads(MARKETPLACE.read_text())  # type: ignore[no-any-return]


def test_a_marketplace_manifest_exists() -> None:
    """Without this file the plugin cannot be installed by any route.

    Claude Code installs from a *marketplace*, not from a plugin directory: `marketplace add`
    resolves `<source>/.claude-plugin/marketplace.json` and fails outright when it is absent. The
    plugin manifest was valid for four specs while the documented install could not be followed,
    because every check that existed looked *inside* `plugin/` and the missing piece was outside it.
    """
    assert MARKETPLACE.exists(), (
        "no marketplace manifest — `claude plugin marketplace add <checkout>` cannot succeed, "
        "so the install documented in docs/03-setup-workflow.md A1 is unfollowable"
    )


def test_the_marketplace_names_the_plugin() -> None:
    manifest = _marketplace()
    assert manifest["name"] == "semantiql"
    names = [entry["name"] for entry in manifest["plugins"]]
    assert names == ["semantiql"], (
        "one plugin, and `install semantiql@semantiql` depends on the name"
    )


def test_the_marketplace_source_resolves_to_the_plugin() -> None:
    """The check `claude plugin validate` cannot make.

    A schema validator confirms `source` is a string. It cannot confirm the string points at a real
    plugin — so renaming or moving `plugin/` would leave both manifests individually valid and the
    install broken. This is the dangling pointer, asserted.

    Note the base directory: `source` resolves against the **marketplace root** — the path handed to
    `claude plugin marketplace add` — not against the `.claude-plugin/` directory the manifest sits
    in. The first version of this test used the manifest's own parent, failed, and was wrong: the
    install had already succeeded, which is what settled which of the two was mistaken.
    """
    (entry,) = _marketplace()["plugins"]
    target = (REPO_ROOT / entry["source"]).resolve()
    assert target == PLUGIN.resolve(), f"source points at {target}, not at {PLUGIN}"

    inner = json.loads((target / ".claude-plugin" / "plugin.json").read_text())
    assert inner["name"] == entry["name"], (
        "the marketplace entry and the plugin manifest disagree about the plugin's name, so "
        "`install semantiql@semantiql` would resolve to something that calls itself otherwise"
    )


def test_the_two_descriptions_agree() -> None:
    """Duplicated on purpose, so pinned on purpose.

    Unlike the version — which lives only in `plugin.json` precisely so it cannot disagree — the
    description has to appear in the marketplace entry, because that is what someone browsing reads
    before installing. Forced duplication is worth a test; drift here means two accounts of what the
    plugin does, and the reader sees whichever one their route showed them.
    """
    (entry,) = _marketplace()["plugins"]
    inner = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    assert entry["description"] == inner["description"]


def test_the_marketplace_entry_carries_no_version() -> None:
    """One version, in one file.

    `plugin.json` has it. `claude plugin tag` exists specifically because a version in a plugin
    manifest and in its marketplace entry can disagree — so the second copy is simply not written,
    and there is nothing to keep in sync.
    """
    (entry,) = _marketplace()["plugins"]
    assert "version" not in entry


def test_the_marketplace_holds_no_absolute_path() -> None:
    """A committed absolute path is one developer's home directory in everyone else's checkout.

    The same hazard the installer creates in `.claude/settings.local.json`, which is why that file
    is git-ignored. Here the source is relative and must stay that way.
    """
    assert "/Users/" not in MARKETPLACE.read_text()
    (entry,) = _marketplace()["plugins"]
    assert entry["source"].startswith("./")
