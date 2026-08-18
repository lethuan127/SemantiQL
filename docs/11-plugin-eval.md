# `claude plugin eval` — the schema, as discovered

**This document is reverse-engineered, not sourced from documentation.** There is no published spec for
`claude plugin eval`. Everything below was established two ways: from `claude plugin eval --help` on the
installed CLI, and by reading string literals out of the shipped binary
(`~/.local/share/claude/versions/2.1.226`, a 279 MB Mach-O). Where the two run out, this document says
so rather than filling the gap.

That provenance is the most important thing on this page. An undocumented format can change in any
release, and a claim here is only as good as the version it was read from. **Re-run the discovery
before trusting it against a newer CLI.**

Version discovered against: **2.1.226**.

## Status: the runner is gated

```console
$ claude plugin eval ./plugin --ablation with-without
`plugin eval` is currently in early access
```

Exit 1. The gate is an account entitlement — the message is a literal inside a compiled binary, there is
no local flag, and nothing in `~/.claude/settings.json` or the project settings changes it. So **no eval
in this repository has ever been scored.** The suite is authored against this schema and waits.

## Layout

`--help` states it exactly:

> Run eval cases (`evals/**/case.yaml` or `evals/**/prompt.md` + `graders/*.md`) against a plugin

Two authoring shapes, and the choice matters:

| Shape | What it is |
|---|---|
| `evals/<case>/case.yaml` | one file per case, metadata and graders inline |
| `evals/<case>/prompt.md` + `evals/<case>/graders/*.md` | the prompt as markdown, one file per grader |

**A note on filenames, because it costs an afternoon to get wrong.** The binary contains `prompt.md`
56 times, `case.yaml` 23 times, `criteria.md` 4 times — and **`case.md` zero times**. A case file named
`case.md` is not read by this version, and the run reports no cases rather than an error.

This repository uses `case.yaml`. See [`../plugin/evals/`](../plugin/evals/README.md).

## `case.yaml`

Field names below are quoted from the binary's own validation messages, which is the strongest evidence
available without running it.

```yaml
schema_version: "1.0"        # required — "missing required field schema_version (e.g. \"1.0\")"
name: build-the-model
tags: [build, discovery]     # filterable with --tag
runs: 3                      # --help: "default: case.runs ?? 3"

execution:
  prompt: |                  # either this…
    Build me a semantic model for the database in my environment.

context:
  history_file: …            # …or this. "either execution.prompt or context.history_file is required"

scaffold_script: ./setup.sh  # author-supplied bash, off unless --scaffold is passed

graders:
  - type: llm
    target: both
    criteria: |
      The rubric the judge grades against.
```

Established messages, verbatim:

- `case.yaml must be a YAML object`
- `missing required field schema_version (e.g. "1.0")`
- `either execution.prompt or context.history_file is required`
- `invalid case.yaml:` *(prefix for the above)*

## Graders

**Six types**, from the validator's own error text:

> `: frontmatter must include "type:" (regex | tool_order | tool_used | file_exists | llm | baseline)`

| Type | Grades |
|---|---|
| `regex` | a pattern against the target |
| `tool_order` | that tools were called in a given order |
| `tool_used` | that a tool was called at all |
| `file_exists` | that the run produced a file |
| `llm` | a rubric, judged by a model (`--judge-model`, default haiku) |
| `baseline` | against the no-plugin arm — the `--ablation` comparison |

The mix is the point: four of the six are **deterministic**. A rule like "never ran `psql`" is a fact and
belongs in a `regex` grader; only "did it ask the right question" needs `llm`. Putting a checkable rule
behind a judge converts a fact into an opinion.

**Targets** — these literals sit beside the parser, so the list is likely but not confirmed complete:
`trace`, `last_message`, `files`, `source`, `file`, `both`, `input_match`.

In the `prompt.md` shape each grader is its own `.md` file whose **frontmatter must carry `type:`** —
`grader .md: frontmatter missing type`. In the `case.yaml` shape they are a list under `graders`.

## What is not established

Honesty about the edges, because a guess here fails a run for the wrong reason:

- **The grader object's rubric field name.** `criteria` is this repository's choice. The binary shows
  `type` and the target vocabulary but no literal for the body field. **`--strict` is the way to find
  out**: `--help` says it fails "on unrecognized fields", so the first strict run names any field this
  schema got wrong.
- **`prompt.md` frontmatter keys.** The parser reports `prompt.md: unknown frontmatter key "…" (expected
  one of: …)`, so an allowlist exists, but its contents are built at runtime and not readable as a
  literal.
- **Whether `graders/` sits inside each case directory or at the `evals/` root.** `--help` writes
  `evals/**/prompt.md + graders/*.md`, and `init --bare` is documented as writing "prompt.md +
  graders/criteria.md". Both readings are consistent with that.
- **Per-case `max_turns` and `timeout_seconds`.** `--help` mentions both as bounding a run, so they are
  probably case fields, but no validation message names them.

## The flags worth knowing

| Flag | Why it matters |
|---|---|
| `--ablation with-without` | runs a no-plugin baseline and reports the delta. **This is the number that says whether the plugin helps**, rather than whether the model is capable |
| `--strict` | fails on unrecognized fields — the schema discovery tool named above |
| `--runs <n>` | per-case repeats. An LLM grader is noisy; one run is not a measurement |
| `--threshold <0..1>` | exit 1 below this score (default 1.0) |
| `--case <glob>`, `--tag <tag…>` | filters. Case directory names are chosen so `--case '01-*'` works |
| `--allow-tools` | operator grant for gated tools (`Bash`, `Write`, `WebFetch`, `mcp__*`) |
| `--max-cost-usd` | hard ceiling; aborts with partial results |
| `--json`, `--report <path>` | machine output, and a self-contained HTML report |
| `--no-publish` | keeps the report local instead of publishing to claude.ai |

`claude plugin eval init [--bare] <name>` scaffolds a suite — an interview by default, or a blank
template. Also gated.

## How this was discovered, so it can be repeated

```bash
claude plugin eval --help          # the layout and every flag

python3 - <<'EOF'                  # the schema, from the binary's validation messages
import re
data = open("/Users/you/.local/share/claude/versions/<version>", "rb").read()
i = data.find(b"either execution.prompt or context.history_file is required")
for s in re.findall(rb"[ -~]{4,}", data[i-9000:i+9000]):
    print(s.decode("ascii", "replace"))
EOF
```

Searching for `case.yaml`, `frontmatter must include`, and `scaffold_script` finds the three clusters
that carry the schema. Nothing here required network access or an entitlement.
