---
name: release
description: "Ship the current state through the gates: confirm the tree is what you think it is, run the full verify gate, run the deploy command from factory.yaml, smoke the deployed instance, stamp the release log with what shipped (issues-log entries and PRD sections since the last release), and refresh the derived pages. Refuses on any red gate. Triggers on: release, deploy, ship it, redeploy, push to production, roll out, what shipped, cut a release."
metadata:
  author: "Solo Product Toolkit"
  version: "1.0"
  category: "operations"
---

# Release — through the gates, with a record

Deploying is the one action in the loop that is hard to undo. This skill exists so it
never happens on a red gate, on the wrong tenant, or without a record of what shipped.
Five phases **in order**, each with a **gate**. Read `factory.yaml` (`commands.*`,
`environments.*`, `release.*`) and `CLAUDE.md` (the deploy notes) first.

## Phase 1 — WHAT IS BEING SHIPPED

- `git status` and `git log <last-release-tag-or-entry>..HEAD --oneline`. The last
  release is the top entry of `docs.release_log`.
- Uncommitted changes: list them and ask **one** question — include, stash, or stop.
  Never deploy a tree that differs from what was tested.
- Collect the issues-log entries and PRD sections completed since the last release; they
  are the release notes.

**Gate:** the exact tree (commit) being shipped is named; the notes list is drafted.

## Phase 2 — VERIFY GATE

- `commands.verify` — must exit 0. Backend present → `commands.test_backend`. E2E present
  → `commands.test_e2e` (whole suite if the release touches workflows; else the specs for
  the touched areas — say which).
- Red anywhere → **stop**. Report the failure with its output; do not "deploy the
  frontend only". A red gate is a finding, not an obstacle.

**Gate:** every configured suite green, in this session, on this tree.

## Phase 3 — DEPLOY

- Confirm the target environment with the user if the manifest lists more than one, or if
  the deploy script takes a tenant / environment argument. Read the script's own refusals
  (tenant mismatch, base path) and satisfy them — never bypass them.
- Run `commands.deploy`. Capture its output.
- Config-only changes (packs, flags, seed rows) may need `commands.reseed` or a config
  re-seed: say so explicitly and **ask before running anything that truncates or
  rewrites data**; take the backup the seeding doc prescribes first.

**Gate:** the deploy command exited 0 and printed the build / version it published.

## Phase 4 — SMOKE

- `commands.smoke` (health endpoint). Then check the things a health endpoint cannot:
  an **asset** answers with the right content type (a wrong base path serves HTML for
  JS and shows a blank page behind a 200); the version stamp in the running app equals
  the tree you shipped; a login works; one API call per touched module returns the new
  shape.
- Failure → say exactly what is wrong and whether the previous version is still
  reachable; rolling back is the user's call unless the site is down.

**Gate:** health, asset type, version stamp, login, touched endpoints — each observed.

## Phase 5 — RECORD

- Prepend to `docs.release_log`: `## <version> — <date>` · commit · environment ·
  **Shipped** (the issues-log ids and PRD sections) · **Verification** (suite counts, smoke
  results) · **Notes** (reseed run? hot-patch superseded? anything the next deployer needs).
- Tag the commit if the repo uses tags.
- Refresh derived pages: `/issues-dashboard` if the log grew; `commands.docs_site` if it
  exists.
- Tracker: issues in `fixed` that this release carries can now be verified by testers —
  say so in the report with their keys.

Report: version, environment, what shipped (ids), gates and smoke results, and the keys
testers can now verify. Do not commit the release-log entry unless asked.

## Definition of done

- [ ] Tree identified; uncommitted changes resolved by the user's choice.
- [ ] Every configured suite green on this tree, this session.
- [ ] Deploy run through the manifest command; its own refusals honoured, not bypassed.
- [ ] Smoke: health, asset content type, version stamp, login, touched endpoints.
- [ ] Release-log entry; derived pages refreshed; testers told what to verify.

## Anti-patterns

- Deploying a tree that differs from the tested one.
- "The frontend tests are green, the backend failure is unrelated."
- Bypassing the deploy script's tenant / environment refusal.
- Trusting `/` returning 200 as proof the app is up.
- Reseeding without a backup and without asking.
