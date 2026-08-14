"""SemantiQL — a semantic layer that lets AI query your database accurately.

The four architectural layers map to these modules; see docs/07-code-map.md.

    knowledge/   Semantic Knowledge — the model, and its only reader
    engine/      SQL Engine — validate, compile, run
    adapters/    Database — one module per datasource, behind adapters.base.Adapter
                 Data Governance — not yet implemented

Query through `semantiql.run`. It is the single validated path to the data.
"""

from importlib import metadata as _metadata

from semantiql.engine.run import Result, run
from semantiql.engine.validate import Refusal
from semantiql.knowledge.loader import ModelError, load_model
from semantiql.knowledge.model import SemanticModel

# Read from installed metadata rather than restated here: two copies of a version drift,
# and the one in the wheel is the one users actually have. pyproject.toml is authoritative.
__version__ = _metadata.version("semantiql")

__all__ = ["ModelError", "Refusal", "Result", "SemanticModel", "load_model", "run"]
