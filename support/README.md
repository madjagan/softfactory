# Support desk

A sibling of `issues/`: one FastAPI process, one SQLite file, screenshots on disk, one static
page with a customer view and a support view, and an in-app widget. One server for every org;
isolation is the org filter on every query, proved by `support/tests` (release-blocking).

```bash
python3 -m pip install -r support/requirements.txt
eval "$(python3 tools/factory.py env)"                  # SUPPORT_PREFIX, SUPPORT_ORGS, …
python3 -m uvicorn support.app:app --port 3003          # http://127.0.0.1:3003/
python3 -m pytest support/tests -q
```

| Env | Meaning | Default |
|---|---|---|
| `SUPPORT_PREFIX` | key prefix (`SUP-1001`) | `SUP` |
| `SUPPORT_BRAND` | eyebrow and page title | `Support` |
| `SUPPORT_ORGS` | comma list of customer orgs | none |
| `SUPPORT_TOKEN` | the support team's shared token (roles support, agent, admin) | open |
| `SUPPORT_TOKEN_<ORG>` | one per org; the token a customer presents is their org | open |
| `SUPPORT_WIDGET_SECRET_ENV` | name of the env var holding the widget signing secret | `SUPPORT_WIDGET_SECRET` |
| `SUPPORT_AUTO_CLOSE_DAYS` | an unanswered `resolved` ticket closes after this (0 = off) | `7` |
| `SUPPORT_CATEGORIES` | comma list | `question,how-to,defect,account,other` |
| `SUPPORT_FIRST_NUM` | first ticket number | `1001` |
| `SUPPORT_TRACKER_URL` | the internal tracker; set it and escalating a ticket drops it into the tracker's intake as board `support` | none (escalation then needs an issue key) |
| `SUPPORT_TRACKER_TOKEN` | the tracker's `ISSUES_TOKEN` | none |
| `SUPPORT_TRACKER_SYNC_INTERVAL` | seconds between outcome checks (0 = only `POST /api/sync`) | `60` |

**Escalation.** With `SUPPORT_TRACKER_URL` set, support escalates a ticket and it lands in the tracker's
intake (`POST /api/reports`, board `support`, key = the ticket key); an issue key support types is passed
on as a hint. The sync reads `GET /api/reports/support/<key>`: a question from the product team becomes an
internal note, and a verdict (released once an internal tester verifies the issue) becomes a **draft** for
support to send. The ticket stays `escalated` until support resolves it.

With no token configured at all the app is open for local dev and a customer names their org
in `X-Org`. Once any token is set, every request needs a matching one.

## Who does what

| Role (`X-Role`) | May |
|---|---|
| customer | file; read and reply to **their own** tickets (other requesters and other orgs get 404); confirm (`resolved → closed`) or reopen (note required; reopening `closed` starts a new linked ticket) |
| support | reply (public), internal notes, edit and send drafts, category and priority, `new/open/waiting → open/waiting/escalated/resolved`, `escalated → open/resolved`, `resolved → open` |
| agent | drafts, internal notes (incl. the escalation recommendation), category. Never sends, never changes status |
| admin | anything |

A customer's reply on `waiting_on_customer` or `resolved` moves the ticket to `open`.
`escalated` needs `issueRef`, the internal issue key, stored on the support side only.

The customer API is an allowlist (`customer_view`): public messages only, no `escalation`,
category, priority or org list, and every non-customer actor in `history` reads `Support`.

## Widget

```html
<script src="https://support.example.com/widget.js" data-token="SIGNED" data-app-version="3.4.1" async></script>
```

The product's backend signs `{org, email, name, userId?, exp}` with the secret, in the same
format as `support.app.sign_widget_token`: `base64url(json) + "." + base64url(HMAC-SHA256(secret, that part))`.
The widget files with the page URL, app version and user agent, and lists the user's tickets.

## API

`GET /api/tickets[?status=&org=&category=&q=&needsDraft=1&full=1]`, `GET /api/tickets/{key}`,
`POST /api/tickets`, `POST /api/tickets/{key}/messages` (`{text, screenshots, visibility, tag}`),
`POST /api/tickets/{key}/messages/{id}` (edit a draft), `POST /api/tickets/{key}/messages/{id}/send`,
`POST /api/tickets/{key}/fields` (`{category, priority}`), `POST /api/tickets/{key}/transition`
(`{to, note, issueRef}`), `POST /api/uploads`, `GET /uploads/{id}`, `GET /api/meta`, `GET /api/stats`,
`GET /widget.js`. Headers: `X-Role`, `X-Actor`, `X-Email` (customer), `X-Support-Token`, or `X-Widget-Token`.

Auto-close runs whenever tickets are read; time comes only from `support.app.now` (the clock seam).
`tools/support_cli.py` is the Support Agent's client; `/process-tickets` launches it.
