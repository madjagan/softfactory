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


def test_tester_cannot_give_verdicts_but_claude_can(client):
    k = file_issue(client)["key"]
    r = client.post(f"/api/issues/{k}/transition", json={"to": "fixed"}, headers=hdr())
    assert r.status_code == 409
    r = client.post(f"/api/issues/{k}/transition", json={"to": "fixed", "claude": {"rootCause": "x", "fixProposed": "p", "fix": "y", "tests": "t", "humanTests": "h"}}, headers=hdr("claude", "claude"))
    assert r.status_code == 200
    doc = r.json()
    assert doc["status"] == "fixed" and doc["claude"]["processedAt"] and doc["claude"]["fix"] == "y" and doc["claude"]["fixProposed"] == "p"
    assert doc["history"][-1] == {**doc["history"][-1], "by": "claude", "from": "new", "to": "fixed"}


def test_full_happy_path_to_closed(client):
    k = file_issue(client)["key"]
    client.post(f"/api/issues/{k}/transition", json={"to": "fixed", "claude": {"fix": "done"}}, headers=hdr("claude", "claude"))
    assert client.post(f"/api/issues/{k}/transition", json={"to": "verified"}, headers=hdr()).json()["verification"]["by"] == "Priya"
    assert client.post(f"/api/issues/{k}/transition", json={"to": "closed"}, headers=hdr()).json()["status"] == "closed"


def test_more_info_needs_an_answer_to_reopen(client):
    k = file_issue(client)["key"]
    client.post(f"/api/issues/{k}/transition", json={"to": "more_info", "claude": {"infoNeeded": "which login?"}}, headers=hdr("claude", "claude"))
    r = client.post(f"/api/issues/{k}/transition", json={"to": "open"}, headers=hdr())
    assert r.status_code == 400
    r = client.post(f"/api/issues/{k}/transition", json={"to": "open", "note": "Logged in as Layla"}, headers=hdr())
    assert r.status_code == 200 and r.json()["comments"][-1]["text"] == "Logged in as Layla"
    assert client.post(f"/api/issues/{k}/transition", json={"to": "verified"}, headers=hdr()).status_code == 409


def test_claude_cannot_verify_or_close(client):
    k = file_issue(client)["key"]
    client.post(f"/api/issues/{k}/transition", json={"to": "fixed"}, headers=hdr("claude", "claude"))
    assert client.post(f"/api/issues/{k}/transition", json={"to": "verified"}, headers=hdr("claude", "claude")).status_code == 409


def test_claude_may_restate_its_own_verdict_but_not_a_testers_status(client):
    # IS-424 — a duplicate-of pointed at an issues-log number; re-pointing it at the tracker key
    # is the same verdict with revised fields, not a move.
    k = file_issue(client)["key"]
    client.post(f"/api/issues/{k}/transition", json={"to": "duplicate", "claude": {"duplicateOf": "#184"}}, headers=hdr("claude", "claude"))
    r = client.post(f"/api/issues/{k}/transition", json={"to": "duplicate", "claude": {"duplicateOf": "IS-345"}}, headers=hdr("claude", "claude"))
    assert r.status_code == 200 and r.json()["status"] == "duplicate" and r.json()["claude"]["duplicateOf"] == "IS-345"
    assert r.json()["history"][-1] == {**r.json()["history"][-1], "from": "duplicate", "to": "duplicate"}
    # Verified is a tester's status: Claude may not restate it, and a tester may not restate a verdict.
    client.post(f"/api/issues/{k}/transition", json={"to": "verified"}, headers=hdr())
    assert client.post(f"/api/issues/{k}/transition", json={"to": "verified"}, headers=hdr("claude", "claude")).status_code == 409
    assert client.post(f"/api/issues/{k}/transition", json={"to": "verified"}, headers=hdr()).status_code == 409


def test_admin_may_set_any_status(client):
    k = file_issue(client)["key"]
    assert client.post(f"/api/issues/{k}/transition", json={"to": "closed"}, headers=hdr("Madhavan", "admin")).json()["status"] == "closed"


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
    monkeypatch.setenv("ISSUES_ROLES", "tester,claude")
    import issues.app as appmod
    importlib.reload(appmod)
    with TestClient(appmod.app) as c:
        assert c.get("/api/meta", headers=hdr()).json()["roles"] == ["tester"]
        assert c.get("/api/issues", headers=hdr("X", "admin")).status_code == 403
        k = c.post("/api/issues", json={"title": "Customer report"}, headers=hdr("Customer")).json()["key"]
        assert c.post(f"/api/issues/{k}/transition", json={"to": "closed"}, headers=hdr("X", "admin")).status_code == 403
        assert c.post(f"/api/issues/{k}/transition", json={"to": "fixed"}, headers=hdr("claude", "claude")).status_code == 200


# ---------------- the customer board and its mirror ----------------
def _load_board(name: str, data_dir, env: dict):
    """A second, independent copy of the app module with its own config and database."""
    import importlib.util
    for k in ("ISSUES_TOKEN", "ISSUES_BRAND", "ISSUES_PREFIX", "ISSUES_ROLES", "ISSUES_CUSTOMER", "FEEDBACK_SYNC_URL"):
        os.environ.pop(k, None)
    os.environ["ISSUES_DATA"] = str(data_dir)
    os.environ.update(env)
    spec = importlib.util.spec_from_file_location(name, ROOT / "issues" / "app.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod          # pydantic resolves the models' forward references through here
    spec.loader.exec_module(mod)
    return mod


class FakeRemote:
    """The customer board reached through its TestClient, the way Remote reaches it over HTTP."""

    def __init__(self, client, actor):
        self.c, self.h = client, {"X-Role": "claude", "X-Actor": actor}

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
    customer = _load_board("issues_app_customer", tmp_path / "fb", {"ISSUES_PREFIX": "FB", "ISSUES_ROLES": "tester,claude", "ISSUES_CUSTOMER": "1"})
    internal = _load_board("issues_app_internal", tmp_path / "tp", {})
    with TestClient(customer.app) as fb, TestClient(internal.app) as tp:
        yield customer, fb, internal, tp


def test_a_customer_board_withholds_the_analysis(boards):
    customer, fb, *_ = boards
    k = file_issue(fb)["key"]
    r = fb.post(f"/api/issues/{k}/transition", json={"to": "fixed", "claude": {"rootCause": "secret", "fix": "y"}}, headers=hdr("claude", "claude"))
    assert r.status_code == 200 and r.json()["claude"] == {}
    assert fb.get(f"/api/issues/{k}", headers=hdr()).json()["claude"] == {}
    assert fb.get("/api/issues?full=true", headers=hdr()).json()[0]["claude"] == {}
    assert fb.get("/api/issues", headers=hdr()).json()[0]["processed"] is False
    assert fb.get("/api/meta", headers=hdr()).json()["customer"] is True
    assert "secret" not in fb.get(f"/api/issues/{k}", headers=hdr()).text


def test_customer_issues_mirror_in_and_only_status_travels_back(boards):
    customer, fb, internal, tp = boards
    remote = FakeRemote(fb, internal.PUSH_ACTOR)
    # 1. a customer files with a screenshot and adds a comment
    up = fb.post("/api/uploads", files={"file": ("s.png", io.BytesIO(PNG), "image/png")}, headers=hdr("Nousheed")).json()["id"]
    f = fb.post("/api/issues", json={"title": "Payslip is blank", "description": "steps", "module": "api", "screenshots": [up]}, headers=hdr("Nousheed")).json()
    fb.post(f"/api/issues/{f['key']}/comments", json={"text": "also on Safari"}, headers=hdr("Nousheed"))
    rep = internal.sync_feedback(remote)
    assert rep["created"] == [f"IS-501←{f['key']}"] and rep["comments"] == 1
    m = tp.get("/api/issues/IS-501", headers=hdr()).json()
    assert m["source"] == "customer" and m["sourceRef"] == f["key"] and m["reporter"] == "Nousheed" and m["status"] == "new"
    assert m["screenshots"] == [up] and tp.get(f"/uploads/{up}").status_code == 200
    assert m["comments"][0]["text"] == "also on Safari"
    assert internal.sync_feedback(remote) == {"created": [], "comments": 0, "customerMoves": 0, "pushed": [], "skipped": []}
    # 2. the agent asks a question here → the customer sees more_info and the question, nothing else
    tp.post("/api/issues/IS-501/transition", json={"to": "more_info", "claude": {"rootCause": "cannot see it", "infoNeeded": "Which month?"}}, headers=hdr("claude", "claude"))
    rep = internal.sync_feedback(remote)
    assert rep["pushed"] == [f"{f['key']}→more_info"]
    fdoc = fb.get(f"/api/issues/{f['key']}", headers=hdr()).json()
    assert fdoc["status"] == "more_info" and fdoc["claude"] == {} and "cannot see it" not in fb.get(f"/api/issues/{f['key']}", headers=hdr()).text
    assert fdoc["history"][-1]["by"] == internal.PUSH_ACTOR and fdoc["history"][-1]["note"] == "Which month?"
    assert internal.sync_feedback(remote)["pushed"] == []        # pushed once, not again
    # 3. the customer answers and reopens → the mirror reopens with the answer
    fb.post(f"/api/issues/{f['key']}/transition", json={"to": "open", "note": "August"}, headers=hdr("Nousheed"))
    rep = internal.sync_feedback(remote)
    assert rep["customerMoves"] == 1 and rep["comments"] == 1
    m = tp.get("/api/issues/IS-501", headers=hdr()).json()
    assert m["status"] == "open" and m["history"][-1]["note"] == "August" and m["comments"][-1]["text"] == "August"
    # 4. the agent fixes it → NOTHING travels yet: the customer still sees Open until it is verified here
    tp.post("/api/issues/IS-501/transition", json={"to": "fixed", "claude": {"rootCause": "r", "fix": "f", "tests": "t", "humanTests": "h"}}, headers=hdr("claude", "claude"))
    assert internal.sync_feedback(remote)["pushed"] == []
    assert fb.get(f"/api/issues/{f['key']}", headers=hdr()).json()["status"] == "open"
    # 5. an internal tester verifies → Fixed is released to the customer with a plain note, analysis withheld
    tp.post("/api/issues/IS-501/transition", json={"to": "verified", "note": "checked on build 510"}, headers=hdr("Priya"))
    assert internal.sync_feedback(remote)["pushed"] == [f"{f['key']}→fixed"]
    fdoc = fb.get(f"/api/issues/{f['key']}", headers=hdr()).json()
    assert fdoc["status"] == "fixed" and fdoc["claude"] == {} and "build 510" not in fb.get(f"/api/issues/{f['key']}", headers=hdr()).text
    assert fdoc["history"][-1]["by"] == internal.PUSH_ACTOR and fdoc["history"][-1]["note"].startswith("Fixed")
    assert internal.sync_feedback(remote)["pushed"] == []
    # 6. the customer verifies and closes → the mirror closes; the internal verification record stays
    fb.post(f"/api/issues/{f['key']}/transition", json={"to": "verified"}, headers=hdr("Nousheed"))
    fb.post(f"/api/issues/{f['key']}/transition", json={"to": "closed"}, headers=hdr("Nousheed"))
    assert internal.sync_feedback(remote)["customerMoves"] == 1        # verified was already the mirror's state
    m = tp.get("/api/issues/IS-501", headers=hdr()).json()
    assert m["status"] == "closed" and m["verification"]["by"] == "Priya" and m["claude"]["fix"] == "f"


def test_a_customer_reopen_after_release_reopens_the_mirror_and_a_verdict_verified_here_is_released(boards):
    customer, fb, internal, tp = boards
    remote = FakeRemote(fb, internal.PUSH_ACTOR)
    f = fb.post("/api/issues", json={"title": "Column header says Role", "description": "steps"}, headers=hdr("Nousheed")).json()
    internal.sync_feedback(remote)
    tp.post("/api/issues/IS-501/transition", json={"to": "as_speced", "claude": {"specRef": "PRD 3.1"}}, headers=hdr("claude", "claude"))
    assert internal.sync_feedback(remote)["pushed"] == []
    tp.post("/api/issues/IS-501/transition", json={"to": "verified"}, headers=hdr("Priya"))
    assert internal.sync_feedback(remote)["pushed"] == [f"{f['key']}→as_speced"]
    fb.post(f"/api/issues/{f['key']}/transition", json={"to": "open", "note": "I expected Designation"}, headers=hdr("Nousheed"))
    rep = internal.sync_feedback(remote)
    assert rep["customerMoves"] == 1
    m = tp.get("/api/issues/IS-501", headers=hdr()).json()
    assert m["status"] == "open" and m["comments"][-1]["text"] == "I expected Designation"


def test_sync_endpoint_needs_a_mirror_and_a_non_tester(boards):
    _, _, internal, tp = boards
    assert tp.post("/api/sync", headers=hdr()).status_code == 403
    assert tp.post("/api/sync", headers=hdr("claude", "claude")).status_code == 404   # no FEEDBACK_SYNC_URL here


def test_a_report_splits_into_independent_issues_linked_both_ways(client):
    p = file_issue(client, title="Three things wrong on one screen", description="a, b and c")
    r = client.post(f"/api/issues/{p['key']}/split", json={"parts": [
        {"title": "Part A", "module": "api", "kind": "bug", "severity": "high", "description": "a"},
        {"title": "Part B", "module": "ui", "kind": "enhancement", "severity": "low", "description": "b"}]}, headers=hdr())
    assert r.status_code == 403, "a tester files reports; the agent splits them"
    r = client.post(f"/api/issues/{p['key']}/split", json={"parts": [
        {"title": "Part A", "module": "api", "kind": "bug", "severity": "high", "description": "a"},
        {"title": "Part B", "module": "ui", "kind": "enhancement", "severity": "low", "description": "b"}], "note": "two defects in one report"},
        headers=hdr("Issue Agent", "claude"))
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
    r = client.post("/api/issues/IS-502/transition", json={"to": "fixed", "claude": {"fix": "done"}}, headers=hdr("Issue Agent", "claude"))
    assert r.status_code == 200 and client.get(f"/api/issues/{p['key']}", headers=hdr()).json()["status"] == "new"
    # a part is not split again; the parent is
    r = client.post("/api/issues/IS-502/split", json={"parts": [{"title": "Deeper"}]}, headers=hdr("Issue Agent", "claude"))
    assert r.status_code == 409
    rows = client.get("/api/issues?status=new", headers=hdr()).json()
    assert any(x["key"] == p["key"] and x.get("splitInto") == ["IS-502", "IS-503"] for x in rows)


def test_a_customer_board_has_no_split(boards):
    customer, fb, internal, tp = boards
    f = fb.post("/api/issues", json={"title": "Two problems", "description": "x"}, headers=hdr("Nousheed")).json()
    r = fb.post(f"/api/issues/{f['key']}/split", json={"parts": [{"title": "One"}]}, headers=hdr("Issue Agent", "claude"))
    assert r.status_code == 404


def test_a_split_folds_back_into_its_parent_without_deleting_the_parts(client):
    p = file_issue(client, title="Two things")
    out = client.post(f"/api/issues/{p['key']}/split", json={"parts": [{"title": "One"}, {"title": "Two"}]}, headers=hdr("Issue Agent", "claude")).json()
    a, b = [c["key"] for c in out["children"]]
    client.post(f"/api/issues/{a}/transition", json={"to": "fixed", "claude": {"fix": "x"}}, headers=hdr("Issue Agent", "claude"))
    r = client.post(f"/api/issues/{p['key']}/unsplit", json={"text": "meant another issue"}, headers=hdr())
    assert r.status_code == 403
    r = client.post(f"/api/issues/{p['key']}/unsplit", json={"text": "meant another issue"}, headers=hdr("Issue Agent", "claude"))
    assert r.status_code == 200 and "splitInto" not in r.json() and "meant another issue" in r.json()["comments"][-1]["text"]
    for k in (a, b):
        d = client.get(f"/api/issues/{k}", headers=hdr()).json()
        assert d["status"] == "duplicate" and d["claude"]["duplicateOf"] == p["key"] and d["source"] == "split"
    assert client.get(f"/api/issues/{a}", headers=hdr()).json()["claude"]["fix"] == "x", "the part's analysis is kept"
    r = client.post(f"/api/issues/{p['key']}/unsplit", json={}, headers=hdr("Issue Agent", "claude"))
    assert r.status_code == 409
