---
name: semantiql
description: Answer questions about a business database through SemantiQL's reviewed semantic model, using the read-only describe_model and query tools, and build that model by inspecting a real database. Use whenever someone asks about company data — revenue, orders, customers, counts, totals, trends over time — or names a metric, dimension or semantic model. Use proactively when building a model for a new datasource, when creating or extending dimensions, measures and metrics, when debugging a query SemantiQL refused, for repairing a model that doctor rejects, and when deciding what a business word like revenue should mean. Triggers when a question needs a number from a database rather than from a file, and automatically when a refusal needs reading and repairing.
---

# Asking SemantiQL

SemantiQL sits between you and a SQL database. You do not write SQL against tables; you write
**semantic SQL** against a reviewed model of the business, and SemantiQL validates it, compiles it,
and runs it.

The point of this arrangement is that **a wrong number is worse than no number**. The person
reading your answer usually cannot read SQL, so they cannot catch a mistake. When a question
cannot be answered from the model, say so — never estimate, never substitute a near-miss.

## What you can do, and what you get back

**Your contract is small.** One request in, one answer out. You call two read-only tools and return a
number with its labels; you do not manage other agents, spawn subtasks, or own a pipeline. Everything
below is what to send those two tools and how to read what comes back.

**Two tools, both read-only.** `describe_model` returns the vocabulary — tables, dimensions, measures,
metrics, each with a label and description; with several tables it returns an index and you call again
for one table's detail. `query` accepts one string of semantic SQL and returns column names, rows, and
the physical SQL that ran — **or a refusal carrying its reason, which is a normal answer, not an
error.** Read the reason and repair the query.

Report values as the answer produced them. They arrive as strings to keep decimals exact: format them
for a reader, never re-round them.

**In scope, and deliberately not:**

| Supported | Refused, and what to do instead |
|---|---|
| one table per query | joins → model a database **view** as one table |
| measures, metrics, dimensions by name | `HAVING`, filtering a measure → filter a dimension |
| `WHERE <dimension> <op> <literal>` | `DISTINCT`, CTEs, subqueries, `PIVOT` → use the subset below |
| `ORDER BY` a selected name, `LIMIT`, `OFFSET` | `ORDER BY 1` → order by a name you selected |
| `DATE_TRUNC('<grain>', <date dimension>)` | `MONTH()` / `EXTRACT` → they collapse every July into one row |

**Two limits that are never negotiable.** Never invent a measure's aggregation or a metric's formula —
if you cannot get an answer, say what is missing. And never change a model to answer a question: a
missing definition is reported, and adding it is a reviewed change to a file in git.

**Three requests, and exactly what you should return:**

| They ask | You send `query` | You reply |
|---|---|---|
| "revenue by channel last quarter" | `SELECT revenue, channel FROM orders WHERE order_date >= '2026-04-01'` | *Web £18,400.00, store £9,120.00.* Figures and labels, no SQL |
| "revenue by sales region" | nothing — `describe_model` lists no `region` | *Your model defines revenue by channel, order_date and customer_segment. There is no region. Adding one is a reviewed change — want me to open it?* |
| "revenue by month this year" | `SELECT revenue, DATE_TRUNC('month', order_date) FROM orders ORDER BY order_date_month` | the monthly series, in month order, labelled by month |

The middle row is the one that matters. **Reporting the gap is the correct answer**, and it beats
substituting `channel` because that is also a grouping. Never volunteer the SQL unless asked: the
person reading usually cannot check it, which is the whole reason this layer exists.

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

### First, work out how to run the CLI

Do this once, before step 1. **`semantiql` is usually not on `PATH`.** The documented setup is a git
checkout plus `uv sync`, which puts the executable inside that project's own virtualenv, so the bare
command fails with `command not found` — inside the checkout as much as outside it.

```bash
uv run --project "$SEMANTIQL_HOME" semantiql --help   # a checkout: the common case
semantiql --help                                     # installed as a tool: bare works
```

Run one, and use whichever answered for every command below.

**Write it out in full each time.** Each Bash call is its own shell, so assigning it to a variable
once looks tidy and then silently expands to nothing on the next call — which reads as a broken CLI
rather than a broken variable.

If neither form works, `$SEMANTIQL_HOME` is unset. **Ask where the SemantiQL checkout is**; do not
guess at a path or go hunting through the filesystem.

`--project` and not `--directory`: both find the checkout, but `--directory` **moves** there, so
`-m model/` and `--database ./shop.duckdb` would resolve against SemantiQL's own tree instead of the
user's. `--project` leaves you where you are, which is what every relative path below assumes.

The examples below use the checkout form, since that is what a builder following the setup workflow
has.

### The loop

**1. See what is actually there.**

```bash
uv run --project "$SEMANTIQL_HOME" semantiql inspect --json                 # the relations
uv run --project "$SEMANTIQL_HOME" semantiql inspect --table orders --json  # one relation's columns
```

`inspect` needs no model — it is what runs before one exists. Every option the other verbs take for
choosing a datasource applies here too; DuckDB is the default, so add `--datasource postgres` only
when that is what you are pointed at.

List first, then inspect only the relations you are going to model. A warehouse can have hundreds of
tables and pulling every column of every one into the conversation wastes the context you need for
the actual work.

**2. Propose a shortlist and stop.** Say which relations look like the core and why, and ask which
matter. Do not model everything you found; the user knows which tables the business actually asks
about, and you do not.

**2b. Look at what is actually in the columns.**

```bash
uv run --project "$SEMANTIQL_HOME" semantiql profile --table orders --json
```

`profile` reads the rows and reports, per column: nulls, distinct count, min/max, the **sum** of a
numeric column, and the **value distribution** of any low-cardinality column. `inspect` tells you a
column exists; this tells you what is in it.

Two things it gives you that types never will:

- **Which of five money columns is worth what.** On a real dataset `fare_amount` summed to $53.9M and
  `total_amount` to $79.5M. That is the difference between two defensible definitions of revenue, and
  quoting it is what lets a non-technical analyst actually answer step 3's first question.
- **Which numeric columns are secretly categories.** `payment_type` is `bigint` on every engine and a
  category in truth. `profile` shows `1(2,319,046) 2(439,191) 0(140,162)` — six values, so it is a
  code, and a model that groups by it produces a chart labelled 1, 2, 3 unless you do something about
  it.

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

**4. Write the files.** One YAML per table, in a directory, with `datasource` declared once. This is
the shape, with the fields that carry meaning filled in from what the analyst told you:

```yaml
tables:
  order_lines:
    source: order_lines
    description: >-
      One row per order line, not per order. Counting rows counts products sold; use
      order_count for orders.
    dimensions:
      channel:
        column: channel
        type: string
        label: Sales channel
        description: How the order was placed — web or store.
    measures:
      revenue:
        column: net_amount
        agg: sum
        label: Revenue
        description: >-
          Gross less discounts and refunds, as confirmed by the analyst. Excludes tax.
      order_count:
        column: order_id
        agg: count_distinct
        label: Orders
        description: Distinct orders. Distinct because one order can span several lines.
    metrics:
      average_order_value:
        expression: revenue / order_count
```

The directory layout:

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
uv run --project "$SEMANTIQL_HOME" semantiql doctor -m model/
```

`doctor` compares your files against the real schema and names every disagreement — a column that
does not exist, a `type:` that contradicts reality, an aggregation the column cannot take, a missing
or misplaced `timezone:`. Fix and re-run until it exits 0. Do not stop before that: a model `doctor`
rejects will produce refusals in chat that read like a broken product.

**6. Show the user what you wrote** and let them read it before it is committed. They are files in
their working tree, and the whole point is that the definitions are theirs.

### Limits on this, and they are not negotiable

**Never run SQL against the database yourself.** Not `psql`, not the `duckdb` CLI, not a Python
client, not a query through any other tool. Everything you need is `inspect` (what exists), `profile`
(what is in it) and `doctor` (whether the model matches). Those go through SemantiQL, which means the
figures you quote to a human came from a path someone reviewed — and a number that decides what
"revenue" means is exactly the number that must not come from improvised SQL. This is not a style
preference: a run once read every figure it presented with twelve raw `psql` calls, and the numbers
were right by luck rather than by construction.

**Never write to the database.** No `CREATE`, no `INSERT`, no `UPDATE`, no DDL of any kind. If the
model needs a database object — a view to label a coded column, or to expose a join the engine
refuses — **print the SQL and ask the analyst to run it**. It is their database, the object outlives
the conversation, and something the model depends on should be created deliberately by its owner.

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

## When to use which verb

Four commands, and picking the wrong one is the difference between a cheap question and a full table
scan. All of them are run as `uv run --project "$SEMANTIQL_HOME" semantiql …`.

| Verb | Reads | Needs a model | Use it when |
|---|---|---|---|
| `inspect` | catalogue metadata, no rows | no | you need to know what relations and columns exist |
| `profile` | every row of one relation | no | you need the numbers that decide a definition |
| `doctor` | catalogue metadata | yes | you have written a model and need it checked against reality |
| the MCP `query` tool | the rows the question needs | yes | answering a question, which is the only time |

The comparison that matters: `inspect` is the cheap one and answers *what exists*; `profile` is the
expensive one and answers *what is in it*. Do not reach for `profile` on a whole warehouse, and do not
try to answer a definition question from `inspect` alone.

## Input and output format

**What the tools accept.** `describe_model` accepts an optional `table` name and nothing else.
`query` accepts one string of semantic SQL — the supported subset described above — and no other
parameters. There is no way to pass raw SQL, a connection string, or a model path through either.

**What they return.** `describe_model` returns the tables, dimensions, measures and metrics with their
labels and descriptions; with several tables it returns an index and you call again for one table's
detail. `query` returns column names, rows, and the physical SQL that produced them — or a refusal
carrying its reason, which is a normal answer and not an error.

Report the values as the answer produces them. They arrive as strings to preserve exact decimals, so
format them for a reader if you like, but never re-round them: a figure that has been rounded twice is
a figure nobody can reconcile against the database.

## Examples

Three walkthroughs. Each is a real shape of request, not an illustration.

### A question the model can answer

> *"What was revenue by channel last quarter?"*

| Step | What you do |
|---|---|
| 1 | `describe_model()` — learn the vocabulary before writing anything |
| 2 | See `revenue` (measure), `channel` and `order_date` (dimensions) |
| 3 | Write the query below |
| 4 | Report the number, and the labels — not the SQL |

```sql
SELECT revenue, channel
FROM orders
WHERE order_date >= '2026-04-01' AND order_date < '2026-07-01'
ORDER BY revenue DESC
```

### A question the model cannot answer

> *"What was revenue by sales region?"*

`describe_model` lists no `region`. **Report that and stop.** Do not substitute `channel` because it
is also a grouping, and do not add a `region` dimension to make the question work — that is a change
to what a number means, and it belongs in a reviewed pull request rather than in a chat reply.

```
Your model has no region dimension. Revenue is defined by channel, order_date and
customer_segment. Adding region means editing the model, which is a reviewed change —
want me to open one?
```

### A refusal you can repair

A refusal is a normal answer carrying its reason. Read the reason before changing anything.

| Refusal says | What it means | The repair |
|---|---|---|
| `'revenu' is not selected by this request` | a typo, and the reply lists the real names | use the suggested name |
| `ORDER BY takes the name of something this request selects` | you ordered by a function or a position | order by a selected name; the message lists them |
| `HAVING is not supported` | you filtered a measure | filter a dimension, or aggregate differently |
| `each selected item must be a plain dimension or measure name` | you wrote SQL the compiler cannot rebuild | use the supported subset above |

## Troubleshooting

Every row here was hit for real while building or testing this plugin.

| Symptom | Cause | Fix |
|---|---|---|
| `command not found: semantiql` | the executable lives in the checkout's virtualenv, not on `PATH` | `uv run --project "$SEMANTIQL_HOME" semantiql …` |
| `$SEMANTIQL_HOME` is empty | the variable was never exported before Claude started | ask the user where the checkout is; do not guess a path |
| `relation "orders_v" does not exist` | the model points at a database **view** that has been dropped or was never created | recreate the view, or point the model at the base table |
| `doctor` reports a column that is not there | the model was written against a different schema than the one you are connected to | re-run `semantiql inspect --table <name>` and reconcile |
| `doctor` reports a timezone mismatch | `timezone:` is declared on a column that carries no zone, or missing from one that does | `inspect` reports `carries a timezone`; match it |
| every month collapses into one row | `EXTRACT`/`MONTH()` was used instead of `DATE_TRUNC` | `DATE_TRUNC('month', <date dimension>)` |
| a monthly series comes back unsorted | ordering by the grain expression was refused in an older build | `ORDER BY <dimension>_<grain>`, e.g. `order_date_month` |
| the numbers look plausible but wrong | a measure's `agg` or a metric's formula was guessed rather than confirmed | stop, and ask which definition is sanctioned |

| a figure differs from the analyst's own report | the model's definition is not the one their report uses | show the definition and ask which is sanctioned |
| `profile` is slow on a huge table | it aggregates every row, by design | profile the one relation you are modelling, not the warehouse |

**When `doctor` and the query disagree, trust `doctor`.** It compares the model against the real
schema. A query that runs against a model `doctor` rejects is answering from a definition nobody
checked.

## Related

Reference material lives beside this file, so it is here when you need it and not in the context when
you do not:

| File | Read it when |
|---|---|
| [references/refusals.md](references/refusals.md) | a query was refused and the message is not enough |
| [references/model-fields.md](references/model-fields.md) | writing or reviewing a model's YAML |
| [assets/datasource.template.yml](assets/datasource.template.yml) and [assets/table.template.yml](assets/table.template.yml) | starting a model directory from scratch |

See also, in the SemantiQL repository itself: `docs/09-data-modeling.md` for the complete field
reference, `docs/03-setup-workflow.md` for the setup flow this skill sits inside, and
`docs/02-architecture.md` for why the tool surface is two read-only tools.
