---
type: Spec
title: An eval suite for the plugin, over real ERP data
description: Native evals/ cases for the three things the plugin does — build a model, answer from it, enrich it — graded against the rules from shipped specs, on real SAP ERP sales data.
resource: specs/021-plugin-eval-suite/spec.md
tags: [sdd, spec]
generated: { by: claude-code/claude-opus-5, at: '2026-08-18T15:37:58+00:00' }
sources:
  - id: constitution
    resource: ../.specify/memory/constitution.md
    title: Repo non-negotiables as read at spec time
    last_modified: 2026-08-17
  - id: native-format
    resource: ../plugin/evals/01-build-the-model/prompt.md
    title: The native layout, taken from claude plugin eval --help and two official plugins
    last_modified: 2026-08-18
  - id: profile-spec
    resource: ../specs/020-profile-through-semantiql/spec.md
    title: The rules the graders encode, and the run that motivated them
    last_modified: 2026-08-18
  - id: eval-record
    resource: ../plugin/README.md
    title: The PluginEval scores and the judge's 0.9375 structural ceiling
    last_modified: 2026-08-18
status: stable
verified:
  - { by: claude-code/claude-opus-5, at: '2026-08-18T15:37:58+00:00', checkpoint: 1,
      basis: 'Formats were read from the shipped CLI help and from two official plugins on disk (math-olympiad trigger_eval.json, skill-creator evals.json plus its schema reference), not invented. The gate on  was verified as an account entitlement in a compiled binary rather than a local flag, which is what makes authoring-now-running-later the correct shape. Scope covers exactly the three phases the user named. A draft of the three case directories was written before this lifecycle was invoked; it is treated as input to be reviewed here, not as settled work.' }
sdd_phase: shipped
sdd_tier: T2
---

**T2.** Adds a directory to `plugin/`, which is shipped product, and takes on a **non-commercial
licensed dataset** whose handling has to be got right. Neither is a T1 change.

# What

The plugin carries an eval suite in the layout `claude plugin eval` reads, covering the three things
it actually does:

| Case | The question it answers |
|---|---|
| `01-build-the-model` | given a real database, does it inspect, ask, and write a model without improvising SQL? |
| `02-ask-a-business-question` | does it answer from the model, and **report the gap** when it cannot? |
| `03-enrich-the-model` | asked to change what a word means, does it disclose what moves? |

Each case is a `prompt.md` and a `graders/criteria.md`. The criteria are the rules from shipped specs
written as gradeable statements, so a behaviour that took four specs to establish cannot quietly
regress.

**Today there is nothing.** Reliability rests on `tests/interfaces/test_plugin.py`, which asserts the
skill *says* things. Nothing checks whether a model *does* them, and the one time that was checked by
hand it found two defects (specs 018 and 020).

# Why

**The rules exist and nothing exercises them.** Spec 016 excluded row profiling in a spec; a run
ignored it. Spec 018 found the skill teaching a command that does not run. Spec 020 found a run reading
every figure it quoted with raw `psql`. Each was found by a human watching one run. That is not a
process, and the fix each time was a drift test asserting the *prose* — which catches deletion of a
rule, never disobedience of it.[^profile-spec]

**The native runner is gated, and that changes the deliverable rather than cancelling it.**
`claude plugin eval` exists in the shipped CLI, its layout is documented in `--help`, and running it
answers *"is currently in early access"* with exit 1. The binary is compiled and the gate is an account
entitlement, not a local flag. So the suite is authored to the native layout and runs the day access
arrives; until then the corpus is still the artefact that states what correct behaviour is, and the
tests still keep it valid.[^native-format]

**Real ERP data is the point, and it was blocked until now.** The earlier attempt used NYC taxi trips —
real, and not a sales domain. SAP's SALT dataset is **authentic S/4HANA sales data**: sales documents,
document items, customers, addresses. It was gated behind a licence needing an organisation and a
non-commercial declaration, which is not a declaration an agent may make. The repository owner has now
accepted it and put a token in `.env`, so the fixture can be real ERP data rather than a proxy for it.

Why that matters for the evals specifically: an ERP schema is where the hard questions are *native*.
Net versus gross versus tax, document versus item grain, multiple currencies, credit memos as negative
values, and column names like `NetAmount` that a human still has to sanction. A model built over it is
the real exercise.

**Amendment, measured after the token arrived: SALT is still blocked, one step short.** The token in
`.env` is valid — Hugging Face's `whoami` returns 200 for user `lethuan127` with a fine-grained token —
and `SAP/SALT`'s metadata reads `gated: auto`. But a file request returns **403** with the dataset's own
message: *"Access to dataset SAP/SALT is restricted and you are not in the authorized list. Visit
https://huggingface.co/datasets/SAP/SALT to ask for access."* So the credential works and the
authorisation does not exist yet; accepting the terms on that page with that account is the one
remaining step, and it is not a step an agent may take.

The consequence for this spec, stated rather than absorbed: **FR-7's loader is built and its failure
path is the thing that has been exercised**, and the graders quote figures from the NYC fixture already
loaded rather than from ERP columns. Swapping the fixture is one command once access lands, because the
loader is finished and the graders name their source. What is *not* claimed is that these graders have
been calibrated against real ERP data.

**Second amendment: the fixture is UCI Online Retail II, not SALT.** With SALT blocked, the choice was
between waiting and finding real data that is actually reachable. Online Retail II is 1,067,371 real
invoice lines from a UK gift-ware retailer, 2009-12-01 to 2011-12-09, **CC BY 4.0** — attribution only,
no account, no gate.

It is a weaker domain match and a **stronger test**, which is worth stating plainly rather than
presenting the substitution as equivalent. Weaker, because it is retail transactions rather than ERP
sales documents. Stronger, because **there is no revenue column**: sales are `quantity * unit_price`,
a SemantiQL measure maps to one column, and so the headline metric cannot be modelled directly at all.
The correct answer is a database view, and a run that instead sums `unit_price` produces a meaningless
number that looks fine. No fixture anyone invented would have produced that trap so cleanly, and it is
now the pivot of the build case.

Also native to it: credit notes carried as negative quantities (19,494 lines), 243,007 lines with no
customer id, and naive timestamps that must **not** receive a `timezone:`.

# User stories

- **As a maintainer**, I run one command and learn whether the plugin still obeys the rules four specs
  established — instead of reading a transcript by hand and hoping I notice.
- **As a maintainer**, the corpus tells a new contributor what correct behaviour *is*, in gradeable
  sentences, without them reading twenty specs.
- **As the repository owner**, the licensed dataset is fetched on demand and never committed.

# Functional requirements

- **FR-1** — Three cases exist under `plugin/evals/`, one per phase, each a `prompt.md` plus
  `graders/criteria.md`, in the layout `claude plugin eval` documents.
- **FR-2** — Each grader states its rules as **Must** and **Must not**, each traceable to a shipped
  spec, and defines how to score.
- **FR-3** — The build grader requires: reads through `inspect`/`profile`, **no raw SQL client**, **no
  write**, asks before writing, prices the choice with real numbers, gets the timezone question right
  in both directions, loops on `doctor`.
- **FR-4** — The ask grader requires `describe_model` first, `DATE_TRUNC` for a grain, figures not SQL,
  and **reporting the gap** for a dimension the model lacks rather than substituting a near-miss.
- **FR-5** — The enrich grader requires the change be a reviewed edit, quantified, with the statement
  that **past numbers move**, then `doctor`.
- **FR-6** — A trigger corpus in the official `trigger_eval.json` shape covers all three phases plus
  negatives that must **not** trigger.
- **FR-7** — A fetch script loads SALT into Postgres, reading `HF_ACCESS_TOKEN` from the environment or
  `.env` **itself** — the token is never printed, passed on a command line, or committed.
- **FR-8** — No SALT data is committed. The dataset is CC-BY-NC-SA-4.0; the fetch script is the artefact
  and the data is output.
- **FR-9** — Tests validate the corpus: layout, unique ids, both trigger polarities present, every case
  has a grader, and every CLI verb a grader names is a verb the CLI dispatches.
- **FR-10** — Documentation states plainly that the native runner is gated, what to run instead, and
  that the suite is ready when access lands.

# Non-functional requirements

- **Never commit secrets** — the token stays in `.env`, which is already ignored, and the script reads
  it without echoing it. This is the constitution's rule and the repo's tightest one.[^constitution]
- **Licence discipline** — CC-BY-NC-SA-4.0 is non-commercial and share-alike. Fetch-on-demand keeps the
  repository free of it; the licence is named wherever the fixture is described.
- **CI stays secret-free and dependency-light** — the suite must not enter `scripts/verify.sh` as a
  *run*. Its **validation** may, because that is free and offline.[^constitution]
- **N6** — the enrich case is the one that could teach the wrong thing. Its grader must reward stopping
  and proposing when the request arrives mid-answer, and only reward editing when the change was asked
  for deliberately.[^constitution]
- **Trust boundary** — `plugin/` is shipped product. If `SKILL.md` changes as a result, that is called
  out separately.

# Out of scope

- **Enabling the gated runner.** It is an account entitlement; routing around it is not on the table.
- **Making the evals a CI gate.** Running them costs money and needs a database and a licensed dataset.
- **Splitting the skill in two** to lift the PluginEval judge past its 0.9375 ceiling. Recorded in
  `plugin/README.md` and still its own spec.[^eval-record]
- **Automating the self-improvement loop.** The enrich case tests that a *requested* change is handled
  well. A model proposing enrichments unprompted is a different feature and the README lists it as not
  built.

[^constitution]: `.specify/memory/constitution.md` — never commit secrets, CI secret-free, N6, and the trust-boundary artifact list.
[^native-format]: `claude plugin eval --help` for the layout; `math-olympiad/skills/*/evals/trigger_eval.json` and `skill-creator/skills/*/references/schemas.md` for the two official corpus shapes.
[^profile-spec]: `specs/020-profile-through-semantiql/spec.md` — the raw-`psql` finding, and 016's unenforced exclusion.
[^eval-record]: `plugin/README.md` — the recorded PluginEval scores and the scope ceiling.
