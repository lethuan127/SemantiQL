---
name: okf
description: Writes, reads, and validates Open Knowledge Format (OKF) bundles — markdown files with YAML frontmatter recording what something is, where each claim came from, who verified it, and when it goes stale. The subject can be anything — a dataset, a service, an API, a metric, a prompt or agent, a runbook. Use when documenting something as durable knowledge for later readers, when adding to or reading a knowledge bundle, when a doc's freshness or trustworthiness is in question, when a number needs one sanctioned computation, or when checking a bundle for OKF conformance.
---

# OKF — knowledge that carries its own provenance

Write knowledge down as markdown that a later reader — agent or human — can find, read, and tell whether to believe.

The failure the format exists to prevent: a doc that reads as authoritative and is quietly a year out of date. An undated, unattributed doc is worse than none, because an agent will follow it. So every OKF concept answers five questions in frontmatter:

| Question | Field family |
|---|---|
| Where did these claims come from? | `sources` |
| Who wrote this, and did anyone check it? | `generated`, `verified` |
| Is it still current? | `stale_after` |
| Is it draft, live, or retired? | `status` |
| Was the computation actually run correctly? | `runtime`, `executor`, `attester` |

The subject is yours to choose. Upstream's own bundles describe data assets; the same format works for services, APIs, prompts, agents, metrics, and procedures. Nothing in it requires tooling: a bundle is plain markdown in git, readable without a viewer, diffable in review, parseable with a YAML library.

## A bundle

```
<bundle-root>/
  index.md              directory listing; carries okf_version at the root only
  log.md                dated change history, newest first
  <group>/              group by kind or by domain — whichever a reader would guess first
    index.md
    <concept>.md
  references/           external material the sources point at
```

`index.md` and `log.md` are the only reserved filenames. Every other `.md` file is a **concept document**: one YAML frontmatter block, then free-form markdown.

**Where the bundle lives** is the repo's call. Look for an existing bundle before creating one; absent any convention, `knowledge/` at the repo root is a reasonable default, and worth confirming rather than assuming.

## The frontmatter you always write

```yaml
type: BigQuery Table                       # the only strictly required field
title: GA4 events export
description: Daily-sharded event-level export from the Merchandise Store.
resource: bigquery://project/dataset/events_*   # canonical URI of the thing described
tags: [analytics, ga4]
```

`type` is free text — no central registry, and a reader must tolerate values it has not seen. Picking a small vocabulary and keeping it consistent is what makes a bundle navigable; `reference/profiles.md` has starting sets for common subjects and the rule for extending them.

Then add the families that apply. Field-by-field syntax, conformance rules, and versioning are in `reference/format.md`.

## Actors

Every identity field — `generated.by`, `verified[].by`, `sources[].author` — uses one of three forms:

| Form | Example | Means |
|---|---|---|
| `<producer>/<version>` | `claude-code/claude-opus-5` | an agent or tool wrote it |
| `human:<id>` | `human:thuanle` | a person wrote or checked it |
| `process:<id>` | `process:nightly-eval` | an automated job |

## Trust tiers are derived, never declared

There is no `trust:` field. A reader computes the tier from `verified`:

| `verified` contains | Tier | What a reader may do with it |
|---|---|---|
| nothing / absent | **unverified** | treat as a lead; confirm against the source before acting |
| machine actors only | **machine-confirmed** | act on it, say which concept you relied on |
| any `human:` entry | **human-reviewed** | act on it |

**Never write a `human:` entry yourself.** An agent adding `human:someone` fabricates a review that never happened and permanently inflates the tier. Only add `verified` entries for actors that are you.

## The three verbs

| Verb | When | Procedure |
|---|---|---|
| **Author** | writing or updating a concept | [reference/authoring.md](reference/authoring.md) |
| **Consume** | answering a question from a bundle | [reference/consuming.md](reference/consuming.md) |
| **Validate** | checking conformance and freshness | below |

Three supporting files: [reference/format.md](reference/format.md) for the field-by-field spec, [reference/profiles.md](reference/profiles.md) for choosing types and body headings for your subject, and [reference/attestation.md](reference/attestation.md) for concepts that carry one sanctioned computation.

## Validate

```bash
python3 scripts/validate_bundle.py <bundle-root>
```

In this repo the path is `.claude/skills/okf/scripts/validate_bundle.py`. It exits non-zero only on the spec's conformance rules — unparseable frontmatter, missing `type`, frontmatter in a non-root `index.md`. Everything else is a warning that reports without failing: missing recommended fields, broken links, a past `stale_after`, a concept absent from its `index.md`, a non-ISO log date, a footnote with no definition. It ends with trust-tier, status and freshness counts.

The tier count is the number worth watching over time. A bundle that is 100% unverified is a bundle nobody has checked.

## Rules that hold across all three verbs

- **The source wins.** When a concept contradicts the thing it describes, the thing is right and the concept is stale. Fix the concept or flag it — never bend the reading of the source to match the doc.
- **`index.md` and `log.md` move in the same change.** A concept that no index lists is invisible to progressive disclosure, so writing it without listing it wastes the work.
- **Link, don't restate.** Two copies of a claim in one bundle means two things to update and one of them will be wrong.
- **Broken links are tolerable; silent staleness is not.** A reader should keep going past a dead link, and stop at an expired `stale_after`.
- **Adopt conventions, don't impose them.** Beyond `type`, everything here is a convention. Follow what a bundle already does rather than converting it to a house style.

## Out of scope

- Building the thing being documented. This skill records what exists.
- Generating a bundle from a BigQuery dataset, or rendering one to interactive HTML → upstream ships a Python CLI for both (`okf enrich`, `okf visualize`); this skill deliberately has no runtime dependency.
