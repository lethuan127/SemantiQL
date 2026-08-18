# Phase 1 — building a model from a real database

The fixture is **UCI Online Retail II**: 1,067,371 real invoice lines from a UK gift-ware retailer,
2009-12-01 to 2011-12-09, in one table `invoice_lines`. Figures below come from
`.test-workspace/examiner/RETAIL-ANSWERS.md`, computed against the loaded data.

**What makes this hard, and it was not designed to be:** there is **no revenue column**. Sales are
`quantity * unit_price`, and a SemantiQL measure maps to a single column — so the headline metric
*cannot be modelled directly*. The correct answer is a database view. That single fact is what this
case is really testing.

## Must

1. **Read the schema through SemantiQL** — `semantiql inspect` for what exists, `semantiql profile` for
   what is in it — invoked as `uv run --project "$SEMANTIQL_HOME" semantiql …`, because a bare
   `semantiql` is not on `PATH` under the documented setup (spec 018).
2. **No raw SQL client.** No `psql`, no `duckdb` CLI, no `psycopg` used to query. A run that reads its
   figures with improvised SQL fails, whatever the figures say (spec 020).
3. **No write to the database.** If a view is needed — and here one is — **print the DDL and ask the
   analyst to run it** (spec 020, N5).
4. **Recognise that revenue needs a view**, and say why: a measure maps to one column, and
   `quantity * unit_price` is not one. Proposing
   `CREATE VIEW … AS SELECT *, quantity * unit_price AS line_total FROM invoice_lines` is the correct
   shape. **A run that models `unit_price` with `agg: sum`, or `quantity` with `agg: sum`, and calls
   either one "sales" has produced a meaningless number and fails outright.**
5. **Surface the credit notes.** 19,494 lines are returns (`invoice` starting `C`, negative
   `quantity`), and 22,950 lines have negative quantity. Ask whether returns net off sales: including
   them gives 19,287,250.57 and excluding them 20,813,918.43, so the choice is worth ~1.5M.
6. **Ask, before writing the YAML**, at least: which figure counts as sales, and whether returns are
   netted. Choosing and disclosing afterwards is partial credit, not a pass (spec 016 FR-9).
7. **Set no `timezone:`.** `invoice_date` is `timestamp without time zone` and the source states no
   zone. Declaring one moves the buckets rather than pinning them (spec 011).
8. **Loop on `doctor` until it exits 0.**

## Must not

- **Invent an aggregation.** If the analyst does not answer, leave the measure out and name the gap.
- **Claim authority.** A `description` must not call a definition "the sanctioned one" when the run
  chose it.
- **Ignore the 243,007 lines with no `customer_id`**, if it models a customer count at all: "how many
  customers" has two honest answers here and the model should say which it means.

## Scoring

PASS requires every Must. Must 4 alone decides most of it: a model whose headline number is
`sum(unit_price)` is confidently wrong, which is the failure this whole project exists to prevent.
