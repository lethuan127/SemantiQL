#!/usr/bin/env python3
"""Validate an OKF 0.2 bundle.

Usage: python3 validate_bundle.py <bundle-root>

Errors are the spec's conformance rules only: parseable frontmatter, a non-empty
`type`, reserved-file structure, and `runtime` on an Attested Computation. Everything
else — missing recommended fields, broken links, staleness, index coverage — is a
warning, because the spec leaves it to the producer.

Exit codes: 0 = conformant (warnings allowed), 1 = conformance errors, 2 = bad usage.

Uses pyyaml when importable. Without it, runs in degraded mode: structural,
link, log and footnote checks still run; field-syntax checks are skipped and
trust tiers are approximated from the frontmatter text.
"""

import re
import sys
from datetime import date
from pathlib import Path

try:
    import yaml

    HAVE_YAML = True
except ImportError:  # degraded mode — see module docstring
    HAVE_YAML = False

RESERVED = {"index.md", "log.md"}
STATUSES = {"draft", "stable", "deprecated"}

FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.S)
ACTOR = re.compile(r"\A(human:[\w.@-]+|process:[\w.-]+|[\w.-]+/[\w.+-]+)\Z")
ISO_DATE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
LINK = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+)")
FOOTNOTE_REF = re.compile(r"(?<!\])\[\^([^\]]+)\](?!:)")
FOOTNOTE_DEF = re.compile(r"^\[\^([^\]]+)\]:", re.M)
LOG_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.M)
TOP_LEVEL_KEY = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")

errors: list[str] = []
warnings: list[str] = []
tiers = {"human-reviewed": 0, "machine-confirmed": 0, "unverified": 0}
statuses: dict[str, int] = {}
past_stale = 0
no_stale = 0


def err(path: Path, msg: str) -> None:
    errors.append(f"{path}: {msg}")


def warn(path: Path, msg: str) -> None:
    warnings.append(f"{path}: {msg}")


def split_frontmatter(text: str):
    """Return (frontmatter_text, body) or (None, text) when there is no block."""
    if not text.startswith("---"):
        return None, text
    match = FRONTMATTER.match(text)
    if not match:
        return "", text  # opened but never closed
    return match.group(1), match.group(2)


def parse_frontmatter(fm_text: str):
    """Parse with pyyaml, or fall back to top-level scalars only."""
    if HAVE_YAML:
        return yaml.safe_load(fm_text)
    data = {}
    for line in fm_text.splitlines():
        match = TOP_LEVEL_KEY.match(line)
        if match:
            data[match.group(1)] = match.group(2).strip() or None
    return data


def as_list(value):
    """The spec requires readers to accept a bare mapping where a list is expected."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def parse_date(value):
    text = str(value)
    if not ISO_DATE.match(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def check_links(path: Path, root: Path, body: str) -> None:
    for target in LINK.findall(body):
        target = target.split("#", 1)[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#", "<")):
            continue
        resolved = (root / target.lstrip("/")) if target.startswith("/") else (path.parent / target)
        if not resolved.exists():
            warn(path, f"broken link: {target}")


def check_footnotes(path: Path, body: str, source_ids: set[str]) -> None:
    refs = set(FOOTNOTE_REF.findall(body))
    defs = set(FOOTNOTE_DEF.findall(body))
    for label in sorted(refs - defs):
        warn(path, f"footnote [^{label}] has no definition")
    for source_id in sorted(source_ids - refs):
        warn(path, f"source '{source_id}' is never cited by a footnote")


def check_concept(path: Path, root: Path, text: str) -> None:
    global past_stale, no_stale

    fm_text, body = split_frontmatter(text)
    if fm_text is None:
        err(path, "no YAML frontmatter block")
        return
    if fm_text == "":
        err(path, "frontmatter block is opened but never closed")
        return

    try:
        data = parse_frontmatter(fm_text)
    except Exception as exc:  # yaml.YAMLError and anything it wraps
        err(path, "unparseable frontmatter: " + " ".join(str(exc).split())[:180])
        return
    if not isinstance(data, dict):
        err(path, "frontmatter is not a mapping")
        return

    concept_type = data.get("type")
    if not concept_type or not str(concept_type).strip():
        err(path, "missing or empty required field: type")

    check_links(path, root, body)

    if not HAVE_YAML:
        fm_lower = fm_text.lower()
        if "verified:" in fm_lower:
            tiers["human-reviewed" if "human:" in fm_lower else "machine-confirmed"] += 1
        else:
            tiers["unverified"] += 1
        if "stale_after:" not in fm_lower:
            no_stale += 1
        return

    # Recommended, not required: reported together, and legitimately absent for some
    # subjects (a procedure has no resource to point at).
    absent = [f for f in ("title", "description", "resource") if not data.get(f)]
    if absent:
        warn(path, "no " + ", ".join(absent))

    generated = data.get("generated")
    if not isinstance(generated, dict) or not generated.get("by"):
        warn(path, "no generated.by — the author is unrecorded")
    elif not ACTOR.match(str(generated["by"])):
        warn(path, f"generated.by is not an actor string: {generated['by']}")

    verified = as_list(data.get("verified"))
    human = False
    for entry in verified:
        actor = entry.get("by") if isinstance(entry, dict) else None
        if not actor:
            warn(path, "verified entry with no by")
            continue
        if not ACTOR.match(str(actor)):
            warn(path, f"verified.by is not an actor string: {actor}")
        if str(actor).startswith("human:"):
            human = True
    tiers["human-reviewed" if human else "machine-confirmed" if verified else "unverified"] += 1

    status = data.get("status", "stable")
    statuses[str(status)] = statuses.get(str(status), 0) + 1
    if status not in STATUSES:
        warn(path, f"status is not draft/stable/deprecated: {status}")

    stale_after = data.get("stale_after")
    if stale_after is None:
        no_stale += 1
    else:
        parsed = parse_date(stale_after)
        if parsed is None:
            warn(path, f"stale_after is not YYYY-MM-DD: {stale_after}")
        elif parsed < date.today():
            past_stale += 1
            warn(path, f"stale since {parsed.isoformat()}")

    source_ids = set()
    for source in as_list(data.get("sources")):
        if not isinstance(source, dict):
            warn(path, "sources entry is not a mapping")
            continue
        if not source.get("id"):
            warn(path, f"source with no id: {source.get('resource', source)}")
        else:
            source_ids.add(str(source["id"]))
        if not source.get("resource"):
            warn(path, f"source '{source.get('id')}' has no resource")
        last_modified = source.get("last_modified")
        if last_modified is not None and parse_date(last_modified) is None:
            warn(path, f"source '{source.get('id')}' last_modified is not YYYY-MM-DD")

    check_footnotes(path, body, source_ids)

    if str(concept_type) == "Attested Computation":
        if not data.get("runtime"):
            err(path, "Attested Computation without required field: runtime")
        if not data.get("computation") and "# Computation" not in body:
            warn(path, "no computation path and no '# Computation' section")
        executor = data.get("executor")
        if isinstance(executor, dict) and not executor.get("receipt"):
            warn(path, "executor with no receipt — nothing to attest against")


def check_index(path: Path, root: Path, text: str, is_root: bool) -> set[Path]:
    """Validate an index.md and return the set of paths it links to."""
    fm_text, body = split_frontmatter(text)
    if fm_text is not None:
        if not is_root:
            err(path, "only the bundle-root index.md may carry frontmatter")
        else:
            data = parse_frontmatter(fm_text) or {}
            if isinstance(data, dict):
                if not data.get("okf_version"):
                    warn(path, "root index.md carries frontmatter but no okf_version")
                extra = sorted(k for k in data if k != "okf_version")
                if extra:
                    warn(path, f"root index.md frontmatter has extra keys: {', '.join(extra)}")
    elif is_root:
        warn(path, "no okf_version declared in the bundle-root index.md")

    check_links(path, root, body)

    linked = set()
    for target in LINK.findall(body):
        target = target.split("#", 1)[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        resolved = (root / target.lstrip("/")) if target.startswith("/") else (path.parent / target)
        linked.add(resolved.resolve())
    return linked


def check_log(path: Path, root: Path, text: str) -> None:
    fm_text, body = split_frontmatter(text)
    if fm_text is not None:
        err(path, "log.md must not carry frontmatter")
        body = text
    headings = LOG_HEADING.findall(body)
    if not headings:
        warn(path, "no '## YYYY-MM-DD' date headings")
    for heading in headings:
        if parse_date(heading) is None:
            warn(path, f"date heading is not YYYY-MM-DD: {heading}")
    check_links(path, root, body)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip())
        return 2
    root = Path(argv[1])
    if not root.is_dir():
        print(f"not a directory: {root}")
        return 2

    concepts = indexes = logs = material = 0

    for directory in sorted(p for p in root.rglob("*") if p.is_dir()) + [root]:
        md_files = sorted(directory.glob("*.md"))
        if not md_files:
            continue
        # Under references/, a .md file with frontmatter is a concept; one without is
        # external material (run instructions, a saved doc) and carries no obligations.
        in_references = "references" in directory.relative_to(root).parts
        candidates = []
        for path in (p for p in md_files if p.name not in RESERVED):
            text = path.read_text(encoding="utf-8")
            if in_references and not text.startswith("---"):
                material += 1
                continue
            candidates.append((path, text))

        index_path = directory / "index.md"
        linked: set[Path] = set()

        if index_path.exists():
            indexes += 1
            linked = check_index(
                index_path, root, index_path.read_text(encoding="utf-8"), directory == root
            )
        elif candidates:
            warn(directory, f"no index.md for {len(candidates)} concept(s)")

        log_path = directory / "log.md"
        if log_path.exists():
            logs += 1
            check_log(log_path, root, log_path.read_text(encoding="utf-8"))

        for path, text in candidates:
            concepts += 1
            check_concept(path, root, text)
            if index_path.exists() and path.resolve() not in linked:
                warn(path, "not listed in its directory's index.md")

    mode = "pyyaml" if HAVE_YAML else "degraded: pyyaml not installed, tiers approximate"
    print(f"OKF validation — {root}  ({mode})")
    print(
        f"  {concepts} concept(s), {indexes} index file(s), {logs} log file(s),"
        f" {material} reference file(s)"
    )

    for line in errors:
        print(f"  ERROR    {line}")
    for line in warnings:
        print(f"  warning  {line}")

    tier_counts = ", ".join(f"{count} {tier}" for tier, count in tiers.items() if count)
    print(f"  trust: {tier_counts or 'nothing counted'}")
    if statuses:
        print("  status: " + ", ".join(f"{count} {name}" for name, count in sorted(statuses.items())))
    print(f"  freshness: {past_stale} past stale_after, {no_stale} without one")
    print(f"  {len(errors)} error(s), {len(warnings)} warning(s)")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
