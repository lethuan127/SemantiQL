# Attested computations

## Contents

- The problem
- The contract
- Where the computation lives
- Receipts
- The attester
- Worked example: a metric in SQL
- Worked example: a score in Python
- Keep the meaning and the computation separate
- When attestation fails
- Anti-patterns

## The problem

Ask an agent for a number — revenue last quarter, refund rate, an accuracy score — and it will write a plausible query and return a plausible number. Ask twice and the two differ, because the two queries differed: a different denominator, a different date boundary, a silently dropped null. In a chat window both answers look identical: confident, formatted, one of them wrong.

`type: Attested Computation` closes that gap. The concept carries the **one sanctioned way** to produce the number, plus enough evidence to check afterwards that this is what actually ran.

## The contract

```yaml
type: Attested Computation
runtime: bigquery                  # required — bigquery | postgres | dbt | python | Looker
parameters:
  - { name: start_date, type: date, required: true }
  - { name: end_date, type: date, required: true }
  - { name: region, type: string, required: false }
computation: /references/net_revenue.sql   # omit to use the `# Computation` body fence
executor:
  resource: /references/run-net-revenue.md
  receipt: [net_revenue, row_count, start_date, end_date, query_sha, run_at]
attester:
  resource: /references/check_net_revenue.py
```

`runtime` is the only required addition to the core fields, and the values above are the ones the spec lists.

**The rule that makes this work: a caller binds parameter values and nothing else.** Not the SQL, not the script, not "an equivalent query". If the sanctioned computation cannot answer the question asked, the answer is that it cannot — then propose amending the computation as a deliberate, reviewed change. Rewriting it to fit the question produces an unattested number wearing an attested concept's name.

## Where the computation lives

Two options, and the choice is about size:

- **Inline**, in a `# Computation` fenced block in the body. Good for a query or a short function — the reader sees it without opening anything.
- **Referenced**, via `computation: <path>`, usually into `references/`. Right once it is a real script with imports.

Either way it is version-controlled text, diffable in review. A computation that lives only in someone's notebook is not sanctioned, it is remembered.

## Receipts

`executor.receipt` lists the fields a run must emit. It is what turns "I ran it" into evidence. Four kinds are worth having in almost every receipt:

| Receipt field | Why |
|---|---|
| the result itself | the number being claimed |
| a size — `row_count`, `n_examples` | a figure over 12 rows is not a figure over 400,000 |
| the bound parameter values | the same computation over a different window is a different number |
| `run_at`, and a hash of the computation | lets a reader see the number is from March, produced by a version since edited |

Add whatever else changes the result without changing the computation. For anything model-dependent, that means the model identifier and a hash of the prompt — the two things that move while the eval file stays untouched.

## The attester

`attester.resource` points at a **deterministic** checker: given the receipt, does it hold together? Sizes plausible, parameters inside the supported range, hashes matching what is committed.

Deterministic is the whole point. An LLM asked "does this look right" will usually say yes, which is not a check. If a claim can only be judged by a model, that belongs in the prose as a caveat, not in an attester.

## Worked example: a metric in SQL

````markdown
---
type: Attested Computation
title: Net revenue
description: The sanctioned net-revenue figure — gross less refunds and tax, by order date.
resource: /references/net_revenue.sql
tags: [finance, revenue]
runtime: bigquery
parameters:
  - { name: start_date, type: date, required: true }
  - { name: end_date, type: date, required: true }
executor:
  resource: /references/run-net-revenue.md
  receipt: [net_revenue, row_count, start_date, end_date, query_sha, run_at]
attester:
  resource: /references/check_net_revenue.py
generated: { by: human:thuanle, at: '2026-08-10T10:02:00+00:00' }
verified:
  - { by: human:thuanle, at: '2026-08-10T10:02:00+00:00' }
status: stable
---

The figure finance reports. Excludes tax and refunds, and attributes on **order date**
rather than settlement date — the decision that makes two implementations disagree, so it
is fixed here rather than left to the caller.

Means what [net revenue](/metrics/net-revenue.md) says it means.

# Computation

```sql
SELECT SUM(gross - refunds - tax) AS net_revenue, COUNT(*) AS row_count
FROM orders
WHERE order_date BETWEEN @start_date AND @end_date
```
````

## Worked example: a score in Python

Same shape, `runtime: python`, `computation` pointing at the eval script, and `parameters` for the things that vary — which prompt file, which model, which golden set. The receipt carries `accuracy`, `n_examples`, `model`, `prompt_sha`, `run_at`.

One addition worth making in the prose: **the noise floor**, how much the score moves between identical runs. Without it a reader will read 0.913 over 0.908 as an improvement.

## Keep the meaning and the computation separate

The metric concept says what the number *means*; the computation concept says how it is *produced*. Splitting them lets each carry its own trust tier and lifecycle — a stable, human-reviewed computation can serve a definition still in draft, and a deprecated metric does not drag its computation down with it.

Link them: `See the [net revenue computation](/computations/net-revenue.md).`

## When attestation fails

Surface it. Say which receipt field failed and what the attester expected. A failed attestation is a finding, not an error to retry past — the usual causes are an edited computation whose hash no longer matches, or a shrunken input set, and both are things the reader needs to know before quoting the number.

Never fall back to computing the number another way and reporting that instead.

## Anti-patterns

- **Rewriting the computation to answer a slightly different question.** Amend it deliberately, or say it does not apply.
- **An attester written as an LLM prompt.** Determinism is the requirement.
- **A receipt with only the result in it.** Then there is nothing to check.
- **Reporting a figure with no size and no noise floor.** Precision the number does not have.
- **One computation concept per caller.** They diverge, and now there are three sanctioned truths.
