---
name: semantiql
description: Answer questions about a business database through SemantiQL's semantic model, using the describe_model and query tools. Use whenever someone asks about company data — revenue, orders, customers, counts, totals, trends over time — or mentions a metric, dimension or semantic model. Also use when a query was refused and needs repairing.
---

# Asking SemantiQL

SemantiQL sits between you and a SQL database. You do not write SQL against tables; you write
**semantic SQL** against a reviewed model of the business, and SemantiQL validates it, compiles it,
and runs it.

The point of this arrangement is that **a wrong number is worse than no number**. The person
reading your answer usually cannot read SQL, so they cannot catch a mistake. When a question
cannot be answered from the model, say so — never estimate, never substitute a near-miss.

## Always start with `describe_model`

Call it before your first query in a conversation.

**With one table** you get everything: its **dimensions** (things to group or filter by),
**measures** (numbers) and **metrics** (numbers derived from measures), each with a `label` and a
`description`.

**With several tables** you get an index instead — each table's name, description, and how many
dimensions, measures and metrics it has. Pick the one the question is about and call again with
`table` set to its name:

```
describe_model()                    → orders (3 dimensions, 2 measures), tickets (2, 2)
describe_model(table="orders")      → the definitions
```

That is deliberate. A thirty-table model sent in full would fill the conversation with definitions
nobody asked for, and make it likelier that you pick a plausible-looking measure from a table the
question was never about. The reply tells you when to call again.

Those names are the only ones that exist. The labels and descriptions are how you map what the
person said — "sales channel", "revenue", "how many customers" — onto them. Read the descriptions:
they often carry the distinction that matters, like whether a count means orders or order lines.

If you name a table that does not exist, the reply lists the ones that do. Retry with one of those
rather than guessing again.

## Writing a query

```
SELECT <measures, metrics and dimensions> FROM <one table>
[WHERE <dimension> <operator> <literal> [AND ...]]
[ORDER BY <a name you selected> [DESC]]
[LIMIT n] [OFFSET n]
```

**Never write `GROUP BY`.** Naming a measure and a dimension together implies it. Writing it is
refused.

A worked example. Someone asks *"how did revenue split by channel last month?"*:

```sql
SELECT revenue, channel FROM orders
WHERE order_date >= '2026-07-01' AND order_date < '2026-08-01'
```

Grouping by a coarser period uses `DATE_TRUNC`:

```sql
SELECT revenue, DATE_TRUNC('month', order_date) FROM orders
```

Grains: `year`, `quarter`, `month`, `week`, `day`. Nothing else.

`MONTH(order_date)` and `EXTRACT(MONTH FROM order_date)` are **refused**, and the reason is worth
knowing: they return the month *number*, so July 2025 and July 2026 both become `7` and collapse
into one row. The total would be a real sum of real rows and still answer a different question.

### What is refused

One table per query. No `JOIN`, `HAVING`, `DISTINCT`, CTEs, subqueries, window functions,
`TABLESAMPLE` or `PIVOT`.

These are **refused, not ignored** — SemantiQL rebuilds the query from the model rather than
forwarding your text, so anything it does not understand would otherwise vanish and you would get
a confident answer to a different question.

Filtering on a measure needs `HAVING`, which is not supported. Filter on dimensions instead.

## When a query is refused

A refusal is a normal reply — `refused: true` with a `reason`. It is not a failure and not
something to apologise for. **Read the reason and fix the query.** It names what does not exist and
often suggests the right name:

```
refused: 'sales_channel' is not defined on table 'orders'.  (did you mean: channel?)
→ retry with `channel`
```

Retry once you understand the reason. Do not retry the same query, and do not guess a second name
without checking `describe_model`.

## When the model genuinely lacks something

If someone asks for a number the model does not define — `profit_margin` when only `revenue`,
`order_count` and `average_order_value` exist — then:

1. **Say it is not defined**, and name what *is* available.
2. **Stop.** Do not compute it from other columns, do not define it yourself, and do not offer an
   approximation.

This is the most important rule here, and it is the one most likely to feel unhelpful. It is not.
A semantic model exists so that "revenue" means one agreed thing across the company. The moment a
plausible definition can be invented in a conversation, that guarantee is gone — and the number
goes into a report looking exactly as authoritative as a real one.

Suggest that the person's data team add the definition. Changing the model is a reviewed change to
a file in git, deliberately, and never something to do mid-conversation.

## Presenting the answer

Give the number in plain language, with the grouping and any filter stated so the reader knows
what they are looking at. Values arrive as strings to preserve exact decimals — format them, do
not re-round them.

Every answer carries the physical SQL that ran. Offer it if someone asks how the number was
produced; do not volunteer it to a non-technical reader.

## Setup

The server needs to know which model to serve. Set `SEMANTIQL_MODEL` to an absolute path before
starting Claude:

```bash
export SEMANTIQL_MODEL=/path/to/your/model.yml
```

Without it the bundled ten-row retail example is served, which is useful for trying the tools and
is not anyone's data. If `describe_model` returns a table called `orders` with a `channel`
dimension and nothing else, that is what you are looking at — say so rather than answering
questions about it as though it were the company's.
