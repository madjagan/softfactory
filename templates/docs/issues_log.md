# Issues Log

A running log of issues found, their root cause, and the fix applied — and of every
feature completed and every diagnostic sweep. Each entry is separated by a horizontal
rule. Entries are appended by `/fix-issue` (`## #N — title`), `/create-feature`
(`## §3.N — title`) and `/find-issues` (`## Diagnostic — scope (date)`). Dates are real
(`date +%F`), never guessed.

Entry shape for a bug:

- **Date:** YYYY-MM-DD
- **Reported symptom:** what the user did, expected, saw
- **Area:** module / layer

**Root cause** — the mechanism, to `file:line`, and why it manifested only under the trigger.

**Fix** — what changed and why it cannot affect anything else.

**Files changed** — list, one line each.

**Verification** — the regression test (would have failed before), suite results, the reproduction re-run.

**Deploy note** — hot-patched? durable deploy pending? reseed needed?

---

## #0 — Factory set up

- **Date:** {{date}}
- **What was created:** `factory.yaml`, the docs ledger, `CLAUDE.md`, the issue tracker.
- **Gates verified:** {{gates_verified}}

---
