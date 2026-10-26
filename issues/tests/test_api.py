"""Issue tracker API: the state machine, actors, uploads and numbering."""
import importlib
import io
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8cfc000000301010018dd8db00000000049454e44ae426082")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ISSUES_DATA", str(tmp_path))
    monkeypatch.delenv("ISSUES_TOKEN", raising=False)
    import issues.app as appmod
    importlib.reload(appmod)
    with TestClient(appmod.app) as c:
        yield c


def hdr(name="Priya", role="tester"):
    return {"X-Actor": name, "X-Role": role}


def file_issue(c, **over):
    body = {"title": "Cancel does nothing", "description": "steps", "module": "ui", "kind": "bug", "severity": "medium"}
    body.update(over)
    r = c.post("/api/issues", json=body, headers=hdr())
    assert r.status_code == 201, r.text
    return r.json()


def test_numbering_starts_at_501_and_increments(client):
    a = file_issue(client)
    b = file_issue(client, title="Second one")
    assert (a["key"], a["num"]) == ("IS-501", 501)
    assert (b["key"], b["num"]) == ("IS-502", 502)
    assert a["status"] == "new" and a["reporter"] == "Priya"


def test_filing_needs_a_name(client):
    r = client.post("/api/issues", json={"title": "No name given"}, headers={"X-Role": "tester"})
    assert r.status_code == 400


def test_tester_cannot_give_verdicts_but_agent_can(client):
    k = file_issue(client)["key"]
    r = client.post(f"/api/issues/{k}/transition", json={"to": "fixed"}, headers=hdr())
    assert r.status_code == 409
    r = client.post(f"/api/issues/{k}/transition", json={"to": "fixed", "agent": {"rootCause": "x", "fixProposed": "p", "fix": "y", "tests": "t", "humanTests": "h"}}, headers=hdr("agent", "agent"))
    assert r.status_code == 200
    doc = r.json()
    assert doc["status"] == "fixed" and doc["agent"]["processedAt"] and doc["agent"]["fix"] == "y" and doc["agent"]["fixProposed"] == "p"
    assert doc["history"][-1] == {**doc["history"][-1], "by": "agent", "from": "new", "to": "fixed"}


def test_the_old_claude_role_is_refused(client):
    k = file_issue(client)["key"]
    r = client.post(f"/api/issues/{k}/transition", json={"to": "fixed"}, headers=hdr("claude", "claude"))
    assert r.status_code == 400


def test_startup_carries_an_old_claude_board_over_to_agent(client):
    import issues.app as appmod
    k = file_issue(client)["key"]
    with appmod.tx() as con:
        doc = appmod.get_issue(con, k)
        doc.pop("agent")
        doc["claude"] = {"fix": "old fix", "processedAt": "2026-01-01T00:00:00.000Z"}
        doc["history"].append({"at": "2026-01-01T00:00:00.000Z", "by": "claude", "from": "new", "to": "fixed", "note": ""})
        doc["comments"].append({"at": "2026-01-01T00:00:00.000Z", "by": "claude", "text": "done", "screenshots": []})
        appmod.put_issue(con, doc)
    appmod.init_db()
    doc = client.get(f"/api/issues/{k}", headers=hdr()).json()
    assert "claude" not in doc and doc["agent"]["fix"] == "old fix"
    assert doc["history"][-1]["by"] == "agent" and doc["comments"][-1]["by"] == "agent"


def test_full_happy_path_to_closed(client):
    k = file_issue(client)["key"]
    client.post(f"/api/issues/{k}/transition", json={"to": "fixed", "agent": {"fix": "done"}}, headers=hdr("agent", "agent"))
    assert client.post(f"/api/issues/{k}/transition", json={"to": "verified"}, headers=hdr()).json()["verification"]["by"] == "Priya"
    assert client.post(f"/api/issues/{k}/transition", json={"to": "closed"}, headers=hdr()).json()["status"] == "closed"


def test_more_info_needs_an_answer_to_reopen(client):
    k = file_issue(client)["key"]
    client.post(f"/api/issues/{k}/transition", json={"to": "more_info", "agent": {"infoNeeded": "which login?"}}, headers=hdr("agent", "agent"))
    r = client.post(f"/api/issues/{k}/transition", json={"to": "open"}, headers=hdr())
    assert r.status_code == 400
    r = client.post(f"/api/issues/{k}/transition", json={"to": "open", "note": "Logged in as Layla"}, headers=hdr())
    assert r.status_code == 200 and r.json()["comments"][-1]["text"] == "Logged in as Layla"
    assert client.post(f"/api/issues/{k}/transition", json={"to": "verified"}, headers=hdr()).status_code == 409


def test_agent_cannot_verify_or_close(client):
    k = file_issue(client)["key"]
    client.post(f"/api/issues/{k}/transition", json={"to": "fixed"}, headers=hdr("agent", "agent"))
    assert client.post(f"/api/issues/{k}/transition", json={"to": "verified"}, headers=hdr("agent", "agent")).status_code == 409


def test_agent_may_restate_its_own_verdict_but_not_a_testers_status(client):
    # IS-424 — a duplicate-of pointed at an issues-log number; re-pointing it at the tracker key
    # is the same verdict with revised fields, not a move.
    k = file_issue(client)["key"]
    client.post(f"/api/issues/{k}/transition", json={"to": "duplicate", "agent": {"duplicateOf": "#184"}}, headers=hdr("agent", "agent"))
    r = client.post(f"/api/issues/{k}/transition", json={"to": "duplicate", "agent": {"duplicateOf": "IS-345"}}, headers=hdr("agent", "agent"))
    assert r.status_code == 200 and r.json()["status"] == "duplicate" and r.json()["agent"]["duplicateOf"] == "IS-345"
    assert r.json()["history"][-1] == {**r.json()["history"][-1], "from": "duplicate", "to": "duplicate"}
    # Verified is a tester's status: the agent may not restate it, and a tester may not restate a verdict.
    client.post(f"/api/issues/{k}/transition", json={"to": "verified"}, headers=hdr())
    assert client.post(f"/api/issues/{k}/transition", json={"to": "verified"}, headers=hdr("agent", "agent")).status_code == 409
    assert client.post(f"/api/issues/{k}/transition", json={"to": "verified"}, headers=hdr()).status_code == 409


def test_admin_may_set_any_status(client):
    k = file_issue(client)["key"]
    assert client.post(f"/api/issues/{k}/transition", json={"to": "closed"}, headers=hdr("Owner", "admin")).json()["status"] == "closed"


def test_upload_then_attach_only_known_ids(client):
    r = client.post("/api/uploads", files={"file": ("shot.png", io.BytesIO(PNG), "image/png")}, headers=hdr())
    assert r.status_code == 201
    uid = r.json()["id"]
    assert client.get(f"/uploads/{uid}").status_code == 200
    doc = file_issue(client, screenshots=[uid, "not-a-real-id.png"])
    assert doc["screenshots"] == [uid]
    r = client.post("/api/uploads", files={"file": ("x.txt", io.BytesIO(b"hi"), "text/plain")}, headers=hdr())
    assert r.status_code == 415


def test_token_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("ISSUES_DATA", str(tmp_path))
    monkeypatch.setenv("ISSUES_TOKEN", "s3cret")
    import issues.app as appmod
    importlib.reload(appmod)
    with TestClient(appmod.app) as c:
        assert c.get("/api/issues").status_code == 401
        assert c.get("/api/issues", headers={"Authorization": "Bearer s3cret"}).status_code == 200
        assert c.get("/api/issues", headers={"X-Issues-Token": "s3cret"}).status_code == 200
        assert c.get("/api/issues", headers={"X-Issues-Token": "wrong", "Authorization": "Basic abc"}).status_code == 401
        assert c.get("/healthz").status_code == 200


def test_list_filters_and_stats(client):
    file_issue(client, module="api")
    file_issue(client, module="data", kind="enhancement")
    assert [i["module"] for i in client.get("/api/issues?module=data", headers=hdr()).json()] == ["data"]
    assert client.get("/api/issues?q=cancel", headers=hdr()).json()
    assert client.get("/api/stats", headers=hdr()).json()["byStatus"]["new"] == 2


def test_a_second_board_carries_its_own_brand_and_key_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv("ISSUES_DATA", str(tmp_path))
    monkeypatch.delenv("ISSUES_TOKEN", raising=False)
    monkeypatch.setenv("ISSUES_BRAND", "Customer · Feedback")
    monkeypatch.setenv("ISSUES_PREFIX", "FB")
    import issues.app as appmod
    importlib.reload(appmod)
    with TestClient(appmod.app) as c:
        meta = c.get("/api/meta", headers=hdr()).json()
        assert meta["brand"] == "Customer · Feedback" and meta["prefix"] == "FB"
        doc = c.post("/api/issues", json={"title": "Customer report"}, headers=hdr("Customer")).json()
        assert doc["key"] == "FB-501" and doc["num"] == 501
        assert c.get("/api/stats", headers=hdr()).json()["total"] == 1


def test_a_board_can_refuse_the_admin_role(tmp_path, monkeypatch):
    monkeypatch.setenv("ISSUES_DATA", str(tmp_path))
    monkeypatch.delenv("ISSUES_TOKEN", raising=False)
    monkeypatch.setenv("ISSUES_ROLES", "tester,agent")
    import issues.app as appmod
    importlib.reload(appmod)
    with TestClient(appmod.app) as c:
        assert c.get("/api/meta", headers=hdr()).json()["roles"] == ["tester"]
        assert c.get("/api/issues", headers=hdr("X", "admin")).status_code == 403
        k = c.post("/api/issues", json={"title": "Customer report"}, headers=hdr("Customer")).json()["key"]
        assert c.post(f"/api/issues/{k}/transition", json={"to": "closed"}, headers=hdr("X", "admin")).status_code == 403
        assert c.post(f"/api/issues/{k}/transition", json={"to": "fixed"}, headers=hdr("agent", "agent")).status_code == 200


# ---------------- the customer boards and triage ----------------
def _clear_board_env():
    for k in [k for k in os.environ if k.startswith("FEEDBACK_")] + ["ISSUES_TOKEN", "ISSUES_BRAND", "ISSUES_PREFIX", "ISSUES_ROLES", "ISSUES_CUSTOMER"]:
        os.environ.pop(k, None)


def _load_board(name: str, data_dir, env: dict):
    """A second, independent copy of the app module with its own config and database."""
    import importlib.util
    _clear_board_env()
    os.environ["ISSUES_DATA"] = str(data_dir)
    os.environ.update(env)
    spec = importlib.util.spec_from_file_location(name, ROOT / "issues" / "app.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod          # pydantic resolves the models' forward references through here
    spec.loader.exec_module(mod)
    return mod


class FakeRemote:
    """The customer board reached through its TestClient, the way Remote reaches it over HTTP."""

    def __init__(self, client, actor, token=""):
        self.c, self.h = client, {"X-Role": "agent", "X-Actor": actor, **({"X-Issues-Token": token} if token else {})}

    def get_json(self, path):
        r = self.c.get(path, headers=self.h); assert r.status_code == 200, r.text; return r.json()

    def post_json(self, path, body):
        import urllib.error
        r = self.c.post(path, json=body, headers=self.h)
        if r.status_code >= 400:
            raise urllib.error.HTTPError(path, r.status_code, r.text, {}, io.BytesIO(r.content))
        return r.json()

    def get_bytes(self, path):
        r = self.c.get(path); assert r.status_code == 200; return r.content


@pytest.fixture()
def boards(tmp_path):
    customer = _load_board("issues_app_customer", tmp_path / "fb", {"ISSUES_PREFIX": "FB", "ISSUES_ROLES": "tester,agent", "ISSUES_CUSTOMER": "1"})
    internal = _load_board("issues_app_internal", tmp_path / "tp", {})
    with TestClient(customer.app) as fb, TestClient(internal.app) as tp:
        yield customer, fb, internal, tp


def test_a_customer_board_withholds_the_analysis(boards):
    customer, fb, *_ = boards
    k = file_issue(fb)["key"]
    r = fb.post(f"/api/issues/{k}/transition", json={"to": "fixed", "agent": {"rootCause": "secret", "fix": "y"}}, headers=hdr("agent", "agent"))
    assert r.status_code == 200 and r.json()["agent"] == {}
    assert fb.get(f"/api/issues/{k}", headers=hdr()).json()["agent"] == {}
    assert fb.get("/api/issues?full=true", headers=hdr()).json()[0]["agent"] == {}
    assert fb.get("/api/issues", headers=hdr()).json()[0]["processed"] is False
    assert fb.get("/api/meta", headers=hdr()).json()["customer"] is True
    assert "secret" not in fb.get(f"/api/issues/{k}", headers=hdr()).text


@pytest.fixture()
def tri(tmp_path):
    """Two customer boards (acme, globex), each its own module, database, token and prefix, and the
    internal board that triages both. Sync reaches each board through its TestClient."""
    from types import SimpleNamespace
    cust = {"ISSUES_ROLES": "tester,agent", "ISSUES_CUSTOMER": "1"}
    acme = _load_board("issues_app_acme", tmp_path / "acme", {**cust, "ISSUES_PREFIX": "ACME", "ISSUES_TOKEN": "a-tok"})
    globex = _load_board("issues_app_globex", tmp_path / "globex", {**cust, "ISSUES_PREFIX": "GLX", "ISSUES_TOKEN": "g-tok"})
    internal = _load_board("issues_app_tri", tmp_path / "tp", {
        "FEEDBACK_BOARDS": "acme=http://acme-feedback:3002/, globex=http://globex-feedback:3002",
        "FEEDBACK_TOKEN_ACME": "a-tok", "FEEDBACK_TOKEN_GLOBEX": "g-tok", "FEEDBACK_SYNC_INTERVAL": "0"})
    try:
        with TestClient(acme.app) as a, TestClient(globex.app) as g, TestClient(internal.app) as tp:
            real = dict(internal.REMOTES)
            internal.REMOTES = {"acme": FakeRemote(a, internal.PUSH_ACTOR, real["acme"].token),
                                "globex": FakeRemote(g, internal.PUSH_ACTOR, real["globex"].token)}
            yield SimpleNamespace(acme=acme, globex=globex, internal=internal, a=a, g=g, tp=tp, real=real,
                                  ah=lambda n="Alice": {**hdr(n), "X-Issues-Token": "a-tok"},
                                  gh=lambda n="Bob": {**hdr(n), "X-Issues-Token": "g-tok"})
    finally:
        _clear_board_env()


AGENT = hdr("Issue Agent", "agent")


def _file(c, h, title, **over):
    r = c.post("/api/issues", json={"title": title, "description": "steps", "module": "api", **over}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _sync(t):
    r = t.tp.post("/api/sync", headers=AGENT)
    assert r.status_code == 200, r.text
    return r.json()


def _shot(c, h):
    return c.post("/api/uploads", files={"file": ("s.png", io.BytesIO(PNG), "image/png")}, headers=h).json()["id"]


def _two_linked(t):
    """acme/ACME-501 promoted to IS-501, globex/GLX-501 attached to it."""
    _file(t.a, t.ah(), "Invoice is blank")
    _file(t.g, t.gh(), "Blank invoice in August")
    _sync(t)
    assert t.tp.post("/api/reports/acme/ACME-501/promote", json={}, headers=AGENT).status_code == 201
    assert t.tp.post("/api/reports/globex/GLX-501/attach", json={"to": "IS-501"}, headers=AGENT).status_code == 200


def _fix_and_verify(t, key="IS-501"):
    t.tp.post(f"/api/issues/{key}/transition", json={"to": "fixed", "agent": {"rootCause": "secret cause", "fix": "f"}}, headers=AGENT)
    assert t.tp.post(f"/api/issues/{key}/transition", json={"to": "verified", "note": "checked on build 510"}, headers=hdr("Priya")).status_code == 200


def test_g1_each_customer_board_is_its_own_deployment_database_token_and_prefix(tri):
    t = tri
    assert {n: (r.base, r.token) for n, r in t.real.items()} == {"acme": ("http://acme-feedback:3002", "a-tok"), "globex": ("http://globex-feedback:3002", "g-tok")}
    assert t.acme.DB_PATH != t.globex.DB_PATH != t.internal.DB_PATH
    assert t.a.get("/api/issues", headers={**hdr(), "X-Issues-Token": "g-tok"}).status_code == 401
    assert _file(t.a, t.ah(), "Acme thing")["key"] == "ACME-501" and _file(t.g, t.gh(), "Globex thing")["key"] == "GLX-501"
    assert t.tp.get("/api/meta", headers=hdr()).json()["boards"] == ["acme", "globex"]
    rep = _sync(t)
    assert rep["acme"]["intake"] == ["acme/ACME-501"] and rep["globex"]["intake"] == ["globex/GLX-501"]
    # deploy: one internal service that names every board, one status-only feedback service per customer
    compose = (ROOT / "deploy" / "docker-compose.issues.yml").read_text()
    assert compose.count("ISSUES_CUSTOMER=1") == 2 and "FEEDBACK_BOARDS=" in compose and "FEEDBACK_SYNC_URL" not in compose
    for n in ("acme", "globex"):
        assert f"feedback-{n}:" in compose and f"FEEDBACK_TOKEN_{n.upper()}" in compose and f"{{{{slug}}}}_feedback_{n}_data" in compose


def test_g1_one_board_down_does_not_hold_up_the_others(tri):
    t = tri
    _file(t.g, t.gh(), "Globex thing")
    t.internal.REMOTES["acme"] = t.internal.Remote("http://127.0.0.1:9", "")
    rep = _sync(t)
    assert "error" in rep["acme"] and rep["globex"]["intake"] == ["globex/GLX-501"]


def test_g3_sync_creates_no_issues_and_g4_promote_keeps_the_customers_words(tri):
    t = tri
    up = _shot(t.a, t.ah())
    _file(t.a, t.ah(), "Invoice is blank", description="open August", screenshots=[up], severity="high")
    t.a.post("/api/issues/ACME-501/comments", json={"text": "also on Safari"}, headers=t.ah())
    rep = _sync(t)
    assert rep["acme"]["intake"] == ["acme/ACME-501"] and rep["acme"]["comments"] == 1
    assert t.tp.get("/api/issues", headers=hdr()).json() == []
    assert t.tp.get("/api/stats", headers=hdr()).json() == {"byStatus": {}, "total": 0, "intake": 1, "flagged": 0}
    [r] = t.tp.get("/api/reports?intake=true", headers=hdr()).json()
    assert (r["board"], r["key"], r["issue"], r["reporter"], r["customerStatus"]) == ("acme", "ACME-501", None, "Alice", "new")
    assert r["screenshots"] == [up] and t.tp.get(f"/uploads/{up}").status_code == 200 and r["comments"][0]["text"] == "also on Safari"
    assert _sync(t)["acme"] == {"intake": [], "comments": 0, "customerMoves": 0, "pushed": [], "skipped": []}
    # promote: the first report becomes the issue
    assert t.tp.post("/api/reports/acme/ACME-501/promote", json={}, headers=hdr()).status_code == 403
    r = t.tp.post("/api/reports/acme/ACME-501/promote", json={}, headers=AGENT)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert (doc["key"], doc["title"], doc["description"], doc["screenshots"], doc["reporter"], doc["severity"], doc["source"]) == \
        ("IS-501", "Invoice is blank", "open August", [up], "Alice", "high", "customer")
    assert doc["reports"] == ["acme/ACME-501"] and doc["customerReports"][0]["issue"] == "IS-501"
    assert t.tp.get("/api/reports?intake=true", headers=hdr()).json() == []
    assert t.tp.post("/api/reports/acme/ACME-501/promote", json={}, headers=AGENT).status_code == 409
    assert _sync(t)["acme"]["intake"] == [] and len(t.tp.get("/api/issues", headers=hdr()).json()) == 1


def test_g4_attach_links_a_report_to_an_existing_issue(tri):
    t = tri
    k = file_issue(t.tp)["key"]
    other = file_issue(t.tp, title="Something else")["key"]
    _file(t.g, t.gh(), "Cancel does nothing for me")
    _sync(t)
    r = t.tp.post("/api/reports/globex/GLX-501/attach", json={"to": k}, headers=AGENT)
    assert r.status_code == 200, r.text
    assert r.json()["reports"] == ["globex/GLX-501"] and "Attached globex/GLX-501" in r.json()["history"][-1]["note"]
    assert t.tp.get("/api/reports/globex/GLX-501", headers=hdr()).json()["issue"] == k
    assert t.tp.post("/api/reports/globex/GLX-501/attach", json={"to": other}, headers=AGENT).status_code == 409
    assert t.tp.post("/api/reports/globex/GLX-501/attach", json={"to": k}, headers=AGENT).json()["reports"] == ["globex/GLX-501"]
    assert t.tp.post("/api/reports/globex/GLX-501/attach", json={"to": "IS-999"}, headers=AGENT).status_code == 404
    assert t.tp.post("/api/reports/globex/GLX-501/attach", json={"to": k}, headers=hdr()).status_code == 403


def test_g5_the_internal_issue_lists_every_linked_report(tri):
    t = tri
    up = _shot(t.g, t.gh())
    _file(t.a, t.ah(), "Invoice is blank")
    _file(t.g, t.gh(), "Blank invoice in August", screenshots=[up])
    t.g.post("/api/issues/GLX-501/comments", json={"text": "every user"}, headers=t.gh())
    _sync(t)
    t.tp.post("/api/reports/acme/ACME-501/promote", json={}, headers=AGENT)
    t.tp.post("/api/reports/globex/GLX-501/attach", json={"to": "IS-501"}, headers=AGENT)
    doc = t.tp.get("/api/issues/IS-501", headers=hdr()).json()
    assert doc["reports"] == ["acme/ACME-501", "globex/GLX-501"]
    rows = {r["board"]: r for r in doc["customerReports"]}
    assert (rows["acme"]["key"], rows["acme"]["reporter"], rows["acme"]["customerStatus"]) == ("ACME-501", "Alice", "new")
    assert (rows["globex"]["key"], rows["globex"]["reporter"], rows["globex"]["screenshots"]) == ("GLX-501", "Bob", [up])
    assert rows["globex"]["comments"][0]["text"] == "every user"
    assert t.tp.get("/api/issues", headers=hdr()).json()[0]["reports"] == ["acme/ACME-501", "globex/GLX-501"]
    page = t.tp.get("/").text
    assert "Customer reports" in page and "Intake" in page and "api/reports?intake=true" in page


def test_g6_a_verdict_verified_internally_reaches_every_linked_report(tri):
    t = tri
    _two_linked(t)
    t.tp.post("/api/issues/IS-501/transition", json={"to": "fixed", "agent": {"rootCause": "secret cause", "fix": "f"}}, headers=AGENT)
    rep = _sync(t)
    assert rep["acme"]["pushed"] == [] and rep["globex"]["pushed"] == []
    t.tp.post("/api/issues/IS-501/transition", json={"to": "verified", "note": "checked on build 510"}, headers=hdr("Priya"))
    rep = _sync(t)
    assert rep["acme"]["pushed"] == ["ACME-501→fixed"] and rep["globex"]["pushed"] == ["GLX-501→fixed"]
    for c, h, k in ((t.a, t.ah(), "ACME-501"), (t.g, t.gh(), "GLX-501")):
        d = c.get(f"/api/issues/{k}", headers=h).json()
        assert d["status"] == "fixed" and d["history"][-1]["by"] == t.internal.PUSH_ACTOR and d["history"][-1]["note"].startswith("Fixed")
        assert "secret cause" not in c.get(f"/api/issues/{k}", headers=h).text
    rep = _sync(t)
    assert rep["acme"]["pushed"] == [] and rep["globex"]["pushed"] == []
    assert {r["customerStatus"] for r in t.tp.get("/api/issues/IS-501", headers=hdr()).json()["customerReports"]} == {"fixed"}
    # a customer's own verify / close is recorded on their report only
    t.a.post("/api/issues/ACME-501/transition", json={"to": "verified"}, headers=t.ah())
    t.a.post("/api/issues/ACME-501/transition", json={"to": "closed"}, headers=t.ah())
    assert _sync(t)["acme"]["customerMoves"] == 2
    doc = t.tp.get("/api/issues/IS-501", headers=hdr()).json()
    assert doc["status"] == "verified" and {r["board"]: r["customerStatus"] for r in doc["customerReports"]} == {"acme": "closed", "globex": "fixed"}


def test_g6_a_customer_never_sees_duplicate_but_gets_the_twins_verdict(tri):
    t = tri
    twin = file_issue(t.tp)["key"]
    _file(t.a, t.ah(), "Invoice is blank")
    _sync(t)
    k = t.tp.post("/api/reports/acme/ACME-501/promote", json={}, headers=AGENT).json()["key"]
    t.tp.post(f"/api/issues/{k}/transition", json={"to": "duplicate", "agent": {"duplicateOf": twin}}, headers=AGENT)
    t.tp.post(f"/api/issues/{k}/transition", json={"to": "verified"}, headers=hdr("Priya"))
    assert _sync(t)["acme"]["pushed"] == [], "the twin is not verified yet"
    _fix_and_verify(t, twin)
    assert _sync(t)["acme"]["pushed"] == ["ACME-501→fixed"]
    hist = t.a.get("/api/issues/ACME-501", headers=t.ah()).json()["history"]
    assert "duplicate" not in [h["to"] for h in hist] and twin not in t.a.get("/api/issues/ACME-501", headers=t.ah()).text


def test_g2_nothing_from_one_customer_reaches_another(tri):
    t = tri
    up = _shot(t.a, t.ah("Alice Acme"))
    _file(t.a, t.ah("Alice Acme"), "Acme invoice export blank", description="acme-only steps", screenshots=[up])
    t.a.post("/api/issues/ACME-501/comments", json={"text": "acme secret comment"}, headers=t.ah("Alice Acme"))
    _file(t.g, t.gh(), "Blank invoice in August")
    _sync(t)
    t.tp.post("/api/reports/acme/ACME-501/promote", json={}, headers=AGENT)
    t.tp.post("/api/reports/globex/GLX-501/attach", json={"to": "IS-501"}, headers=AGENT)
    t.tp.post("/api/reports/acme/ACME-501/ask", json={"text": "Which acme billing code?"}, headers=AGENT)
    _sync(t)
    _fix_and_verify(t)
    assert _sync(t)["globex"]["pushed"] == ["GLX-501→fixed"]
    seen = " ".join(t.g.get(p, headers=t.gh()).text for p in ("/api/issues?full=true", "/api/issues", "/api/issues/GLX-501", "/api/stats"))
    for leak in ("acme", "ACME", "Alice", up, "IS-501", "secret", "Acme invoice", "billing code", "Invoice is blank", "1 other", "2 customers"):
        assert leak.lower() not in seen.lower(), leak
    assert t.g.get("/api/stats", headers=t.gh()).json()["total"] == 1
    assert [h["note"] for h in t.g.get("/api/issues/GLX-501", headers=t.gh()).json()["history"] if h["by"] == t.internal.PUSH_ACTOR] == [t.internal.CUSTOMER_NOTES["fixed"]]


def test_g7_more_info_is_per_report(tri):
    t = tri
    _two_linked(t)
    assert t.tp.post("/api/reports/acme/ACME-501/ask", json={"text": "Which month?"}, headers=hdr()).status_code == 403
    assert t.tp.post("/api/reports/acme/ACME-501/ask", json={"text": " "}, headers=AGENT).status_code == 400
    assert t.tp.post("/api/reports/acme/ACME-501/ask", json={"text": "Which month?"}, headers=AGENT).status_code == 200
    rep = _sync(t)
    assert rep["acme"]["pushed"] == ["ACME-501→more_info"] and rep["globex"]["pushed"] == []
    a = t.a.get("/api/issues/ACME-501", headers=t.ah()).json()
    assert a["status"] == "more_info" and a["history"][-1]["note"] == "Which month?"
    assert t.g.get("/api/issues/GLX-501", headers=t.gh()).json()["status"] == "new"
    assert t.tp.get("/api/issues/IS-501", headers=hdr()).json()["status"] == "new"
    assert _sync(t)["acme"]["pushed"] == []
    # the customer answers → the report is flagged "answered" for the agent; the issue does not move
    t.a.post("/api/issues/ACME-501/transition", json={"to": "open", "note": "August"}, headers=t.ah())
    assert _sync(t)["acme"]["customerMoves"] == 1
    [r] = t.tp.get("/api/reports?intake=true", headers=hdr()).json()
    assert (r["key"], r["flag"], r["customerStatus"], r["comments"][-1]["text"]) == ("ACME-501", "answered", "open", "August")
    assert t.tp.get("/api/stats", headers=hdr()).json()["flagged"] == 1 and t.tp.get("/api/issues/IS-501", headers=hdr()).json()["status"] == "new"
    t.tp.post("/api/reports/acme/ACME-501/attach", json={"to": "IS-501"}, headers=AGENT)
    assert t.tp.get("/api/reports?intake=true", headers=hdr()).json() == []
    assert _sync(t)["acme"]["pushed"] == []


def test_g8_a_customer_reopen_after_a_verdict_flags_the_report_and_nothing_reopens_by_itself(tri):
    t = tri
    _two_linked(t)
    _fix_and_verify(t)
    _sync(t)
    t.a.post("/api/issues/ACME-501/transition", json={"to": "open", "note": "still blank for me"}, headers=t.ah())
    rep = _sync(t)
    assert rep["acme"]["customerMoves"] == 1 and rep["acme"]["pushed"] == []
    doc = t.tp.get("/api/issues/IS-501", headers=hdr()).json()
    assert doc["status"] == "verified"
    assert doc["comments"][-1]["text"] == "ACME-501 reopened by acme (Alice): still blank for me"
    assert {r["board"]: r["flag"] for r in doc["customerReports"]} == {"acme": "reopened", "globex": ""}
    assert [r["key"] for r in t.tp.get("/api/reports?intake=true", headers=hdr()).json()] == ["ACME-501"]
    assert t.a.get("/api/issues/ACME-501", headers=t.ah()).json()["status"] == "open", "the verdict it reopened is not sent again"
    assert t.g.get("/api/issues/GLX-501", headers=t.gh()).json()["status"] == "fixed"
    assert _sync(t)["acme"]["pushed"] == []
    assert t.tp.post("/api/issues/IS-501/transition", json={"to": "open", "note": "x"}, headers=AGENT).status_code == 409
    # a different defect: detach, then promote as a new issue; its own verdict reaches the customer
    assert t.tp.post("/api/reports/acme/ACME-501/detach", json={}, headers=hdr()).status_code == 403
    r = t.tp.post("/api/reports/acme/ACME-501/detach", json={"text": "different month"}, headers=AGENT).json()
    assert r["issue"] is None and r["flag"] == ""
    assert t.tp.get("/api/issues/IS-501", headers=hdr()).json()["reports"] == ["globex/GLX-501"]
    assert t.tp.post("/api/reports/acme/ACME-501/detach", json={}, headers=AGENT).status_code == 409
    assert t.tp.post("/api/reports/acme/ACME-501/promote", json={}, headers=AGENT).json()["key"] == "IS-502"
    _fix_and_verify(t, "IS-502")
    assert _sync(t)["acme"]["pushed"] == ["ACME-501→fixed"]
    assert t.tp.get("/api/reports/acme/ACME-501", headers=hdr()).json()["flag"] == ""


def test_g8_a_human_reopen_and_new_verdict_reaches_the_reopened_report(tri):
    t = tri
    _two_linked(t)
    _fix_and_verify(t)
    _sync(t)
    t.a.post("/api/issues/ACME-501/transition", json={"to": "open", "note": "still blank"}, headers=t.ah())
    _sync(t)
    t.tp.post("/api/issues/IS-501/transition", json={"to": "open", "note": "acme still sees it"}, headers=hdr("Priya"))
    _fix_and_verify(t)
    rep = _sync(t)
    assert rep["acme"]["pushed"] == ["ACME-501→fixed"]
    assert rep["globex"]["pushed"] == [], "globex already shows fixed"


def test_g9_single_board_mirror_data_migrates_to_an_issue_with_one_attached_report(tri):
    t = tri
    up = _shot(t.a, t.ah())
    f = _file(t.a, t.ah(), "Old mirrored report", screenshots=[up])
    t.a.post("/api/issues/ACME-501/comments", json={"text": "seen before"}, headers=t.ah())
    at = "2026-01-01T00:00:00.000Z"
    with t.internal.tx() as con:
        t.internal.put_issue(con, {"key": "IS-501", "num": 501, "title": f["title"], "description": "steps", "module": "api", "kind": "bug",
                                   "severity": "medium", "persona": "", "build": "", "status": "open", "source": "customer", "sourceRef": "ACME-501",
                                   "reporter": "Alice", "createdAt": at, "updatedAt": at, "screenshots": [up], "agent": {}, "comments": [],
                                   "history": [{"at": at, "by": "sync", "from": "", "to": "new", "note": "Mirrored"}],
                                   "sync": {"commentsSeen": 1, "historySeen": 1, "pushedAt": ""}})
    t.internal.init_db()
    t.internal.init_db()
    doc = t.tp.get("/api/issues/IS-501", headers=hdr()).json()
    assert doc["reports"] == ["acme/ACME-501"] and doc["status"] == "open"
    [r] = doc["customerReports"]
    assert (r["board"], r["key"], r["issue"], r["title"], r["reporter"], r["screenshots"]) == ("acme", "ACME-501", "IS-501", "Old mirrored report", "Alice", [up])
    assert len(t.tp.get("/api/reports", headers=hdr()).json()) == 1
    rep = _sync(t)["acme"]
    assert rep["intake"] == [] and rep["comments"] == 0 and rep["pushed"] == []
    assert t.tp.get("/api/reports/acme/ACME-501", headers=hdr()).json()["customerStatus"] == "new"


def test_another_app_drops_a_report_into_intake_and_reads_its_outcome(tri):
    t = tri
    up = t.tp.post("/api/uploads", files={"file": ("s.png", io.BytesIO(PNG), "image/png")}, headers=AGENT).json()["id"]
    body = {"board": "support", "key": "SUP-12", "title": "Export button greyed out", "description": "ticket text", "reporter": "Dana (acme)", "screenshots": [up, "nope.png"]}
    assert t.tp.post("/api/reports", json=body, headers=hdr()).status_code == 403
    r = t.tp.post("/api/reports", json=body, headers=AGENT)
    assert r.status_code == 201, r.text
    assert (r.json()["issue"], r.json()["screenshots"], r.json()["customerStatus"]) == (None, [up], "new")
    assert t.tp.post("/api/reports", json=body, headers=AGENT).status_code == 409
    assert t.tp.post("/api/reports", json={**body, "board": "acme"}, headers=AGENT).status_code == 409
    assert t.tp.post("/api/reports", json={**body, "board": "Bad/Board"}, headers=AGENT).status_code == 422
    assert t.tp.post("/api/reports", json={**body, "key": "SUP-13", "module": "nope"}, headers=AGENT).status_code == 400
    assert [x["board"] for x in t.tp.get("/api/reports?intake=true", headers=hdr()).json()] == ["support"]
    k = t.tp.post("/api/reports/support/SUP-12/promote", json={}, headers=AGENT).json()["key"]
    assert t.tp.get("/api/reports/support/SUP-12", headers=hdr()).json()["release"] is None
    _fix_and_verify(t, k)
    rel = t.tp.get("/api/reports/support/SUP-12", headers=hdr()).json()["release"]
    assert rel["status"] == "fixed" and rel["note"] == t.internal.CUSTOMER_NOTES["fixed"]
    assert "support" not in _sync(t)


def test_g10_a_customer_board_has_no_triage(tri):
    t = tri
    assert t.a.get("/api/reports", headers=t.ah()).status_code == 404
    assert t.a.post("/api/reports/acme/ACME-501/promote", json={}, headers={**AGENT, "X-Issues-Token": "a-tok"}).status_code == 404
    assert "intake" not in t.a.get("/api/stats", headers=t.ah()).json()
    assert t.a.get("/api/meta", headers=t.ah()).json()["customer"] is True


def test_sync_endpoint_needs_a_mirror_and_a_non_tester(boards):
    _, _, internal, tp = boards
    assert tp.post("/api/sync", headers=hdr()).status_code == 403
    assert tp.post("/api/sync", headers=hdr("agent", "agent")).status_code == 404   # no FEEDBACK_BOARDS here


def test_a_report_splits_into_independent_issues_linked_both_ways(client):
    p = file_issue(client, title="Three things wrong on one screen", description="a, b and c")
    r = client.post(f"/api/issues/{p['key']}/split", json={"parts": [
        {"title": "Part A", "module": "api", "kind": "bug", "severity": "high", "description": "a"},
        {"title": "Part B", "module": "ui", "kind": "enhancement", "severity": "low", "description": "b"}]}, headers=hdr())
    assert r.status_code == 403, "a tester files reports; the agent splits them"
    r = client.post(f"/api/issues/{p['key']}/split", json={"parts": [
        {"title": "Part A", "module": "api", "kind": "bug", "severity": "high", "description": "a"},
        {"title": "Part B", "module": "ui", "kind": "enhancement", "severity": "low", "description": "b"}], "note": "two defects in one report"},
        headers=hdr("Issue Agent", "agent"))
    assert r.status_code == 201, r.text
    out = r.json()
    a, b = out["children"]
    assert [c["key"] for c in out["children"]] == ["IS-502", "IS-503"]
    assert a["source"] == "split" and a["sourceRef"] == p["key"] and a["reporter"] == "Priya" and a["status"] == "new"
    assert b["module"] == "ui" and b["kind"] == "enhancement"
    parent = client.get(f"/api/issues/{p['key']}", headers=hdr()).json()
    assert parent["splitInto"] == ["IS-502", "IS-503"] and parent["status"] == "new"
    assert "Split into IS-502" in parent["comments"][-1]["text"] and "two defects" in parent["comments"][-1]["text"]
    # each part is worked on its own
    r = client.post("/api/issues/IS-502/transition", json={"to": "fixed", "agent": {"fix": "done"}}, headers=hdr("Issue Agent", "agent"))
    assert r.status_code == 200 and client.get(f"/api/issues/{p['key']}", headers=hdr()).json()["status"] == "new"
    # a part is not split again; the parent is
    r = client.post("/api/issues/IS-502/split", json={"parts": [{"title": "Deeper"}]}, headers=hdr("Issue Agent", "agent"))
    assert r.status_code == 409
    rows = client.get("/api/issues?status=new", headers=hdr()).json()
    assert any(x["key"] == p["key"] and x.get("splitInto") == ["IS-502", "IS-503"] for x in rows)


def test_a_customer_board_has_no_split(boards):
    customer, fb, internal, tp = boards
    f = fb.post("/api/issues", json={"title": "Two problems", "description": "x"}, headers=hdr("Nousheed")).json()
    r = fb.post(f"/api/issues/{f['key']}/split", json={"parts": [{"title": "One"}]}, headers=hdr("Issue Agent", "agent"))
    assert r.status_code == 404


def test_a_split_folds_back_into_its_parent_without_deleting_the_parts(client):
    p = file_issue(client, title="Two things")
    out = client.post(f"/api/issues/{p['key']}/split", json={"parts": [{"title": "One"}, {"title": "Two"}]}, headers=hdr("Issue Agent", "agent")).json()
    a, b = [c["key"] for c in out["children"]]
    client.post(f"/api/issues/{a}/transition", json={"to": "fixed", "agent": {"fix": "x"}}, headers=hdr("Issue Agent", "agent"))
    r = client.post(f"/api/issues/{p['key']}/unsplit", json={"text": "meant another issue"}, headers=hdr())
    assert r.status_code == 403
    r = client.post(f"/api/issues/{p['key']}/unsplit", json={"text": "meant another issue"}, headers=hdr("Issue Agent", "agent"))
    assert r.status_code == 200 and "splitInto" not in r.json() and "meant another issue" in r.json()["comments"][-1]["text"]
    for k in (a, b):
        d = client.get(f"/api/issues/{k}", headers=hdr()).json()
        assert d["status"] == "duplicate" and d["agent"]["duplicateOf"] == p["key"] and d["source"] == "split"
    assert client.get(f"/api/issues/{a}", headers=hdr()).json()["agent"]["fix"] == "x", "the part's analysis is kept"
    r = client.post(f"/api/issues/{p['key']}/unsplit", json={}, headers=hdr("Issue Agent", "agent"))
    assert r.status_code == 409
