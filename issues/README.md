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
| `FEEDBACK_BOARDS` | the customer boards this internal board triages: `acme=http://acme-feedback:3002,globex=…` (list a board that was mirrored before first: old mirrors migrate onto it) | off |
| `FEEDBACK_TOKEN_<NAME>` | that board's `ISSUES_TOKEN` (`FEEDBACK_TOKEN_ACME`; `-` in a name becomes `_`) | none |
| `FEEDBACK_SYNC_INTERVAL` | seconds between syncs; `0` = only on `POST /api/sync` | `30` |

## Who does what

| Actor (`X-Role`) | May move an issue |
|---|---|
| tester (default) | more_info → open (note required); fixed / duplicate / as_speced → verified or open; verified → closed or open; closed → open |
| agent (the Issue Agent) | new / open → fixed, duplicate, as_speced, more_info — and writes the analysis fields; triages customer reports (attach, promote, ask, detach) |
| admin | anything (the page offers "Set status…" when the role is admin) |

The Issue Agent never verifies, closes or reopens; a tester never gives a verdict. `tools/issues_cli.py`
is its client; `.claude/agents/issue-agent.md` is the procedure and `/process-issues` launches it.

## One board per customer

- **Internal board** — testers and the Issue Agent. Full analysis visible.
- **Customer boards** (optional, one per customer) — the same image, each with its own deployment,
  database, token and prefix (`ACME`, `GLX`), `ISSUES_CUSTOMER=1`, `ISSUES_ROLES=tester,agent`. No
  customer ever sees another customer's reports.

The internal board syncs every board in `FEEDBACK_BOARDS` (every 30 s, or `POST /api/sync`). Sync
creates **no issues**: a new customer report lands in the **intake** queue (table `reports`, ref
`acme/ACME-501`), with its comments and screenshots. The Issue Agent triages each one:

| Move | Effect |
|---|---|
| `attach acme/ACME-501 --to IS-612` | the same defect as an existing issue: link it. Again on the same issue = keep it there, clear its flag |
| `promote acme/ACME-501` | a new defect: the report becomes a new issue (its title, description, screenshots, reporter; source `customer`) |
| `ask acme/ACME-501 "…"` | `more_info` to that one report's board, at the next sync; no other board, and the issue does not move |
| `detach acme/ACME-501` | unlink (a reopen that is a different defect); back to intake, to promote or attach elsewhere |

What travels back is status only, with a generic note (no internal keys, no other customers):
`more_info` and the question as soon as the agent asks; the issue's verdict once a tester marks it
**Verified** (or it is closed), to **every** linked report. A customer never sees `duplicate`: a
verified duplicate passes on the verdict of the issue it duplicates, once that one is verified too.

A customer's own moves are recorded on their report only. An answer (`more_info → open`) flags it
`answered`; a reopen after a verdict flags it `reopened` and comments on the linked issue. Nothing
reopens by itself and the verdict it reopened is not sent again: the agent detaches and promotes it
(a different defect) or recommends that a tester reopen the issue; the next verdict verified there
reaches it. The issue page shows a **Customer reports** card; the list has an **Intake** chip.

A board that was **mirrored** before (one issue per customer issue, `sourceRef` = its key) migrates on
startup: each mirror becomes an issue with one attached report on the first board in `FEEDBACK_BOARDS`.

### Dropping a report in from another app

An app with no board of its own (the support desk, as board `support`) files straight into intake and
reads the outcome back. Role `agent` or `admin`, the internal board's `ISSUES_TOKEN`:

```
POST /api/reports   {board, key, title, reporter, description?, module?, kind?, severity?, persona?, build?, screenshots?}
     → 201 the report (issue: null)        409 already in, or board is a FEEDBACK_BOARDS board   400 unknown module/kind/severity
GET  /api/reports/{board}/{key}  → the report + release: null | {status: more_info | fixed | as_speced, at, note}
```

`board` is a slug (`[a-z0-9-]`), `key` has no `/`. Upload screenshots first (`POST /api/uploads`) and
pass the ids. `release.at` changes whenever a new outcome is decided; act on each new value once.

## API

`GET /api/issues[?status=a,b&module=&source=&kind=&q=&full=1]`, `GET /api/issues/{key}` (with
`customerReports` in full), `POST /api/issues`, `POST /api/issues/{key}/comments`,
`POST /api/issues/{key}/transition` (`{to, note, screenshots, agent?}`), `POST /api/uploads`
(multipart image), `GET /uploads/{id}`, `GET /api/stats` (`intake`, `flagged` on the internal board),
`GET /api/meta`, `POST /api/sync`, `GET /api/reports[?intake=1&board=]`, `GET|POST` as above,
`POST /api/reports/{board}/{key}/attach` (`{to, note}`) · `/promote` · `/ask` (`{text}`) · `/detach`,
`GET /api/docs` (OpenAPI). Headers: `X-Actor` (name), `X-Role`, `X-Issues-Token` when a token is set.

## Deployment

Internal boxes only: `deploy/docker-compose.issues.yml` runs the internal board and one feedback
board per customer behind a reverse proxy with basic auth. A customer deployment of the product
omits this layer and the path does not exist. The page uses relative URLs, so it works at any prefix.
