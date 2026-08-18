"""The datasource seam (constitution N4).

Adding a datasource means writing one module that satisfies `Adapter` — connect,
introspect, execute — and registering it. No change to `engine/` or `knowledge/`.

This is a `Protocol` rather than a base class on purpose: a third-party adapter never
imports or subclasses SemantiQL internals, so "one adapter, no core changes" holds for
outside contributors too, not just for code in this repo.

`execute` takes SQL that has already been validated and transpiled. Adapters do not
validate, and they must not rewrite: the single validation chokepoint is
`engine.run.run`, and an adapter second-guessing it would create a path where a query
reaches data on terms nothing checked (N1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from sqlglot import exp


class AdapterError(Exception):
    """The datasource could not be reached, or rejected the SQL."""


#: The semantic model's own type vocabulary, plus `other` for a type the adapter cannot map.
#: Deliberately the model's words rather than any engine's: DuckDB says `VARCHAR`, Postgres
#: says `character varying`, BigQuery says `STRING`, and the checker that compares a column to
#: `type:` must not learn all three. Translation is the adapter's job (N4).
ColumnKind = Literal["string", "date", "number", "boolean", "other"]


@dataclass(frozen=True)
class Column:
    """A column as the datasource describes it.

    `native_type` is the engine's own name, kept for error messages a DBA will recognise.
    `kind` is that type expressed in the model's vocabulary — or `other`, which means the
    adapter could not tell and callers must treat as silence rather than as a mismatch. An
    honest unknown is worth more here than a confident wrong answer.
    """

    name: str
    native_type: str
    kind: ColumnKind
    carries_timezone: bool = False
    """Whether this column stores an instant with a zone attached (`timestamptz`).

    Deliberately a flag rather than a fifth `ColumnKind`. `doctor` compares `kind` to the
    model's `type:` for **equality**, so a fifth value would make every `timestamptz` column
    report "declared date, but the column is timestamp with time zone — filters on it will be
    typed wrongly". That is false: filtering a `timestamptz` against a date literal is fine.
    The distinction matters for exactly one thing — time grains — so it travels as one bit
    beside `kind` instead of fragmenting the four-word vocabulary (spec 011).

    Defaults to `False`, so an adapter written before this existed keeps working and simply
    reports "no zone", which is the safe answer for the types it was built for.
    """


@runtime_checkable
class Adapter(Protocol):
    """What SemantiQL needs from a datasource."""

    @property
    def dialect(self) -> str:
        """The sqlglot dialect name SQL must be transpiled to before `execute`."""
        ...

    def relation(self, source: str) -> exp.Expr:
        """Turn a model `source` into a relation expression this datasource can select from.

        Returns a **built expression**, never a SQL string: a string would be re-parsed by
        the compiler, letting a quote inside `source` escape into the FROM clause. Build it
        with `exp.to_table` or `exp.func` and the value stays a value.
        """
        ...

    def tables(self) -> list[str]:
        """Every relation this datasource offers, as names `columns()` will accept.

        Tables *and* views. A view is the documented way to model a join, so omitting them would
        hide the exact relations a modeller is most likely to want.

        Names are qualified by schema only where they need to be — bare in the default schema,
        `schema.name` outside it — so a discovered name can be pasted into a model's `source:`
        unchanged and still be unambiguous.

        Returns names rather than a richer record on purpose. A name is what `columns()` needs, and
        a Protocol that an outside adapter has to satisfy should ask for the least that does the
        job; `semantiql inspect` can present more without the seam growing.

        **This is the third time this Protocol has grown** — `close()` (spec 010),
        `carries_timezone` (011), now `tables()` (016). Each was found by building a real consumer
        against it, which is the seam doing its job. But three is a pattern: a fourth should prompt
        asking whether this is still the right shape, rather than adding a fifth.
        """
        ...

    def columns(self, source: str) -> list[Column]:
        """Describe the columns of a model `source` — the basis for checking model vs reality.

        Takes the `source` exactly as the semantic model writes it, not a relation string: the
        adapter turns it into something selectable with its own `relation()`, so a CSV path and
        a table name are both handled here rather than by the caller, and the value is built
        into the probe rather than interpolated into it.

        Classifies each column into `ColumnKind`. An adapter that cannot map one of its types
        returns `other`.
        """
        ...

    def execute(self, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Run already-validated, already-transpiled SQL. Returns (column names, rows)."""
        ...

    def close(self) -> None:
        """Release whatever the adapter holds open. An adapter holding nothing no-ops.

        This arrived late, and how it arrived is the point (spec 010). The CLI has always
        called `close()` in a `finally`, and both adapters have always defined it — but the
        Protocol did not declare it, and nothing noticed, because the CLI was typed against
        `DuckDBAdapter` rather than against this. An outside adapter written to the published
        Protocol would have passed `isinstance`, passed mypy, and then crashed on the way out.

        One implementation cannot tell you a seam is incomplete. The second one can.
        """
        ...
