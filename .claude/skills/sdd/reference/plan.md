# plan phase

Produce `plan.md`. **The Repository Impact Map is the highest-leverage checkpoint in the lifecycle** — and on an autonomous run it is the last thing between a guess and a shipped mistake. Get it right.

## Steps

0. **Tier check.** Read `sdd_tier` from `spec.md` frontmatter.
   - **T1** → impact-map-only mode. Fill in Tier rationale, Constitution check, and Repository Impact Map. Skip Approach, architecture decisions, and open questions. Checkpoint 2 still fires.
   - **T2** → full mode. Every section below.
1. **Identify the active spec dir.**
2. **Read in this order:** the constitution, `spec.md`, then `clarifications.md` if it exists.
3. **Write `plan.md`** — frontmatter, then the sections below. Every file you `Grep` / `Glob` / `Read` while deriving the map gets a `sources` entry here, because that is what makes the map auditable at checkpoint 2:

   ```yaml
   ---
   type: Plan
   title: <spec title> — plan
   description: <one line on the approach>
   resource: specs/NNN-short-kebab-name/plan.md
   tags: [sdd, plan]
   generated: { by: claude-code/<model>, at: '<now>' }
   sources:
     - id: constitution
       resource: /.specify/memory/constitution.md
       title: Repo non-negotiables as read at plan time
     - id: <slug per file or search you actually read>
       resource: <repo-relative path>
       title: <what you learned from it>
       last_modified: <YYYY-MM-DD>
   status: draft
   ---
   ```

   Sections:

### Constitution check

Walk every non-negotiable. For each invariant the change touches, name it and explain how the plan preserves it, footnoting `[^constitution]`. If an invariant would have to be amended, **stop** and open a `specs/NNN-constitution-update-<topic>/` spec first.

Every `sources` entry must be cited by at least one footnote — the validator warns on an uncited source, because a source nothing points at records where you looked rather than what you learned.

### Approach

The tech shape: modules and their interfaces, data flow, the seams tests will run at, external dependencies, config, migration. Prefer existing seams to new ones, and propose any new seam as high as possible.

### Architecture decisions

Numbered, ADR-style. Architecturally significant ones get written into the repo's ADR location during implement.

### Repository Impact Map

Derived from real `Grep` / `Glob` / `Read` of the codebase, never from guessing:

- **Files to modify** — path, what changes, the exact symbols / keys / frontmatter fields affected.
- **Files to add** — path, purpose, shape.
- **Files not touched, but adjacent** — name them, so the user can correct you.

**Every row about an existing file carries a footnote** keyed to the `sources` entry for the file you read:

```markdown
- `src/webhooks/handler.py` — wrap `_deliver` in the backoff loop.[^handler]
```

An unfootnoted row about an existing file is an unverified claim, and checkpoint 2 exists to catch exactly that. Rows under *Files to add* need no footnote — nothing has been read yet. Define every footnote at the bottom of the file.

Where a change has a canonical source and derived copies, call out both explicitly, plus the re-sync step that reconciles them.

### Open research questions

Each resolves to a `clarifications.md` entry, a constitution amendment, or a stated confidence note.

4. **Draft `validation.md`** as a skeleton under `type: Validation` frontmatter (same shape as `plan.md`'s, `status: draft`, no `sources` needed yet): acceptance criteria `AC-1`, `AC-2`, … each traced to an `FR-N`; non-functional acceptance (the repo's verify gate green); and the manual verification steps.
5. **Set `sdd_phase: planning`** in `spec.md`, and append `* **Update**: Plan and impact map drafted [NNN](/NNN-short-kebab-name/plan.md)` to `specs/log.md`.

## Checkpoint 2

Print the Repository Impact Map as the headline of the summary, and flag every open research question.

This is the checkpoint that matters most, and on an autonomous run nothing downstream will catch what it misses. Before attesting, audit your own map: does every row about an existing file carry a footnote to a `sources` entry for a file you actually read? An unfootnoted row is a guess. Fix it or delete it — do not attest around it.

**Autonomous** — record the attestation, naming the evidence, and continue into tasks:

```yaml
verified:
  - { by: claude-code/<model>, at: '<now>', checkpoint: 2,
      basis: 'map derived from <N> reads/greps; all <M> existing-file rows footnoted; <K> open questions resolved as stated' }
```

An open research question you could not resolve from evidence is reported in the run's final report, not silently defaulted. If resolving it either way would change the file list materially, that is a fabrication stop — ask.

**Gated** — stop and wait for "approved" / "map looks right", then record the human entry:

```yaml
verified:
  - { by: human:<id>, at: '<now>', checkpoint: 2, approval: '<their exact words>' }
```
