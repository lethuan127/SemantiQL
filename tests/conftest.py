"""Shared fixtures. The example model is the test corpus — if it breaks, the demo breaks."""

from __future__ import annotations

from pathlib import Path

import pytest

from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.knowledge.loader import load_model
from semantiql.knowledge.model import SemanticModel

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "retail" / "semantic_model.yml"


@pytest.fixture(scope="session")
def model() -> SemanticModel:
    return load_model(EXAMPLE)


@pytest.fixture
def adapter() -> DuckDBAdapter:
    return DuckDBAdapter()
