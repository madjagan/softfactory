---
name: create-feature
description: "Add a new feature the disciplined way: dated requirement in the PRD → acceptance tests that define done (RED first) → conflict/risk review + dated implementation-plan entry → implement → verify (tests, full gate, real flow) → mark complete (dated) + issues-log entry. Also runs in AMENDMENT mode for a change to an existing requirement. Use whenever the user wants to add, build, create or change a capability (not fix a bug — that's /fix-issue). Triggers on: add a feature, new feature, build, implement, add capability, add a module, feature request, spec out and build, change the rule, amend the requirement."
metadata:
  author: "softfactory"
  version: "2.0"
  category: "engineering"
---

# Create Feature — spec-first, test-gated delivery

You are adding a feature (or amending a requirement). Run the phases **in order**; each
has a **gate** — do not advance until it is met. Every doc entry is **dated** with
`date +%F` (never guessed).

Prime directive: **the acceptance test is the definition of done.** A feature is complete
only when the test that encodes its requirement passes in the full gate — the rule the
implementation plan states: *a PRD section is feature-complete only when its test file
passes in the verify gate.*

Read first: `factory.yaml` (paths under `docs.*`, commands under `commands.*`, test dirs
under `tests.*`) and `CLAUDE.md` (the house invariants — design system, clock seam, money
rules, whatever the product declares).

---

## Operating principles

1. **Spec before code.** Requirement + acceptance criteria exist before the first edit.
2. **Test-first defines done.** The acceptance test **fails now** (feature absent), then
   passes. A test that was green before you started proves nothing.
3. **Review before building.** Conflicts found mid-implementation mean the review was skipped.
4. **House invariants are law.** Whatever `CLAUDE.md` declares non-negotiable (tokens,
   seams, patterns) applies to every line you add.
5. **Follow the established data/store/API pattern** the repo already uses; grep for a
   sibling feature and copy its shape.
6. **Prove it, don't assume.** Drive the real flow, hit the live API, run the suites.
7. **Minimal, coherent scope.** Build exactly the requirement; list deferrals as non-goals.
8. **Money, statutory and security numbers are business decisions.** If the feature
   changes a computed amount, a legal rate or an access rule, confirm with the user before
   Phase 4.

---

## Phase 1 — REQUIREMENT (dated)

**Goal:** an unambiguous, testable specification in the PRD (`docs.prd`).

- `date +%F` for the stamp. Next section number = last `§3.N` + 1.
- **New feature:** add `### §3.N — <Title>` with: date, one-line **user story** (*As a
  <persona>, I want <capability> so that <value>*), **acceptance criteria** as a numbered
  list of observable, testable statements, **scope / non-goals**, and impact on personas /
  access / data / config.
- **Amendment** (the user wants an existing behaviour changed): do **not** add a new
  section. Under the owning section add `**Amendment (date):** was <old>; now <new>;
  because <reason>` and renumber or reword the affected criteria in place.
- Each criterion must be checkable by a test or a driven interaction.

**Gate:** a reviewer could build and verify the feature from this text alone. If the
request is ambiguous in a way that changes the build, ask ONE question with options.

---

## Phase 2 — ACCEPTANCE TESTS (RED first)

**Goal:** a test file that encodes the criteria and **fails today**.

- Pick the layer that proves the criteria (from `tests.*` in the manifest):
  - UI / module → `tests.unit_dir/<feature>.test.*`: render + interactions; expectations
    computed from the data, writes mocked the way sibling tests do it.
  - Backend / workflow → `tests.backend_dir/test_<feature>.*` and/or an e2e spec under
    `tests.e2e_dir` against a fresh-seeded DB.
  - Spans both → cover the write round-trip **and** the rendered result.
- Write assertions against the *intended* behaviour. Run the file with `commands.test_one`
  (or the layer's runner) and **capture that it is RED for the right reason** (feature
  absent — not a syntax error).
- **Amendment:** existing tests asserting the old behaviour are **retargeted, not
  deleted**; name each one and why in the plan entry. The test is red against the *new*
  behaviour while the old assertions currently pass.

**Gate:** the acceptance test exists, targets the criteria (not a proxy), and is
observed red for the right reason.

---

## Phase 3 — CONFLICT / RISK REVIEW → dated plan entry

**Goal:** a thorough pre-build review, then a dated row in the plan (`docs.plan`).

- **Conflicts (grep, don't guess):** route / nav / store / name collisions, duplicate data,
  access rules and feature gates, API contract shape, seed / migration impact, cross-
  dataset integrity tests, the CI / Docker test gate.
- **Risks:** data-shape mismatch between API and page (the recurring bug class), breaking
  existing tests, reseeding a shared DB, hot-patch vs durable deploy, scope creep.
- Write the plan row: feature, scope, **the acceptance test file as its gate**, risks with
  mitigations, status **`In progress (YYYY-MM-DD)`**.

**Gate:** no unresolved blocking conflict; every material risk has a mitigation; the plan
entry is written and dated. A blocking conflict → surface it and stop for a decision.

---

## Phase 4 — IMPLEMENT

**Goal:** the smallest coherent change that satisfies every criterion.

- Check branch / worktree rules first; note untracked WIP a fresh worktree would not hold.
- Follow the sibling pattern: new page → wire the router + access map + nav + feature
  flag / gate entry; new data → seed + store + hydrate; writes → API endpoint → re-hydrate.
- Backend: model / router / service + serialization contract + seed; keep the API shape
  flat and identical to what the page reads.
- Stay within the requirement; append extras to the non-goals list instead of building them.

**Gate:** the code loads and compiles; you can say, per criterion, which lines satisfy it.

---

## Phase 5 — VERIFY

**Goal:** prove the feature works and nothing regressed.

- The Phase-2 test now **passes** — the same file, unchanged assertions.
- Full gate green: `commands.verify`. Backend touched → `commands.test_backend`; workflow
  touched → `commands.test_e2e` on the new spec.
- **Drive the real flow** end to end in the running app / live API (`commands.run_dev` or
  the local stack). Tests alone do not close this phase. If you hot-patched a running
  container to verify, say so; a durable deploy still needs `/release`.

**Gate:** acceptance test green + full gate green + the real flow observed working.

---

## Phase 6 — MARK COMPLETE (dated)

- Flip the PRD section and the plan row to **`✅ Complete (YYYY-MM-DD)`**.
- Add or update the feature's row in the feature list (`docs.feature_list`): stable id,
  req id, maturity `●` only if an engine computes it and a test pins it, else `◐`.
  (The feature-list hook will ask for a user-guide reconciliation — let it.)
- Append to the issues log (`docs.issues_log`), `---` separated: `## §3.N — <title>`,
  date, acceptance test file, files changed, verification result.
- Report: what you checked, then a one-line self-contained headline. Do not commit unless asked.

---

## Definition of done

- [ ] Dated requirement (or amendment) with testable criteria in the PRD.
- [ ] Acceptance test written and observed RED before implementation.
- [ ] Conflict/risk review done; dated, risk-annotated plan entry naming the gate.
- [ ] Implemented within the house invariants and the sibling pattern, within scope.
- [ ] Acceptance test GREEN; full gate green; real flow driven.
- [ ] PRD + plan flipped Complete (dated); feature list row; issues-log entry.

## Anti-patterns (reject)

- Code before requirement and red test.
- A test that passes before the feature exists.
- Skipping the review and finding collisions mid-build.
- Complete on green units without driving the real flow.
- A greenfield section for what is really an amendment; deleted tests instead of retargeted ones.
- Undated entries, or a guessed date.
