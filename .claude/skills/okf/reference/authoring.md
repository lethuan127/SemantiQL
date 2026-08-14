# Authoring

## Contents

- Before writing
- 1. Locate the bundle and check for an existing concept
- 2. Read the source
- 3. Collect sources
- 4. Write the frontmatter
- 5. Write the body
- 6. Update index.md and log.md
- 7. Validate and report
- Updating an existing concept
- Done means

## Before writing

Two things decide whether this concept is worth anything, and both happen before the first line: reading the source itself, and writing down where each claim came from. A concept assembled from memory is a guess with frontmatter on it.

## 1. Locate the bundle and check for an existing concept

Find the bundle before writing into it. If none exists, propose a location and confirm it — `knowledge/` at the repo root is a reasonable default, and a bundle in the wrong place gets abandoned.

Read the root `index.md`, then the `index.md` of the directory you expect to write into, then two or three existing concepts. That last read is what tells you the bundle's profile: which `type` values it uses, which headings, how `resource` is written. Match it. `reference/profiles.md` covers the case where nothing exists yet.

If a concept for this thing already exists, this is an **update**, not a new file. Two concepts for one subject is the failure that makes a bundle untrustworthy, because a reader cannot tell which one is live.

New directory → it needs its own `index.md` and a line in the parent's.

## 2. Read the source

Open the thing you are describing — the table, the endpoint, the config, the prompt file — and read the authoritative form of it rather than a doc about it: the live schema, the tool's own parameter list, the committed file. Note its identifier and its last-modified date; both become source fields.

Structural claims come from the thing itself. Behavioural and performance claims come from a run or a measurement, not from an impression.

## 3. Collect sources

Give every source a short stable `id` you can use as a footnote label:

```yaml
sources:
  - id: schema
    resource: bigquery://project/dataset/orders
    title: Table schema as read
    last_modified: 2026-08-04
  - id: owner-note
    resource: /references/orders-grain.md
    title: Data owner's note on grain
    usage_count: 12
```

If a claim has no source, either find one or drop the claim. "It probably retries" is not a claim, it is a question — write it down as an open question or leave it out.

External material that could disappear goes into `references/` in the bundle, and the source `resource` points there as well as at the URL.

## 4. Write the frontmatter

In this order, so diffs stay readable across a bundle:

```yaml
type:            # required
title:
description:
resource:
tags: []
generated: { by: <you>, at: <ISO 8601 now> }
verified:        # omit entirely unless you are the verifier
sources: []
usage_window: {} # only when usage_count is present
status:          # omit for stable
stale_after:     # when the subject moves; omit for something settled
```

`generated.by` is your own actor string — the model or process actually writing the file. On `verified`, see the rule in `SKILL.md`: never add a `human:` entry.

Pick `stale_after` deliberately; the horizons table in `reference/format.md` gives the ranges.

## 5. Write the body

Lead with two or three sentences that answer "what is this and when would I care", each substantive claim footnoted to a source id. That paragraph is what a reader sees before deciding to read on.

Then the headings the bundle already uses for this kind of concept — `reference/profiles.md` collects the common ones. Skip a heading you have nothing real to put under; an empty `# Examples` section is worse than none, because it reads as "there are no examples".

Cross-link related concepts inline with bundle-absolute paths, and say what the relationship is: "computed by [the refund-rate computation](/computations/refund-rate.md)".

Footnote definitions go at the bottom of the file.

## 6. Update index.md and log.md

Both, in the same change:

```markdown
* [Orders](orders.md) - one row per order line; grain is order_id + sku
```

The index description is not the concept's `description` verbatim — it is shorter, and it answers "why would I open this one". Keep entries in a stable order (alphabetical, or grouped with a heading per group).

Then `log.md`, newest date first, `**Creation**` or `**Update**` and a link. One line per concept touched.

## 7. Validate and report

```bash
python3 scripts/validate_bundle.py <bundle-root>
```

Fix every error. Read the warnings — a broken link or a concept missing from its index is usually a step 6 you half-did.

Then report, in three lines: which concepts you wrote, their trust tier (`unverified` for anything you produced alone), and the `stale_after` you chose or deliberately omitted. The tier line matters — it tells the user what remains for them to do, which is to verify.

## Updating an existing concept

1. Re-read the source first. The doc is the thing under suspicion, not the thing it describes.
2. Edit the prose and the affected sources.
3. **On a material change, drop the `verified` entries that predate it.** They attest to content that no longer exists, and leaving them makes a rewritten concept look reviewed. A wording fix is not a material change; a changed contract, a changed failure mode, or a new claim is.
4. Reconsider `stale_after` — a fresh read earns a fresh horizon.
5. Migrate any 0.1 legacy fields you find (`timestamp`, a `# Citations` list) in the same edit.
6. Add an `**Update**` line to `log.md`.

## Done means

- The validator reports zero errors.
- Every substantive claim in the body carries a footnote, and every footnote label matches a source `id`.
- `resource` points at something a reader can open, or the type genuinely has nothing to point at.
- `stale_after` is set, or the subject is settled enough not to need one.
- The concept is listed in its directory's `index.md`, and that directory is reachable from the root `index.md`.
- `log.md` has a line for today naming every concept touched.
- No `verified` entry was added for an actor other than you.
