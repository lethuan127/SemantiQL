# What SemantiQL refuses, and what to write instead

A refusal is not a failure of the tool. It is the tool declining to answer with a number it cannot
verify, which is the property the whole system exists to provide. Every entry below is refused
*before* the database is reached.

## Constructs the compiler cannot rebuild

| You wrote | Why it is refused | Write instead |
|---|---|---|
| `HAVING revenue > 100` | filtering a measure needs an aggregate filter the compiler does not build | filter a dimension, or post-process the answer |
| `SELECT DISTINCT …` | grouping is implied by naming a dimension; `DISTINCT` would change the row set silently | name the dimensions you want |
| `WITH x AS (…)` | a CTE is a second query the model cannot validate | one table, one request |
| `SELECT … FROM a JOIN b` | joins are out of scope; a wrong join produces a plausible wrong number | a database **view**, modelled as one table |
| `FROM orders TABLESAMPLE …` | a sample answers a different question from the one asked | remove it |
| `PIVOT` / `UNPIVOT` | reshapes the result outside the model's vocabulary | group by the dimension instead |
| `SELECT (SELECT 1)` | a subquery is unvalidated SQL | one table, one request |
| `MONTH(order_date)` | extracts a number, so every July collapses into one row | `DATE_TRUNC('month', order_date)` |

## Identifiers

| Refusal | Meaning |
|---|---|
| `'x' is not a dimension, measure or metric of <table>` | the name is not in the model. The reply lists what is |
| `'x' is not selected by this request` | you ordered by something the answer does not show |
| `<table> is not a table in this model` | the reply lists the tables that are |

## Filters

`WHERE` compares a **dimension** to a **literal** whose type matches the dimension's declared `type`.
A filter on a measure is refused as needing `HAVING`. The predicate is rebuilt from the model rather
than copied, which is why an unsupported operator is refused rather than passed through.

## Ordering, limits

`ORDER BY` takes the name of something the request selects — a dimension, a measure, a metric, or a
grain's output name (`order_date_month`). A position (`ORDER BY 1`) is refused. `LIMIT` and `OFFSET`
take non-negative whole numbers.

## Time grains

Exactly five, and `DATE_TRUNC` is the only spelling. The grain truncates a cast column so the bucket
cannot depend on the database server's timezone; a dimension that declares `timezone:` is converted
first. Declaring `timezone:` on a column that carries no zone *moves* the buckets rather than pinning
them, and `doctor` checks both directions.
