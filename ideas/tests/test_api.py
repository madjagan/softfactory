"""Ideas portal API: org isolation, the four sources, curation, votes, the state machine, drafts."""
import importlib
import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8cfc000000301010018dd8db00000000049454e44ae426082")
MARKER = "ZQX-acme-secret-7731"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("IDEAS_DATA", str(tmp_path))
    monkeypatch.setenv("IDEAS_ORGS", "acme,globex")
    monkeypatch.setenv("IDEAS_TOKEN_ACME", "tok-acme")
    monkeypatch.setenv("IDEAS_TOKEN_GLOBEX", "tok-globex")
    monkeypatch.delenv("IDEAS_TOKEN", raising=False)
    import ideas.app as appmod
    importlib.reload(appmod)
    with TestClient(appmod.app) as c:
        yield c


def cust(org="acme", name="Nousheed"):
    return {"X-Role": "customer", "X-Ideas-Token": f"tok-{org}", "X-Actor": name}


def team(role="product", name="Owner"):
    return {"X-Role": role, "X-Actor": name}


AGENT = team("agent", "Ideas Agent")


def ok(r, code=200):
    assert r.status_code == code, r.text
    return r.json()


def submit(c, org="acme", name="Nousheed", text="Export the ledger to CSV please"):
    return ok(c.post("/api/portal/submissions", json={"text": text}, headers=cust(org, name)), 201)


def promote(c, key, title="Export ledger data", problem="Teams need ledger data outside the app"):
    return ok(c.post(f"/api/submissions/{key}/promote", json={"title": title, "problem": problem}, headers=AGENT), 201)


def draft_public(c, idea, title="Export your ledger", desc="Download ledger entries as a spreadsheet file."):
    ok(c.post(f"/api/ideas/{idea}/edit", json={"publicTitle": title, "publicDescription": desc}, headers=AGENT))


def move(c, idea, to, headers=None, **body):
    return c.post(f"/api/ideas/{idea}/transition", json={"to": to, **body}, headers=headers or team())


def published_idea(c, text=f"Export the ledger to CSV please {MARKER}", name="Layla"):
    s = submit(c, "acme", name, text)
    i = promote(c, s["key"])["key"]
    draft_public(c, i)
    ok(move(c, i, "under_review", AGENT))
    ok(c.post(f"/api/ideas/{i}/publish", json={}, headers=team()))
    return s, i


# ---------------- I1 — a customer sees only their own org's submissions ----------------
def test_I1_org_b_never_sees_org_a_submissions(client):
    up = ok(client.post("/api/uploads", files={"file": ("s.png", io.BytesIO(PNG), "image/png")}, headers=cust("acme")), 201)["id"]
    a = ok(client.post("/api/portal/submissions", json={"text": f"Bulk edit please {MARKER}", "screenshots": [up]}, headers=cust("acme")), 201)
    submit(client, "globex", "Gary", "Dark mode")
    mine = ok(client.get("/api/portal/submissions", headers=cust("acme")))
    assert [s["key"] for s in mine] == [a["key"]] and mine[0]["screenshots"] == [up]
    theirs = client.get("/api/portal/submissions", headers=cust("globex"))
    assert [s["requester"] for s in theirs.json()] == ["Gary"] and MARKER not in theirs.text
    assert client.get(f"/api/portal/submissions/{a['key']}", headers=cust("globex")).status_code == 404
    assert client.get(f"/uploads/{up}", headers=cust("globex")).status_code == 404
    assert client.get(f"/uploads/{up}", headers=cust("acme")).status_code == 200
    # globex cannot attach acme's screenshot to its own submission
    g = ok(client.post("/api/portal/submissions", json={"text": "Steal a screenshot", "screenshots": [up]}, headers=cust("globex")), 201)
    assert g["screenshots"] == []


def test_I1_tokens_decide_the_org_and_customers_never_reach_the_team_api(client):
    assert client.get("/api/portal/submissions", headers={"X-Role": "customer", "X-Actor": "x"}).status_code == 401
    assert client.get("/api/portal/submissions", headers={"X-Role": "customer", "X-Ideas-Token": "guess"}).status_code == 401
    assert client.get("/api/portal/submissions", headers={**cust("globex"), "X-Org": "acme"}).json() == []
    submit(client, "acme", text=f"Private {MARKER}")
    for path in ("/api/submissions", "/api/ideas", "/api/submissions/IDR-1"):
        assert client.get(path, headers=cust("globex")).status_code == 403
    assert client.get("/api/submissions", headers={**cust("globex"), "X-Role": "product"}).status_code == 403
    assert "orgs" not in ok(client.get("/api/meta", headers=cust("globex")))


def test_I1_internal_notes_on_behalf_of_an_org_stay_internal(client):
    ok(client.post("/api/submissions", json={"source": "internal", "org": "acme", "text": f"Heard on a call {MARKER}"}, headers=team()), 201)
    r = client.get("/api/portal/submissions", headers=cust("acme"))
    assert r.json() == [] and MARKER not in r.text
    assert client.get("/api/portal/submissions/IDR-1", headers=cust("acme")).status_code == 404


# ---------------- I2 — all four sources land in intake with their ref ----------------
def test_I2_portal_submission_lands_in_intake(client):
    s = submit(client)
    doc = ok(client.get(f"/api/submissions/{s['key']}", headers=AGENT))
    assert (doc["key"], doc["source"], doc["org"], doc["requester"], doc["idea"]) == ("IDR-1", "portal", "acme", "Nousheed", None)
    assert [x["key"] for x in ok(client.get("/api/submissions?intake=true", headers=AGENT))] == ["IDR-1"]
    assert s["status"] == "received"
    assert client.post("/api/portal/submissions", json={"text": "no name"}, headers={**cust(), "X-Actor": ""}).status_code == 400


def test_I2_internal_submission_carries_the_staff_name_and_optional_org(client):
    a = ok(client.post("/api/submissions", json={"source": "internal", "text": "Sales keep hearing about SSO"}, headers=team("product", "Maya")), 201)
    b = ok(client.post("/api/submissions", json={"source": "internal", "org": "globex", "text": "Globex asked for SSO on the call"}, headers=team()), 201)
    assert (a["source"], a["requester"], a["org"], a["idea"]) == ("internal", "Maya", None, None)
    assert b["org"] == "globex"
    assert client.post("/api/submissions", json={"source": "internal", "text": "Agent cannot log calls"}, headers=AGENT).status_code == 403
    assert client.post("/api/submissions", json={"source": "internal", "org": "initech", "text": "Unknown org"}, headers=team()).status_code == 400


def test_I2_tracker_submission_keeps_its_issue_key_once(client):
    body = {"source": "tracker", "sourceRef": "IS-612", "requester": "Priya", "text": "Filter the ledger by date range"}
    doc = ok(client.post("/api/submissions", json=body, headers=AGENT), 201)
    assert (doc["source"], doc["sourceRef"], doc["idea"]) == ("tracker", "IS-612", None)
    assert client.post("/api/submissions", json=body, headers=AGENT).status_code == 409
    board = ok(client.post("/api/submissions", json={**body, "sourceRef": "acme/ACME-501", "org": "acme"}, headers=AGENT), 201)
    assert board["sourceRef"] == "acme/ACME-501" and board["org"] == "acme"
    assert client.post("/api/submissions", json={**body, "sourceRef": ""}, headers=AGENT).status_code == 400


def test_I2_support_submission_keeps_its_ticket_key(client):
    doc = ok(client.post("/api/submissions", json={"source": "support", "sourceRef": "SUP-1042", "org": "acme", "requester": "Nousheed",
                                                   "text": "Can we schedule exports?"}, headers=AGENT), 201)
    assert (doc["source"], doc["sourceRef"], doc["org"], doc["idea"]) == ("support", "SUP-1042", "acme", None)
    assert ok(client.get("/api/submissions?intake=true&source=support", headers=AGENT))[0]["key"] == doc["key"]
    assert client.post("/api/submissions", json={"source": "portal", "text": "Team cannot fake a portal one"}, headers=team()).status_code == 400


# ---------------- I3 — attach, promote, recommend already built / merge ----------------
def test_I3_promote_then_attach_a_second_submission(client):
    s1, s2 = submit(client), submit(client, "globex", "Gary", "CSV export of entries")
    idea = promote(client, s1["key"])
    assert (idea["key"], idea["status"], idea["submissions"]) == ("IDEA-1", "new", [s1["key"]])
    assert client.post(f"/api/submissions/{s1['key']}/promote", json={"title": "Again"}, headers=AGENT).status_code == 409
    out = ok(client.post(f"/api/submissions/{s2['key']}/attach", json={"idea": "IDEA-1", "note": "same export ask"}, headers=AGENT))
    assert out["idea"]["submissions"] == [s1["key"], s2["key"]] and out["submission"]["idea"] == "IDEA-1"
    assert ok(client.get("/api/submissions?intake=true", headers=AGENT)) == []
    # moving a linked submission to another idea is the product team's call
    other = promote(client, ok(client.post("/api/submissions", json={"source": "internal", "text": "Something else"}, headers=team()), 201)["key"], "Other")["key"]
    assert client.post(f"/api/submissions/{s2['key']}/attach", json={"idea": other}, headers=AGENT).status_code == 409
    ok(client.post(f"/api/submissions/{s2['key']}/attach", json={"idea": other}, headers=team()))
    assert ok(client.get("/api/ideas/IDEA-1", headers=AGENT))["submissions"] == [s1["key"]]
    assert client.post(f"/api/submissions/{s1['key']}/promote", json={"title": "Customer cannot"}, headers=cust()).status_code == 403


def test_I3_agent_recommends_already_built_and_merge_without_deciding(client):
    a = promote(client, submit(client)["key"])["key"]
    b = promote(client, submit(client, "globex", "Gary", "CSV please")["key"], "CSV export")["key"]
    assert client.post(f"/api/ideas/{a}/recommend", json={"kind": "already_built", "featureId": "nope"}, headers=AGENT).status_code == 400
    ok(client.post(f"/api/ideas/{a}/recommend", json={"kind": "already_built", "featureId": "LED-04", "note": "Reports → Export"}, headers=AGENT))
    doc = ok(client.post(f"/api/ideas/{b}/recommend", json={"kind": "merge", "mergedInto": a, "note": "same ask"}, headers=AGENT))
    assert doc["status"] == "new" and doc["recommendations"][-1] == {**doc["recommendations"][-1], "kind": "merge", "mergedInto": a}
    assert ok(client.get(f"/api/ideas/{a}", headers=AGENT))["recommendations"][0]["featureId"] == "LED-04"
    assert client.post(f"/api/ideas/{b}/recommend", json={"kind": "merge", "mergedInto": b}, headers=AGENT).status_code == 409
    assert move(client, a, "already_built", AGENT, featureId="LED-04").status_code == 409
    assert move(client, b, "merged", AGENT, mergedInto=a).status_code == 409


def test_I3_product_merges_moving_submissions_and_votes(client):
    s, a = published_idea(client)
    b_sub = submit(client, "globex", "Gary", "CSV please")
    b = promote(client, b_sub["key"], "CSV export")["key"]
    draft_public(client, b, "Spreadsheet export", "Get entries out as CSV.")
    ok(client.post(f"/api/ideas/{b}/publish", json={}, headers=team()))
    ok(client.post(f"/api/portal/ideas/{a}/vote", headers=cust("globex", "Gary")))
    ok(client.post(f"/api/portal/ideas/{b}/vote", headers=cust("globex", "Gary")))
    ok(client.post(f"/api/portal/ideas/{b}/vote", headers=cust("globex", "Hana")))
    doc = ok(move(client, b, "merged", mergedInto=a, note="same ask"))
    assert doc["status"] == "merged" and doc["mergedInto"] == a and doc["submissions"] == []
    target = ok(client.get(f"/api/ideas/{a}", headers=team()))
    assert target["submissions"] == [s["key"], b_sub["key"]] and target["demand"]["votes"] == 2
    assert ok(client.get(f"/api/submissions/{b_sub['key']}", headers=team()))["idea"] == a
    assert [i["key"] for i in ok(client.get("/api/portal/ideas", headers=cust("globex")))] == [a]
    assert client.post(f"/api/portal/ideas/{b}/vote", headers=cust("globex", "Gary")).status_code == 404


# ---------------- I4 — demand per idea, sortable ----------------
def test_I4_demand_counts_orgs_people_votes_tickets_issues_and_sorts(client):
    s, a = published_idea(client)
    ok(client.post(f"/api/submissions/{submit(client, 'acme', 'Nousheed', 'Export as CSV')['key']}/attach", json={"idea": a}, headers=AGENT))
    for src, ref, org in (("support", "SUP-1", "globex"), ("tracker", "IS-612", None)):
        k = ok(client.post("/api/submissions", json={"source": src, "sourceRef": ref, "org": org or "", "requester": "Pat", "text": "CSV export"}, headers=AGENT), 201)["key"]
        ok(client.post(f"/api/submissions/{k}/attach", json={"idea": a}, headers=AGENT))
    ok(client.post(f"/api/portal/ideas/{a}/vote", headers=cust("globex", "Gary")))
    ok(client.post(f"/api/portal/ideas/{a}/vote", headers=cust("acme", "Layla")))
    small = promote(client, submit(client, "globex", "Gary", "Dark mode")["key"], "Dark mode")["key"]
    d = ok(client.get(f"/api/ideas/{a}", headers=team()))["demand"]
    assert d == {"orgs": 2, "people": 5, "votes": 2, "tickets": 1, "issues": 1, "submissions": 4}
    for key in ("orgs", "people", "votes", "tickets", "issues"):
        assert [i["key"] for i in ok(client.get(f"/api/ideas?sort={key}", headers=team()))] == [a, small]
    assert client.get("/api/ideas?sort=size", headers=team()).status_code == 400


# ---------------- I5 — only product publishes; no submission text, requester or org on a published idea ----------------
def test_I5_only_product_publishes(client):
    i = promote(client, submit(client)["key"])["key"]
    draft_public(client, i)
    assert client.post(f"/api/ideas/{i}/publish", json={}, headers=AGENT).status_code == 403
    assert client.post(f"/api/ideas/{i}/publish", json={}, headers=cust()).status_code == 403
    assert ok(client.get("/api/portal/ideas", headers=cust())) == []
    doc = ok(client.post(f"/api/ideas/{i}/publish", json={}, headers=team()))
    assert doc["public"]["title"] == "Export your ledger" and doc["history"][-1]["note"] == "Published"


def test_I5_public_text_refuses_names_orgs_and_verbatim_wording(client):
    s = submit(client, "acme", "Layla", "Export the ledger to CSV please")
    i = promote(client, s["key"])["key"]
    for title, desc in (("Export for Layla", "x x x"), ("Export", "As Acme asked"), ("Export", "They said: export the ledger to CSV please")):
        r = client.post(f"/api/ideas/{i}/publish", json={"title": title, "description": desc}, headers=team())
        assert r.status_code == 400, (title, desc)
    assert client.post(f"/api/ideas/{i}/publish", json={"title": "Export your ledger"}, headers=team()).status_code == 400


def test_I5_a_planted_marker_never_reaches_any_customer_response(client):
    up = ok(client.post("/api/uploads", files={"file": ("s.png", io.BytesIO(PNG), "image/png")}, headers=cust("acme", "Layla")), 201)["id"]
    s = ok(client.post("/api/portal/submissions", json={"text": f"Export the ledger to CSV please {MARKER}", "screenshots": [up]},
                       headers=cust("acme", f"Layla{MARKER}")), 201)
    i = promote(client, s["key"], title=f"Export for {MARKER}", problem=f"{MARKER} needs export")["key"]
    draft_public(client, i)
    ok(move(client, i, "under_review", AGENT))
    ok(client.post(f"/api/ideas/{i}/recommend", json={"kind": "publish", "note": MARKER}, headers=AGENT))
    ok(client.post(f"/api/ideas/{i}/drafts", json={"to": s["key"], "text": f"Draft {MARKER}"}, headers=AGENT), 201)
    ok(client.post(f"/api/ideas/{i}/publish", json={}, headers=team()))
    ok(client.post(f"/api/portal/ideas/{i}/vote", headers=cust("acme", f"Voter{MARKER}")))
    responses = []
    for org in ("acme", "globex"):
        h = cust(org, "Gary")
        responses += [client.get("/api/portal/ideas", headers=h), client.get("/api/meta", headers=h),
                      client.post(f"/api/portal/ideas/{i}/vote", headers=h), client.post(f"/api/portal/ideas/{i}/vote", headers=h)]
    responses += [client.get("/api/portal/submissions", headers=cust("globex")),
                  client.get(f"/api/portal/submissions/{s['key']}", headers=cust("globex"))]
    for r in responses:
        assert MARKER not in r.text and up not in r.text, r.text
    pub = ok(client.get("/api/portal/ideas", headers=cust("globex")))[0]
    assert set(pub) == {"key", "title", "description", "status", "statusNote", "publishedAt", "votes", "voted"}
    # acme's own view links the submission to the public face only
    own = ok(client.get(f"/api/portal/submissions/{s['key']}", headers=cust("acme")))
    assert own["idea"] == {"key": i, "title": "Export your ledger"} and own["notices"] == []


# ---------------- I6 — one vote per user per published idea; a toggle; no voter names ----------------
def test_I6_voting_toggles_and_counts_without_naming_voters(client):
    _, i = published_idea(client)
    v = ok(client.post(f"/api/portal/ideas/{i}/vote", headers=cust("globex", "Gary")))
    assert (v["votes"], v["voted"]) == (1, True)
    assert ok(client.post(f"/api/portal/ideas/{i}/vote", headers=cust("globex", "gary ")))["votes"] == 0
    ok(client.post(f"/api/portal/ideas/{i}/vote", headers=cust("globex", "Gary")))
    r = client.post(f"/api/portal/ideas/{i}/vote", headers=cust("acme", "Gary"))
    assert r.json()["votes"] == 2 and r.json()["voted"] is True
    seen = client.get("/api/portal/ideas", headers=cust("acme", "Layla"))
    assert seen.json()[0]["votes"] == 2 and seen.json()[0]["voted"] is False and "Gary" not in seen.text
    assert [v["user"] for v in ok(client.get(f"/api/ideas/{i}", headers=team()))["voters"]] == ["gary", "gary"]
    unpublished = promote(client, submit(client)["key"])["key"]
    assert client.post(f"/api/portal/ideas/{unpublished}/vote", headers=cust("acme", "Gary")).status_code == 404
    assert client.post(f"/api/portal/ideas/{i}/vote", headers={**cust("acme"), "X-Actor": ""}).status_code == 400
    assert client.post(f"/api/portal/ideas/{i}/vote", headers=AGENT).status_code == 403


# ---------------- I7 — only product accepts or declines; accepting records the PRD § ----------------
def test_I7_only_product_accepts_and_declines(client):
    i = promote(client, submit(client)["key"])["key"]
    draft_public(client, i)
    ok(move(client, i, "under_review", AGENT))
    assert move(client, i, "accepted", AGENT, prdRef="3.14").status_code == 409
    assert move(client, i, "declined", AGENT, note="no").status_code == 409
    assert move(client, i, "accepted", cust()).status_code == 403
    assert move(client, i, "accepted").status_code == 400
    doc = ok(move(client, i, "accepted", prdRef="§3.14", featureId="LED-07"))
    assert (doc["status"], doc["prdRef"], doc["featureId"]) == ("accepted", "3.14", "LED-07")
    j = promote(client, submit(client, text="Dark mode")["key"], "Dark mode")["key"]
    assert move(client, j, "declined").status_code == 400
    assert ok(move(client, j, "declined", note="not our market"))["status"] == "declined"


def test_I7_a_declined_published_idea_stays_visible_as_not_planned_with_a_public_reason(client):
    _, i = published_idea(client)
    assert move(client, i, "declined", note="internal reason").status_code == 400
    ok(move(client, i, "declined", note="internal reason", statusNote="We are focusing on reconciliation this year."))
    pub = ok(client.get("/api/portal/ideas", headers=cust("globex")))[0]
    assert (pub["status"], pub["statusNote"]) == ("not planned", "We are focusing on reconciliation this year.")
    assert "internal reason" not in client.get("/api/portal/ideas", headers=cust("globex")).text
    assert ok(client.get("/api/portal/submissions", headers=cust("acme")))[0]["status"] == "not planned"


def test_I7_already_built_needs_a_feature_id(client):
    i = promote(client, submit(client)["key"])["key"]
    assert move(client, i, "already_built").status_code == 400
    assert ok(move(client, i, "already_built", featureId="LED-04"))["featureId"] == "LED-04"
    assert ok(client.get("/api/portal/submissions", headers=cust()))[0]["status"] == "already available"


# ---------------- I8 — after acceptance, the agent applies ledger statuses with a citation ----------------
def test_I8_ledger_statuses_are_the_agents_and_need_a_citation(client):
    i = promote(client, submit(client)["key"])["key"]
    ok(move(client, i, "accepted", prdRef="3.14", featureId="LED-07"))
    assert move(client, i, "in_development", AGENT).status_code == 400
    assert move(client, i, "shipped", AGENT, citation="x").status_code == 409
    doc = ok(move(client, i, "in_development", AGENT, citation="IMPLEMENTATION_PLAN.md §3.14 row: In progress (2026-10-01)"))
    assert doc["history"][-1]["citation"].startswith("IMPLEMENTATION_PLAN.md")
    assert ok(client.get("/api/portal/submissions", headers=cust()))[0]["status"] == "in development"
    ok(move(client, i, "shipped", AGENT, citation="FEATURE_LIST.md LED-07 ●; RELEASE_LOG.md 1.4.0 — 2026-10-15"))
    assert ok(client.get("/api/portal/submissions", headers=cust()))[0]["status"] == "shipped"


# ---------------- I9 — notices are drafts until product sends them ----------------
def test_I9_drafts_reach_the_customer_only_when_product_sends_them(client):
    s, i = published_idea(client)
    other = submit(client, "acme", "Nousheed", "Export as CSV too")
    ok(client.post(f"/api/submissions/{other['key']}/attach", json={"idea": i}, headers=AGENT))
    t = ok(client.post("/api/submissions", json={"source": "support", "sourceRef": "SUP-1042", "org": "globex", "requester": "Gary", "text": "CSV?"}, headers=AGENT), 201)
    ok(client.post(f"/api/submissions/{t['key']}/attach", json={"idea": i}, headers=AGENT))
    ok(move(client, i, "accepted", prdRef="3.14", featureId="LED-07"))
    ok(move(client, i, "in_development", AGENT, citation="plan"))
    ok(move(client, i, "shipped", AGENT, citation="release"))
    ok(client.post(f"/api/ideas/{i}/drafts", json={"to": s["key"], "text": "Ledger export shipped in 1.4.0: Reports → Export."}, headers=AGENT), 201)
    ok(client.post(f"/api/ideas/{i}/drafts", json={"to": "SUP-1042", "text": "Support: tell Gary export is live."}, headers=AGENT), 201)
    assert client.post(f"/api/ideas/{i}/drafts", json={"to": "SUP-9999", "text": "Unlinked ticket"}, headers=AGENT).status_code == 400
    for org in ("acme", "globex"):
        for path in ("/api/portal/submissions", "/api/portal/ideas"):
            r = client.get(path, headers=cust(org))
            assert "shipped in 1.4.0" not in r.text and "Support: tell" not in r.text
    assert client.post(f"/api/ideas/{i}/drafts/0/send", headers=AGENT).status_code == 403
    sent = ok(client.post(f"/api/ideas/{i}/drafts/0/send", headers=team()))
    assert sent["drafts"][0]["sentAt"] and sent["drafts"][1]["sentAt"] is None
    assert client.post(f"/api/ideas/{i}/drafts/0/send", headers=team()).status_code == 409
    mine = {x["key"]: x for x in ok(client.get("/api/portal/submissions", headers=cust("acme")))}
    assert [n["text"] for n in mine[s["key"]]["notices"]] == ["Ledger export shipped in 1.4.0: Reports → Export."]
    assert mine[other["key"]]["notices"] == [] and mine[s["key"]]["status"] == "shipped"
    assert "shipped in 1.4.0" not in client.get("/api/portal/submissions", headers=cust("globex")).text


# ---------------- I10 — history for every move; the state machine per role ----------------
def test_I10_the_state_machine_per_role_and_history(client):
    i = promote(client, submit(client)["key"])["key"]
    assert move(client, i, "under_review", AGENT).status_code == 400, "needs the problem and a drafted public text"
    draft_public(client, i)
    assert move(client, i, "bogus", AGENT).status_code == 400
    assert move(client, i, "in_development", AGENT, citation="x").status_code == 409
    ok(move(client, i, "under_review", AGENT))
    assert move(client, i, "shipped", citation="x").status_code == 409
    ok(move(client, i, "accepted", prdRef="3.14"))
    assert move(client, i, "under_review").status_code == 409
    assert move(client, i, "declined", note="late").status_code == 409
    ok(move(client, i, "in_development", citation="plan row"))
    assert move(client, i, "accepted", prdRef="3.15").status_code == 409
    doc = ok(move(client, i, "new", team("admin", "Op")))
    moves = [(h["from"], h["to"], h["role"]) for h in doc["history"] if h["from"] != h["to"]]
    assert moves == [("", "new", "agent"), ("new", "under_review", "agent"), ("under_review", "accepted", "product"),
                     ("accepted", "in_development", "product"), ("in_development", "new", "admin")]
    assert all(h["at"] and h["by"] for h in doc["history"])
    sub = ok(client.get("/api/submissions/IDR-1", headers=team()))
    assert [(h["from"], h["to"]) for h in sub["history"]] == [("", "intake"), ("intake", i)]


def test_I10_team_token_gate_and_org_tokens_cannot_act_as_the_team(tmp_path, monkeypatch):
    monkeypatch.setenv("IDEAS_DATA", str(tmp_path))
    monkeypatch.setenv("IDEAS_ORGS", "acme")
    monkeypatch.setenv("IDEAS_TOKEN_ACME", "tok-acme")
    monkeypatch.setenv("IDEAS_TOKEN", "team-s3cret")
    import ideas.app as appmod
    importlib.reload(appmod)
    with TestClient(appmod.app) as c:
        assert c.get("/api/ideas", headers=team()).status_code == 401
        assert c.get("/api/ideas", headers={**team(), "X-Ideas-Token": "team-s3cret"}).status_code == 200
        assert c.get("/api/ideas", headers={**team(), "Authorization": "Bearer team-s3cret"}).status_code == 200
        assert c.get("/api/ideas", headers={**team("admin"), "X-Ideas-Token": "tok-acme"}).status_code == 403
        assert c.get("/api/portal/ideas", headers={"X-Role": "customer", "X-Ideas-Token": "team-s3cret"}).status_code == 401
        assert c.get("/healthz").status_code == 200
