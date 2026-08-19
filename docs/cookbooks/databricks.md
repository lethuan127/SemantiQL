# Cookbook — SemantiQL on Databricks

**Read this first: the workspace steps below have not been run.** No Databricks workspace exists on the
machine this was written on, so steps 4 to 7 show the commands and *not* their captured output — unlike
[postgres.md](postgres.md), where every figure came out of a terminal.

What *has* been captured is marked as such: the install, the credential refusals, and the physical SQL
SemantiQL emits for a Databricks model, which can be produced without connecting to anything. Treat the
rest as a design you should verify on first contact, and please correct this page when you do.

That distinction matters more than the convenience of a tidy document. A cookbook with invented output
is worse than one with gaps, because you cannot tell which parts were tested.

## 1. Install the driver

The Databricks driver is an **optional extra**, so a default install does not carry it — most people
querying DuckDB or Postgres should not have to download Thrift.

```console
$ uv sync --extra databricks
 + databricks-sql-connector==4.x
 + thrift==0.24.0
 …
```

Without it, every Databricks command tells you exactly this:

```console
$ uv run semantiql inspect --datasource databricks
error: the Databricks driver is not installed. It is an optional extra, so that a clone stays light:
  uv sync --extra databricks
or  pip install 'semantiql[databricks]'
```

*(Captured.)*

## 2. Get the three connection values

From your SQL warehouse's **Connection details** tab in the Databricks UI:

| Value | Looks like | Environment variable |
|---|---|---|
| Server hostname | `adb-1234567890.12.azuredatabricks.net` | `DATABRICKS_SERVER_HOSTNAME` |
| HTTP path | `/sql/1.0/warehouses/abc123def456` | `DATABRICKS_HTTP_PATH` |
| Access token | `dapi…` | `DATABRICKS_TOKEN` |

```bash
export DATABRICKS_SERVER_HOSTNAME='adb-1234567890.12.azuredatabricks.net'
export DATABRICKS_HTTP_PATH='/sql/1.0/warehouses/abc123def456'
export DATABRICKS_TOKEN='dapi…'
export DATABRICKS_CATALOG=main          # optional
export DATABRICKS_SCHEMA=shop           # optional, defaults to `default`
```

**Use the environment, not `--dbx-token`.** A token on a command line lands in your shell history and in
every process listing on the machine. The flag exists for scripting; the variable is the default for a
reason.

A missing value is refused by name rather than as a connection failure:

```console
$ uv run semantiql inspect --datasource databricks --dbx-host adb-123.azuredatabricks.net
error: Databricks needs --dbx-http-path / DATABRICKS_HTTP_PATH, --dbx-token / DATABRICKS_TOKEN
```

*(Captured.)* "Connection failed" would send you to the network; this sends you to your shell.

## 3. Use a read-only identity

Do this before anything else, and do not skip it because the token you already have works.

- Prefer a **service principal** over your own personal access token, so the grants are the identity's
  rather than yours.
- Grant `USE CATALOG`, `USE SCHEMA` and `SELECT` on the relations you intend to model. Nothing more.
- SemantiQL never needs write access. Its own validation refuses every non-`SELECT`, but that is the
  *inner* defence — a Unity Catalog grant is the one a bug in this project cannot reach past.

The Databricks driver exposes no read-only session flag of the kind `psycopg` has, which is worth
knowing precisely: on Postgres the connection itself is read-only, and here the guarantee rests on the
grant plus SemantiQL's refusal. Two layers either way, but they are not the same two.

## 4. See what is there — **not captured**

```bash
uv run semantiql inspect --datasource databricks
uv run semantiql inspect --datasource databricks --table main.shop.order_lines
```

Relations come from `information_schema.tables`, so you see what your grants allow. A name outside the
default schema stays qualified, because an unqualified one would not resolve.

Column types arrive as Spark's own and are mapped into the model's four words — `STRING` → `string`,
`BIGINT`/`DOUBLE`/`DECIMAL` → `number`, `DATE`/`TIMESTAMP`/`TIMESTAMP_NTZ` → `date`, `BOOLEAN` →
`boolean`, and `MAP`/`STRUCT`/`ARRAY` → `other`, which means "the adapter cannot tell" rather than
"mismatch".

> **The Spark trap.** `TIMESTAMP` **is** zone-aware and `TIMESTAMP_NTZ` is the naive one — the opposite
> of what the longer name suggests to anyone arriving from Postgres. `inspect` prints
> `carries a timezone` for the first and not the second, and that flag is what decides whether a
> dimension needs `timezone:`. Declaring one on a naive column *moves* the buckets rather than pinning
> them.

## 5. Write the model

Identical to any other datasource except two lines: the dialect, and a fully qualified `source`.

```yaml
# model/datasource.yml
version: 1

datasource:
  name: lakehouse
  dialect: databricks
```

```yaml
# model/order_lines.yml
tables:
  order_lines:
    source: main.shop.order_lines      # catalog.schema.table
    description: >-
      One row per order line, not per order — use order_count for orders.

    dimensions:
      channel:
        column: channel
        type: string
        label: Sales channel
      placed_at:
        column: placed_at
        type: date
        # placed_at is TIMESTAMP in Spark, which IS zone-aware. Add `timezone:` only after
        # asking which zone the business means; there is no safe default.
        label: Order date

    measures:
      revenue:
        column: net_amount
        agg: sum
        label: Revenue
      order_count:
        column: order_id
        agg: count_distinct
        label: Orders
```

**A file path is not a source here.** Databricks has no notion of one, so `orders.csv` is refused by
name rather than passed through to become a confusing "table or view not found":

```
'orders.csv' looks like a file path, and Databricks has no file sources.
Register it as a table or view in Unity Catalog first.
```

Register the file as an external table or a view, and model that.

## 6. What SemantiQL actually sends — **captured**

This part needs no workspace, because building the SQL is local. Given the model above:

```
semantic:  SELECT revenue, order_count, channel FROM order_lines ORDER BY revenue DESC
physical:  SELECT SUM(net_amount) AS revenue, COUNT(DISTINCT order_id) AS order_count,
                  channel AS channel
             FROM main.shop.order_lines GROUP BY channel ORDER BY revenue DESC

semantic:  SELECT revenue, DATE_TRUNC('month', placed_at) FROM order_lines
physical:  SELECT SUM(net_amount) AS revenue,
                  DATE_TRUNC('MONTH', CAST(placed_at AS TIMESTAMP_NTZ)) AS placed_at_month
             FROM main.shop.order_lines
            GROUP BY DATE_TRUNC('MONTH', CAST(placed_at AS TIMESTAMP_NTZ))
```

Two things worth reading off that. The grain casts to **`TIMESTAMP_NTZ`**, so the bucket cannot depend
on the warehouse's session timezone — the same guarantee the Postgres adapter gets from its own cast.
And nothing in `engine/` knows Databricks exists: sqlglot transpiles, which is why adding this
datasource changed zero engine files (spec 023).

You can produce this yourself before you have credentials, which makes it a cheap way to sanity-check a
model:

```bash
uv run semantiql -m model/ --datasource databricks --show-sql "SELECT revenue FROM order_lines"
```

## 7. Check, then ask — **not captured**

```bash
uv run semantiql doctor -m model/ --datasource databricks
uv run semantiql -m model/ --datasource databricks \
  "SELECT revenue, order_count, channel FROM order_lines ORDER BY revenue DESC"
```

`doctor` compares every `column:` against the real relation and every `timezone:` against whether the
column carries one. Loop on it until it exits 0 before trusting a figure.

## 8. Hand it to Claude

```bash
export SEMANTIQL_MODEL="$PWD/model"
export SEMANTIQL_DATASOURCE=databricks
# the three DATABRICKS_* variables from step 2 are read from the environment

uv run semantiql serve -m model/ --datasource databricks --print-config
```

The MCP server exposes the same two read-only tools whatever the datasource is — `describe_model` and
`query`. Nothing about Databricks widens that surface.

## Known limits

- **Neither the introspection nor the query path has been exercised against a real workspace.** Spec
  023's `validation.md` records the same thing. Everything in steps 4, 7 and 8 is design.
- **`information_schema` is assumed available.** It is, under Unity Catalog. On a workspace still using
  the legacy Hive metastore, `tables()` and `columns()` may need `SHOW`-based fallbacks.
- **No read-only session flag**, as described in step 3.
- **One table per query.** Joins are refused; a Databricks **view** is the supported way to model
  something wider, and it is a good fit here because the warehouse is where that view belongs anyway.
