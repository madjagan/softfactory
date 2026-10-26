---
name: test-pack
description: "Produce or refresh the human-testing material from the feature list and the PRD: the structured human test plan (one observable expectation per row, cited), the testing companion (what automation covers, what it cannot see, exploratory charters per module, the rule card), and a per-module tester coaching pack (single HTML with pass/fail toggles). Use when testers are about to start, when a module goes live, or after a batch of fixes. Triggers on: test pack, human test plan, coaching pack, UAT pack, tester material, exploratory charters, refresh the test plan, what should testers try."
metadata:
  author: "Solo Product Toolkit"
  version: "1.0"
  category: "quality"
---

# Test Pack — the human half of testing

Automation checks what we know; people discover what we did not know to check. This skill
writes the material that makes a non-developer's session productive. Everything it writes
is **derived** from the feature list (`docs.feature_list`), the PRD (`docs.prd`) and the
manifest (`personas`, `seed.*`, `environments.*`) — never from memory.

Read first: `docs.why_testing` (the philosophy), the current `docs.test_plan_human` and
`docs.testing_companion` (you are updating, not rewriting), `factory.yaml`.

## Rules

1. **One row, one action, one observable expectation**, in the app's own labels, with the
   PRD criterion or feature id it comes from. No row may depend on reading code.
2. **Expected values are derived**, from the seed and the configuration. If a figure cannot
   be derived, the row says "note the value shown".
3. **Never promise what the engine does not do.** A `◐` feature is tested as a display; a
   `◐!` caveat is carried into the row verbatim in substance.
4. **Say which rows change data**, so the hand-over names them and a reseed is a decision,
   not a surprise.
5. **Real date** from `date +%F` in every header and footer.
6. **Confirm every screen, tab and button name** in the code or a test before naming it.

## What to produce

### A. `docs.test_plan_human` — the structured half
- Header: environments, logins per persona, seed facts, the "passwords are not checked"
  kind of note if it applies, how to record (Pass / Fail / Blocked + one line).
- Summary table: area · cases · personas.
- One section per module (or per feature area), rows `AREA-NN | Title | Login |
  Preconditions | Steps | Expected (with citation) | Result`.
- Target 3–10 rows per live module; dev modules get one "renders and says it is in
  development" row.

### B. `docs.testing_companion` — the exploratory half
- **Part A** — the suite table with real counts (count test files and cases with the
  manifest's runners), coverage by area, what makes the product testable (seams, twin
  engines, fresh seeds), and **what the tests cannot see** (real date, the mouse, screen ⇄
  server seam, real data, long horizons, the eye, declared-but-unread config).
- **Part B** — how to run a session; a **rule card** (the product's numbers and policies a
  tester can check by hand); one **charter per module**: *Mission · Anchor (do once) ·
  Explore (variations) · Look for (bug classes) · Where it goes (the test file a finding
  lands in)*.
- **Part C** — the report shape (Issue · Current · Expected · Where it broke), the loop
  (`/find-issues` → `/fix-issue` → `/create-feature` → docs follow), the learning questions.

### C. A tester coaching pack — one HTML per module, `docs/manual-test-<module>.html`
Single file, no build step:
- Header strip: build, seed, narrative date, default login.
- Orientation ("how the module is shaped") and a who-can-do-what role table.
- ≤ 30 rows grouped: orientation → each named flow → role gates → experience probes.
- Pass / fail / note toggles per row, counts at the top, results in `localStorage` (every
  read and write wrapped in try/catch; the page must render with storage blocked).
- Closing "what to capture on a fail" and "you change the data" notes.
- Works at phone width; design tokens as CSS variables on `:root` with a dark-mode block.

If the `evaluator-assistant` agent exists, it uses these packs; keep the shape stable.

Related: a **one-page click-by-click guide for a single subject** (a module, feature or use
case) is `/test-guide`, and its annotated screenshot storyboard is `/guide-screenshots`. The
test plan says *what* to check across the product; a test guide says *exactly how* for one
thing.

## Procedure

1. Diff the feature list since the plan's footer date (`git log -p` on it); list rows to
   add, retarget or drop.
2. For each live feature, locate the criterion in the PRD and the screen in the code.
3. Write / update the three artefacts; re-stamp footers.
4. If `commands.docs_site` exists, render the internal docs site.
5. Report: rows added / changed per file, rows that change data, anything you could not
   derive (and therefore wrote as "note the value shown").
