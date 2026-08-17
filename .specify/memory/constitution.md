---
type: Constitution
title: SemantiQL constitution
description: The repo's non-negotiables, taxonomy, tech stack, and governance — what no spec, plan, or implementation may violate.
resource: .specify/memory/constitution.md
tags: [sdd, constitution, semantiql]
generated: { by: claude-code/claude-opus-5, at: '2026-08-15T00:00:00+00:00' }
sources:
  - id: readme
    resource: /README.md
    title: Project README — why, how it works, key ideas, roadmap
    last_modified: 2026-08-14
  - id: architecture
    resource: /docs/02-architecture.md
    title: The 4-layer architecture and why validation matters most
    last_modified: 2026-08-14
  - id: product
    resource: /docs/01-product.md
    title: Product — users, core use case, interface decisions
    last_modified: 2026-08-14
  - id: self-improvement
    resource: /docs/04-self-improvement.md
    title: Two-tier learning model
    last_modified: 2026-08-14
  - id: datasources
    resource: /docs/05-datasources.md
    title: Adapter architecture and datasource roadmap
    last_modified: 2026-08-14
  - id: benchmark
    resource: https://arxiv.org/abs/2405.11706
    title: Allemang & Sequeda — accuracy of LLM SQL with and without a knowledge layer
status: draft
stale_after: 2026-11-15
---

Draft for approval — `status` flips to `stable` once approved. Nothing below is derived from another repo.

# Mission

A semantic layer that lets AI query a database accurately. The AI works against a business model — dimensions, measures, metrics, virtual views — and SemantiQL translates that into correct, validated SQL.[^readme]

Effectiveness means four things at once: high accuracy, consistency, strong capability, low cost.[^product]

# Non-negotiables

These are invariants. A change that would violate one needs its own `specs/NNN-constitution-update-<topic>/` spec at T2, not a judgement call mid-implement.

**N1 — Validation over generation.** Every query is checked against the semantic model before it runs. A query that cannot be verified is blocked, never best-effort executed. The founding evidence: raw-schema LLM SQL scores ~16%, adding a knowledge layer ~54%, adding query checking ~72% — the check earns more than the generator.[^benchmark][^architecture]

**N2 — A silently wrong number is the worst possible failure.** End users are non-technical and never see SQL, so they cannot catch an error.[^product] Refusing to answer beats answering unverifiably. This is the tie-breaker for every design trade-off below.

**N3 — One YAML file is the source of truth.** The semantic model lives in git — reviewable, diffable — and is datasource-independent. Swapping databases must never require rewriting the model.[^readme]

**N4 — Canonical dialect, then transpile.** The engine emits SQL in one canonical dialect and transpiles to the target via sqlglot. Adding a datasource means writing one thin adapter — connect, introspect schema, run query — with **no core changes**. Datasource work that requires core changes is a design smell and needs a spec of its own.[^datasources]

**N5 — Read-only by default.** Setup recommends a read-only database account, and nothing in the query path requires write access.

**N6 — Two learning tiers, permanently separate.** The *examples tier* (verified question → semantic-SQL pairs used as few-shot/RAG) may update automatically. The *YAML schema tier* is **always** human-reviewed. **Never auto-change a metric definition** — schema changes are only ever proposed as diffs for a human to merge.[^self-improvement]

**N7 — No NoSQL.** MongoDB and friends are permanently out of scope, stated in the README to deflect off-topic contributions.[^datasources]

# Taxonomy

| Lives at | Holds |
|---|---|
| `README.md` | the public summary; the roadmap table is canonical |
| `docs/NN-*.md` | design docs — the spec for the system, indexed by `docs/README.md` |
| `specs/` | SDD change records, as an OKF bundle |
| `tests/` | three suites, split by what each one needs — see the rule below |
| `examples/` | the bundled example, and simultaneously the unit suite's corpus |
| `scripts/` | `verify.sh` is the gate: the one command CI and a contributor both run |
| `compose.yaml` | a throwaway database for the `pg` suite; CI starts it from this same file |
| `.specify/memory/` | this constitution |
| `.claude/skills/`, `.claude/agents/` | agent configuration |
| `CLAUDE.md` | agent-facing orientation; mirrors this constitution, never contradicts it |

Two of those carry a rule that outlives any single change.

**A suite that cannot run must skip, never fail.** The unmarked tests need nothing; `e2e` needs a
generated corpus; `pg` needs a database. A fresh clone has to pass the gate with nothing
installed and no network, so neither optional suite may become a hard failure and the gate may
never require Docker.

**`examples/` is test data as much as demonstration.** Its totals are asserted by hand, so a row
cannot be changed without recomputing them.

**Source-code layout is deliberately unassigned**, and stays that way — it is decided by the repo-initialization spec and mapped in [`docs/07-code-map.md`](../../docs/07-code-map.md), not presumed here. The rows above cover the top level only.

# Tech stack

**Python, single runtime.** Decided 2026-08-15, closing the open question this section previously held.

The reasoning, recorded because it will be re-litigated: sqlglot is Python-only, and N4 names it as *the*
transpile mechanism. The rest of the stack follows the hardest constraint rather than working around it —
a Node core would mean either amending N4 for a materially weaker transpiler, or running two runtimes with
IPC between them, paid on every future change. The target user is a data analyst, whose ecosystem is Python
either way.[^product]

| Layer | Choice |
|---|---|
| Runtime | Python 3.11+ |
| Dependencies, distribution | uv; `uvx semantiql` for zero-install runs |
| Dialect transpiling | sqlglot — see N4 |
| MVP engines | DuckDB, then Postgres[^datasources] |
| Semantic model validation | pydantic over the YAML — see N3 |
| Test, lint, types | pytest, ruff, mypy |
| CI | GitHub Actions, secret-free so fork PRs run to completion |
| Claude-facing interface | MCP, official Python SDK |

MIT license, mirrored as the SPDX id in the project manifest.

**Consequence:** `npx semantiql init` in `README.md` and `docs/03-setup-workflow.md` is now wrong, and
becomes `uvx semantiql init`. Correcting it is in scope for the repo-initialization spec — `docs/NN-*.md` is
a trust-boundary artifact, so that edit runs through the lifecycle rather than ad hoc.

Adding an external dependency, connector, or MCP server is never a T1 change.

# Roadmap

| Stage | Scope |
|---|---|
| MVP | DuckDB + Postgres · semantic model YAML · semantic SQL → raw SQL engine · MCP server for Claude · accuracy benchmark vs. raw-table querying |
| Next | MySQL, SQLite · verified-examples loop · `semantiql doctor` |
| Later | BigQuery, Snowflake, Databricks · remote server mode · access control |

The MVP MCP server is **local**, deliberately, with a clear path to remote. Hosting and multi-user auth are out of MVP scope.[^product]

Builder setup must complete in ≤ 15 minutes, every step automatically checked, every error carrying fix instructions. End users never touch a connection string or YAML.

# Governance

- Changing a **non-negotiable** requires its own spec, run at T2 through the full lifecycle.
- Changing a lower-stakes section — a roadmap entry, a tech-stack note — can be proposed as an inline diff and applied on explicit approval.
- No agent edits this file unilaterally. Propose, then wait.
- When this file and `CLAUDE.md` disagree, **this file wins**, and `CLAUDE.md` gets corrected in the same change.

# Trust-boundary artifacts

The files other work resolves against. Touching any of them forces **T2** and, mid-implement, a hard escalation:

- `.specify/memory/constitution.md` — this file.
- `docs/NN-*.md` — the canonical design spec. Code follows these; when code and docs disagree, one of them is a bug.
- The semantic model YAML schema definition, once it exists — every downstream layer resolves against it.
- The query-validation layer, once it exists — N1 and N2 live or die there.
- The project manifest and dependency lockfile, once they exist.
- `.claude/skills/*/SKILL.md` — the procedures agents follow in this repo.

[^readme]: The project README's "Why" and "Key ideas" sections.
[^architecture]: `docs/02-architecture.md`, "Why validation is the centerpiece".
[^product]: `docs/01-product.md`, goal, primary users, and interface decisions.
[^self-improvement]: `docs/04-self-improvement.md`, the two-tier principle.
[^datasources]: `docs/05-datasources.md`, adapter architecture and roadmap.
[^benchmark]: Allemang & Sequeda, arXiv:2405.11706, as cited and marked source-verified in `docs/06-research-notes.md`.
