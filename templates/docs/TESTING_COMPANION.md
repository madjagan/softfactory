# Testing {{project_name}} — companion to "Why do we need testing?"

**Date:** {{date}} · **Product:** {{project_name}} · **Numbers:** counted {{date}} from the suites as run.

Part A: what the structured tests already check. Part B: charters for exploring beyond them. Part C: how a discovery gets back into the suites.

---

## Part A — What we already check

### A.1 The suites

| Suite | Where | Files | Tests | Proves | Run |
|---|---|---|---|---|---|
| Unit / component | `{{unit_dir}}` | {{n}} | {{n}} | Screens render, controls act, engines compute the PRD's numbers. Writes mocked. | `{{test_unit}}` |
| Backend | `{{backend_dir}}` | {{n}} | {{n}} | Services, engines, route gates, on a real database. | `{{test_backend}}` |
| End-to-end | `{{e2e_dir}}` | {{n}} | {{n}} | Whole flows with real logins on a fresh-seeded database. | `{{test_e2e}} <spec>` |

All are deploy gates. `{{verify}}` runs before any deploy; the container / CI build runs the suite first; `{{deploy}}` refuses a red gate. No override.

### A.2 Coverage by area

| Area | Backend files / tests | Frontend files / tests | Pinned |
|---|---|---|---|
| {{area}} | — | — | … |

Also: **diagnostic tests** (`{{diagnostic_prefix}}*`) written during exploration, labelled `DEFECT:` while wrong, `FIXED` when fixed. **Every PRD section has a named gate** in `IMPLEMENTATION_PLAN.md`; green file = done.

### A.3 What makes it testable

- **The clock is a seam** — {{clock_seam}}. Tests freeze it; a running server cannot be told another date.
- **One fresh seed per scenario** — the e2e harness rebuilds its database each run. The dev database keeps hand-inspected scenarios.
- **Twin engines** — where a rule lives on both sides, parity tests compare them function by function.
- **Logins** — see `TEST_PLAN_HUMAN.md`.

### A.4 What the tests cannot see

1. **The real date.** Anything keyed on "today" is tested frozen; a live session sees only today.
2. **The mouse.** No scrolling, resizing, dragging, tabbing, second tab.
3. **Screen ⇄ server.** Each half is tested alone. The seam between them is the recurring bug class.
4. **Real data.** Tidy seed records. No odd names, missing fields, contradictory states.
5. **Long horizons.** A few periods, never a year.
6. **The eye.** Layout, contrast, focus order, RTL, PDF appearance.
7. **Declared-but-unread configuration.** A key in a config file that no code reads. Expect nothing from it.

---

## Part B — The exploratory guide

### B.1 Running a session

- One charter, one persona, 60–90 minutes. Stay logged in as that person.
- Do the anchor once by hand. It should work. Then leave it.
- Vary: boundary inputs, different order, skip a step, repeat, combine two features, revisit after a change, same request from another login.
- Write as you go. Report shape in Part C.
- Need a clean slate? Ask for a reseed of the test database; never reseed the shared one yourself.

### B.2 Rule card

The product's numbers and policies a tester can check by hand, in one page. Derived from
the configuration, cited.

{{rule_card}}

### B.3 Charters

Each: Mission · Anchor (do once) · Explore · Look for · Where it goes.

#### C1 — {{module_1_title}}
- **Mission.** …
- **Anchor.** `{{e2e_dir}}/…`, `{{unit_dir}}/…` (none yet → say so)
- **Explore.** …
- **Look for.** …
- **Where it goes.** `{{tests}}` — RED first.

### B.4 Bug classes seen so far

(Filled from the issues log as it grows. At the third instance of a class, a guard test is added.)

---

## Part C — Back into the suites

### C.1 Report it

- **Issue.** One sentence.
- **Current behaviour.** Login, screen, record id, the number.
- **Expected behaviour.** PRD section, rule card, or plain sense.
- **Where it broke, if known.** File and line, API response, database row. A mechanism makes a report a fix; without one it is an investigation. Blank is fine.

File on the issue tracker, or hand to an engineer with `/address-feedback`.

### C.2 The loop

1. **`/find-issues`** — cases, tests with teeth, verdicts. Confirmed defects pinned as `DEFECT:` tests that pass on broken code.
2. **`/fix-issue`** — reproduce, name file and line, fix at source, flip to `FIXED` (RED first), all suites, real flow, issues log.
3. **`/create-feature`** — for a missing capability: dated requirement, RED acceptance test, plan, build, verify, log.
4. **Docs follow.** `FEATURE_LIST.md` is the inventory; the user guides derive from it; the citation hook checks them.

### C.3 The learning questions

- **Add a test?** Always, at the layer the bug lived.
- **Add a category?** At the third instance of a class in B.4, add a guard test.
- **Change expected behaviour?** A dated PRD amendment with its own test. Never a quiet test edit.
