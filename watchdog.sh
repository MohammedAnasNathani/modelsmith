#!/bin/bash
# Keeps ModelSmith's public tunnels alive.
#
# Primary : localtunnel, fixed subdomain  https://modelsmith-live.loca.lt
# Backup  : cloudflared quick tunnel, random URL (rewritten into frontend/live-url.json)
#
# Both are published to the demo site so the frontend can fail over when one
# provider blips. loca.lt drops its server socket fairly often, so this script
# re-checks both every CHECK_EVERY seconds and restarts whichever is down.
#
# Usage: ./watchdog.sh    (go-live.sh starts it automatically)
cd "$(dirname "$0")"

LOCAL="http://127.0.0.1:8100/api/health"
LT_URL="https://modelsmith-live.loca.lt"
CHECK_EVERY=20
FAILS_BEFORE_RESTART=2

log() { echo "[watchdog $(date '+%H:%M:%S')] $*"; }

start_lt() {
  pkill -f "localtunnel" 2>/dev/null
  sleep 1
  nohup npx -y localtunnel --port 8100 --subdomain modelsmith-live > /tmp/lt.log 2>&1 &
  log "localtunnel started"
}

start_cf() {
  pkill -f "cloudflared tunnel" 2>/dev/null
  sleep 1
  nohup cloudflared tunnel --url http://127.0.0.1:8100 > /tmp/cf_tunnel.log 2>&1 &
  log "cloudflared started"
}

# Publish the currently-working backend URLs so the frontend can fail over.
publish_urls() {
  python3 - "$@" <<'PY' 2>/dev/null
import json, sys, time
urls = [u for u in sys.argv[1:] if u]
data = {"urls": urls, "url": urls[0] if urls else "", "updated_at": time.time()}
json.dump(data, open("frontend/live-url.json", "w"))
PY
}

cf_url() { grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cf_tunnel.log 2>/dev/null | head -1; }

probe() { curl -s -o /dev/null -w "%{http_code}" -m 15 "$1/api/health" 2>/dev/null; }

# Rebuild the Vercel site with the current URL list so its login page can fail
# over between tunnels. Only runs when the list actually changed, so we do not
# hammer Vercel on every loop.
redeploy_site() {
  ( cd deploy-demo && ./build-demo.sh >/dev/null 2>&1 && vercel deploy --prod --yes >/dev/null 2>&1 ) \
    && log "vercel site redeployed with $*" || log "vercel redeploy failed (will retry on next change)"
}

start_lt
start_cf
sleep 10

lt_fails=0; cf_fails=0; LAST_LIST=""
while true; do
  sleep "$CHECK_EVERY"

  # If the backend itself is down, nothing to do but wait.
  if [ "$(curl -s -o /dev/null -w "%{http_code}" -m 5 "$LOCAL" 2>/dev/null)" != "200" ]; then
    log "backend down - waiting"
    continue
  fi

  lt_ok=$(probe "$LT_URL")
  if [ "$lt_ok" = "200" ]; then lt_fails=0; else
    lt_fails=$((lt_fails + 1))
    log "localtunnel failed ($lt_ok) x$lt_fails"
    if [ "$lt_fails" -ge "$FAILS_BEFORE_RESTART" ]; then start_lt; lt_fails=0; sleep 8; fi
  fi

  CF=$(cf_url)
  if [ -z "$CF" ]; then
    log "cloudflared has no URL yet - restarting"
    start_cf; sleep 10; CF=$(cf_url)
  else
    cf_ok=$(probe "$CF")
    if [ "$cf_ok" = "200" ]; then cf_fails=0; else
      cf_fails=$((cf_fails + 1))
      log "cloudflared failed ($cf_ok) x$cf_fails"
      if [ "$cf_fails" -ge "$FAILS_BEFORE_RESTART" ]; then start_cf; cf_fails=0; sleep 10; CF=$(cf_url); fi
    fi
  fi

  # Keep the failover list fresh: healthy URLs first.
  healthy=""
  [ "$(probe "$LT_URL")" = "200" ] && healthy="$LT_URL"
  [ -n "$CF" ] && [ "$(probe "$CF")" = "200" ] && healthy="$healthy $CF"
  healthy=$(echo "$healthy" | xargs)
  if [ -n "$healthy" ] && [ "$healthy" != "$LAST_LIST" ]; then
    publish_urls $healthy
    LAST_LIST="$healthy"
    redeploy_site $healthy
  fi
done