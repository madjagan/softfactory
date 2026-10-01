#!/usr/bin/env bash
# The local stack a screenshot run drives: a FRESH test seed, the API on its own port with any
# test-only tools enabled, and a dev server whose /api proxy points at it. Never the developer's
# own backend, never the deployed site: a guide's destructive steps run for real here.
#
# The three commands come from factory.yaml → screenshots.{seed, api, web} and the two health
# URLs from screenshots.{api_health, web_url}; see factory.example.yaml.
#   tools/screenshots/stack.sh up      # seed + start, waits until both answer (do not pipe its
#                                      #   output: the servers are detached, a pipe would wait on them)
#   tools/screenshots/stack.sh down    # stop both
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
get() { python3 "$ROOT/tools/factory.py" get "screenshots.$1"; }
SEED="$(get seed)"; APIC="$(get api)"; WEB="$(get web)"
API_HEALTH="$(get api_health)"; WEB_URL="$(get web_url)"
[ -n "$APIC" ] && [ -n "$WEB" ] && [ -n "$API_HEALTH" ] && [ -n "$WEB_URL" ] || { echo "factory.yaml needs screenshots.{api, web, api_health, web_url} (seed optional)"; exit 2; }

case "${1:-up}" in
  up)
    if [ -n "$SEED" ]; then
      echo "[1/3] fresh seed: $SEED"
      ( cd "$ROOT" && bash -c "$SEED" ) > /tmp/shots-seed.log 2>&1 || { echo "seed failed:"; tail -20 /tmp/shots-seed.log; exit 1; }
    else
      echo "[1/3] no screenshots.seed configured — using the database as it is"
    fi
    echo "[2/3] API: $APIC"
    [ -n "${SHOTS_API_PKILL:-}" ] && pkill -f "$SHOTS_API_PKILL" 2>/dev/null; sleep 1
    ( cd "$ROOT" && nohup bash -c "$APIC" > /tmp/shots-api.log 2>&1 < /dev/null & disown )
    for i in $(seq 1 40); do curl -sf "$API_HEALTH" >/dev/null 2>&1 && break; sleep 1; done
    curl -sf "$API_HEALTH" >/dev/null || { echo "API did not start:"; tail -20 /tmp/shots-api.log; exit 1; }
    echo "[3/3] web: $WEB"
    [ -n "${SHOTS_WEB_PKILL:-}" ] && pkill -f "$SHOTS_WEB_PKILL" 2>/dev/null
    ( cd "$ROOT" && nohup bash -c "$WEB" > /tmp/shots-web.log 2>&1 < /dev/null & disown )
    for i in $(seq 1 40); do curl -sf "$WEB_URL" >/dev/null 2>&1 && break; sleep 1; done
    curl -sf "$WEB_URL" >/dev/null || { echo "web did not start:"; tail -20 /tmp/shots-web.log; exit 1; }
    echo "up: $WEB_URL (API $API_HEALTH)";;
  down)
    # The manifest may name a pkill pattern per process (screenshots.api_pkill / web_pkill);
    # otherwise the ports are freed by pattern on the commands themselves.
    P1="$(get api_pkill)"; P2="$(get web_pkill)"
    pkill -f "${P1:-$APIC}" 2>/dev/null; pkill -f "${P2:-$WEB}" 2>/dev/null; echo "down";;
  *) echo "usage: stack.sh up|down"; exit 2;;
esac
