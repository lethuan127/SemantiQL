"""SemantiQL — a semantic layer that lets AI query your database accurately.

The four architectural layers map to these modules; see docs/07-code-map.md.

    knowledge/   Semantic Knowledge — the model, and its only reader
    engine/      SQL Engine — validate, compile, run
    adapters/    Database — one module per datasource, behind adapters.base.Adapter
                 Data Governance — not yet implemented

Query through `semantiql.run`. It is the single validated path to the data.
"""

from importlib import metadata as _metadata
from pathlib import Path as _Path

from semantiql.engine.run import Result, run
from semantiql.engine.validate import Refusal
from semantiql.knowledge.loader import ModelError, load_model
from semantiql.knowledge.model import SemanticModel


def _resolve_version() -> str:
    """The version, from installed metadata where there is any.

    Read rather than restated, because two copies of a version drift and the one in the wheel is
    the one users have. The fallbacks exist for code on `sys.path` without a distribution
    installed, and the Desktop bundle is the real case: it carries this package as source and
    never installs it, so the metadata lookup raises.

    Before this existed, importing SemantiQL failed outright on any machine that did not already
    have it installed — and the bug was invisible in development, because a checkout always has
    the distribution present (spec 014).
    """
    try:
        return _metadata.version("semantiql")
    except _metadata.PackageNotFoundError:  # pragma: no cover - only outside an installed package
        # A build stamp, written beside this file by scripts/build_bundle.py. A plain text file
        # rather than a module: there is nothing to import, nothing for a type checker to stub,
        # and it is obviously generated.
        stamp = _Path(__file__).with_name("_version.txt")
        if stamp.is_file():
            return stamp.read_text().strip()
        # A source tree on PYTHONPATH with neither. Honest rather than invented.
        return "0+unknown"


__version__ = _resolve_version()

__all__ = ["ModelError", "Refusal", "Result", "SemanticModel", "load_model", "run"]
