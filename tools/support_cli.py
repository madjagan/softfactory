#!/usr/bin/env python3
"""The Support Agent's side of the support desk (support/app.py): queue, show, draft, note, category.

  python3 tools/support_cli.py list [--all] [--status new,open] [--org acme]   # default: the drafting queue
  python3 tools/support_cli.py show SUP-1042
  python3 tools/support_cli.py shots SUP-1042 [--out DIR]                      # download screenshots to view
  python3 tools/support_cli.py draft SUP-1042 --text "…"                       # a reply support checks and sends
  python3 tools/support_cli.py note SUP-1042 --text "…"                        # internal, never shown to the customer
  python3 tools/support_cli.py recommend-escalate SUP-1042 --text "…" [--issue-ref IS-512]
  python3 tools/support_cli.py category SUP-1042 --set defect

The server refuses anything else from this role: it never sends, never changes status.
Env: SUPPORT_URL (default http://127.0.0.1:3003), SUPPORT_TOKEN (if the server requires one).
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

PARSED = urllib.parse.urlsplit(os.environ.get("SUPPORT_URL", "http://127.0.0.1:3003").rstrip("/"))
URL = urllib.parse.urlunsplit((PARSED.scheme, PARSED.hostname + (f":{PARSED.port}" if PARSED.port else ""), PARSED.path, "", ""))
TOKEN = os.environ.get("SUPPORT_TOKEN", "")


def call(method: str, path: str, body: dict | None = None, raw: bool = False):
    req = urllib.request.Request(f"{URL}/{path.lstrip('/')}", method=method)
    req.add_header("X-Role", "agent")
    req.add_header("X-Actor", "Support Agent")
    if TOKEN:
        req.add_header("X-Support-Token", TOKEN)
    if PARSED.username:  # user:pass@host in SUPPORT_URL → the proxy's basic auth
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
        sys.exit(f"Cannot reach {URL}: {e.reason}. Start it with: uvicorn support.app:app --port 3003")


def cmd_list(a):
    q = f"api/tickets?status={a.status}" + ("" if a.all else "&needsDraft=true") + (f"&org={a.org}" if a.org else "")
    rows = call("GET", q)
    for r in rows:
        flags = ("draft " if r["draftPending"] else "") + (f"→{r['issueRef']} " if r["issueRef"] else "")
        print(f"{r['key']:9} {r['status']:20} {r['org']:10} {r['category'] or '-':9} {flags:12} {r['title']}")
    print(f"{len(rows)} ticket(s)" + ("" if a.all else " waiting for a draft"))


def cmd_show(a):
    print(json.dumps(call("GET", f"api/tickets/{a.key}"), indent=2, ensure_ascii=False))


def cmd_shots(a):
    doc = call("GET", f"api/tickets/{a.key}")
    ids = list(doc.get("screenshots") or [])
    for m in doc.get("messages") or []:
        ids += m.get("screenshots") or []
    out = Path(a.out or f"/tmp/support-{a.key}")
    out.mkdir(parents=True, exist_ok=True)
    for i in ids:
        (out / i).write_bytes(call("GET", f"uploads/{i}", raw=True))
        print(out / i)
    if not ids:
        print("no screenshots")


def cmd_draft(a):
    doc = call("POST", f"api/tickets/{a.key}/messages", {"text": a.text, "visibility": "draft"})
    print(f"{doc['key']}: draft written; support sends it")


def cmd_note(a):
    doc = call("POST", f"api/tickets/{a.key}/messages", {"text": a.text, "visibility": "internal"})
    print(f"{doc['key']}: internal note added")


def cmd_recommend(a):
    text = "**Escalation recommended**" + (f" onto {a.issue_ref}" if a.issue_ref else " as a new defect") + "\n\n" + a.text
    doc = call("POST", f"api/tickets/{a.key}/messages", {"text": text, "visibility": "internal", "tag": "recommend_escalation"})
    print(f"{doc['key']}: escalation recommended; a person escalates")


def cmd_category(a):
    doc = call("POST", f"api/tickets/{a.key}/fields", {"category": a.set})
    print(f"{doc['key']}: category {doc['category']}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list"); s.add_argument("--status", default="new,open"); s.add_argument("--org")
    s.add_argument("--all", action="store_true", help="every ticket in --status, not only those waiting for a draft"); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("show"); s.add_argument("key"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("shots"); s.add_argument("key"); s.add_argument("--out"); s.set_defaults(fn=cmd_shots)
    s = sub.add_parser("draft"); s.add_argument("key"); s.add_argument("--text", required=True); s.set_defaults(fn=cmd_draft)
    s = sub.add_parser("note"); s.add_argument("key"); s.add_argument("--text", required=True); s.set_defaults(fn=cmd_note)
    s = sub.add_parser("recommend-escalate"); s.add_argument("key"); s.add_argument("--text", required=True)
    s.add_argument("--issue-ref", help="the existing internal issue it belongs to, when known"); s.set_defaults(fn=cmd_recommend)
    s = sub.add_parser("category"); s.add_argument("key"); s.add_argument("--set", required=True); s.set_defaults(fn=cmd_category)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
