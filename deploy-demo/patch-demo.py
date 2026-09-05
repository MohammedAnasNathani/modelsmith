#!/usr/bin/env python3
"""Rebuild app.demo.js: current frontend/app.js + demo-mode patches.

Patches extracted from the previous app.demo.js (kept verbatim so demo
behavior never drifts):
  1. DEMO MODE adapter (snapshot routing, write refusal) before logoutLocal()
  2. demo banner injected above bg-fx in shell()
  3. demo login screen (single Enter button) replacing viewLogin()
Run after every frontend/app.js change:  python3 patch-demo.py
"""
import sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
old_path = os.path.join(HERE, "app.demo.js")
src_path = os.path.join(HERE, "..", "frontend", "app.js")

old = open(old_path).read()
cur = open(src_path).read()

# 1) demo adapter
p1 = old.index("/* ================= DEMO MODE")
p2 = old.index("function logoutLocal()")
demo_block = old[p1:p2]

# 2) banner
b1 = old.index('<div class="demo-banner">')
b2 = old.index('<div class="bg-fx">')
banner = old[b1:b2]

# 3) demo viewLogin (up to viewDashboard)
v1 = old.index("function viewLogin(")
v2 = old.index("async function viewDashboard(")
demo_viewlogin = old[v1:v2]

out = cur
assert '<div class="bg-fx"></div>' in out, "bg-fx anchor missing from app.js"
out = out.replace('<div class="bg-fx"></div>', banner + '<div class="bg-fx"></div>', 1)
assert "function logoutLocal()" in out, "logoutLocal anchor missing"
out = out.replace("function logoutLocal()", demo_block + "function logoutLocal()", 1)
assert "function viewLogin(" in out, "viewLogin anchor missing"
assert "async function viewDashboard(" in out, "viewDashboard anchor missing"
c1 = out.index("function viewLogin(")
c2 = out.index("async function viewDashboard(")
out = out[:c1] + demo_viewlogin + out[c2:]

open(old_path, "w").write(out)
print(f"app.demo.js rebuilt: {len(out)} bytes")
