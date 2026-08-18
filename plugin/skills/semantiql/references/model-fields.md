# Semantic model fields, in brief

The authoritative reference is `docs/09-data-modeling.md` in the SemantiQL repository. This is the
subset you need while writing one.

## Shape

```yaml
version: 1

datasource:
  name: shop            # a label for the connection
  dialect: duckdb       # duckdb | postgres — must match how it is run

tables:
  orders:
    source: orders      # a table, a view, or on DuckDB a .csv/.parquet path
    description: >-
      One row per order line, not per order. Say what a row *is*, and name the trap.
    dimensions: {}
    measures: {}
    metrics: {}
```

A model may be one file, or a **directory** of files with `datasource` declared exactly once. One
file per table keeps a change a small diff in an obvious place.

## Dimensions — things you group or filter by

| Field | Meaning |
|---|---|
| `column` | the physical column |
| `type` | `string`, `date`, `number`, `boolean`. Decides which literals may filter it |
| `label` | what a person calls it. Read by `describe_model`, so it is how a question maps onto the model |
| `description` | the distinction that matters. Worth more than the label |
| `timezone` | IANA name, **only** for a column that carries a zone. Omit otherwise |

## Measures — a number and its one sanctioned aggregation

| Field | Meaning |
|---|---|
| `column` | the physical column |
| `agg` | `sum`, `count`, `count_distinct`, `min`, `max`, `avg` |
| `label`, `description` | as above. Say what is *excluded*, not only what is included |

`count_distinct` is the answer whenever the table's grain is finer than the thing being counted —
counting rows in a per-line table overstates orders.

## Metrics — derived from this table's measures

```yaml
metrics:
  revenue_per_order:
    expression: revenue / order_count
```

The grammar is closed: measure names, numbers, `+ - * /`, unary minus, parentheses. No aggregates
(the measure already carries one), no comparisons, no functions, no `CASE`. Checked when the model
loads, so a typo in a metric nobody has queried is still an error you see immediately.

## What the model deliberately cannot say

No joins, no row-level security, no filtered measures. A view is the escape hatch for the first; the
other two are not built. If a question needs one, say so rather than approximating it.
