# Spec — sell-assist: `/messaging` and `/sales-kit`

## Purpose

Softfactory takes a product from an idea to a release that keeps evolving. It doesn't help anyone
**sell** the product. The ledger already holds most of what selling needs: the personas, the value
proposition canvas, the alternatives, the features with their maturity, the acceptance criteria,
the tester guides with their screenshots, and the release log. Two skills turn that into sales
material, under the same rules as `/marketing-site`:

- **`/messaging`** writes the **messaging ledger** (`docs/MESSAGING.md`): what to say to each
  persona, the proof behind it, objections and their answers, and the owner's decisions on pricing
  and packaging. Every downstream page or document reads from it.
- **`/sales-kit`** produces the material for **a persona** (a reusable kit) or for **one prospect**
  (a kit tailored to them): a one-pager, a demo script, a discovery call guide, battlecards, a
  proposal and an outreach draft.

Claude drafts and the owner sends. Nothing leaves the repo on its own.

## Principles (inherited from `/marketing-site`, plus two)

1. **Traceable claims.** Every capability, number and statement cites a ledger source (`file:line`
   or an `AREA-NN` row). A claim without a source is cut.
2. **Never invented:** customers, logos, testimonials, quotes, user or revenue counts, case
   studies, certifications, **prices** (until the owner sets them), and **facts about competitors**.
   A competitor claim comes from the owner's own words in summary §4, or from a public page cited
   with its URL and the date it was read.
3. **◐ rows are part of the offer, labelled "in development — available soon".** As on the
   marketing site, they are presented as part of the product; in sales material each one carries
   that phrase where it appears (owner's decision, 2026-10-20). No dates are promised. §7
   won't-haves appear only as exclusions in the proposal.
4. **Drafts only.** Outreach emails, proposals and follow-ups are files the owner reviews and sends.
   No skill sends email, posts, books meetings or writes to a CRM.
5. **The persona's own words.** Copy uses the phrases the owner gave in the interview (jobs, pains,
   concrete instances) in preference to marketing language.
6. **Prospect facts are labelled.** Anything about a prospect says where it came from: "owner's
   notes (date)" or a public URL with the date read.

## The two skills

### `/messaging` — the messaging ledger

**Reads:** `docs.product_summary` (§1 personas, §2 canvas and fit table, §3 component tools,
§4 alternatives, §5 metrics), `docs.feature_list`, `docs.prd`, `marketing.*`.

**Writes:** `docs.messaging` (default `docs/MESSAGING.md`), one dated version. A change rewrites the
affected section and adds a dated amendment line, as in the PRD.

| Section | Content | Source |
|---|---|---|
| §1 Positioning | The positioning statement; pitches at 10 seconds, 30 seconds and 2 minutes | summary header, §2 |
| §2 Messaging house, one per primary persona | **Roof:** one value line. **Three pillars:** each a top-ranked pain or gain → the tool that meets it → the feature row (`AREA-NN`, ● or ◐) → its proof (the acceptance criterion, the test file, the guide). **Words to use / avoid**, taken from the interview | fit table, feature list, PRD §3 |
| §3 Objections | Objection → answer → source. Seeded from §4 alternatives ("why not just use X?") and from open fit rows ("does it do Y?" → honest answer) | summary §2 and §4 |
| §4 Packaging & pricing | **Owner decisions only:** pricing model, tiers, what each tier includes (feature rows), anchors. Claude offers 2–3 options with trade-offs and the owner picks. Blank means "price on request" everywhere downstream | owner, dated |
| §5 Proof inventory | Every fact sales material may cite: ● features with their tests, verify-gate test count, release count, guide videos. No counts that the ledger doesn't hold | ledger |

**Flow:** read the ledger → draft §1–§3 and §5 → ask the owner the §4 questions in one round
(`AskUserQuestion`, with options) → play back each persona's house → write.

**Gate:** every pillar cites a fit row and a feature row; every objection has a sourced answer or
an honest "not today (§7 / open fit row)"; §4 is decided or explicitly blank.

### `/sales-kit` — material for a persona or a prospect

**Invocation:** `/sales-kit <persona-id>` for a persona kit, or `/sales-kit <prospect>` with notes,
a URL or a file for a prospect kit.

**Reads:** `docs.messaging` (and stops if it is missing: run `/messaging` first), the feature list,
the human test plan, the test guides and their storyboards (`docs/screenshots/<subject>/`), and the
release log.

**Writes:** under `docs.sales` (default `docs/sales/`).

| Artefact | File | Content |
|---|---|---|
| One-pager | `<target>/one-pager.html` | The roof, three pillars, one screenshot from a storyboard (labelled "Example"), the CTA from `marketing.*`. Design system tokens, prints to a single A4/Letter page |
| Demo script | `<target>/demo-script.md` | 5–8 steps, each: what to click (taken from a test guide, labels verified in the source), the seeded record to use, **the pain it relieves** (fit row), what to say. Links to the guide's storyboard frames |
| Discovery call guide | `<target>/call-guide.md` | Questions built from the persona's jobs and pains ("When did … last happen?"), a qualification table (does the prospect have the top-3 pains?), the likely objections from `MESSAGING.md` §3 |
| Battlecards | `<target>/battlecards.md` | One per alternative in summary §4: where it wins, where we win (sourced), questions to ask, what not to claim |
| Proposal | `<target>/proposal.html` | Problem (the prospect's pains), proposed scope (chosen feature rows; ◐ rows "in development — available soon"), **acceptance and UAT plan** taken from the human test plan and the test guides, delivery and release approach, pricing from §4 or "on request", exclusions from §7. HTML with print CSS; the owner saves it as PDF from the browser |
| Outreach draft | `<target>/outreach.md` | Prospect kits only: a first email and two follow-ups, each under 120 words, citing one pain the prospect has shown |

**Prospect research:** the owner's notes come first. Public facts (what the company does, its size,
the stack it advertises) may be fetched from the web, each cited with a URL and the date read.
Nothing about named individuals beyond what is on a public company or profile page the owner points
to.

**Privacy:** `docs/sales/` is gitignored. `install.sh` adds it to `.gitignore` (owner's decision,
2026-10-20), so prospect notes and kits stay on the owner's machine.

**Gate:** every claim in every artefact cites `MESSAGING.md` or the ledger; every demo step's labels
grep to the UI source; ◐ rows are marked; nothing in principle 2 is invented; the outreach draft is a
file, not a sent email.

## Goals and success criteria

| # | Criterion | Proved by |
|---|---|---|
| M1 | `/messaging` on a repo with a filled product summary writes `MESSAGING.md` with one house per primary persona and no `{{` left | run on a fixture repo; grep |
| M2 | Every pillar names a fit row, an `AREA-NN` and a proof (criterion, test file or guide); every objection has a source or an honest "not today" | citation check script |
| M3 | §4 holds only owner answers; with §4 blank, no downstream artefact shows a price | fixture with blank §4; grep artefacts for currency symbols |
| M4 | A cited `AREA-NN` that is no longer in the feature list is reported as stale | extend `check_citations.py` to `MESSAGING.md` and `docs/sales/**`; test with a removed row |
| S1 | `/sales-kit <persona>` produces the one-pager, demo script, call guide, battlecards and proposal; `/sales-kit <prospect>` adds the outreach draft | run on the fixture |
| S2 | Every ◐ row in any artefact carries "in development — available soon", with no date; §7 items appear only as proposal exclusions | fixture with one ◐ row and one §7 item |
| S3 | Every demo-script label greps to the UI source | the same check `/test-guide` uses |
| S4 | The one-pager fits one printed page at A4 and Letter; the proposal prints cleanly to PDF (no table row split across pages, no heading stranded at a page foot); both work in light and dark themes and at 375 px | rendered look (print preview + phone width) |
| S5 | Each prospect fact carries "owner's notes (date)" or a URL and date | grep the prospect kit |
| S6 | `docs/sales/` is in `.gitignore` after `install.sh` | install into an empty dir; `git check-ignore docs/sales/x` |
| S7 | No skill sends anything: no mail, HTTP POST or CRM tool calls in either SKILL.md | review of the skill files |

## Fit with the framework

| Change | Where |
|---|---|
| New skills | `.claude/skills/messaging/SKILL.md`, `.claude/skills/sales-kit/SKILL.md` |
| New templates | `templates/docs/MESSAGING.md` (project-owned, written once by `install.sh`); `templates/sales/one-pager.html` and `proposal.html` (token block and print CSS, as in the marketing site reference build) |
| Manifest | `docs.messaging: docs/MESSAGING.md`, `docs.sales: docs/sales` in `factory.example.yaml` and `DEFAULT_DOCS` in `tools/factory.py`. No new top-level block |
| `/marketing-site` | Reads `MESSAGING.md` when present: the roof → hero subhead, the pillars → "why this" points, §3 → the FAQ. Falls back to today's behaviour without it |
| Citation hook | `check_citations.py` also scans `MESSAGING.md` and `docs/sales/**` |
| README loop | A **GROW** stage after DEPLOY: `/marketing-site`, `/messaging`, `/sales-kit` |
| `.gitignore` | `install.sh` adds `docs/sales/` |

## Out of scope

- Sending anything: email, LinkedIn, CRM writes, calendar booking.
- Lead lists and prospect discovery at volume (the `/prospect` agent from option C).
- Content marketing and SEO (`/content`, option B).
- A pipeline dashboard, deal stages or forecasting.
- Contracts, terms and legal language in proposals. The proposal says "terms to follow".
- Pricing research or recommendations from market data. §4 is the owner's decision.
- **Call debriefs (v2, after the first real calls).** `/sales-kit debrief <prospect>` would log each
  call to `docs/sales/DEBRIEFS.md` (pains confirmed or new, objections verbatim, outcome) and
  propose amendments to `MESSAGING.md` §3 or the canvas for the owner to approve, closing the
  EVOLVE loop from the sales side. Specified once real calls show what is worth recording.

## Decisions (2026-10-20)

1. **◐ in sales material:** presented as part of the offer, each labelled "in development —
   available soon"; no dates promised.
2. **Proposal format:** HTML with print CSS, saved to PDF by the owner.
3. **Prospect material:** `docs/sales/` is gitignored.
4. **Debriefs:** deferred to v2, after the first real calls.

## Open questions

1. **This repo first.** Run both skills on softfactory itself (using the README and
   `METHODOLOGY_BRIEF.md` stand-ins, as `/marketing-site` did), or wait for a product with a full
   ledger?
