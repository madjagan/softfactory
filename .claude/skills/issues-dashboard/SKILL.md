---
name: issues-dashboard
description: "Refresh the Issue Ledger page: classify every issues-log entry not yet in the classified JSON (fixed taxonomy: kind, issue bucket, fix kind, layer, module, regression test), re-render the dashboard HTML with tools/issues_dashboard.py, and republish it to the artifact URL stored in the JSON so the link never changes. Triggers on: /issues-dashboard, refresh the issues page, update the issue ledger, reclassify the issues log, issues stats, bug trends."
metadata:
  author: "softfactory"
  version: "2.0"
  category: "reporting"
---

# Issue Ledger — refresh

The page is generated, never hand-edited. Its data is the classified JSON
(`docs.issues_classified`): one record per `## ` entry of the issues log
(`docs.issues_log`), matched by the first 90 characters of the title. Steps in order; stop
at the first that fails.

## 1. Find what is new

```bash
python3 tools/issues_dashboard.py --pending
```

Prints headers of log entries with no record (or "nothing pending" → skip to step 3).

## 2. Classify the new entries

Read each pending entry (`grep -n "^## " <log>` for line numbers; read only that range).
Append one record per entry to `entries`, **in log order**, with exactly these fields:

- `id` — the identifier in the header (`#12`, `§3.44`, `FB-019`, `Diagnostic`, else the first 40 chars)
- `title` — header text after `## `, max 100 chars
- `kind` — `bug` · `feature` · `diagnostic` · `docs` · `other` (a product decision)
- `issue_bucket` — PRIMARY nature of the root cause: `functional-logic` · `boundary-condition`
  · `missing-validation` · `integration-wiring` · `data-config` · `authorization` ·
  `ui-display` · `crash-robustness` · `performance` · `tooling-infra` · `not-applicable`
- `fix_kind` — dominant edit: `logic-correction` · `new-validation` · `wiring-plumbing` ·
  `data-config-change` · `new-mechanism` · `refactor-consolidation` · `defensive-handling` ·
  `ui-change` · `test-or-docs-only` · `none`
- `layer` — `frontend` · `backend` · `both` · `data` · `docs` · `infra`
- `module` — one word from `issues.modules` in `factory.yaml` (or `other`)
- `regression_test_added` — true when the entry names a test added or changed
- `note` — max 15 words on the mechanism

The ROOT CAUSE decides the bucket; the dominant edit decides the fix kind. A feature entry
that also closed a defect keeps `kind: feature` with a real bucket. Do not change existing
records unless the log entry changed; do not bump `taxonomy_version` unless the lists
above change (then reclassify everything). Re-run `--pending` until it prints nothing.

## 3. Render and republish

```bash
python3 tools/issues_dashboard.py
```

Publish the HTML with the Artifact tool, passing `url` = `meta.artifact_url` from the
JSON (this keeps the link stable) and a short `label` like `"<N> entries · #1 to #<last>"`.
First ever publish: no `url`, then write the returned URL into `meta.artifact_url`. If the
project serves an internal docs site (`commands.docs_site`), run it too.

## 4. Report

One paragraph: entries added and their buckets, the new vitals, the URL. Offer to commit
the JSON, the HTML and any log changes; do not commit unasked.
