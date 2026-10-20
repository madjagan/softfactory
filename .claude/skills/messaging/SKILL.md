---
name: messaging
description: "Write or refresh the messaging ledger (docs.messaging, default docs/MESSAGING.md) from the product summary, the feature list and the PRD: the positioning and 10-second / 30-second / 2-minute pitches, a messaging house per primary persona (roof, three pillars each tied to a fit row, a tool, a feature row and its proof, words to use and avoid), objections with sourced answers, the owner's packaging and pricing decisions, and the proof inventory. Every sales page and document reads from it. Nothing invented: no customers, testimonials, counts, prices or competitor facts. Triggers on: messaging, positioning, value line, elevator pitch, messaging house, objections, pricing and packaging, what do we say to, /messaging."
metadata:
  author: "softfactory"
  version: "1.0"
  category: "growth"
---

# Messaging — what to say, to whom, and the proof behind it

You are writing the messaging ledger: the single source every sales page and document reads.
Run the phases **in order**; each ends in a **gate**. Stamp with `date +%F`.

Prime directive: **a message is only as good as its proof.** Every pillar points at a pain or
gain the owner named, the tool that meets it, a feature row and something that proves the row
works. A pillar without proof is cut, however good it sounds.

Read first: `factory.yaml` (`project.*`, `docs.*`, `marketing.*`), then `docs.product_summary`,
`docs.feature_list`, `docs.prd`, and an existing `docs.messaging` if there is one.

---

## Operating principles

1. **Traceable claims.** Features are cited as `AREA-NN (FEATURE_LIST.md:NNN)`; everything else
   as `file:line`. A claim with no source is cut or becomes an open question for the owner.
2. **Never invented:** customers, logos, testimonials, quotes, user or revenue counts, case
   studies, certifications, prices, and facts about competitors. A competitor claim comes from
   the owner's words in summary §4, or from a public page cited with its URL and the date read.
3. **◐ rows are part of the offer.** Present them, and follow each with *in development —
   available soon*. Never a date. §7 won't-haves are never presented as features.
4. **The persona's own words.** Use the phrases from the interview (jobs, pains, concrete
   instances) over marketing language. "Words to avoid" lists the jargon the persona wouldn't use.
5. **Pricing is the owner's.** Offer 2–3 options with trade-offs; write only what the owner
   picks. A blank §4 is a valid answer and means "price on request" everywhere downstream.
6. **Amend, don't rewrite silently.** On a refresh, a changed section gets
   `**Amendment (date):** was …; now …; because …` under it.

---

## No ledger

If the repo has no product summary or feature list (a framework, a library, an early
prototype), use the stand-ins `factory.yaml` records in its header comment, as
`/marketing-site` does: the README or a brief for the summary and PRD, the repo's modules,
commands and skills (by path) for ● rows, and `docs/specs/*` for ◐ rows. Cite the stand-in
`file:line` or path. Say in the report that stand-ins were used, and recommend
`/product-interview` when the repo is a product that should have a ledger.

---

## Phase 1 — GATHER

Build a working table (kept in the session): for each primary persona, the top-3 pains and
gains from the fit table, the tool and feature row that meets each, the maturity (● / ◐) and
the proof available — an acceptance criterion (PRD §3.N), a test file (from the plan row), a
guide or storyboard. Collect the alternatives (summary §4) and every open fit row.

**Gate:** each top-3 pain and gain has a row in the table, or is marked open.

---

## Phase 2 — DRAFT §1–§3 AND §5

- **§1 Positioning:** the positioning statement from the summary header, tightened; pitches at
  10 seconds (one sentence), 30 seconds (problem → what it does → why it is different) and
  2 minutes (adds the three pillars and one proof each).
- **§2 One house per primary persona:** the roof is one line of value in the persona's words;
  three pillars from the strongest fit rows, preferring ● rows with a test as proof. Words to
  use and to avoid.
- **§3 Objections:** one per alternative ("why not just use X?"), one per open fit row ("does it
  do Y?" → an honest "not today", citing §7 or the open row), and the obvious ones a buyer of
  this kind asks (cost, switching, risk), each answered only from the ledger.
- **§5 Proof inventory:** the facts sales material may cite — ● features with their tests, the
  verify-gate test count, release count, guide videos — each with its source. No number the
  ledger doesn't hold.

**Gate:** every pillar has a fit row, a feature citation and a proof; every objection has a
sourced answer or an honest "not today".

---

## Phase 3 — PRICING (owner decides)

Ask in one `AskUserQuestion` round, each with a recommendation drawn from the personas and the
alternatives:

- Pricing model (per seat, per project, flat, usage, free + paid, or "not yet").
- Currency.
- Tiers: names and which feature rows each includes (offer a cut by persona).
- Prices: free text, or "on request".

Write only the answers, dated. Don't research or recommend price points from market data.

**Gate:** §4 holds the owner's answers, or is explicitly blank.

---

## Phase 4 — PLAY BACK AND WRITE

- Show each persona's house and the objections table; apply corrections in one pass.
- Write `docs.messaging` from `templates/docs/MESSAGING.md` (or amend the existing file).
- Check: `grep -n "{{" <file>` finds nothing; `python3 .claude/hooks/check_citations.py` reports
  no stale citation; every ◐ citation is followed by *in development — available soon*.
- Report: the houses in one line each, the ◐ rows the messaging presents, any stand-ins used,
  and the next moves — `/marketing-site` to pick up the new messaging, `/sales-kit <persona>`.

Do not commit unless asked.

---

## Definition of done

- [ ] §1 positioning and three pitches; §2 one house per primary persona with three proven pillars.
- [ ] §3 objections, each sourced or honestly "not today"; §5 proof inventory with sources.
- [ ] §4 is the owner's answers, dated, or blank.
- [ ] No `{{`; citations fresh; ◐ rows labelled; nothing in principle 2 invented.
- [ ] Played back and confirmed; next moves stated.

## Anti-patterns

- A pillar that is a feature name with no pain behind it, or a pain with no proof.
- "Trusted by…", "10,000+ teams", invented quotes, or a competitor weakness nobody sourced.
- Suggesting a price the owner didn't give.
- Dates on ◐ rows ("coming in Q3").
- Rewriting a house without an amendment line.
