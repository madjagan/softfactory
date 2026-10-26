"""Software-factory support desk — a standalone FastAPI app over SQLite, a sibling of issues/.

Customers file tickets from the page or the in-app widget; the support team answers them; the
Support Agent drafts replies through tools/support_cli.py and never sends. One server for every
org: isolation rests on the org filter in every query, so the customer view is an allowlist.
Serve at any path prefix: the page uses relative URLs only.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import sqlite3
import threading
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("SUPPORT_DATA", HERE / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "support.sqlite3"
BRAND = os.environ.get("SUPPORT_BRAND", "Support")
PREFIX = os.environ.get("SUPPORT_PREFIX", "SUP")
FIRST_NUM = int(os.environ.get("SUPPORT_FIRST_NUM", "1001"))
ORGS = [o.strip().lower() for o in os.environ.get("SUPPORT_ORGS", "").split(",") if o.strip()]
TOKEN = os.environ.get("SUPPORT_TOKEN", "")  # the support team's shared token (support, agent, admin)
# One token per org (SUPPORT_TOKEN_<ORG>): the token a customer presents IS their org.
ORG_TOKENS = {t: o for o in ORGS if (t := os.environ.get("SUPPORT_TOKEN_" + re.sub(r"[^A-Z0-9]", "_", o.upper()), ""))}
# Local dev only: with no token configured at all, a customer names their org in X-Org.
OPEN = not TOKEN and not ORG_TOKENS
WIDGET_SECRET = os.environ.get(os.environ.get("SUPPORT_WIDGET_SECRET_ENV", "SUPPORT_WIDGET_SECRET"), "")
AUTO_CLOSE_DAYS = int(os.environ.get("SUPPORT_AUTO_CLOSE_DAYS", "7"))
CATEGORIES = [c.strip() for c in os.environ.get("SUPPORT_CATEGORIES", "question,how-to,defect,account,other").split(",") if c.strip()]
TRACKER_URL = os.environ.get("SUPPORT_TRACKER_URL", "").rstrip("/")  # the internal tracker that takes escalations
TRACKER_TOKEN = os.environ.get("SUPPORT_TRACKER_TOKEN", "")           # the tracker's ISSUES_TOKEN
TRACKER_SYNC_INTERVAL = int(os.environ.get("SUPPORT_TRACKER_SYNC_INTERVAL", "60"))

STATUSES = ["new", "open", "waiting_on_customer", "escalated", "resolved", "closed"]
PRIORITIES = ["low", "normal", "high", "urgent"]
ROLES = {"customer", "support", "agent", "admin"}
STAFF = {"support", "agent", "admin"}
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}

SUPPORT_MOVES = {"new": {"open", "waiting_on_customer", "escalated", "resolved"},
                 "open": {"waiting_on_customer", "escalated", "resolved"},
                 "waiting_on_customer": {"open", "escalated", "resolved"},
                 "escalated": {"open", "resolved"},
                 "resolved": {"open"}}
CUSTOMER_MOVES = {"resolved": {"closed", "open"}, "closed": {"open"}}
NOTE_REQUIRED = {("resolved", "open"), ("closed", "open")}
# A customer's word on these hands the ticket back to support.
ANSWERED = {"waiting_on_customer", "resolved"}


def now() -> datetime:
    """The clock seam: the only reader of the system time in this app. Tests patch it."""
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


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
        CREATE TABLE IF NOT EXISTS tickets (
            key TEXT PRIMARY KEY, num INTEGER UNIQUE NOT NULL, org TEXT NOT NULL, requester TEXT NOT NULL,
            status TEXT NOT NULL, category TEXT, updated_at TEXT NOT NULL, doc TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS tickets_org ON tickets(org, requester);
        CREATE INDEX IF NOT EXISTS tickets_status ON tickets(status);
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


def put_ticket(con: sqlite3.Connection, doc: dict) -> None:
    con.execute(
        "INSERT OR REPLACE INTO tickets(key,num,org,requester,status,category,updated_at,doc) VALUES (?,?,?,?,?,?,?,?)",
        (doc["key"], doc["num"], doc["org"], doc["requester"]["email"], doc["status"], doc.get("category"),
         doc["updatedAt"], json.dumps(doc, ensure_ascii=False)))


def next_num(con: sqlite3.Connection) -> int:
    row = con.execute("SELECT MAX(num) AS m FROM tickets").fetchone()
    return max(row["m"] or 0, FIRST_NUM - 1) + 1


def register_upload(con: sqlite3.Connection, uid: str, filename: str, content_type: str, size: int) -> None:
    con.execute("INSERT OR REPLACE INTO uploads(id,filename,content_type,size,created_at) VALUES (?,?,?,?,?)",
                (uid, filename, content_type, size, now_iso()))


# ---------------- auth / actor ----------------
class Actor(BaseModel):
    name: str
    role: str  # customer | support | agent | admin
    org: str = ""
    email: str = ""
    user_id: str = ""
    widget: bool = False


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_widget_token(payload: dict, secret: str) -> str:
    """What the product's backend does: base64url(JSON) + "." + base64url(HMAC-SHA256 of that part)."""
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{body}.{sig}"


def widget_actor(token: str) -> Actor:
    body, _, sig = token.partition(".")
    good = base64.urlsafe_b64encode(hmac.new(WIDGET_SECRET.encode(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    if not WIDGET_SECRET or not sig or not hmac.compare_digest(sig, good):
        raise HTTPException(401, "Widget token is not signed by this product")
    try:
        p = json.loads(_b64d(body))
    except ValueError:
        raise HTTPException(401, "Widget token is unreadable")
    org, email = str(p.get("org", "")).lower(), str(p.get("email", "")).strip().lower()
    if org not in ORGS or not email or float(p.get("exp", 0)) < now().timestamp():
        raise HTTPException(401, "Widget token is expired or names no known org and user")
    return Actor(name=str(p.get("name") or email)[:80], role="customer", org=org, email=email,
                 user_id=str(p.get("userId") or "")[:80], widget=True)


def actor(request: Request) -> Actor:
    h = request.headers
    if h.get("x-widget-token"):
        return widget_actor(h["x-widget-token"])
    role = h.get("x-role", "customer").lower()
    if role not in ROLES:
        raise HTTPException(400, "X-Role must be customer, support, agent or admin")
    given = h.get("x-support-token") or h.get("authorization", "").removeprefix("Bearer ").strip()
    name = h.get("x-actor", "").strip()[:80]
    if role in STAFF:
        if not OPEN and not (TOKEN and hmac.compare_digest(given, TOKEN)):
            raise HTTPException(401, "Missing or wrong support token")
        return Actor(name=name or ("Support Agent" if role == "agent" else ""), role=role)
    if OPEN:
        org = h.get("x-org", "").strip().lower()
    else:
        org = next((o for t, o in ORG_TOKENS.items() if hmac.compare_digest(given, t)), "")
        if not org:
            raise HTTPException(401, "Missing or wrong organisation token")
    if org not in ORGS:
        raise HTTPException(400, "Say which organisation you are from (X-Org)")
    return Actor(name=name, role="customer", org=org, email=h.get("x-email", "").strip().lower()[:120])


def need_requester(a: Actor) -> None:
    if a.role == "customer" and not a.email:
        raise HTTPException(400, "Say who you are (X-Email header)")


def load(con: sqlite3.Connection, key: str, a: Actor) -> dict:
    """A ticket the caller may see. Another org's ticket, or another requester's, does not exist (404, never 403)."""
    row = con.execute("SELECT doc FROM tickets WHERE key=?", (key,)).fetchone()
    doc = json.loads(row["doc"]) if row else None
    if doc is None or (a.role == "customer" and (doc["org"] != a.org or doc["requester"]["email"] != a.email)):
        raise HTTPException(404, f"{key} not found")
    return doc


# ---------------- what a customer may see ----------------
def customer_view(doc: dict) -> dict:
    """An allowlist, so a field added later stays internal until someone adds it here."""
    keep = ["key", "num", "title", "description", "status", "requester", "context", "screenshots",
            "createdAt", "updatedAt", "reopenedFrom", "reopenedAs"]
    out = {k: doc.get(k) for k in keep if k in doc}
    out["messages"] = [{"at": m["at"], "by": m["by"], "text": m["text"], "screenshots": m.get("screenshots") or []}
                       for m in doc.get("messages") or [] if m.get("visibility") == "public"]
    out["history"] = [{"at": h["at"], "from": h["from"], "to": h["to"], "by": h["by"] if h.get("role") == "customer" else "Support"}
                      for h in doc.get("history") or []]
    return out


def view(doc: dict, a: Actor) -> dict:
    return customer_view(doc) if a.role == "customer" else doc


def summary(doc: dict, a: Actor) -> dict:
    if a.role == "customer":
        return {k: doc.get(k) for k in ("key", "num", "title", "status", "createdAt", "updatedAt")}
    keep = ["key", "num", "org", "requester", "title", "status", "category", "priority", "createdAt", "updatedAt",
            "firstResponseAt", "reopenedFrom"]
    s = {k: doc.get(k) for k in keep}
    s["issueRef"] = (doc.get("escalation") or {}).get("issueRef", "")
    s["draftPending"] = any(m.get("visibility") == "draft" for m in doc.get("messages") or [])
    s["needsDraft"] = needs_draft(doc)
    s["screenshotCount"] = len(doc.get("screenshots") or [])
    return s


def needs_draft(doc: dict) -> bool:
    """The agent's queue: new or open, no draft waiting, and nobody on the team has spoken since the customer did."""
    if doc["status"] not in ("new", "open"):
        return False
    msgs = doc.get("messages") or []
    if any(m.get("visibility") == "draft" for m in msgs):
        return False
    last_customer = max([doc["createdAt"]] + [m["at"] for m in msgs if m.get("role") == "customer"])
    return not any(m.get("role") != "customer" and m["at"] >= last_customer for m in msgs)


# ---------------- auto-close ----------------
def auto_close() -> list[str]:
    """Resolved tickets nobody answered within AUTO_CLOSE_DAYS close themselves. Runs whenever tickets are read."""
    if AUTO_CLOSE_DAYS <= 0:
        return []
    cutoff = now() - timedelta(days=AUTO_CLOSE_DAYS)
    closed = []
    with tx() as con:
        for row in con.execute("SELECT doc FROM tickets WHERE status='resolved'").fetchall():
            doc = json.loads(row["doc"])
            if parse_iso(doc.get("resolvedAt") or doc["updatedAt"]) <= cutoff:
                at = now_iso()
                doc["status"], doc["updatedAt"] = "closed", at
                doc["history"].append({"at": at, "by": "auto-close", "role": "system", "from": "resolved", "to": "closed",
                                       "note": f"No answer in {AUTO_CLOSE_DAYS} days"})
                put_ticket(con, doc)
                closed.append(doc["key"])
    return closed


# ---------------- API ----------------
app = FastAPI(title=f"{BRAND} — support", docs_url="/api/docs", openapi_url="/api/openapi.json")
# The widget runs on the product's origin. It authenticates with a header token, never a cookie,
# so a cross-origin page can do nothing without a token the product's backend signed.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"],
                   allow_headers=["X-Widget-Token", "Content-Type"])


@app.on_event("startup")
def _startup() -> None:
    init_db()


class Tracker:
    """The internal tracker over HTTP, as the support desk: escalations go into its intake as board `support`."""

    def __init__(self, base: str, token: str = ""):
        self.base, self.token = base, token

    def _req(self, path: str, body: Optional[dict] = None) -> urllib.request.Request:
        headers = {"X-Role": "agent", "X-Actor": "support"}
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


tracker = Tracker(TRACKER_URL, TRACKER_TOKEN) if TRACKER_URL else None


class NewTicket(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    screenshots: list[str] = []
    context: dict[str, str] = {}


class Message(BaseModel):
    text: str = ""
    screenshots: list[str] = []
    visibility: str = ""
    tag: str = ""


class DraftEdit(BaseModel):
    text: Optional[str] = None


class Fields(BaseModel):
    category: Optional[str] = None
    priority: Optional[str] = None


class Transition(BaseModel):
    to: str
    note: str = ""
    issueRef: str = ""


@app.get("/api/meta")
def meta(a: Actor = Depends(actor)):
    out = {"statuses": STATUSES, "brand": BRAND, "prefix": PREFIX, "actor": a.model_dump(), "tokenRequired": not OPEN}
    if a.role != "customer":
        out.update({"orgs": ORGS, "categories": CATEGORIES, "priorities": PRIORITIES, "autoCloseDays": AUTO_CLOSE_DAYS})
    return out


@app.get("/api/stats")
def stats(a: Actor = Depends(actor)):
    if a.role == "customer":
        raise HTTPException(403, "Support only")
    auto_close()
    con = connect()
    try:
        rows = con.execute("SELECT status, COUNT(*) AS n FROM tickets GROUP BY status").fetchall()
        return {"byStatus": {r["status"]: r["n"] for r in rows}, "total": sum(r["n"] for r in rows)}
    finally:
        con.close()


@app.get("/api/tickets")
def list_tickets(status: Optional[str] = None, org: Optional[str] = None, category: Optional[str] = None,
                 q: Optional[str] = None, needsDraft: bool = False, full: bool = False,
                 limit: int = Query(2000, le=5000), a: Actor = Depends(actor)):
    need_requester(a)
    auto_close()
    where, args = [], []
    if a.role == "customer":
        where += ["org=?", "requester=?"]; args += [a.org, a.email]
    elif org:
        where.append("org=?"); args.append(org)
    if status:
        vals = status.split(",")
        where.append(f"status IN ({','.join('?' * len(vals))})"); args += vals
    if category:
        where.append("category=?"); args.append(category)
    sql = "SELECT doc FROM tickets" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY num DESC LIMIT ?"
    con = connect()
    try:
        docs = [json.loads(r["doc"]) for r in con.execute(sql, args + [limit])]
    finally:
        con.close()
    if q:
        ql = q.lower()
        docs = [d for d in docs if ql in " ".join(str(d.get(k, "")) for k in ("key", "title", "description")).lower()]
    if needsDraft:
        docs = [d for d in docs if needs_draft(d)]
    return [view(d, a) for d in docs] if full else [summary(d, a) for d in docs]


@app.get("/api/tickets/{key}")
def read_ticket(key: str, a: Actor = Depends(actor)):
    need_requester(a)
    auto_close()
    con = connect()
    try:
        return view(load(con, key, a), a)
    finally:
        con.close()


@app.post("/api/tickets", status_code=201)
def create_ticket(body: NewTicket, a: Actor = Depends(actor)):
    if a.role != "customer":
        raise HTTPException(403, "Customers file tickets")
    need_requester(a)
    if not a.name:
        raise HTTPException(400, "Say who you are (X-Actor header)")
    with tx() as con:
        return customer_view(_new_ticket(con, a, body.title, body.description, body.screenshots,
                                         {k: str(body.context.get(k, ""))[:500] for k in ("pageUrl", "appVersion", "userAgent")} if a.widget else {}))


def _new_ticket(con: sqlite3.Connection, a: Actor, title: str, description: str, shots: list[str], context: dict, **extra) -> dict:
    at = now_iso()
    num = next_num(con)
    requester = {"name": a.name, "email": a.email, **({"userId": a.user_id} if a.user_id else {})}
    doc = {"key": f"{PREFIX}-{num}", "num": num, "org": a.org, "requester": requester, "title": title.strip(),
           "description": description.strip(), "category": "", "priority": "normal", "status": "new", "context": context,
           "screenshots": _known_uploads(con, shots), "messages": [], "escalation": None,
           "history": [{"at": at, "by": a.name, "role": "customer", "from": "", "to": "new", "note": ""}],
           "createdAt": at, "updatedAt": at, "firstResponseAt": "", **extra}
    put_ticket(con, doc)
    return doc


@app.post("/api/tickets/{key}/messages")
def add_message(key: str, body: Message, a: Actor = Depends(actor)):
    need_requester(a)
    vis = body.visibility or {"customer": "public", "agent": "draft"}.get(a.role, "public")
    if vis not in ("public", "internal", "draft"):
        raise HTTPException(400, "visibility must be public, internal or draft")
    if a.role == "customer" and vis != "public":
        raise HTTPException(403, "Customers write public messages")
    if a.role == "agent" and vis == "public":
        raise HTTPException(403, "The Support Agent drafts; a person sends")
    if not body.text.strip() and not body.screenshots:
        raise HTTPException(400, "Write a message or attach a screenshot")
    with tx() as con:
        doc = load(con, key, a)
        if doc["status"] == "closed" and a.role == "customer":
            raise HTTPException(409, f"{key} is closed; reopen it to continue")
        at = now_iso()
        who = a.name or a.role
        msg = {"id": uuid.uuid4().hex[:12], "at": at, "by": who, "role": a.role, "text": body.text.strip(),
               "screenshots": _known_uploads(con, body.screenshots), "visibility": vis}
        if body.tag:
            msg["tag"] = body.tag[:40]
        doc["messages"].append(msg)
        if vis == "public" and a.role != "customer" and not doc.get("firstResponseAt"):
            doc["firstResponseAt"] = at
        if a.role == "customer" and doc["status"] in ANSWERED:
            doc["history"].append({"at": at, "by": who, "role": "customer", "from": doc["status"], "to": "open", "note": ""})
            doc["status"] = "open"
        doc["updatedAt"] = at
        put_ticket(con, doc)
    return view(doc, a)


def _draft(doc: dict, mid: str) -> dict:
    m = next((m for m in doc["messages"] if m.get("id") == mid), None)
    if m is None or m.get("visibility") != "draft":
        raise HTTPException(404, f"No draft {mid} on {doc['key']}")
    return m


@app.post("/api/tickets/{key}/messages/{mid}")
def edit_draft(key: str, mid: str, body: DraftEdit, a: Actor = Depends(actor)):
    if a.role == "customer":
        raise HTTPException(404, f"{key} not found")
    with tx() as con:
        doc = load(con, key, a)
        m = _draft(doc, mid)
        if body.text is not None:
            m["text"] = body.text.strip()
        m["editedBy"], m["editedAt"] = a.name or a.role, now_iso()
        doc["updatedAt"] = m["editedAt"]
        put_ticket(con, doc)
    return doc


@app.post("/api/tickets/{key}/messages/{mid}/send")
def send_draft(key: str, mid: str, body: DraftEdit, a: Actor = Depends(actor)):
    if a.role == "customer":
        raise HTTPException(404, f"{key} not found")
    if a.role == "agent":
        raise HTTPException(403, "The Support Agent drafts; a person sends")
    with tx() as con:
        doc = load(con, key, a)
        m = _draft(doc, mid)
        at = now_iso()
        if body.text is not None:
            m["text"] = body.text.strip()
        m.update({"visibility": "public", "draftedBy": m["by"], "by": a.name or a.role, "role": a.role, "at": at})
        if not doc.get("firstResponseAt"):
            doc["firstResponseAt"] = at
        doc["updatedAt"] = at
        put_ticket(con, doc)
    return doc


@app.post("/api/tickets/{key}/fields")
def set_fields(key: str, body: Fields, a: Actor = Depends(actor)):
    if a.role == "customer":
        raise HTTPException(403, "Support sets these")
    if body.priority is not None and a.role == "agent":
        raise HTTPException(403, "The Support Agent sets the category only")
    if body.category is not None and body.category not in CATEGORIES:
        raise HTTPException(400, f"Unknown category: {body.category}")
    if body.priority is not None and body.priority not in PRIORITIES:
        raise HTTPException(400, f"Unknown priority: {body.priority}")
    with tx() as con:
        doc = load(con, key, a)
        doc.update({k: v for k, v in body.model_dump().items() if v is not None})
        doc["updatedAt"] = now_iso()
        put_ticket(con, doc)
    return doc


@app.post("/api/tickets/{key}/transition")
def transition(key: str, body: Transition, a: Actor = Depends(actor)):
    need_requester(a)
    if body.to not in STATUSES:
        raise HTTPException(400, f"Unknown status: {body.to}")
    if a.role == "agent":
        raise HTTPException(403, "The Support Agent never changes status; it recommends")
    with tx() as con:
        doc = load(con, key, a)
        frm = doc["status"]
        allowed = {"customer": CUSTOMER_MOVES, "support": SUPPORT_MOVES}.get(a.role)
        if allowed is not None and body.to not in allowed.get(frm, set()):
            raise HTTPException(409, f"A {a.role} cannot move {key} from {frm} to {body.to}")
        note = body.note.strip()
        if a.role == "customer" and (frm, body.to) in NOTE_REQUIRED and not note:
            raise HTTPException(400, "Say what is still wrong")
        if body.to == "escalated" and not tracker and not body.issueRef.strip() and not doc.get("escalation"):
            raise HTTPException(400, "Escalating needs the internal issue (issueRef)")
        at = now_iso()
        who = a.name or a.role
        if a.role == "customer" and frm == "closed":
            # A closed ticket stays closed: reopening starts a new one that points back at it.
            new = _new_ticket(con, a, doc["title"], note, [], doc.get("context") or {}, reopenedFrom=key)
            doc["reopenedAs"], doc["updatedAt"] = new["key"], at
            put_ticket(con, doc)
            return customer_view(new)
        if body.to == "escalated" and tracker and not (doc.get("escalation") or {}).get("reportRef"):
            hint = body.issueRef.strip()[:80]
            req = doc.get("requester") or {}
            try:
                tracker.post_json("/api/reports", {
                    "board": "support", "key": key, "title": doc["title"], "build": (doc.get("context") or {}).get("appVersion", ""),
                    "description": doc.get("description", "") + (f"\n\nSupport thinks this is {hint}." if hint else "") + (f"\n\n{note}" if note else ""),
                    "reporter": f"{req.get('name') or req.get('email') or 'customer'} ({doc['org']})"})
            except Exception as e:
                raise HTTPException(502, f"The tracker did not take the escalation: {e}")
            doc["escalation"] = {"at": at, "by": who, "issueRef": hint, "verdict": "", "verdictAt": "", "reportRef": f"support/{key}", "seen": ""}
        elif body.to == "escalated" and body.issueRef.strip():
            doc["escalation"] = {"at": at, "by": who, "issueRef": body.issueRef.strip()[:80], "verdict": "", "verdictAt": ""}
        if body.to == "resolved":
            doc["resolvedAt"] = at
        doc["status"], doc["updatedAt"] = body.to, at
        doc["history"].append({"at": at, "by": who, "role": a.role, "from": frm, "to": body.to, "note": note})
        if a.role == "customer" and note:
            doc["messages"].append({"id": uuid.uuid4().hex[:12], "at": at, "by": who, "role": "customer", "text": note,
                                    "screenshots": [], "visibility": "public"})
        put_ticket(con, doc)
    return view(doc, a)


OUTCOME_DRAFT = {"fixed": "Thanks for your patience. The problem you reported has been fixed.",
                 "as_speced": "We looked into this with the product team: it is working as designed."}


def sync_escalations() -> dict:
    """Read each escalated ticket's outcome from the tracker. A question becomes an internal note; a
    verdict (released once the internal issue is verified) becomes a draft that support sends."""
    con = connect()
    try:
        docs = [json.loads(r["doc"]) for r in con.execute("SELECT doc FROM tickets WHERE status='escalated'")]
    finally:
        con.close()
    out = {"checked": 0, "questions": 0, "verdicts": 0, "errors": []}
    for d in docs:
        esc = d.get("escalation") or {}
        if not esc.get("reportRef"):
            continue
        out["checked"] += 1
        try:
            r = tracker.get_json(f"/api/reports/{esc['reportRef']}")
        except Exception as e:
            out["errors"].append(f"{d['key']}: {e}")
            continue
        rel = r.get("release")
        with tx() as c2:
            doc = json.loads(c2.execute("SELECT doc FROM tickets WHERE key=?", (d["key"],)).fetchone()["doc"])
            esc = doc["escalation"]
            esc["issueRef"] = r.get("issue") or esc.get("issueRef", "")
            if rel and rel.get("at") != esc.get("seen"):
                esc["seen"] = rel["at"]
                at = now_iso()
                if rel["status"] == "more_info":
                    text, vis, tag = f"The product team asks: {rel.get('note', '')}", "internal", "tracker_question"
                    out["questions"] += 1
                else:
                    esc["verdict"], esc["verdictAt"] = rel["status"], rel["at"]
                    text, vis, tag = rel.get("note") or OUTCOME_DRAFT.get(rel["status"], ""), "draft", "verdict"
                    out["verdicts"] += 1
                doc["messages"].append({"id": uuid.uuid4().hex[:12], "at": at, "by": "tracker", "role": "agent", "text": text,
                                        "screenshots": [], "visibility": vis, "tag": tag})
                doc["updatedAt"] = at
            put_ticket(c2, doc)
    return out


@app.post("/api/sync")
def sync_now(a: Actor = Depends(actor)):
    if a.role not in ("support", "admin"):
        raise HTTPException(403, "Only support or an admin runs the tracker sync")
    if not tracker:
        raise HTTPException(409, "No tracker is connected (SUPPORT_TRACKER_URL)")
    return sync_escalations()


def _sync_forever() -> None:
    while True:
        threading.Event().wait(TRACKER_SYNC_INTERVAL)
        try:
            sync_escalations()
        except Exception:
            pass


@app.on_event("startup")
def _start_sync() -> None:
    if tracker and TRACKER_SYNC_INTERVAL > 0:
        threading.Thread(target=_sync_forever, daemon=True, name="tracker-sync").start()


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
    return FileResponse(path, headers={"Cache-Control": "private, max-age=31536000, immutable"})


def _known_uploads(con: sqlite3.Connection, ids: list[str]) -> list[str]:
    return [i for i in ids if con.execute("SELECT 1 FROM uploads WHERE id=?", (i,)).fetchone()]


@app.get("/widget.js")
def widget_js():
    return FileResponse(HERE / "widget.js", media_type="application/javascript")


@app.exception_handler(HTTPException)
async def _http_err(_: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.get("/healthz")
def healthz():
    return {"ok": True}


app.mount("/", StaticFiles(directory=HERE / "static", html=True), name="static")
