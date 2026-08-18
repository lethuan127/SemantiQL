# Setup workflow

Two roles, two flows. **Flow A** is the analyst who owns the semantic model, done once. **Flow B**
is everyone who asks questions, done per person.

Every command and output below was captured from a real run. Where a step is not built, it says so
rather than describing it as though it works — the difference matters, because a reader following
this document is standing at a terminal.

---

## Flow A — Builder (data analyst, done once)

Target: **≤ 15 minutes**, every step checked, every error carrying its fix.

### A1. Install

```bash
git clone https://github.com/lethuan127/semantiql
cd semantiql
uv sync
```

Needs Python 3.11+ and [uv](https://docs.astral.sh/uv/). Confirm it works against the bundled
ten-row example, which needs no database:

```bash
uv run semantiql "SELECT revenue, channel FROM orders"
```

> **Not `uvx semantiql`.** The published package is behind this repository — it predates both
> `semantiql doctor` and the Postgres adapter, so `uvx semantiql doctor` answers *"doctor is not
> implemented yet"*. Install from source until a newer release is cut.

### A2. Create a read-only database account

Nothing in the query path needs write access, and the engine refuses every non-`SELECT`. A
read-only account means that guarantee does not rest on the software alone.

```sql
-- Postgres
CREATE USER semantiql_ro WITH PASSWORD '…';
GRANT CONNECT ON DATABASE yourdb TO semantiql_ro;
GRANT USAGE  ON SCHEMA public    TO semantiql_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO semantiql_ro;
```

Keep the password out of your shell history and out of any file you paste around: omit `--dsn`
and let libpq read `PGHOST`, `PGUSER`, `PGPASSWORD` and `~/.pgpass`, exactly as `psql` does.

### A3. Write the first draft of the model

> **This is the step that is not automated.** `semantiql init` — a wizard that introspects the
> schema and drafts the YAML — is **not built**. What replaces it is A4's correct-the-errors loop,
> which turns model-writing from guesswork into a short conversation with `doctor`. You still
> write the first draft.

Pick **one** table or view. Modelling a whole warehouse before verifying any of it is how a
fifteen-minute setup becomes an afternoon.

```yaml
version: 1

datasource:
  name: shop
  dialect: duckdb          # must match --datasource when you run it

tables:
  orders:
    source: orders                # a table or view name; a .csv/.parquet path works on DuckDB
    description: One row per order line, not per order.

    dimensions:                   # things to group or filter by
      channel:    {column: channel, type: string}
      order_date: {column: order_date, type: date}

    measures:                     # numbers, each with one sanctioned aggregation
      revenue:     {column: amount,   agg: sum,   label: Revenue}
      order_count: {column: order_id, agg: count, label: Orders}

    metrics:                      # numbers derived from measures
      revenue_per_order: {expression: revenue / order_count}
```

**Write the `label` and `description` fields.** They are not decoration: `describe_model` sends
them to Claude, and they are how it maps "sales channel" in a question onto `channel` in your
model. A description that names the trap — *"one row per order line, not per order"* — prevents a
whole class of wrong answer.

The complete field reference is [09-data-modeling.md](09-data-modeling.md).

**When one file stops being reviewable, use a directory** — one YAML per table, `datasource`
declared once, subdirectories allowed. `-m` takes either. See
[09-data-modeling.md §2b](09-data-modeling.md) and the worked example in `examples/warehouse/`.

### A4. Run `doctor` until it exits 0

This is the loop that stands in for the missing wizard. Run it before you run a single query.

```bash
uv run semantiql doctor -m model.yml \
  --datasource postgres --dsn postgresql://semantiql_ro@localhost/yourdb
```

A first draft usually looks like this:

```
✓ datasource 'shop' speaks duckdb
orders
  ✓ source '/…/orders.csv' has 5 columns
  ✗ dimension 'channel' reads column 'chanel', which does not exist  (did you mean: channel?)
  ✗ dimension 'order_date' is declared string, but column 'order_date' is DATE — filters on it will be typed wrongly
  ✗ measure 'volume' applies sum to column 'channel', which is VARCHAR — the database will reject that when asked

1 table checked, 3 problems found.
```

Fix and re-run until:

```
✓ datasource 'shop' speaks duckdb
orders
  ✓ source '/…/orders.csv' has 5 columns
  ✓ 3 dimensions, 2 measures and 1 metric all resolve

1 table checked, no problems found.
```

**Exit codes make this scriptable:** `0` when everything resolves, `1` when it does not. Put it in
your setup script and let a bad model stop the script rather than reach a user.

`doctor` **never edits your model.** Fixes are yours to make, per the two-tier rule in
[04-self-improvement.md](04-self-improvement.md).

#### What `doctor` checks

| Check | Catches |
|---|---|
| `source` is readable | a table or path that does not exist |
| every `column` exists | typos, with a suggestion |
| `type:` matches the real column | a `date` declared `string`, which types filters wrongly |
| the aggregation is possible | `sum` over text, which the database would reject |
| dialect matches the adapter | a DuckDB model pointed at Postgres |
| timezone declarations | see A5 — both directions |

#### What it does not do yet

Run sample questions and confirm the *answers*. `doctor` verifies the model fits the database, not
that it answers well. The MCP server exists now, so the pieces are there — a `doctor --ask` that
puts a few questions through it is the remaining step, and it is **not built**.

### A5. If a date column carries a timezone, declare it

Skip this if your date columns are `date` or naive `timestamp`. It matters only for `timestamptz`.

Truncating an instant to a month has to pick a timezone, and left alone **the database picks its
own server setting**. Same model, same rows, same query, two servers:

```
# no `timezone:` declared, server in UTC     # no `timezone:` declared, server in Asia/Tokyo
24000   2026-06-01                            138000  2026-07-01
114000  2026-07-01                            12000   2026-08-01
12000   2026-08-01
```

**June disappeared.** A customer who signed up at 22:00 UTC on 30 June is 05:00 on 1 July in Tokyo,
so their revenue moved month and the June row stopped existing. No error, no warning.

```yaml
      signed_up:
        column: signed_up_at
        type: date
        timezone: UTC          # the zone month boundaries are drawn in
```

There is no default on purpose: *"revenue by month in UTC"* is a different question from *"revenue
by month where the business operates"*. `doctor` reports both mistakes — a zoned column with no
declaration, **and** a declaration on a column that has no zone, which *moves* the buckets rather
than pinning them.

### A6. Ask a question from the terminal

Before involving Claude, confirm the numbers yourself.

```bash
uv run semantiql "SELECT revenue, channel FROM orders" -m model.yml --show-sql
```

```
-- SELECT SUM(amount) AS revenue, channel AS channel FROM orders GROUP BY channel
revenue  channel
-------  -------
385.25   partner
956.5    web
344.49   retail
```

You never write `GROUP BY` — naming a measure and a dimension together implies it. `--show-sql`
prints what actually ran, which is how you check the work.

Ask for something the model does not define and you get a refusal, not a guess:

```
$ uv run semantiql "SELECT profit FROM orders" -m model.yml
refused: 'profit' is not defined on table 'orders'.        # exit 1
```

**That is the product working.** Exit codes: `0` success · `1` refused, the question is not
answerable · `2` the model is missing or invalid · `3` the datasource is unreachable. `1` and `3`
are worth distinguishing in a script: one means nothing is broken, the other means your connection
is.

### A7. Hand it to Claude

Two routes, depending on the client.

**Claude Code — install the plugin.** `plugin/` registers the MCP server *and* a skill that teaches
Claude the dialect, how to repair a refusal, and to stop rather than invent a definition. It needs
two variables, because a plugin carries configuration rather than a Python environment:

```bash
export SEMANTIQL_HOME=$PWD                          # this checkout
export SEMANTIQL_MODEL=/absolute/path/to/model.yml  # or a model directory
```

**Claude Desktop — build a bundle and send it.** One file the recipient opens:

```bash
uv run python scripts/build_bundle.py
# → dist/semantiql-0.0.2.mcpb  (50 KB)
```

**Debugging, or another client — print the connector block.** Every path already absolute:

```bash
uv run semantiql serve -m model.yml --print-config
```

```json
{
  "mcpServers": {
    "semantiql": {
      "command": "/…/.venv/bin/python3",
      "args": ["-m", "semantiql", "serve", "-m", "/…/model.yml", "--datasource", "duckdb"]
    }
  }
}
```

Paste into `claude_desktop_config.json` (`~/Library/Application Support/Claude/` on macOS,
`%APPDATA%\Claude\` on Windows) and restart Claude Desktop fully.

### A8. Confirm the connector appears

A **semantiql** connector with two tools, `describe_model` and `query`, both marked read-only. That
is the whole surface: no shell, no arbitrary SQL, no write path.

If it does not appear, the usual causes are a relative path in the config block (which is why
`--print-config` resolves them) and a model that fails to load — `serve` exits `2` for a bad model
and `3` for an unreachable datasource, **before** accepting a request, so a server that started can
answer. Claude Desktop's logs are at `~/Library/Logs/Claude/mcp*.log`.

---

## Flow B — End user (per person)

### B1. Install

**From a bundle:** open the `.mcpb` file. Claude Desktop shows an install dialog — a file picker
for the model, a datasource, and a Postgres connection string in a field marked secret so the host
stores it rather than leaving it in a file. No config file, no restart ceremony.

**From a connector block:** paste what the builder sent into `claude_desktop_config.json` and
restart.

### B2. Ask

```
You:     What was revenue by channel last month?

Claude:  [describe_model]  → revenue, order_count, channel, order_date
         [query]           → SELECT revenue, channel FROM orders
                              WHERE order_date >= '2026-07-01' AND order_date < '2026-08-01'

         July revenue by channel: web 826.50 · partner 385.25 · retail 279.99
```

The interesting case is the one that protects you:

```
You:     What's our profit margin?

Claude:  [query] → refused: 'profit_margin' is not defined on table 'orders'

         Your semantic model doesn't define profit margin — it has revenue, order_count
         and average_order_value. Ask your data team to add it.
```

No guess, no invented `SUM`, no plausible wrong number. And when the miss is a near-miss, Claude
reads the reason and fixes its own query rather than asking you to rephrase.

### The honest limit

A **local** server runs on the end user's own machine, so that machine needs SemantiQL installed
and database access. Flow B works today for an analyst or a teammate who already queries the
database. It is **not yet** the non-technical colleague with no credentials — that needs remote
mode, below.

---

## Design principles

- Flow A completes in **≤ 15 minutes**; every step has an automated check, and every error carries
  its fix.
- **Read-only by default**, at both layers: a read-only account, and an engine that refuses every
  non-`SELECT`.
- The semantic model is **YAML in git** — one file, or a directory of them once one file stops
  being reviewable. Diffable, reviewable, and the only source of truth.
- **Refusing beats guessing.** An unanswerable question returns a reason, never a plausible number.
- End users **never** touch a connection string or YAML. The bundle's install dialog is what makes
  that literally true rather than aspirational.

## Open questions

- **Local vs remote MCP server:** local (runs on each person's machine) is simple for the MVP but
  forces the end user's machine to connect directly to the database — wrong fit for non-technical
  users. Remote (shared server, users add a connector URL) is the right model but adds hosting and
  auth. → **MVP goes local first, designed with a clear path to remote.**
- **Auth and permissions when several users share one server** — belongs to the Data Governance
  layer; post-MVP.
- **`semantiql init`** — A3 is the only manual step left in Flow A, and the one that costs the most
  minutes. It should introspect the schema and write dimensions; measures and metrics need
  judgement and stay human.
