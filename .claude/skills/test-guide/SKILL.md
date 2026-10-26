---
name: test-guide
description: "Write a customer tester's guide for one module, feature or use case — logins and rules, numbered click-by-click steps in parts, exact control labels verified against the source, a must-be-refused table, how to repeat the test, where to report. One page, for a non-developer. Offers (never builds unasked) the screenshot storyboard and narrated videos via /guide-screenshots. Triggers on: test guide, tester's guide, how do I test X, steps for the customer, walkthrough for testers, user help for X, /test-guide."
metadata:
  author: "Solo Product Toolkit"
  version: "1.0"
  category: "documentation"
---

# Test guide — one module, feature or use case, for the customer's tester

The argument names the subject: a module (*Invoices*), a feature (*bulk export*) or a use
case (*a customer cancels and is refunded*). The output is **`docs/<SUBJECT>_TEST_GUIDE.md`**
in the shape below (`templates/docs/TEST_GUIDE_TEMPLATE.md`; an existing guide in `docs/` is
the standard of terseness — read one first). The reader is the customer's tester, not a
developer: no code names, no internals, no reasoning. Every line is something to do or
something to expect.

This is the **user-help half** of the factory's documentation: the per-persona user guides
(`docs-agent`) say what the product does for a role; a test guide says exactly which clicks
prove one subject works, on the test site, today.

Read first: `factory.yaml` (`environments.*`, `personas`, `seed.*`, `docs.*`), the PRD
section(s) for the subject, the feature-list rows, and the screen's source.

## Procedure

1. **Establish the facts — from the source, not from memory.**
   - **The requirement:** the PRD sections for the subject and their feature-list rows. What
     it does, what it refuses, and why.
   - **The screen:** the page component(s), the sidebar route and its labels, the tab and
     button labels **as rendered** — grep the UI source for the exact text. A label the guide
     gets wrong stops a tester cold (a guide that says *Run export* for a button that reads
     *Export now* leaves the tester looking for a button that isn't there; the screenshot capture
     catches it).
   - **Who may do it:** the access map, the server gate on the route (which roles, which
     states), and the seeded logins for those roles (`personas` + the seed users).
   - **The rules that block:** calendar / sequence / lock / eligibility gates on the server.
     Each becomes a row of *Must be refused*, with the message the tester will see.
   - **The state of the test site that matters:** what exists today that the tester meets
     first (the newest record, a person already in a special state). Read it from the API
     when it changes the steps; state it under *Rules*.
2. **Walk it once yourself** on the local stack or a read-only pass of the test site, so the
   order of clicks is the app's order, not the PRD's.
3. **Write the guide** to `docs/<SUBJECT>_TEST_GUIDE.md`, dated (`date +%F`), with the build
   it was written against (the version stamp the app shows).
4. **Verify every label:** for each bolded control in the guide, grep the exact string in the
   UI source. A miss is a guide bug — fix the guide, or if the label is wrong in the app, say so.
5. **Offer the follow-ons in one line each; do not build them unasked:** the annotated
   screenshot storyboard and the narrated per-part videos — both `/guide-screenshots <guide>`.

## The shape (mandatory)

```
# <Subject> — tester's guide
*<test site host> · build NNN · YYYY-MM-DD*

## Rules
- Who signs in (named seeded logins and their roles). Who cannot.
- The one or two rules that shape the whole flow (order, calendar, one-per-record …).
- What the test site holds today that the tester meets first.

## <Part title — a verb phrase>          (2–4 parts; step numbers continue across parts)
1. **Menu → Submenu → Tab**. What to press, in bold, as the app reads it.
2. …expect: the visible result, in the app's words (status chip, message, count).

## Must be refused
| Try | Expect |
|---|---|
| the gated action | the exact refusal, or the missing control |

## Repeating the test                       (only when the flow is not freely repeatable)
- How to run it again: reset, reopen, wait for the calendar, an alternative route.
- What needs the team, and the exact words to ask with.

## Reporting
Board entry with build number (where the app shows it), login, the record, screenshot.
```

## Style rules

- Direct and crisp: a step is one line, imperative, ≤ 20 words. No paragraphs, no rationale,
  no "you may want to". A sentence that explains why is cut, or moved to *Rules* as a fact.
- Bold exactly the words on the control; arrows (→) for the path; role names as the app
  shows them; ids and dates in the app's own format.
- One page. If it will not fit, the subject is two guides.
- Say what to *expect* after any step whose result is not obvious, in the app's words.
- Refusals are worth testing: every server gate gets a row.
- Dated, with the build; regenerate after a UI change to that screen.

## Anti-patterns

- Labels from memory or from the PRD instead of the rendered source.
- Steps a tester cannot take on the test site today without saying so in *Rules* and giving
  the practice route.
- Explaining the design. The tester wants clicks and expectations.
- Building screenshots or videos without being asked; offer them.
