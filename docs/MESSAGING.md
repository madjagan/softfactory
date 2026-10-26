# Solo Product Toolkit — Messaging

**Date:** 2026-10-20 · **Owner:** Madhavan Jagannathan · **Source:** `/messaging`, from stand-ins
(this repo has no product summary or feature list): `README.md` and `METHODOLOGY_BRIEF.md` for the
summary and PRD, the repo's skills, agents, hooks and apps by path for ● features, `docs/specs/*`
for ◐. Personas, pains and pricing are the owner's answers of 2026-10-20. Every sales page and
document reads from this file. A change rewrites the affected section and adds a dated amendment
line under it; it is never edited silently.

Citations: a feature by its path, anything else as `file:line`. A ◐ item is always followed by
*in development — available soon*.

---

## 1. Positioning

> For solo founders and small agencies who ship real software with Claude Code to people who test
> it and depend on it, Solo Product Toolkit is a toolkit that takes a product from idea to
> software to customers, and keeps it evolving: every change is proposed with evidence and
> approved by you. (README.md:3, README.md:6-12; personas: owner, 2026-10-20)

**Amendment (2026-10-20):** was "a spec-first framework that takes a product from idea to a release
that keeps evolving"; now "a product factory … from idea to software to customers"; because the
framework also helps sell the product (`/messaging`, `/sales-kit`, `/marketing-site`), and the owner
chose to keep the name and widen the category line instead of renaming.

**Amendment (2026-10-26):** was "softfactory … a product factory"; now "Solo Product Toolkit … a toolkit";
because the owner renamed the product to say who it is for (one person in every role). The
promise is unchanged.

| Length | Pitch |
|---|---|
| 10 seconds | Solo Product Toolkit takes your product from idea to customers with Claude: built the disciplined way, sold on proof, and you always see what is really done. |
| 30 seconds | When Claude writes your code, it's hard to know what is really finished, tester feedback arrives everywhere at once, and the docs drift away from the product. Solo Product Toolkit installs a ledger and gated skills into your repo: a feature is done only when its test passes, testers file issues on a tracker where Claude proposes verdicts and humans close them, and every change to a requirement is a dated entry. When it's ready, the same ledger writes your messaging, sales kit and home page. |
| 2 minutes | The 30-second pitch, then the three pillars of the persona's house (§2), each with one proof, and the close: "It's free to install. If you want help setting it up on your project, that's what the paid setup is for." |

---

## 2. Messaging houses

### 2.1 — Solo founder

*Ships a real product with Claude as the dev team, with no QA or PM, and sells to paying customers.*

**Amendment (2026-10-20):** was "ships a real product … and sells to paying customers"; now: the
founder holds every role on the product — product owner, operator, and often tester and support —
and also owns business development, marketing and sales; because the owner stated that every
persona in the product maps to the founder. Copy for this persona speaks to one person doing all of
these, not to a team.

**Roof:** Know what's really done, hear every tester, and keep the docs true — without hiring a QA
team or a PM.

| Pillar | Pain it answers (owner, 2026-10-20) | Tool | Feature | Proof |
|---|---|---|---|---|
| **Done means a test passes** | No idea what's really done: Claude says it's finished, but nothing shows what is built and tested | `/create-feature` | `.claude/skills/create-feature/SKILL.md` | "A PRD section is feature-complete only when its test file passes" (METHODOLOGY_BRIEF.md:50); RED first (README.md:99) |
| **Every tester report gets a verdict** | Tester feedback is chaos: reports by message and email, no record, no verdict | Issue tracker + `/process-issues` | `issues/`, `.claude/agents/issue-agent.md` | Server-enforced state machine; the agent proposes, humans verify and close (README.md:87, README.md:107); the tracker's own API suite, `issues/tests/test_api.py` |
| **Docs that can't drift** | The PRD, the user guides and the code disagree | Dated amendments, derived guides, citation checker | `.claude/hooks/feature-list-changed.sh`, `.claude/hooks/check_citations.py`, `.claude/agents/docs-agent.md` | Guides are derived from the feature list and regenerated when it changes (METHODOLOGY_BRIEF.md:53, METHODOLOGY_BRIEF.md:105); amendments, never rewrites (METHODOLOGY_BRIEF.md:49) |

**Words to use:** done, tested, what's really built, your testers, every change has a date, you decide.
**Words to avoid:** enterprise, governance, compliance, agile ceremony, "AI-powered", autonomous.

### 2.2 — Agency / consultancy

*Builds for clients, needs UAT sign-off and a release record, and a clear line between a bug and a
change request.*

**Roof:** Get client sign-off faster: a UAT plan in every proposal, a verdict on every finding, and
a dated record of every change.

| Pillar | Pain it answers (owner, 2026-10-20) | Tool | Feature | Proof |
|---|---|---|---|---|
| **UAT your client can run** | Tester feedback is chaos: client findings arrive scattered, and bug-or-change arguments stall sign-off | Tracker, tester guides, test pack | `issues/`, `.claude/skills/test-guide/SKILL.md`, `.claude/skills/guide-screenshots/SKILL.md`, `.claude/skills/test-pack/SKILL.md` | Verdicts classified from evidence against the written requirement (README.md:101); four tester verdicts: Defect, By design, Not built yet, UX finding (METHODOLOGY_BRIEF.md:104) |
| **Status the client can trust** | No idea what's really done: the client asks what's finished and nobody can prove it | Honest feature list, release gates | `.claude/skills/release/SKILL.md`, `.claude/skills/create-feature/SKILL.md` | Maturity ● live / ◐ in dev / ◐! caveated, never softened (METHODOLOGY_BRIEF.md:52); nothing ships past a red gate (README.md:10) |
| **Every change request on the record** | Docs drift: scope and requirements drift away from what was agreed | Dated PRD amendments | `.claude/skills/create-feature/SKILL.md` (amendment mode) | "A change to existing behaviour is a dated amendment stating old and new, never a rewrite" (METHODOLOGY_BRIEF.md:49) |

**Words to use:** sign-off, UAT, change request, release record, your client's testers, scope.
**Words to avoid:** move fast, autonomous, "AI does it all", vibe coding.

**Also for agencies:** one board per customer, triaged into shared internal issues (`issues/`); a
lightweight support desk with an in-app widget (`support/`); a feature-request portal with votes
and demand (`ideas/`).

**Amendment (2026-10-20):** was "on the roadmap … in development — available soon"; now built and
tested (`issues/tests/`, `support/tests/`, `ideas/tests/`).

---

## 3. Objections

| # | Objection | Answer | Source |
|---|---|---|---|
| 1 | "I already use Claude Code. Why add a framework?" | Claude Code writes the code; Solo Product Toolkit decides when it is done (its test passes), records why it changed (a dated amendment), and gives your testers a place to report and a verdict on every report. | README.md:6-12, README.md:98-107 |
| 2 | "Isn't this heavy process for one person?" | `/product-interview` and `/setup-project` write the ledger for you, and every later step is a skill you invoke in plain language. | README.md:62-70 |
| 3 | "Does it lock me in?" | Everything is Markdown and scripts in your own repo. `install.sh --update` refreshes the framework without touching your docs. | README.md:66-69 |
| 4 | "Does it work with Cursor, Copilot or other agents?" | Not today: it is built on Claude Code's skills, agents and hooks. | README.md:6 |
| 5 | "Can my clients' testers use it without being developers?" | Yes: one-page tester guides with annotated screenshots, a tracker that takes screenshots, and an assistant that tells a tester whether what they saw is a defect. | `.claude/skills/test-guide/SKILL.md`, `.claude/agents/evaluator-assistant.md`, METHODOLOGY_BRIEF.md:104 |
| 6 | "What does the paid setup include, and what does it cost?" | Price on request. | §4 |
| 7 | "How is it different from other spec-driven tools?" | *Open: the owner hasn't recorded the alternatives yet. Answer only after `/product-interview` §4 or with cited public pages.* | — |

**Amendment (2026-10-26):** was eight objections; now seven: "Has it been used on a real product?" is
removed, and objection 2 drops its last sentence; because the owner withdrew those claims. Answer that question only from evidence the repo holds.

---

## 4. Packaging & pricing

Owner decisions only. Blank means "price on request" in every sales document.

| Decision | Choice | Date |
|---|---|---|
| Pricing model | Free framework + paid setup per project | 2026-10-20 |
| Currency | — (not set) | — |

| Tier | Price | Includes | For |
|---|---|---|---|
| Framework | Free | Everything in this repo, installed with `install.sh` | Anyone building with Claude Code |
| Setup | On request | *Open: the owner hasn't defined the scope yet* | Solo founders and agencies who want help getting started |

---

## 5. Proof inventory

The only facts and numbers sales material may cite.

| Fact | Value | Source |
|---|---|---|
| Gated skills | 17 | README.md:77; `.claude/skills/` |
| Agents | docs-agent, evaluator-assistant, issue-agent, support-agent, ideas-agent | `.claude/agents/` |
| App tests | 101 passing on 2026-10-20: tracker and customer boards 34, support desk 40, ideas portal 27 | `issues/tests/`, `support/tests/`, `ideas/tests/` |

**Amendment (2026-10-26):** three rows removed; because the owner withdrew those claims.
