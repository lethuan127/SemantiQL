"""The only reader of the semantic model YAML (constitution N3).

Nothing else in the package parses YAML or constructs a `SemanticModel`. Keeping that
true is what makes the file, rather than some value in Python, authoritative.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from semantiql.knowledge.model import SemanticModel


class _StrictLoader(yaml.SafeLoader):
    """A SafeLoader that refuses duplicate mapping keys.

    PyYAML resolves a repeated key last-wins *before* pydantic ever sees the data, so
    `extra="forbid"` cannot catch it. In a file that defines what "revenue" means, a
    duplicate silently redefining it is exactly the class of error this project treats as
    unacceptable — a merge conflict or a careless paste becomes a wrong number with no
    symptom.
    """


def _no_duplicates(
    loader: _StrictLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    seen: set[object] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.YAMLError(
                f"duplicate key {key!r} at line {key_node.start_mark.line + 1} — "
                "the semantic model must define each name exactly once"
            )
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates)


class ModelError(Exception):
    """The model file is missing, unparseable, or invalid.

    Raised rather than returning a partial model: a half-loaded semantic layer would
    answer some questions correctly and others wrongly, which is the failure mode the
    project exists to prevent.
    """


def load_model(path: str | Path) -> SemanticModel:
    """Read and validate the semantic model at `path`."""
    p = Path(path)
    if not p.is_file():
        raise ModelError(f"no semantic model at {p}")

    try:
        raw: Any = yaml.load(p.read_text(encoding="utf-8"), Loader=_StrictLoader)
    except yaml.YAMLError as exc:
        raise ModelError(f"{p} is not parseable YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ModelError(f"{p} must contain a mapping at the top level, got {type(raw).__name__}")

    try:
        model = SemanticModel.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        raise ModelError(f"{p} is not a valid semantic model — {details}") from exc

    return _resolve_sources(model, p.parent)


def _resolve_sources(model: SemanticModel, base: Path) -> SemanticModel:
    """Make a relative file `source` relative to the model file, not the process cwd.

    Without this the bundled example only works when run from the repo root, which would
    make `uvx semantiql` fail for every user who is not standing in the right directory.
    A bare table or view name is left alone.
    """
    updates = {}
    for name, table in model.tables.items():
        source = Path(table.source)
        if source.suffix.lower() in {".csv", ".parquet"} and not source.is_absolute():
            updates[name] = table.model_copy(update={"source": str((base / source).resolve())})
    if not updates:
        return model
    return model.model_copy(update={"tables": {**model.tables, **updates}})
