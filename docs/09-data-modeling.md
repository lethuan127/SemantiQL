# Data modeling — writing the semantic model

The semantic model is the one file that decides what an AI is allowed to ask and what each
business word means. It is the source of truth (constitution N3), and it is the only place a
definition like *revenue* exists — never in Python, never in a prompt, never in the query.

This document is the reference for writing one: every field, every allowed value, what each
one compiles to, what is rejected and when, and what the model deliberately cannot say yet.

It describes **what is implemented today**, verified against the code and by running it.
[02-architecture.md](02-architecture.md) describes the intended shape of layer 1, which is
larger than what is built — where the two differ, this file is the narrower, truer one.
Module ownership is in [07-code-map.md](07-code-map.md).

---

## 1. What the model is for

Three jobs, in order of importance:

1. **It fixes meaning.** `revenue` is `SUM(amount)` on `orders`, once, for everybody. Two
   people asking the same question get the same number because there is only one
   definition to get.
2. **It defines the allowed surface.** `engine/validate.py` resolves every identifier in a
   request against this file. A name that is not here is refused — that refusal is the
   product, not a rough edge (N1, N2).
3. **It separates business words from physical columns.** The AI writes `revenue`, the
   database sees `SUM(amount)`. Renaming a column is a one-line model change and no
   consumer notices.

What the model is *not*: it is not a place to store queries, filters, thresholds, or
report definitions. Nothing here can express "web orders in July" — see §8.

---

## 2. Anatomy of a model file

The bundled [`examples/retail/semantic_model.yml`](../examples/retail/semantic_model.yml) is
a complete, working model. The full structure is:

```yaml
version: 1                      # optional, but must be 1 if present

datasource:
  name: retail                  # required — a label for humans
  dialect: duckdb               # optional, default duckdb. duckdb | postgres

tables:                         # required (may be an empty mapping)
  orders:                       # ← the name the AI writes after FROM
    source: orders.csv          # required — the physical relation

    dimensions:                 # optional, default {}
      channel:                  # ← the name the AI writes in SELECT
        column: channel         # required — the physical column
        type: string            # optional, default string
        label: Sales channel    # optional
        description: How the order was placed — web, retail, or partner.

    measures:                   # optional, default {}
      revenue:
        column: amount          # required — the physical column
        agg: sum                # required — the one sanctioned aggregation
        label: Revenue
        description: Sum of order amounts. The one sanctioned definition of revenue.
```

Four levels, and each has exactly one job:

| Level | Job |
|---|---|
| `datasource` | which engine executes, and therefore which SQL dialect is emitted |
| `tables.<name>` | one physical relation, exposed under a business name |
| `dimensions` | the things you can slice by — become `SELECT` columns and the `GROUP BY` |
| `measures` | the things you can count — become the aggregate in the `SELECT` |

---

## 3. Field reference

Every model object rejects unknown keys and is frozen after loading
(`_Strict` in `knowledge/model.py:17`). A typo is an error, not a silently ignored key —
see §6.

### 3.1 Top level — `SemanticModel` (`model.py:79`)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `version` | `1` | no | `1` | Only the literal `1` is accepted. `version: 2` fails to load. |
| `datasource` | mapping | **yes** | — | See below. |
| `tables` | mapping of name → table | **yes** | — | May be empty (`{}`); a model with no tables loads and refuses every query. |

### 3.2 `datasource` (`model.py:72`)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | string | **yes** | — | A human label. Not used to resolve anything. |
| `dialect` | `duckdb` \| `postgres` | no | `duckdb` | The dialect the SQL is transpiled to, and the dialect the adapter must declare. |

`dialect` is checked against the adapter at runtime. If the model says `postgres` and the
adapter in use is DuckDB, `run` refuses before validating anything
(`engine/run.py:38`) — running one engine's SQL against another silently applies the wrong
semantics to the same text.

The enum is deliberately narrower than sqlglot's dialect list: it names the datasources
this project actually has adapters for. `dialect: mysql` fails to load, by design
([05-datasources.md](05-datasources.md) has the roadmap).

### 3.3 `tables.<name>` — `Table` (`model.py:41`)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `source` | string | **yes** | — | The physical relation. See §5. |
| `dimensions` | mapping of name → dimension | no | `{}` | |
| `measures` | mapping of name → measure | no | `{}` | A table with no measures loads, but every query against it is refused (§4.4). |

The mapping **key** is the semantic name — what the AI writes. It is yours to choose and it
does not have to resemble the physical column.

A name defined as both a dimension and a measure on the same table is rejected at load
(`model.py:48`): the two would resolve inconsistently, so the same word would mean two
different things depending on who asked.

### 3.4 `dimensions.<name>` — `Dimension` (`model.py:23`)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `column` | string | **yes** | — | The physical column name. |
| `type` | `string` \| `date` \| `number` \| `boolean` | no | `string` | Checked against filter literals — see the note below. |
| `label` | string | no | `null` | Human-facing name. **Not consumed by any code path yet.** |
| `description` | string | no | `null` | Meaning and gotchas. **Not consumed by any code path yet.** |

> **`type` governs filters, not the database.** Since filters landed it is load-bearing in
> one direction: a literal in a `WHERE` is checked against it, so `WHERE order_date >=
> 'yesterday'` is refused as a bad date, `WHERE channel = 5` is refused as unquoted, and
> `LIKE` is refused on anything but a `string` dimension. A `date` dimension's literals are
> also emitted as `CAST(… AS DATE)` rather than left to each engine's coercion rules.
>
> What it still does **not** do is check the physical column. Nothing compares `type` to the
> real schema, so a `date` column declared `type: boolean` loads and returns dates — it will
> simply refuse the filters that a boolean cannot take. Declaring it correctly matters more
> than it used to.

> **`label` and `description` are written but never read.** Grep confirms it: no engine, CLI,
> or adapter code touches them. They exist because the MCP server — the thing that will
> present the model to Claude — is not built yet (README roadmap). Write them anyway: they
> are the model's documentation for the humans reviewing the diff, and they are the payload
> the MCP layer will need. Just do not expect them to change an answer today.

### 3.5 `measures.<name>` — `Measure` (`model.py:32`)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `column` | string | **yes** | — | The physical column to aggregate. |
| `agg` | one of the six below | **yes** | — | The *one* sanctioned aggregation for this measure. |
| `label` | string | no | `null` | Not consumed yet. |
| `description` | string | no | `null` | Not consumed yet. |

There is no `type` on a measure and no per-measure filter. A measure is exactly one column
and one aggregation.

---

## 4. Aggregations

Six, defined as a closed enum at `model.py:14` and rendered at `compile.py:33-50`. The list
is fixed by the code — YAML cannot extend it.

| `agg` | Emitted SQL | Use it for |
|---|---|---|
| `sum` | `SUM(col)` | additive amounts — revenue, quantity, cost |
| `count` | `COUNT(col)` | how many rows have a non-null value in `col` |
| `count_distinct` | `COUNT(DISTINCT col)` | how many *different* values — customers, orders, SKUs |
| `min` | `MIN(col)` | earliest date, lowest price |
| `max` | `MAX(col)` | latest date, highest price |
| `avg` | `AVG(col)` | mean of a column |

Anything else fails at load:

```
error: … is not a valid semantic model — tables.orders.measures.revenue.agg:
Input should be 'sum', 'count', 'count_distinct', 'min', 'max' or 'avg'
```

Four things worth knowing before you pick one:

**`count` counts non-null values, not rows.** That is standard SQL, and it is a real trap:
point `count` at a column with nulls and you get fewer than the row count. Point it at a key
that is never null — the example uses `order_id` — when you mean "how many rows".

**`count` and `count_distinct` differ when the column repeats.** `order_count` in the
example counts order *lines*. If a single order spans several rows, `count_distinct` on
`order_id` is the measure you actually wanted. The model cannot tell you which — that is why
the field is called `description`.

**`avg` is the average of the underlying rows, not of a grouped result.** `average_order_value`
is `AVG(amount)`. When the query groups by `channel`, each row is the average within that
channel — correct. There is no way to average an already-aggregated measure, and no way to
express `SUM(amount) / COUNT(DISTINCT order_id)` at all (§8).

**A measure is `agg` applied to one raw column, always.** You cannot aggregate an
expression (`amount * 0.2`), a `CASE`, or another measure. If you need a derived column,
derive it in the database — a view — and point `source` at that.

---

## 5. `source` — how a table binds to physical data

`source` is the one field in the model that is genuinely physical. Its interpretation is the
adapter's job (`adapters/duckdb.py:38`), which is why it is the field that limits
portability.

For the DuckDB adapter:

| `source` ends in | Becomes | Example |
|---|---|---|
| `.csv` | `READ_CSV_AUTO('<path>')` | `orders.csv` |
| `.parquet` | `READ_PARQUET('<path>')` | `orders.parquet` |
| anything else | a table or view name | `orders`, `analytics.orders` |

**Relative file paths resolve against the model file, not the working directory**
(`loader.py:81`). `source: orders.csv` next to `semantic_model.yml` works from any
directory — without that, the bundled example would only run from the repo root, and
`uvx semantiql` would fail for everyone standing somewhere else. Bare table names are left
untouched.

The path is passed to SQL as a **string literal expression**, never as text spliced into the
FROM clause, so a quote inside `source` is escaped rather than injecting extra relations
(`test_compile.py:113` is the regression test for that).

**Portability caveat, stated honestly.** N3 says the model is datasource-independent, and
the semantic half of it is: dimensions, measures and aggregations carry over unchanged.
`source` and `datasource.dialect` do not — a CSV path means nothing to Postgres. Moving a
model between engines is a two-line change per table plus one dialect line, not a rewrite.

---

## 6. What loading rejects, and why

`knowledge/loader.py` is the only reader of the YAML (N3). Every failure raises `ModelError`
with the file path and a field-level message; nothing partial is ever returned, because a
half-loaded semantic layer answers some questions right and others wrong.

| You wrote | Result |
|---|---|
| a missing file | `no semantic model at <path>` |
| broken YAML | `<path> is not parseable YAML: …` |
| a list, or a scalar, at the top level | `must contain a mapping at the top level, got list` |
| `aggregation: sum` instead of `agg:` | `measures.revenue.aggregation: Extra inputs are not permitted` |
| `agg: median` | `measures.revenue.agg: Input should be 'sum', 'count', …` |
| `dialect: mysql` | `datasource.dialect: Input should be 'duckdb' or 'postgres'` |
| `type: timestamp` on a dimension | `dimensions.c.type: Input should be 'string', 'date', 'number' or 'boolean'` |
| the same name as a dimension *and* a measure | `r defined as both a dimension and a measure; each name must be one or the other` |
| `version: 2` | `version: Input should be 1` |
| no `tables:` key | `tables: Field required` |
| the same YAML key twice | `duplicate key 'r' at line 7 — the semantic model must define each name exactly once` |

The duplicate-key check deserves a note. PyYAML resolves a repeated key last-wins *before*
pydantic sees the data, so `extra="forbid"` cannot catch it. In a file that defines what
"revenue" means, a merge conflict or a careless paste that redefines it would otherwise
become a wrong number with no symptom. `_StrictLoader` (`loader.py:18`) refuses it instead.

**What loading does *not* check:** whether `source` exists, whether `column` exists in it, or
whether `agg` makes sense for that column's type. Nothing introspects the database at load
time. Those failures surface at execution — see §7.

---

## 7. What the model does to a query

Worked example, against the bundled retail model:

```
semantic SQL:  SELECT revenue, average_order_value, channel FROM orders

physical SQL:  SELECT SUM(amount) AS revenue,
                      AVG(amount) AS average_order_value,
                      channel AS channel
               FROM READ_CSV_AUTO('…/examples/retail/orders.csv')
               GROUP BY channel
```

The rules the compiler follows (`engine/compile.py:53`):

- **A measure becomes its sanctioned aggregation**, aliased to the name the caller used.
- **A dimension becomes a plain column** *and* a `GROUP BY` entry. Both, always — you cannot
  select a dimension without grouping by it, or group by something you did not select.
- **Requested order is preserved**, in the projection list and in the `GROUP BY`, so a caller
  indexing rows positionally gets what it asked for in the order it asked.
- **No dimension requested → no `GROUP BY`** and a single-row answer.
- **Everything comes from the model.** The compiler rebuilds the query; it never rewrites the
  caller's AST. That is exactly why unsupported clauses must be refused rather than dropped.

### 7.1 Name resolution rules, precisely

Verified by running them:

| Request | Outcome |
|---|---|
| `SELECT revenue FROM orders` | ✅ |
| `select revenue from orders` | ✅ — keywords are case-insensitive |
| `SELECT REVENUE FROM orders` | ❌ refused — **entity names are case-sensitive**; the refusal suggests `revenue` |
| `SELECT revenue FROM ORDERS` | ❌ refused — **table names are case-sensitive**; suggests `orders` |
| `SELECT "revenue" FROM "orders"` | ✅ — quoting is accepted |
| `SELECT revenue AS total FROM orders` | ✅ — the alias is honoured in the output column |
| `SELECT orders.revenue FROM orders` | ✅ — the qualifier is **ignored**; only the last name part is resolved |
| `SELECT bogus.revenue FROM orders` | ✅ — same reason. A wrong qualifier is not currently an error |
| `SELECT revenue FROM main.orders AS o` | ✅ — catalog/schema prefixes and table aliases are ignored |
| `SELECT revenue, revenue FROM orders` | ✅ — duplicates are not deduplicated |
| `SELECT amount FROM orders` | ❌ refused — physical columns are **not** addressable, only model names |
| `SELECT SUM(amount) FROM orders` | ❌ refused — the caller does not choose the aggregation |
| `SELECT * FROM orders` | ❌ refused — `*` is not a dimension or measure |
| `SELECT channel FROM orders` | ❌ refused — no measure means there is no number to compute |

Case-sensitivity is worth designing around: LLM-written SQL is often upper-cased, so
`_suggest` (`validate.py:115`) matches case-insensitively and the refusal names the right
spelling. It suggests; it never substitutes. **Prefer lowercase snake_case names** so the
model matches what a model tends to emit.

### 7.2 When failures surface

| Mistake in the model | Caught | Symptom |
|---|---|---|
| unknown key, bad enum, duplicate key, name clash | **load** | `ModelError`, CLI exit `2` |
| model dialect ≠ adapter dialect | **run**, before validation | `Refusal`, CLI exit `1` |
| name the AI asked for is not in the model | **run**, before the database is touched | `Refusal`, exit `1` |
| `source` does not exist | **execute** | `AdapterError` — `IO Error: No files found…` / `Catalog Error: Table … does not exist`, exit `3` |
| `column` does not exist | **execute** | `AdapterError` — `Binder Error: Referenced column "profit" not found` |
| `agg: sum` on a text column | **execute** | `AdapterError` — `No function matches the given name and argument types 'sum(VARCHAR)'` |
| `type:` disagrees with the real column | **never** for the read; **run** for a filter | rows come back regardless, but filter literals are checked against the declared type, so the wrong `type:` refuses valid filters (§3.4) |

The bottom half of that table is the argument for `semantiql doctor` and schema
introspection, both on the roadmap and neither built. `Adapter.columns()` exists and is
tested but no engine code calls it yet — model-vs-reality checking is the obvious next use.
Until then, a model change is only proven by running a query against it.

---

## 8. What the model cannot express yet

Stated plainly so you do not model around a feature that is not there, and do not file it as
a bug. The README and [02-architecture.md](02-architecture.md) describe layer 1 as
"dimensions, measures, metrics, virtual views" — **metrics and virtual views are intent, not
implementation.**

Not expressible in the model today:

- **Filters in the *model*.** A request may carry a `WHERE` over dimensions (A.2), but the
  model itself cannot declare one: no default filter on a table, no filter baked into a
  measure. Filtering on a measure — `WHERE revenue > 1000`, which SQL would express as
  `HAVING` — is refused.
- **Derived or ratio metrics.** No `SUM(x) / COUNT(y)`, no measure referencing another
  measure, no expression as a `column`.
- **Joins and relationships.** One table per request, and no way to declare that `orders`
  relates to `customers`. Multi-table requests are refused.
- **Virtual views.** No model-defined view composed from other model entities. The
  equivalent today is a database view, referenced through `source`.
- **Time grains.** No `month`/`quarter` derivation on a `date` dimension. `type: date` is a
  declaration, not a truncation. This is also why the transpile step is currently untested
  in anger — nothing the engine emits is dialect-specific yet (`test_compile.py:57`).
- **Synonyms or aliases for entities**, formatting hints, units, or currency.
- **Row-level security, masking, or access control.** That is layer 3, deliberately
  unimplemented ([07-code-map.md](07-code-map.md)).
- **Ordering and limits.** `ORDER BY` and `LIMIT` are refused, so a "top 5 channels" answer
  is the caller's job after the fact.

The workaround for most of these is the same: **push it into the database and point `source`
at a view.** A view can filter, join, derive, and truncate; the model then exposes the result
as plain dimensions and measures. It costs you the diffable definition — the logic now lives
in the warehouse instead of in git — so use it for shape, not for the definition of a
business number.

If you need one of these features in the model itself, it is a spec, not a patch: adding a
construct to the compiler means adding it to the allowlist in `validate.py` **in the same
change that teaches the compiler to honour it, never before** (see A.6).

---

## 9. Modeling guidance

**One table entry per grain.** `source` is one relation and every request is single-table, so
each table entry should be one clean grain of fact (one row = one order line). Mixed grains
produce measures that are right at one grain and wrong at another, with nothing to catch it.

**Name for the business, not the schema.** `revenue`, not `sum_amt`. The semantic name is the
whole point of the indirection; if it matches the column exactly, ask whether the model is
earning its keep for that entity.

**Lowercase snake_case, always.** Resolution is case-sensitive (§7.1). Consistency here
removes a whole class of refusal.

**One definition per business word.** Do not add `revenue_net` and `revenue_gross` and leave
`revenue` ambiguous between them. If two definitions genuinely exist, name both explicitly
and let neither claim the bare word.

**Write `description` as if the reader has no context — because it will be an LLM.** Say what
the number means, what it excludes, and when not to use it: *"Sum of order amounts, gross.
Excludes cancelled orders only if the source view filters them — it does not."* Today only
humans read it; when the MCP server lands, this text is what the model sees.

**Point `count` at a non-null key.** See §4.

**Remember that `<>` and `NOT IN` drop NULLs.** Standard SQL three-valued logic: a row whose
`channel` is NULL matches neither `channel = 'web'` nor `channel <> 'web'`. The engine applies
what you wrote rather than second-guessing it, so if NULL should count as "not web", say
`channel IS NULL OR channel <> 'web'`.

**Prefer a database view to a clever model.** The model has no expressions on purpose. A view
is the sanctioned escape hatch.

**Never let a definition drift silently.** Changing what `revenue` means changes every past
answer's meaning. It is a reviewed diff, with the reason in the commit message — and per N6,
never something a tool applies automatically.

### A worked table, annotated

```yaml
tables:
  orders:
    source: orders.csv          # or: analytics.fct_orders — a view is fine, and often better
    dimensions:
      channel:                  # slice-by; becomes SELECT channel … GROUP BY channel
        column: channel
        type: string
        label: Sales channel
        description: How the order was placed — web, retail, or partner.
      order_date:
        column: order_date
        type: date              # declarative; no truncation exists yet
        label: Order date
    measures:
      revenue:
        column: amount
        agg: sum
        description: Sum of order amounts. The one sanctioned definition of revenue.
      order_count:
        column: order_id        # never null → counts rows, not non-nulls
        agg: count
        description: Number of order lines, not distinct orders.
      buyers:
        column: customer_id
        agg: count_distinct     # → COUNT(DISTINCT customer_id)
```

---

## 10. Changing a model safely

The model is in git precisely so a change is reviewable. A change to a `column` or an `agg`
is a change to what a number *means*, and every dashboard, chat answer, and slide built on it
changes with no other symptom.

Before merging a model change:

- [ ] `uv run semantiql "SELECT <the changed measure> FROM <table>" -m <model> --show-sql` —
      read the emitted SQL, not just the number.
- [ ] Check the number by hand, or against the previous value, and say in the commit message
      why it moved.
- [ ] For a renamed entity: every saved question using the old name now gets a refusal.
      That is the safe direction, but it is not free.
- [ ] For a changed `agg` or `column`: state the before/after definition in the commit
      message. A reviewer cannot see the semantics in a one-line diff.
- [ ] `./scripts/verify.sh` — the example model is also the test corpus
      (`tests/conftest.py`), so changing it moves the end-to-end assertions in
      `tests/test_example_end_to_end.py`, which are hand-computed on purpose.

Per constitution N6, the YAML tier is **always** human-reviewed: an automated loop may
propose a diff, never apply one. See [04-self-improvement.md](04-self-improvement.md).

---

## 11. Where the code is

| Concern | File |
|---|---|
| Field definitions, enums, the dimension/measure clash rule | `src/semantiql/knowledge/model.py` |
| Reading and validating the YAML, resolving relative sources | `src/semantiql/knowledge/loader.py` |
| Which requests resolve, and every refusal | `src/semantiql/engine/validate.py` |
| Measure → aggregation, dimension → `GROUP BY`, transpiling | `src/semantiql/engine/compile.py` |
| The single path from question to answer | `src/semantiql/engine/run.py` |
| How `source` becomes a relation | `src/semantiql/adapters/duckdb.py` |
| Loader failure messages, as tests | `tests/test_loader.py` |
| Compilation and refusal behaviour, as tests | `tests/test_compile.py`, `tests/test_validation_refuses.py` |

---

## Appendix A — SQL coverage map

Every table below was produced by running the construct through `engine/validate.py` against
the bundled retail model, not by reading the code. Recorded against **sqlglot 30.17.0**
(`pyproject.toml` pins `>=30,<31`); parser-shape behaviour can move between major versions.

Legend:

| | Meaning |
|---|---|
| ✅ | works today |
| ❌ | refused — the request is rejected and **the database is never reached** |

There is deliberately no third category. "Accepted, then quietly ignored" is the outcome this
engine is built to make impossible, and A.6 explains the rule that keeps that column empty.

A refusal is the designed answer, not a crash: the CLI prints `refused: …` to stderr and
exits `1`.

### A.1 Statements

Only `SELECT` survives. Everything else is refused by type, before any identifier is looked
at (`validate.py:138`) — this is how read-only (N5) is enforced on the default in-memory
path, where DuckDB cannot give a read-only connection.

| SQL | SemantiQL | Refusal says |
|---|---|---|
| `SELECT …` | ✅ | — |
| `SELECT …;` (one trailing semicolon) | ✅ | — |
| `INSERT` | ❌ | `Only SELECT is supported, and this is INSERT; the semantic layer is read-only.` |
| `UPDATE` | ❌ | `… this is UPDATE …` |
| `DELETE` | ❌ | `… this is DELETE …` |
| `MERGE` | ❌ | `… this is MERGE …` |
| `TRUNCATE TABLE` | ❌ | `… this is TRUNCATETABLE …` |
| `CREATE TABLE` / `CREATE VIEW` | ❌ | `… this is CREATE …` |
| `DROP` / `ALTER` | ❌ | `… this is DROP …` / `… this is ALTER …` |
| `GRANT` / `REVOKE` | ❌ | `… this is GRANT …` |
| `COPY` / `ATTACH` | ❌ | `… this is COPY …` / `… this is ATTACH …` |
| `SET` / `PRAGMA` | ❌ | `… this is SET …` / `… this is PRAGMA …` |
| `DESCRIBE` | ❌ | `… this is DESCRIBE …` |
| `EXPLAIN …` / `CALL …` | ❌ | `… this is COMMAND …` (sqlglot parses both as an opaque command) |
| two statements separated by `;` | ❌ | `… this is BLOCK …` — so `SELECT revenue FROM orders; DROP TABLE orders` is refused as a whole |
| a bare word, e.g. `hello` | ❌ | `'hello' does not look like a query. Semantic SQL looks like 'SELECT <measure>, <dimension> FROM <table>'.` |
| unparseable text | ❌ | `That is not parseable as semantic SQL: …` |

### A.2 Clauses and query shape

The compiler **rebuilds** the query from the model instead of rewriting your AST, so a clause
it does not implement would simply disappear. That is why these are refusals and not
warnings: a dropped `WHERE` returns a grand total that looks exactly like a filtered one.

| SQL clause | SemantiQL | How to get the effect today |
|---|---|---|
| `FROM <one model table>` | ✅ | — |
| `FROM main.orders`, `FROM orders AS o` | ✅ | catalog/schema prefix and table alias are ignored, not honoured |
| `WHERE` over dimensions | ✅ | `=` `<>` `<` `<=` `>` `>=` `IN` `NOT IN` `BETWEEN` `LIKE` `NOT LIKE` `IS NULL` `IS NOT NULL`, with `AND` `OR` `NOT` and parentheses. The dimension goes on the left; the other side is a literal |
| `WHERE` over a measure | ❌ | that is `HAVING` — refused, and the refusal says so |
| `GROUP BY` | ❌ | implicit: selecting a dimension groups by it |
| `HAVING` | ❌ | filter the returned rows in the caller |
| `ORDER BY` | ❌ | sort the returned rows in the caller |
| `LIMIT` / `OFFSET` | ❌ | slice the returned rows in the caller |
| `DISTINCT` (statement-level) | ❌ | use a `count_distinct` measure for distinct counting |
| `QUALIFY`, `WINDOW`, `OVER` | ❌ | not available |
| `WITH` (CTE) | ❌ | a database view |
| subquery in `FROM` | ❌ | `The FROM target must be a single table in the semantic model.` — a database view |
| `JOIN` (any kind), comma-join, `LATERAL` | ❌ | pre-join in a database view; one relation per model table |
| `UNION` / `UNION ALL` / `EXCEPT` / `INTERSECT` | ❌ | `Set operations (UNION, EXCEPT, INTERSECT) are not supported.` |
| `FOR UPDATE` and other locking clauses | ❌ | — |
| more than one table anywhere | ❌ | `Only a single semantic table is supported per request.` |
| `TABLESAMPLE` | ❌ | sample in the database and point `source` at the result |
| `PIVOT` / `UNPIVOT` | ❌ | pivot in the caller, or in a database view |
| `FROM ONLY t`, `WITH ORDINALITY` | ❌ | model the intended relation as its own `source` |
| `-- comment` | ✅ | ignored |

### A.3 SELECT-list forms

`_projections` (`validate.py:99`) admits exactly two shapes: a bare column reference, and a
column reference with an alias. Everything else is refused with
`each selected item must be a plain dimension or measure name, optionally aliased, but got …`.

| Written | SemantiQL | Note |
|---|---|---|
| `SELECT revenue` | ✅ | resolves to a measure |
| `SELECT channel` | ✅ | resolves to a dimension — but at least one measure is required |
| `SELECT revenue AS total` | ✅ | alias becomes the output column name |
| `SELECT "revenue"` | ✅ | quoting accepted |
| `SELECT orders.revenue` | ✅ | qualifier **ignored**; `SELECT bogus.revenue` is accepted too |
| `SELECT revenue, revenue` | ✅ | duplicates are not removed |
| `SELECT ALL revenue` | ✅ | `ALL` is a no-op |
| `SELECT *` | ❌ | `… but got '*'` |
| `SELECT orders.*` | ❌ | `'*' is not defined on table 'orders'.` |
| `SELECT amount` (a physical column) | ❌ | `'amount' is not defined on table 'orders'.` — only model names are addressable |
| `SELECT 1`, `SELECT 'x'`, `SELECT NULL` | ❌ | literals are not projections |
| `SELECT revenue + 1`, `revenue * 0.2` | ❌ | no arithmetic |
| `SELECT (SELECT 1)` | ❌ | no scalar subqueries |
| `SELECT …` with nothing | ❌ | `The request selects nothing.` |
| only dimensions, no measure | ❌ | `The request selects no measure, so there is no number to compute. Measures on 'orders': …` |

### A.4 Aggregate functions

Aggregation is chosen **in the model, by the modeller** — never in the query. `agg:` accepts
six values (`model.py:14`); the query names the measure, never the function.

| SQL aggregate | In the model | In a query |
|---|---|---|
| `SUM(x)` | ✅ `agg: sum` | ❌ — write the measure name |
| `COUNT(x)` | ✅ `agg: count` | ❌ |
| `COUNT(DISTINCT x)` | ✅ `agg: count_distinct` | ❌ |
| `MIN(x)` / `MAX(x)` | ✅ `agg: min` / `max` | ❌ |
| `AVG(x)` | ✅ `agg: avg` | ❌ |
| `COUNT(*)` | ❌ | ❌ — model `count` on a never-null key instead |
| `SUM(DISTINCT x)`, `AVG(DISTINCT x)` | ❌ | ❌ |
| `MEDIAN`, `MODE`, `QUANTILE`, `PERCENTILE_CONT/DISC` | ❌ | ❌ |
| `STDDEV`, `VARIANCE`, `CORR`, `REGR_*` | ❌ | ❌ |
| `STRING_AGG`, `ARRAY_AGG`, `LIST`, `ANY_VALUE`, `FIRST`, `LAST` | ❌ | ❌ |
| `APPROX_COUNT_DISTINCT`, `HLL` | ❌ | ❌ |
| `BOOL_AND`, `BOOL_OR`, `BIT_AND` | ❌ | ❌ |
| `agg FILTER (WHERE …)` | ❌ | ❌ |
| any window aggregate (`SUM(x) OVER (…)`) | ❌ | ❌ |

An unsupported `agg:` fails at load:
`agg: Input should be 'sum', 'count', 'count_distinct', 'min', 'max' or 'avg'`.

For anything in the lower half of that table: compute it in a database view, expose the
result as a column, and model a `sum`/`min`/`max` over it — accepting that the definition now
lives in the warehouse rather than in the diffable YAML.

### A.5 Scalar functions, expressions, and operators

**None are supported, in either place.** A `column:` in the model must be a plain column
name, and a projection must be a plain entity name — so there is no position in the system
where an expression can be written.

| Category | Examples | SemantiQL |
|---|---|---|
| Arithmetic | `+ - * /`, `%`, `POWER` | ❌ both places |
| Casting | `CAST(x AS INT)`, `x::INT`, `TRY_CAST` | ❌ |
| Conditionals | `CASE WHEN`, `IF`, `IFNULL`, `COALESCE`, `NULLIF` | ❌ |
| Date/time | `DATE_TRUNC`, `EXTRACT`, `DATE_PART`, `DATEDIFF`, `NOW()`, `CURRENT_DATE`, interval maths | ❌ — this is why `type: date` grants no time-grain ability |
| String | `UPPER`, `LOWER`, `CONCAT`, `SUBSTRING`, `TRIM`, `REPLACE`, `REGEXP_*` | ❌ |
| Numeric | `ROUND`, `ABS`, `FLOOR`, `CEIL` | ❌ |
| Comparison / predicates | `=`, `>`, `BETWEEN`, `IN`, `LIKE`, `IS NULL`, `AND`, `OR`, `NOT` | ✅ **inside `WHERE`**, against a dimension and a literal (A.2). Still ❌ anywhere else |
| JSON / struct / array access | `x->>'k'`, `x[1]`, `UNNEST` | ❌ |
| Window functions | `ROW_NUMBER`, `RANK`, `LAG`, `LEAD` | ❌ |

The single escape hatch is the same one throughout: **do it in a database view and point
`source` at the view.**

### A.6 Why the tables above have no "accepted but ignored" column

Refusal is decided by an **allowlist**, not by a list of known-bad clauses. `validate.py`
names the two things the compiler consumes:

- `_SELECT_ARGS` — the only arguments a `SELECT` may carry: its projection list and its
  `FROM`.
- `_FROM_NODE_ARGS` — the only node types the `FROM` subtree may contain (the table, the
  identifiers naming it, an optional alias) **and, per type, the only arguments each may
  carry**.

Anything else, anywhere in the request, is refused **because it is absent from those sets** —
not because someone remembered to forbid it. A construct nobody anticipated, in a position
nobody anticipated, in a representation nobody anticipated, fails closed.

The argument half of that rule is not decoration. sqlglot stores some constructs as a bare
flag rather than as a node — `FROM ONLY orders` is `only=True`, `WITH ORDINALITY` is
`ordinality=True` — so a check that walked expression nodes alone let both through. `ONLY`
excludes inheriting child tables on Postgres, so dropping it changes which rows exist. The
rule therefore generalises over *representation* as well as position.

That shape was chosen the hard way. The check used to be the inverse: a tuple of known-bad
clause names, tested against the `SELECT`'s own arguments. `TABLESAMPLE` and `PIVOT` were
both **listed by name in it** and both slipped through anyway, because sqlglot attaches
`sample` and `pivots` to the `Table` inside the `FROM` rather than to the `SELECT`. Both
requests validated, and the clause vanished from the compiled SQL — a caller who asked for a
10% sample received the full-table figure with no warning. That is the exact failure this
engine exists to prevent, and it survived in a list written specifically to prevent it (spec
`003-refuse-unimplemented-constructs`).

The lesson generalises past those two clauses. sqlglot parses all of SQL; this engine
implements a sliver of it; so a denylist has to enumerate an open-ended set *and* track where
the parser chooses to hang each node — two moving targets, and a check that silently stops
matching is worse than no check. An allowlist has to enumerate only what the compiler
already honours, which is a list the compiler's own authors must update anyway.

Filters follow the same rule one level in. `_PREDICATE_ARGS` lists the predicate nodes a
`WHERE` may contain and the arguments each may carry, and the validator turns them into a
neutral form — dimension name, operator, typed Python values — that the compiler rebuilds
from. Nothing the caller wrote reaches the database except escaped literal values, and a
predicate argument the builder does not read is a refusal rather than a drop. `IN (SELECT …)`
is refused that way, and so is any future flag sqlglot adds to a comparison node.

`where` joining `_SELECT_ARGS` in spec 004 is the rule working, not an exception to it: the
construct became answerable in the change that taught the compiler to honour it.

**The rule for contributors:** implementing a construct means adding it to the allowlist in
the same change that teaches `compile_request` to honour it. Adding it earlier reopens the
hole; the regression suite in `tests/test_validation_refuses.py` asserts that a refused
request never reaches the datasource, and includes a case for a construct deliberately absent
from every label map.
