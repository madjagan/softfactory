# Spec — one board per customer, triaged into shared internal issues

## Purpose

The tracker exists to collect issues during testing:

- **Internal board**: the engineering team reports issues while testing.
- **Customer boards**: early customers report issues. There is **one board per customer**, so no
  customer ever sees another customer's reports.

The **Issue Agent** triages every customer report into the internal board. Reports of the same
defect from different customers (and from the internal team) end up on **one internal issue**
that links them all. The fix is tracked once, and the outcome goes back to every reporter on
their own board.

## Goals and success criteria

| # | Criterion | Proved by |
|---|---|---|
| G1 | N customer boards, each its own deployment, database, token and key prefix | compose + manifest; test with 2 boards |
| G2 | Nothing from customer A's report reaches customer B's board: no text, screenshots, keys, names or count | test: A and B link to one issue; B's board API shows only B's data |
| G3 | Sync creates **no issues**. New customer reports land in an **intake queue** on the internal board | test |
| G4 | The agent triages each intake report: **attach** it to an existing internal issue, or **promote** it to a new internal issue (the first report becomes the issue, keeping its title, description and screenshots) | tests for both paths |
| G5 | The internal issue lists every linked report (customer, key, reporter, their status, their comments and screenshots) | API + page |
| G6 | Once an internal tester **verifies** the issue, the verdict goes to **every** linked customer report | test with 2 customers |
| G7 | `more_info` is **per report**. The agent asks one customer, and only that board gets the question | test |
| G8 | When a customer **reopens** after a verdict, their report is flagged on the internal issue and the agent decides. Nothing reopens automatically | test |
| G9 | Existing single-board data (mirror issues) migrates on startup to issues with one attached report | test |
| G10 | Customer boards are unchanged: same app, `ISSUES_CUSTOMER=1`, status only | existing tests stay green |

## Data model (internal board)

New table `reports`, one row per customer report, with a JSON doc:

```
{ board: "acme", key: "ACME-501",             # unique together
  title, description, module, kind, severity, reporter, build, createdAt,
  screenshots: [ids],                         # copied into the internal board's uploads
  comments: [...],                            # the customer's words, in order
  customerStatus: "new" | ...,                # what their board shows now
  issue: null | "IS-612",                     # null = in intake
  flag: "" | "reopened" | "answered",         # needs the agent's attention
  sync: { commentsSeen, historySeen, pushedAt } }
```

An issue doc gets `reports: ["acme/ACME-501", "globex/GLX-503"]`. The API returns those reports
in full when it returns the issue.

`source: "customer"` and `sourceRef` on issues are retired, apart from migrated data.

## Behaviour

### Sync (mechanical, every 30 s, for each board in `FEEDBACK_BOARDS`)
1. Pull the board's issues. An unknown key creates a `reports` row with `issue: null` (intake).
2. Copy new comments and screenshots onto the report row.
3. Customer moves are recorded on the report only (`customerStatus`):
   - `more_info → open` (they answered): set `flag: "answered"`.
   - A reopen after a verdict: set `flag: "reopened"` and add a comment on the linked issue
     ("ACME-501 reopened by <customer>: <note>").
   - Verify or close: record it on the report only. It never moves the internal issue.
4. Status sent back to each report:
   - `more_info` as soon as the agent asks that report.
   - The issue's verdict (fixed / duplicate / as_speced) once the internal issue is **verified
     or closed**, sent to every linked report that hasn't been reopened since.
   - Notes stay generic: no internal keys and no mention of other customers.

### Agent triage (new CLI commands, role `agent`)
- `intake`: list unlinked reports and flagged reports.
- `attach acme/ACME-501 --to IS-612`: link the report to an existing issue.
- `promote acme/ACME-501`: create a new internal issue from the report (source `customer`) and
  link it.
- `ask acme/ACME-501 "question"`: send `more_info` to that one report.
- `detach acme/ACME-501`: unlink (for a reopen that turns out to be a different defect). It is then
  promoted or attached elsewhere.
- Verdicts stay on the internal issue (`verdict IS-612 …`), unchanged.

### Reopen (G8)
The agent can't reopen a verified issue. That move belongs to testers, and the role rules stay as
they are. Its options:
- **detach + promote** the report as a new issue (a different defect), or
- **recommend a reopen** in its report, which a human makes on the internal board.

### Page
- Internal issue view: a "Customer reports" card with one row per linked report, showing customer,
  key, reporter, their status, any flag, and their comments.
- Internal list: an "Intake" filter showing the unlinked count.
- Customer page: no change.

### Configuration
- `factory.yaml`: `issues.customer_boards: [{name: acme, url: ..., prefix: ACME}]`. This replaces
  `issues.customer_board`.
- Env: `FEEDBACK_BOARDS="acme=http://acme-feedback:3002,globex=..."`, with tokens in
  `FEEDBACK_TOKEN_<NAME>`. `FEEDBACK_SYNC_URL` is removed.
- `deploy/docker-compose.issues.yml`: one internal service, plus one `feedback` service per
  customer. `/setup-project` writes these from the manifest list.

## Out of scope
- One customer app hosting several customers (rejected: separate deployments are the isolation
  guarantee).
- Customers seeing that others reported the same thing.
- Automatic similarity matching. The agent decides every link.

## Open questions
1. **Duplicate verdict to customers.** When the shared issue's verdict is `duplicate` (of another
   internal issue), should linked reports instead get the other issue's verdict once that one is
   verified? Proposed: yes. A customer only ever sees fixed, as_speced or more_info, never
   "duplicate".
2. **Customer names on internal issues.** A promoted issue keeps the first customer's wording and
   reporter name (you chose this). Is that fine for the whole internal team to see?
3. **Board names.** Is a short customer slug (`acme`) the right key everywhere: config, report
   refs (`acme/ACME-501`), container names?
