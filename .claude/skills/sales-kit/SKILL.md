---
name: sales-kit
description: "Produce sales material from the messaging ledger, for a persona (a reusable kit) or for one prospect (a tailored kit): a one-page leave-behind, a demo script whose steps come from the test guides with labels verified in the source, a discovery call guide built from the persona's jobs and pains, a battlecard per alternative, and a proposal with scope and a UAT plan drawn from the human test plan (HTML that prints to PDF). Prospect kits add an outreach email and two follow-ups. Written to docs/sales/ (gitignored). Every claim cites MESSAGING.md or the ledger; ◐ rows say 'in development — available soon'; nothing invented; Claude drafts, the owner sends. Triggers on: sales kit, one-pager, leave-behind, demo script, call guide, discovery questions, battlecard, proposal, outreach email, prospect, pitch to, /sales-kit."
metadata:
  author: "softfactory"
  version: "1.0"
  category: "growth"
---

# Sales kit — what to send, show and ask, for one persona or one prospect

You are producing sales material from `docs.messaging`. Run the phases **in order**; each ends
in a **gate**. Stamp with `date +%F`.

Prime directive: **the kit says nothing the messaging ledger can't prove.** It chooses, orders
and tailors what `MESSAGING.md` and the ledger already hold. When the kit needs a claim that
isn't there, the fix is `/messaging`, not a sentence written here.

**Invocation:** `/sales-kit <persona-id>` for a persona kit, or `/sales-kit <prospect>` plus
notes, a URL or a file for a prospect kit.

Read first: `factory.yaml` (`docs.*`, `marketing.*`, `stack.design_system`), then
`docs.messaging` — **if it is missing or still the template, stop and offer `/messaging`.**
Then `docs.feature_list`, `docs.prd`, `docs.test_plan_human`, the test guides
(`docs/*_TEST_GUIDE.md`) and their storyboards (`docs/screenshots/<subject>/`), and
`docs.release_log`.

---

## Operating principles

1. **Traceable claims.** Every statement cites `MESSAGING.md` (section and row) or a ledger
   `file:line`; features as `AREA-NN (FEATURE_LIST.md:NNN)`. Citations sit in an HTML comment
   or a "Sources" footnote, so the buyer reads clean copy and the owner can still check it.
2. **Never invented:** customers, logos, testimonials, quotes, counts, case studies,
   certifications, prices beyond `MESSAGING.md` §4, and facts about competitors beyond summary
   §4 or a cited public page.
3. **◐ rows are part of the offer**, each followed by *in development — available soon*, with no
   date. §7 won't-haves appear only as proposal exclusions.
4. **Drafts only.** Every artefact is a file. Never send email, post, book meetings or write to a
   CRM, and never call a tool that would.
5. **Prospect facts are labelled:** "owner's notes (date)" or a public URL with the date read.
   Nothing about a named individual beyond a public company or profile page the owner points to.
6. **Labels as rendered.** Every control named in the demo script greps to the UI source, as
   `/test-guide` requires.
7. **The design system is law** for the HTML artefacts, as in `/marketing-site`.

---

## Phase 1 — TARGET

- **Persona kit:** confirm the persona id is a primary persona in `MESSAGING.md` §2.
- **Prospect kit:** read the owner's notes (and fetch a URL if given). Write a short prospect
  brief: who they are, the persona they map to, which of that persona's pains they have shown
  (with the evidence), what they use today (→ which alternative), and what is unknown. Label
  every fact. Ask the owner, in one round, to confirm the persona mapping and fill the gaps that
  change the kit.
- `mkdir -p docs/sales/<target>` where `<target>` is the persona id or the prospect's slug.
  Confirm `docs/sales/` is in `.gitignore`; add it if not.

**Gate:** the target maps to one house in `MESSAGING.md`, and (for a prospect) every fact in the
brief is labelled.

---

## Phase 2 — BUILD THE KIT

| Artefact | File | How |
|---|---|---|
| One-pager | `one-pager.html` | From `templates/sales/one-pager.html`: the roof, the three pillars (for a prospect, ordered by the pains they've shown), one storyboard frame labelled "Example", the CTA from `marketing.*`. Fits one printed A4/Letter page |
| Demo script | `demo-script.md` | 5–8 steps. Each: what to click (from a test guide, labels verified), the seeded record to use, **the pain it relieves** (fit row), what to say (one or two sentences from the house), and the storyboard frame. Ends on the strongest pillar |
| Call guide | `call-guide.md` | Opening (30-second pitch); discovery questions from the persona's jobs and pains ("When did … last happen? What did it cost?"); a qualification table — does the prospect have each top-3 pain? (yes / no / unknown, with evidence); the likely objections from §3 with their answers; next-step options |
| Battlecards | `battlecards.md` | One per alternative in summary §4: what it is, where it wins (be honest), where we win (sourced), questions that surface the difference, what **not** to claim |
| Proposal | `proposal.html` | From `templates/sales/proposal.html`: the problem (the prospect's pains, or the persona's for a persona kit), proposed scope (chosen feature rows, ◐ labelled), **acceptance and UAT plan** (rows from the human test plan and the test guides for that scope: what the client will test and how), delivery and release approach (the verify gate, `/release`, the release log), pricing from §4 or "on request", exclusions from §7, "terms to follow" |
| Outreach | `outreach.md` | **Prospect kits only.** A first email and two follow-ups, each under 120 words, each built around one pain the prospect has shown, with one proof and one clear ask. Subject lines. No fake familiarity |

For a persona kit, the proposal is a template: prospect-specific parts read `{{prospect}}` and
are listed in the report.

**Gate:** every artefact exists; every claim is sourced; every ◐ row is labelled.

---

## Phase 3 — VERIFY

1. Every claim in every artefact maps to `MESSAGING.md` or the ledger.
   `python3 .claude/hooks/check_citations.py` reports nothing stale.
2. Every demo-script label greps to the UI source.
3. No price appears unless `MESSAGING.md` §4 holds it (grep for currency symbols and digits next
   to them).
4. Prospect facts are labelled; nothing in principle 2 is invented.
5. One rendered look at the one-pager and the proposal, if the session offers one: print preview
   at A4 and Letter (one page for the one-pager; no row cut across a page break in the proposal),
   phone width, light and dark. Print always renders the light theme.

**Gate:** all five pass.

---

## Phase 4 — REPORT

The folder path, each artefact in one line, the ◐ rows the kit presents, any `{{prospect}}`
placeholders left for the owner, the prospect facts still unknown, and how to make the PDF
(open the HTML, print, save as PDF). Remind the owner that `docs/sales/` is not committed.

---

## Definition of done

- [ ] Target mapped to a house; prospect brief labelled (prospect kits).
- [ ] One-pager, demo script, call guide, battlecards and proposal; outreach for prospects.
- [ ] Every claim sourced; ◐ labelled; no invented customers, numbers, prices or competitor facts.
- [ ] Demo labels verified; one-pager prints to one page; proposal prints cleanly.
- [ ] Nothing sent; `docs/sales/` gitignored; report delivered.

## Anti-patterns

- Writing a claim the messaging ledger doesn't hold, instead of running `/messaging`.
- A demo that tours features instead of relieving pains in order.
- Battlecards that trash an alternative with unsourced claims.
- Outreach that pretends to know the prospect ("loved your recent post") without a cited source.
- Dates on ◐ rows, or a price the owner never set.
- Sending, scheduling or logging anything outside `docs/sales/`.
