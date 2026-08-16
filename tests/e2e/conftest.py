"""The corpus these tests run against, built once per session.

The unit suite proves the engine on ten rows whose totals were computed by hand. That is
exact, and it is small enough that a fault needing many groups, several years of dates, or a
hundred thousand rows can hide in it. This fixture builds the other kind of evidence.

**TPC-H, generated locally.** DuckDB's `dbgen` writes the standard eight tables with no
credentials and no download of data, and takes a scale factor — 0.18s for 60,175 line items at
the default, 9.5s for six million at `sf=1`. Set `SEMANTIQL_E2E_SF` to scale it up for a soak
run.

**Denormalised, because the engine is single-table by design.** The eight tables are joined
once, here, into a `sales` view — the same escape hatch the documentation recommends to a
modeller who needs a join.

**A companion `edge` table, because TPC-H cannot cover everything.** It contains no nulls and
no boolean column, so on its own it would leave the traps the documentation warns about —
`count` versus `count_distinct`, `<>` dropping nulls, a metric with a zero divisor — tested
only by the ten-row corpus. `edge` is small and deliberate.

**Read-only.** The generating connection is closed before any test runs, and the adapter
reopens the file `read_only=True`. That is the half of N5 the in-memory CLI path cannot
demonstrate, and `test_edge_semantics.py` asserts DuckDB itself rejects a write.

If `dbgen` is unavailable the whole package skips. The extension is fetched once from DuckDB's
repository, so a first run with no network would otherwise fail the verify gate and make the
README's "no network" promise false.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from semantiql.adapters.duckdb import DuckDBAdapter
from semantiql.knowledge.loader import load_model
from semantiql.knowledge.model import SemanticModel

MODEL_PATH = Path(__file__).parent / "semantic_model.yml"

#: Default scale factor. 60,175 rows in under a fifth of a second — large enough for many
#: groups and seven years of dates, small enough to run on every save.
DEFAULT_SF = "0.01"

#: The eight TPC-H tables as the one wide relation a single-table engine can address.
_SALES_VIEW = """
CREATE VIEW sales AS
SELECT
    l.l_orderkey                          AS order_id,
    o.o_orderdate                         AS order_date,
    c.c_custkey                           AS customer_id,
    c.c_mktsegment                        AS segment,
    n.n_name                              AS nation,
    r.r_name                              AS region,
    l.l_shipmode                          AS ship_mode,
    l.l_returnflag                        AS return_flag,
    l.l_quantity                          AS quantity,
    l.l_extendedprice                     AS gross_amount,
    l.l_extendedprice * (1 - l.l_discount) AS net_amount
FROM lineitem l
JOIN orders   o ON l.l_orderkey  = o.o_orderkey
JOIN customer c ON o.o_custkey   = c.c_custkey
JOIN nation   n ON c.c_nationkey = n.n_nationkey
JOIN region   r ON n.n_regionkey = r.r_regionkey
"""

#: What TPC-H has none of: nulls, a boolean, and a group whose metric divisor is zero.
#: `refunds` is null for every 'quiet' row, so a metric dividing by it has nothing to divide.
_EDGE_TABLE = """
CREATE TABLE edge (label VARCHAR, flagged BOOLEAN, amount DECIMAL(10,2), refunds INTEGER);
INSERT INTO edge VALUES
    ('busy',  TRUE,  100.00, 2),
    ('busy',  FALSE,  50.00, 1),
    ('busy',  TRUE,   25.00, NULL),
    ('quiet', TRUE,   10.00, NULL),
    ('quiet', FALSE,   5.00, NULL),
    (NULL,    NULL,    1.00, NULL);
"""


def _scale_factor() -> float:
    raw = os.environ.get("SEMANTIQL_E2E_SF", DEFAULT_SF)
    try:
        return float(raw)
    except ValueError:  # pragma: no cover - operator error, reported rather than guessed
        pytest.fail(f"SEMANTIQL_E2E_SF must be a number, got {raw!r}")


@pytest.fixture(scope="session")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Generate the corpus once, then close every writable handle to it."""
    path = tmp_path_factory.mktemp("corpus") / "tpch.duckdb"
    connection = duckdb.connect(str(path))
    try:
        connection.execute(f"CALL dbgen(sf={_scale_factor()})")
    except duckdb.Error as exc:
        connection.close()
        pytest.skip(
            "DuckDB's tpch extension is unavailable, so the large corpus cannot be built — "
            f"the first generation fetches it from DuckDB's repository. ({exc})"
        )
    connection.execute(_SALES_VIEW)
    connection.execute(_EDGE_TABLE)
    connection.close()
    yield path


@pytest.fixture(scope="session")
def e2e_model() -> SemanticModel:
    """The semantic model over the corpus — a real file, read by the real loader."""
    return load_model(MODEL_PATH)


@pytest.fixture
def e2e_adapter(corpus: Path) -> Iterator[DuckDBAdapter]:
    """The adapter under test: the same file, opened read-only."""
    adapter = DuckDBAdapter(str(corpus))
    yield adapter
    adapter.close()


@pytest.fixture(scope="session")
def oracle(corpus: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    """A plain DuckDB connection for the hand-written SQL each case is checked against.

    Deliberately not the adapter: the point is to ask the same question by a route the engine
    had no part in building.
    """
    connection = duckdb.connect(str(corpus), read_only=True)
    yield connection
    connection.close()
