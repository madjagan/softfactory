---
name: setup-project
description: "Stand up the Solo Product Toolkit in a repo from a product summary: write factory.yaml (the manifest every other skill reads), the docs ledger (PRD skeleton with the first dated requirement sections, implementation plan with test gates, issues log, feature list, human test plan, testing companion, user-guide index), CLAUDE.md house rules, the test gates and deploy path, and the issue tracker. Idempotent — re-run to fill gaps. Triggers on: set up the factory, setup project, bootstrap this repo, new project, initialise the ledger, start a product from a summary, factory init."
metadata:
  author: "Solo Product Toolkit"
  version: "1.0"
  category: "engineering"
---

# Setup Project — from a product summary to a working factory

You are turning a product summary (the invocation argument, a pasted brief, or a file the
user points at; with no argument, `docs/PRODUCT_SUMMARY.md` as written by
`/product-interview` — if that is still the unfilled template, offer to run the interview
first) into a repo that runs the **setup → develop → deploy → grow → evolve** loop. Run
the phases **in order**; each ends in a **gate**. Everything you write into a doc is a
**dated entry** stamped with `date +%F` — never a guessed date.

Prime directive: **the ledger comes before the code.** A repo is "set up" when a stranger
can read `factory.yaml`, the PRD and the plan and know what the product is, what is
required, what is built, and which command proves it. Code is optional at this stage;
the ledger is not.

The factory's own files (skills, agents, hooks, tracker, tools, templates) come from the
Solo Product Toolkit repo via `install.sh`. This skill does not copy them; it assumes they are in
place (`ls .claude/skills tools/factory.py templates/`) and stops with instructions if not.

---

## Operating principles

1. **Ask once, in one batch.** Collect every unknown the manifest needs in a single
   `AskUserQuestion` (stack, deploy target, personas, module list). Never drip questions.
2. **Existing repo wins.** If the repo already has tests, a deploy script, docs or a
   CLAUDE.md, read them and write the manifest *around* them. Never overwrite a file that
   has content the template does not; merge and say what you kept.
3. **Every manifest command must run.** A command you write into `factory.yaml` is one you
   have executed (or, for deploy, dry-run) in this session. An untested command is a lie
   the next skill will trip on.
4. **Requirements are dated, numbered, testable.** The PRD starts with real sections
   derived from the summary, each with a user story and observable acceptance criteria,
   not a table of contents.
5. **Honesty in the feature list.** Nothing is marked live that has no engine and no test.
6. **Delegate noisy searches.** Mapping an existing codebase goes to a subagent; keep the
   findings, not the dumps.

---

## Phase 1 — INTAKE (what is this product?)

**Goal:** the seven facts the manifest needs, from the summary or the user.

Extract from the summary; ask for what is missing, in one question:

| Fact | Where it goes |
|---|---|
| Name, slug, owner, one-paragraph summary | `project.*` |
| Stack per layer (frontend / backend / e2e / design system) | `stack.*` |
| Personas and what each may reach | `personas[]` |
| Modules / areas (8–20 one-word ids) | `issues.modules`, PRD §3 layout |
| Test commands per layer + the full verify gate | `commands.*` |
| Deploy path and environments | `commands.deploy`, `environments.*` |
| Seed / demo data facts (password, narrative date, notable records) | `seed.*` |

For an **existing repo**, launch an Explore subagent first: package manifests, test dirs,
CI files, deploy scripts, existing docs. Bring back the commands it found and whether they
run green.

**Gate:** you can fill every non-optional key in `factory.example.yaml` without guessing,
and you have run (or dry-run) each command you will write.

---

## Phase 2 — MANIFEST

- Copy `templates/factory.yaml` → `factory.yaml` at the repo root and fill it. Keep the
  comments; the next reader needs them.
- Run `python3 tools/factory.py check`. It lists missing docs — expected now; Phase 3
  creates them. Any *command* gap it reports must be fixed here.

**Gate:** `python3 tools/factory.py dump` prints the manifest with no placeholder values
left (`Acme`, `example.com`, `TODO`).

---

## Phase 3 — THE LEDGER (docs/)

Copy each template from `templates/docs/` to the path the manifest names, then **fill it
from the summary** — a template with `{{placeholders}}` still in it is not done. Use
`date +%F` for every stamp.

| File | What to write |
|---|---|
| `PRODUCT_SUMMARY.md` | The input, not an output: keep it as written. If the summary came from elsewhere, copy it in under the template's headings; `[assumed]` items stay marked. Its component tools are the module list, its primary personas lead §2 of the PRD, its fit table seeds each §3 user story, and its §7 open questions join Phase 1's single batch of questions. |
| `PRODUCT_REQUIREMENTS.md` | §1 purpose and principles from the summary; §2 personas from the manifest; **§3 one dated section per module** (`§3.N — <Module>`), each with a user story, 3–8 numbered observable acceptance criteria, scope / non-goals, RBAC and data impact. Mark each `Planned (date)`. |
| `IMPLEMENTATION_PLAN.md` | Phase table (0 test infrastructure · 1 ledger · 2 modules · 3 hardening · 4 backlog); **one row per PRD §3.N naming the test file that is its gate**, status `Planned`. |
| `issues_log.md` | Header only, plus entry `#0 — Factory set up` (date, what was created, which commands were verified). |
| `FEATURE_LIST.md` | §0 how to read it; §2 personas; §3 one row per intended feature with a stable id (`AREA-NN`), req id, MoSCoW, maturity `◐` (nothing is `●` yet); §7 explicit out-of-scope from the summary; §8 empty gap register. |
| `WHY_WE_NEED_TESTING.md` | Copy as-is (it is product-independent). |
| `TESTING_COMPANION.md` | Part A with the three suite rows from `commands.*` (counts `0` are fine), the "what tests cannot see" list; Part B with **one charter per module**, anchor left as `(none yet)`; Part C verbatim. |
| `TEST_PLAN_HUMAN.md` | Header (environments, logins from personas, seed facts) and **one section per module with 2–5 rows**, each one observable expectation citing its PRD criterion. |
| `RELEASE_LOG.md` | Header only. |
| `SEEDING.md` | Which seeders exist, which is safe, what `reseed` does; if none, say so. |
| `user-guide/README.md` | Persona table from the manifest; provenance note pointing at the feature list. |
| `issues_classified.json` | From `templates/issues_classified.json` with the project name in `meta`. |

Then `CLAUDE.md`: from `templates/CLAUDE.md`, filled with the quick-start commands, the
docs map, the architecture in five lines, the invariants the summary implies (design
system, clock seam, money rules — whatever applies), and the "adding a module" recipe.

**Gate:** `python3 tools/factory.py check` prints `manifest ok`; `grep -rn "{{" docs
CLAUDE.md` finds nothing; every PRD §3 section has numbered acceptance criteria.

---

## Phase 4 — GATES AND TRACKER

- **Test gate.** `commands.verify` runs and exits 0 (an empty suite passing is fine on a
  new repo; a missing runner is not). If the repo has a Dockerfile or CI file, confirm the
  suite runs inside it *before* the build step; if it has neither, add the CI workflow from
  `templates/ci.yml` adapted to the manifest commands.
- **Deploy gate.** `commands.deploy` exists and **refuses when verify is red** (read the
  script; add the refusal if absent). Do not deploy in this skill.
- **Tracker.** `pip install -r issues/requirements.txt`, then
  `eval "$(python3 tools/factory.py env)" && python3 -m uvicorn issues.app:app --port 3002`
  in the background; `curl -s localhost:3002/api/meta -H 'X-Role: tester'` shows the
  project's brand, prefix and modules. Run `python3 -m pytest issues/tests -q`. Stop the
  server afterwards unless the user wants it up.
- **Hook.** `.claude/settings.json` carries the feature-list hook; touch the feature list
  and confirm the hook fires once (it prints an `additionalContext` block).

**Gate:** verify green, deploy refuses on red (shown, not assumed), tracker answers with
the manifest's modules, hook fires.

---

## Phase 5 — MEMORY AND HAND-OFF

- Write the project's first memory files under the Claude project memory dir: one
  `project` memory with the deploy target and the reseed rule, one `reference` memory with
  the tracker URL. Index them in `MEMORY.md`.
- Append to `issues_log.md` entry `#0` what was verified.
- Report: the manifest summary (name, stack, commands), the ledger files created, the
  gates proven, and the **next three moves** — usually `/create-feature` for the first
  PRD section, `/test-pack` once one module is live, `/release` for the first deploy.

Do not commit unless asked.

---

## Definition of done

- [ ] `factory.yaml` complete; every command executed or dry-run in this session.
- [ ] PRD with dated §3 sections and numbered acceptance criteria; plan with a named gate per section.
- [ ] Issues log, feature list, human test plan, testing companion, release log, seeding note, user-guide index, classified JSON all present and filled.
- [ ] `CLAUDE.md` written or merged.
- [ ] Verify gate green; deploy refuses on red; tracker up with the project's modules; hook fires.
- [ ] Memory written; entry `#0` in the issues log; next three moves stated.

## Anti-patterns

- Writing the manifest from the summary alone and never running a command.
- A PRD that is a table of contents with no acceptance criteria.
- Marking anything `●` live on day one.
- Overwriting an existing CLAUDE.md or docs instead of merging.
- Guessing the date.
