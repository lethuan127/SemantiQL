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
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from semantiql.engine.validate import Refusal, validate
from semantiql.knowledge.model import SemanticModel

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"
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
