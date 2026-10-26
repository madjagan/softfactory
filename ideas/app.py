"""Software-factory ideas portal — a standalone FastAPI app over SQLite.

Customers submit and vote on the portal view; the team curates ideas on the product view; the
Ideas Agent links submissions and applies ledger-derived statuses through tools/ideas_cli.py.
One server for every org: a customer's org comes from their token, and every customer query is
filtered by it. Serve at any path prefix: the page uses relative URLs only.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("IDEAS_DATA", HERE / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "ideas.sqlite3"
TEAM_TOKEN = os.environ.get("IDEAS_TOKEN", "")  # product / agent / admin; empty = open (local dev)
BRAND = os.environ.get("IDEAS_BRAND", "Ideas")
PREFIX = os.environ.get("IDEAS_PREFIX", "IDEA")
SUB_PREFIX = os.environ.get("IDEAS_SUBMISSION_PREFIX", "IDR")
ORGS = [o.strip() for o in os.environ.get("IDEAS_ORGS", "").split(",") if o.strip()]
# One token per org (IDEAS_TOKEN_<ORG>). The token IS the org: a customer never names it.
ORG_BY_TOKEN = {t: o for o in ORGS if (t := os.environ.get("IDEAS_TOKEN_" + re.sub(r"\W", "_", o).upper(), ""))}

STATUSES = ["new", "under_review", "accepted", "in_development", "shipped", "declined", "already_built", "merged"]
SOURCES = ["portal", "support", "tracker", "internal"]
# What a submitter sees: the status of its idea, in plain words.
PLAIN = {None: "received", "new": "received", "under_review": "under review", "accepted": "planned",
         "in_development": "in development", "shipped": "shipped", "declined": "not planned",
         "already_built": "already available", "merged": "under review"}
DECISIONS = {"accepted", "declined", "already_built", "merged"}       # the owner's calls
LEDGER = {"accepted": "in_development", "in_development": "shipped"}  # facts read from the ledger
MOVES = {"product": {"new": {"under_review", *DECISIONS}, "under_review": set(DECISIONS), **{k: {v} for k, v in LEDGER.items()}},
         "agent": {"new": {"under_review"}, **{k: {v} for k, v in LEDGER.items()}}}
DEMAND = ["orgs", "people", "votes", "tickets", "issues", "submissions"]
RECOMMENDATIONS = ["accept", "decline", "already_built", "merge", "publish"]
FEATURE_ID = re.compile(r"^[A-Z][A-Z0-9]*-\d+$")
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


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
        CREATE TABLE IF NOT EXISTS submissions (
            key TEXT PRIMARY KEY, num INTEGER UNIQUE NOT NULL, source TEXT NOT NULL, source_ref TEXT, org TEXT,
            idea TEXT, updated_at TEXT NOT NULL, doc TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS submissions_org ON submissions(org);
        CREATE INDEX IF NOT EXISTS submissions_idea ON submissions(idea);
        CREATE TABLE IF NOT EXISTS ideas (
            key TEXT PRIMARY KEY, num INTEGER UNIQUE NOT NULL, status TEXT NOT NULL, updated_at TEXT NOT NULL, doc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS votes (
            idea TEXT NOT NULL, org TEXT NOT NULL, user TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY (idea, org, user));
        CREATE TABLE IF NOT EXISTS uploads (
            id TEXT PRIMARY KEY, filename TEXT, content_type TEXT, size INTEGER, org TEXT, created_at TEXT NOT NULL);
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


def put_submission(con: sqlite3.Connection, doc: dict) -> None:
    con.execute("INSERT OR REPLACE INTO submissions(key,num,source,source_ref,org,idea,updated_at,doc) VALUES (?,?,?,?,?,?,?,?)",
                (doc["key"], doc["num"], doc["source"], doc["sourceRef"], doc["org"], doc["idea"], doc["updatedAt"],
                 json.dumps(doc, ensure_ascii=False)))


def put_idea(con: sqlite3.Connection, doc: dict) -> None:
    con.execute("INSERT OR REPLACE INTO ideas(key,num,status,updated_at,doc) VALUES (?,?,?,?,?)",
                (doc["key"], doc["num"], doc["status"], doc["updatedAt"], json.dumps(doc, ensure_ascii=False)))


def get_submission(con: sqlite3.Connection, key: str, org: Optional[str] = None) -> dict:
    row = con.execute("SELECT doc FROM submissions WHERE key=?" + (" AND org=? AND source!='internal'" if org else ""),
                      (key, org) if org else (key,)).fetchone()
    if not row:
        raise HTTPException(404, f"{key} not found")
    return json.loads(row["doc"])


def get_idea(con: sqlite3.Connection, key: str) -> dict:
    row = con.execute("SELECT doc FROM ideas WHERE key=?", (key,)).fetchone()
    if not row:
        raise HTTPException(404, f"{key} not found")
    return json.loads(row["doc"])


def next_num(con: sqlite3.Connection, table: str) -> int:
    return (con.execute(f"SELECT MAX(num) AS m FROM {table}").fetchone()["m"] or 0) + 1


def submissions_of(con: sqlite3.Connection, idea: str) -> list[dict]:
    return [json.loads(r["doc"]) for r in con.execute("SELECT doc FROM submissions WHERE idea=? ORDER BY num", (idea,))]


def demand(con: sqlite3.Connection, idea: str) -> dict:
    """Computed on read, never stored. Orgs and people count everyone who asked or voted."""
    subs = submissions_of(con, idea)
    votes = con.execute("SELECT org, user FROM votes WHERE idea=?", (idea,)).fetchall()
    orgs = {s["org"] for s in subs if s["org"]} | {v["org"] for v in votes}
    people = {(s["org"] or "", (s["requester"] or "").lower()) for s in subs if s["requester"]} | {(v["org"], v["user"]) for v in votes}
    return {"orgs": len(orgs), "people": len(people), "votes": len(votes),
            "tickets": sum(s["source"] == "support" for s in subs), "issues": sum(s["source"] == "tracker" for s in subs),
            "submissions": len(subs)}


# ---------------- auth / actor ----------------
class Actor(BaseModel):
    name: str
    role: str  # customer | product | agent | admin
    org: Optional[str] = None


def actor(request: Request) -> Actor:
    given = request.headers.get("x-ideas-token") or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    org = ORG_BY_TOKEN.get(given) if given else None
    role = request.headers.get("x-role", "customer").lower()
    if role not in {"customer", "product", "agent", "admin"}:
        raise HTTPException(400, "X-Role must be customer, product, agent or admin")
    if role == "customer":
        if not org:
            raise HTTPException(401, "Missing or wrong org token")
    else:
        if org:
            raise HTTPException(403, "An org token only opens the portal")
        if TEAM_TOKEN and given != TEAM_TOKEN:
            raise HTTPException(401, "Missing or wrong token")
    name = request.headers.get("x-actor", "").strip()[:80] or ("agent" if role == "agent" else "")
    return Actor(name=name, role=role, org=org)


def team(a: Actor = Depends(actor)) -> Actor:
    if a.role == "customer":
        raise HTTPException(403, "The product view is for the team")
    return a


def customer(a: Actor = Depends(actor)) -> Actor:
    if a.role != "customer":
        raise HTTPException(403, "The portal is for customers (an org token)")
    return a


def need(a: Actor, *roles: str, what: str) -> None:
    if a.role != "admin" and a.role not in roles:
        raise HTTPException(403, f"Only {' or '.join(roles)} may {what}")


# ---------------- API ----------------
app = FastAPI(title=f"{BRAND} — ideas", docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.on_event("startup")
def _startup() -> None:
    init_db()


class NewSubmission(BaseModel):
    text: str = Field(min_length=3, max_length=5000)
    screenshots: list[str] = []


class TeamSubmission(NewSubmission):
    source: str = "internal"
    sourceRef: str = ""
    org: str = ""
    requester: str = ""


class Attach(BaseModel):
    idea: str
    note: str = ""


class Promote(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    problem: str = ""


class Edit(BaseModel):
    title: Optional[str] = None
    problem: Optional[str] = None
    featureId: Optional[str] = None
    publicTitle: Optional[str] = None
    publicDescription: Optional[str] = None


class Publish(BaseModel):
    title: str = ""
    description: str = ""
    statusNote: str = ""


class Transition(BaseModel):
    to: str
    note: str = ""
    prdRef: str = ""
    featureId: str = ""
    mergedInto: str = ""
    citation: str = ""
    statusNote: str = ""


class Recommend(BaseModel):
    kind: str
    note: str = ""
    featureId: str = ""
    mergedInto: str = ""


class Draft(BaseModel):
    to: str
    text: str = Field(min_length=3, max_length=5000)


def _hist(doc: dict, a: Actor, frm: str, to: str, note: str = "", **extra) -> None:
    doc["updatedAt"] = now_iso()
    doc.setdefault("history", []).append({"at": doc["updatedAt"], "by": a.name or a.role, "role": a.role, "from": frm, "to": to,
                                          "note": note, **extra})


@app.get("/api/meta")
def meta(a: Actor = Depends(actor)):
    out = {"brand": BRAND, "actor": a.model_dump(), "tokenRequired": bool(TEAM_TOKEN)}
    if a.role != "customer":
        out.update({"prefix": PREFIX, "submissionPrefix": SUB_PREFIX, "statuses": STATUSES, "sources": SOURCES, "orgs": ORGS,
                    "plain": {k or "": v for k, v in PLAIN.items()}, "recommendations": RECOMMENDATIONS, "demand": DEMAND})
    return out


# ---------------- portal (customers; every query filtered by the token's org) ----------------
def _status_of(con: sqlite3.Connection, idea_key: Optional[str]) -> tuple[Optional[dict], str]:
    if not idea_key:
        return None, PLAIN[None]
    idea = get_idea(con, idea_key)
    return idea, PLAIN[idea["status"]]


def portal_submission(con: sqlite3.Connection, s: dict) -> dict:
    idea, word = _status_of(con, s["idea"])
    notices = [{"text": d["text"], "sentAt": d["sentAt"]} for d in (idea or {}).get("drafts", []) if d["to"] == s["key"] and d.get("sentAt")]
    pub = idea.get("public") if idea else None
    return {"key": s["key"], "text": s["text"], "requester": s["requester"], "createdAt": s["createdAt"],
            "screenshots": s["screenshots"], "status": word, "notices": notices,
            "idea": {"key": idea["key"], "title": pub["title"]} if pub else None}


def portal_idea(con: sqlite3.Connection, i: dict, a: Actor) -> dict:
    n = con.execute("SELECT COUNT(*) AS n FROM votes WHERE idea=?", (i["key"],)).fetchone()["n"]
    mine = con.execute("SELECT 1 FROM votes WHERE idea=? AND org=? AND user=?", (i["key"], a.org, a.name.lower())).fetchone()
    p = i["public"]
    return {"key": i["key"], "title": p["title"], "description": p["description"], "status": PLAIN[i["status"]],
            "statusNote": p.get("statusNote", ""), "publishedAt": p["publishedAt"], "votes": n, "voted": bool(mine)}


def published(con: sqlite3.Connection) -> list[dict]:
    docs = [json.loads(r["doc"]) for r in con.execute("SELECT doc FROM ideas WHERE status!='merged' ORDER BY num DESC")]
    return [d for d in docs if d.get("public")]


@app.get("/api/portal/submissions")
def portal_list(a: Actor = Depends(customer)):
    con = connect()
    try:
        rows = con.execute("SELECT doc FROM submissions WHERE org=? AND source!='internal' ORDER BY num DESC", (a.org,))
        return [portal_submission(con, json.loads(r["doc"])) for r in rows]
    finally:
        con.close()


@app.get("/api/portal/submissions/{key}")
def portal_read(key: str, a: Actor = Depends(customer)):
    con = connect()
    try:
        return portal_submission(con, get_submission(con, key, a.org))
    finally:
        con.close()


@app.post("/api/portal/submissions", status_code=201)
def portal_submit(body: NewSubmission, a: Actor = Depends(customer)):
    if not a.name:
        raise HTTPException(400, "Say who you are (X-Actor header)")
    with tx() as con:
        doc = _new_submission(con, a, "portal", "", a.org, a.name, body)
        return portal_submission(con, doc)


@app.get("/api/portal/ideas")
def portal_ideas(a: Actor = Depends(customer)):
    con = connect()
    try:
        return [portal_idea(con, i, a) for i in published(con)]
    finally:
        con.close()


@app.post("/api/portal/ideas/{key}/vote")
def portal_vote(key: str, a: Actor = Depends(customer)):
    """One vote per customer user per published idea; voting again removes it."""
    if not a.name:
        raise HTTPException(400, "Say who you are (X-Actor header)")
    with tx() as con:
        i = next((d for d in published(con) if d["key"] == key), None)
        if i is None:
            raise HTTPException(404, f"{key} not found")
        user = a.name.lower()
        if con.execute("DELETE FROM votes WHERE idea=? AND org=? AND user=?", (key, a.org, user)).rowcount == 0:
            con.execute("INSERT INTO votes(idea,org,user,at) VALUES (?,?,?,?)", (key, a.org, user, now_iso()))
        return portal_idea(con, i, a)


# ---------------- product view (team) ----------------
def _new_submission(con: sqlite3.Connection, a: Actor, source: str, ref: str, org: Optional[str], requester: str, body: NewSubmission) -> dict:
    at = now_iso()
    num = next_num(con, "submissions")
    doc = {"key": f"{SUB_PREFIX}-{num}", "num": num, "source": source, "sourceRef": ref, "org": org or None,
           "requester": requester, "text": body.text.strip(), "screenshots": _known_uploads(con, body.screenshots, a.org),
           "idea": None, "createdAt": at, "updatedAt": at,
           "history": [{"at": at, "by": a.name or a.role, "role": a.role, "from": "", "to": "intake", "note": ""}]}
    put_submission(con, doc)
    return doc


@app.get("/api/submissions")
def list_submissions(source: Optional[str] = None, org: Optional[str] = None, idea: Optional[str] = None,
                     intake: bool = False, q: Optional[str] = None, a: Actor = Depends(team)):
    where, args = [], []
    for col, val in (("source", source), ("org", org), ("idea", idea)):
        if val:
            where.append(f"{col}=?"); args.append(val)
    if intake:
        where.append("idea IS NULL")
    sql = "SELECT doc FROM submissions" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY num DESC"
    con = connect()
    try:
        docs = [json.loads(r["doc"]) for r in con.execute(sql, args)]
    finally:
        con.close()
    if q:
        ql = q.lower()
        docs = [d for d in docs if ql in " ".join(str(d.get(k) or "") for k in ("key", "text", "sourceRef", "requester", "org")).lower()]
    return docs


@app.get("/api/submissions/{key}")
def read_submission(key: str, a: Actor = Depends(team)):
    con = connect()
    try:
        return get_submission(con, key)
    finally:
        con.close()


@app.post("/api/submissions", status_code=201)
def create_submission(body: TeamSubmission, a: Actor = Depends(team)):
    """Internal: staff log what they heard (product). Tracker / support: the agent gathers them, one per ref."""
    if body.source == "internal":
        need(a, "product", what="log an internal submission")
    elif body.source in ("tracker", "support"):
        need(a, "product", "agent", what=f"add a {body.source} submission")
        if not body.sourceRef.strip():
            raise HTTPException(400, f"A {body.source} submission needs its sourceRef")
    else:
        raise HTTPException(400, f"Unknown source for the team: {body.source}")
    if body.org and body.org not in ORGS:
        raise HTTPException(400, f"Unknown org: {body.org}")
    requester = body.requester.strip() or (a.name if body.source == "internal" else "")
    if not requester:
        raise HTTPException(400, "Say who asked (requester, or X-Actor for an internal submission)")
    with tx() as con:
        ref = body.sourceRef.strip()
        if ref and con.execute("SELECT 1 FROM submissions WHERE source=? AND source_ref=?", (body.source, ref)).fetchone():
            raise HTTPException(409, f"{ref} is already a submission")
        return _new_submission(con, a, body.source, ref, body.org, requester, body)


def _link(con: sqlite3.Connection, a: Actor, sub: dict, idea: dict, note: str) -> None:
    frm = sub["idea"]
    if frm:
        old = get_idea(con, frm)
        old["submissions"] = [k for k in old["submissions"] if k != sub["key"]]
        _hist(old, a, old["status"], old["status"], f"{sub['key']} moved to {idea['key']}")
        put_idea(con, old)
    sub["idea"] = idea["key"]
    _hist(sub, a, frm or "intake", idea["key"], note)
    put_submission(con, sub)
    idea["submissions"] = [*idea["submissions"], sub["key"]]
    _hist(idea, a, idea["status"], idea["status"], f"{sub['key']} attached" + (f": {note}" if note else ""))
    put_idea(con, idea)


@app.post("/api/submissions/{key}/attach")
def attach(key: str, body: Attach, a: Actor = Depends(team)):
    need(a, "product", "agent", what="attach a submission")
    with tx() as con:
        sub = get_submission(con, key)
        if sub["idea"] == body.idea:
            raise HTTPException(409, f"{key} is already on {body.idea}")
        if sub["idea"] and a.role == "agent":
            raise HTTPException(409, f"{key} is on {sub['idea']}; moving it is the product team's call")
        idea = get_idea(con, body.idea)
        if idea["status"] == "merged":
            raise HTTPException(409, f"{body.idea} is merged into {idea['mergedInto']}")
        _link(con, a, sub, idea, body.note.strip())
        return {"submission": sub, "idea": idea}


@app.post("/api/submissions/{key}/promote", status_code=201)
def promote(key: str, body: Promote, a: Actor = Depends(team)):
    need(a, "product", "agent", what="promote a submission")
    with tx() as con:
        sub = get_submission(con, key)
        if sub["idea"]:
            raise HTTPException(409, f"{key} is already on {sub['idea']}")
        at = now_iso()
        num = next_num(con, "ideas")
        idea = {"key": f"{PREFIX}-{num}", "num": num, "title": body.title.strip(), "problem": body.problem.strip(), "status": "new",
                "prdRef": "", "featureId": "", "mergedInto": "", "submissions": [], "public": None, "publicDraft": None,
                "drafts": [], "recommendations": [], "createdAt": at, "updatedAt": at,
                "history": [{"at": at, "by": a.name or a.role, "role": a.role, "from": "", "to": "new", "note": f"Promoted from {key}"}]}
        _link(con, a, sub, idea, "")
        return idea


def _full(con: sqlite3.Connection, idea: dict) -> dict:
    voters = [dict(r) for r in con.execute("SELECT org, user, at FROM votes WHERE idea=? ORDER BY at", (idea["key"],))]
    return {**idea, "demand": demand(con, idea["key"]), "voters": voters}


@app.get("/api/ideas")
def list_ideas(status: Optional[str] = None, sort: str = "orgs", a: Actor = Depends(team)):
    if sort not in DEMAND:
        raise HTTPException(400, f"Sort by one of {DEMAND}")
    con = connect()
    try:
        where, args = "", []
        if status:
            vals = status.split(",")
            where, args = f" WHERE status IN ({','.join('?' * len(vals))})", vals
        rows = [{**(d := json.loads(r["doc"])), "demand": demand(con, d["key"])} for r in con.execute("SELECT doc FROM ideas" + where + " ORDER BY num DESC", args)]
    finally:
        con.close()
    return sorted(rows, key=lambda d: -d["demand"][sort])


@app.get("/api/ideas/{key}")
def read_idea(key: str, a: Actor = Depends(team)):
    con = connect()
    try:
        return {**_full(con, get_idea(con, key)), "submissionDocs": submissions_of(con, key)}
    finally:
        con.close()


@app.post("/api/ideas/{key}/edit")
def edit_idea(key: str, body: Edit, a: Actor = Depends(team)):
    """The team's words: title, problem, the draft public text, the feature id. Publishing is separate."""
    need(a, "product", "agent", what="edit an idea")
    if body.featureId and not FEATURE_ID.match(body.featureId):
        raise HTTPException(400, f"featureId must look like AREA-NN: {body.featureId}")
    with tx() as con:
        idea = get_idea(con, key)
        changed = []
        for f in ("title", "problem", "featureId"):
            v = getattr(body, f)
            if v is not None and v.strip() != idea.get(f):
                idea[f] = v.strip(); changed.append(f)
        if body.publicTitle is not None or body.publicDescription is not None:
            d = idea.get("publicDraft") or {"title": "", "description": ""}
            idea["publicDraft"] = {"title": (body.publicTitle if body.publicTitle is not None else d["title"]).strip(),
                                   "description": (body.publicDescription if body.publicDescription is not None else d["description"]).strip()}
            changed.append("publicDraft")
        if not changed:
            raise HTTPException(400, "Nothing to change")
        _hist(idea, a, idea["status"], idea["status"], "Edited " + ", ".join(changed))
        put_idea(con, idea)
        return idea


def _leaks(con: sqlite3.Connection, idea: dict, texts: list[str]) -> Optional[str]:
    """Public text carries no customer names, orgs or wording."""
    blob = " ".join(texts).lower()
    for s in submissions_of(con, idea["key"]):
        for word, what in ((s["requester"], "a requester's name"), (s["org"], "an org")):
            if word and len(word) >= 3 and re.search(rf"\b{re.escape(word.lower())}\b", blob):
                return f"Public text names {what} ({s['key']})"
        if len(s["text"]) >= 12 and s["text"].lower() in blob:
            return f"Public text quotes {s['key']} word for word"
    return None


@app.post("/api/ideas/{key}/publish")
def publish(key: str, body: Publish, a: Actor = Depends(team)):
    need(a, "product", what="publish an idea")
    with tx() as con:
        idea = get_idea(con, key)
        if idea["status"] == "merged":
            raise HTTPException(409, f"{key} is merged into {idea['mergedInto']}")
        d = idea.get("publicDraft") or {}
        title, desc = body.title.strip() or d.get("title", ""), body.description.strip() or d.get("description", "")
        if not title or not desc:
            raise HTTPException(400, "A public title and description are needed (or a drafted one)")
        prev = idea.get("public") or {}
        note = body.statusNote.strip() or prev.get("statusNote", "")
        leak = _leaks(con, idea, [title, desc, note])
        if leak:
            raise HTTPException(400, leak)
        idea["public"] = {"title": title, "description": desc, "publishedAt": prev.get("publishedAt") or now_iso(), "statusNote": note}
        _hist(idea, a, idea["status"], idea["status"], "Republished" if prev else "Published")
        put_idea(con, idea)
        return idea


@app.post("/api/ideas/{key}/transition")
def transition(key: str, body: Transition, a: Actor = Depends(team)):
    if body.to not in STATUSES:
        raise HTTPException(400, f"Unknown status: {body.to}")
    with tx() as con:
        idea = get_idea(con, key)
        frm = idea["status"]
        allowed = MOVES.get(a.role)
        if allowed is not None and body.to not in allowed.get(frm, set()):
            raise HTTPException(409, f"A {a.role} cannot move {key} from {frm} to {body.to}")
        extra = {}
        if body.to == "under_review" and not (idea["problem"] and (idea.get("publicDraft") or {}).get("title") and idea["publicDraft"].get("description")):
            raise HTTPException(400, "Under review needs the problem statement and a drafted public title and description")
        if body.to == "accepted":
            if not body.prdRef.strip():
                raise HTTPException(400, "Accepting records the PRD § that /create-feature produced (prdRef)")
            idea["prdRef"] = body.prdRef.strip().lstrip("§").strip()
            if body.featureId:
                idea["featureId"] = body.featureId.strip()
        if body.to == "already_built":
            if not FEATURE_ID.match(body.featureId.strip()):
                raise HTTPException(400, "Already built points at the feature that has it (featureId AREA-NN)")
            idea["featureId"] = body.featureId.strip()
        if body.to == "declined" and not body.note.strip():
            raise HTTPException(400, "Say why it is declined (note)")
        if body.to in ("declined", "already_built") and idea.get("public"):
            if body.to == "declined" and not body.statusNote.strip():
                raise HTTPException(400, "This idea is published: give customers the reason (statusNote)")
            if body.statusNote.strip():
                leak = _leaks(con, idea, [body.statusNote])
                if leak:
                    raise HTTPException(400, leak)
                idea["public"]["statusNote"] = body.statusNote.strip()
        if body.to in LEDGER.values():
            if not body.citation.strip():
                raise HTTPException(400, f"{body.to} is read from the ledger: cite the plan row or release entry (citation)")
            extra["citation"] = body.citation.strip()
        if body.to == "merged":
            target = get_idea(con, body.mergedInto)
            if target["key"] == key or target["status"] == "merged":
                raise HTTPException(409, "Merge into another idea that is not itself merged")
            for sub in submissions_of(con, key):
                sub["idea"] = target["key"]
                _hist(sub, a, key, target["key"], f"{key} merged into {target['key']}")
                put_submission(con, sub)
            target["submissions"] = [*target["submissions"], *idea["submissions"]]
            con.execute("INSERT OR IGNORE INTO votes(idea,org,user,at) SELECT ?, org, user, at FROM votes WHERE idea=?", (target["key"], key))
            con.execute("DELETE FROM votes WHERE idea=?", (key,))
            _hist(target, a, target["status"], target["status"], f"{key} merged in ({len(idea['submissions'])} submission(s))")
            put_idea(con, target)
            idea["mergedInto"], idea["submissions"] = target["key"], []
        idea["status"] = body.to
        _hist(idea, a, frm, body.to, body.note.strip(), **extra)
        put_idea(con, idea)
        return idea


@app.post("/api/ideas/{key}/recommend")
def recommend(key: str, body: Recommend, a: Actor = Depends(team)):
    """The agent's recommendation for a product decision. It changes nothing but the record."""
    if body.kind not in RECOMMENDATIONS:
        raise HTTPException(400, f"Unknown recommendation: {body.kind}")
    if body.kind == "already_built" and not FEATURE_ID.match(body.featureId):
        raise HTTPException(400, "Already built points at a feature id (AREA-NN)")
    with tx() as con:
        idea = get_idea(con, key)
        if body.kind == "merge" and (body.mergedInto == key or get_idea(con, body.mergedInto)["status"] == "merged"):
            raise HTTPException(409, "Recommend a merge into another idea that is not itself merged")
        rec = {"at": now_iso(), "by": a.name or a.role, "kind": body.kind, "note": body.note.strip(),
               **({"featureId": body.featureId} if body.featureId else {}), **({"mergedInto": body.mergedInto} if body.mergedInto else {})}
        idea.setdefault("recommendations", []).append(rec)
        _hist(idea, a, idea["status"], idea["status"], f"Recommends {body.kind}" + (f": {body.note.strip()}" if body.note.strip() else ""))
        put_idea(con, idea)
        return idea


@app.post("/api/ideas/{key}/drafts", status_code=201)
def add_draft(key: str, body: Draft, a: Actor = Depends(team)):
    """A notice for one linked submission, or a support draft for one linked ticket. Product sends it."""
    need(a, "product", "agent", what="draft a notice")
    with tx() as con:
        idea = get_idea(con, key)
        targets = {s["key"] for s in submissions_of(con, key)} | {s["sourceRef"] for s in submissions_of(con, key) if s["source"] == "support"}
        if body.to not in targets:
            raise HTTPException(400, f"{body.to} is not a submission or ticket linked to {key}")
        idea.setdefault("drafts", []).append({"to": body.to, "text": body.text.strip(), "sentAt": None, "by": a.name or a.role, "at": now_iso()})
        _hist(idea, a, idea["status"], idea["status"], f"Drafted a notice to {body.to}")
        put_idea(con, idea)
        return idea


@app.post("/api/ideas/{key}/drafts/{n}/send")
def send_draft(key: str, n: int, a: Actor = Depends(team)):
    need(a, "product", what="send a notice")
    with tx() as con:
        idea = get_idea(con, key)
        drafts = idea.get("drafts") or []
        if not 0 <= n < len(drafts):
            raise HTTPException(404, f"{key} has no draft {n}")
        if drafts[n]["sentAt"]:
            raise HTTPException(409, "Already sent")
        drafts[n]["sentAt"] = now_iso()
        drafts[n]["sentBy"] = a.name or a.role
        _hist(idea, a, idea["status"], idea["status"], f"Sent the notice to {drafts[n]['to']}")
        put_idea(con, idea)
        return idea


# ---------------- uploads (tagged with the uploader's org; a customer reads only their own) ----------------
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
        con.execute("INSERT INTO uploads(id,filename,content_type,size,org,created_at) VALUES (?,?,?,?,?,?)",
                    (uid, file.filename or uid, ctype, len(data), a.org, now_iso()))
    return {"id": uid, "url": f"uploads/{uid}", "size": len(data), "contentType": ctype}


@app.get("/uploads/{uid}")
def serve_upload(uid: str, a: Actor = Depends(actor)):
    if "/" in uid or ".." in uid:
        raise HTTPException(404)
    con = connect()
    try:
        row = con.execute("SELECT org FROM uploads WHERE id=?", (uid,)).fetchone()
    finally:
        con.close()
    path = UPLOAD_DIR / uid
    if not row or not path.is_file() or (a.role == "customer" and row["org"] != a.org):
        raise HTTPException(404)
    return FileResponse(path, headers={"Cache-Control": "private, max-age=31536000, immutable"})


def _known_uploads(con: sqlite3.Connection, ids: list[str], org: Optional[str]) -> list[str]:
    out = []
    for i in ids:
        row = con.execute("SELECT org FROM uploads WHERE id=?", (i,)).fetchone()
        if row and (org is None or row["org"] == org):
            out.append(i)
    return out


@app.exception_handler(HTTPException)
async def _http_err(_: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.get("/healthz")
def healthz():
    return {"ok": True}


app.mount("/", StaticFiles(directory=HERE / "static", html=True), name="static")
