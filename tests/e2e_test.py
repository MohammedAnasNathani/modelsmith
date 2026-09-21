
import io
import json
import sys
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8100"
PASS, FAIL = 0, 0
def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name} {extra}")

def req(method, path, body=None, token=None, raw_body=None, content_type="application/json"):
    url = BASE + path
    data = raw_body if raw_body is not None else (json.dumps(body).encode() if body else None)
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", content_type)
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            payload = resp.read() or b"{}"
            ctype = resp.headers.get("Content-Type", "")
            if "json" in ctype:
                return resp.status, json.loads(payload), dict(resp.headers)
            return resp.status, payload, dict(resp.headers)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}"), dict(e.headers)
        except Exception:
            return e.code, {}, {}

def wait_job(job_id, token, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        _, j, _ = req("GET", f"/api/jobs/{job_id}", token=token)
        if j.get("status") in ("success", "failed"):
            return j
        time.sleep(2)
    return {"status": "timeout"}

print("== 1. Health ==")
s, h, _ = req("GET", "/api/health")
check("health ok", s == 200 and h["status"] == "ok", h)
check("3 models seeded analyzed", h["counts"]["models"] >= 3, h["counts"])
check("3 analyze jobs success", h["counts"]["jobs"].get("success", 0) >= 3)

print("== 2. Auth (FR-01) ==")
TESTER = f"tester{int(time.time())}@x.com"
s, r, _ = req("POST", "/api/auth/login", {"email": "demo@modelsmith.io", "password": "demo12345"})
check("demo login", s == 200 and "token" in r, r)
demo_tok = r.get("token", "")
s, r, _ = req("POST", "/api/auth/login", {"email": "demo@modelsmith.io", "password": "WRONG"})
check("wrong password rejected", s == 401)
s, r, _ = req("POST", "/api/auth/register", {"email": TESTER, "password": "tester12345", "full_name": "Tester"})
check("register", s == 200, r)
s, r, _ = req("POST", "/api/auth/register", {"email": TESTER, "password": "tester12345"})
check("duplicate register rejected", s == 409)
s, r, _ = req("POST", "/api/auth/login", {"email": TESTER, "password": "tester12345"})
tester_tok = r.get("token")
check("new user login", s == 200)
s, r, _ = req("GET", "/api/auth/me", token=tester_tok)
check("me endpoint", s == 200 and r["email"] == TESTER)
s, r, _ = req("POST", "/api/auth/password/reset-request", {"email": TESTER})
check("reset request returns token", s == 200 and r.get("reset_token"), r)
reset_tok = r.get("reset_token", "")
time.sleep(1.1)
s, r, _ = req("POST", "/api/auth/password/reset-confirm", {"reset_token": reset_tok, "password": "newpass12345"})
check("reset confirm", s == 200, r)
s, r, _ = req("GET", "/api/auth/me", token=tester_tok)
check("reset revokes old tokens", s == 401)
s, r, _ = req("POST", "/api/auth/login", {"email": TESTER, "password": "newpass12345"})
check("login with new password", s == 200)
tester_tok = r.get("token")
s, r, _ = req("POST", "/api/auth/logout", token=tester_tok)
check("logout", s == 200)
s, r, _ = req("GET", "/api/auth/me", token=tester_tok)
check("revoked token rejected", s == 401)
s, r, _ = req("POST", "/api/auth/login", {"email": TESTER, "password": "newpass12345"})
tester_tok = r.get("token")

print("== 3. Projects (FR-02) ==")
s, r, _ = req("POST", "/api/projects", {"name": "E2E Test Project", "description": "created by test"}, token=demo_tok)
check("create project", s == 200, r)
proj_id = r.get("id")
s, r, _ = req("GET", "/api/projects", token=demo_tok)
check("list projects has demo+test", len(r["projects"]) >= 2)
demo_proj = next((p for p in r["projects"] if p["name"] == "Demo Optimization Lab"), None)
check("demo project exists", demo_proj is not None)
s, r, _ = req("PUT", f"/api/projects/{proj_id}", {"name": "E2E Renamed", "description": "upd"}, token=demo_tok)
check("update project", s == 200)
s, r, _ = req("GET", f"/api/projects/{demo_proj['id']}", token=demo_tok)
check("project detail w/ 3 models", s == 200 and len(r["models"]) == 3, len(r.get("models", [])))
models = r["models"]

models.sort(key=lambda m: m["size_bytes"])
s, r, _ = req("GET", f"/api/projects/{demo_proj['id']}", token=tester_tok)
check("other user blocked from project", s == 403)

print("== 4. Model detail (FR-04/05/07-10) ==")
mid = models[0]["id"]
demo_model_name = models[0]["name"]
s, m, _ = req("GET", f"/api/models/{mid}", token=demo_tok)
check("model analyzed", m["status"] == "analyzed", m.get("status"))
a = m.get("analysis") or {}
check("analysis has params+flops+layers", a.get("total_params", 0) > 0 and a.get("total_flops", 0) > 0 and len(a.get("layers", [])) > 0)
check("benchmark measured", a.get("benchmark", {}).get("latency_ms", 0) > 0)
check("bottlenecks detected", len(a.get("bottlenecks", {}).get("notes", [])) > 0)
plans = m.get("plans") or {}
check("plans generated+ranked", len(plans.get("valid", [])) >= 3 and plans["valid"][0].get("rank") == 1)
check("plans have predictions+reasons", "predicted" in plans["valid"][0] and len(plans["valid"][0].get("reasons", [])) > 0)
check("rejected plans have reasons", all(p.get("rejected_because") for p in plans.get("rejected", [])))

print("== 5. Goals re-rank (FR-06/08) ==")
s, r, _ = req("PUT", f"/api/models/{mid}/goals", {"objective": "min_size", "target_hardware": "mobile", "min_accuracy_pct": 98}, token=demo_tok)
check("set goals", s == 200 and r["goals"]["objective"] == "min_size", r)
new_plans = r["plans"]
check("plans re-ranked for min_size", new_plans["valid"][0]["predicted"]["size_saved_pct"] >=
      max(p["predicted"]["size_saved_pct"] for p in new_plans["valid"]) - 0.1)
s, r, _ = req("PUT", f"/api/models/{mid}/goals", {"objective": "bogus"}, token=demo_tok)
check("invalid objective rejected", s == 422)

req("PUT", f"/api/models/{mid}/goals", {"objective": "balanced", "target_hardware": "cpu-server", "min_accuracy_pct": 95}, token=demo_tok)

print("== 6. Upload own model (FR-03) ==")
import torch
sys.path.insert(0, "backend")
net = torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(784, 256), torch.nn.ReLU(), torch.nn.Linear(256, 10))
buf = io.BytesIO(); torch.save(net, buf)
boundary = "----e2eboundary"
part = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"project_id\"\r\n\r\n{proj_id}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"name\"\r\n\r\nE2E MLP\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"input_shape\"\r\n\r\n784\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"mlp.pt\"\r\n"
        f"Content-Type: application/octet-stream\r\n\r\n").encode() + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode()
s, r, _ = req("POST", "/api/models/upload", raw_body=part, token=demo_tok,
              content_type=f"multipart/form-data; boundary={boundary}")
check("upload accepted+queued", s == 200 and r.get("job_id"), r)
up_job = wait_job(r["job_id"], demo_tok)
check("upload analysis job success", up_job["status"] == "success", up_job.get("error"))
up_id = r["model_id"]
s, r, _ = req("GET", f"/api/models/{up_id}", token=demo_tok)
check("uploaded model analyzed", r["status"] == "analyzed")
check("MLP arch detected", r["analysis"].get("arch") == "mlp", r["analysis"].get("arch"))
s, r, _ = req("GET", "/api/models/m_doesnotexist", token=demo_tok)
check("missing model 404", s == 404)

print("== 7. Execute plan (FR-11/12/13) ==")
s, m2, _ = req("GET", f"/api/models/{mid}", token=demo_tok)
best = next(p for p in m2["plans"]["valid"] if p["auto_executable"])
s, r, _ = req("POST", f"/api/models/{mid}/execute", {"plan_id": best["plan_id"]}, token=demo_tok)
check("execute accepted", s == 200 and r.get("run_id"), r)
run_id, ex_job = r["run_id"], r["job_id"]
j = wait_job(ex_job, demo_tok, timeout=600)
check("execution job success", j["status"] == "success", j.get("error"))
s, run, _ = req("GET", f"/api/runs/{run_id}", token=demo_tok)
check("run recorded success", run["status"] == "success", run.get("error"))
check("steps recorded", all(st.get("status") for st in (run.get("steps") or [])))
bm = run.get("benchmark") or {}
check("benchmark has baseline+optimized", "baseline" in bm and "optimized" in bm)
check("size saved measured", isinstance(bm.get("size_saved_pct"), (int, float)) and bm["size_saved_pct"] > 0, bm.get("size_saved_pct"))
check("agreement computed", (bm.get("output_agreement") or {}).get("agreement_pct") is not None, bm.get("output_agreement"))
arts = run.get("artifacts") or []
check("artifacts stored", len(arts) >= 1 and all(a.get("sha256") for a in arts), arts)
check("repro metadata", (run.get("repro") or {}).get("versions", {}).get("torch") is not None)
s, r, h = req("GET", f"/api/runs/{run_id}/artifacts/optimized.pt/download", token=demo_tok)
check("artifact download authorized", s == 200 and isinstance(r, bytes) and len(r) > 1000, s)
s, r, _ = req("GET", f"/api/runs/{run_id}/artifacts/optimized.pt/download", token=tester_tok)
check("artifact download blocked for stranger", s in (403, 404))

print("== 7b. Real training (knowledge distillation) ==")
s, r, _ = req("POST", f"/api/models/{mid}/execute",
              body={"plan_id": "distill", "mode": "platform"}, token=demo_tok)
check("distill execute accepted", s == 200 and r.get("run_id"), r)
dist_run = r.get("run_id", "")
dist_job = r.get("job_id", "")
dj = wait_job(dist_job, demo_tok, timeout=600)
check("distill job success", dj.get("status") == "success", dj.get("status"))
s, r, _ = req("GET", f"/api/runs/{dist_run}", token=demo_tok)
steps = r.get("steps") or []
epochs = [st for st in steps if "Training epoch" in str(st.get("label", ""))]
check("real training epochs recorded", len(epochs) >= 4, len(epochs))
losses = [float(st["note"].split()[-1]) for st in epochs if st.get("note")]
check("loss decreases (genuine training)", losses[-1] < losses[0], losses[:3])
check("student artifact stored", any(a.get("name") == "optimized.pt"
      for a in (r.get("artifacts") or [])))

print("== 8. Report (FR-14) ==")
import urllib.request as ur
rq = ur.Request(f"{BASE}/api/models/{mid}/report"); rq.add_header("Authorization", f"Bearer {demo_tok}")
with ur.urlopen(rq) as resp:
    md = resp.read().decode()
check("report markdown generated", "ModelSmith Report" in md and "Model analysis" in md and "Execution history" in md)
check("report free of internal requirement IDs", not any(x in md for x in ("FR-", "NFR-")))

print("== 9. Notifications (FR-14) ==")
s, r, _ = req("GET", "/api/notifications", token=demo_tok)
check("notifications exist", r["unread"] >= 1 and len(r["notifications"]) >= 2, r.get("unread"))
s, r, _ = req("POST", "/api/notifications/read", token=demo_tok)
check("mark read", s == 200)
s, r, _ = req("GET", "/api/notifications", token=demo_tok)
check("unread now 0", r["unread"] == 0)

print("== 10. Admin (FR-15) ==")
s, r, _ = req("POST", "/api/auth/login", {"email": "admin@modelsmith.io", "password": "admin12345"})
admin_tok = r.get("token")
check("admin login", s == 200 and r["user"]["role"] == "admin")
s, r, _ = req("GET", "/api/admin/overview", token=admin_tok)
check("overview totals", s == 200 and r["totals"]["models"] >= 4 and r["totals"]["runs"] >= 1, r.get("totals"))
check("audit log populated", len(r["audit_log"]) >= 5)
s, r, _ = req("GET", "/api/admin/users", token=admin_tok)
check("users list", s == 200 and len(r["users"]) >= 3)
tester_id = next(u["id"] for u in r["users"] if u["email"] == TESTER)
s, r, _ = req("PATCH", f"/api/admin/users/{tester_id}", {"action": "disable"}, token=admin_tok)
check("disable user", s == 200)
s, r, _ = req("POST", "/api/auth/login", {"email": TESTER, "password": "newpass12345"})
check("disabled user cannot login", s == 403)
s, r, _ = req("PATCH", f"/api/admin/users/{tester_id}", {"action": "enable"}, token=admin_tok)
check("re-enable user", s == 200)
s, r, _ = req("GET", "/api/admin/overview", token=demo_tok)
check("member blocked from admin", s == 403)
s, r, _ = req("GET", "/api/admin/jobs", token=admin_tok)
check("admin jobs view", s == 200 and len(r["jobs"]) >= 4)

print("== 11. V4 endpoints ==")
s, r, _ = req("GET", "/api/search?q=resnet", token=demo_tok)
check("server-side search works", s == 200 and r["total"] >= 1 and r["total"] <= r["scanned"], r.get("total"))
s, r, _ = req("GET", "/api/search?status=analyzed", token=demo_tok)
check("search status filter", s == 200 and all(m["status"] == "analyzed" for m in r["results"]))
s, r, _ = req("GET", f"/api/models/{mid}/suggestions", token=demo_tok)
check("suggestions generated", s == 200 and len(r["suggestions"]) >= 1, r.get("suggestions"))
s, r, _ = req("PATCH", f"/api/models/{mid}", {"name": "Renamed E2E Model"}, token=demo_tok)
check("model renamed", s == 200 and r["name"] == "Renamed E2E Model")

req("PATCH", f"/api/models/{mid}", {"name": demo_model_name}, token=demo_tok)
s, r, _ = req("GET", "/api/auth/me/session", token=demo_tok)
check("session info", s == 200 and r["seconds_remaining"] > 0 and r["ttl_hours"] == 12.0)
s, r, _ = req("GET", "/api/auth/me/activity", token=demo_tok)
check("personal activity feed", s == 200 and len(r["activity"]) >= 3)
s, r, _ = req("GET", "/api/admin/stats/storage", token=admin_tok)
check("storage stats", s == 200 and r["uploads"]["files"] >= 3 and r["encrypted_share_pct"] > 90, r.get("encrypted_share_pct"))
s, r, _ = req("GET", "/api/admin/audit/export", token=admin_tok)
check("audit csv export", s == 200 and (r if isinstance(r, bytes) else b"").startswith(b"id,action"))
s, r, _ = req("GET", "/api/admin/audit/export", token=demo_tok)
check("audit export blocked for member", s == 403)

s, r, _ = req("POST", "/api/models/upload", raw_body=part, token=demo_tok,
              content_type=f"multipart/form-data; boundary={boundary}")
check("duplicate upload rejected with 409", s == 409, s)

s, r, _ = req("POST", f"/api/jobs/{ex_job}/cancel", token=demo_tok)
check("cancel rejects finished job with 409", s == 409, s)
s, r, _ = req("POST", f"/api/jobs/{ex_job}/retry", token=demo_tok)
check("retry rejects finished job with 409", s == 409, s)

print("== 12. V5 endpoints ==")
s, r, _ = req("GET", f"/api/models/{mid}/history", token=demo_tok)
check("model history timeline", s == 200 and r["history"][0]["kind"] == "baseline"
      and r["run_count"] >= 1, r.get("run_count"))
s, r, _ = req("GET", "/api/jobs", token=demo_tok)
check("user job center list", s == 200 and len(r["jobs"]) >= 5)
s, r, _ = req("GET", "/api/jobs?status=success", token=demo_tok)
check("job status filter", s == 200 and all(j["status"] == "success" for j in r["jobs"]))
s, r, _ = req("GET", "/api/dashboard/insights", token=demo_tok)
check("insights computed", s == 200 and r["heaviest_model"] is not None and r["best_run"] is not None)
s, r, _ = req("GET", "/api/metrics")
check("prometheus metrics", s == 200 and "modelsmith_models_total" in (r if isinstance(r, str) else r.decode()))
s, r, _ = req("GET", "/api/config")
check("public config", s == 200 and r["max_upload_mb"] >= 100 and "rate_limits" in r)
s, r, _ = req("PATCH", f"/api/models/{mid}", {"notes": "test note", "tags": ["a", "b"]}, token=demo_tok)
check("notes+tags saved", s == 200 and r["tags"] == ["a", "b"])
req("PATCH", f"/api/models/{mid}", {"notes": "", "tags": []}, token=demo_tok)
s, r, _ = req("PATCH", f"/api/models/{mid}", {"tags": ["x" * 40]}, token=demo_tok)
check("oversized tag rejected", s == 422)

s, r, _ = req("POST", f"/api/projects/{proj_id}/archive", token=demo_tok)
check("project archived", s == 200 and r["archived"] is True)
s, r, _ = req("GET", "/api/projects", token=demo_tok)
archived_view = next((p for p in r["projects"] if p["id"] == proj_id), {})
check("archived flag visible in list", archived_view.get("archived") == 1)
s, r, _ = req("POST", f"/api/projects/{proj_id}/unarchive", token=demo_tok)
check("project unarchived", s == 200)

rq_dl = urllib.request.Request(f"{BASE}/api/models/{up_id}/download", method="GET")
rq_dl.add_header("Authorization", f"Bearer {demo_tok}")
with ur.urlopen(rq_dl, timeout=60) as resp:
    dl_bytes = resp.read()
check("original download byte-identical", dl_bytes == buf.getvalue(), len(dl_bytes))

s, r, _ = req("POST", "/api/admin/broadcast", {"title": "e2e check", "message": "broadcast pipe test"}, token=admin_tok)
check("admin broadcast", s == 200 and r["delivered"] >= 2, r.get("delivered"))
s, r, _ = req("POST", "/api/admin/broadcast", {"title": ""}, token=admin_tok)
check("broadcast validation", s == 422)
s, r, _ = req("GET", f"/api/admin/users/{tester_id}/detail", token=admin_tok)
check("admin user detail", s == 200 and r["user"]["email"] == TESTER)
s, r, _ = req("GET", f"/api/admin/users/{tester_id}/detail", token=demo_tok)
check("user detail blocked for member", s == 403)
s, r, _ = req("GET", "/api/admin/backup", token=admin_tok)
check("database backup", s == 200 and isinstance(r, bytes) and r[:15] == b"SQLite format 3")

print("== 13. V6 endpoints ==")
s, r, _ = req("GET", "/api/achievements", token=demo_tok)
ok_ach = s == 200 and r["earned_count"] >= 3 and r["total"] == 12
check("achievements computed", ok_ach, r.get("earned_count"))
check("achievement counters", r["counters"]["models"] >= 3)
s, r, _ = req("POST", f"/api/models/{mid}/share", token=demo_tok)
check("share link minted", s == 200 and r["token"], r)
share_tok = r.get("token", "")
s, r, _ = req("GET", f"/api/share/{share_tok}")
check("public share card", s == 200 and r["model"]["name"] and r["views"] >= 1)
s, r, _ = req("GET", "/api/share/nonexistent-token-xyz")
check("bad share 404", s == 404)

rq_sc = urllib.request.Request(f"{BASE}/api/runs/{run_id}/script", method="GET")
rq_sc.add_header("Authorization", f"Bearer {demo_tok}")
with ur.urlopen(rq_sc, timeout=30) as resp:
    script = resp.read().decode()
check("repro script generated", "import torch" in script and run_id in script
      and m2["name"] in script)
s, r, _ = req("GET", f"/api/models/{mid}", token=demo_tok)
check("efficiency score present", isinstance(r.get("efficiency_score"), int)
      and 1 <= r["efficiency_score"] <= 100, r.get("efficiency_score"))

print("== 14. V7 endpoints ==")
s, r, _ = req("GET", f"/api/projects/{proj_id}/stats", token=demo_tok)
check("project stats", s == 200 and r["models"] >= 1 and r["total_bytes"] > 0, r)
s, r, _ = req("GET", f"/api/models/{mid}/diff", token=demo_tok)
check("model diff vs best run", s == 200 and len(r["rows"]) >= 2
      and "summary" in r, r.get("rows"))
s, r, _ = req("GET", "/api/health")
check("health reports queue lag", "queue_lag_seconds" in r and "queue_depth" in r)
s, r, _ = req("GET", f"/api/models/m_doesnotexist/diff", token=demo_tok)
check("diff on missing model 404", s == 404)

print("== 14b. Own-infrastructure execution (runner protocol) ==")
import base64 as _b64
s, r, _ = req("POST", f"/api/models/{mid}/execute",
              body={"plan_id": "edge-lite", "mode": "own_infra"}, token=demo_tok)
check("own-infra execute accepted", s == 200 and r.get("mode") == "own_infra"
      and r.get("runner_token", "").startswith("msr_"), r)
oi_run = r.get("run_id", "")
oi_tok = r.get("runner_token", "")
s, j, _ = req("GET", f"/api/jobs/{r.get('job_id')}", token=demo_tok)
check("job waiting for runner", j.get("status") == "waiting_runner", j.get("status"))
s, mf, _ = req("GET", f"/api/runner/{oi_tok}/manifest", token=None)
check("runner manifest", s == 200 and mf["plan"]["plan_id"] == "edge-lite"
      and mf["model"]["name"], mf.get("plan"))
s, mb, _ = req("GET", f"/api/runner/{oi_tok}/model")
check("runner model download", s == 200 and len(mb) > 100, len(mb) if isinstance(mb, bytes) else mb)
s, r2, _ = req("POST", f"/api/runner/{oi_tok}/checkin",
               body={"progress": 40, "message": "Applying int8"}, token=None)
check("runner check-in", s == 200)
s, j, _ = req("GET", f"/api/jobs/{r.get('job_id')}", token=demo_tok)
check("check-in visible on job", j.get("progress") == 40 and "int8" in (j.get("message") or ""),
      (j.get("progress"), j.get("message")))

s, r2, _ = req("POST", f"/api/runner/{oi_tok}/result",
               body={"benchmark": {"baseline": {"size_mb": 1}}, "artifacts": []}, token=None)
check("result without artifacts refused", s == 422, s)
fake_art = _b64.b64encode(b"PK\x03\x04e2e-fake-artifact").decode()
s, r2, _ = req("POST", f"/api/runner/{oi_tok}/result", body={
    "steps": [{"technique": "int8", "status": "success", "note": "ok"}],
    "benchmark": {"baseline": {"size_mb": 10, "latency_ms": 20},
                  "optimized": {"size_mb": 3, "latency_ms": 12},
                  "size_saved_pct": 70.0, "latency_gain_pct": 40.0,
                  "output_agreement": {"agreement_pct": 100.0}},
    "repro": {"seed": 42}, "artifacts": [{"name": "optimized.onnx", "content_b64": fake_art}],
}, token=None)
check("runner result accepted", s == 200, r2)
s, rr, _ = req("GET", f"/api/runs/{oi_run}", token=demo_tok)
check("own-infra run success", rr.get("status") == "success"
      and rr.get("execution_mode") == "own_infra", rr.get("status"))
check("own-infra benchmark stored", (rr.get("benchmark") or {}).get("size_saved_pct") == 70.0)
check("own-infra artifact stored encrypted",
      any(a.get("encrypted") for a in (rr.get("artifacts") or [])))
s, r2, _ = req("GET", f"/api/runner/{oi_tok}/manifest")
check("runner token burned after result", s == 401)
s, r2, _ = req("GET", f"/api/runs/{oi_run}/runner-script", token=demo_tok)
check("runner script for finished run refused", s == 409)
s, r2, _ = req("DELETE", f"/api/runs/{oi_run}", token=demo_tok)
check("own-infra run deleted", s == 200, r2)

print("== 14c. AWS launch (validation, no real credentials) ==")
s, r, _ = req("POST", f"/api/models/{mid}/execute",
              body={"plan_id": "edge-lite", "mode": "own_infra"}, token=demo_tok)
aw_run = r.get("run_id", "")
s, r2, _ = req("POST", f"/api/runs/{aw_run}/aws-launch",
               body={"region": "us-east-1", "instance_type": "c6i.xlarge"}, token=demo_tok)
check("aws launch without creds 422", s == 422, (s, r2))
s, r2, _ = req("POST", f"/api/runs/{aw_run}/aws-launch",
               body={"region": "us-east-1", "instance_type": "c6i.xlarge",
                     "access_key_id": "x", "secret_access_key": "y"})
check("aws launch unauthenticated 401", s == 401)

s, r2, _ = req("POST", f"/api/runs/{aw_run}/aws-launch",
               body={"region": "us-east-1", "instance_type": "c6i.xlarge",
                     "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                     "secret_access_key": "fakeSecretKeyForValidationTest"}, token=demo_tok)
check("aws launch bogus creds honest error", s in (401, 403, 502)
      and isinstance(r2.get("detail"), str), (s, r2))
s, r2, _ = req("DELETE", f"/api/runs/{aw_run}", token=demo_tok)
check("aws test run deleted", s == 200, r2)

print("== 15. Run & project cleanup ==")
s, r, _ = req("DELETE", f"/api/runs/{run_id}", token=demo_tok)
check("run deleted", s == 200, r)
s, r, _ = req("GET", f"/api/runs/{run_id}", token=demo_tok)
check("deleted run 404", s == 404)
s, r, _ = req("DELETE", f"/api/projects/{proj_id}", token=demo_tok)
check("test project deleted (cascades models/runs/artifacts)", s == 200, r)
s, r, _ = req("GET", f"/api/projects/{proj_id}", token=demo_tok)
check("deleted project 404", s == 404)

print("== 15b. API keys, webhooks, project report ==")
import http.server as _hs
import threading as _th
import hashlib as _hl

s, r, _ = req("POST", "/api/auth/me/keys", body={"name": "e2e key"}, token=demo_tok)
check("api key created", s == 200 and r.get("token", "").startswith("msk_"), r)
e2e_key = r.get("token", "")
e2e_key_id = r.get("id", "")
s, r2, _ = req("GET", "/api/dashboard", token=e2e_key)
check("api key authenticates", s == 200, s)
s, r2, _ = req("GET", "/api/auth/me/keys", token=demo_tok)
check("key listed with prefix only", any(k["id"] == e2e_key_id and "token" not in k
      for k in r2.get("keys", [])), r2)
s, r2, _ = req("DELETE", f"/api/auth/me/keys/{e2e_key_id}", token=demo_tok)
check("api key revoked", s == 200)
s, r2, _ = req("GET", "/api/dashboard", token=e2e_key)
check("revoked key rejected", s == 401)

received = {}
class _Hook(_hs.BaseHTTPRequestHandler):
    def do_POST(self):
        received["body"] = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass
_rcv = _hs.HTTPServer(("127.0.0.1", 8198), _Hook)
_th.Thread(target=_rcv.serve_forever, daemon=True).start()
s, r2, _ = req("PUT", "/api/auth/me/webhook",
               body={"webhook_url": "http://127.0.0.1:8198/hook"}, token=demo_tok)
check("webhook url saved", s == 200)
s, r2, _ = req("POST", "/api/auth/me/webhook/test", token=demo_tok)
check("webhook test delivered", s == 200 and r2.get("ok") and received.get("body")
      and b"webhook_test" in received["body"], r2)
s, r2, _ = req("PUT", "/api/auth/me/webhook",
               body={"webhook_url": "ftp://nope"}, token=demo_tok)
check("bad webhook scheme 422", s == 422)
s, r2, _ = req("PUT", "/api/auth/me/webhook", body={"webhook_url": ""}, token=demo_tok)
check("webhook cleared", s == 200)
_rcv.shutdown()

import urllib.request as _ur
_r = _ur.Request(f"{BASE}/api/health")
with _ur.urlopen(_r) as _resp:
    _h = {k.lower(): v for k, v in _resp.headers.items()}
check("security headers present", _h.get("x-content-type-options") == "nosniff"
      and str(_h.get("x-frame-options", "")).lower() == "deny")
_r = _ur.Request(f"{BASE}/assets/app.js?v=9")
with _ur.urlopen(_r) as _resp:
    _cc = _resp.headers.get("Cache-Control", "")
check("versioned assets cached immutable", "immutable" in _cc, _cc)
s, dp, _ = req("GET", "/api/projects", token=demo_tok)
demo_proj = dp["projects"][0]["id"]
s, r2, _ = req("GET", f"/api/projects/{demo_proj}/report", token=demo_tok)
check("project report generated", s == 200 and b"Project Report" in (r2 if isinstance(r2, bytes) else b""))

print("== 15c. Account export, logout-everywhere, rate headers ==")
import urllib.request as _ur2
_r = _ur2.Request(f"{BASE}/api/health")
with _ur2.urlopen(_r) as _resp:
    check("rate limit remaining header", "x-ratelimit-remaining" in
          {k.lower() for k in _resp.headers.keys()})
s, r, _ = req("GET", "/api/dashboard/impact", token=demo_tok)
check("dashboard impact endpoint", s == 200 and isinstance(r.get("runs"), list))
s, r, _ = req("GET", "/api/auth/me/export", token=demo_tok)
import json as _xj
_x = _xj.loads(r) if isinstance(r, bytes) else (r or {})
check("account export returns full JSON", s == 200 and
      "profile" in _x and "models" in _x and "projects" in _x)
check("account export has runs", any(m.get("runs") is not None for m in _x.get("models", [])))

s, r, _ = req("POST", "/api/auth/login",
              body={"email": "demo@modelsmith.io", "password": "demo12345"})
tok_b = r.get("token", "")
s, r, _ = req("POST", "/api/auth/logout-all", token=demo_tok)
check("logout-everywhere accepted", s == 200)
s, r, _ = req("GET", "/api/dashboard", token=tok_b)
check("second session revoked", s == 401)
s, r, _ = req("POST", "/api/auth/login",
              body={"email": "demo@modelsmith.io", "password": "demo12345"})
check("fresh login after logout-all", s == 200)
demo_tok = r.get("token", demo_tok)

print("== 16. Input validation & abuse limits ==")
s, r, _ = req("POST", "/api/projects", body={"name": "X" * 300}, token=demo_tok)
check("oversized project name rejected 422", s == 422, r)
s, r, _ = req("POST", "/api/projects", body={"name": "ok", "description": "D" * 600}, token=demo_tok)
check("oversized description rejected 422", s == 422, r)
if s == 200:
    req("DELETE", f"/api/projects/{r['id']}", token=demo_tok)
s, r, _ = req("GET", "/api/dashboard", token="forged.token.value")
check("forged token 401", s == 401)
s, r, _ = req("GET", "/api/search?q=%27%20OR%201%3D1--", token=demo_tok)
check("sql-injection-style query safe", s == 200 and r["total"] == 0)
s, r, _ = req("GET", "/api/dashboard")
check("unauthenticated 401", s == 401)
s, r, _ = req("GET", "/assets/app.js", raw_body=None)
check("assets served", s == 200 and (isinstance(r, bytes) or s == 200))

print(f"\n{'='*50}\nRESULT: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
