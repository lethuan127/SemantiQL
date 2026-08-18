# Eval suite

Three cases, one per thing this plugin does. Each is a `prompt.md` handed to an agent and a
`graders/criteria.md` used to score what it did.

| Case | Asks |
|---|---|
| `01-build-the-model` | given a real database, does it inspect, ask, and write a model without improvising SQL? |
| `02-ask-a-business-question` | does it answer from the model, and **report the gap** when it cannot? |
| `03-enrich-the-model` | asked to change what a word means, does it disclose what moves? |

## Running it

```bash
claude plugin eval ./plugin --ablation with-without
```

**That command is gated.** On this account it exits 1 with *"`plugin eval` is currently in early
access"*, and the gate is an entitlement inside a compiled binary rather than a local flag — there is
nothing to switch on. The suite is written to the layout the shipped CLI documents
(`evals/**/prompt.md` plus `graders/*.md`, both confirmed as string literals in the binary; `case.md`
appears zero times), so it runs the day access arrives.

Until then the corpus still earns its place twice over: it is the clearest statement anyone has of what
correct behaviour *is*, and `tests/interfaces/test_plugin.py` keeps it valid — every case has a grader,
every grader cites the spec its rules came from, and every `semantiql` verb a grader names is one the
CLI actually dispatches.

## The graders are rules, not preferences

Each Must traces to a shipped spec, and that provenance is load-bearing. "No raw `psql` (spec 020)" is
something you can argue with. "No raw SQL", unattributed, is not defensible at five in the afternoon
when someone needs a number — which is exactly when it gets broken.

The rules exist because each was broken once, by a real run, and found by a human reading a transcript:

| Rule | Found by |
|---|---|
| read through `inspect`/`profile`, never raw SQL | a run that read every figure it quoted with twelve `psql` calls (spec 020) |
| never write to the database | the same run, which executed `CREATE OR REPLACE VIEW` (spec 020) |
| use a runnable invocation | the skill taught `semantiql inspect`, which is not on `PATH` (spec 018) |
| ask before writing the model | spec 016 FR-9, verified by hand and passing |
| `timezone:` only on a column that carries one | spec 011, and its `doctor` check in both directions |

## The fixture

`.test-workspace/fetch_retail.py` loads **UCI Online Retail II** into its own Postgres database:
1,067,371 real invoice lines from a UK gift-ware retailer, 2009-12-01 to 2011-12-09, CC BY 4.0.

It was chosen over SAP's SALT — a better domain match, being actual ERP data — because SALT is gated
and remains so: the token is valid but the account is not on its authorized list, so every file request
returns 403. `fetch_salt.py` sits ready beside it for when that changes.

What makes Online Retail II a hard test anyway, and none of it was designed: **there is no revenue
column**. Sales are `quantity * unit_price`, and a SemantiQL measure maps to one column — so the
headline metric cannot be modelled directly, and the correct answer is a database view. Add credit
notes carried as negative quantities, 243,007 lines with no customer id, and naive timestamps that must
**not** get a `timezone:`, and the fixture asks harder questions than an invented one would.

Ground truth lives in `.test-workspace/examiner/RETAIL-ANSWERS.md`, computed rather than typed. **Keep
it out of any directory a run under evaluation can read** — the exercise is whether the agent asks a
human what these columns mean, and an answer key beside it turns that into reading comprehension.

Attribution, as CC BY 4.0 requires: Chen, D. (2012). *Online Retail II*. UCI Machine Learning
Repository. https://doi.org/10.24432/C5CG6D
