# {{project_name}} — Human Test Plan

**Date:** {{date}} · **Product:** {{project_name}} · **Companion:** `TESTING_COMPANION.md`

## Purpose

The structured half of manual testing. One observable expectation per row, across the whole product, sourced from `FEATURE_LIST.md` and the PRD sections it cites. The exploratory half is `TESTING_COMPANION.md` Part B. Run this plan first; then run the charters.

## How to run

- Environments: local `{{env_local}}` · staging `{{env_staging}}` · production `{{env_production}}`.
- Logins: {{logins}}. Password: `{{password}}`.
- Seed narrative date: {{narrative_date}}. Notable records: {{notable_records}}.
- Record Pass / Fail / Blocked per row, one-line note. A Fail becomes a report in the companion's Part C shape and goes on the issue tracker.
- Rows marked **(changes data)** alter the shared database; write them into the hand-over.

## Summary

| Area | Cases | Personas used |
|---|---|---|
| {{area}} | {{n}} | … |
| **Total** | **{{n}}** | |

---

## {{area_1}}

| ID | Title | Login | Preconditions | Steps | Expected | Result |
|---|---|---|---|---|---|---|
| {{AREA}}-01 | … | … | none | Log in · … | … — cites `§3.N` criterion k / feature id | |

---

*Generated from `FEATURE_LIST.md` v{{fl_version}} ({{fl_date}}) on {{date}}.*
