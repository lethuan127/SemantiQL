# Update Log

## 2026-08-15
* **Update**: Published to a public remote after a clean pre-push audit; ownership commentary and work addresses redacted from the change records first [001](/001-init-project-scaffold/spec.md)
* **Update**: Implemented 001 autonomously — 15 of 16 tasks; working Python package, 23 tests, verify gate green on 3.11 and 3.13. T14/AC-9 blocked on the missing conduct address; AC-6/8/12 partial pending a remote [001](/001-init-project-scaffold/tasks.md)
* **Creation**: Plan and impact map drafted — src-layout package with one module per architectural layer, `adapters/base.py` as the N4 seam, one verify script CI also calls. 4 files to modify, 27 to add. Three open questions for gate 2, the live one being that `uvx semantiql` cannot work before PyPI [001](/001-init-project-scaffold/plan.md)
* **Creation**: Clarify resolved four questions — Python+uv runtime, GitHub-only security reporting (5-day ack), a personal CoC contact (value still pending), weekly-triage no-SLA review. FR-8..FR-11 made concrete; phase moves to planning [001](/001-init-project-scaffold/clarifications.md)
* **Update**: Gate 1 passed — spec approved by human:thuan.le, recorded as a `verified` entry; phase moves to clarifying [001](/001-init-project-scaffold/spec.md)
* **Update**: Scope confirmed — 001 stays a single spec covering all 15 FRs; the three-way split was considered and declined because the setup, CI, and quickstart commands are the same commands [001](/001-init-project-scaffold/spec.md)
* **Update**: Added three engineer comprehension stories and FR-14 (layer→module orientation, adapter seam) and FR-15 (positioning vs Cube, dbt Semantic Layer, MetricFlow, Malloy) [001](/001-init-project-scaffold/spec.md)
* **Update**: Runtime decided — Python 3.11+ with uv, closing the constitution's open tech-stack question; sqlglot being Python-only was the forcing constraint. Adds FR-13 to 001 for correcting the stale `npx semantiql init` in README and docs [constitution](../.specify/memory/constitution.md)
* **Update**: Folded the open-source artifacts into 001 — FR-8..FR-12 (SECURITY, CoC, CONTRIBUTING, README support line, issue/PR templates); FR-6 tightened to require fork-PR CI without secrets. Public push recorded as out of scope, gated on licensing confirmation [001](/001-init-project-scaffold/spec.md)
* **Creation**: Spec drafted for repo initialization, gate 1 pending [001](/001-init-project-scaffold/spec.md)
* **Creation**: Bundle opened — `index.md` and `log.md` at `specs/`
