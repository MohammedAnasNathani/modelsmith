#!/bin/bash
# Get a public URL for the locally running ModelSmith (port 8100).
# Uses Cloudflare quick tunnels: no account, no token, nothing to configure.
# The URL changes each run; this script prints the new one.
set -e
cd "$(dirname "$0")"
if ! curl -s -o /dev/null http://127.0.0.1:8100/api/health; then
  echo "Starting server first…"
  (cd backend && nohup ../.venv/bin/python -m uvicorn app.main:app \
      --host 127.0.0.1 --port 8100 > /tmp/ms_server.log 2>&1 &)
  sleep 5
fi
pkill -f "cloudflared tunnel" 2>/dev/null || true
sleep 1
nohup cloudflared tunnel --url http://127.0.0.1:8100 --no-autoupdate \
  > /tmp/cf_tunnel.log 2>&1 &
for i in $(seq 1 15); do
  URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /tmp/cf_tunnel.log | head -1)
  [ -n "$URL" ] && break
  sleep 1
done
echo ""
echo "  Public URL:  $URL"
echo "  (lives as long as this Mac stays on; rerun this script for a fresh URL)"
