---
name: fix-issue
description: "Diagnose and fix a bug described in natural language via a disciplined, gated pipeline: description → reproducibility → root cause → fix → regression test → ensure no regression → log. Use whenever something is broken and should be fixed properly (not a quick patch). Triggers on: fix bug, fix issue, \"X is not working\", \"clicking does nothing\", broken, throws, diagnose, root cause, regression, \"why is this failing\", \"it crashes when\"."
metadata:
  author: "Solo Product Toolkit"
  version: "2.0"
  category: "engineering"
---

# Fix Issue — disciplined bug-fix pipeline

You are fixing a bug described in natural language (the invocation argument or the user's
message, possibly with a tracker key or a screenshot). Run the seven phases **in order**;
each has a **gate**.

Prime directive: **prove, never assume.** The symptom, the root cause, the fix working and
the absence of regressions are each demonstrated with a command, a test or a direct
observation — not asserted from reading code.

Read first: `factory.yaml` (`commands.*`, `tests.*`) and `CLAUDE.md`.

---

## Operating principles

1. **Reproduce before theorizing.** A bug you cannot reproduce, you cannot prove you fixed.
2. **Symptom → exact mechanism.** Name the `file:line` and the data flow that produces it.
3. **Minimal blast radius.** The smallest change at the source; opt-in over global.
4. **Consistency with existing patterns.** Grep for how siblings solve the same class;
   the sibling that *avoids* the bug is usually the fix template.
5. **The regression test must reproduce the original failure.** It fails before the fix
   and passes after.
6. **Verify at the boundary that broke.** If it broke in the running app or live API,
   verify there, not only in a unit that mocks that layer.
7. **Delegate noisy searches** to a subagent; keep the findings.
8. **Money, legal and access changes need the user's explicit confirmation** before
   Phase 4, whatever the report says.

---

## Phase 1 — DESCRIPTION

**Goal:** an unambiguous restatement.

- Restate: the exact flow (`login → Module → Tab → action`), expected vs observed, the
  surface (module / page / endpoint / component) and the environment (persona, data,
  local vs deployed, build).
- If a tracker key was given, read the issue and its screenshots first
  (`python3 tools/issues_cli.py show KEY`, `shots KEY`).

**Gate:** one sentence — *"When the user does X, Y happens instead of Z, in surface S."*
Ask ONE clarifying question only if a wrong guess is costly; otherwise state your reading.

---

## Phase 2 — REPRODUCIBILITY

**Goal:** trigger the failure deterministically and capture the *actual* error.

- Locate the owning code path. Reproduce by the cheapest faithful means:
  - UI bug → drive the real app or the render path; a click that "does nothing" is usually
    an unhandled throw — check for an error boundary.
  - API / data-shape bug → hit the **live endpoint** with real auth and inspect the real
    response; the static seed shape often hides it.
  - Logic bug → a minimal failing check or the existing test that should have covered it.
- Capture the exception, the input and the state that produce it, and any trigger
  (only after login / hydration / a persona) — that trigger is a root-cause clue.

**Gate:** the actual error and the exact conditions, observed. "It probably fails
because…" does not pass.

---

## Phase 3 — ROOT CAUSE

**Goal:** the single precise mechanism, proven.

- Trace backward from the captured error through serializers, stores, adapters, gates.
- Separate symptom from cause: `undefined.toFixed()` is the symptom; *why it is undefined*
  is the cause.
- **Show the smoking gun:** the live payload, the differing shape, the null, the off-by-one.
  Quote `file:line`.
- Check the siblings: do they share the pattern (also broken) or avoid it (how?).

**Gate:** exact `file:line` + mechanism, backed by an observation, and an explanation of
why it manifests only under the Phase-2 trigger.

---

## Phase 4 — FIX

**Goal:** the minimal root-cause change, consistent with the codebase.

- Check branch / worktree rules; edit only files you have confirmed exist.
- Fix at the layer that produces the wrong value, not in every consumer. Prefer an
  opt-in / allow-list narrowing over a global behaviour change. Reuse the sibling pattern.
- No unrelated refactors, defensive noise or scope creep.

**Gate:** the change is written and loads; you can state why it cannot affect paths
outside its intended scope.

---

## Phase 5 — TEST

**Goal:** a regression test that reproduces the original failure and now passes.

- Add it at the layer where the bug lived (contract test for an API shape; e2e assertion
  on the real endpoint; render test for a component throw). Assert the specific broken thing.
- Confirm it has teeth: run it against the pre-fix code (stash the fix, or revert
  mentally with the exact assertion) so you know it would have failed.
- If existing tests missed the bug, write *why* (e.g. they used the flat static seed and
  never exercised the hydrated shape). If this is the third instance of that class, add a
  guard test for the class, not just the instance.

**Gate:** the new test targets the exact failure and passes with the fix.

---

## Phase 6 — ENSURE NO REGRESSION

**Goal:** prove the fix is safe and complete.

- Full gate: `commands.verify`. Backend touched → `commands.test_backend`. Workflow
  touched → `commands.test_e2e` on the relevant spec (fresh-seeded DB).
- Shared code touched → demonstrate the other consumers behave byte-for-byte as before.
- Re-run the Phase-2 reproduction in the environment that broke; it must now succeed.
- Hot-patched a running container? Say so; the durable deploy is `/release`.

**Gate:** all suites green + neighbours proven unchanged + the original reproduction passes.

---

## Phase 7 — LOG

Append to the issues log (`docs.issues_log`), `---` separated, the next `#N`:
**Date · Reported symptom · Area · Root cause (file:line, mechanism) · Fix · Files changed
· Verification · Deploy note**. Match the existing entries' shape.

If the report came from the tracker, `/process-issues` writes the verdict; if from the
in-app register, `/address-feedback` closes the row. This skill writes the log entry in
every case.

---

## Definition of done

- [ ] Issue restated (surface, expected vs observed, environment).
- [ ] Failure reproduced; the *actual* error captured.
- [ ] Root cause proven to `file:line` + mechanism.
- [ ] Minimal fix at the source, in the sibling pattern.
- [ ] Regression test added that would have failed before and passes now.
- [ ] Full suites green; neighbours unchanged; reproduction now passes.
- [ ] Issues-log entry appended.
- [ ] Report: what was checked, then a one-line self-contained headline. No commit unless asked.

## Anti-patterns (reject)

- Fixing the symptom in the consumer while the source keeps emitting bad data.
- A global change when a narrow one suffices.
- "Fixed" without re-running the reproduction.
- A test that passes before and after.
- Unrelated refactors bundled into the fix.
