---
type: Clarifications
title: Initialize the SemantiQL repo — clarifications
description: Four ambiguities resolved before planning — runtime, security channel, conduct contact, review turnaround.
resource: specs/001-init-project-scaffold/clarifications.md
tags: [sdd, clarifications]
generated: { by: claude-code/claude-opus-5, at: '2026-08-15T01:10:04+07:00' }
status: stable
---

Decisions the maintainer made in front of the agent. Later phases cite this file rather than re-deriving the
reasoning. No `verified` entry — the clarify phase carries no gate.

## Q1: Which runtime does the repo commit to, given sqlglot is Python-only but the docs promise `npx`?
- (a) Python + uv, single runtime
- (b) Node/TS core + Python sidecar for sqlglot
- (c) Node/TS, drop sqlglot for a JS transpiler
- **Chosen:** (a) — sqlglot is named by N4 as *the* transpile mechanism, so the stack follows the hardest
  constraint rather than working around it; (b) costs two runtimes on every future change, (c) amends N4 for
  a materially weaker transpiler. Recorded in the constitution's tech-stack section; user-visible consequence
  is FR-13.

## Q2: What private channel does FR-8 publish for vulnerability reports?
- (a) GitHub private vulnerability reporting only
- (b) GitHub reporting plus a published email fallback
- (c) A faster 48-hour acknowledgement window
- **Chosen:** (a), with **acknowledgement within 5 business days** and a fix or timeline within 30 days — no
  inbox to monitor and no published address that can rot, and a window that is actually meetable.

## Q3: What reporting contact does FR-9's Code of Conduct name?
- (a) a work address
- (b) an alternate work address
- (c) A personal address, unconnected to either employer
- (d) Defer the Code of Conduct entirely
- **Chosen:** (c) — a personal address is consistent with the personal copyright in `LICENSE`, and it
  survives a change of employer.
- **⚠ Value still pending.** The specific address was not supplied. FR-9 cannot ship until it is: an agent
  inventing one would publish a conduct-reporting channel nobody reads, which is the failure the requirement
  exists to prevent. This blocks the FR-9 implement task only — it does not block planning.

## Q4: What review turnaround do FR-10 and FR-11 promise?
- (a) Best-effort, weekly triage, no SLA
- (b) First response within 3 business days
- (c) No response commitment, stated explicitly
- **Chosen:** (a) — honest for an early-stage solo project and consistent with the README's design-phase
  framing. Carries the corollary that large unsolicited PRs should start as an issue, which FR-10 states.
