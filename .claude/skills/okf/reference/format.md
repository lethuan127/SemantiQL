# The format — OKF 0.2

Condensed from the [Open Knowledge Format specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) v0.2 (Google Cloud, Apache-2.0, commit `3fcbb9f`). This is a working summary in this repo's voice, not the normative text — when the two disagree, upstream wins.

## Contents

- Bundle rules
- Reserved file: index.md
- Reserved file: log.md
- Concept anatomy
- Core fields
- Provenance: sources
- Trust: generated and verified
- Lifecycle: status and stale_after
- Body headings
- Cross-linking
- Conformance
- Versioning
- Legacy fields from 0.1

## Bundle rules

A bundle is a directory tree of `.md` files. Nesting is free-form — group by kind (`agents/`, `prompts/`, `tools/`) or by domain, whichever a reader would guess first.

Distribution is a git repository (preferred), a subdirectory of a larger repo, or a tarball. Nothing about the format depends on which.

One convention worth keeping: `references/` holds external material the `sources` entries point at — a saved spec, run instructions, a script. It keeps a bundle useful when the source URL rots.

## Reserved file: index.md

A directory listing, so a reader can descend by need instead of globbing the tree. Markdown lists, one line per entry, each with a short description:

```markdown
# Tables

* [Orders](orders.md) - one row per order line, grain is order_id + sku
* [Events](events/) - daily-sharded event exports
```

Relative paths. Subdirectories end in `/`.

The bundle-root `index.md` is the **only** file that may carry frontmatter, and it holds exactly one field:

```yaml
---
okf_version: "0.2"
---
```

Frontmatter in any other `index.md` is a conformance error.

## Reserved file: log.md

Change history, date-grouped, newest first. ISO `YYYY-MM-DD` headings; the bold keyword is conventional:

```markdown
# Update Log

## 2026-08-10
* **Update**: Corrected the grain — one row per order *line*, not per order [orders](/tables/orders.md)
* **Creation**: Added the refund-rate metric and its computation [refund-rate](/metrics/refund-rate.md)
```

One `log.md` per directory is allowed; a single root log is usually enough and easier to read.

## Concept anatomy

Every non-reserved `.md` file is a concept: a YAML frontmatter block delimited by `---`, then free-form markdown.

```markdown
---
type: Table
title: Orders
---

Prose. Claims carry footnote markers keyed to source ids.[^warehouse-docs]

# Schema
...

[^warehouse-docs]: Per the warehouse schema documentation.
```

## Core fields

| Field | Status | Notes |
|---|---|---|
| `type` | **required** | Non-empty string. Free text, no registry. See `reference/profiles.md` on choosing a vocabulary. |
| `title` | recommended | Display name. |
| `description` | recommended | One line. This is what shows up in a search result or an index. |
| `resource` | recommended | Canonical URI of the thing being described — repo path, URL, or `server/tool_name`. |
| `tags` | recommended | Flat list of lowercase strings. |

Unknown extra keys are legal. A reader ignores what it does not recognise rather than rejecting the file.

## Provenance: sources

Where the claims came from. Each entry needs a stable `id`, because footnotes key to it.

```yaml
sources:
  - id: warehouse-docs
    resource: https://internal.example/docs/orders
    title: Orders schema documentation
    author: human:thuanle          # optional — who produced the source
    usage_count: 412               # optional — how often it was exercised
    last_modified: 2026-07-30      # optional — YYYY-MM-DD
usage_window: { from: 2026-07-01, to: 2026-08-10 }
```

`resource` is a URL or a bundle-relative path. `usage_count` and `usage_window` describe how much evidence sits behind a claim — a query pattern seen 400 times in a window is a stronger claim than one seen twice.

Per-claim attribution uses standard markdown footnotes whose labels are source ids: `...one row per order line.[^warehouse-docs]`. A concept with `sources` but no footnotes states where it looked; a concept with footnotes states which claim came from where. Prefer the second.

## Trust: generated and verified

```yaml
generated: { by: claude-code/claude-opus-5, at: '2026-08-10T09:14:00+00:00' }
verified:
  - { by: process:nightly-eval, at: '2026-08-11T02:00:00+00:00' }
  - { by: human:thuanle, at: '2026-08-11T09:30:00+00:00' }
```

`generated` is who first produced the concept; `verified` accumulates confirmations. Both use the actor forms in `SKILL.md`, and `at` is ISO 8601 with an offset.

A reader may encounter `verified` as a bare mapping instead of a list. Treat it as a one-element list.

The trust tier is derived from `verified` — see `SKILL.md`. There is no field to declare it.

## Lifecycle: status and stale_after

```yaml
status: stable          # draft | stable | deprecated — defaults to stable when absent
stale_after: 2026-11-01 # absolute date, YYYY-MM-DD
```

Both are optional. `stale_after` is a date, not a duration, so it needs a deliberate choice at write time — set it from how fast the subject moves, and omit it for something genuinely stable rather than inventing a horizon:

| Subject moves | Reasonable horizon |
|---|---|
| With every edit to a string or a config | 1-2 months |
| When a vendor ships, or a schema migrates | 3-6 months |
| Only when the system is redesigned | 6-12 months |
| Not at all — a settled definition, a closed incident | leave it out |

`deprecated` means superseded, not deleted. Keep the file, set the status, and link forward to the replacement — a reader who arrives from an old link needs to land somewhere.

## Body headings

Conventional, not required. Upstream defines three:

| Heading | Holds |
|---|---|
| `# Schema` | structured field/column description |
| `# Examples` | concrete usage |
| `# Computation` | a fenced block holding the sanctioned computation |

Other names are free, and `reference/profiles.md` collects the ones worth reusing. Follow whatever a bundle already does.

## Cross-linking

Plain markdown links. Bundle-absolute paths are preferred because they survive a file moving between directories:

```markdown
[The triage agent](/agents/triage.md)          preferred
[The triage agent](../agents/triage.md)        legal
[Linear MCP docs](https://linear.app/docs/mcp) external
```

A link asserts that a relationship exists; the prose around it says which one. There is no typed-edge syntax, so write the relationship out: "reads the schema described in X", "superseded by Y".

## Conformance

A bundle conforms when:

1. Every non-reserved `.md` file has a parseable YAML frontmatter block.
2. Every frontmatter block has a non-empty `type`.
3. `index.md` and `log.md`, where present, follow the structures above.

A reader must:

- accept a bare `verified` mapping as a single-element list
- accept missing optional fields
- carry on past unknown `type` values and unknown keys
- carry on past broken links
- surface a failing attestation rather than dropping it

A reader must not reject a bundle for missing optional frontmatter, an unknown `type`, unknown keys, or an absent `index.md`.

## Versioning

`<major>.<minor>`. Minor bumps add backward-compatible fields and conventions; major bumps break. A bundle may declare its target with `okf_version` in the root `index.md`, and a reader should attempt a best-effort read of any version it meets.

## Legacy fields from 0.1

Two 0.1 constructs were superseded, and old bundles still carry them:

| 0.1 | 0.2 |
|---|---|
| `timestamp` | `generated: { by, at }` |
| a `# Citations` body list | `sources` frontmatter |

Fall back to the legacy field when the 0.2 one is absent. When updating such a concept, migrate it in the same edit.
