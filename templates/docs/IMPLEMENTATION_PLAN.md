# {{project_name}} — Implementation Plan & Test Gates

**Companion to:** `PRODUCT_REQUIREMENTS.md`
**Rule:** a PRD section is **feature-complete only when its test file passes** in the
verify gate (`{{verify}}`). The CI / container build runs the full suite — a red suite
blocks deployment.

---

## Phase overview

| Phase | Scope | Status |
|---|---|---|
| **0. Test infrastructure** | Runners per layer, `verify` script, CI / container test gate, clock seam | {{status_0}} |
| **1. Ledger** | PRD, plan, issues log, feature list, human test plan, tracker | ✅ Done ({{date}}) |
| **2. Modules** | One PRD §3 section at a time, each gated by its test file (table below) | Planned |
| **3. Hardening** | Auth, audit, backups, monitoring, rate limits | Planned |
| **4. Backlog** | From the gap register in `FEATURE_LIST.md` §8 | Planned |

---

## Test gates per PRD section

Every row names the file that is the section's definition of done. `/create-feature`
adds a row with status `In progress (date)` and risks; flips it to `✅ Complete (date)`.

| PRD § | Feature | Test file | Acceptance criteria (what the tests assert) | Risks & mitigations | Status |
|---|---|---|---|---|---|
| 3.1 | {{module_1_title}} | `{{unit_dir}}/{{module_1}}.test.*` | … | … | Planned |
| 3.2 | {{module_2_title}} | `{{unit_dir}}/{{module_2}}.test.*` | … | … | Planned |

---

## Automation gates

1. **Local:** `{{verify}}` — full suite + build; run before any deploy.
2. **Container / CI:** the image build (or CI job) runs the suite before the build step; a failing test fails the build.
3. **Deploy:** `{{deploy}}` refuses when the gate is red or the target does not match the build.
4. **Release record:** `/release` writes `RELEASE_LOG.md`.

---

## Known data issues / reconciliation backlog

(Rows whose tests assert something the data no longer matches. Empty on day one.)
