# Ideas portal

A lightweight feature-request portal: one FastAPI process, one SQLite file, screenshots on
disk, a single static page with two views. Customers submit and vote on the **portal view**;
the team curates on the **product view**; the Ideas Agent links and syncs from the ledger
through `tools/ideas_cli.py`. Spec: `docs/specs/ideas-portal.md`.

```bash
python3 -m pip install -r ideas/requirements.txt
eval "$(python3 tools/factory.py env)"                       # IDEAS_URL, IDEAS_PREFIX, IDEAS_ORGS …
IDEAS_TOKEN_ACME=dev-acme python3 -m uvicorn ideas.app:app --port 3004    # http://127.0.0.1:3004/
python3 -m pytest ideas/tests -q
```

Data lives in `ideas/data/` (`IDEAS_DATA` to move it; gitignored).

| Env | Meaning | Default |
|---|---|---|
| `IDEAS_ORGS` | comma list of customer orgs | none |
| `IDEAS_TOKEN_<ORG>` | one token per org; the token decides the org | none (no customer can sign in) |
| `IDEAS_TOKEN` | the team token (product / agent / admin); **set it on any deployment customers reach** | empty = open team (local dev) |
| `IDEAS_PREFIX` / `IDEAS_SUBMISSION_PREFIX` | key prefixes (`IDEA-3`, `IDR-12`) | `IDEA` / `IDR` |
| `IDEAS_BRAND` | eyebrow and page title | `Ideas` |

## Tenancy

One server for every org. A customer's org comes from their token (`X-Ideas-Token`), never
from a header they choose, and every portal query is filtered by it: another org's
submission is a 404, their screenshots are a 404. Customers reach only `/api/portal/*`
(and uploads); the team API answers them 403. An org token cannot act as the team.
Internal submissions logged on behalf of an org stay internal.

**Voting identity** is the org token plus a typed name, as on the tracker. One person can vote
twice under two names; accepted for a lightweight tool. Names are compared case-insensitively.

## Who does what

| Role (`X-Role`) | May |
|---|---|
| `customer` (default) | submit; see their org's submissions (status in plain words, sent notices); see and vote on published ideas |
| `product` | everything the agent may, plus: publish, accept (with the PRD §), decline, already built, merge, send notices, log internal submissions, re-attach a linked submission |
| `agent` (the Ideas Agent) | add tracker / support submissions, attach, promote, edit the team's text and the public draft, recommend, move `new → under_review`, apply `in_development` / `shipped` with a citation, draft notices. Never accepts, declines, publishes or sends |
| `admin` | any status |

## Idea states

`new → under_review` (problem + drafted public text needed) → product decides from either:
`accepted` (prdRef) · `declined` (reason; a public reason too if published) · `already_built`
(featureId) · `merged` (into another idea: submissions and votes move across, duplicates
dropped). Then from the ledger, with a citation: `accepted → in_development → shipped`.

What a submitter sees: received / under review / planned / in development / shipped / not
planned / already available. A declined published idea stays on the portal as **not planned**
with its public reason. Publishing refuses public text that names a linked requester or org,
or quotes a submission word for word.

**Demand** is computed on read: distinct orgs and people (submitters and voters), votes,
linked tickets (source `support`) and linked issues (source `tracker`). `GET /api/ideas?sort=`
any of them.

## API

Portal: `GET /api/portal/submissions[/{key}]`, `POST /api/portal/submissions`,
`GET /api/portal/ideas`, `POST /api/portal/ideas/{key}/vote` (toggle).
Team: `GET|POST /api/submissions`, `GET /api/submissions/{key}`, `POST /api/submissions/{key}/attach|promote`,
`GET /api/ideas[?status=&sort=]`, `GET /api/ideas/{key}`, `POST /api/ideas/{key}/edit|publish|transition|recommend|drafts`,
`POST /api/ideas/{key}/drafts/{n}/send`. Both: `POST /api/uploads`, `GET /uploads/{id}`, `GET /api/meta`.
Headers: `X-Actor` (name), `X-Role`, `X-Ideas-Token`.

## Deployment

`deploy/docker-compose.ideas.yml`, behind your reverse proxy with TLS. The compose file
refuses to start without `IDEAS_TOKEN` and `IDEAS_ORGS`.
