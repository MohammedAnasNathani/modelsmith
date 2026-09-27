#!/usr/bin/env python3
"""Capture real workspace data for the landing page.

Queries the LIVE local server and writes frontend/landing-data.json.
Every number on the landing page comes from this file: real model,
real analysis, real executed run, real plans. Rerun after significant
workspace changes:  .venv/bin/python tools/capture_landing.py
"""
import json, sys, time, urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8100"

def get(path, token=None):
    req = urllib.request.Request(BASE + path)
    if token: req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def post(path, body, token=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    if token: req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

tok = post("/api/auth/login", {"email": "demo@modelsmith.io", "password": "demo12345"})["token"]
health = get("/api/health")
endpoints = len(get("/openapi.json")["paths"])

# pick the analyzed model with the best successful run
target, best = None, None
for m in get("/api/search?q=", token=tok)["results"]:
    if m["status"] != "analyzed": continue
    full = get(f"/api/models/{m['id']}", token=tok)
    for r in full.get("runs", []):
        bm = r.get("benchmark") or {}
        if r.get("status") == "success" and bm.get("size_saved_pct") is not None:
            if not best or bm["size_saved_pct"] > best[1]:
                best = (m["id"], bm["size_saved_pct"], full, r)
    if target is None and full.get("analysis"):
        target = full

mid, saved, model_full, run = best
a = model_full.get("analysis") or {}
bm = run.get("benchmark") or {}
base, opt = bm.get("baseline") or {}, bm.get("optimized") or {}
art = next((x for x in (run.get("artifacts") or [])
            if x["name"] == ("optimized.pt" if any(t in (run.get("plan_name") or "") for t in ("Prune", "INT8", "Knowledge")) else "optimized.onnx")),
           (run.get("artifacts") or [{}])[0])

layers = [{"name": l["name"], "type": l["type"], "params": l["params"], "flops": l.get("flops", 0)}
          for l in (a.get("layers") or []) if l.get("params")][:12]
total_params = a.get("total_params") or 1
layers_top = sorted([l for l in layers if l["params"]], key=lambda l: -l["params"])[:4]

plans = (model_full.get("plans") or {}).get("valid", [])[:3]
radar = []
for i, p in enumerate(plans):
    pr = p["predicted"]
    radar.append({"name": " + ".join(x.split("(")[0].strip() for x in p["technique_labels"]),
                  "color": ["#ffb224", "#ff6b2c", "#4ade80"][i],
                  "values": [round(pr["size_saved_pct"] / 60, 2),
                             round(pr["latency_gain_pct"] / 60, 2),
                             round((pr["accuracy_retention_pct"] - 80) / 20, 2),
                             round(pr["memory_saved_pct"] / 60, 2),
                             1.0 if p.get("auto_executable") else 0.55]})
steps = [{"label": s.get("label") or s.get("technique", "step"),
          "detail": (s.get("note") or "")[:60]}
         for s in (run.get("steps") or []) if s.get("status") == "success"]
duration = int((run.get("finished_at") or 0) - (run.get("created_at") or 0))
checks = open("tests/e2e_test.py").read().count("check(") - 1

config = get("/api/config")
out = {
  "captured_at": time.strftime("%Y-%m-%d"),
  "endpoints": endpoints, "checks": checks, "max_upload_mb": config.get("max_upload_mb", 500),
  "model": {
    "id": mid, "name": model_full["name"], "file": model_full.get("orig_name") or "model.pt",
    "size_mb": round((model_full.get("size_bytes") or 0) / 1e6, 1),
    "dtype": "fp32", "layers": a.get("layer_count"),
    "params": total_params, "flops": a.get("total_flops"),
    "arch": (a.get("arch") or "model"),
  },
  "layers": layers,
  "layers_top": [{"name": l["name"], "share": round(100 * l["params"] / total_params, 1)} for l in layers_top],
  "analysis_summary": a.get("summary") or {},
  "run": {
    "id": run["id"], "short_id": run["id"][:12], "plan": run.get("plan_name"),
    "duration_s": max(1, duration),
    "artifact": art.get("name", "optimized.pt"),
    "artifact_mb": round((art.get("size_bytes") or 0) / 1e6, 1),
    "saved_pct": bm.get("size_saved_pct"),
    "latency_gain_pct": bm.get("latency_gain_pct"),
    "agreement_pct": (bm.get("output_agreement") or {}).get("agreement_pct"),
    "p95_before": base.get("p95_ms"), "p95_after": opt.get("p95_ms"),
    "size_before_mb": base.get("size_mb"), "size_after_mb": opt.get("size_mb"),
    "steps": steps,
  },
  "plan_radar": radar,
  "techniques": 8,
}
json.dump(out, open("frontend/landing-data.json", "w"), indent=1)
print("captured:", out["model"]["name"], "| run", out["run"]["short_id"],
      f"| saved {out['run']['saved_pct']}% | {endpoints} endpoints | {checks} checks")
