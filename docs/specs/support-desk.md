# Spec — lightweight support desk (`support/`)

## Purpose

Customers of a live product ask for help, and a small support team answers them. Most tickets are
questions that can be answered from the user guides. A ticket that turns out to be a defect is
**escalated** into the issue tracker. There it is attached to an internal issue, using the same
attach/promote model as the per-customer boards, and the outcome comes back to the ticket.

It lives inside softfactory as a sibling of `issues/`. `install.sh` installs it into every project,
and it is configured from `factory.yaml`.

**Depends on** the [per-customer-boards spec](per-customer-boards.md). Escalation reuses its intake queue and its
`attach` / `promote` commands. Build that first.

## Architecture (mirrors `issues/`)

| | Issue tracker | Support desk |
|---|---|---|
| Process | FastAPI + one SQLite file + uploads on disk | same |
| Page | one static `index.html`, no build step | same, with a customer view and a support view |
| Config | env derived from `factory.yaml` by `tools/factory.py env` | `support:` block, same mechanism |
| Agent | Issue Agent (`.claude/agents/issue-agent.md`), role `agent` | **Support Agent** (`.claude/agents/support-agent.md`), role `agent` |
| CLI | `tools/issues_cli.py` | `tools/support_cli.py` |
| Skill | `/process-issues` launches the agent | `/process-tickets` launches the agent |
| Rules | state machine enforced on the server | same |
| Deploy | `deploy/docker-compose.issues.yml` | `deploy/docker-compose.support.yml` |

New files are needed because this is a separate app. Shared code (the upload handling, the token
check) is copied, not factored out, until a third app needs it.

## Goals and success criteria

| # | Criterion | Proved by |
|---|---|---|
| S1 | A customer files a ticket from the **web form** (title, description, screenshots) and sees only their own organisation's tickets | API test: org A cannot list or fetch org B's tickets (404, not 403) |
| S2 | The **in-app widget** (`support/widget.js`, one script tag) files a ticket with the page URL, app version and user filled in, authenticated by a token the product's backend signs | test with a signed and a forged token |
| S3 | The Support Agent **drafts** replies. A draft never reaches the customer until a support person sends it | server test: the agent role cannot publish; the customer API never returns drafts |
| S4 | Server-enforced state machine (below); every move is in `history` | API tests per role |
| S5 | **Escalation**: support (or the agent, as a recommendation) escalates a ticket. It appears in the tracker's intake as a report from board `support`, and the Issue Agent attaches or promotes it | integration test with both apps |
| S6 | Once the internal issue is **verified**, the ticket gets the outcome as a **draft** for support to send. The ticket stays `escalated` until then | integration test |
| S7 | Internal analysis (root cause, internal keys, other customers) never reaches a customer | test on the customer API |
| S8 | Customers can confirm a fix (`resolved → closed`) or reopen it. An unanswered `resolved` ticket auto-closes after `support.auto_close_days` | tests with the clock seam |

## Roles

| Role (`X-Role`) | Who | May do |
|---|---|---|
| `customer` | the end user, through the page or the widget | file, comment, answer, confirm or reopen their own org's tickets |
| `support` | the human support team | everything on any ticket: reply (send), set status, escalate, send or edit drafts |
| `agent` | Support Agent, through the CLI | read, write **drafts**, set category, recommend an escalation. It never sends and never changes status |
| `admin` | operator | anything |

## States

```
new ──support──► open ──support──► waiting_on_customer ──customer replies──► open
                  │                                                          ▲
                  ├──support──► escalated ──verdict draft sent──► resolved ──customer reopens──┘
                  └──support──► resolved ──customer confirms / auto-close──► closed
```

- `new`: just filed.
- `open`: support owns it.
- `waiting_on_customer`: a question has been sent. A customer comment moves it back to `open`
  automatically.
- `escalated`: linked to an internal issue (`issueRef` is stored on the support side only).
- `resolved`: an answer or fix has been sent and is waiting for the customer to confirm.
- `closed`: final. A customer reopening a `closed` ticket starts a new one, linked to the old one.

## Data model

`tickets` table, one JSON doc per ticket (the same pattern as issues):

```
{ key: "SUP-1042", org: "acme", requester: {name, email, userId?},
  title, description, category, priority, status,
  context: {pageUrl, appVersion, userAgent},      # widget only
  screenshots: [ids],
  messages: [ {at, by, role, text, screenshots, visibility: "public" | "internal" | "draft"} ],
  escalation: null | {at, by, issueRef, verdict, verdictAt},
  history: [...], createdAt, updatedAt, firstResponseAt }
```

The customer API filters `messages` to `public` and drops `escalation` and `history.by` for
internal actors.

## Agent behaviour (`/process-tickets` → Support Agent, its own context)

**When it runs: on demand only (decided).** Drafts are written when someone runs `/process-tickets`.
There is no schedule and no Claude API call inside `support/`. The server never calls an agent.

The agent reads the repo's docs. The ticket app does not.

1. Pull `new` and `open` tickets that have no current draft.
2. For each one, categorise it (question / how-to / defect / account / other), then check these
   in order:
   1. **Released?** Compare `RELEASE_LOG.md` with the ticket's `context.appVersion`, when the
      widget recorded it. Anything shipped after that version counts as not available to this
      customer.
   2. **Known issue?** Search `docs.issues_log` and the tracker (`issues_cli.py list`, plus
      intake). If the issue is already known, the draft says it is known and being worked on, and
      the agent recommends escalating onto that existing internal issue.
   3. **Feature status:** `docs.feature_list`. ● can be explained. ◐ or a §8 gap is answered as
      "not available yet", never as a how-to.
   4. **How to:** `docs.user_guides` for the requester's persona, quoted.
   5. **Is this the intended behaviour?** The acceptance criteria in `docs.prd`.
3. Write a **draft** reply that cites its sources (`AREA-NN`, guide section, PRD §, issues-log
   `#N`), so support can check it before sending.
4. If it looks like a new defect, write an **escalation recommendation** (an internal note)
   instead of an answer. A human escalates.
5. Report: one line per ticket (key → draft / recommend-escalate / needs human), plus anything
   it couldn't decide.

## Configuration (`factory.yaml`)
```
support:
  url: http://127.0.0.1:3003
  prefix: SUP
  brand: Acme Ledger · Support
  orgs: [acme, globex]            # one token per org: SUPPORT_TOKEN_<ORG>
  widget_secret_env: SUPPORT_WIDGET_SECRET
  auto_close_days: 7
  categories: [question, how-to, defect, account, other]
```

## Out of scope
- Email intake and replies (it could be added later with SES).
- SLAs, routing rules, assignment queues and macros. Only `firstResponseAt` is recorded.
- A knowledge base. The user guides already do that job.
- The agent sending anything to a customer.
- Scheduled or real-time drafting. Drafting is on demand only. A schedule (`/schedule`) or an
  API call inside the server can be added later if first responses are too slow.

## Decisions

- **Tenancy: one server for every org (decided).** Each org has its own token, and every query is
  filtered by org on the server. Isolation therefore rests on code and tests, not on separate
  databases, so S1 and S7 are release-blocking tests. Unlike the per-customer boards, there is one
  deployment for every customer.
- **Drafting: on demand only (decided).** See Agent behaviour.
- **Released and known-issue checks: kept (decided).** See Agent behaviour, step 2.

## Open questions
1. **Visibility inside an org.** Should a customer see every ticket from their org (shared inbox) or
   only their own? Proposed: their own; a later flag can open the shared view.
2. **Support identity.** Support staff authenticate with a shared support token, and names come from
   `X-Actor`, as on the tracker. Is that enough, or do you need per-person logins?
3. **Customer boards after launch.** Once a product is live, do early customers keep their boards, or
   do they move to support?
