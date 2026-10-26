#!/usr/bin/env python3
"""The Issue Agent's side of the issue tracker (issues/app.py): list, show, verdict, screenshots, triage.

  python3 tools/issues_cli.py list [--status new,open]
  python3 tools/issues_cli.py show IS-512 | acme/ACME-501         # an issue (with its customer reports) or one report
  python3 tools/issues_cli.py shots IS-512 | acme/ACME-501 [--out DIR]   # download screenshots to view
  python3 tools/issues_cli.py verdict IS-512 --status fixed --note "…" --root-cause "…" --fix-proposed "…" --fix "…" \
      --tests "…" --human-tests "…" [--files "…"] [--duplicate-of IS-3] [--spec-ref "§3.x"] [--info-needed "…"]
  python3 tools/issues_cli.py comment IS-512 --note "…"
  python3 tools/issues_cli.py split IS-512 --part "title | module | kind | severity | description" [--part …]   # one report → n issues
  python3 tools/issues_cli.py intake                             # customer reports not on an issue, or flagged
  python3 tools/issues_cli.py attach acme/ACME-501 --to IS-612   # the same defect as an existing issue
  python3 tools/issues_cli.py promote acme/ACME-501              # a new defect: the report becomes a new issue
  python3 tools/issues_cli.py ask acme/ACME-501 "question"       # more_info to that one customer only
  python3 tools/issues_cli.py detach acme/ACME-501 [--note "…"]  # unlink, back to intake
  python3 tools/issues_cli.py sync                               # pull every customer board now

Env: ISSUES_URL (default http://127.0.0.1:3002), ISSUES_TOKEN (if the server requires one).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PARSED = urllib.parse.urlsplit(os.environ.get("ISSUES_URL", "http://127.0.0.1:3002").rstrip("/"))
URL = urllib.parse.urlunsplit((PARSED.scheme, PARSED.hostname + (f":{PARSED.port}" if PARSED.port else ""), PARSED.path, "", ""))
TOKEN = os.environ.get("ISSUES_TOKEN", "")


def call(method: str, path: str, body: dict | None = None, raw: bool = False):
    req = urllib.request.Request(f"{URL}/{path.lstrip('/')}", method=method)
    req.add_header("X-Role", "agent")
    req.add_header("X-Actor", "Issue Agent")
    if TOKEN:
        req.add_header("X-Issues-Token", TOKEN)
    if PARSED.username:  # user:pass@host in ISSUES_URL → the proxy's basic auth
        cred = base64.b64encode(f"{PARSED.username}:{PARSED.password or ''}".encode()).decode()
        req.add_header("Authorization", f"Basic {cred}")
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, data, timeout=30) as r:
            return r.read() if raw else json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        sys.exit(f"HTTP {e.code} {path}: {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"Cannot reach {URL}: {e.reason}. Start it with: uvicorn issues.app:app --port 3002")


def cmd_list(a):
    rows = call("GET", f"api/issues?status={a.status}" + (f"&module={a.module}" if a.module else ""))
    for r in rows:
        print(f"{r['key']:8} {r['status']:10} {r['severity'] or '':8} {r['module'] or '':11} {('📎' + str(r['screenshotCount'])) if r['screenshotCount'] else '   ':4} {r['title']}")
    print(f"{len(rows)} issue(s)")


def doc_path(key: str) -> str:
    return f"api/reports/{key}" if "/" in key else f"api/issues/{key}"   # acme/ACME-501 is a customer report


def cmd_show(a):
    print(json.dumps(call("GET", doc_path(a.key)), indent=2, ensure_ascii=False))


def cmd_shots(a):
    doc = call("GET", doc_path(a.key))
    ids = []
    for d in [doc, *(doc.get("customerReports") or [])]:
        ids += d.get("screenshots") or []
        for c in d.get("comments") or []:
            ids += c.get("screenshots") or []
    out = Path(a.out or f"/tmp/issues-{a.key.replace('/', '-')}")
    out.mkdir(parents=True, exist_ok=True)
    for i in ids:
        (out / i).write_bytes(call("GET", f"uploads/{i}", raw=True))
        print(out / i)
    if not ids:
        print("no screenshots")


def cmd_verdict(a):
    agent = {k: v for k, v in {"rootCause": a.root_cause, "fixProposed": a.fix_proposed, "fix": a.fix, "files": a.files, "tests": a.tests,
                                "humanTests": a.human_tests, "duplicateOf": a.duplicate_of, "specRef": a.spec_ref,
                                "infoNeeded": a.info_needed}.items() if v}
    doc = call("POST", f"api/issues/{a.key}/transition", {"to": a.status, "note": a.note or "", "agent": agent})
    print(f"{doc['key']} → {doc['status']} ({', '.join(agent) or 'no analysis fields'})")


def cmd_comment(a):
    doc = call("POST", f"api/issues/{a.key}/comments", {"text": a.note})
    print(f"{doc['key']}: comment added")


def cmd_split(a):
    parts = []
    for raw in a.part:
        f = [x.strip() for x in raw.split("|")]
        if len(f) < 5:
            sys.exit(f"--part needs 'title | module | kind | severity | description': {raw!r}")
        parts.append({"title": f[0], "module": f[1], "kind": f[2], "severity": f[3], "description": "|".join(f[4:]).strip()})
    out = call("POST", f"api/issues/{a.key}/split", {"parts": parts, "note": a.note or ""})
    for c in out["children"]:
        print(f"{c['key']}  new  {c['module']:10} {c['title']}")
    print(f"{out['parent']['key']} split into {', '.join(c['key'] for c in out['children'])}")


def cmd_unsplit(a):
    doc = call("POST", f"api/issues/{a.key}/unsplit", {"text": a.note or ""})
    print(f"{doc['key']}: split folded back; the parts are duplicates of it")


def cmd_intake(a):
    rows = call("GET", "api/reports?intake=true")
    for r in rows:
        print(f"{r['board'] + '/' + r['key']:22} {r['flag'] or '-':9} {r['customerStatus'] or '':10} {r['issue'] or 'unlinked':9} {r['reporter']:14} {r['title']}")
    print(f"{len(rows)} report(s) to triage")


def cmd_attach(a):
    doc = call("POST", f"api/reports/{a.ref}/attach", {"to": a.to, "note": a.note or ""})
    print(f"{a.ref} → {doc['key']} (now {len(doc['reports'])} report(s))")


def cmd_promote(a):
    doc = call("POST", f"api/reports/{a.ref}/promote", {"text": a.note or ""})
    print(f"{a.ref} → {doc['key']} new  {doc['module']:10} {doc['title']}")


def cmd_ask(a):
    call("POST", f"api/reports/{a.ref}/ask", {"text": a.question})
    print(f"{a.ref}: more_info goes to that board at the next sync")


def cmd_detach(a):
    call("POST", f"api/reports/{a.ref}/detach", {"text": a.note or ""})
    print(f"{a.ref}: detached, back in intake — promote it or attach it elsewhere")


def cmd_sync(a):
    for board, rep in call("POST", "api/sync").items():
        if "error" in rep:
            print(f"{board}: {rep['error']}")
            continue
        print(f"{board}: {len(rep['intake'])} new to intake, {rep['comments']} comment(s), {rep['customerMoves']} customer move(s); pushed {rep['pushed'] or 'nothing'}"
              + (f"; skipped {rep['skipped']}" if rep.get("skipped") else ""))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list"); s.add_argument("--status", default="new,open"); s.add_argument("--module"); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("show"); s.add_argument("key"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("shots"); s.add_argument("key"); s.add_argument("--out"); s.set_defaults(fn=cmd_shots)
    s = sub.add_parser("verdict"); s.add_argument("key")
    s.add_argument("--status", required=True, choices=["fixed", "duplicate", "as_speced", "more_info"])
    for opt in ("--note", "--root-cause", "--fix-proposed", "--fix", "--files", "--tests", "--human-tests", "--duplicate-of", "--spec-ref", "--info-needed"):
        s.add_argument(opt)
    s.set_defaults(fn=cmd_verdict)
    s = sub.add_parser("comment"); s.add_argument("key"); s.add_argument("--note", required=True); s.set_defaults(fn=cmd_comment)
    s = sub.add_parser("split", help="one report → several independent issues (1-n); each --part is 'title | module | kind | severity | description'")
    s.add_argument("key"); s.add_argument("--part", action="append", required=True); s.add_argument("--note"); s.set_defaults(fn=cmd_split)
    s = sub.add_parser("unsplit", help="fold a split back into its parent; the parts become duplicates of it"); s.add_argument("key"); s.add_argument("--note"); s.set_defaults(fn=cmd_unsplit)
    s = sub.add_parser("intake", help="customer reports not on an issue yet, or flagged (answered / reopened)"); s.set_defaults(fn=cmd_intake)
    s = sub.add_parser("attach", help="link a report (board/KEY) to an existing issue; again to the same issue clears its flag")
    s.add_argument("ref"); s.add_argument("--to", required=True); s.add_argument("--note"); s.set_defaults(fn=cmd_attach)
    s = sub.add_parser("promote", help="a new defect: the report becomes a new issue, linked to it"); s.add_argument("ref"); s.add_argument("--note"); s.set_defaults(fn=cmd_promote)
    s = sub.add_parser("ask", help="more_info to that one report's board"); s.add_argument("ref"); s.add_argument("question"); s.set_defaults(fn=cmd_ask)
    s = sub.add_parser("detach", help="unlink a report; it goes back to intake"); s.add_argument("ref"); s.add_argument("--note"); s.set_defaults(fn=cmd_detach)
    s = sub.add_parser("sync", help="sync every customer board now (it also runs on its own every 30 s)"); s.set_defaults(fn=cmd_sync)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
