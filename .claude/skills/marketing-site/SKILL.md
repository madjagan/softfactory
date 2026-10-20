---
name: marketing-site
description: "Generate or refresh the product's marketing home page from the ledger: the brief in factory.yaml (marketing.*), the product summary (personas, value proposition canvas, alternatives), the PRD, the feature list and the user guides, styled with the project's design system. One HTML file at docs.marketing_site plus a private claude.ai link that stays the same on every regeneration. Every claim is traced to a source; nothing about customers, logos, testimonials, counts, offices or legal pages is invented. Triggers on: marketing site, marketing page, landing page, home page for the product, product website, refresh the marketing page, /marketing-site."
metadata:
  author: "softfactory"
  version: "1.1"
  category: "documentation"
---

# Marketing site — the product's home page, derived from the ledger

**Prime directive:** the page is a rendering of the ledger, in the same way the user guides are.
Every claim on it comes from a file in the repo, and the skill can name that file. When the
ledger changes, the page is regenerated. It is never hand-edited.

Read first: `factory.yaml` (`product.*`, `stack.design_system`, `marketing.*`, `docs.*`),
`CLAUDE.md`, `docs.messaging` if `/messaging` has written it, and an existing
`docs.marketing_site` if there is one. This framework's own page,
`site/index.html` in the softfactory repo, is the reference build: it shows the section spine,
the token block and the publish markers.

## No ledger

Some repos have no feature list, PRD or product summary yet, such as a framework, a library or
an early prototype. Don't stop, and don't invent one. Before Phase 1:

1. Map each ledger role to the nearest file that holds the facts, and ask the owner to confirm
   the mapping:

   | Ledger role | Stand-in |
   |---|---|
   | product summary | `README.md` |
   | PRD | a methodology, design or brief document; otherwise the README |
   | feature list ● | what exists in the repo: modules, commands, skills, apps, each with its path |
   | feature list ◐ | approved or drafted specs (`docs/specs/*`) |
   | user guides | usage docs, or the README's usage section |
   | release log | tags and `git log`, for numbers only |

2. Write the mapping into `factory.yaml`: `docs.product_summary` and `docs.prd` take the stand-in
   paths, and a comment block at the top of the file records the rest. The next run then reads
   it and asks nothing.
3. Claims cite the stand-in `file:line`, or a path for a ● row. Specs count as ◐ and are listed in
   the report like any other ◐ row.
4. The report says the page was built from stand-ins, and recommends `/product-interview` then
   `/setup-project` when the repo is a product that should have a ledger.

## Principles

1. **Traceable claims.** Every capability, number and statement maps to a source line. Product
   facts come from the PRD, the feature list, the user guides, the product summary and the
   release log. Never from memory, and never from the reference site.
2. **What the page may present as available:** every feature row in `docs.feature_list`, both
   ● live and ◐ in development. This is the owner's standing decision (2026-10-19). §7 (won't
   have) and the §8 gap register are not features and never appear as available. The run summary
   lists every ◐ row the page presents, so the owner always sees what the page claims beyond what
   is live. No status chips on the page.
3. **Never invented:** customers, logos, testimonials, quotes, user or revenue counts, offices,
   awards, certifications, pricing, legal pages. A stats band uses only numbers the ledger holds
   (feature count, PRD sections, tests in the verify gate, release count), each with its source,
   or the band is left out.
4. **Example data is labelled.** Mock screens, sample documents and replayed runs use seed
   names and labels taken from the source, and each one says "Example".
5. **The design system is law.** When `stack.design_system` names a tokens file, use its colours,
   type, radii and components. Define tokens in the page only when there is no system, and keep
   them in one `:root` block.
6. **Labels as rendered.** Any screen the page mocks uses the product's real control labels,
   checked by grepping the UI source, as `/test-guide` does.
7. **One URL forever.** The first publish records `marketing.artifact_url`, and every
   regeneration republishes there.

## Phase 1 — Brief

Read `marketing.*`. For each blank field, ask the owner, in one round, with a recommendation
drawn from the product summary:

| Field | Default suggestion from |
|---|---|
| `audience` | the primary personas in `docs.product_summary` |
| `headline` | the product's own line if the PRD or summary has one; otherwise offer 2–3 from the value proposition, one word in `*asterisks*` |
| `primary_cta` / `primary_href` | B2B: "Book a demo"; self-serve: "Start" / "Install" |
| `secondary_cta` / `secondary_href` | "See it in action" → the page's replay or deep-dive section |
| `reference_url` | optional; only the section order is mirrored, never its copy or claims |
| `contact` | blank → `hello@<slug>.example`, flagged as a placeholder |

Write the answers back into `factory.yaml` under `marketing:`, so the next regeneration needs no
questions.

**Gate:** every field is filled or explicitly left blank by the owner.

## Phase 2 — Claims table

Build a working table (kept in the session, not shipped): **claim → page section → source
`file:line`**.

- **Messaging** (`docs.messaging`, when present — it takes precedence over the summary for copy):
  the roof → the hero subhead; the three pillars → the "why this" points, with their proofs; §3
  objections → the FAQ; §4 pricing → a pricing section only if the owner set prices there.
- **Product summary:** the jobs, pains and gains per persona → the hero subhead, the lifecycle
  tabs and the FAQ. Alternatives → the "why this" points. The stack → the trust strip.
- **PRD:** the purpose and principles → the hero and the positioning. The acceptance criteria → the
  specifics in deep-dives ("each line shows its source", "refuses X").
- **Feature list:** every row (● and ◐) → the module grid, grouped by area, with its `AREA-NN`.
  The persona map → who each section speaks to. §7 → the FAQ "what it doesn't do", when useful.
- **User guides:** the task wording → section copy in the reader's language.
- **Release log / plan:** numbers for the stats band, if used.

**Gate:** every claim has a source. Anything without one is cut, or marked as an open question
for the owner.

## Phase 3 — Section plan (owner approves)

Use the spine below. Drop any section the ledger can't fill, and mirror `reference_url`'s order
if one is given.

1. Sticky nav: the brand, 4–5 section links, the secondary link and the primary CTA.
2. Hero: the headline (one italic accent word), the subhead from the value proposition, both CTAs,
   and a **mock of the product's most characteristic screen**, using real labels and example data.
3. Trust strip: stack and approach facts, never logos.
4. Tabbed lifecycle: one tab per stage of the primary persona's job, with the features for each.
5. Stats band: ledger numbers with their source, or omitted.
6. Deep-dive: the product's most characteristic artefact (a document, a calculation, a record),
   **each line labelled with where it comes from**.
7. Automation / agents: if the product has them, the agents' boundaries plus **one replayed run**.
8. Configuration: what an admin sets, from the configuration features.
9. Module grid: every feature row, grouped.
10. Audience showcase: the product's differentiator for this audience (languages, roles,
    regulation, integrations), from the PRD.
11. FAQ: 5–7 questions answered from the PRD non-goals, the guides and §7.
12. CTA band: the primary CTA again, with one line of what happens next.
13. Footer, five columns: product sections, features, docs, company/project, contact. No legal
    links unless the repo has the pages.

Show the owner the plan as a table (section → content → sources), plus the success criteria:
traceable claims, nothing invented, light and dark themes, works at 375 px with no horizontal
scroll, keyboard tabs, reduced motion respected, and the ◐ rows listed.

**Gate:** the owner approves the plan. On a regeneration with an unchanged plan, say what changed
in the ledger and go straight to Phase 4.

## Phase 4 — Build

- One full HTML document at `docs.marketing_site`. The publishable part sits between
  `<!-- page:start -->` (right after the viewport meta) and `<!-- page:end -->` (before
  `</body>`), as in the reference build.
- Tokens from the design system. Light and dark themes through tokens only, with the dark values
  under `prefers-color-scheme` guarded by `:root:not([data-theme="light"])` and again under
  `:root[data-theme="dark"]`. Fonts from Google Fonts, with fallbacks. No other external assets.
- A monospace or tabular face for every number. Phone width with a 16 px gutter, no horizontal
  scroll, and wide tables and code inside their own `overflow-x: auto`.
- Tabs with `role="tab"`, arrow keys and Home/End. Replays are visible at rest, animate only on a
  click, and do nothing under `prefers-reduced-motion`.
- Copy: plain, active, specific. No lorem ipsum. No stock phrases.
- The placeholder contact (if used) carries an HTML comment: `PLACEHOLDER contact address`.

## Phase 5 — Verify

1. Every claim in the page matches the claims table, and every ◐ row is in the run's list.
2. Every mocked label greps to the UI source.
3. A tag-balance check passes, and the publish fragment holds no `<html>`, `<head>` or `<body>`.
4. One rendered look if the session offers one (preview or screenshot), at desktop and phone
   width in both themes. Fix what it shows, once.

**Gate:** all four pass.

## Phase 6 — Publish and report

1. Extract the fragment between the markers into the scratchpad, and publish it with the Artifact
   tool: pass `url` = `marketing.artifact_url` when it is set. On the first publish, add `icon`
   and a one-sentence `description`, then write the returned URL into `marketing.artifact_url`.
2. Report: the link, which sections changed, **the ◐ rows presented as available**, the
   placeholder contact (if any), and the example data used. Offer to commit `docs.marketing_site`
   and `factory.yaml`, and don't commit unasked.

## Definition of done

- [ ] `marketing.*` is complete in `factory.yaml`
- [ ] Every claim is sourced. Nothing in principle 3 is invented. Example data is labelled
- [ ] The owner approved the section plan (or it is unchanged since the last run)
- [ ] Both themes, 375 px, keyboard and reduced motion are all checked
- [ ] Published to `marketing.artifact_url`. The report lists the ◐ rows and any placeholder

## Anti-patterns

- Copying claims, numbers or wording from the reference site.
- "Trusted by…" strips, made-up quotes, round-number counts ("10,000+ teams").
- Presenting §8 gaps or §7 non-goals as features.
- Status chips, "beta" badges or roadmaps on the page (the owner's decision: every feature-list
  row reads as available).
- Hand-editing the published page instead of regenerating it from the ledger.
- A new artifact URL on each run.
- A `100vh` hero, or content hidden until scroll.
