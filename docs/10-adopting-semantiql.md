# Adopting SemantiQL for your own data

A task-by-task guide for pointing SemantiQL at a database you own. Every command and every
output below was captured from a real run against a real Postgres — nothing here is illustrative.

If you want the two-minute version against bundled sample data, use the README Quickstart. If
you want the *design* of the eventual setup flow, including the parts that are not built,
read [03-setup-workflow.md](03-setup-workflow.md). This document is the part that works today.

---

## Read this before you start

**Claude writes the semantic model; you review it.** There is no `semantiql init` wizard, and
there is something better: `semantiql inspect` reads your catalogue with no model required, and the
skill has Claude drive it — read the schema, ask you what the schema cannot say, write the YAML,
then loop on `semantiql doctor` until the model and the database agree. Your job is answering the
judgement questions and reading the diff. Writing it by hand still works, and [Step 3](#step-3--get-a-first-draft-of-the-model)
covers both.

**There is a Claude interface, and there is a limit to it.** `semantiql serve` runs an MCP
server, so you can ask questions in English through Claude Desktop rather than writing semantic
SQL — see [Step 7](#step-7--ask-through-claude-instead). The limit: the server runs **locally**,
so whoever chats needs SemantiQL installed and database access. That is fine for you and for
teammates who already query the database; it is not yet the non-technical colleague with no
credentials. That needs a remote server, which is deliberately post-MVP.

**Install from source, not from PyPI.** There is a published `semantiql` on PyPI, and at the time
of writing it is **behind this repository** — it predates both `semantiql doctor` and the Postgres
adapter, so `uvx semantiql doctor` answers *"doctor is not implemented yet"*. Until a newer
release is cut, clone the repo.

**One table at a time.** SemantiQL models a single relation per query — no joins. If your
question spans tables, create a database view that joins them and point the model at the view.
That is a deliberate design choice, not a gap; see [02-architecture.md](02-architecture.md).

---

## Step 1 — Install

```bash
git clone https://github.com/lethuan127/semantiql
cd semantiql
uv sync
```

Needs Python 3.11+ and [uv](https://docs.astral.sh/uv/). Confirm it works:

```bash
uv run semantiql "SELECT revenue, channel FROM orders"
```

That queries the bundled ten-row CSV example and needs no database at all. If it prints a table,
your install is good.

## Step 2 — Get a read-only account

Point SemantiQL at a **read-only** database user. Nothing in the query path needs write access,
and the engine refuses every non-`SELECT` statement, but a read-only account means that
guarantee does not rest on the software alone.

```sql
-- Postgres
CREATE USER semantiql_ro WITH PASSWORD '…';
GRANT CONNECT ON DATABASE yourdb TO semantiql_ro;
GRANT USAGE ON SCHEMA public TO semantiql_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO semantiql_ro;
```

Keep the password out of your shell history: omit `--dsn` entirely and let libpq read `PGHOST`,
`PGUSER`, `PGPASSWORD` and `~/.pgpass`, exactly as `psql` does.

## Step 3 — Get a first draft of the model

**The fast path is to let Claude write it.** Open Claude Code in the checkout, with the plugin
installed, and ask for a model for your database. It runs `semantiql inspect` to read your real
catalogue, asks you the few questions a schema cannot answer — which aggregation counts as revenue,
what a row is, which columns are sensitive — writes one YAML per table, and loops on `doctor` until
it passes. [03-setup-workflow.md §A3](03-setup-workflow.md) is that loop in detail.

The rest of this step is the same work done by hand. Read it anyway: reviewing what Claude wrote is
the one part of this you cannot delegate, and this is what you are reviewing.

Pick **one** table or view and describe it. Model the one thing you are asked about most and grow
from there — not because the engine cannot handle more, but because a model you have not verified
is worse than a small one you have.

When one file stops being reviewable, split it into a **directory** — one YAML per table, which is
what makes a per-table diff and per-team ownership possible. `-m` takes either. See
[09-data-modeling.md §2b](09-data-modeling.md) and the worked example in `examples/warehouse/`.

Three kinds of thing go in a model:

| | What it is | Example |
|---|---|---|
| **dimension** | something you group or filter by | `plan`, `country`, `signed_up` |
| **measure** | a number, and the *one* sanctioned way to aggregate it | `mrr` = `SUM(mrr_cents)` |
| **metric** | a number derived from measures | `mrr_per_customer` = `mrr / customers` |

Here is a real first draft, against a `subscriptions` table:

```yaml
version: 1

datasource:
  name: billing
  dialect: postgres

tables:
  subscriptions:
    source: subscriptions          # a table or view name

    dimensions:
      plan:
        column: plan
        type: string
      country:
        column: country
        type: string
      signed_up:
        column: signed_up_at
        type: date

    measures:
      mrr:
        column: mrr_cents
        agg: sum
      customers:
        column: id
        agg: count
      total_seats:
        column: seat               # <- a typo, on purpose
        agg: sum
```

The full field reference — every key, what it compiles to, and what is refused — is
[09-data-modeling.md](09-data-modeling.md). You do not need to read it before step 4.

## Step 4 — Run `doctor` and fix what it finds

Run it before you run a single query — and again whenever the database changes. Claude runs this
same command during discovery; running it yourself is how you confirm what it concluded:

```bash
uv run semantiql doctor -m model.yml \
  --datasource postgres --dsn postgresql://semantiql_ro@localhost/yourdb
```

```
✓ datasource 'billing' speaks postgres
subscriptions
  ✓ source 'subscriptions' has 7 columns
  ✗ dimension 'signed_up' reads column 'signed_up_at', which is timestamp with time zone — a time grain on it would bucket in the database server's timezone, so the answer changes on another host. Set `timezone:` to the zone the buckets belong to
  ✗ measure 'total_seats' reads column 'seat', which does not exist  (did you mean: seats, signed_up_at?)

1 table checked, 2 problems found.
```

Two real problems, and the second is the interesting one — see step 5. Fix them, re-run:

```
✓ datasource 'billing' speaks postgres
subscriptions
  ✓ source 'subscriptions' has 7 columns
  ✓ 3 dimensions, 3 measures and 0 metrics all resolve

1 table checked, no problems found.
```

`doctor` exits `0` when everything resolves and `1` when it does not, so put it in your setup
script and let a bad model stop the script rather than reach a user. It **never edits your
model** — fixes are yours to make.

## Step 5 — If your date column carries a timezone, say which one

This is the failure most likely to bite you silently, so it gets its own step.

If your date column is a plain `date` or a naive `timestamp`, skip this — there is nothing to do.
But if it stores an *instant with a zone* (`timestamptz`), then truncating it to a month has to
pick a timezone to draw the boundary in, and left alone the database picks **its own server
setting**. Here is that happening, same model, same five rows, same query — only the server's
timezone differs:

```
# no `timezone:` declared, server running in UTC
mrr     signed_up_month
------  -------------------
24000   2026-06-01 00:00:00
114000  2026-07-01 00:00:00
12000   2026-08-01 00:00:00

# no `timezone:` declared, server running in Asia/Tokyo
mrr     signed_up_month
------  -------------------
138000  2026-07-01 00:00:00
12000   2026-08-01 00:00:00
```

**June disappeared.** A customer who signed up at 22:00 UTC on 30 June is 05:00 on 1 July in
Tokyo, so their £24,000 moved into July and the June row stopped existing. No error, no warning,
and a perfectly reasonable-looking table.

Declaring the zone fixes it, and the answer stops depending on where the database happens to run:

```yaml
      signed_up:
        column: signed_up_at
        type: date
        timezone: UTC          # the zone month boundaries are drawn in
```

Choose the zone your business reports in — often UTC, often the headquarters timezone. There is
no default on purpose: "revenue by month in UTC" is a different question from "revenue by month
where the business operates", and guessing would answer one while looking like it answered the
other. `doctor` reports both mistakes: a zoned column with no declaration, and a declaration on a
column that has no zone.

## Step 6 — Ask questions

```bash
uv run semantiql "SELECT mrr, plan FROM subscriptions ORDER BY mrr DESC" \
  -m model.yml --datasource postgres --dsn postgresql://semantiql_ro@localhost/yourdb
```

```
mrr    plan
-----  -------
96000  scale
52000  team
2000   starter
```

You never write `GROUP BY` — naming a measure and a dimension together implies it. Add
`--show-sql` to see exactly what ran, which is how you check the work:

```bash
uv run semantiql "SELECT mrr, DATE_TRUNC('month', signed_up) FROM subscriptions" … --show-sql
```

```
-- SELECT SUM(mrr_cents) AS mrr, DATE_TRUNC('MONTH', signed_up_at AT TIME ZONE 'UTC') AS signed_up_month FROM subscriptions GROUP BY DATE_TRUNC('MONTH', signed_up_at AT TIME ZONE 'UTC')
mrr     signed_up_month
------  -------------------
24000   2026-06-01 00:00:00
114000  2026-07-01 00:00:00
12000   2026-08-01 00:00:00
```

Ask for something the model does not define and you get a refusal, not a guess:

```
$ uv run semantiql "SELECT profit FROM subscriptions" …
refused: 'profit' is not defined on table 'subscriptions'.
```

**That is the product working, not failing.** The whole design is that an unanswerable question
is refused rather than answered plausibly — a wrong number nobody can detect is the failure this
project exists to prevent.

## Step 7 — Ask through Claude instead

Once the model resolves, stop writing SQL yourself. Two routes, depending on your client.

**Claude Code — install the plugin.** `plugin/` in this repo carries the MCP server definition and
a skill that teaches Claude the dialect and what to do with a refusal. Point it at your model with
one environment variable:

```bash
export SEMANTIQL_MODEL=/absolute/path/to/model.yml
```

Nothing else to configure — the plugin locates this checkout through its own root, so it holds no
path from your machine. See [plugin/README.md](../plugin/README.md).

**Claude Desktop — build a bundle and open it.** Desktop takes a different packaging format from
Claude Code, so the plugin does not install there. Build one file instead:

```bash
uv run python scripts/build_bundle.py       # → dist/semantiql-<version>.mcpb
```

Open that file with Claude Desktop. It shows an install dialog: a **file picker** for your model, a
datasource, and a Postgres connection string in a field marked secret so the host stores it rather
than leaving it in a file. Nothing to paste, nothing to restart.

The bundle carries SemantiQL's own source, so it works on a machine that has never installed it —
and it is the file you send a colleague. See
[../bundle/README.md](../bundle/README.md).

You get the server without the skill; the server carries the essential guidance in its own
instructions, so this route works — it is just less well briefed than the plugin.

**Still debugging, or on another client?** `semantiql serve --print-config` prints the connector
block with every path resolved, to paste into `claude_desktop_config.json` by hand.

Then ask in English. Claude calls `describe_model` to learn your vocabulary, writes the semantic
SQL, and — this is the part worth watching — when it gets a refusal it reads the reason and
fixes its own query. Ask for something your model does not define and it tells you so instead of
inventing a number.

Note there is no password in that block. Postgres credentials stay in libpq's environment and
`~/.pgpass`, which is what keeps them out of a JSON file people paste into chat windows.

## Step 8 — Grow the model

Now add the things that make it worth having: a metric with one sanctioned definition, so
"revenue per customer" means the same thing to everyone who asks.

```yaml
    metrics:
      mrr_per_customer:
        expression: mrr / customers
        description: >-
          Computed after grouping, so per-plan figures use that plan's own MRR
          and its own customer count.
```

Metrics are checked when the model loads, and every divisor is guarded — a group with no
customers reports no value rather than an error or an infinity.

Re-run `doctor` after every change. Commit the model to git: it is a source-of-truth file, and
its diff is the audit trail of how your metric definitions changed.

---

## Exit codes

Useful for setup scripts:

| Code | Meaning |
|---|---|
| `0` | success |
| `1` | the request was **refused** — it cannot be answered from the model |
| `2` | the model file is missing or invalid |
| `3` | the datasource could not be reached, or rejected the SQL |

`1` and `3` are worth distinguishing: `1` means nothing is broken, the question was not
answerable; `3` means your connection or credentials are.

## What is not supported, and what to do instead

| Not supported | Do this instead |
|---|---|
| `JOIN` | create a database view that joins, point `source:` at the view |
| `HAVING` — filtering a measure | not available yet; filter on dimensions |
| `DISTINCT`, CTEs, subqueries, window functions | not available; the request is refused, never silently dropped |
| `MONTH(d)` / `EXTRACT(…)` | use `DATE_TRUNC('month', d)` — `MONTH()` returns the month *number*, so every July across every year collapses into one row |
| Multiple tables in one query | one table per query, by design |

Everything in that first column is **refused**, not ignored. That matters: a construct the
compiler silently dropped would change your question without telling you.

## Troubleshooting

**`error: could not connect to Postgres`** (exit 3) — the server, host, database or user is
wrong. The message repeats what to check. Try the same DSN with `psql` to isolate whether it is
SemantiQL or the connection.

**`'x' is not defined on table 'y'`** (exit 1) — you asked for something the model does not
declare. Run `doctor` to see what it does declare.

**A `.csv` source refused on Postgres** — file sources are a DuckDB feature. Load the file into a
table and point `source:` at the table.

**`refused: The semantic model declares datasource dialect 'duckdb', but the adapter in use is
'postgres'`** — you passed `--datasource postgres` against a model whose `datasource.dialect` is
`duckdb`. Fix whichever is wrong. This refusal exists so that pointing a model at the wrong
engine is loud rather than silently answered by the other one.

## Where to go next

- [09-data-modeling.md](09-data-modeling.md) — the complete model reference.
- [02-architecture.md](02-architecture.md) — why validation is the centrepiece.
- [05-datasources.md](05-datasources.md) — which databases are supported, and the roadmap.
- [03-setup-workflow.md](03-setup-workflow.md) — the same ground with both roles separated, and
  §A3 on the discovery loop in more detail than here.
