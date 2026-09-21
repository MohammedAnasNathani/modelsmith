#!/bin/bash
# One command: start the real backend, publish it, refresh the landing data,
# and redeploy the site so its login page talks to the live workspace.
set -e
cd "$(dirname "$0")"

echo "1/5 starting backend..."
pkill -f "uvicorn app.main" 2>/dev/null || true
pkill -f "cloudflared tunnel" 2>/dev/null || true
sleep 1
./.run-keep.sh > /tmp/modelsmith.log 2>&1 &
for i in $(seq 1 30); do curl -s http://127.0.0.1:8100/api/health >/dev/null 2>&1 && break; sleep 1; done
curl -s http://127.0.0.1:8100/api/health | grep -q '"ok"' || { echo "backend failed"; exit 1; }
echo "   backend up"

echo "2/5 opening public tunnel..."
cloudflared tunnel --url http://127.0.0.1:8100 > /tmp/cf_tunnel.log 2>&1 &
URL=""
for i in $(seq 1 30); do
  URL=$(grep -o "https://[a-z0-9-]*\.trycloudflare.com" /tmp/cf_tunnel.log | head -1)
  [ -n "$URL" ] && break; sleep 1
done
[ -z "$URL" ] && { echo "tunnel failed"; exit 1; }
echo "   tunnel: $URL"

echo "3/5 publishing live URL + refreshing real landing data..."
python3 - "$URL" <<'PY'
import json, sys, time
json.dump({"url": sys.argv[1], "updated_at": time.time()},
          open("frontend/live-url.json", "w"))
PY
.venv/bin/python tools/capture_landing.py http://127.0.0.1:8100

echo "4/5 rebuilding + deploying site..."
python3 deploy-demo/patch-demo.py >/dev/null
(cd deploy-demo && ./build-demo.sh >/dev/null && vercel deploy --prod --yes >/dev/null 2>&1)

echo "5/5 done."
echo ""
echo "  REAL APP (signup, training, optimization):  $URL"
echo "  Marketing site + real login:                https://modelsmith-alpha.vercel.app"
echo ""
wait
