---
name: address-feedback
description: "Address a piece of user feedback end-to-end: read the actual report → clarify (surface, persona, expected, observed, desired) → classify from evidence (unproven / bug / modification / feature / no-change) → dispatch to exactly one skill (/find-issues, /fix-issue, /create-feature) → close the loop in the register it came from. Use whenever someone hands you a user report, suggestion, complaint or feedback id and wants it dealt with properly. Triggers on: address this feedback, handle this report, a user says, someone reported, triage this, close this feedback, user complaint, user suggestion, act on feedback."
metadata:
  author: "softfactory"
  version: "2.0"
  category: "engineering"
---

# Address Feedback — clarify, classify, dispatch, close

You are the triage front door for user feedback. You do **not** re-implement what
`/fix-issue`, `/create-feature` and `/find-issues` do — you decide *which* owns the
report, hand it a clean brief, and **close the loop in the register the report lives in**
(the in-app feedback register if the product has one, else the tracker, else the issues
log alone).

Two prime directives:

1. **Classify from evidence, not wording.** A report that says "bug" may be the app
   behaving as specified; "small tweak" may be a new requirement. The class comes from
   comparing the app's behaviour to the **written requirement** in the PRD.
2. **The register is the ledger of record.** A report is finished only when its row
   carries a resolution trail and an honest status — and `done` only **after** the
   dispatched skill's own definition of done is met.

Read first: `factory.yaml`, the PRD section that owns the surface, the last twenty
issues-log entries (this may be a reopen).

---

## Operating principles

1. **One report, one class, one skill.** Split mixed reports into separate rows.
2. **Clarify cheaply, don't diagnose.** Root-causing is `/fix-issue`; test strategy is
   `/find-issues`. Do the minimum observation needed to pick the class.
3. **Ask only when a wrong reading changes the work** — one `AskUserQuestion` with options.
4. **Money, statutory and access changes are business decisions.** Confirm before dispatch.
5. **Never invent a date.** Doc entries: `date +%F`. Register writes: the app's own clock
   (if `seed.narrative_date` is set, the app stamps with it — match it).
6. **Delegate noisy searches.**

---

## Phase 1 — INTAKE

- **Given an id** — read the row back (API or tracker CLI), including its trail and
  attachments. Look at screenshots; they settle what three questions would ask.
- **Given free text** — search the open rows for one that already covers it; a match means
  **append**, not a new row. Closed rows are not a dedup target; a recurrence opens fresh.
- **No row exists** — create one so the register stays the ledger, and say which id.

**Gate:** the report verbatim, its id, status, full trail and attachments — read, not assumed.

## Phase 2 — CLARIFY

State all five: **Surface** (module → page → control), **Persona** (role, entity),
**Expected**, **Observed** (the actual message / number), **Desired** (often different
from expected — that gap separates bug from modification).

- Do the cheapest faithful observation: open the owning component, run the one relevant
  test file, or hit the live endpoint. Stop when the class is decidable.
- Grep the PRD and the plan status: is this behaviour specified? Is the module marked
  live or in development? "Nothing happens" against a dev-status screen is a known gap.

**Gate:** *"As <persona> in <surface>, doing X produces Y; the reporter wants Z"* — and
you know whether a requirement covers Z.

## Phase 3 — CLASSIFY (first match wins)

1. **`unproven`** — nobody has shown the behaviour is wrong → `/find-issues`, then re-enter.
2. **`bug`** — a requirement exists and the app disagrees, or it throws / miscomputes /
   drops a write → `/fix-issue`.
3. **`modification`** — the app matches its requirement; the reporter wants the requirement
   changed → `/create-feature` in **amendment** mode.
4. **`feature`** — no requirement covers it → `/create-feature`.
5. **`no-change`** — question, duplicate, working as designed, named non-goal, out of scope
   for this deployment → answer and close `dismissed` with the reason.

Sharp edges: a label change is a modification unless it contradicts a documented string;
a design-system deviation is a bug; a missing test is a gap folded into the underlying class.

**Gate:** the class in one sentence with the evidence that chose it. Torn between bug and
modification means you have not read the requirement — go back, don't coin-flip.

## Phase 4 — OPEN THE ROW

Flip to `in-progress` (or the register's equivalent) with a trail entry naming the class,
surface and skill. Read it back. `no-change` skips to Phase 6.

## Phase 5 — DISPATCH

Invoke exactly one skill via the `Skill` tool with a brief containing, in order: the id,
the Phase-2 sentence, surface (`file:line` where known), persona, observed error verbatim,
class + evidence, in-scope vs out-of-scope, and any business decision the user confirmed.

For a modification add: PRD amendment (not new section); existing tests retargeted, not
deleted; still RED-first against the new behaviour.

Let the sub-skill own its gates. If its evidence contradicts your class, stop and
reclassify in the open.

**Gate:** the sub-skill reports its definition of done met — or a blocker you carry forward.

## Phase 6 — CLOSE IN THE REGISTER

| Outcome | Status |
|---|---|
| Delivered and verified | `done` |
| Won't do / as designed / duplicate / out of scope | `dismissed` + reason |
| Partial or blocked | stays `in-progress` + what remains and who is blocking |

**Never mark done on your own diff.** Tests green but not deployed is not done — say the
deploy is pending. Append the resolution trail in the reporter's language (what changed,
where, how verified). If the register is a whole-array write, **read then append** so the
trail survives. Read the closure back. No backend reachable → say so, state what you
would have written, do not claim closure.

## Phase 7 — REPORT

One line: id, class, what shipped, row status.
*"FB-007 (modification) — list now sorts by date desc; module tests 12 green, gate green, row done."*
Do not commit unless asked.

---

## Definition of done

- [ ] Report read verbatim (or row created); attachments viewed.
- [ ] Five-part clarification; requirement located.
- [ ] One class with evidence; money / access changes confirmed.
- [ ] Row in progress with a triage trail (except no-change).
- [ ] One skill dispatched with the brief; its DoD met or blocker carried.
- [ ] Resolution trail appended, trail preserved, status honest; read back.
- [ ] One-line headline.

## Anti-patterns

- Classifying from the reporter's vocabulary.
- `/fix-issue` on a hunch (that's `/find-issues`).
- A spec change disguised as a bug fix, so the PRD drifts.
- Greenfield `/create-feature` for an amendment.
- `done` before the suite, the flow, or the deploy.
- Overwriting the trail; stamping the register with the wrong clock.
