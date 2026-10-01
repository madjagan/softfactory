#!/usr/bin/env bash
# Install the software factory into a target repo.
#
#   ./install.sh /path/to/repo            # copy skills, agents, hooks, tools, tracker, templates
#   ./install.sh /path/to/repo --update   # refresh factory-owned files only; never touches
#                                         # factory.yaml, docs/ or CLAUDE.md once they exist
#
# Then, inside the target repo, run Claude Code and say: /product-interview (writes
# docs/PRODUCT_SUMMARY.md), then /setup-project (or give it a summary or a path to one).
# Idempotent: existing factory.yaml, docs/*, CLAUDE.md and tracker data are never overwritten.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-}"
MODE="${2:-}"
[ -n "$TARGET" ] || { echo "usage: $0 /path/to/repo [--update]"; exit 2; }
[ -d "$TARGET" ] || { echo "no such directory: $TARGET"; exit 2; }
TARGET="$(cd "$TARGET" && pwd)"

copy_tree() {  # copy_tree <src-dir> <dst-dir>  — factory-owned, always refreshed
  mkdir -p "$2"
  ( cd "$1" && find . -type f ! -name '.DS_Store' ! -path './data/*' ! -path '*/__pycache__/*' \
      ! -path './screenshots/app.config.mjs' ! -path './screenshots/storyboards/*' ) | while read -r f; do
    mkdir -p "$2/$(dirname "$f")"
    cp "$1/$f" "$2/$f"
  done
}

copy_if_absent() {  # copy_if_absent <src> <dst> — project-owned, written once
  if [ -e "$2" ]; then echo "  keep   ${2#$TARGET/}"; else mkdir -p "$(dirname "$2")"; cp "$1" "$2"; echo "  create ${2#$TARGET/}"; fi
}

echo "Installing the software factory into $TARGET"

echo "factory-owned (refreshed):"
copy_tree "$HERE/.claude/skills" "$TARGET/.claude/skills"
copy_tree "$HERE/.claude/agents" "$TARGET/.claude/agents"
copy_tree "$HERE/.claude/hooks"  "$TARGET/.claude/hooks"
chmod +x "$TARGET"/.claude/hooks/*.sh
copy_tree "$HERE/tools"          "$TARGET/tools"
copy_tree "$HERE/issues"         "$TARGET/issues"
copy_tree "$HERE/templates"      "$TARGET/templates"
mkdir -p "$TARGET/deploy"; cp "$HERE/deploy/docker-compose.issues.yml" "$TARGET/deploy/docker-compose.issues.yml"
echo "  .claude/skills .claude/agents .claude/hooks tools/ issues/ templates/ deploy/docker-compose.issues.yml"

# settings.json: merge the hook in without clobbering the project's own settings
python3 - "$HERE/.claude/settings.json" "$TARGET/.claude/settings.json" <<'PY'
import json, sys, pathlib
src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
ours = json.loads(src.read_text())
theirs = json.loads(dst.read_text()) if dst.exists() else {}
hooks = theirs.setdefault("hooks", {})
post = hooks.setdefault("PostToolUse", [])
want = ours["hooks"]["PostToolUse"][0]
if not any(json.dumps(h, sort_keys=True) == json.dumps(want, sort_keys=True) for h in post):
    post.append(want)
    print("  hook   .claude/settings.json (feature-list hook added)")
else:
    print("  keep   .claude/settings.json (hook present)")
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps(theirs, indent=2) + "\n")
PY

if [ "$MODE" != "--update" ]; then
  echo "project-owned (written once):"
  copy_if_absent "$HERE/factory.example.yaml" "$TARGET/factory.yaml"
  copy_if_absent "$HERE/templates/CLAUDE.md" "$TARGET/CLAUDE.md"
  for f in PRODUCT_SUMMARY.md PRODUCT_REQUIREMENTS.md IMPLEMENTATION_PLAN.md issues_log.md FEATURE_LIST.md WHY_WE_NEED_TESTING.md TESTING_COMPANION.md TEST_PLAN_HUMAN.md RELEASE_LOG.md SEEDING.md user-guide/README.md; do
    copy_if_absent "$HERE/templates/docs/$f" "$TARGET/docs/$f"
  done
  copy_if_absent "$HERE/templates/issues_classified.json" "$TARGET/docs/issues_classified.json"
  # screenshot capture: the app adapter and the example storyboard are the project's to edit
  copy_if_absent "$HERE/tools/screenshots/app.config.mjs" "$TARGET/tools/screenshots/app.config.mjs"
  copy_if_absent "$HERE/tools/screenshots/storyboards/example-payroll.mjs" "$TARGET/tools/screenshots/storyboards/example-payroll.mjs"
fi

# .gitignore entries the factory needs
GI="$TARGET/.gitignore"; touch "$GI"
for line in "issues/data/" ".claude/.feature-list.sha" ".claude/settings.local.json" "build/docs-site/" "__pycache__/"; do
  grep -qxF "$line" "$GI" || echo "$line" >> "$GI"
done

echo
echo "Done. Next, in $TARGET with Claude Code:"
echo "  /product-interview   interviews you and writes docs/PRODUCT_SUMMARY.md"
echo "  /setup-project       reads it (or pass a summary or a path to one)"
echo "It fills factory.yaml and the docs ledger, proves the gates, and starts the tracker."
echo "Later: ./install.sh $TARGET --update  refreshes skills/agents/tools without touching your docs."
