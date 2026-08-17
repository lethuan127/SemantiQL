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


#: Files a model directory is made of. Anything else in the tree is ignored as not-a-model;
#: anything with these suffixes must contribute, or it is an error (see `_read_directory`).
_MODEL_SUFFIXES = (".yml", ".yaml")

#: Keys that belong to the model as a whole rather than to a table. Declared once across a
#: directory — not merged, and not required to be repeated identically in thirty files.
_SINGLETON_KEYS = ("version", "datasource")


def load_model(path: str | Path) -> SemanticModel:
    """Read and validate the semantic model at `path`, which may be a file or a directory.

    A directory is one model spread over several files — typically one per table, so a warehouse
    is a reviewable tree instead of a two-thousand-line document. A single file behaves exactly as
    it always has.
    """
    p = Path(path)
    if p.is_dir():
        raw, provenance = _read_directory(p)
    elif p.is_file():
        raw = _read_file(p)
        provenance = dict.fromkeys(_tables_in(raw, p), p)
    else:
        raise ModelError(f"no semantic model at {p}")

    try:
        model = SemanticModel.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        where = p if p.is_file() else f"the model in {p}"
        raise ModelError(f"{where} is not a valid semantic model — {details}") from exc

    return _resolve_sources(model, provenance)


def _read_file(p: Path) -> dict[str, Any]:
    """One file's mapping, or an error naming it."""
    try:
        raw: Any = yaml.load(p.read_text(encoding="utf-8"), Loader=_StrictLoader)
    except yaml.YAMLError as exc:
        raise ModelError(f"{p} is not parseable YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ModelError(f"{p} must contain a mapping at the top level, got {type(raw).__name__}")
    return raw


def _tables_in(raw: dict[str, Any], p: Path) -> list[str]:
    tables = raw.get("tables")
    if tables is None:
        return []
    if not isinstance(tables, dict):
        raise ModelError(f"{p}: `tables` must be a mapping, got {type(tables).__name__}")
    return list(tables)


def _read_directory(directory: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    """Merge every model file under `directory` into one mapping, refusing every ambiguity.

    The mappings are merged and validated **once**, by the same schema a single file goes through,
    so every rule already written applies here unchanged. Validating file by file is not possible
    even in principle — a table file has no `datasource`, so it is not a `SemanticModel` — and a
    second, looser schema would be a second place for the model's rules to live and disagree.

    Where the strictness goes is the point. `_StrictLoader` already refuses a duplicate key inside
    one file, because a careless paste redefining "revenue" becomes a wrong number with no symptom.
    Two files defining one table is that same failure one level up, so it is refused the same way —
    naming both files, because in a tree of thirty an error that could be about any of them is
    barely an error at all.
    """
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in _MODEL_SUFFIXES
    )
    if not files:
        raise ModelError(
            f"{directory} contains no {' or '.join(_MODEL_SUFFIXES)} files, so there is no model "
            "to load"
        )

    merged: dict[str, Any] = {"tables": {}}
    declared_by: dict[str, Path] = {}  # singleton key -> the file that declared it
    provenance: dict[str, Path] = {}  # table name -> the file that declared it

    for path in files:
        raw = _read_file(path)
        contributed = False

        for key in _SINGLETON_KEYS:
            if key not in raw:
                continue
            if key in declared_by:
                raise ModelError(
                    f"`{key}` is declared in both {declared_by[key]} and {path}. Declare it once "
                    "for the whole model — two declarations cannot both be authoritative"
                )
            declared_by[key] = path
            merged[key] = raw[key]
            contributed = True

        for name in _tables_in(raw, path):
            if name in provenance:
                raise ModelError(
                    f"table {name!r} is defined in both {provenance[name]} and {path}. "
                    "Rename one — merging them would silently pick a definition"
                )
            provenance[name] = path
            merged["tables"][name] = raw["tables"][name]
            contributed = True

        unknown = set(raw) - set(_SINGLETON_KEYS) - {"tables"}
        if unknown:
            raise ModelError(
                f"{path} declares {', '.join(sorted(repr(k) for k in unknown))}, which mean "
                f"nothing in a semantic model. Expected any of: "
                f"{', '.join(_SINGLETON_KEYS)}, tables"
            )
        if not contributed:
            # Skipping it silently would leave someone believing they had modelled a table that
            # is absent, and the symptom is a refusal that reads like a bug in the engine.
            raise ModelError(
                f"{path} contributes nothing to the model — it declares no tables and no "
                f"{' or '.join(_SINGLETON_KEYS)}. Remove it or give it content"
            )

    if "datasource" not in merged:
        raise ModelError(
            f"no file under {directory} declares `datasource`. Exactly one must — conventionally "
            "a datasource.yml alongside the table files"
        )
    return merged, provenance


def _resolve_sources(model: SemanticModel, provenance: dict[str, Path]) -> SemanticModel:
    """Make a relative file `source` relative to the file that declared it, not the process cwd.

    Without this the bundled example only works when run from the repo root, which would
    make `uvx semantiql` fail for every user who is not standing in the right directory.
    A bare table or view name is left alone.

    Per declaring file rather than per model, because a directory model has no single base: a CSV
    should be able to sit beside the YAML that describes it, wherever in the tree that is.
    """
    updates = {}
    for name, table in model.tables.items():
        source = Path(table.source)
        if source.suffix.lower() in {".csv", ".parquet"} and not source.is_absolute():
            base = provenance[name].parent
            updates[name] = table.model_copy(update={"source": str((base / source).resolve())})
    if not updates:
        return model
    return model.model_copy(update={"tables": {**model.tables, **updates}})
