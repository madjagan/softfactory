"""Software-factory issue tracker — a standalone FastAPI app over SQLite.

Testers file issues (with screenshots) from the static page; the Issue Agent works them through
tools/issues_cli.py and writes verdicts back. One process, one file database, disk uploads.
Serve at any path prefix: the page uses relative URLs only.
"""
from __future__ import annotations

import json
import mimetypes
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("ISSUES_DATA", HERE / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "issues.sqlite3"
TOKEN = os.environ.get("ISSUES_TOKEN", "")  # empty = open (local dev)
FIRST_NEW_NUM = int(os.environ.get("ISSUES_FIRST_NUM", "501"))  # room below for an issues-log import
# A second board (the customer-facing /feedback/) runs this same app with its own database, its own
# brand line and its own key prefix, so FB-501 on that board can never be confused with TP-501 here.
BRAND = os.environ.get("ISSUES_BRAND", "Issue tracker")
PREFIX = os.environ.get("ISSUES_PREFIX", "IS")
# The roles a board ACCEPTS. The customer board sets ISSUES_ROLES=tester,agent so nobody there can
# act as admin (set any status), whatever header a request carries; the page offers only what is
# listed here, minus agent, which is the CLI's role.
ALLOWED_ROLES = {r.strip() for r in os.environ.get("ISSUES_ROLES", "tester,agent,admin").split(",") if r.strip()}
# A CUSTOMER board shows status only: the analysis never leaves the server, however it got there.
CUSTOMER = os.environ.get("ISSUES_CUSTOMER", "") == "1"
# The internal board triages ONE BOARD PER CUSTOMER: FEEDBACK_BOARDS="acme=http://acme-feedback:3002,…",
# each board's token in FEEDBACK_TOKEN_<NAME>. Every customer report lands here in an intake queue
# (table `reports`); the Issue Agent attaches it to an internal issue or promotes it to a new one,
# and only the resulting STATUS travels back to that customer's own board.
FEEDBACK_BOARDS = {n.strip(): u.strip().rstrip("/") for n, _, u in (p.partition("=") for p in os.environ.get("FEEDBACK_BOARDS", "").split(","))
                   if n.strip() and u.strip()}
FEEDBACK_SYNC_INTERVAL = int(os.environ.get("FEEDBACK_SYNC_INTERVAL", "30"))
PUSH_ACTOR = os.environ.get("ISSUES_PUSH_ACTOR", "Product team")   # how a status pushed to the customer board signs itself

STATUSES = ["new", "more_info", "open", "fixed", "duplicate", "as_speced", "verified", "closed"]
KINDS = ["bug", "enhancement", "decision", "feature", "question", "diagnostic", "other"]
SEVERITIES = ["low", "medium", "high", "critical"]
# The product's module list comes from the project manifest (factory.yaml → issues.modules), passed
# in as ISSUES_MODULES; "other" is always present so a tester can file without choosing.
MODULES = [m.strip() for m in os.environ.get("ISSUES_MODULES", "core,ui,api,data,auth,admin,docs,infra").split(",") if m.strip()]
if "other" not in MODULES:
    MODULES.append("other")
AGENT_FIELDS = ["rootCause", "fixProposed", "fix", "files", "tests", "humanTests", "duplicateOf", "specRef", "infoNeeded"]
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}

# Who may move an issue where. Testers verify and reopen; the Issue Agent gives verdicts; admin does anything.
TESTER_MOVES = {"more_info": {"open"}, "fixed": {"verified", "open"}, "duplicate": {"verified", "open"},
                "as_speced": {"verified", "open"}, "verified": {"closed", "open"}, "closed": {"open"}}
AGENT_VERDICTS = {"fixed", "duplicate", "as_speced", "more_info"}
AGENT_MOVES = {"new": set(AGENT_VERDICTS), "open": set(AGENT_VERDICTS)}
NOTE_REQUIRED = {("more_info", "open"), ("fixed", "open"), ("duplicate", "open"), ("as_speced", "open"), ("verified", "open"), ("closed", "open")}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ---------------- storage ----------------
def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db() -> None:
    with tx() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS issues (
            key TEXT PRIMARY KEY, num INTEGER UNIQUE NOT NULL, status TEXT NOT NULL, module TEXT, source TEXT,
            kind TEXT, severity TEXT, updated_at TEXT NOT NULL, doc TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS issues_status ON issues(status);
        CREATE TABLE IF NOT EXISTS uploads (
            id TEXT PRIMARY KEY, filename TEXT, content_type TEXT, size INTEGER, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reports (
            board TEXT NOT NULL, key TEXT NOT NULL, issue TEXT, flag TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
            doc TEXT NOT NULL, PRIMARY KEY (board, key));
        """)
        # A single customer board used to be MIRRORED (one issue per customer issue, source "customer",
        # sourceRef = its key). Each mirror becomes an issue with one attached report, on the board listed first.
        board = next(iter(FEEDBACK_BOARDS), "customer")
        for row in con.execute("SELECT doc FROM issues WHERE source='customer'").fetchall():
            doc = json.loads(row["doc"])
            if doc.get("reports") or not doc.get("sourceRef"):
                continue
            put_report(con, {"board": board, "key": doc["sourceRef"], **{k: doc.get(k, "") for k in REPORT_FIELDS},
                             "screenshots": list(doc.get("screenshots") or []), "comments": [], "customerStatus": "",
                             "issue": doc["key"], "flag": "", "sync": doc.get("sync") or {"commentsSeen": 0, "historySeen": 0, "pushedAt": ""}})
            doc["reports"] = [f"{board}/{doc['sourceRef']}"]
            put_issue(con, doc)
        # The verdict-giving role was called "claude" before it became the Issue Agent: carry old boards over.
        for row in con.execute("""SELECT doc FROM issues WHERE doc LIKE '%"claude"%'""").fetchall():
            doc = json.loads(row["doc"])
            if "claude" in doc:
                doc["agent"] = {**doc.pop("claude"), **(doc.get("agent") or {})}
            for entry in doc.get("history", []) + doc.get("comments", []):
                if entry.get("by") == "claude":
                    entry["by"] = "agent"
            put_issue(con, doc)


@contextmanager
def tx():
    con = connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def put_issue(con: sqlite3.Connection, doc: dict) -> None:
    con.execute(
        "INSERT OR REPLACE INTO issues(key,num,status,module,source,kind,severity,updated_at,doc) VALUES (?,?,?,?,?,?,?,?,?)",
        (doc["key"], doc["num"], doc["status"], doc.get("module"), doc.get("source"), doc.get("kind"),
         doc.get("severity"), doc["updatedAt"], json.dumps(doc, ensure_ascii=False)))


def get_issue(con: sqlite3.Connection, key: str) -> dict:
    row = con.execute("SELECT doc FROM issues WHERE key=?", (key,)).fetchone()
    if not row:
        raise HTTPException(404, f"{key} not found")
    return json.loads(row["doc"])


REPORT_FIELDS = ["title", "description", "module", "kind", "severity", "persona", "reporter", "build", "createdAt"]


def ref(r: dict) -> str:
    return f"{r['board']}/{r['key']}"


def put_report(con: sqlite3.Connection, r: dict) -> None:
    con.execute("INSERT OR REPLACE INTO reports(board,key,issue,flag,updated_at,doc) VALUES (?,?,?,?,?,?)",
                (r["board"], r["key"], r.get("issue"), r.get("flag") or "", now_iso(), json.dumps(r, ensure_ascii=False)))


def find_report(con: sqlite3.Connection, board: str, key: str) -> Optional[dict]:
    row = con.execute("SELECT doc FROM reports WHERE board=? AND key=?", (board, key)).fetchone()
    return json.loads(row["doc"]) if row else None


def get_report(con: sqlite3.Connection, board: str, key: str) -> dict:
    r = find_report(con, board, key)
    if not r:
        raise HTTPException(404, f"{board}/{key} not found")
    return r


def next_num(con: sqlite3.Connection) -> int:
    row = con.execute("SELECT MAX(num) AS m FROM issues WHERE num >= ?", (FIRST_NEW_NUM,)).fetchone()
    return (row["m"] or FIRST_NEW_NUM - 1) + 1


def register_upload(con: sqlite3.Connection, uid: str, filename: str, content_type: str, size: int) -> None:
    con.execute("INSERT OR REPLACE INTO uploads(id,filename,content_type,size,created_at) VALUES (?,?,?,?,?)",
                (uid, filename, content_type, size, now_iso()))


# ---------------- auth / actor ----------------
class Actor(BaseModel):
    name: str
    role: str  # tester | agent | admin


def actor(request: Request) -> Actor:
    if TOKEN:  # X-Issues-Token, so a reverse proxy's basic auth can keep the Authorization header
        given = request.headers.get("x-issues-token") or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if given != TOKEN:
            raise HTTPException(401, "Missing or wrong token")
    role = request.headers.get("x-role", "tester").lower()
    if role not in {"tester", "agent", "admin"}:
        raise HTTPException(400, "X-Role must be tester, agent or admin")
    if role not in ALLOWED_ROLES:
        raise HTTPException(403, f"This board does not offer the {role} role")
    name = request.headers.get("x-actor", "").strip()[:80] or ("agent" if role == "agent" else "")
    return Actor(name=name, role=role)


# ---------------- API ----------------
app = FastAPI(title=f"{BRAND} — issues", docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.on_event("startup")
def _startup() -> None:
    init_db()


class NewIssue(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    module: str = "other"
    kind: str = "bug"
    severity: str = "medium"
    persona: str = ""
    build: str = ""
    screenshots: list[str] = []


class Comment(BaseModel):
    text: str = ""
    screenshots: list[str] = []


class SplitPart(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    module: str = "other"
    kind: str = "bug"
    severity: str = "medium"


class Split(BaseModel):
    parts: list[SplitPart] = Field(min_length=1, max_length=20)
    note: str = ""


class Transition(BaseModel):
    to: str
    note: str = ""
    screenshots: list[str] = []
    agent: Optional[dict[str, Any]] = None


def public(doc: dict) -> dict:
    """What a caller may see. On a customer board the analysis block is withheld entirely."""
    if CUSTOMER:
        doc = {**doc, "agent": {}}
    return doc


def summary(doc: dict) -> dict:
    keep = ["key", "num", "title", "status", "module", "kind", "severity", "source", "sourceRef", "reporter",
            "createdAt", "updatedAt", "build", "persona", "splitInto", "reports"]
    s = {k: doc.get(k) for k in keep}
    s["screenshotCount"] = len(doc.get("screenshots") or [])
    s["processed"] = bool((doc.get("agent") or {}).get("processedAt")) and not CUSTOMER
    return s


@app.get("/api/meta")
def meta(a: Actor = Depends(actor)):
    return {"statuses": STATUSES, "kinds": KINDS, "severities": SEVERITIES, "modules": MODULES, "actor": a.model_dump(),
            "tokenRequired": bool(TOKEN), "brand": BRAND, "prefix": PREFIX, "customer": CUSTOMER, "pushActor": PUSH_ACTOR,
            "mirrors": bool(FEEDBACK_BOARDS), "boards": list(FEEDBACK_BOARDS),
            "roles": [r for r in ("tester", "admin") if r in ALLOWED_ROLES]}


@app.get("/api/stats")
def stats(a: Actor = Depends(actor)):
    con = connect()
    try:
        rows = con.execute("SELECT status, COUNT(*) AS n FROM issues GROUP BY status").fetchall()
        out = {"byStatus": {r["status"]: r["n"] for r in rows}, "total": sum(r["n"] for r in rows)}
        if not CUSTOMER:
            out["intake"] = con.execute("SELECT COUNT(*) FROM reports WHERE issue IS NULL").fetchone()[0]
            out["flagged"] = con.execute("SELECT COUNT(*) FROM reports WHERE issue IS NOT NULL AND flag != ''").fetchone()[0]
        return out
    finally:
        con.close()


@app.get("/api/issues")
def list_issues(status: Optional[str] = None, module: Optional[str] = None, source: Optional[str] = None,
                kind: Optional[str] = None, q: Optional[str] = None, reporter: Optional[str] = None,
                full: bool = False, limit: int = Query(2000, le=5000), a: Actor = Depends(actor)):
    where, args = [], []
    if status:
        vals = status.split(",")
        where.append(f"status IN ({','.join('?' * len(vals))})"); args += vals
    for col, val in (("module", module), ("source", source), ("kind", kind)):
        if val:
            where.append(f"{col}=?"); args.append(val)
    sql = "SELECT doc FROM issues" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY num DESC LIMIT ?"
    con = connect()
    try:
        docs = [json.loads(r["doc"]) for r in con.execute(sql, args + [limit])]
    finally:
        con.close()
    if q:
        ql = q.lower()
        docs = [d for d in docs if ql in " ".join(str(d.get(k, "")) for k in ("key", "title", "description", "sourceRef", "reports")).lower()]
    if reporter:
        docs = [d for d in docs if (d.get("reporter") or "").lower() == reporter.lower()]
    return [public(d) for d in docs] if full else [summary(d) for d in docs]


@app.get("/api/issues/{key}")
def read_issue(key: str, a: Actor = Depends(actor)):
    con = connect()
    try:
        return with_reports(con, get_issue(con, key))
    finally:
        con.close()


def with_reports(con: sqlite3.Connection, doc: dict) -> dict:
    """The issue as a caller sees it, with every linked customer report in full."""
    out = public(doc)
    if doc.get("reports"):
        out = {**out, "customerReports": [r for r in (find_report(con, *x.split("/", 1)) for x in doc["reports"]) if r]}
    return out


@app.post("/api/issues", status_code=201)
def create_issue(body: NewIssue, a: Actor = Depends(actor)):
    if not a.name:
        raise HTTPException(400, "Say who you are (X-Actor header)")
    for val, allowed, what in ((body.kind, KINDS, "kind"), (body.severity, SEVERITIES, "severity"), (body.module, MODULES, "module")):
        if val not in allowed:
            raise HTTPException(400, f"Unknown {what}: {val}")
    at = now_iso()
    with tx() as con:
        num = next_num(con)
        doc = {"key": f"{PREFIX}-{num}", "num": num, "title": body.title.strip(), "description": body.description.strip(),
               "module": body.module, "kind": body.kind, "severity": body.severity, "persona": body.persona.strip(),
               "build": body.build.strip(), "status": "new", "source": "tester", "sourceRef": "", "reporter": a.name,
               "createdAt": at, "updatedAt": at, "screenshots": _known_uploads(con, body.screenshots), "agent": {},
               "comments": [], "history": [{"at": at, "by": a.name, "from": "", "to": "new", "note": ""}]}
        put_issue(con, doc)
    return doc


@app.post("/api/issues/{key}/split", status_code=201)
def split_issue(key: str, body: Split, a: Actor = Depends(actor)):
    """One report, several independent defects or requirements: the agent SPLITS it (1-n). Each
    part becomes an issue of its own (source `split`, sourceRef = the parent), inheriting the
    reporter, build, persona and screenshots, worked and closed on its own. The parent stays
    the report — and, for a customer issue, the one link the customer sees. Never on a customer
    board: the customer files reports; the split is the team's reading of them."""
    if CUSTOMER:
        raise HTTPException(404, "Not on a customer board")
    if a.role not in ("agent", "admin"):
        raise HTTPException(403, "Only the Issue Agent or an admin splits an issue")
    for n, part in enumerate(body.parts, 1):
        for val, allowed, what in ((part.kind, KINDS, "kind"), (part.severity, SEVERITIES, "severity"), (part.module, MODULES, "module")):
            if val not in allowed:
                raise HTTPException(400, f"Part {n}: unknown {what}: {val}")
    at = now_iso()
    who = a.name or a.role
    with tx() as con:
        parent = get_issue(con, key)
        if parent.get("source") == "split":
            raise HTTPException(409, f"{key} is itself a part of {parent.get('sourceRef')}; split the parent instead")
        children = []
        for part in body.parts:
            num = next_num(con)
            child = {"key": f"{PREFIX}-{num}", "num": num, "title": part.title.strip(), "description": part.description.strip(),
                     "module": part.module, "kind": part.kind, "severity": part.severity, "persona": parent.get("persona", ""),
                     "build": parent.get("build", ""), "status": "new", "source": "split", "sourceRef": key,
                     "reporter": parent.get("reporter", ""), "createdAt": at, "updatedAt": at,
                     "screenshots": list(parent.get("screenshots") or []), "agent": {}, "comments": [],
                     "history": [{"at": at, "by": who, "from": "", "to": "new", "note": f"Split from {key} ({parent.get('title', '')})."}]}
            put_issue(con, child)
            children.append(child)
        keys = [c["key"] for c in children]
        parent["splitInto"] = [*(parent.get("splitInto") or []), *keys]
        parent["updatedAt"] = at
        text = (body.note.strip() + "\n\n" if body.note.strip() else "") + "Split into " + ", ".join(f"{c['key']} — {c['title']}" for c in children) + "."
        parent.setdefault("comments", []).append({"at": at, "by": who, "text": text, "screenshots": []})
        parent.setdefault("history", []).append({"at": at, "by": who, "from": parent["status"], "to": parent["status"], "note": "Split into " + ", ".join(keys)})
        put_issue(con, parent)
    return {"parent": public(parent), "children": [public(c) for c in children]}


@app.post("/api/issues/{key}/unsplit")
def unsplit_issue(key: str, body: Comment, a: Actor = Depends(actor)):
    """Fold a split back into its parent. Parts are never deleted: each becomes a duplicate of
    the parent (its analysis stays readable), and the parent forgets the split."""
    if CUSTOMER:
        raise HTTPException(404, "Not on a customer board")
    if a.role not in ("agent", "admin"):
        raise HTTPException(403, "Only the Issue Agent or an admin folds a split")
    at = now_iso()
    who = a.name or a.role
    with tx() as con:
        parent = get_issue(con, key)
        parts = list(parent.get("splitInto") or [])
        if not parts:
            raise HTTPException(409, f"{key} is not split")
        for k in parts:
            child = get_issue(con, k)
            if child.get("status") not in ("verified", "closed"):
                frm = child["status"]
                child["status"] = "duplicate"
                child.setdefault("agent", {})["duplicateOf"] = key
                child["agent"]["processedAt"] = at
                child["history"].append({"at": at, "by": who, "from": frm, "to": "duplicate", "note": f"Folded back into {key}."})
                child.setdefault("comments", []).append({"at": at, "by": who, "text": f"Folded back into {key}: the report is worked as one issue.", "screenshots": []})
                child["updatedAt"] = at
                put_issue(con, child)
        parent.pop("splitInto", None)
        parent["updatedAt"] = at
        text = (body.text.strip() + "\n\n" if body.text.strip() else "") + "Folded back: " + ", ".join(parts) + " are duplicates of this issue; it is worked as one."
        parent.setdefault("comments", []).append({"at": at, "by": who, "text": text, "screenshots": []})
        parent.setdefault("history", []).append({"at": at, "by": who, "from": parent["status"], "to": parent["status"], "note": "Split folded back: " + ", ".join(parts)})
        put_issue(con, parent)
    return public(parent)


@app.post("/api/issues/{key}/comments")
def add_comment(key: str, body: Comment, a: Actor = Depends(actor)):
    if not body.text.strip() and not body.screenshots:
        raise HTTPException(400, "Write a note or attach a screenshot")
    with tx() as con:
        doc = get_issue(con, key)
        doc.setdefault("comments", []).append({"at": now_iso(), "by": a.name or a.role, "text": body.text.strip(),
                                               "screenshots": _known_uploads(con, body.screenshots)})
        doc["updatedAt"] = now_iso()
        put_issue(con, doc)
    return public(doc)


@app.post("/api/issues/{key}/transition")
def transition(key: str, body: Transition, a: Actor = Depends(actor)):
    if body.to not in STATUSES:
        raise HTTPException(400, f"Unknown status: {body.to}")
    with tx() as con:
        doc = get_issue(con, key)
        frm = doc["status"]
        allowed = {"tester": TESTER_MOVES, "agent": AGENT_MOVES}.get(a.role)
        # The Issue Agent may restate a verdict it already holds — same status, fields revised (a duplicate-of
        # re-pointed at the right key). Its own verdict statuses only; a tester's stay out of reach.
        revising = a.role == "agent" and body.to == frm and frm in AGENT_VERDICTS
        if allowed is not None and body.to not in allowed.get(frm, set()) and not revising:
            raise HTTPException(409, f"A {a.role} cannot move {key} from {frm} to {body.to}")
        if a.role != "admin" and (frm, body.to) in NOTE_REQUIRED and not body.note.strip():
            raise HTTPException(400, "A note is required for that move")
        if body.agent is not None:
            if a.role == "tester":
                raise HTTPException(403, "Only the Issue Agent or an admin writes the analysis")
            unknown = set(body.agent) - set(AGENT_FIELDS)
            if unknown:
                raise HTTPException(400, f"Unknown analysis fields: {sorted(unknown)}")
            doc.setdefault("agent", {}).update({k: v for k, v in body.agent.items() if v})
            doc["agent"]["processedAt"] = now_iso()
        at = now_iso()
        who = a.name or a.role
        doc["status"] = body.to
        doc["updatedAt"] = at
        doc.setdefault("history", []).append({"at": at, "by": who, "from": frm, "to": body.to, "note": body.note.strip()})
        shots = _known_uploads(con, body.screenshots)
        if body.note.strip() or shots:
            doc.setdefault("comments", []).append({"at": at, "by": who, "text": body.note.strip(), "screenshots": shots})
        if body.to == "verified":
            doc["verification"] = {"by": who, "at": at, "note": body.note.strip()}
        put_issue(con, doc)
    return public(doc)


@app.post("/api/uploads", status_code=201)
async def upload(file: UploadFile = File(...), a: Actor = Depends(actor)):
    ctype = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if ctype not in IMAGE_TYPES:
        raise HTTPException(415, f"Only PNG, JPEG, GIF or WebP screenshots ({ctype or 'unknown type'})")
    data = await file.read()
    if not data or len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "Screenshot must be 1 byte to 20 MB")
    uid = uuid.uuid4().hex + (mimetypes.guess_extension(ctype) or ".png")
    (UPLOAD_DIR / uid).write_bytes(data)
    with tx() as con:
        register_upload(con, uid, file.filename or uid, ctype, len(data))
    return {"id": uid, "url": f"uploads/{uid}", "size": len(data), "contentType": ctype}


@app.get("/uploads/{uid}")
def serve_upload(uid: str):
    if "/" in uid or ".." in uid:
        raise HTTPException(404)
    path = UPLOAD_DIR / uid
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})


def _known_uploads(con: sqlite3.Connection, ids: list[str]) -> list[str]:
    out = []
    for i in ids:
        if con.execute("SELECT 1 FROM uploads WHERE id=?", (i,)).fetchone():
            out.append(i)
    return out


# ---------------- syncing the customer boards ----------------
class Remote:
    """The customer board over HTTP, as the Issue Agent (role agent, signed PUSH_ACTOR)."""

    def __init__(self, base: str, token: str = ""):
        self.base, self.token = base.rstrip("/"), token

    def _req(self, path: str, body: Optional[dict] = None) -> urllib.request.Request:
        headers = {"X-Role": "agent", "X-Actor": PUSH_ACTOR}
        if self.token:
            headers["X-Issues-Token"] = self.token
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        return urllib.request.Request(self.base + path, data=data, headers=headers, method="POST" if body is not None else "GET")

    def get_json(self, path: str):
        with urllib.request.urlopen(self._req(path), timeout=20) as r:
            return json.loads(r.read())

    def post_json(self, path: str, body: dict):
        with urllib.request.urlopen(self._req(path, body), timeout=20) as r:
            return json.loads(r.read())

    def get_bytes(self, path: str) -> bytes:
        with urllib.request.urlopen(self._req(path), timeout=60) as r:
            return r.read()


VERDICTS = {"fixed", "as_speced"}                                   # what a customer is told, once verified here
REOPENABLE = {"fixed", "duplicate", "as_speced", "verified", "closed"}  # a customer move to open from these is a reopen
CUSTOMER_NOTES = {
    "fixed": "Fixed — it reaches you with the next build. Please verify and mark Verified, or reopen with what you see.",
    "as_speced": "This is the specified behaviour. If you disagree, reopen and tell us what you expected.",
}


def _copy_shots(con: sqlite3.Connection, remote: Remote, ids: list[str]) -> list[str]:
    """Bring the customer's screenshots over under the same ids; a fetch that fails is skipped."""
    out = []
    for uid in ids or []:
        if "/" in uid or ".." in uid:
            continue
        if not (UPLOAD_DIR / uid).is_file():
            try:
                data = remote.get_bytes(f"/uploads/{uid}")
            except Exception:
                continue
            (UPLOAD_DIR / uid).write_bytes(data)
            register_upload(con, uid, uid, mimetypes.guess_type(uid)[0] or "image/png", len(data))
        out.append(uid)
    return out


def _verdict(con: sqlite3.Connection, doc: dict, seen: tuple = ()) -> Optional[tuple[str, str]]:
    """The verdict a customer may be told for this issue, with the time it was given: fixed or as_speced
    once the issue is verified or closed here. A customer never sees "duplicate": a verified duplicate
    passes on the verdict of the issue it duplicates, once that one is verified or closed too."""
    if doc["status"] not in ("verified", "closed"):
        return None
    h = next((h for h in reversed(doc.get("history") or []) if h.get("to") in VERDICTS | {"duplicate"}), None)
    if h is None:
        return None
    if h["to"] != "duplicate":
        return h["to"], h["at"]
    twin = (doc.get("agent") or {}).get("duplicateOf", "")
    seen = (*seen, doc["key"])
    row = con.execute("SELECT doc FROM issues WHERE key=?", (twin,)).fetchone()
    return _verdict(con, json.loads(row["doc"]), seen) if row and twin not in seen else None


def outbound(con: sqlite3.Connection, r: dict) -> Optional[tuple[str, str, str]]:
    """What this report's copy should carry now, as (status, when it was decided, the note): the later
    of the agent's question to this one report and its linked issue's released verdict; else none."""
    out = []
    if r.get("ask"):
        out.append(("more_info", r["ask"]["at"], r["ask"]["text"]))
    v = _verdict(con, get_issue(con, r["issue"])) if r.get("issue") else None
    if v:
        out.append((v[0], v[1], CUSTOMER_NOTES[v[0]]))
    return max(out, key=lambda o: o[1], default=None)


def sync_feedback(board: str, remote: Remote) -> dict:
    """One pass over one customer board. A report not seen before lands in intake (sync creates no
    issues); new comments and screenshots go onto the report; the customer's own moves are recorded on
    the report only — an answer or a reopen flags it for the agent, nothing moves an internal issue.
    Back goes STATUS only: the agent's question to this report at once, the linked issue's verdict once
    it is verified here. Idempotent; safe to run every few seconds."""
    report = {"intake": [], "comments": 0, "customerMoves": 0, "pushed": [], "skipped": []}
    theirs = sorted(remote.get_json("/api/issues?full=true&limit=5000"), key=lambda d: d.get("num", 0))
    with tx() as con:
        for f in theirs:
            r = find_report(con, board, f["key"])
            changed = r is None
            if r is None:
                r = {"board": board, "key": f["key"], **{k: f.get(k, "") for k in REPORT_FIELDS},
                     "screenshots": _copy_shots(con, remote, f.get("screenshots") or []), "comments": [],
                     "customerStatus": f.get("status", "new"), "issue": None, "flag": "",
                     "sync": {"commentsSeen": 0, "historySeen": len(f.get("history") or []), "pushedAt": ""}}
                report["intake"].append(ref(r))
            sy = r["sync"]
            for cm in (f.get("comments") or [])[sy.get("commentsSeen", 0):]:
                if cm.get("by") != PUSH_ACTOR:
                    r["comments"].append({**cm, "screenshots": _copy_shots(con, remote, cm.get("screenshots") or [])})
                    report["comments"] += 1; changed = True
            sy["commentsSeen"] = len(f.get("comments") or [])
            for h in (f.get("history") or [])[sy.get("historySeen", 0):]:
                if h.get("by") == PUSH_ACTOR:
                    continue
                report["customerMoves"] += 1; changed = True
                if h.get("to") == "open" and h.get("from") == "more_info":
                    r["flag"] = "answered"
                elif h.get("to") == "open" and h.get("from") in REOPENABLE:
                    # A reopen answers the verdict it reopens: that verdict is never sent to this report again.
                    r["flag"] = "reopened"
                    sy["pushedAt"] = (outbound(con, r) or ("", sy.get("pushedAt", "")))[1]
                    if r.get("issue"):
                        doc = get_issue(con, r["issue"])
                        doc.setdefault("comments", []).append({"at": now_iso(), "by": "sync", "screenshots": [],
                                                               "text": f"{f['key']} reopened by {board} ({h.get('by') or 'customer'}): {h.get('note', '')}"})
                        doc["updatedAt"] = now_iso()
                        put_issue(con, doc)
            sy["historySeen"] = len(f.get("history") or [])
            if r.get("customerStatus") != f.get("status"):
                r["customerStatus"] = f.get("status"); changed = True
            out = outbound(con, r)
            if out and f.get("status") != out[0] and sy.get("pushedAt") != out[1]:
                if f.get("status") in AGENT_MOVES and out[0] in AGENT_MOVES[f["status"]]:
                    try:
                        remote.post_json(f"/api/issues/{f['key']}/transition", {"to": out[0], "note": out[2]})
                        sy["pushedAt"] = out[1]   # our own push comes back signed PUSH_ACTOR and is ignored above
                        r["customerStatus"], r["flag"] = out[0], ""
                        report["pushed"].append(f"{f['key']}→{out[0]}"); changed = True
                    except urllib.error.HTTPError as e:
                        report["skipped"].append(f"{f['key']}: {e.code} {e.read().decode(errors='replace')[:120]}")
                else:
                    report["skipped"].append(f"{f['key']}: customer copy is {f.get('status')}, cannot move it to {out[0]}")
            if changed:
                put_report(con, r)
    return report


REMOTES = {n: Remote(u, os.environ.get(f"FEEDBACK_TOKEN_{n.upper().replace('-', '_')}", "")) for n, u in FEEDBACK_BOARDS.items()}
_sync_lock = threading.Lock()


def run_sync() -> dict:
    if not REMOTES:
        raise HTTPException(404, "This board triages no customer boards")
    out = {}
    with _sync_lock:
        for name, remote in REMOTES.items():
            try:
                out[name] = sync_feedback(name, remote)
            except Exception as e:  # one board down never holds up the others
                out[name] = {"error": f"unreachable: {e}"}
    return out


@app.post("/api/sync")
def sync_now(a: Actor = Depends(actor)):
    if a.role == "tester":
        raise HTTPException(403, "Only the Issue Agent or an admin runs a sync")
    return run_sync()


def _sync_forever() -> None:
    while True:
        time.sleep(FEEDBACK_SYNC_INTERVAL)
        try:
            run_sync()
        except Exception:
            pass


@app.on_event("startup")
def _start_sync() -> None:
    if REMOTES and FEEDBACK_SYNC_INTERVAL > 0:
        threading.Thread(target=_sync_forever, daemon=True, name="feedback-sync").start()


# ---------------- triage: customer reports → internal issues ----------------
class NewReport(BaseModel):
    board: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")
    key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,59}$")
    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    module: str = "other"
    kind: str = "bug"
    severity: str = "medium"
    persona: str = ""
    reporter: str = Field(min_length=1, max_length=80)
    build: str = ""
    screenshots: list[str] = []


class Attach(BaseModel):
    to: str
    note: str = ""


def _triager(a: Actor) -> None:
    if CUSTOMER:
        raise HTTPException(404, "Not on a customer board")
    if a.role not in ("agent", "admin"):
        raise HTTPException(403, "Only the Issue Agent or an admin triages a customer report")


@app.get("/api/reports")
def list_reports(intake: bool = False, board: Optional[str] = None, a: Actor = Depends(actor)):
    """Every customer report, oldest first; `intake` = the agent's queue: unlinked or flagged."""
    if CUSTOMER:
        raise HTTPException(404, "Not on a customer board")
    where, args = [], []
    if intake:
        where.append("(issue IS NULL OR flag != '')")
    if board:
        where.append("board=?"); args.append(board)
    con = connect()
    try:
        return [json.loads(r["doc"]) for r in con.execute("SELECT doc FROM reports" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY rowid", args)]
    finally:
        con.close()


@app.get("/api/reports/{board}/{key}")
def read_report(board: str, key: str, a: Actor = Depends(actor)):
    """The report, plus `release`: the status (and the note) its reporter should be shown now."""
    if CUSTOMER:
        raise HTTPException(404, "Not on a customer board")
    con = connect()
    try:
        r = get_report(con, board, key)
        out = outbound(con, r)
        return {**r, "release": {"status": out[0], "at": out[1], "note": out[2]} if out else None}
    finally:
        con.close()


@app.post("/api/reports", status_code=201)
def file_report(body: NewReport, a: Actor = Depends(actor)):
    """Another app drops a report straight into intake (the support desk escalates a ticket as board
    `support`). It is triaged like any customer report and reads its outcome back from `release`."""
    _triager(a)
    if body.board in FEEDBACK_BOARDS:
        raise HTTPException(409, f"{body.board} is a customer board: its reports arrive by sync")
    for val, allowed, what in ((body.kind, KINDS, "kind"), (body.severity, SEVERITIES, "severity"), (body.module, MODULES, "module")):
        if val not in allowed:
            raise HTTPException(400, f"Unknown {what}: {val}")
    with tx() as con:
        if find_report(con, body.board, body.key):
            raise HTTPException(409, f"{body.board}/{body.key} is already in")
        r = {**body.model_dump(exclude={"screenshots"}), "createdAt": now_iso(), "screenshots": _known_uploads(con, body.screenshots),
             "comments": [], "customerStatus": "new", "issue": None, "flag": "", "sync": {"commentsSeen": 0, "historySeen": 0, "pushedAt": ""}}
        put_report(con, r)
    return r


@app.post("/api/reports/{board}/{key}/attach")
def attach_report(board: str, key: str, body: Attach, a: Actor = Depends(actor)):
    """Link a report to an existing internal issue (the same defect). Attaching it again to the issue it
    is already on keeps it there and clears its flag: the agent read the answer or reopen and agrees."""
    _triager(a)
    at, who = now_iso(), a.name or a.role
    with tx() as con:
        r = get_report(con, board, key)
        doc = get_issue(con, body.to)
        if r.get("issue") and r["issue"] != body.to:
            raise HTTPException(409, f"{ref(r)} is on {r['issue']}; detach it first")
        if ref(r) not in (doc.get("reports") or []):
            doc["reports"] = [*(doc.get("reports") or []), ref(r)]
            doc.setdefault("history", []).append({"at": at, "by": who, "from": doc["status"], "to": doc["status"],
                                                  "note": f"Attached {ref(r)} ({r.get('reporter') or 'unknown'}): {r.get('title', '')}" + (f" — {body.note.strip()}" if body.note.strip() else "")})
            doc["updatedAt"] = at
            put_issue(con, doc)
        r["issue"], r["flag"] = doc["key"], ""
        put_report(con, r)
        return with_reports(con, doc)


@app.post("/api/reports/{board}/{key}/promote", status_code=201)
def promote_report(board: str, key: str, body: Comment, a: Actor = Depends(actor)):
    """A new defect: the report becomes a new internal issue (its title, description and screenshots), linked to it."""
    _triager(a)
    at, who = now_iso(), a.name or a.role
    with tx() as con:
        r = get_report(con, board, key)
        if r.get("issue"):
            raise HTTPException(409, f"{ref(r)} is on {r['issue']}; detach it first")
        num = next_num(con)
        doc = {"key": f"{PREFIX}-{num}", "num": num, "title": r.get("title") or ref(r), "description": r.get("description", ""),
               "module": r.get("module") if r.get("module") in MODULES else "other", "kind": r.get("kind") if r.get("kind") in KINDS else "bug",
               "severity": r.get("severity") if r.get("severity") in SEVERITIES else "medium", "persona": r.get("persona", ""),
               "build": r.get("build", ""), "status": "new", "source": "customer", "sourceRef": "", "reporter": r.get("reporter", ""),
               "createdAt": at, "updatedAt": at, "screenshots": list(r.get("screenshots") or []), "agent": {}, "comments": [],
               "reports": [ref(r)], "history": [{"at": at, "by": who, "from": "", "to": "new",
                                                 "note": f"Promoted from {ref(r)} (filed by {r.get('reporter') or 'unknown'})." + (f" {body.text.strip()}" if body.text.strip() else "")}]}
        put_issue(con, doc)
        r["issue"], r["flag"] = doc["key"], ""
        put_report(con, r)
        return with_reports(con, doc)


@app.post("/api/reports/{board}/{key}/ask")
def ask_report(board: str, key: str, body: Comment, a: Actor = Depends(actor)):
    """more_info is per report: the question goes to this one customer's board at the next sync."""
    _triager(a)
    if not body.text.strip():
        raise HTTPException(400, "Write the question")
    at, who = now_iso(), a.name or a.role
    with tx() as con:
        r = get_report(con, board, key)
        r["ask"] = {"at": at, "by": who, "text": body.text.strip()}
        r["comments"].append({"at": at, "by": who, "text": body.text.strip(), "screenshots": []})
        r["flag"] = ""
        put_report(con, r)
    return r


@app.post("/api/reports/{board}/{key}/detach")
def detach_report(board: str, key: str, body: Comment, a: Actor = Depends(actor)):
    """Unlink a report (a reopen that is a different defect); it is back in intake, to promote or attach elsewhere."""
    _triager(a)
    at, who = now_iso(), a.name or a.role
    with tx() as con:
        r = get_report(con, board, key)
        if not r.get("issue"):
            raise HTTPException(409, f"{ref(r)} is not on an issue")
        doc = get_issue(con, r["issue"])
        doc["reports"] = [x for x in doc.get("reports") or [] if x != ref(r)]
        doc.setdefault("history", []).append({"at": at, "by": who, "from": doc["status"], "to": doc["status"],
                                              "note": f"Detached {ref(r)}" + (f": {body.text.strip()}" if body.text.strip() else ".")})
        doc["updatedAt"] = at
        put_issue(con, doc)
        r["issue"], r["flag"] = None, ""
        put_report(con, r)
    return r


@app.exception_handler(HTTPException)
async def _http_err(_: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.get("/healthz")
def healthz():
    return {"ok": True}


app.mount("/", StaticFiles(directory=HERE / "static", html=True), name="static")
