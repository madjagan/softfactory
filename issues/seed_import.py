"""Seed the issue tracker from the issues log, so the board starts with the project's history.

  python3 issues/seed_import.py --log        # <PREFIX>-1…: every issues_log.md entry, closed

Writes straight into the app's SQLite (ISSUES_DATA, default issues/data). Re-running
replaces the same keys; tester-filed issues (ISSUES_FIRST_NUM and up) are never touched.
Paths come from factory.yaml (docs.issues_log, docs.issues_classified).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from issues import app as tracker  # noqa: E402
from factory import doc_path  # noqa: E402


def norm(t):
    return re.sub(r"\s+", " ", t.strip())[:90]


def clip(s, n=1800):
    s = (s or "").strip()
    return s if len(s) <= n else s[:n].rstrip() + " …"


LABELS = re.compile(r"^\*\*([A-Z][A-Za-z /\-'’]{2,40}?)[.:]?\*\*[ \t]*", re.M)
MAP = {
    "symptom": ["Symptom", "Reported symptom", "Issue", "Request", "Ask", "Feature", "Gap", "Problem", "Observation", "Report", "Scope"],
    "rootCause": ["Root cause", "Why it slipped", "Why no test caught it", "Cause", "Diagnosis", "Mechanism"],
    "fix": ["Fix", "Change", "Changes", "Implementation", "Resolution", "What changed"],
    "files": ["Files", "Files changed"],
    "tests": ["Acceptance", "Acceptance tests", "Acceptance test", "Tests", "Test"],
    "verification": ["Verification", "Verified", "Proof"],
}
LOOK = {l.lower(): k for k, ls in MAP.items() for l in ls}


def log_docs(log_path: Path, classified_path: Path) -> list[dict]:
    classified = {norm(e["title"]): e for e in json.load(open(classified_path))["entries"]} if classified_path.exists() else {}
    parts = re.split(r"^## ", log_path.read_text(encoding="utf-8"), flags=re.M)[1:]
    last_date, out = "1970-01-01", []
    for n, part in enumerate(parts, 1):
        if n >= tracker.FIRST_NEW_NUM:
            break  # never collide with tester-filed numbers
        head, _, body = part.partition("\n")
        head = head.strip(); date = None
        m = re.match(r"(\d{4}-\d{2}-\d{2}) — (.*)", head)
        if m:
            date, head_t = m.group(1), m.group(2)
        else:
            head_t = head
            m2 = re.search(r"\((\d{4}-\d{2}-\d{2})\)\s*$", head)
            if m2:
                date, head_t = m2.group(1), head[:m2.start()].strip()
        m3 = re.search(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", body)
        if m3:
            date = m3.group(1)
        date = date or last_date; last_date = date
        ref = re.match(r"(#\d+(?:[–-]#?\d+)?|§\d+\.\d+[a-z]?(?: [A-Z]+\d+(?:\.\d+)?)?)", head_t)
        ref = ref.group(1) if ref else ""
        title = re.sub(r"^(#\d+(?:[–-]#?\d+)?|§[\d.]+[a-z]?)\s*[—:–-]?\s*", "", head_t).strip() or head_t
        cls = classified.get(norm(head)) or classified.get(norm(head_t)) or {}
        secs = defaultdict(list)
        pos = [(mm.start(), mm.end(), mm.group(1).strip().lower()) for mm in LABELS.finditer(body)]
        preamble = body[: pos[0][0]] if pos else body
        for idx, (s, e, lab) in enumerate(pos):
            end = pos[idx + 1][0] if idx + 1 < len(pos) else len(body)
            key = LOOK.get(lab)
            if key:
                secs[key].append(body[e:end].strip())

        def sec(k):
            return clip("\n\n".join(secs[k]))

        kind = {"bug": "bug", "feature": "feature", "diagnostic": "diagnostic", "docs": "other", "other": "other"}.get(
            cls.get("kind"), "bug" if re.match(r"#\d", ref) else "feature")
        desc = sec("symptom") or clip(re.sub(r"^- \*\*(Date|Area)[^\n]*\n?", "", preamble, flags=re.M).strip(), 1200)
        if cls.get("note") and cls["note"] not in desc:
            desc = (desc + "\n\n" + cls["note"]).strip() if desc else cls["note"]
        at = date + "T00:00:00.000Z"
        agent = {k: v for k, v in {
            "rootCause": sec("rootCause"), "fix": sec("fix"), "files": sec("files"),
            "tests": sec("tests") or ("Regression test added" if cls.get("regression_test_added") else ""),
            "humanTests": sec("verification"), "processedAt": at,
        }.items() if v}
        hist = [{"at": at, "by": "import", "from": "", "to": "new", "note": f"Imported from {log_path.name}"},
                {"at": at, "by": "agent", "from": "new", "to": "fixed" if kind == "bug" else "closed", "note": ""}]
        if kind == "bug":
            hist.append({"at": at, "by": "import", "from": "fixed", "to": "closed", "note": "Verified at the time; closed on import"})
        module = cls.get("module") if cls.get("module") in tracker.MODULES else "other"
        out.append({"key": f"{tracker.PREFIX}-{n}", "num": n, "title": clip(title, 200), "description": desc, "module": module,
                    "kind": kind, "severity": "medium" if kind == "bug" else "low", "persona": "", "build": "",
                    "status": "closed", "source": "issues_log", "sourceRef": ref, "reporter": "Issues log",
                    "createdAt": at, "updatedAt": at, "screenshots": [], "agent": agent, "comments": [], "history": hist})
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log", action="store_true", help="import the issues log as closed issues")
    a = p.parse_args()
    if not a.log:
        p.print_help(); return
    tracker.init_db()
    docs = log_docs(doc_path("issues_log"), doc_path("issues_classified"))
    with tracker.tx() as con:
        for d in docs:
            tracker.put_issue(con, d)
    print(f"imported {len(docs)} issues as {tracker.PREFIX}-1…{tracker.PREFIX}-{len(docs)} (closed)")


if __name__ == "__main__":
    main()
