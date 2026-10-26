---
name: find-issues
description: "Investigate whether a piece of functionality actually works: strategize a layered test plan, fold in the user's hunches as hypotheses to falsify, enumerate typical + boundary + negative + state + integration + permission cases, then write, code and EXECUTE tests to prove which issues are real. Diagnostic only — finds and proves defects, never fixes them (hand off to /fix-issue). Triggers on: does X actually work, test this thoroughly, find the issues, I have a hunch, is this wired up, verify the behaviour, audit this feature, probe for bugs, edge cases, what could break, sweep."
metadata:
  author: "Solo Product Toolkit"
  version: "2.0"
  category: "engineering"
---

# Find Issues — strategize, code and run tests to prove what is broken

You are investigating whether a functionality behaves correctly. Your job is to **find and
prove issues**, not to fix them. Six phases **in order**, each with a **gate**.

Prime directive: **prove, never assume.** "Looks wired" or "looks broken" from reading
code is a hypothesis. Every issue reported — and every "this part is fine" — is
demonstrated by a test that ran.

Output: a **verdict per behaviour** — CONFIRMED ISSUE (with the test that proves it), NOT
AN ISSUE (with the test that would have caught it), or INCONCLUSIVE (and why). A clean
sweep that found nothing is a valid, valuable result.

Read first: `factory.yaml` (`commands.*`, `tests.*`, `seed.*`, `personas`), the PRD
section that owns the behaviour, and `CLAUDE.md`.

---

## Operating principles

1. **Hunches are hypotheses.** Record the user's hunch verbatim as Hypothesis #1 and try
   hard to prove it FALSE; if it survives, it is real.
2. **Localize the break.** Design tests so the failing layer says *where* the chain snaps.
3. **Teeth.** A test that passes regardless of the bug proves nothing.
4. **Verify at the boundary that matters.** A claim about what a user sees → drive the
   real component; about an API shape → hit the live endpoint.
5. **Comprehensiveness beats cleverness.** Enumerate systematically.
6. **Never leave the suite red.** Characterization tests that pin *current* (wrong)
   behaviour must PASS and be labelled `DEFECT:`; `/fix-issue` flips them to `FIXED`.
7. **Delegate noisy searches** to a subagent.

---

## Phase 1 — SCOPE & INTAKE

- Restate the functionality: surface, intended contract (quote the PRD criterion), owning
  code and its collaborators (store, serializer, router, gate).
- Intake hunches as hypotheses; if none, plan a full sweep. ONE clarifying question only
  if the target is genuinely ambiguous.

**Gate:** surface, intended behaviour, owning code and the hypothesis list are named.

---

## Phase 2 — CASE ENUMERATION

Enumerate across every dimension that applies:

- **Happy path**
- **Boundary:** empty / one / many, min / max, first / last, zero, off-by-one, period edges
- **Negative / invalid:** bad input, missing record, unauthorized, wrong type, null, duplicate
- **State & persistence:** survives re-render, navigation, reload, re-hydrate; optimistic vs source of truth
- **Integration:** the action reaches the thing it should affect, not just local state
- **Identity / permission:** each persona in `factory.yaml`; does gating hold at the API too?
- **Concurrency / ordering:** double-submit, stale snapshot, write-vs-rehydrate race
- **Time:** if the manifest names a clock seam, freeze it at the edges the rule cares about
- **This repo's known bug classes:** read the issues log's last twenty entries and the
  testing companion §B.4; add a case per class

**Gate:** a written checklist, each case mapped to a hypothesis or dimension, ordered so
a failure localizes the break.

---

## Phase 3 — TEST STRATEGY (layered)

- **L1 Positive control** — does the surface react at all in isolation?
- **L2 Persistence** — does an effect survive unmount / reload?
- **L3 Source of truth** — does it reach the object / endpoint the system depends on?
- **L4 End-to-end** — from the real user flow, does the intended outcome occur?

Assign each case a layer and a tool (unit runner, backend runner, e2e harness, live probe)
and state in advance what result confirms vs refutes each hypothesis.

**Gate:** every case has a layer, a tool and a pass/fail meaning.

---

## Phase 4 — WRITE & CODE THE TESTS

- Unit / integration → `tests.unit_dir`, in the repo's conventions; e2e → `tests.e2e_dir`
  (fresh-seeded DB); backend → `tests.backend_dir`.
- Name files with `tests.diagnostic_prefix` and a short strategy comment at the top.
- Label defect-documenting assertions `DEFECT:` in the test name.
- Each suspected-defect test exercises the actual failing path and asserts the observable
  wrong / right result.

**Gate:** tests written, load, and target the exact behaviours (no proxy assertions).

---

## Phase 5 — EXECUTE & CLASSIFY

- Run the focused files first (`commands.test_one`), then the relevant layer suites.
- Verdict per case: **CONFIRMED ISSUE** (cite `file:line` mechanism + layer) · **NOT AN
  ISSUE** (a teeth-having test passed) · **INCONCLUSIVE** (what is needed).
- Leave the suite intentionally green; explain any deliberate red.

**Gate:** every case has a verdict backed by a run.

---

## Phase 6 — REPORT (+ log)

- Lead with the verdict on the user's hunch.
- Layered results table (which layer passed, which broke).
- Per confirmed issue: symptom → mechanism (`file:line`) → proving test → suggested severity.
- Why it slipped (which existing test gave false confidence).
- Hand-off: `/fix-issue` per confirmed issue, in the order you recommend.
- Append a **Diagnostic** entry to the issues log (`## Diagnostic — <scope> (date)`:
  cases, verdicts, tests added). Do not fix here.

---

## Definition of done

- [ ] Contract restated; hunches captured.
- [ ] Case list across all applicable dimensions, mapped to layers.
- [ ] Real tests with teeth, in repo conventions, labelled.
- [ ] Executed; every case has a verdict backed by a run.
- [ ] Suite intentionally green.
- [ ] Report + diagnostic log entry + `/fix-issue` hand-off.

## Anti-patterns

- "Broken / fine" from reading code.
- Tests that pass regardless.
- Happy path only when the hunch is about an edge.
- Mocking away the suspect layer.
- Fixing here.
