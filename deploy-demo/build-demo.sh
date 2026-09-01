#!/bin/bash
# Rebuild deploy-demo/public from frontend assets + the demo-patched app.js.
# Asset URLs get a build stamp so browsers always fetch the fresh version.
set -e
cd "$(dirname "$0")"
STAMP=$(date +%s)
mkdir -p public
cp ../frontend/index.html ../frontend/style.css ../frontend/charts.js \
   ../frontend/landing.js ../frontend/favicon.svg ../frontend/manifest.json \
   ../frontend/og.png public/
cp app.demo.js public/app.js
STAMP=$STAMP python3 - <<'PYEOF'
import os, re
stamp = os.environ["STAMP"]
src = open("public/index.html").read()
src = re.sub(r"\?v=\d+", f"?b={stamp}", src)
src = src.replace('<link rel="stylesheet" href="/assets/style.css', '<link rel="stylesheet" href="/style.css')
src = src.replace('<link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">', '<link rel="icon" type="image/svg+xml" href="/favicon.svg">')
src = src.replace('<link rel="manifest" href="/assets/manifest.json">', '<link rel="manifest" href="/manifest.json">')
src = src.replace('<meta property="og:image" content="/assets/og.png">', '<meta property="og:image" content="/og.png">')
src = src.replace('<script src="/assets/charts.js', '<script src="/charts.js')
src = src.replace('<script src="/assets/landing.js', '<script src="/landing.js')
src = src.replace('<script src="/assets/app.js', '<script src="/app.js')
src = src.replace('<script src="/charts.js', f'<script src="/api-snapshot-load.js?b={stamp}"></script>\n  <script src="/charts.js')
open("public/index.html", "w").write(src)
print("stamped + relinked, assets/ refs left:", src.count("/assets/"))
PYEOF
echo "demo build complete (stamp $STAMP)"
