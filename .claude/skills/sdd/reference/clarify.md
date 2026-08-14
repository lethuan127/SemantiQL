# clarify phase

Resolve ambiguity *before* the plan phase. Ambiguity caught here is cheap; caught after `tasks.md` exists it is expensive.

## Steps

0. **Tier check.** Read `sdd_tier` from `spec.md` frontmatter. At `T1`, add `> clarify auto-skipped: Tier T1` as the first line of the spec body and exit. T1 changes are unambiguous by construction; ambiguity found in a T1 spec means the spec was mis-classified — recommend re-running specify at T2 rather than forcing this phase to run.
1. **Identify the active spec dir** from the user's argument or recent edits. Unclear → ask.
2. **Read `spec.md`** end to end, then the constitution — surface any ambiguity that bumps against a non-negotiable.
3. **Hunt ambiguity** in these categories, in order:
   - **Placement** — which module, package, or layer does this belong to?
   - **Canonical source** — if it adds something that gets copied or bundled, which copy is authoritative?
   - **Coupling** — hidden dependencies on another module's internals, or paths reaching across a boundary.
   - **Edge-case behaviour** — empty inputs, large inputs, repeat invocations, partial failure.
   - **Naming and triggers** — for anything a user or an agent has to *find*, is the name or description a clear enough signal?
   - **Backward compatibility** — does this break an existing entry point, name, or contract?
   - **Auth model** — for anything touching credentials, how does the user supply them?
   - **Surface parity** — does anything assume one platform, client, or environment only?
4. **Resolve each ambiguity.** Autonomous runs decide rather than ask — but the test is strict, and it is the line the whole mode depends on:

   - **Decidable from evidence** → decide it. The constitution, the design docs, the existing code, and the spec are evidence. Record the decision, the options considered, and what made the choice, exactly as if the user had answered.
   - **Would require inventing a fact** → stop and ask. A contact address, a response-time commitment someone must honour, a credential, a licence or ownership question, a product decision with no basis in the repo. There is no defensible default, so a default here is a fabrication.
   - **Decidable but expensive to reverse** → decide, and flag it prominently in the run's report as a judgement call with its alternative.

   Gated runs ask **one question at a time**, as multiple choice with 2–4 options plus "other (please explain)", waiting for each answer before the next.
5. **Record every pair** in `clarifications.md`, under OKF frontmatter:

   ```yaml
   ---
   type: Clarifications
   title: <spec title> — clarifications
   description: <N> ambiguities resolved before planning.
   resource: specs/NNN-short-kebab-name/clarifications.md
   tags: [sdd, clarifications]
   generated: { by: claude-code/<model>, at: '<now>' }
   status: draft
   ---
   ```

   ```markdown
   ## Q1: <question>
   - (a) <option a>
   - (b) <option b>
   - **Chosen:** <option> — <one-line rationale>
   ```

   Each answer is a decision the user made in front of you, so this file is its own source: later phases footnote back to it rather than re-deriving the reasoning. No `verified` entry — this phase carries no gate.

6. **Absorb the answers into `spec.md`**, then set `sdd_phase: planning` in its frontmatter and append `* **Update**: Clarified <N> ambiguities [NNN](/NNN-short-kebab-name/clarifications.md)` to `specs/log.md`.

## Skipping at T2

An already-unambiguous T2 spec may skip this phase. Say so explicitly and record the decision at the top of `spec.md`: `> clarify skipped: spec is unambiguous.`

## Stop condition

Diff-summary what changed in `spec.md`. Autonomous: continue into plan, carrying any unresolved fabrication-stop question into the report. Gated: stop and wait for approval.

Record who decided each pair. A decision you made reads `**Chosen:** … — decided by the agent from <evidence>`; one the user made names them. A later reader must be able to tell the two apart, because they carry very different weight.
