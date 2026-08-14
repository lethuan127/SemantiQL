# Profiles — types and headings for your subject

The spec leaves two things open on purpose: `type` is free text with no registry, and body headings are conventional. A **profile** is one bundle's answer — the small set of types it uses and the headings its concepts carry. Nothing here is required by OKF, and none of it is required by this skill.

## Contents

- Joining a bundle that already has a profile
- Choosing a vocabulary
- Starting set: data assets
- Starting set: AI artifacts
- Starting set: services and operations
- Body headings
- Worked example: a data asset
- Worked example: an AI artifact
- Anti-patterns

## Joining a bundle that already has a profile

Read three existing concepts before writing one. Reuse their `type` values, their heading names, and their `resource` style even when you would have chosen differently — a consistent bundle a reader can predict beats a better vocabulary applied to a third of the files.

Only propose a change when the existing vocabulary cannot express the thing you are documenting, and then say so rather than quietly adding a fourth spelling.

## Choosing a vocabulary

For a new bundle, five to nine types is usually right. The test for each one: would a reader searching the bundle expect a *different set of questions* answered by this type than by its neighbours? If not, it is the same type.

- **Nouns for kinds of thing**, not for activities. `Metric`, not `Measuring`.
- **One spelling per kind.** `System Prompt` alongside `Prompt` splits the bundle for nothing.
- **Add a type when a genuinely new kind appears**, and add it to the bundle's own `index.md` prose so the next author sees it.
- Types are strings, so nothing enforces this. Consistency is the only mechanism.

## Starting set: data assets

Upstream's own bundles use roughly this, and it is a good default for warehouses and pipelines.

| `type` | Documents | `resource` is |
|---|---|---|
| `Dataset` | a schema or dataset as a whole | dataset URI |
| `Table` / `BigQuery Table` | one table or table family, its columns and grain | table URI, wildcards allowed |
| `Metric` | what a number means and how it is defined | — |
| `Attested Computation` | one sanctioned way to compute a number | path to the computation |
| `Query Pattern` | a query shape that answers a recurring question | doc URL |
| `Reference` | an external doc or spec | URL |
| `Playbook` | a procedure for one situation | — |

Fits `# Schema`, `# Examples`, `# Common query patterns`, `# Computation`.

## Starting set: AI artifacts

For documenting an AI system itself. Its distinguishing feature is speed of drift: a prompt changes when someone edits a string, and behaviour changes when the model underneath is swapped — neither leaves a migration behind. So `stale_after` does more work here than in a warehouse bundle, and a prompt concept without its model name is unusable.

| `type` | Documents | `resource` is |
|---|---|---|
| `Agent` | an agent's job, loop shape, tools, escalation rules | path to the definition |
| `Prompt` | a prompt template and the model it was tuned for | path to the prompt |
| `MCP Tool` | one tool: parameters, return shape, side effects | `server/tool_name` |
| `MCP Server` | a server's tool set, auth, deployment | server URL or repo |
| `Skill` | a skill, what fires it, what it excludes | path to `SKILL.md` |
| `Eval` | a golden set and its grader | path to the eval |
| `Playbook` | a procedure for one failure class | — |

Fits `# Contract`, `# Failure modes`, `# Examples`.

## Starting set: services and operations

| `type` | Documents | `resource` is |
|---|---|---|
| `Service` | one deployable: what it owns, its dependencies | repo or service URL |
| `API Endpoint` | one route: request, response, error shapes | the URL template |
| `Runbook` | an on-call procedure with a stop condition | — |
| `Incident` | one postmortem, kept as knowledge | ticket URL |
| `Configuration` | a setting that changes behaviour and who owns it | path to the config |

Fits `# Contract`, `# Failure modes`, `# Dependencies`, `# Runbook`.

## Body headings

Upstream defines three; the rest are conventions worth knowing because readers look for them. Keep whichever names your bundle already uses, exactly.

| Heading | Holds | Suits |
|---|---|---|
| `# Schema` | fields, types, modes, grain | data assets |
| `# Examples` | concrete usage | anything |
| `# Computation` | a fenced block with the sanctioned computation | attested computations |
| `# Contract` | inputs, outputs, parameters, side effects | tools, endpoints, prompts |
| `# Failure modes` | symptom → cause → what to do | anything operational |

Two rules that matter more than the names: **only write a heading you have real content for** — an empty `# Examples` reads as "there are no examples" — and **put the thing a reader came for above the fold**, in the lead paragraph, not under the fourth heading.

## Worked example: a data asset

```markdown
---
type: BigQuery Table
title: GA4 events export
description: Daily-sharded event-level export from the Merchandise Store.
resource: bigquery://bigquery-public-data/ga4_obfuscated_sample_ecommerce/events_*
tags: [analytics, ga4, sharded-tables]
generated: { by: claude-code/claude-opus-5, at: '2026-08-10T09:14:00+00:00' }
sources:
  - id: export-docs
    resource: https://support.google.com/analytics/answer/7029846
    title: 'GA4: BigQuery export schema'
  - id: metadata
    resource: bigquery://bigquery-public-data/ga4_obfuscated_sample_ecommerce/events_*
    title: Table metadata
    last_modified: 2026-07-30
status: stable
---

One row per event, sharded daily as `events_YYYYMMDD`.[^metadata] Event parameters and
items are repeated records, so most questions need an `UNNEST` before they can be
grouped.[^export-docs]

# Schema

| Field | Type | Mode | Notes |
| :--- | :--- | :--- | :--- |
| `event_date` | STRING | NULLABLE | `YYYYMMDD`, not a DATE. |
| `event_params` | RECORD | REPEATED | Key-value; value nested by data type. |

[^export-docs]: GA4 BigQuery export schema documentation.
[^metadata]: Table metadata as read on 2026-07-30.
```

## Worked example: an AI artifact

```markdown
---
type: Prompt
title: Triage classifier system prompt
description: Sorts an inbound support issue into one of five buckets, with a confidence score.
resource: services/triage/prompts/classifier.md
tags: [triage, classification, claude-opus-5, json-output]
generated: { by: claude-code/claude-opus-5, at: '2026-08-10T09:14:00+00:00' }
verified:
  - { by: process:nightly-eval, at: '2026-08-11T02:00:00+00:00' }
sources:
  - id: prompt-file
    resource: services/triage/prompts/classifier.md
    title: The prompt as committed
    last_modified: 2026-08-04
  - id: eval-run
    resource: /evals/triage-accuracy.md
    title: Nightly accuracy eval
    usage_count: 340
usage_window: { from: 2026-07-01, to: 2026-08-10 }
status: stable
stale_after: 2026-10-01
---

Classifies an inbound issue into `bug`, `billing`, `access`, `feature`, or `other`, with a
confidence between 0 and 1.[^prompt-file] Accuracy on the golden set is 0.91, and `access`
versus `bug` accounts for most confusions.[^eval-run]

Tuned against `claude-opus-5`; a model swap invalidates the confusion profile, so re-run
[the accuracy computation](/computations/triage-accuracy.md) before trusting it again.

# Contract

Input: issue title and body, untruncated. Output: a single JSON object,
`{"bucket": <one of the five>, "confidence": <float>}` — no prose, no code fence.

# Failure modes

| Symptom | Cause | Do this |
| :--- | :--- | :--- |
| A sixth bucket appears | The issue text names a category and the model echoes it | Validate against the enum, re-ask once. |
| Confidence pinned at 0.95 | Every few-shot example carries high confidence | Vary the examples' confidences. |

[^prompt-file]: The committed prompt at `services/triage/prompts/classifier.md`.
[^eval-run]: 340 nightly runs, 2026-07-01 to 2026-08-10.
```

## Anti-patterns

- **Restating the source in the concept.** A pasted copy of a schema or a prompt drifts from the original within one edit. Point at it with `resource` and describe what it *means*.
- **Converting a bundle to a different profile mid-stream.** Half-converted is worse than either.
- **A type per instance.** `GA4EventsTable` is a title, not a type.
- **Documenting capability without boundary.** For anything that acts — an agent, a service, a job — the limits are the half that prevents incidents.
- **One giant file.** One concept per thing, listed in an `index.md`; that is what makes progressive disclosure work.
