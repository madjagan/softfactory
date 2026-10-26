#!/usr/bin/env python3
"""The Ideas Agent's side of the ideas portal (ideas/app.py): gather, link, draft, ledger sync.

  python3 tools/ideas_cli.py intake                                   # unlinked submissions
  python3 tools/ideas_cli.py list [--status new,under_review] [--sort orgs]
  python3 tools/ideas_cli.py show IDR-12 | IDEA-3
  python3 tools/ideas_cli.py shots IDR-12 [--out DIR]
  python3 tools/ideas_cli.py tracker                                  # tracker issues not yet submitted (ISSUES_URL)
  python3 tools/ideas_cli.py add --source tracker|support --ref IS-612 --requester "…" --text "…" [--org acme]
  python3 tools/ideas_cli.py attach IDR-12 IDEA-3 [--note "…"]
  python3 tools/ideas_cli.py promote IDR-12 --title "…" --problem "…"
  python3 tools/ideas_cli.py edit IDEA-3 [--title …] [--problem …] [--public-title …] [--public-description …] [--feature AREA-NN]
  python3 tools/ideas_cli.py review IDEA-3                            # new → under_review (problem + public draft written)
  python3 tools/ideas_cli.py recommend IDEA-3 --kind already_built --feature AREA-07 | --kind merge --into IDEA-1 | --kind decline|accept|publish
  python3 tools/ideas_cli.py ledger [--apply]                         # accepted → in_development → shipped, with citations
  python3 tools/ideas_cli.py draft IDEA-3 --to IDR-12|SUP-1042 --text "…"
  python3 tools/ideas_cli.py report                                   # what waits for product
  python3 tools/ideas_cli.py accept IDEA-3 --prd 3.14 [--feature AREA-NN]   # product role: the owner's call, run by the session

Env: IDEAS_URL (default http://127.0.0.1:3004), IDEAS_TOKEN (the team token, if set);
ISSUES_URL / ISSUES_TOKEN for `tracker`. Ledger paths come from factory.yaml (docs.plan, docs.feature_list, docs.release_log).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

PARSED = urllib.parse.urlsplit(os.environ.get("IDEAS_URL", "http://127.0.0.1:3004").rstrip("/"))
URL = urllib.parse.urlunsplit((PARSED.scheme, PARSED.hostname + (f":{PARSED.port}" if PARSED.port else ""), PARSED.path, "", ""))
TOKEN = os.environ.get("IDEAS_TOKEN", "")


def http(base: urllib.parse.SplitResult, token_header: str, token: str, method: str, path: str, body: dict | None, role: str, actor: str, raw: bool):
    url = urllib.parse.urlunsplit((base.scheme, base.hostname + (f":{base.port}" if base.port else ""), base.path, "", ""))
    req = urllib.request.Request(f"{url}/{path.lstrip('/')}", method=method)
    req.add_header("X-Role", role)
    req.add_header("X-Actor", actor)
    if token:
        req.add_header(token_header, token)
    if base.username:  # user:pass@host → the proxy's basic auth
        cred = base64.b64encode(f"{base.username}:{base.password or ''}".encode()).decode()
        req.add_header("Authorization", f"Basic {cred}")
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, data, timeout=30) as r:
            return r.read() if raw else json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {path}: {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"Cannot reach {url}: {e.reason}")


def call(method: str, path: str, body: dict | None = None, raw: bool = False, role: str = "agent"):
    return http(PARSED, "X-Ideas-Token", TOKEN, method, path, body, role, "Ideas Agent" if role == "agent" else "Product", raw)


def tracker_call(path: str):
    base = urllib.parse.urlsplit(os.environ.get("ISSUES_URL", "http://127.0.0.1:3002").rstrip("/"))
    return http(base, "X-Issues-Token", os.environ.get("ISSUES_TOKEN", ""), "GET", path, None, "agent", "Ideas Agent", False)


# ---------------- the ledger, read the way the agent reads it ----------------
def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def plan_row(plan: str, prd: str) -> list[str] | None:
    for line in plan.splitlines():
        if line.lstrip().startswith("|") and cells(line)[0].lstrip("§").strip() == prd:
            return cells(line)
    return None


def feature_row(features: str, fid: str) -> list[str] | None:
    for line in features.splitlines():
        if line.lstrip().startswith("|") and cells(line)[0].strip("*").strip() == fid:
            return cells(line)
    return None


def release_entry(log: str, prd: str, fid: str) -> str | None:
    """The heading of the newest release entry that names the PRD § or the feature id."""
    heading = None
    pat = re.compile(rf"(§\s?{re.escape(prd)}(?![\d.])|\b{re.escape(fid)}\b)" if fid else rf"§\s?{re.escape(prd)}(?![\d.])")
    for line in log.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
        elif heading and pat.search(line):
            return heading
    return None


def ledger_move(idea: dict, plan: str, features: str, log: str) -> tuple[str, str] | None:
    """The next ledger-derived status for an accepted idea, with its citation; None when the ledger says nothing new."""
    prd, fid = idea.get("prdRef") or "", idea.get("featureId") or ""
    if idea["status"] == "accepted":
        row = plan_row(plan, prd)
        if row and re.search(r"in progress|complete|✅", row[-1], re.I):
            return "in_development", f"IMPLEMENTATION_PLAN.md §{prd} row: {row[-1]}"
    if idea["status"] == "in_development" and fid:
        row = feature_row(features, fid)
        entry = release_entry(log, prd, fid)
        if row and "●" in row and entry:
            return "shipped", f"FEATURE_LIST.md {fid} ●; RELEASE_LOG.md {entry}"
    return None


def doc_text(key: str) -> str:
    from factory import doc_path
    p = doc_path(key)
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ---------------- commands ----------------
def cmd_intake(a):
    rows = call("GET", "api/submissions?intake=true")
    for r in rows:
        print(f"{r['key']:9} {r['source']:8} {r['sourceRef'] or '':14} {r['org'] or '':10} {r['requester']:16} {r['text'][:70]}")
    print(f"{len(rows)} submission(s) in intake")


def cmd_list(a):
    rows = call("GET", f"api/ideas?sort={a.sort}" + (f"&status={a.status}" if a.status else ""))
    for r in rows:
        d = r["demand"]
        print(f"{r['key']:9} {r['status']:14} orgs {d['orgs']:<3} people {d['people']:<3} votes {d['votes']:<3} tickets {d['tickets']:<3} issues {d['issues']:<3} "
              f"{'[public] ' if r.get('public') else ''}{r['title']}")
    print(f"{len(rows)} idea(s)")


def cmd_show(a):
    kind = "ideas" if a.key.upper().startswith(call("GET", "api/meta")["prefix"] + "-") else "submissions"
    print(json.dumps(call("GET", f"api/{kind}/{a.key}"), indent=2, ensure_ascii=False))


def cmd_shots(a):
    doc = call("GET", f"api/submissions/{a.key}")
    out = Path(a.out or f"/tmp/ideas-{a.key}")
    out.mkdir(parents=True, exist_ok=True)
    for i in doc.get("screenshots") or []:
        (out / i).write_bytes(call("GET", f"uploads/{i}", raw=True))
        print(out / i)
    if not doc.get("screenshots"):
        print("no screenshots")


def cmd_tracker(a):
    """Feature / enhancement issues, and as_speced verdicts, that are not yet a submission. You judge the as_speced ones."""
    have = {s["sourceRef"] for s in call("GET", "api/submissions?source=tracker")}
    seen = set()
    for q in ("kind=feature", "kind=enhancement", "status=as_speced"):
        for r in tracker_call(f"api/issues?{q}"):
            if r["key"] in have or r["key"] in seen:
                continue
            seen.add(r["key"])
            print(f"{r['key']:10} {r['status']:10} {r['kind'] or '':12} {r['reporter'] or '':16} {r['title']}")
    print(f"{len(seen)} tracker issue(s) not yet submitted")


def cmd_add(a):
    doc = call("POST", "api/submissions", {"source": a.source, "sourceRef": a.ref, "org": a.org or "", "requester": a.requester, "text": a.text})
    print(f"{doc['key']} ← {a.source} {a.ref} (intake)")


def cmd_attach(a):
    out = call("POST", f"api/submissions/{a.key}/attach", {"idea": a.idea, "note": a.note or ""})
    print(f"{a.key} → {out['idea']['key']} ({len(out['idea']['submissions'])} submission(s))")


def cmd_promote(a):
    doc = call("POST", f"api/submissions/{a.key}/promote", {"title": a.title, "problem": a.problem or ""})
    print(f"{a.key} → {doc['key']} new: {doc['title']}")


def cmd_edit(a):
    body = {k: v for k, v in {"title": a.title, "problem": a.problem, "publicTitle": a.public_title,
                              "publicDescription": a.public_description, "featureId": a.feature}.items() if v is not None}
    doc = call("POST", f"api/ideas/{a.key}/edit", body)
    print(f"{doc['key']}: edited {', '.join(body)}")


def cmd_review(a):
    doc = call("POST", f"api/ideas/{a.key}/transition", {"to": "under_review", "note": a.note or ""})
    print(f"{doc['key']} → {doc['status']}")


def cmd_recommend(a):
    if a.kind == "already_built":
        row = feature_row(doc_text("feature_list"), a.feature or "")
        if not row or "●" not in row:
            sys.exit(f"{a.feature} is not ● in the feature list; recommend already_built only for a live feature")
    doc = call("POST", f"api/ideas/{a.key}/recommend", {"kind": a.kind, "note": a.note or "", "featureId": a.feature or "", "mergedInto": a.into or ""})
    print(f"{doc['key']}: recommends {a.kind}")


def cmd_ledger(a):
    plan, features, log = doc_text("plan"), doc_text("feature_list"), doc_text("release_log")
    moves = 0
    for idea in call("GET", "api/ideas?status=accepted,in_development"):
        while (m := ledger_move(idea, plan, features, log)):
            to, cite = m
            moves += 1
            if not a.apply:
                print(f"{idea['key']} {idea['status']} → {to}  [{cite}]  (dry run)")
                break
            idea = call("POST", f"api/ideas/{idea['key']}/transition", {"to": to, "citation": cite})
            print(f"{idea['key']} → {to}  [{cite}]")
    print(f"{moves} ledger move(s)" + ("" if a.apply else "; --apply to write them"))


def cmd_draft(a):
    doc = call("POST", f"api/ideas/{a.key}/drafts", {"to": a.to, "text": a.text})
    print(f"{doc['key']}: draft {len(doc['drafts']) - 1} to {a.to} (waits for product to send)")


def cmd_report(a):
    for i in call("GET", "api/ideas"):
        if i["status"] in ("new", "under_review"):
            for r in i.get("recommendations") or []:
                print(f"{i['key']:9} recommends {r['kind']}{' ' + r.get('featureId', '') if r.get('featureId') else ''}{' → ' + r['mergedInto'] if r.get('mergedInto') else ''}: {r['note']}")
            if i.get("publicDraft") and not i.get("public"):
                print(f"{i['key']:9} public text drafted, not published")
        for n, d in enumerate(i.get("drafts") or []):
            if not d["sentAt"]:
                print(f"{i['key']:9} draft {n} to {d['to']} waits to be sent")


def cmd_accept(a):
    doc = call("POST", f"api/ideas/{a.key}/transition", {"to": "accepted", "prdRef": a.prd, "featureId": a.feature or "", "note": a.note or ""}, role="product")
    print(f"{doc['key']} → accepted (PRD §{doc['prdRef']})")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("intake"); s.set_defaults(fn=cmd_intake)
    s = sub.add_parser("list"); s.add_argument("--status"); s.add_argument("--sort", default="orgs"); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("show"); s.add_argument("key"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("shots"); s.add_argument("key"); s.add_argument("--out"); s.set_defaults(fn=cmd_shots)
    s = sub.add_parser("tracker"); s.set_defaults(fn=cmd_tracker)
    s = sub.add_parser("add"); s.add_argument("--source", required=True, choices=["tracker", "support"]); s.add_argument("--ref", required=True)
    s.add_argument("--requester", required=True); s.add_argument("--text", required=True); s.add_argument("--org"); s.set_defaults(fn=cmd_add)
    s = sub.add_parser("attach"); s.add_argument("key"); s.add_argument("idea"); s.add_argument("--note"); s.set_defaults(fn=cmd_attach)
    s = sub.add_parser("promote"); s.add_argument("key"); s.add_argument("--title", required=True); s.add_argument("--problem"); s.set_defaults(fn=cmd_promote)
    s = sub.add_parser("edit"); s.add_argument("key")
    for opt in ("--title", "--problem", "--public-title", "--public-description", "--feature"):
        s.add_argument(opt)
    s.set_defaults(fn=cmd_edit)
    s = sub.add_parser("review"); s.add_argument("key"); s.add_argument("--note"); s.set_defaults(fn=cmd_review)
    s = sub.add_parser("recommend"); s.add_argument("key"); s.add_argument("--kind", required=True, choices=["accept", "decline", "already_built", "merge", "publish"])
    s.add_argument("--feature"); s.add_argument("--into"); s.add_argument("--note"); s.set_defaults(fn=cmd_recommend)
    s = sub.add_parser("ledger"); s.add_argument("--apply", action="store_true"); s.set_defaults(fn=cmd_ledger)
    s = sub.add_parser("draft"); s.add_argument("key"); s.add_argument("--to", required=True); s.add_argument("--text", required=True); s.set_defaults(fn=cmd_draft)
    s = sub.add_parser("report"); s.set_defaults(fn=cmd_report)
    s = sub.add_parser("accept", help="product role: record the PRD § /create-feature produced")
    s.add_argument("key"); s.add_argument("--prd", required=True); s.add_argument("--feature"); s.add_argument("--note"); s.set_defaults(fn=cmd_accept)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
