"""Software-factory issue tracker — a standalone FastAPI app over SQLite.

Testers file issues (with screenshots) from the static page; Claude works them through
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
# The roles a board ACCEPTS. The customer board sets ISSUES_ROLES=tester,claude so nobody there can
# act as admin (set any status), whatever header a request carries; the page offers only what is
# listed here, minus claude, which is the CLI's role.
ALLOWED_ROLES = {r.strip() for r in os.environ.get("ISSUES_ROLES", "tester,claude,admin").split(",") if r.strip()}
# A CUSTOMER board shows status only: the analysis never leaves the server, however it got there.
CUSTOMER = os.environ.get("ISSUES_CUSTOMER", "") == "1"
# The internal board MIRRORS a customer board: every issue filed there is copied here (source
# "customer", sourceRef = its key, screenshots and comments included), the analysis is written
# here, and only the resulting STATUS travels back. Set to the customer board's base URL.
FEEDBACK_SYNC_URL = os.environ.get("FEEDBACK_SYNC_URL", "").rstrip("/")
FEEDBACK_SYNC_TOKEN = os.environ.get("FEEDBACK_SYNC_TOKEN", "")
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
CLAUDE_FIELDS = ["rootCause", "fixProposed", "fix", "files", "tests", "humanTests", "duplicateOf", "specRef", "infoNeeded"]
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}

# Who may move an issue where. Testers verify and reopen; Claude gives verdicts; admin does anything.
TESTER_MOVES = {"more_info": {"open"}, "fixed": {"verified", "open"}, "duplicate": {"verified", "open"},
                "as_speced": {"verified", "open"}, "verified": {"closed", "open"}, "closed": {"open"}}
CLAUDE_MOVES = {"new": {"fixed", "duplicate", "as_speced", "more_info"}, "open": {"fixed", "duplicate", "as_speced", "more_info"}}
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
        """)


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


def next_num(con: sqlite3.Connection) -> int:
    row = con.execute("SELECT MAX(num) AS m FROM issues WHERE num >= ?", (FIRST_NEW_NUM,)).fetchone()
    return (row["m"] or FIRST_NEW_NUM - 1) + 1


def register_upload(con: sqlite3.Connection, uid: str, filename: str, content_type: str, size: int) -> None:
    con.execute("INSERT OR REPLACE INTO uploads(id,filename,content_type,size,created_at) VALUES (?,?,?,?,?)",
                (uid, filename, content_type, size, now_iso()))


# ---------------- auth / actor ----------------
class Actor(BaseModel):
    name: str
    role: str  # tester | claude | admin


def actor(request: Request) -> Actor:
    if TOKEN:  # X-Issues-Token, so a reverse proxy's basic auth can keep the Authorization header
        given = request.headers.get("x-issues-token") or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if given != TOKEN:
            raise HTTPException(401, "Missing or wrong token")
    role = request.headers.get("x-role", "tester").lower()
    if role not in {"tester", "claude", "admin"}:
        raise HTTPException(400, "X-Role must be tester, claude or admin")
    if role not in ALLOWED_ROLES:
        raise HTTPException(403, f"This board does not offer the {role} role")
    name = request.headers.get("x-actor", "").strip()[:80] or ("claude" if role == "claude" else "")
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


class Transition(BaseModel):
    to: str
    note: str = ""
    screenshots: list[str] = []
    claude: Optional[dict[str, Any]] = None


def public(doc: dict) -> dict:
    """What a caller may see. On a customer board the analysis block is withheld entirely."""
    if CUSTOMER:
        doc = {**doc, "claude": {}}
    return doc


def summary(doc: dict) -> dict:
    keep = ["key", "num", "title", "status", "module", "kind", "severity", "source", "sourceRef", "reporter",
            "createdAt", "updatedAt", "build", "persona"]
    s = {k: doc.get(k) for k in keep}
    s["screenshotCount"] = len(doc.get("screenshots") or [])
    s["processed"] = bool((doc.get("claude") or {}).get("processedAt")) and not CUSTOMER
    return s


@app.get("/api/meta")
def meta(a: Actor = Depends(actor)):
    return {"statuses": STATUSES, "kinds": KINDS, "severities": SEVERITIES, "modules": MODULES, "actor": a.model_dump(),
            "tokenRequired": bool(TOKEN), "brand": BRAND, "prefix": PREFIX, "customer": CUSTOMER, "pushActor": PUSH_ACTOR,
            "mirrors": bool(FEEDBACK_SYNC_URL),
            "roles": [r for r in ("tester", "admin") if r in ALLOWED_ROLES]}


@app.get("/api/stats")
def stats(a: Actor = Depends(actor)):
    con = connect()
    try:
        rows = con.execute("SELECT status, COUNT(*) AS n FROM issues GROUP BY status").fetchall()
        return {"byStatus": {r["status"]: r["n"] for r in rows}, "total": sum(r["n"] for r in rows)}
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
        docs = [d for d in docs if ql in " ".join(str(d.get(k, "")) for k in ("key", "title", "description", "sourceRef")).lower()]
    if reporter:
        docs = [d for d in docs if (d.get("reporter") or "").lower() == reporter.lower()]
    return [public(d) for d in docs] if full else [summary(d) for d in docs]


@app.get("/api/issues/{key}")
def read_issue(key: str, a: Actor = Depends(actor)):
    con = connect()
    try:
        return public(get_issue(con, key))
    finally:
        con.close()


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
               "createdAt": at, "updatedAt": at, "screenshots": _known_uploads(con, body.screenshots), "claude": {},
               "comments": [], "history": [{"at": at, "by": a.name, "from": "", "to": "new", "note": ""}]}
        put_issue(con, doc)
    return doc


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
        allowed = {"tester": TESTER_MOVES, "claude": CLAUDE_MOVES}.get(a.role)
        if allowed is not None and body.to not in allowed.get(frm, set()):
            raise HTTPException(409, f"A {a.role} cannot move {key} from {frm} to {body.to}")
        if a.role != "admin" and (frm, body.to) in NOTE_REQUIRED and not body.note.strip():
            raise HTTPException(400, "A note is required for that move")
        if body.claude is not None:
            if a.role == "tester":
                raise HTTPException(403, "Only Claude or an admin writes the analysis")
            unknown = set(body.claude) - set(CLAUDE_FIELDS)
            if unknown:
                raise HTTPException(400, f"Unknown analysis fields: {sorted(unknown)}")
            doc.setdefault("claude", {}).update({k: v for k, v in body.claude.items() if v})
            doc["claude"]["processedAt"] = now_iso()
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


# ---------------- mirroring a customer board ----------------
class Remote:
    """The customer board over HTTP, as the Issue Agent (role claude, signed PUSH_ACTOR)."""

    def __init__(self, base: str, token: str = ""):
        self.base, self.token = base.rstrip("/"), token

    def _req(self, path: str, body: Optional[dict] = None) -> urllib.request.Request:
        headers = {"X-Role": "claude", "X-Actor": PUSH_ACTOR}
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


CUSTOMER_MOVES = {"open", "verified", "closed"}   # what the customer may do to their copy
VERDICTS = {"fixed", "duplicate", "as_speced"}    # released to the customer once verified here


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


def _release_status(m: dict) -> Optional[str]:
    """The status the customer's copy should carry now: more_info as soon as the agent asks; the agent's
    verdict (fixed / duplicate / as_speced) only once the mirror is verified or closed here; else none."""
    if m["status"] == "more_info":
        return "more_info"
    if m["status"] in ("verified", "closed"):
        for h in reversed(m.get("history") or []):
            if h.get("to") in VERDICTS:
                return h["to"]
    return None


def _customer_note(mirror: dict, st: str) -> str:
    """The one line the customer sees with a status: the question when we need an answer, else a plain word."""
    c = mirror.get("claude") or {}
    if st == "more_info":
        return (c.get("infoNeeded") or "We need more information to reproduce this — please add what you can and reopen.").strip()
    if st == "fixed":
        return "Fixed — it reaches you with the next build. Please verify and mark Verified, or reopen with what you see."
    if st == "duplicate":
        return "This is the same defect as one already being worked; it is tracked there."
    if st == "as_speced":
        return "This is the specified behaviour. If you disagree, reopen and tell us what you expected."
    return ""


def sync_feedback(remote: Remote) -> dict:
    """One pass: customer issues → mirrors here (new ones, new comments, the customer's own moves); a
    question here → more_info there at once; a verdict here → its STATUS there once verified internally.
    Idempotent; safe to run every few seconds."""
    report = {"created": [], "comments": 0, "customerMoves": 0, "pushed": [], "skipped": []}
    # Oldest first, so mirrors are numbered in the order the customer filed them.
    theirs = sorted(remote.get_json("/api/issues?full=true&limit=5000"), key=lambda d: d.get("num", 0))
    with tx() as con:
        mine = {d["sourceRef"]: d for d in (json.loads(r["doc"]) for r in con.execute("SELECT doc FROM issues WHERE source='customer'"))}
        for f in theirs:
            m = mine.get(f["key"])
            changed = m is None
            if m is None:
                at = now_iso()
                num = next_num(con)
                m = {"key": f"{PREFIX}-{num}", "num": num, "title": f.get("title", ""), "description": f.get("description", ""),
                     "module": f.get("module", "other"), "kind": f.get("kind", "bug"), "severity": f.get("severity", "medium"),
                     "persona": f.get("persona", ""), "build": f.get("build", ""), "status": f.get("status", "new"), "source": "customer",
                     "sourceRef": f["key"], "reporter": f.get("reporter", ""), "createdAt": f.get("createdAt", at), "updatedAt": at,
                     "screenshots": _copy_shots(con, remote, f.get("screenshots") or []), "claude": {},
                     "comments": [], "history": [{"at": at, "by": "sync", "from": "", "to": f.get("status", "new"),
                                                  "note": f"Mirrored from the customer board ({f['key']}, filed by {f.get('reporter') or 'unknown'})."}],
                     "sync": {"commentsSeen": 0, "historySeen": len(f.get("history") or []), "pushedAt": ""}}
                report["created"].append(f"{m['key']}←{f['key']}")
            sy = m.setdefault("sync", {"commentsSeen": 0, "historySeen": 0, "pushedAt": ""})
            # the customer's words, with their screenshots
            for cm in (f.get("comments") or [])[sy.get("commentsSeen", 0):]:
                if cm.get("by") != PUSH_ACTOR:
                    m.setdefault("comments", []).append({**cm, "screenshots": _copy_shots(con, remote, cm.get("screenshots") or [])})
                    report["comments"] += 1; changed = True
            sy["commentsSeen"] = len(f.get("comments") or [])
            # the customer's own moves: answer/reopen, verify, close
            for h in (f.get("history") or [])[sy.get("historySeen", 0):]:
                if h.get("by") != PUSH_ACTOR and h.get("to") in CUSTOMER_MOVES and m["status"] != h.get("to"):
                    m.setdefault("history", []).append({"at": h.get("at") or now_iso(), "by": h.get("by") or "customer", "from": m["status"],
                                                        "to": h["to"], "note": h.get("note", "")})
                    m["status"] = h["to"]
                    if h["to"] == "verified":
                        m["verification"] = {"by": h.get("by"), "at": h.get("at"), "note": h.get("note", "")}
                    report["customerMoves"] += 1; changed = True
            sy["historySeen"] = len(f.get("history") or [])
            # what travels back, status only: a question at once; a verdict (fixed / duplicate /
            # as_speced) only after someone here has VERIFIED it — the internal Verified is the release.
            last = (m.get("history") or [{}])[-1]
            release = _release_status(m)
            if release and f.get("status") != release and sy.get("pushedAt") != last.get("at"):
                if f.get("status") in CLAUDE_MOVES and release in CLAUDE_MOVES[f["status"]]:
                    try:
                        remote.post_json(f"/api/issues/{f['key']}/transition", {"to": release, "note": _customer_note(m, release)})
                        sy["pushedAt"] = last.get("at")   # our own push comes back signed PUSH_ACTOR and is ignored above
                        report["pushed"].append(f"{f['key']}→{release}"); changed = True
                    except urllib.error.HTTPError as e:
                        report["skipped"].append(f"{f['key']}: {e.code} {e.read().decode(errors='replace')[:120]}")
                else:
                    report["skipped"].append(f"{f['key']}: customer copy is {f.get('status')}, cannot move it to {release}")
            if changed:
                m["updatedAt"] = now_iso()
                put_issue(con, m)
    return report


REMOTE: Optional[Remote] = Remote(FEEDBACK_SYNC_URL, FEEDBACK_SYNC_TOKEN) if FEEDBACK_SYNC_URL else None
_sync_lock = threading.Lock()


def run_sync() -> dict:
    if REMOTE is None:
        raise HTTPException(404, "This board mirrors no customer board")
    with _sync_lock:
        return sync_feedback(REMOTE)


@app.post("/api/sync")
def sync_now(a: Actor = Depends(actor)):
    if a.role == "tester":
        raise HTTPException(403, "Only the Issue Agent or an admin runs a sync")
    try:
        return run_sync()
    except HTTPException:
        raise
    except Exception as e:  # the customer board is down: say so, keep serving
        raise HTTPException(502, f"Customer board unreachable: {e}")


def _sync_forever() -> None:
    while True:
        time.sleep(FEEDBACK_SYNC_INTERVAL)
        try:
            run_sync()
        except Exception:
            pass


@app.on_event("startup")
def _start_sync() -> None:
    if REMOTE is not None and FEEDBACK_SYNC_INTERVAL > 0:
        threading.Thread(target=_sync_forever, daemon=True, name="feedback-sync").start()


@app.exception_handler(HTTPException)
async def _http_err(_: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.get("/healthz")
def healthz():
    return {"ok": True}


app.mount("/", StaticFiles(directory=HERE / "static", html=True), name="static")
