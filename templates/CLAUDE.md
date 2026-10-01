# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.
It is the house-rules layer of the software factory: the manifest (`factory.yaml`) says
*what to run*; this file says *why things are the way they are*. Keep every rule with
its reason; a rule without a reason gets deleted by the next reader.

## Quick start

```bash
{{run_dev}}          # dev server
{{build}}            # production build
{{verify}}           # full gate: tests + build — run before any deploy
{{deploy}}           # the ONE deploy path; refuses on a red gate
```

Testing: `{{test_unit}}` (fast suite) · `{{test_one}} <file>` (single file) ·
`{{test_backend}}` · `{{test_e2e}} <spec>` (fresh-seeded DB).

## The factory loop

This repo runs the **setup → develop → deploy → maintain** loop with Claude Code skills.
Use them; do not go direct.

| Want to… | Use |
|---|---|
| Add or change a capability | `/create-feature` (amendment mode for a change) |
| Fix something broken | `/fix-issue` — always, even for "obvious" fixes |
| Find out whether something works | `/find-issues` (diagnostic only) |
| Deal with a user report | `/address-feedback` |
| Work the testers' board | `/process-issues` |
| Ship | `/release` |
| Refresh tester material | `/test-pack` · the Issue Ledger: `/issues-dashboard` |
| Write user help for one subject | `/test-guide <subject>` → `docs/<SUBJECT>_TEST_GUIDE.md`; then `/guide-screenshots <guide>` for the storyboard and videos |
| Ask what the product does | `docs-agent` subagent · help a tester: `evaluator-assistant` |

## Documentation (the ledger)

All project docs live in `docs/`; only this file stays at the root.
- `docs/PRODUCT_REQUIREMENTS.md` — the PRD: dated `§3.N` sections, numbered acceptance criteria.
- `docs/IMPLEMENTATION_PLAN.md` — one row per section with **its test file as the gate**;
  a section is complete only when that file passes in `{{verify}}`.
- `docs/issues_log.md` — every bug and feature: symptom · root cause · fix · verification.
- `docs/FEATURE_LIST.md` — traceability inventory with maturity `●` / `◐` / `◐!`. The user
  guides in `docs/user-guide/` are **derived** from it; a hook reconciles them.
- `docs/TEST_PLAN_HUMAN.md`, `docs/TESTING_COMPANION.md`, `docs/WHY_WE_NEED_TESTING.md` —
  the human half of testing. `docs/RELEASE_LOG.md` — what shipped when. `docs/SEEDING.md`
  — which seeder is safe.
- `docs/<SUBJECT>_TEST_GUIDE.md` — customer tester's guides, one per module / feature / use
  case (`/test-guide`); `docs/screenshots/<subject>/` their annotated storyboards and videos
  (`/guide-screenshots`, via `tools/screenshots/`). Labels in a guide are verified against the
  rendered source; the capture is the ground truth when it disagrees with the guide.

## Architecture

{{architecture}}

## Invariants (non-negotiable, each with its reason)

{{invariants}}

Two that apply to every product built this way:

- **The clock is a seam.** Only the modules named in `factory.yaml → tests.clock_seam` may
  read the system time. Tests freeze it; a running server cannot be told another date.
  Reason: anything triggered by elapsed time is otherwise untestable, and an external
  override would be a forgery hook. If the product has no seam yet, add one before the
  first time-dependent rule.
- **Derived artefacts are generated, never hand-edited.** Compiled config, seed JSON, the
  user guides, the issue dashboard. Reason: two sources of truth drift silently.

## Testing strategy

A red suite blocks deployment. No exceptions, no "unrelated failure".
- Unit / component tests under `{{unit_dir}}`; backend under `{{backend_dir}}`; end-to-end
  under `{{e2e_dir}}` against a fresh-seeded database.
- Tests compute expectations from the data; change the data → change the expectations.
- Diagnostic tests (`{{diagnostic_prefix}}*`) pin current behaviour, labelled `DEFECT:`
  while wrong and `FIXED` after.
- At the third instance of a bug class, add a guard test for the class.

## Common workflows

### Adding a module
1. Requirement first: `/create-feature` writes the dated PRD section and the RED test.
2. Page / handler in the established pattern; data + store + API in the sibling shape.
3. Register it wherever the shell enumerates modules (router, access map, nav, feature
   flag, tracker module list in `factory.yaml → issues.modules`).
4. `{{verify}}` green, real flow driven, PRD + plan flipped Complete, feature-list row.

### Changing data or seeds — read `docs/SEEDING.md` first
{{seeding_note}}

### Deploying
`/release`. It runs `{{verify}}`, then `{{deploy}}`, then smokes health, an asset's
content type, the version stamp and a login, then records the release.

## Debugging tips

{{debugging}}
