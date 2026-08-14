# Self-improvement — SemantiQL gets better as Claude works

Idea: every user chat is an opportunity to improve the semantic model. The loop:

## At runtime (automatic, per question)

1. **Outcome-tagged logging:** question → semantic SQL → raw SQL → result + status (ran fine / blocked by validation / error / user complained).
2. **End-user feedback:** an MCP tool `rate_answer` — Claude asks back "was this correct?" or the user says "that's wrong"; the rating is stored with the log.
3. **Good answers become examples:** confirmed (question, semantic SQL) pairs are saved as *verified examples*, used as few-shot/RAG context for later questions (the Vanna AI approach). The model gets more accurate with use **without editing the YAML**.

## Periodically (proposals for the builder to review — never auto-applied)

4. **Gap detection:** questions that couldn't be answered due to a missing metric/dimension are collected into a "gaps" list.
5. **YAML change proposals:** the tool drafts changes (add a metric, fix a misleading description, add synonyms) as a diff/PR — the builder reviews and merges. The YAML in git remains the single source of truth.

## Principles

- Two separate learning tiers: the **examples tier** (automatic, safe, reversible) and the **YAML schema tier** (always human-reviewed).
- **Never auto-change a metric definition** — a silently wrong business number is the biggest risk.
- This is the differentiator vs. Cube/dbt Semantic Layer (static semantic models) — put it in the benchmark: accuracy in week 1 vs. week 4.
