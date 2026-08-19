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

The complete schema, recovered from the Zod definition embedded in the binary. Every field, default and
bound below is read from that definition rather than inferred.

```yaml
schema_version: "1.0"          # required. Major must be ≤ 1; this binary writes "1.1"
name: build-the-model          # required, non-empty
description: …                 # optional
tags: []                       # default []
plugins: […]                   # optional — which plugins to load

context:                       # default {add_dirs: []}
  scaffold_script: ./setup.sh  # optional; runs only with --scaffold
  history_file: …              # optional; the alternative to execution.prompt
  add_dirs: []                 # default []

execution:                     # required
  prompt: |                    # optional — but one of this or context.history_file must exist
    …
  max_turns: 10                # default 10, integer, 1..200
  timeout_seconds: 300         # default 300, integer, 1..3600
  model: sonnet                # optional
  allowed_tools: []            # default []
  append_system_prompt: …      # optional
  env: {}                      # default {} — string to string

runs: 3                        # default 3, integer, 1..50
expected_outcome: …            # optional

graders:                       # required, at least one, names must be unique
  - type: llm
    name: asks-before-writing
    criteria: |
      …
```

**`execution` carries seven fields, not one.** `max_turns` and `timeout_seconds` are the two that bite:
both have defaults that are fine for a toy case and wrong for real work, and the authoring guide
embedded beside the schema is blunt about the second — *"an under-set timeout reads as a 0 score, not a
timeout"*. A case that does database discovery will exceed 300 seconds and be scored zero for it.

Validation messages, verbatim:

- `case.yaml must be a YAML object`
- `missing required field schema_version (e.g. "1.0")`
- `schema_version "X" is not a valid version string`
- `schema_version "X" requires a newer Claude Code (this binary supports up to N.x)`
- `either execution.prompt or context.history_file is required`
- `duplicate grader name "X"`

## Graders

Six types. **Every schema is `.strict()`**, so an unknown key is an error rather than something the
runtime tolerates — and **every grader requires a `name`**, which must be unique within the case.

| Type | Fields |
|---|---|
| `regex` | `name`, `pattern`, `target` = `last_message`, `flags` = `""`, `match` = `contains`, `weight` = 1, `arm?` |
| `tool_used` | `name`, `tool`, `input_match?`, `min?`, `max?`, `weight` = 1, `arm?` |
| `tool_order` | `name`, `before`, `after`, `weight` = 1, `arm?` |
| `file_exists` | `name`, `path`, `exists` = `true`, `weight` = 1, `arm?` |
| `llm` | `name`, `criteria`, `focus` = `last_message`, `weight` = 1, `arm?` |
| `baseline` | `name`, `baseline_file`, `criteria`, `weight` = 1, `arm?` |

**`target` and `focus` are the same union**, and note that `llm` spells it `focus` while `regex` spells
it `target` — a `.strict()` schema means using the wrong one is a hard error:

```
trace | last_message | files | {source: file, path: <path>}
```

- `flags` must be JS RegExp flags — `d g i m s u v y`.
- `match` is `contains`, `not_contains`, or `count:N`.
- `arm` is `with-only` or `both`, and it matters under ablation.
- `tool_used.min` defaults to **1**. For "must NOT call tool X" the guide is explicit: set `min: 0`,
  `max: 0` **and** `arm: both` — omitting `min` leaves it at 1, and omitting `arm` on `tool: Skill`
  makes the grader display-only.

**`files` is a list of paths, not contents.** As a `target`/`focus` it is the newline-separated list of
files *created* during the run — paths only, and a file that existed before the run never appears even
if it was modified. `file_exists` reads that same list, so a pre-existing file grades as **absent**. To
grade what is inside a created file, use `{source: file, path: …}`.

## The `prompt.md` shape

The same case expressed as files. A grader's **filename is its `name`**, and its markdown **body**
becomes the field named for its type: `criteria` for `llm` and `baseline`, `pattern` for `regex`.

```
evals/
└── 01-say-hello/
    ├── prompt.md
    └── graders/
        ├── greets-by-name.md
        └── friendly-tone.md
```

`graders/` sits **inside** the case directory — that was an open question here and the guide's own
example settles it.

`prompt.md` frontmatter has two allowlists, and a key outside both is an error naming every accepted
key:

| Goes to the case | Goes to `execution` |
|---|---|
| `schema_version`, `name`, `description`, `tags`, `plugins`, `runs`, `expected_outcome` | `model`, `max_turns`, `timeout_seconds`, `allowed_tools`, `append_system_prompt`, `env` |

Caps worth knowing: a prose `.md` is capped at **1 MiB**, and `graders/` at **256** files.

## What the embedded guide says about writing them

Shipped in the same binary, and more opinionated than the schema:

- **Every case runs twice** — with the plugin and without — so the headline number is **Δ, the uplift**,
  not the pass rate. `--ablation with-without`.
- **Prefer verifiable graders.** The stated hierarchy is ① regex / `file_exists` / exit code ②
  binary criterion ③ n-ary ④ llm rubric ⑤ preference, and *"use llm only when ①-② can't capture it"*.
  Four of the six types are deterministic; a rule like "never ran `psql`" is a fact and belongs in a
  `regex` grader with `match: not_contains`.
- **Use a big judge, and not the agent's own model.** *"Small judges miss nuance"*, and a judge that is
  the same model as the agent has a self-preference. `--judge-model sonnet` or larger.
- **Set `timeout_seconds` on every case.** An under-set timeout scores 0 and looks like a failure.
- **No absolute paths and no `~/`** in prompts or graders: cases run in a sandbox cwd.
- **Read `evals/results/*/aggregate-result.json`.** If `suite.plugins` is `[]` the plugin did not load
  and the whole run is meaningless. Its top-level `costUsd` is one run of one arm pair — multiply by
  `runs` for the real bill.
- **An implausible score jump is judge-gaming until proven otherwise**, by hand.

## What is still not established

- **How `case.yaml` and `prompt.md` merge** when both exist. There is a merge function — case fields
  win at the top, `execution` is spread over, graders concatenate — but the precedence has not been
  exercised.
- **Whether `plugins:` names a marketplace id or a path.**
- **Everything above is read from version 2.1.226.** An undocumented format can change silently, so
  re-run the recipe below before trusting this against a newer CLI.

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

Searching for `case.yaml`, `frontmatter must include`, and `scaffold_script` finds the clusters that
carry the schema. **The binary embeds its own minified JavaScript**, so the Zod definition itself is
readable once you find it — search for `schema_version:Le.string()` and print a few kilobytes as ASCII.
That is where every default and bound on this page came from, and it is far better evidence than the
error strings alone. Nothing here required network access or an entitlement.
