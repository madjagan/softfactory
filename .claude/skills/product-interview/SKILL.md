---
name: product-interview
description: "Interview the product owner on the command line and write the product summary that /setup-project consumes: personas, Osterwalder's value proposition canvas per primary persona (jobs to be done, pains, gains → products & services, pain relievers, gain creators, fit), the component tools, inspiration and alternatives, 3-month success metrics, stack and deploy. Pushes back on vague answers, plays every section back for confirmation, writes docs/PRODUCT_SUMMARY.md as it goes and resumes from it. Triggers on: product interview, write the product summary, discover the product, value proposition, jobs to be done, pains and gains, who is this for, interview me about the product, before setup-project."
metadata:
  author: "softfactory"
  version: "1.0"
  category: "product"
---

# Product Interview — from an idea in someone's head to a summary a factory can build

You are interviewing the product owner, in this terminal, to write the product summary
(`docs.product_summary`, default `docs/PRODUCT_SUMMARY.md`) that `/setup-project` turns into
the manifest and the ledger. Run the rounds **in order**; each ends in a **gate**. Stamp the
file with `date +%F` — never a guessed date.

Prime directive: **every line in the summary is the owner's, confirmed.** You ask, probe,
restate and structure; you never fill a gap with a plausible guess. Anything the owner has
not confirmed is marked `[assumed]` or goes to §7 Open questions.

The frame is Osterwalder's **value proposition canvas**: a *customer profile* (jobs, pains,
gains — true of the persona whether or not the product exists) matched to a *value map*
(products & services, pain relievers, gain creators — what the product does about it). The
product is clear when the two sides **fit**.

---

## Operating principles

1. **One topic per turn, at most three questions.** A wall of questions gets a wall of
   shallow answers.
2. **Open questions as plain text; closed choices with `AskUserQuestion`.** Use the tool for
   picks and ranks (which persona is primary, a pain's severity, a gain's level, MoSCoW,
   stack options) — never for "describe your user".
3. **Concrete over abstract.** For every pain ask for *the last time it happened*; for every
   job, *what they do today*. "Users want it to be easier" is not an answer — ask easier
   than what, measured how.
4. **Jobs and pains are about the persona, not the product.** If an answer names a feature
   ("they need a dashboard"), ask what the dashboard is for — that is the job.
5. **Play back before moving on.** End each round with the section as it will be written,
   and get a yes or a correction.
6. **Write as you go.** After each confirmed round, write that section into the file. A
   broken session loses one round, not the interview.
7. **Respect "skip".** The owner can skip or defer any question; record it in §7 with why it
   matters, and move on.
8. **Stay out of the solution's details.** Screens, schemas and APIs belong to
   `/create-feature`. Here the product is described by what it does for whom.

---

## Round 0 — PREPARE

- `date +%F`. Read `factory.yaml` if it exists (`docs.product_summary`, `project.*`).
- **Resume mode:** if the summary file exists and is filled past the template (no `{{`
  left in a section), show the owner which sections are done and ask whether to resume at
  the first open one, revise a named section, or start over.
- **Seed notes:** if the owner passed a path (Obsidian markdown, an image of a sketch), read
  it first and pre-fill your understanding — then confirm it in the rounds below rather than
  skipping them.
- Tell the owner the shape in one line: about nine short rounds, each played back, written
  as it goes, any question skippable.

**Gate:** you know whether this is a fresh, resumed or seeded interview, and the owner has
agreed to start.

---

## Round 1 — SNAPSHOT

Ask: the product's working name, and what it does in one sentence for whom. Then ask what
made them want to build it now.

**Gate:** a name and a one-liner the owner accepts. (The positioning statement at the top of
the file is written last, in Round 9.)

---

## Round 2 — PERSONAS (customer segments)

- Ask who uses it, and who pays or decides if that is someone else. Get 1–4 personas; for
  each, the context in which they meet the product (when, where, how often).
- `AskUserQuestion`: which persona is **primary** (multi-select up to two). Only primary
  personas get a full canvas; the others keep a row in §1.

**Gate:** §1 confirmed and written.

---

## Round 3 — JOBS TO BE DONE (per primary persona)

- Ask what the persona is trying to get done — not with the product, in their work or life.
- Shape each job as *When I …, I want to …, so I can …*, and tag its kind:
  **functional** (a task), **social** (how they want to be seen), **emotional** (how they
  want to feel). Probe for one social or emotional job if only functional ones come up.
- Ask what they do today to get each job done (this seeds Round 7).
- `AskUserQuestion` to rank the jobs by importance to the persona.

**Gate:** 3–7 ranked jobs per primary persona, each in the When/want/so shape, confirmed.

---

## Round 4 — PAINS

- For the top jobs, ask what is annoying, slow, risky or blocked before, during and after.
- For every pain: *when did this last happen, and what did it cost them?* Record the
  concrete instance.
- `AskUserQuestion` for severity (1 = mild annoyance … 5 = they would pay to make it stop),
  then rank.

**Gate:** 3–7 pains per primary persona, each with a concrete instance and a severity.

---

## Round 5 — GAINS

- Ask what a great outcome looks like, and what would delight them.
- Tag each gain's level: **required** (nothing works without it), **expected** (basic
  hygiene), **desired** (they would ask for it), **unexpected** (they would not think to ask).
  Probe for one unexpected gain.
- `AskUserQuestion` to rank.

**Gate:** 3–7 ranked gains per primary persona, each tagged with a level.

---

## Round 6 — VALUE MAP, FIT AND COMPONENT TOOLS

- Ask which products and services the product offers — these are the **component tools**.
  For each: a one-word module id, what it does in one sentence.
- For each **top-3 pain**, ask which tool relieves it and how; for each **top-3 gain**, which
  tool creates it. Build the fit table; a pain or gain nothing addresses is marked `open`
  — say so out loud and ask whether that is deliberate.
- A tool that serves no job, pain or gain: ask what it is for, or drop it.
- `AskUserQuestion` for MoSCoW per tool.

**Gate:** every top-3 pain and gain has a fit row (strong, partial or open-by-decision);
every tool serves something; §2 value map and §3 written.

---

## Round 7 — INSPIRATION & ALTERNATIVES

- From Round 3's "what they do today": for each alternative (a competitor, a spreadsheet, a
  person, doing nothing), what it gets right and where it fails them.
- Ask which products or ideas inspire this one — and for each, what to borrow and what not
  to copy.

**Gate:** at least one alternative (doing nothing counts) and §4 confirmed.

---

## Round 8 — SUCCESS METRICS AND STACK

- **Metrics:** ask what would make the owner call this a win in three months. For each
  metric: today's value (or "unknown"), the target, and how it will be measured. Push back
  on vanity metrics with no link to a ranked job or pain.
- **Stack & deploy:** `AskUserQuestion` with options for frontend, backend and end-to-end
  tests (offer what the owner usually builds with first, from memory or the global
  CLAUDE.md); then plain-text questions for deploy target, environments and seed or demo
  data. "Not decided" is a valid answer — it goes to §7, and `/setup-project` will ask again.

**Gate:** 1–4 metrics each with a target and a measurement; §6 filled or deferred to §7.

---

## Round 9 — PLAYBACK AND WRITE

- Write the positioning statement at the top from the confirmed rounds.
- Print the whole summary once; ask for corrections in one pass. Apply them.
- Check the file: `grep -n "{{" <summary path>` finds nothing; `[assumed]` items are in §7.
- Set **Status** to `Confirmed (date)`, or `Draft (date)` if §7 has open items the owner
  wants to settle first.
- Hand off: the next move is `/setup-project`, which reads this file when given no argument.

**Gate:** the owner says the summary is right.

Do not commit unless asked.

---

## Definition of done

- [ ] §1 personas with a primary marked; one full canvas per primary persona.
- [ ] Ranked jobs (When/want/so, kind-tagged), pains (instance + severity), gains (level).
- [ ] Value map and a fit row for every top-3 pain and gain; every tool serves something.
- [ ] Alternatives and inspiration; 1–4 measured success metrics; stack or deferral.
- [ ] No `{{` left; unconfirmed items in §7; status and date stamped from the shell.
- [ ] The owner confirmed the playback; next move `/setup-project` stated.

## Anti-patterns

- Filling a section from your own idea of the product, or writing it without a playback.
- Pains with no concrete instance; jobs that are really features ("use the dashboard").
- A component tool list written before the jobs, pains and gains — it becomes a wish list.
- Ten questions in one turn, or `AskUserQuestion` for an open-ended answer.
- Treating "skip" as "make something up".
- Designing screens, schemas or APIs in the interview.
