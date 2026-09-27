#!/bin/bash
# One command: start the real backend, publish it (fixed URL), refresh the landing data,
# and redeploy the site so its login page talks to the live workspace.
# Primary tunnel: localtunnel with a FIXED subdomain -> https://modelsmith-live.loca.lt
# Fallback: cloudflared quick tunnel (random URL) if localtunnel is unreachable.
set -e
cd "$(dirname "$0")"

echo "1/6 starting backend..."
pkill -f "uvicorn app.main" 2>/dev/null || true
pkill -f "cloudflared tunnel" 2>/dev/null || true
pkill -f "localtunnel" 2>/dev/null || true
sleep 1
./.run-keep.sh > /tmp/modelsmith.log 2>&1 &
for i in $(seq 1 60); do curl -s http://127.0.0.1:8100/api/health >/dev/null 2>&1 && break; sleep 1; done
curl -s http://127.0.0.1:8100/api/health | grep -q '"ok"' || { echo "backend failed (check /tmp/modelsmith.log; .venv may need to rebuild)"; exit 1; }
echo "   backend up"

echo "2/6 opening public tunnel (fixed URL https://modelsmith-live.loca.lt)..."
nohup npx -y localtunnel --port 8100 --subdomain modelsmith-live > /tmp/lt.log 2>&1 &
URL="https://modelsmith-live.loca.lt"
TUN_OK=0
for i in $(seq 1 25); do
  curl -s -m 3 "$URL/api/health" 2>/dev/null | grep -q '"ok"' && TUN_OK=1 && break
  sleep 1
done
if [ "${TUN_OK:-0}" != "1" ]; then
  echo "   fixed tunnel busy, falling back to cloudflared (URL will vary)..."
  pkill -f "localtunnel" 2>/dev/null || true
  cloudflared tunnel --url http://127.0.0.1:8100 > /tmp/cf_tunnel.log 2>&1 &
  URL=""
  for i in $(seq 1 30); do
    URL=$(grep -o "https://[a-z0-9-]*\.trycloudflare\.com" /tmp/cf_tunnel.log | head -1)
    [ -n "$URL" ] && break; sleep 1
  done
fi
[ -z "$URL" ] && { echo "tunnel failed"; exit 1; }
echo "   tunnel: $URL"

echo "3/6 starting tunnel watchdog (auto-restarts the URL if it ever drops)..."
pkill -f "watchdog.sh" 2>/dev/null || true
nohup ./watchdog.sh > /tmp/ms_watchdog.log 2>&1 &
echo "   watchdog pid $(pgrep -f watchdog.sh | head -1)"

echo "4/6 publishing live URL + refreshing real landing data..."
python3 - "$URL" <<'PY'
import json, sys, time
json.dump({"url": sys.argv[1], "updated_at": time.time()},
          open("frontend/live-url.json", "w"))
PY
if [ -x .venv/bin/python ]; then .venv/bin/python tools/capture_landing.py http://127.0.0.1:8100;
else python3 tools/capture_landing.py http://127.0.0.1:8100 2>/dev/null || true; fi

echo "5/6 rebuilding + deploying site..."
python3 deploy-demo/patch-demo.py >/dev/null 2>&1 || true
(cd deploy-demo && ./build-demo.sh >/dev/null && vercel deploy --prod --yes >/dev/null 2>&1)

echo "6/6 done."
echo ""
echo "  REAL APP (signup, training, optimization):  $URL"
echo "  Marketing site + real login:                https://modelsmith-alpha.vercel.app"
echo ""
wait
