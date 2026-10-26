"""Support desk API: org isolation, the customer allowlist, drafts, the state machine, the widget token, auto-close."""
import importlib
import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8cfc000000301010018dd8db00000000049454e44ae426082")
T0 = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)
STAFF, TOK_A, TOK_B, SECRET = "staff-tok", "acme-tok", "globex-tok", "widget-secret"


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPORT_DATA", str(tmp_path))
    monkeypatch.setenv("SUPPORT_ORGS", "acme,globex")
    monkeypatch.setenv("SUPPORT_TOKEN", STAFF)
    monkeypatch.setenv("SUPPORT_TOKEN_ACME", TOK_A)
    monkeypatch.setenv("SUPPORT_TOKEN_GLOBEX", TOK_B)
    monkeypatch.setenv("SUPPORT_WIDGET_SECRET", SECRET)
    monkeypatch.setenv("SUPPORT_AUTO_CLOSE_DAYS", "7")
    return monkeypatch


@pytest.fixture()
def appmod(env):
    import support.app as appmod
    importlib.reload(appmod)
    clock = Clock(T0)
    env.setattr(appmod, "now", clock)
    appmod.clock = clock
    return appmod


@pytest.fixture()
def c(appmod):
    with TestClient(appmod.app) as client:
        yield client


def cust(org="acme", name="Nousheed", email="nousheed@acme.test"):
    return {"X-Support-Token": {"acme": TOK_A, "globex": TOK_B}[org], "X-Actor": name, "X-Email": email}


def staff(role="support", name="Sam"):
    return {"X-Support-Token": STAFF, "X-Role": role, "X-Actor": name}


def file_ticket(c, h=None, **over):
    body = {"title": "Invoice export is blank", "description": "steps"}
    body.update(over)
    r = c.post("/api/tickets", json=body, headers=h or cust())
    assert r.status_code == 201, r.text
    return r.json()


def move(c, key, to, h=None, **kw):
    return c.post(f"/api/tickets/{key}/transition", json={"to": to, **kw}, headers=h or staff())


def draft_id(c, key):
    return next(m["id"] for m in c.get(f"/api/tickets/{key}", headers=staff()).json()["messages"] if m["visibility"] == "draft")


# ---------------- S1 / S7: isolation and the customer allowlist (release-blocking) ----------------
MARKERS = ["ORGA-TITLE-MARK", "ORGA-DESC-MARK", "INTERNAL-NOTE-MARK", "DRAFT-MARK", "IS-SECRET-512", "ROOT-CAUSE-MARK", "Sam"]


@pytest.fixture()
def planted(c):
    """Org A's ticket carrying every kind of internal content there is."""
    t = file_ticket(c, title="ORGA-TITLE-MARK export", description="ORGA-DESC-MARK")
    k = t["key"]
    assert c.post(f"/api/tickets/{k}/messages", json={"text": "INTERNAL-NOTE-MARK other customers hit this", "visibility": "internal"}, headers=staff()).status_code == 200
    assert c.post(f"/api/tickets/{k}/messages", json={"text": "DRAFT-MARK see guide §2"}, headers=staff("agent", "Support Agent")).status_code == 200
    assert c.post(f"/api/tickets/{k}/messages", json={"text": "Escalate: ROOT-CAUSE-MARK", "visibility": "internal", "tag": "recommend_escalation"}, headers=staff("agent", "Support Agent")).status_code == 200
    assert c.post(f"/api/tickets/{k}/fields", json={"category": "defect", "priority": "high"}, headers=staff()).status_code == 200
    assert move(c, k, "open", note="ROOT-CAUSE-MARK in the export job").status_code == 200
    r = move(c, k, "escalated", issueRef="IS-SECRET-512", note="ROOT-CAUSE-MARK")
    assert r.status_code == 200 and r.json()["escalation"]["issueRef"] == "IS-SECRET-512"
    return k


def customer_responses(c, h, key):
    """Every response a customer can get, for a key that may or may not be theirs."""
    rs = [c.get("/api/meta", headers=h), c.get("/api/tickets", headers=h), c.get("/api/tickets?full=true", headers=h),
          c.get("/api/tickets?q=ORGA", headers=h), c.get("/api/tickets?org=acme&full=true", headers=h),
          c.get("/api/tickets?status=escalated&full=true", headers=h),
          c.get(f"/api/tickets/{key}", headers=h), c.get("/api/stats", headers=h),
          c.post(f"/api/tickets/{key}/messages", json={"text": "hello"}, headers=h),
          c.post(f"/api/tickets/{key}/transition", json={"to": "closed"}, headers=h),
          c.post(f"/api/tickets/{key}/fields", json={"category": "other"}, headers=h),
          c.post(f"/api/tickets/{key}/messages/x/send", json={}, headers=h)]
    return rs


def test_s1_another_org_cannot_list_or_fetch_and_gets_404_not_403(c, planted):
    hb = cust("globex", "Gina", "gina@globex.test")
    file_ticket(c, hb, title="Globex own ticket")
    assert [t["title"] for t in c.get("/api/tickets", headers=hb).json()] == ["Globex own ticket"]
    for path in (f"/api/tickets/{planted}", f"/api/tickets/{planted}?full=true"):
        r = c.get(path, headers=hb)
        assert r.status_code == 404 and r.json() == {"error": f"{planted} not found"}
    assert c.get("/api/tickets/SUP-9999", headers=hb).json() == {"error": "SUP-9999 not found"}, "a real key and a missing one look the same"
    assert c.post(f"/api/tickets/{planted}/messages", json={"text": "hi"}, headers=hb).status_code == 404
    assert c.post(f"/api/tickets/{planted}/transition", json={"to": "closed"}, headers=hb).status_code == 404
    text = "".join(r.text for r in customer_responses(c, hb, planted))
    for m in MARKERS + ["acme", "nousheed"]:
        assert m not in text, m


def test_s1_a_widget_user_of_another_org_cannot_reach_it_either(c, appmod, planted):
    tok = appmod.sign_widget_token({"org": "globex", "email": "gina@globex.test", "name": "Gina", "exp": T0.timestamp() + 3600}, SECRET)
    h = {"X-Widget-Token": tok}
    assert c.get(f"/api/tickets/{planted}", headers=h).status_code == 404
    assert c.get("/api/tickets?full=true", headers=h).json() == []
    assert not any(m in "".join(r.text for r in customer_responses(c, h, planted)) for m in MARKERS)


def test_s1_the_same_email_in_another_org_is_another_customer(c, planted):
    twin = cust("globex", "Nousheed", "nousheed@acme.test")
    assert c.get("/api/tickets?full=true", headers=twin).json() == []
    assert c.get(f"/api/tickets/{planted}", headers=twin).status_code == 404
    assert not any(m in "".join(r.text for r in customer_responses(c, twin, planted)) for m in MARKERS)


def test_s1_inside_an_org_a_customer_sees_only_their_own_tickets(c, planted):
    colleague = cust("acme", "Ravi", "ravi@acme.test")
    assert c.get("/api/tickets", headers=colleague).json() == []
    assert c.get(f"/api/tickets/{planted}", headers=colleague).status_code == 404


def test_s1_the_web_form_files_with_title_description_and_screenshots(c):
    up = c.post("/api/uploads", files={"file": ("s.png", io.BytesIO(PNG), "image/png")}, headers=cust()).json()["id"]
    t = file_ticket(c, screenshots=[up, "made-up.png"], context={"appVersion": "9.9"})
    assert t["key"] == "SUP-1001" and t["status"] == "new" and t["screenshots"] == [up]
    assert t["requester"] == {"name": "Nousheed", "email": "nousheed@acme.test"} and t["context"] == {}, "context is the widget's"
    assert c.get(f"/uploads/{up}").status_code == 200
    assert c.get("/api/tickets/SUP-1001", headers=staff()).json()["org"] == "acme"


def test_s7_the_owner_sees_public_messages_only_never_internal_analysis(c, planted):
    ha = cust()
    rs = customer_responses(c, ha, planted)
    doc = c.get(f"/api/tickets/{planted}", headers=ha).json()
    assert doc["status"] == "escalated" and "ORGA-TITLE-MARK" in doc["title"]
    assert set(doc) <= {"key", "num", "title", "description", "status", "requester", "context", "screenshots", "createdAt",
                        "updatedAt", "reopenedFrom", "reopenedAs", "messages", "history"}
    assert all(set(h) == {"at", "from", "to", "by"} for h in doc["history"]) and {h["by"] for h in doc["history"]} == {"Nousheed", "Support"}
    text = "".join(r.text for r in rs)
    for m in ["INTERNAL-NOTE-MARK", "DRAFT-MARK", "IS-SECRET-512", "ROOT-CAUSE-MARK", "Sam", "Support Agent", "globex",
              "escalation", "internal", "draft", "priority", "category", "recommend_escalation"]:
        assert m not in text, m


def test_s7_meta_never_lists_other_customers(c):
    assert "orgs" not in c.get("/api/meta", headers=cust()).json()
    assert c.get("/api/meta", headers=staff()).json()["orgs"] == ["acme", "globex"]


def test_tokens_decide_org_and_role(c):
    assert c.get("/api/tickets", headers={"X-Actor": "N", "X-Email": "n@acme.test"}).status_code == 401
    assert c.get("/api/tickets", headers={**cust(), "X-Support-Token": "wrong"}).status_code == 401
    assert c.get("/api/tickets", headers={**cust(), "X-Role": "support"}).status_code == 401, "an org token is not the support token"
    assert c.get("/api/tickets", headers={**cust(), "X-Org": "globex"}).json() == [], "the token names the org, not a header"
    assert c.get("/api/tickets", headers={"X-Support-Token": TOK_A, "X-Actor": "N"}).status_code == 400
    assert c.get("/api/tickets", headers=staff()).status_code == 200
    assert c.get("/healthz").status_code == 200


def test_local_dev_without_tokens_names_the_org_in_a_header(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPORT_DATA", str(tmp_path))
    monkeypatch.setenv("SUPPORT_ORGS", "acme,globex")
    for k in ("SUPPORT_TOKEN", "SUPPORT_TOKEN_ACME", "SUPPORT_TOKEN_GLOBEX"):
        monkeypatch.delenv(k, raising=False)
    import support.app as appmod
    importlib.reload(appmod)
    with TestClient(appmod.app) as c:
        h = {"X-Org": "acme", "X-Actor": "N", "X-Email": "n@acme.test"}
        k = c.post("/api/tickets", json={"title": "Local one"}, headers=h).json()["key"]
        assert c.get(f"/api/tickets/{k}", headers={**h, "X-Org": "globex"}).status_code == 404
        assert c.get("/api/tickets", headers={**h, "X-Org": "initech"}).status_code == 400
        assert c.get("/api/meta", headers={"X-Role": "support"}).json()["tokenRequired"] is False


# ---------------- S2: the widget ----------------
def widget(appmod, secret=SECRET, **over):
    p = {"org": "acme", "userId": "u-77", "email": "Layla@acme.test", "name": "Layla", "exp": T0.timestamp() + 600}
    p.update(over)
    return {"X-Widget-Token": appmod.sign_widget_token(p, secret)}


def test_s2_a_signed_widget_token_files_with_context_and_user(c, appmod):
    h = widget(appmod)
    up = c.post("/api/uploads", files={"file": ("s.png", io.BytesIO(PNG), "image/png")}, headers=h).json()["id"]
    ctx = {"pageUrl": "https://app.acme.test/invoices?m=8", "appVersion": "3.4.1", "userAgent": "Safari 17", "evil": "x"}
    t = file_ticket(c, h, context=ctx, screenshots=[up])
    assert t["context"] == {k: ctx[k] for k in ("pageUrl", "appVersion", "userAgent")}
    assert t["requester"] == {"name": "Layla", "email": "layla@acme.test", "userId": "u-77"} and t["screenshots"] == [up]
    s = c.get(f"/api/tickets/{t['key']}", headers=staff()).json()
    assert s["org"] == "acme" and s["context"]["appVersion"] == "3.4.1"
    assert [x["key"] for x in c.get("/api/tickets", headers=cust("acme", "Layla", "layla@acme.test")).json()] == [t["key"]], "same user on the web form"


@pytest.mark.parametrize("bad", ["forged", "tampered", "expired", "unknown_org", "no_email", "garbage"])
def test_s2_a_forged_or_stale_widget_token_is_refused(c, appmod, bad):
    if bad == "forged":
        h = widget(appmod, secret="not-the-secret")
    elif bad == "tampered":
        body, sig = widget(appmod)["X-Widget-Token"].split(".")
        other = appmod.sign_widget_token({"org": "globex", "email": "layla@acme.test", "exp": T0.timestamp() + 600}, SECRET).split(".")[0]
        h = {"X-Widget-Token": f"{other}.{sig}"}
    elif bad == "expired":
        h = widget(appmod, exp=T0.timestamp() - 1)
    elif bad == "unknown_org":
        h = widget(appmod, org="initech")
    elif bad == "no_email":
        h = widget(appmod, email="")
    else:
        h = {"X-Widget-Token": "not.a-token"}
    assert c.post("/api/tickets", json={"title": "From the widget"}, headers=h).status_code == 401
    assert c.get("/api/tickets", headers=h).status_code == 401


def test_s2_the_widget_token_cannot_claim_a_staff_role(c, appmod):
    k = file_ticket(c)["key"]
    h = {**widget(appmod, email="nousheed@acme.test"), "X-Role": "support", "X-Support-Token": STAFF}
    assert c.post(f"/api/tickets/{k}/transition", json={"to": "open"}, headers=h).status_code == 409
    assert "messages" in c.get(f"/api/tickets/{k}", headers=h).json() and "org" not in c.get(f"/api/tickets/{k}", headers=h).json()


def test_s2_no_secret_configured_means_no_widget(c, env, appmod):
    env.setattr(appmod, "WIDGET_SECRET", "")
    assert c.post("/api/tickets", json={"title": "From the widget"}, headers=widget(appmod)).status_code == 401


def test_s2_the_widget_script_is_served_and_cors_allows_its_header(c):
    r = c.get("/widget.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"] and "X-Widget-Token" in r.text
    pre = c.options("/api/tickets", headers={"Origin": "https://app.acme.test", "Access-Control-Request-Method": "POST",
                                              "Access-Control-Request-Headers": "x-widget-token,content-type"})
    assert pre.status_code == 200 and "x-widget-token" in pre.headers["access-control-allow-headers"].lower()
    pre = c.options("/api/tickets", headers={"Origin": "https://evil.test", "Access-Control-Request-Method": "POST",
                                              "Access-Control-Request-Headers": "x-support-token"})
    assert pre.status_code == 400, "a staff token is never sent cross-origin"


# ---------------- S3: drafts ----------------
def test_s3_the_agent_drafts_and_a_draft_reaches_the_customer_only_when_support_sends_it(c):
    k = file_ticket(c)["key"]
    ag = staff("agent", "Support Agent")
    r = c.post(f"/api/tickets/{k}/messages", json={"text": "Use Export ▸ PDF (guide §3.2)"}, headers=ag)
    assert r.status_code == 200 and r.json()["messages"][-1]["visibility"] == "draft"
    assert c.get(f"/api/tickets/{k}", headers=cust()).json()["messages"] == []
    mid = draft_id(c, k)
    assert c.post(f"/api/tickets/{k}/messages/{mid}/send", json={}, headers=ag).status_code == 403
    assert c.post(f"/api/tickets/{k}/messages/{mid}", json={"text": "Use Export ▸ PDF (see guide §3.2)."}, headers=staff()).status_code == 200
    assert c.get(f"/api/tickets/{k}", headers=cust()).json()["messages"] == [], "an edited draft is still a draft"
    sent = c.post(f"/api/tickets/{k}/messages/{mid}/send", json={}, headers=staff())
    assert sent.status_code == 200
    m = sent.json()["messages"][-1]
    assert (m["visibility"], m["by"], m["draftedBy"], m["text"]) == ("public", "Sam", "Support Agent", "Use Export ▸ PDF (see guide §3.2).")
    assert sent.json()["firstResponseAt"] == m["at"]
    assert c.get(f"/api/tickets/{k}", headers=cust()).json()["messages"] == [{"at": m["at"], "by": "Sam", "text": m["text"], "screenshots": []}]
    assert c.post(f"/api/tickets/{k}/messages/{mid}/send", json={}, headers=staff()).status_code == 404, "sent once"


def test_s3_the_agent_role_can_only_draft_categorise_and_note(c):
    k = file_ticket(c)["key"]
    ag = staff("agent", "Support Agent")
    assert c.post(f"/api/tickets/{k}/messages", json={"text": "hi", "visibility": "public"}, headers=ag).status_code == 403
    for to in STATUS_ALL:
        assert move(c, k, to, ag, issueRef="IS-1").status_code == 403
    assert c.post(f"/api/tickets/{k}/fields", json={"priority": "urgent"}, headers=ag).status_code == 403
    assert c.post(f"/api/tickets/{k}/fields", json={"category": "defect"}, headers=ag).json()["category"] == "defect"
    r = c.post(f"/api/tickets/{k}/messages", json={"text": "New defect: export job drops rows", "visibility": "internal", "tag": "recommend_escalation"}, headers=ag)
    assert r.status_code == 200 and r.json()["messages"][-1]["tag"] == "recommend_escalation"
    doc = c.get(f"/api/tickets/{k}", headers=staff()).json()
    assert doc["status"] == "new" and doc["escalation"] is None and doc["firstResponseAt"] == ""
    assert c.post(f"/api/tickets/{k}/messages", json={"text": "x", "visibility": "draft"}, headers=cust()).status_code == 403


def test_s3_the_agents_queue_is_new_and_open_tickets_nobody_has_answered(c, appmod):
    a = file_ticket(c, title="Needs a draft")["key"]
    b = file_ticket(c, title="Has a draft")["key"]
    d = file_ticket(c, title="Agent noted")["key"]
    e = file_ticket(c, title="Waiting")["key"]
    ag = staff("agent", "Support Agent")
    c.post(f"/api/tickets/{b}/messages", json={"text": "draft"}, headers=ag)
    c.post(f"/api/tickets/{d}/messages", json={"text": "recommend", "visibility": "internal"}, headers=ag)
    move(c, e, "waiting_on_customer")
    queue = lambda: [t["key"] for t in c.get("/api/tickets?needsDraft=true", headers=ag).json()]
    assert queue() == [a]
    appmod.clock.t = T0 + timedelta(minutes=5)
    c.post(f"/api/tickets/{e}/messages", json={"text": "here is the month"}, headers=cust())
    assert sorted(queue()) == sorted([a, e]), "a customer answer puts it back in the queue"


# ---------------- S4: the state machine ----------------
STATUS_ALL = ["new", "open", "waiting_on_customer", "escalated", "resolved", "closed"]


def test_s4_support_walks_the_machine_and_every_move_is_in_history(c):
    k = file_ticket(c)["key"]
    for to in ("open", "waiting_on_customer", "open", "escalated", "resolved"):
        r = move(c, k, to, issueRef="IS-512")
        assert r.status_code == 200, (to, r.text)
    h = c.get(f"/api/tickets/{k}", headers=staff()).json()["history"]
    assert [(x["from"], x["to"]) for x in h] == [("", "new"), ("new", "open"), ("open", "waiting_on_customer"),
                                                 ("waiting_on_customer", "open"), ("open", "escalated"), ("escalated", "resolved")]
    assert all(x["by"] == "Sam" and x["role"] == "support" for x in h[1:])


def test_s4_support_cannot_close_or_leave_closed(c):
    k = file_ticket(c)["key"]
    assert move(c, k, "closed").status_code == 409
    move(c, k, "resolved")
    assert move(c, k, "closed").status_code == 409
    move(c, k, "closed", cust())
    assert move(c, k, "open").status_code == 409


def test_s4_escalation_needs_an_issue_ref_and_stays_on_the_support_side(c):
    k = file_ticket(c)["key"]
    assert move(c, k, "escalated").status_code == 400
    doc = move(c, k, "escalated", issueRef="IS-512", note="export job").json()
    assert doc["status"] == "escalated"
    assert doc["escalation"] == {**doc["escalation"], "by": "Sam", "issueRef": "IS-512", "verdict": "", "verdictAt": ""}
    assert move(c, k, "escalated", h=cust()).status_code == 409


def test_s4_the_customer_may_only_answer_confirm_or_reopen(c):
    k = file_ticket(c)["key"]
    for to in ("open", "waiting_on_customer", "escalated", "resolved", "closed"):
        assert move(c, k, to, cust(), issueRef="IS-1").status_code == 409
    move(c, k, "waiting_on_customer")
    r = c.post(f"/api/tickets/{k}/messages", json={"text": "It was August"}, headers=cust())
    assert r.json()["status"] == "open" and r.json()["history"][-1] == {**r.json()["history"][-1], "from": "waiting_on_customer", "to": "open", "by": "Nousheed"}
    assert c.post("/api/tickets", json={"title": "Filed by support"}, headers=staff()).status_code == 403


def test_s4_admin_may_set_any_status(c):
    k = file_ticket(c)["key"]
    adm = staff("admin", "Owner")
    assert move(c, k, "closed", adm).json()["status"] == "closed"
    assert move(c, k, "open", adm).json()["status"] == "open", "admin reopens in place"
    assert move(c, k, "escalated", adm, issueRef="IS-9").json()["escalation"]["issueRef"] == "IS-9"


def test_uploads_are_images_only(c):
    assert c.post("/api/uploads", files={"file": ("x.txt", io.BytesIO(b"hi"), "text/plain")}, headers=cust()).status_code == 415


# ---------------- S8: confirm, reopen, auto-close (clock seam) ----------------
def test_s8_the_customer_confirms_a_fix(c):
    k = file_ticket(c)["key"]
    move(c, k, "resolved")
    r = move(c, k, "closed", cust())
    assert r.status_code == 200 and r.json()["status"] == "closed"


def test_s8_the_customer_reopens_a_resolved_ticket_with_a_reason(c):
    k = file_ticket(c)["key"]
    move(c, k, "resolved")
    assert move(c, k, "open", cust()).status_code == 400
    r = move(c, k, "open", cust(), note="Still blank on Safari")
    assert r.json()["status"] == "open" and r.json()["messages"][-1]["text"] == "Still blank on Safari"


def test_s8_reopening_a_closed_ticket_starts_a_new_one_linked_to_it(c):
    k = file_ticket(c)["key"]
    move(c, k, "resolved")
    move(c, k, "closed", cust())
    r = move(c, k, "open", cust(), note="Back again after the update")
    new = r.json()
    assert r.status_code == 200 and new["key"] != k and new["status"] == "new" and new["reopenedFrom"] == k
    assert new["description"] == "Back again after the update"
    old = c.get(f"/api/tickets/{k}", headers=cust()).json()
    assert old["status"] == "closed" and old["reopenedAs"] == new["key"]
    assert c.post(f"/api/tickets/{k}/messages", json={"text": "hi"}, headers=cust()).status_code == 409


def test_s8_an_unanswered_resolved_ticket_auto_closes_after_the_configured_days(c, appmod):
    k = file_ticket(c)["key"]
    other = file_ticket(c, title="Answered in time")["key"]
    move(c, k, "resolved")
    move(c, other, "resolved")
    appmod.clock.t = T0 + timedelta(days=3)
    c.post(f"/api/tickets/{other}/messages", json={"text": "Not quite"}, headers=cust())
    appmod.clock.t = T0 + timedelta(days=7) - timedelta(seconds=1)
    assert c.get(f"/api/tickets/{k}", headers=cust()).json()["status"] == "resolved"
    appmod.clock.t = T0 + timedelta(days=7, seconds=1)
    assert c.get(f"/api/tickets/{k}", headers=cust()).json()["status"] == "closed"
    h = c.get(f"/api/tickets/{k}", headers=staff()).json()["history"][-1]
    assert (h["by"], h["role"], h["from"], h["to"]) == ("auto-close", "system", "resolved", "closed")
    assert c.get(f"/api/tickets/{other}", headers=staff()).json()["status"] == "open", "a customer answer is not 'unanswered'"
    assert c.get("/api/stats", headers=staff()).json()["byStatus"] == {"closed": 1, "open": 1}


def test_s8_auto_close_zero_days_is_off(c, env, appmod):
    env.setattr(appmod, "AUTO_CLOSE_DAYS", 0)
    k = file_ticket(c)["key"]
    move(c, k, "resolved")
    appmod.clock.t = T0 + timedelta(days=400)
    assert c.get(f"/api/tickets/{k}", headers=staff()).json()["status"] == "resolved"


def test_the_clock_seam_is_the_only_reader_of_time():
    src = (ROOT / "support" / "app.py").read_text()
    assert src.count("datetime.now(") == 1 and "time.time(" not in src and "import time" not in src
    assert "datetime.now(" not in (ROOT / "tools" / "support_cli.py").read_text()
