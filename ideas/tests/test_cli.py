"""tools/ideas_cli.py against the app: ledger sync from fixture docs, the ● check, tracker gathering, accept."""
import importlib
import sys
from argparse import Namespace

import pytest
from fastapi.testclient import TestClient

from ideas.tests.test_api import AGENT, ROOT, client, cust, move, ok, promote, submit, team  # noqa: F401

sys.path.insert(0, str(ROOT / "tools"))
import ideas_cli  # noqa: E402

PLAN = """| PRD § | Feature | Test file | Acceptance | Risks | Status |
|---|---|---|---|---|---|
| 3.13 | Budgets | `t/budgets.test.ts` | … | … | ✅ Complete (2026-09-01) |
| 3.14 | Ledger export | `t/export.test.ts` | … | … | {status} |
"""
FEATURES = """| ID | Feature | Req IDs | Pri | Mat | Personas | Acceptance (short) | Deps |
|---|---|---|---|---|---|---|---|
| **LED-04** | Reports export | §3.2 | M | ● | P1 | … | — |
| **LED-07** | Ledger export | §3.14 | M | {mat} | P1 | … | — |
"""
RELEASES = """# Release Log

## 1.4.0 — 2026-10-15

- **Shipped:** §3.14, #212
{older}"""


@pytest.fixture()
def cli(client, monkeypatch):
    def fake_call(method, path, body=None, raw=False, role="agent"):
        h = team(role, "Ideas Agent" if role == "agent" else "Product")
        r = client.request(method, "/" + path, json=body, headers=h)
        if r.status_code >= 400:
            sys.exit(f"HTTP {r.status_code} {path}: {r.text}")
        return r.content if raw else r.json()
    monkeypatch.setattr(ideas_cli, "call", fake_call)
    docs = {"plan": PLAN.format(status="Planned"), "feature_list": FEATURES.format(mat="◐"), "release_log": RELEASES.format(older="")}
    monkeypatch.setattr(ideas_cli, "doc_text", lambda key: docs[key])
    return client, docs


def accepted_idea(c):
    i = promote(c, submit(c)["key"])["key"]
    ok(move(c, i, "accepted", prdRef="3.14", featureId="LED-07"))
    return i


def test_I8_ledger_move_reads_the_plan_row_then_feature_and_release_log():
    idea = {"status": "accepted", "prdRef": "3.14", "featureId": "LED-07"}
    released = RELEASES.format(older="")
    assert ideas_cli.ledger_move(idea, PLAN.format(status="Planned"), FEATURES.format(mat="◐"), released) is None
    to, cite = ideas_cli.ledger_move(idea, PLAN.format(status="In progress (2026-10-01)"), FEATURES.format(mat="◐"), released)
    assert to == "in_development" and cite == "IMPLEMENTATION_PLAN.md §3.14 row: In progress (2026-10-01)"
    idea["status"] = "in_development"
    assert ideas_cli.ledger_move(idea, "", FEATURES.format(mat="◐"), released) is None, "◐ is not shipped"
    assert ideas_cli.ledger_move(idea, "", FEATURES.format(mat="●"), "## 1.3.0 — 2026-09-01\n\n- **Shipped:** §3.13, §3.140\n") is None, "● but not released"
    to, cite = ideas_cli.ledger_move(idea, "", FEATURES.format(mat="●"), released)
    assert to == "shipped" and cite == "FEATURE_LIST.md LED-07 ●; RELEASE_LOG.md 1.4.0 — 2026-10-15"
    assert ideas_cli.ledger_move({**idea, "featureId": ""}, "", FEATURES.format(mat="●"), released) is None, "no feature id, no ship"


def test_I8_ledger_apply_moves_accepted_ideas_with_citations(cli, capsys):
    c, docs = cli
    i = accepted_idea(c)
    ideas_cli.cmd_ledger(Namespace(apply=True))
    assert ok(c.get(f"/api/ideas/{i}", headers=AGENT))["status"] == "accepted"
    docs["plan"] = PLAN.format(status="In progress (2026-10-01)")
    ideas_cli.cmd_ledger(Namespace(apply=False))
    assert ok(c.get(f"/api/ideas/{i}", headers=AGENT))["status"] == "accepted", "a dry run writes nothing"
    ideas_cli.cmd_ledger(Namespace(apply=True))
    assert ok(c.get(f"/api/ideas/{i}", headers=AGENT))["status"] == "in_development"
    docs["feature_list"] = FEATURES.format(mat="●")
    ideas_cli.cmd_ledger(Namespace(apply=True))
    doc = ok(c.get(f"/api/ideas/{i}", headers=AGENT))
    assert doc["status"] == "shipped"
    assert [(h["to"], h["role"], h.get("citation")) for h in doc["history"] if h["from"] != h["to"]][-2:] == [
        ("in_development", "agent", "IMPLEMENTATION_PLAN.md §3.14 row: In progress (2026-10-01)"),
        ("shipped", "agent", "FEATURE_LIST.md LED-07 ●; RELEASE_LOG.md 1.4.0 — 2026-10-15")]
    assert "1 ledger move(s)" in capsys.readouterr().out


def test_I3_recommend_already_built_only_for_a_live_feature(cli):
    c, _ = cli
    i = promote(c, submit(c)["key"])["key"]
    with pytest.raises(SystemExit):
        ideas_cli.cmd_recommend(Namespace(key=i, kind="already_built", feature="LED-07", into=None, note="◐ only"))
    ideas_cli.cmd_recommend(Namespace(key=i, kind="already_built", feature="LED-04", into=None, note="Reports → Export"))
    assert ok(c.get(f"/api/ideas/{i}", headers=AGENT))["recommendations"][0]["featureId"] == "LED-04"


def test_I7_accept_runs_as_product_and_records_the_prd_section(cli):
    c, _ = cli
    i = promote(c, submit(c)["key"])["key"]
    ideas_cli.cmd_accept(Namespace(key=i, prd="3.14", feature="LED-07", note="owner said yes"))
    doc = ok(c.get(f"/api/ideas/{i}", headers=AGENT))
    assert (doc["status"], doc["prdRef"], doc["history"][-1]["role"]) == ("accepted", "3.14", "product")


def test_I2_tracker_lists_feature_enhancement_and_as_speced_issues_not_yet_submitted(cli, tmp_path, monkeypatch, capsys):
    c, _ = cli
    monkeypatch.setenv("ISSUES_DATA", str(tmp_path / "issues"))
    monkeypatch.delenv("ISSUES_TOKEN", raising=False)
    import issues.app as issues_mod
    importlib.reload(issues_mod)
    with TestClient(issues_mod.app) as tracker:
        h = {"X-Actor": "Priya", "X-Role": "tester"}
        for title, kind in (("Filter by date range", "feature"), ("Bigger fonts", "enhancement"), ("Crash on save", "bug"), ("Column says Role", "bug")):
            ok(tracker.post("/api/issues", json={"title": title, "kind": kind}, headers=h), 201)
        ok(tracker.post("/api/issues/IS-504/transition", json={"to": "as_speced", "agent": {"specRef": "PRD 3.1"}}, headers={"X-Role": "agent"}))
        monkeypatch.setattr(ideas_cli, "tracker_call", lambda path: ok(tracker.get("/" + path, headers=h)))
        ideas_cli.cmd_add(Namespace(source="tracker", ref="IS-501", requester="Priya", text="Filter by date range", org=None))
        capsys.readouterr()
        ideas_cli.cmd_tracker(Namespace())
        out = capsys.readouterr().out
    assert "IS-502" in out and "IS-504" in out and "IS-501" not in out and "IS-503" not in out
    assert "2 tracker issue(s) not yet submitted" in out
    sub = ok(c.get("/api/submissions?source=tracker&intake=true", headers=AGENT))[0]
    assert (sub["sourceRef"], sub["requester"]) == ("IS-501", "Priya")
