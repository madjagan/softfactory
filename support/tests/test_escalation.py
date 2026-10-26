"""S5 / S6: a ticket escalates into the tracker's intake as board `support`, and the verdict comes back as a draft."""
import importlib
import importlib.util
import io
import os
import sys
import urllib.error
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from support.tests.test_api import Clock, T0, cust, file_ticket, move, staff

ROOT = Path(__file__).resolve().parents[2]
AGENT = {"X-Role": "agent", "X-Actor": "issue-agent"}
TESTER = {"X-Role": "tester", "X-Actor": "Priya"}


class FakeTracker:
    """The tracker reached through its TestClient, the way support.app.Tracker reaches it over HTTP."""

    def __init__(self, client):
        self.c, self.h, self.down = client, {"X-Role": "agent", "X-Actor": "support"}, False

    def _check(self, r, path):
        if self.down:
            raise urllib.error.URLError("connection refused")
        if r.status_code >= 400:
            raise urllib.error.HTTPError(path, r.status_code, r.text, {}, io.BytesIO(r.content))
        return r.json()

    def get_json(self, path):
        return self._check(self.c.get(path, headers=self.h), path)

    def post_json(self, path, body):
        return self._check(self.c.post(path, json=body, headers=self.h), path)


@pytest.fixture()
def both(tmp_path, monkeypatch):
    for k in [k for k in os.environ if k.startswith(("FEEDBACK_", "ISSUES_"))]:
        monkeypatch.delenv(k)
    monkeypatch.setenv("ISSUES_DATA", str(tmp_path / "tp"))
    spec = importlib.util.spec_from_file_location("issues_app_for_support", ROOT / "issues" / "app.py")
    tracker_mod = importlib.util.module_from_spec(spec)
    sys.modules["issues_app_for_support"] = tracker_mod
    spec.loader.exec_module(tracker_mod)

    monkeypatch.setenv("SUPPORT_DATA", str(tmp_path / "sup"))
    monkeypatch.setenv("SUPPORT_ORGS", "acme,globex")
    monkeypatch.setenv("SUPPORT_TOKEN", "staff-tok")
    monkeypatch.setenv("SUPPORT_TOKEN_ACME", "acme-tok")
    monkeypatch.setenv("SUPPORT_TOKEN_GLOBEX", "globex-tok")
    monkeypatch.setenv("SUPPORT_TRACKER_URL", "http://tracker:3002")
    monkeypatch.setenv("SUPPORT_TRACKER_SYNC_INTERVAL", "0")
    import support.app as sup
    importlib.reload(sup)
    monkeypatch.setattr(sup, "now", Clock(T0))
    with TestClient(tracker_mod.app) as tp, TestClient(sup.app) as c:
        fake = FakeTracker(tp)
        monkeypatch.setattr(sup, "tracker", fake)
        yield sup, c, tp, fake


def sync(c):
    r = c.post("/api/sync", headers=staff())
    assert r.status_code == 200, r.text
    return r.json()


def test_s5_escalating_drops_the_ticket_into_the_trackers_intake(both):
    sup, c, tp, _ = both
    k = file_ticket(c, title="Invoice export is blank", description="Since Monday")["key"]
    doc = move(c, k, "escalated", note="happens on every export").json()
    assert doc["status"] == "escalated" and doc["escalation"]["reportRef"] == f"support/{k}"
    intake = tp.get("/api/reports?intake=true", headers=TESTER).json()
    assert [(r["board"], r["key"], r["title"]) for r in intake] == [("support", k, "Invoice export is blank")]
    assert "Since Monday" in intake[0]["description"] and "happens on every export" in intake[0]["description"]
    assert intake[0]["reporter"] == "Nousheed (acme)"
    issue = tp.post(f"/api/reports/support/{k}/promote", json={}, headers=AGENT).json()["key"]
    assert sync(c)["checked"] == 1
    assert c.get(f"/api/tickets/{k}", headers=staff()).json()["escalation"]["issueRef"] == issue


def test_s5_an_issue_key_from_support_is_a_hint_and_escalating_twice_files_once(both):
    sup, c, tp, _ = both
    k = file_ticket(c)["key"]
    move(c, k, "escalated", issueRef="IS-512")
    assert "Support thinks this is IS-512." in tp.get(f"/api/reports/support/{k}", headers=TESTER).json()["description"]
    move(c, k, "open")
    assert move(c, k, "escalated").status_code == 200
    assert len(tp.get("/api/reports", headers=TESTER).json()) == 1


def test_s5_a_tracker_that_is_down_refuses_the_escalation_and_changes_nothing(both):
    sup, c, tp, fake = both
    k = file_ticket(c)["key"]
    fake.down = True
    r = move(c, k, "escalated")
    assert r.status_code == 502
    assert c.get(f"/api/tickets/{k}", headers=staff()).json()["status"] == "new"


def test_s6_the_verdict_comes_back_as_a_draft_only_after_the_issue_is_verified(both):
    sup, c, tp, _ = both
    k = file_ticket(c)["key"]
    move(c, k, "escalated")
    issue = tp.post(f"/api/reports/support/{k}/promote", json={}, headers=AGENT).json()["key"]
    tp.post(f"/api/issues/{issue}/transition", json={"to": "fixed", "agent": {"rootCause": "ROOT-CAUSE-MARK", "fix": "f"}}, headers=AGENT)
    assert sync(c)["verdicts"] == 0, "fixed is not released until a tester verifies it"
    tp.post(f"/api/issues/{issue}/transition", json={"to": "verified"}, headers=TESTER)
    assert sync(c)["verdicts"] == 1
    assert sync(c)["verdicts"] == 0, "the same verdict is drafted once"
    t = c.get(f"/api/tickets/{k}", headers=staff()).json()
    assert t["status"] == "escalated" and t["escalation"]["verdict"] == "fixed"
    draft = [m for m in t["messages"] if m["visibility"] == "draft"]
    assert len(draft) == 1 and draft[0]["tag"] == "verdict" and "ROOT-CAUSE-MARK" not in draft[0]["text"]
    seen = c.get(f"/api/tickets/{k}", headers=cust()).text
    assert draft[0]["text"] not in seen and issue not in seen and "ROOT-CAUSE-MARK" not in seen
    c.post(f"/api/tickets/{k}/messages/{draft[0]['id']}/send", json={}, headers=staff())
    assert draft[0]["text"] in c.get(f"/api/tickets/{k}", headers=cust()).text
    assert move(c, k, "resolved").json()["status"] == "resolved"


def test_s6_a_question_from_the_product_team_is_an_internal_note(both):
    sup, c, tp, _ = both
    k = file_ticket(c)["key"]
    move(c, k, "escalated")
    tp.post(f"/api/reports/support/{k}/ask", json={"text": "Which invoice month?"}, headers=AGENT)
    assert sync(c)["questions"] == 1
    note = [m for m in c.get(f"/api/tickets/{k}", headers=staff()).json()["messages"] if m.get("tag") == "tracker_question"]
    assert note[0]["visibility"] == "internal" and "Which invoice month?" in note[0]["text"]
    assert "Which invoice month?" not in c.get(f"/api/tickets/{k}", headers=cust()).text


def test_the_sync_endpoint_is_support_or_admin_only(both):
    sup, c, *_ = both
    assert c.post("/api/sync", headers=staff("agent", "bot")).status_code == 403
    assert c.post("/api/sync", headers=cust()).status_code == 403
