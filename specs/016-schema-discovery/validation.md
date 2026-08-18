---
type: Validation
title: Schema discovery — Claude reads the database and writes the model — validation
description: Acceptance criteria traced to FR-1..FR-11.
resource: specs/016-schema-discovery/validation.md
tags: [sdd, validation]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T09:50:21+00:00' }
status: stable
---

# Acceptance criteria

- [x] **AC-1** (FR-1): An `Adapter` enumerates its relations as displayed names, sorted by what is
      displayed rather than by schema.
  - **Proven by:** `Adapter.tables` in `src/semantiql/adapters/base.py`; `uv run mypy` holds both
    implementations to it. The sort key was a real bug: sorting by schema first printed a list that
    looked unsorted to a reader who only sees the qualified name.
- [x] **AC-2** (FR-2): Both shipped adapters implement it, and views are included.
  - **Proven by:** `test_tables_lists_tables_and_views` in `tests/adapters/test_duckdb_adapter.py`,
    and `test_every_enumerated_name_can_be_described` in `tests/adapters/test_postgres_adapter.py`
    — the second is the stronger check, since it feeds every enumerated name back through
    `columns()` and so proves the two members agree about what a name means. A view is the
    documented escape hatch for a join, so a discovery that hid views would hide the answer to the
    one thing the engine cannot do.
- [x] **AC-3** (FR-3): A relation outside the default schema comes back qualified; one inside it
      does not.
  - **Proven by:** `test_a_relation_outside_the_default_schema_is_qualified`,
    `test_enumeration_excludes_the_system_schemas`, and
    `test_inspect_json_lists_relations_and_the_dialect`. Qualification is not cosmetic — the
    unqualified name is not resolvable, so it would produce a model that fails `doctor`.
- [x] **AC-4** (FR-4): `semantiql inspect` lists relations, and `--table X` lists that relation's
      columns with each one's SemantiQL type.
  - **Proven by:** `test_inspect_lists_relations_then_columns_on_request`.
- [x] **AC-5** (FR-5): `inspect` runs with no model, and does not fall back to the bundled example.
  - **Proven by:** `test_inspect_needs_no_model`. This is the property the whole feature rests on:
    a command that needed a model could not help you write your first one.
- [x] **AC-6** (FR-6): `--json` emits the relations list, the dialect, and per column the native
      type, the SemantiQL type, and `carries_timezone`.
  - **Proven by:** `test_inspect_json_gives_claude_what_it_needs_to_write_a_model`. The mapped type
    travels because the adapter already did that translation (N4); re-deriving it from the native
    type in a prompt would put a dialect's vocabulary back into the client.
- [x] **AC-7** (FR-7): The default output has no columns in it.
  - **Proven by:** the `assert "placed_at" not in listing` in
    `test_inspect_lists_relations_then_columns_on_request`. A 500-table warehouse arriving in one
    reply is a context problem, and asserting the *absence* is the only way that stays true.
- [x] **AC-8** (FR-8): The skill instructs Claude to inspect, ask the judgement questions, write the
      YAML itself, and loop on `doctor`.
  - **Proven by:** `test_the_skill_tells_claude_to_write_the_model_itself`,
    `test_the_skill_puts_the_judgement_calls_to_the_human`,
    `test_the_skill_tells_claude_to_run_doctor_until_it_passes`.
- [x] **AC-9** (FR-9): The skill forbids inventing an aggregation or a formula, and forbids changing
      a model to answer a question.
  - **Proven by:** `test_the_skill_forbids_changing_a_model_to_answer_a_question`.
- [x] **AC-10** (FR-10): The server still exposes exactly two tools, and the skill names no tool the
      server lacks.
  - **Proven by:** the pre-existing two-tool assertion in `tests/interfaces/test_server.py`, plus
    `test_the_skill_does_not_promise_a_tool_the_server_lacks`. Discovery uses a shell, not a third
    tool — so the enforcement boundary is the same width it was before this spec.
- [x] **AC-11** (FR-11): A3 describes the discovery loop, and every document that described
      hand-writing as *the* flow now describes it as the alternative.
  - **Proven by:** `docs/03-setup-workflow.md` A3; the reconciled standfirst and Step 3 of
    `docs/10-adopting-semantiql.md`; the README's Key ideas; `grep -rn "wizard" README.md docs/`
    returning only deliberate uses.

# Non-functional acceptance

- [x] The repo's verify gate is green, run **both** with Postgres up and with it down — the second
      run is what proves the `pg` tests skip rather than fail on a fresh clone.
- [x] **N4** — `grep -rnE "adapters(\.|[[:space:]]+import)" src/semantiql/engine/` still returns only
      `adapters.base`. The seam widened; `engine/` did not change.
- [x] **N5** — enumeration reads `information_schema` only. The Postgres path rolls back after the
      fetch, leaving the connection `idle`.
- [x] **N6** — the two forbidding sentences are in the skill and each has a test. The architecture
      doc now states the narrower true rule: Claude never writes the model *as a side effect of
      answering*.
- [x] **N1 / N2** — `inspect` returns metadata, never rows. It is not a query path, so the single
      path to the data is unchanged.

# Manual verification

1. `uv run semantiql inspect` with no arguments — expect the explanation of why an in-memory
   DuckDB reading CSV files has an empty catalogue, not a blank line.
2. `uv run semantiql inspect --database <a .duckdb file>` — expect relations, no columns.
3. `uv run semantiql inspect --datasource postgres --table orders` against the compose container —
   expect `placed_at timestamp with time zone -> type: date  carries a timezone`, which is the fact
   an analyst needs to write `timezone:` correctly and cannot get from `type:` alone.
4. In Claude Code, ask for a model for a database you have. Expect to be **asked** which aggregation
   is revenue and what a row is. If it picks one silently, FR-9 has regressed and no test caught it.

**Steps 1–3 were run and their output is quoted in `docs/03-setup-workflow.md` A3.**

**Step 4 has now been run, twice, and it passes** — recorded here by spec 018, which is the change
that running it produced. Two independent `claude` processes were given the same request against a
purpose-built ambiguous DuckDB fixture: eleven columns, five of them money (`gross_amount`,
`discount_amount`, `refund_amount`, `net_amount`, `unit_price`), one row per order *line* with an
order spanning two lines, a `timestamptz`, and a customer email.

- **Interactive, in tmux — the run that answers FR-9.** It loaded the skill, ran `inspect`, then
  **stopped and asked, before writing any YAML**: *"Which column is the sanctioned definition of
  revenue?"* offering `net_amount` / `gross_amount` / both-separately-named beside the figures
  (65.00 gross, 63.00 net of discount, 33.00 net) and noting that row 2 is a fully refunded line; and
  *"placed_at carries a timezone. Which timezone should months be bucketed in?"* showing that
  `2026-07-31 23:30Z` is July in UTC and August in Asia/Bangkok, splitting one month across two.
  Better than FR-9 requires: each question carried the numeric consequence of answering it wrongly.
- **Headless (`claude -p`) — what a harness with no TTY can and cannot show.** With nothing to ask,
  the same skill chose `net_amount`, disclosed the choice with its 33.00-versus-65.00 consequence, and
  invited correction. `doctor` exited 0, and both queries it reported were re-run here and matched
  exactly. It also derived `count_distinct(order_id)` unprompted, catching the order-line grain trap.
  One flaw belongs to the harness rather than the skill: the YAML it wrote called its own choice *"the
  sanctioned definition of revenue"*, asserting a sanction nobody had given — which is what the
  interactive run shows the skill avoids when it has somewhere to ask.

**What running it actually found was a different defect**, and one no amount of reading would have
surfaced: both runs failed on the skill's very first command, because it taught bare
`semantiql inspect` and the executable is not on `PATH` under the documented setup. Both recovered —
one after five extra tool calls hunting for the binary — which is precisely why it had survived.
Fixed in spec 018, with the drift test that would have caught it.
