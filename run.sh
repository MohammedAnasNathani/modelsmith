#!/bin/bash
# ModelSmith — one-command start (macOS / Linux, requires python3.11)
set -e
cd "$(dirname "$0")"

PYTHON=""
for cand in python3.11 python3.12 python3.13 python3; do
  if command -v "$cand" >/dev/null 2>&1; then PYTHON="$cand"; break; fi
done
[ -z "$PYTHON" ] && { echo "No python3 found"; exit 1; }

if [ ! -d .venv ]; then
  echo "Creating virtualenv with $PYTHON ..."
  "$PYTHON" -m venv .venv
  .venv/bin/pip install --upgrade pip -q
  echo "Installing dependencies (torch is large, first run takes a few minutes)..."
  .venv/bin/pip install -r requirements.txt
fi

PORT="${MODELSMITH_PORT:-8100}"
echo ""
echo "  ModelSmith running at  http://127.0.0.1:$PORT"
echo "  Demo logins:  admin@modelsmith.io / admin12345   ·   demo@modelsmith.io / demo12345"
echo ""
exec .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$PORT"
