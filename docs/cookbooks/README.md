# Cookbooks

End-to-end walkthroughs, one per datasource. Each takes you from an empty database to a question
answered, and each says plainly which of its commands were actually run.

| Cookbook | Datasource | Output |
|---|---|---|
| [postgres.md](postgres.md) | Postgres, via the throwaway container this repo ships | **every figure captured from a real run** |
| [databricks.md](databricks.md) | Databricks SQL warehouse | install, refusals and emitted SQL captured; the **workspace steps are not** |

## Why these are not numbered docs

The `docs/NN-*.md` files are the ones other work resolves against — the architecture, the model
reference, the invariants. Changing one of those is a trust-boundary edit. A cookbook is a walkthrough:
if it goes stale it misleads a reader for an afternoon, where a stale architecture document misleads
every change made after it. Different weight, so a different place.

## The one rule they follow

**A captured output is labelled, and an uncaptured one is labelled too.** The Postgres cookbook can show
you that changing `timezone: Europe/London` to `timezone: UTC` moves 15.00 between months, because that
was run. The Databricks cookbook cannot show you `doctor` passing, because there is no workspace here —
so it says so, at the top, rather than printing something plausible.

A cookbook with invented output is worse than one with gaps: the gaps are visible, and the invention is
not.

If you run the Databricks steps for real, please correct that page with what actually came back.
