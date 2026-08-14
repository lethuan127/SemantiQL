# Consuming

## Contents

- Enter at the index
- Gate every concept before relying on it
- Say what you relied on
- When sources conflict
- When the question is a number
- When the bundle has nothing
- Feed back what you learn

## Enter at the index

Read the root `index.md`, pick the one or two branches that could hold the answer, read those `index.md` files, then open only the concepts whose descriptions match. That is what the index files are for.

Globbing the bundle and reading every concept defeats the design: it spends the context budget on files you did not need and buries the two that mattered. A bundle is built for descent.

## Gate every concept before relying on it

Three checks, in this order, on each concept you plan to act on:

| Check | Fails when | Then |
|---|---|---|
| `status` | `draft` | usable as a lead; say it is a draft |
| | `deprecated` | follow the forward link instead; do not act on it |
| `stale_after` | the date has passed | **verify against the source before acting** |
| trust tier | `unverified` | confirm the specific claim you need against `resource` |

The tier derivation is in `SKILL.md`. `machine-confirmed` and `human-reviewed` are both actionable; `unverified` means one agent wrote it and nobody has checked it, which is a lead rather than a fact.

Expired `stale_after` does not make a concept wrong — it makes it unchecked. The cheap move is almost always to open `resource` and confirm the single claim you need, which takes one read and converts a stale doc into a usable one. A concept with no `stale_after` at all is an implicit claim that the subject does not move; test that claim once rather than trusting it forever.

## Say what you relied on

When a concept drove your answer, name it: the path, and the tier. "Per `/tables/orders.md` (machine-confirmed, fresh until 2026-10-01), the grain is one row per order line."

This is not ceremony. It lets the user check the one thing your answer rests on, and it makes a wrong doc visible instead of laundering it through your prose.

## When sources conflict

**The source always wins.** A concept that contradicts the schema, config, or code it describes is stale. Never reinterpret the source to fit the doc.

Two concepts contradicting each other, in order:

1. Prefer the higher trust tier.
2. Tie → prefer the later `generated.at`.
3. Still tied → open both `resource` values and settle it against the sources.

Either way, report the conflict. Two live concepts disagreeing is a bundle defect worth one line in your answer, and usually a `log.md` entry once fixed.

Unknown `type` values, unknown frontmatter keys, and broken links are all normal — keep going. Note a broken link if it was the link you needed.

## When the question is a number

A score, a rate, an accuracy, a cost. Look for an `Attested Computation` before writing any query or script of your own: the point of that type is that one computation is sanctioned and the rest are guesses that look identical in a chat window.

Bind the declared parameters, run it, and compare the result against the `executor.receipt` fields. See `reference/attestation.md`. If attestation fails, surface the failure — a number that failed its check is worse than no number, because it will be quoted later without the caveat.

Only when no computation exists do you compute it yourself, and then say plainly that the number is unattested and offer to write the computation down.

## When the bundle has nothing

Say so in one line, answer from the sources directly, and offer to author the concept — the gap you just hit is exactly the concept worth writing, and you now have the sources in hand. See `reference/authoring.md`.

## Feed back what you learn

While doing other work you will discover that a concept is wrong, incomplete, or now verifiable. Three responses, in order of preference:

1. **Fix it** — you have the source open and the evidence in hand. Follow the update procedure in `reference/authoring.md`.
2. **Verify it** — you confirmed a claim against the source, so add a `verified` entry for your own actor and nothing else.
3. **Flag it** — no time to fix: add one `log.md` line saying which claim looked wrong and what you saw.

Silently working around a doc you know is wrong is the one response that leaves the bundle worse than finding nothing at all.
