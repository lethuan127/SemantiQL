---
name: semantiql
description: Answer questions about a business database through SemantiQL's semantic model, using the describe_model and query tools, and build that model by inspecting a real database. Use whenever someone asks about company data — revenue, orders, customers, counts, totals, trends over time — or mentions a metric, dimension or semantic model. Also use when a query was refused and needs repairing, or when someone asks to create, generate, extend or fix a semantic model for a database.
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

## Building a model from a real database

When someone asks you to create or extend a model, you have a shell and file-writing tools. Use
them: **you** write the YAML. Do not ask the user to hand-write it, and do not invent a schema.

### The loop

**1. See what is actually there.**

```bash
semantiql inspect --datasource postgres --json          # the relations
semantiql inspect --table orders --json                  # one relation's columns
```

`inspect` needs no model — it is what runs before one exists. Every option the other verbs take for
choosing a datasource applies here too.

List first, then inspect only the relations you are going to model. A warehouse can have hundreds of
tables and pulling every column of every one into the conversation wastes the context you need for
the actual work.

**2. Propose a shortlist and stop.** Say which relations look like the core and why, and ask which
matter. Do not model everything you found; the user knows which tables the business actually asks
about, and you do not.

**3. Ask the questions a schema cannot answer.** This is the part that needs the human, and it is
the reason this is a conversation rather than a command:

- **Which aggregation is the sanctioned one?** `amount` could be `sum`, `avg` or `max`, and they are
  three different business figures. Ask; never pick.
- **What is a row?** "One row per order line, not per order" changes what every count means. Put the
  answer in the table's `description`.
- **Which columns are sensitive?** Ask. Do not guess at PII from column names — a confident wrong
  answer here is a leak.
- **For any `timestamptz` column, which timezone do months belong to?** `inspect` tells you which
  columns carry a zone. The answer is a business decision — often UTC, often headquarters — and
  getting it wrong moves revenue between months. See the timezone section above.
- **What do people actually call these things?** The column is `amt_net_ex_vat`; the business says
  "revenue". Your `label` and `description` are what make that mapping work later.

**4. Write the files.** One YAML per table, in a directory, with `datasource` declared once:

```
model/
├── datasource.yml
├── orders.yml
└── customers.yml
```

One file per table means a later change is a small diff in an obvious place, and adding a table is a
new file rather than a rewrite. Use the types `inspect` reported under `semantiql_type` — they are
already in the model's vocabulary.

**5. Check what you wrote, and fix it.**

```bash
semantiql doctor -m model/
```

`doctor` compares your files against the real schema and names every disagreement — a column that
does not exist, a `type:` that contradicts reality, an aggregation the column cannot take, a missing
or misplaced `timezone:`. Fix and re-run until it exits 0. Do not stop before that: a model `doctor`
rejects will produce refusals in chat that read like a broken product.

**6. Show the user what you wrote** and let them read it before it is committed. They are files in
their working tree, and the whole point is that the definitions are theirs.

### Limits on this, and they are not negotiable

**Never invent a measure's aggregation or a metric's formula.** If you cannot get an answer, leave
it out and say what is missing. A model with three measures the user chose is worth more than ten
you guessed, because every guess becomes a number someone trusts.

**Never change a model to answer a question.** Discovery is a task the user asked for, with them
present. Mid-conversation, if a question needs a metric that does not exist, say so and stop — do not
add it and answer. The difference is that one is a reviewed change and the other is a definition
nobody approved becoming an authoritative figure.

**Leave the model alone unless asked.** Being asked "revenue by channel?" is not permission to
restructure the model.

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
