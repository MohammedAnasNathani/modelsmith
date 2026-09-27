#!/bin/bash
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { python3.11 -m venv .venv && .venv/bin/pip install --no-cache-dir -q -r requirements.txt boto3; }
exec .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8100
