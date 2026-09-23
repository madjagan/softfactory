#!/usr/bin/env bash
# PostToolUse hook: when the feature list (factory.yaml docs.feature_list, default
# docs/FEATURE_LIST.md) changes, ask Claude to reconcile the derived per-persona user
# guides (docs.user_guides, default docs/user-guide/) via the docs-agent subagent.
#
# Detection is by CONTENT HASH, not by the tool's declared file_path, so an edit made
# through Bash (sed, python, a heredoc) is caught exactly like an Edit/Write. The last
# seen hash lives in .claude/.feature-list.sha; the hook fires only when it moves, so a
# long run of Bash calls against a dirty tree stays silent after the first.
#
# Reads the hook payload as JSON on stdin; emits additionalContext, never blocks.
set -uo pipefail

payload="$(cat)"

python3 - "$payload" <<'PY'
import hashlib, json, os, sys

try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)

root = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
src = os.path.join(root, "docs", "FEATURE_LIST.md")
guides = os.path.join(root, "docs", "user-guide")
try:  # the manifest may move them
    sys.path.insert(0, os.path.join(root, "tools"))
    from factory import doc_path
    src, guides = str(doc_path("feature_list")), str(doc_path("user_guides"))
except Exception:
    pass
state = os.path.join(root, ".claude", ".feature-list.sha")

# Nothing to watch, or nothing to reconcile into.
if not os.path.isfile(src) or not os.path.isdir(guides):
    sys.exit(0)

try:
    with open(src, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
except OSError:
    sys.exit(0)

previous = ""
try:
    with open(state) as fh:
        previous = fh.read().strip()
except OSError:
    pass

try:
    with open(state, "w") as fh:
        fh.write(digest + "\n")
except OSError:
    pass

# First run just records the baseline — it is not evidence of a change.
if not previous or previous == digest:
    sys.exit(0)

# Line citations rot on any insertion — nothing fails, the reader just lands on the wrong
# row. Surfaced here so the hook catches it rather than a person noticing weeks later.
import subprocess
checker = os.path.join(root, ".claude", "hooks", "check_citations.py")
stale = ""
if os.path.isfile(checker):
    r = subprocess.run([sys.executable, checker, root], capture_output=True, text=True)
    if r.returncode == 1 and r.stdout.strip():
        stale = ("\n\nSTALE LINE CITATIONS — every insertion shifts the rows below it:\n  "
                 + "\n  ".join(r.stdout.strip().splitlines())
                 + "\nFix these too (resolve each feature id to its current line).")

msg = (
    f"{os.path.relpath(src, root)} just changed (content hash moved). {os.path.relpath(guides, root)}/ is DERIVED "
    "from it and is now potentially stale.\n\n"
    "Before you finish this turn, launch the `docs-agent` subagent to reconcile the guides. "
    "Brief it to follow the 'Reconciliation' procedure in its own definition: diff the feature "
    "list, classify each changed row (new / removed / maturity change / description change / "
    "gap-register change), update ONLY the persona guides whose §6 feature scope covers the "
    "changed IDs, re-stamp the traceability footer with today's real date, and report a per-file "
    "summary.\n\n"
    "If the change was cosmetic (formatting, a typo, no feature row touched), say so and skip the "
    "reconciliation rather than running it for nothing." + stale
)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": msg,
    }
}))
PY
