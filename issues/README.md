# Issue tracker

A lean, standalone tracker for testers: one FastAPI process, one SQLite file, screenshots
on disk, a single static page. No build step, no framework on the client. Everything
project-specific comes from the environment, which `tools/factory.py env` derives from
`factory.yaml`.

```bash
python3 -m pip install -r issues/requirements.txt
eval "$(python3 tools/factory.py env)"                  # ISSUES_PREFIX, ISSUES_BRAND, ISSUES_MODULES …
python3 -m uvicorn issues.app:app --port 3002           # http://127.0.0.1:3002/
python3 issues/seed_import.py --log                     # import docs/issues_log.md as closed issues (optional)
python3 -m pytest issues/tests -q
```

Data lives in `issues/data/` (`ISSUES_DATA` to move it; gitignored). Set `ISSUES_TOKEN` to
require a token — testers paste it once on the page, the CLI reads it from the environment.

| Env | Meaning | Default |
|---|---|---|
| `ISSUES_PREFIX` | key prefix (`IS-501`) | `IS` |
| `ISSUES_BRAND` | eyebrow and page title | `Issue tracker` |
| `ISSUES_MODULES` | comma list for the module picker (`other` is always added) | generic list |
| `ISSUES_FIRST_NUM` | first tester-filed number (room below for an import) | `501` |
| `ISSUES_ROLES` | roles the board accepts | `tester,agent,admin` |
| `ISSUES_CUSTOMER` | `1` = status only, the analysis never leaves the server | off |
| `ISSUES_PUSH_ACTOR` | how a status pushed to a customer board signs itself | `Product team` |
| `FEEDBACK_SYNC_URL` / `_TOKEN` / `_INTERVAL` | mirror a customer board into this one | off |

## Who does what

| Actor (`X-Role`) | May move an issue |
|---|---|
| tester (default) | more_info → open (note required); fixed / duplicate / as_speced → verified or open; verified → closed or open; closed → open |
| agent (the Issue Agent) | new / open → fixed, duplicate, as_speced, more_info — and writes the analysis fields |
| admin | anything (the page offers "Set status…" when the role is admin) |

The Issue Agent never verifies or closes; a tester never gives a verdict. `tools/issues_cli.py` is
its client; `.claude/agents/issue-agent.md` is the procedure and `/process-issues` launches it.

## Two boards

- **Internal board** — testers and the Issue Agent. Full analysis visible.
- **Customer board** (optional) — the same image with its own database, `ISSUES_CUSTOMER=1`,
  `ISSUES_ROLES=tester,agent`, its own prefix (e.g. `FB`). The internal board mirrors it
  (`FEEDBACK_SYNC_URL`): customer issues arrive internally with source `customer`, verdicts
  are written internally, and only the status travels back — `more_info` at once, a verdict
  after an internal tester marks the mirror Verified. See `deploy/docker-compose.issues.yml`.

## API

`GET /api/issues[?status=a,b&module=&source=&kind=&q=&full=1]`, `GET /api/issues/{key}`,
`POST /api/issues`, `POST /api/issues/{key}/comments`, `POST /api/issues/{key}/transition`
(`{to, note, screenshots, agent?}`), `POST /api/uploads` (multipart image), `GET /uploads/{id}`,
`GET /api/stats`, `GET /api/meta`, `POST /api/sync`, `GET /api/docs` (OpenAPI). Headers:
`X-Actor` (name), `X-Role`, `X-Issues-Token` when a token is set.

## Deployment

Internal boxes only: `deploy/docker-compose.issues.yml` runs the two boards behind a
reverse proxy with basic auth. A customer deployment of the product omits this layer and
the path does not exist. The page uses relative URLs, so it works at any prefix.
