# specify phase

Produce `spec.md` — what and why, with no tech in it.

## Steps

1. **Read the constitution.** The spec must respect every non-negotiable.
2. **Pick the next `NNN`** by listing `specs/` and incrementing the highest number. Pad to three digits.
3. **Choose a `short-kebab-name`** — 2–5 words, lowercase, dashes, naming the change (`add-webhook-retries`, not `fix-stuff`).
4. **Suggest the branch** `NNN-short-kebab-name`, and recommend rather than enforce `git checkout -b NNN-short-kebab-name`.
5. **Determine the tier** by applying the T1 qualification rule to the requested change. Any condition failing, or any doubt → T2. State it with a one-line rationale; autonomous runs proceed on it, and the user may override at any point.
6. **Ensure the bundle exists.** Absent `specs/index.md`, create it carrying `okf_version: "0.2"` frontmatter and an `# Specs` heading. Absent `specs/log.md`, create it with an `# Update Log` heading. These are OKF's only two reserved filenames, and only the root `index.md` may carry frontmatter.

7. **Create `specs/NNN-short-kebab-name/`** and write `spec.md` — frontmatter first, then the body.

   ```yaml
   ---
   type: Spec
   title: <descriptive, not generic>
   description: <one line — this is what the index shows>
   resource: specs/NNN-short-kebab-name/spec.md
   tags: [sdd, spec]
   generated: { by: claude-code/<model>, at: '<now, ISO 8601 with offset>' }
   sources:
     - id: constitution
       resource: /.specify/memory/constitution.md
       title: Repo non-negotiables as read at spec time
   status: draft
   sdd_phase: drafting
   sdd_tier: <T1 | T2>
   ---
   ```

   No `verified` yet — checkpoint 1 hasn't fired. No `stale_after`, ever.

   Body sections:

   - **Tier rationale** — one line on why T1 or T2, matching `sdd_tier`.
   - **What** — one paragraph of user-visible behaviour. No tech, no architecture, no implementation.
   - **Why** — the concrete problem, with a real user scenario.
   - **User stories** — at least two.
   - **Functional requirements** — numbered `FR-1`, `FR-2`, …, each testable.
   - **Non-functional requirements** — naming the specific constitutional invariants that apply, footnoted `[^constitution]`.
   - **Out of scope** — what's tempting here but deferred.

   The title lives in frontmatter — don't repeat it as an `# H1`. At T1, keep the body under 25 lines.

8. **Add the bundle entries**, one line each:

   - `specs/index.md` → `* [NNN-short-kebab-name/](NNN-short-kebab-name/) - <tier>, drafting - <description>`
   - `specs/log.md` → `* **Creation**: Spec drafted [NNN](/NNN-short-kebab-name/spec.md)`, under today's `## YYYY-MM-DD` heading, newest first.

9. **Write nothing else.** `plan.md`, `tasks.md`, and `validation.md` belong to later phases.

Use the project's domain vocabulary throughout — `CONTEXT.md` and the ADRs, where the repo keeps them.

## Generator scripts

When the repo has a scaffolder that writes real files (`scripts/new-plugin.py` and friends), running it is **a task inside the plan**, not a shortcut around it — its output is a code change, and code changes start from a written spec. So: spec the thing being scaffolded, record checkpoint 1, and let the first task of `tasks.md` be the scaffolder invocation plus a check that its output matches the impact map.

One carve-out: the user explicitly wants a scaffold to experiment with, no PR. Run it, and remind them that committing the output needs a spec first.

## Checkpoint 1

Print the spec dir path, the branch suggestion, and the spec in two or three sentences.

**Autonomous** — record your own attestation and continue straight into clarify:

```yaml
verified:
  - { by: claude-code/<model>, at: '<now>', checkpoint: 1,
      basis: '<N> FRs, each testable; NFRs name the invariants they are bound by' }
```

**Gated** — stop and wait. On an explicit approval, record the human entry instead:

```yaml
verified:
  - { by: human:<id>, at: '<now>', checkpoint: 1, approval: '<their exact words>' }
```

Never write a `human:` entry on an autonomous run. See the conditions in `SKILL.md`.
