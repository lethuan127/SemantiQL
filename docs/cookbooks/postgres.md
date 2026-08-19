# Cookbook — SemantiQL on Postgres

A complete walkthrough, from an empty database to answering a question. **Every command and every
output below was captured from a real run**, on the throwaway Postgres this repository ships. Where a
figure appears, it came out of the terminal.

Takes about ten minutes. You need Docker and `psql` — see
[12-development-environment.md](../12-development-environment.md) if either is missing.

## 1. A database with something in it

```bash
docker compose up -d --wait

export PGPASSWORD=postgres
psql -h 127.0.0.1 -p 55432 -U postgres -d postgres \
  -c 'CREATE DATABASE semantiql_cookbook'
psql -h 127.0.0.1 -p 55432 -U postgres -d semantiql_cookbook \
  -f scripts/fixtures/seed.sql
```

That loads a deliberately awkward five-row fixture: one row per order *line*, five money columns, a
`timestamptz`, and a customer email. Small enough to check by hand, which is the point.

## 2. A read-only account

Do this before anything else. It is the outer of two defences, and the only one a bug in SemantiQL
cannot reach past.

```bash
psql -h 127.0.0.1 -p 55432 -U postgres -d semantiql_cookbook <<'SQL'
CREATE ROLE cookbook_ro LOGIN PASSWORD 'readonly';
GRANT CONNECT ON DATABASE semantiql_cookbook TO cookbook_ro;
GRANT USAGE ON SCHEMA public TO cookbook_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO cookbook_ro;
SQL

export DSN='postgresql://cookbook_ro:readonly@127.0.0.1:55432/semantiql_cookbook'
```

Everything from here uses that role. In production, keep the password out of your shell history: omit
`--dsn` and let libpq read `PGHOST`, `PGUSER` and `~/.pgpass`, exactly as `psql` does.

## 3. See what is there

```console
$ uv run semantiql inspect --datasource postgres --dsn "$DSN"
3 relations:
  customers
  order_lines
  order_totals

Next: semantiql inspect --table <name>   (add --json for machine output)
```

Needs no model — it is what runs *before* one exists. And on Postgres it sees exactly what the role is
permitted to see, so a narrow grant produces a correspondingly narrow list.

```console
$ uv run semantiql inspect --datasource postgres --dsn "$DSN" --table order_lines
order_lines:
  line_id          bigint                    -> type: number
  order_id         bigint                    -> type: number
  customer_email   text                      -> type: string
  placed_at        timestamp with time zone  -> type: date  carries a timezone
  channel          text                      -> type: string
  quantity         integer                   -> type: number
  unit_price       numeric                   -> type: number
  gross_amount     numeric                   -> type: number
  discount_amount  numeric                   -> type: number
  refund_amount    numeric                   -> type: number
  net_amount       numeric                   -> type: number
```

**`carries a timezone` on `placed_at` is the line to notice.** `type: date` cannot tell a `date`, a
naive `timestamp` and a `timestamptz` apart, and only the third takes a `timezone:`. Step 5 is where
that matters, and it is worth 15.00 on this fixture.

## 4. See what is *in* it

`inspect` reports what exists; `profile` reports what is inside. This is what lets you answer the
question a schema cannot.

```console
$ uv run semantiql profile --datasource postgres --dsn "$DSN" --table order_lines
order_lines:  5 rows

  order_id         nulls 0  distinct 3  sum 505  min 100  max 102
                   values: 102(2)  100(2)  101(1)
  channel          nulls 0  distinct 2
                   values: web(4)  store(1)
  unit_price       nulls 0  distinct 5  sum 97.50  min 5.00  max 40.00
  gross_amount     nulls 0  distinct 5  sum 130.00  min 15.00  max 40.00
```

Two things fall out immediately. **`order_id` has 3 distinct values across 5 rows**, so a row count is
not an order count — this table is one row per line. And **five money columns sum to different
totals**: gross is 130.00, and net (after discounts and refunds) is 69.00. Which one is "revenue" is a
business decision, and now you can price it before asking.

## 5. Write the model

One file per table, `datasource` declared once.

```yaml
# model/datasource.yml
version: 1

datasource:
  name: shop
  dialect: postgres
```

```yaml
# model/order_lines.yml
tables:
  order_lines:
    source: order_lines
    description: >-
      One row per order line, not per order. Order 100 has two lines, so counting rows counts
      products sold rather than orders — use order_count for orders.

    dimensions:
      channel:
        column: channel
        type: string
        label: Sales channel
        description: How the order was placed — web or store.
      placed_at:
        column: placed_at
        type: date
        timezone: Europe/London
        label: Order date
        description: >-
          When the order was placed. Months are bucketed in Europe/London, which is the answer the
          business gave when asked; the column itself stores an instant with a zone.

    measures:
      revenue:
        column: net_amount
        agg: sum
        label: Revenue
        description: >-
          Gross less discounts and less refunds. The sanctioned definition, confirmed by finance.
      order_count:
        column: order_id
        agg: count_distinct
        label: Orders
        description: Distinct orders. Distinct because one order can span several lines.

    metrics:
      average_order_value:
        expression: revenue / order_count
        label: Average order value
```

Three decisions in there are **judgement, not derivation**, and none of them could be read off the
schema: that revenue is `net_amount`, that orders need `count_distinct`, and that months belong to
Europe/London. The `description` fields are where the reasoning goes — they are sent to Claude by
`describe_model`, so they are how a question about "sales channel" finds `channel`.

## 6. Check it against reality

```console
$ uv run semantiql doctor -m model/ --datasource postgres --dsn "$DSN"
✓ datasource 'shop' speaks postgres
order_lines
  ✓ source 'order_lines' has 11 columns
  ✓ 2 dimensions, 2 measures and 1 metric all resolve

1 table checked, no problems found.
```

Run it before you trust a number, and whenever the database changes. `doctor` proves the model matches
the *database*; nothing can prove it matches your *business* except a person reading it.

## 7. Ask

```console
$ uv run semantiql -m model/ --datasource postgres --dsn "$DSN" \
    "SELECT revenue, order_count, average_order_value, channel FROM order_lines ORDER BY revenue DESC"
revenue  order_count  average_order_value  channel
-------  -----------  -------------------  -------
54.00    2            27.0                 web
15.00    1            15.0                 store
```

54.00 + 15.00 = 69.00, which is the net total `profile` reported. The metric divided per group, not
overall — `web`'s 54.00 over its own 2 orders.

### The timezone, made concrete

```console
$ uv run semantiql -m model/ --datasource postgres --dsn "$DSN" --show-sql \
    "SELECT revenue, DATE_TRUNC('month', placed_at) FROM order_lines ORDER BY placed_at_month"
-- SELECT SUM(net_amount) AS revenue,
--        DATE_TRUNC('MONTH', placed_at AT TIME ZONE 'Europe/London') AS placed_at_month
--   FROM order_lines GROUP BY ... ORDER BY placed_at_month ASC
revenue  placed_at_month
-------  -------------------
18.00    2026-07-01 00:00:00
51.00    2026-08-01 00:00:00
```

Now change one line — `timezone: UTC` — and ask again:

```console
revenue  placed_at_month
-------  -------------------
33.00    2026-07-01 00:00:00
36.00    2026-08-01 00:00:00
```

**15.00 moved from August to July.** One order sits at `2026-07-31 23:30+00`, which is past midnight in
British Summer Time. Nothing errored, both answers are correct for their question, and only one is the
question the business asked. That is why `timezone:` is a declared field in git rather than an
assumption inherited from whichever server happens to run the query.

## 8. What refusal looks like

Two defences, and both are worth seeing.

```console
$ uv run semantiql -m model/ ... "SELECT revenue, region FROM order_lines"
refused: 'region' is not defined on table 'order_lines'.

$ uv run semantiql -m model/ ... "DELETE FROM order_lines"
refused: Only SELECT is supported, and this is DELETE; the semantic layer is read-only.
```

And the account behind it, checked independently:

```console
$ psql -U cookbook_ro -d semantiql_cookbook -c 'DELETE FROM order_lines'
ERROR:  permission denied for table order_lines
```

The first refusal is the important one. There *is* no region here, and the answer is to say so — not to
substitute `channel` because it is also a grouping. A plausible wrong number is undetectable by the
person reading it, which is the whole reason this layer exists.

## 9. Hand it to Claude

```bash
export SEMANTIQL_MODEL="$PWD/model"
export SEMANTIQL_DATASOURCE=postgres
export SEMANTIQL_DSN="$DSN"

uv run semantiql serve -m model/ --datasource postgres --print-config
```

That prints the `mcpServers` JSON with paths resolved, for `claude_desktop_config.json`. For Claude
Code, install the plugin instead — see [03-setup-workflow.md](../03-setup-workflow.md).

## Tidy up

```bash
psql -h 127.0.0.1 -p 55432 -U postgres -d postgres \
  -c 'DROP DATABASE semantiql_cookbook' -c 'DROP ROLE cookbook_ro'
docker compose down
```
