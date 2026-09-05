#!/usr/bin/env python3"""End-to-end API verification for ModelSmith (run against live server)."""
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
time.sleep(1.1)  # ensure the pre-reset token's iat is strictly older than the watermark
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
# prefer the smallest seeded model for the execute stage (keeps artifacts tiny)
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
# restore default goals so later test runs see a pristine model
req("PUT", f"/api/models/{mid}/goals", {"objective": "balanced", "target_hardware": "cpu-server", "min_accuracy_pct": 95}, token=demo_tok)

print("== 6. Upload own model (FR-03) ==")
import torch  # venv python runs this script
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

print("== 8. Report (FR-14) ==")
import urllib.request as ur
rq = ur.Request(f"{BASE}/api/models/{mid}/report"); rq.add_header("Authorization", f"Bearer {demo_tok}")
with ur.urlopen(rq) as resp:
    md = resp.read().decode()
check("report markdown generated", "ModelSmith Report" in md and "Analysis" in md and "Execution history" in md)

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
# restore the demo model's original name so the seeded workspace stays pristine
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
# duplicate upload: same exact bytes as section 6 must be refused
s, r, _ = req("POST", "/api/models/upload", raw_body=part, token=demo_tok,
              content_type=f"multipart/form-data; boundary={boundary}")
check("duplicate upload rejected with 409", s == 409, s)
# cancel/retry guards: the job has already finished, so both must refuse with 409
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
# archive round-trip on the test project
s, r, _ = req("POST", f"/api/projects/{proj_id}/archive", token=demo_tok)
check("project archived", s == 200 and r["archived"] is True)
s, r, _ = req("GET", "/api/projects", token=demo_tok)
archived_view = next((p for p in r["projects"] if p["id"] == proj_id), {})
check("archived flag visible in list", archived_view.get("archived") == 1)
s, r, _ = req("POST", f"/api/projects/{proj_id}/unarchive", token=demo_tok)
check("project unarchived", s == 200)
# download original: byte-identical to what section 6 uploaded
rq_dl = urllib.request.Request(f"{BASE}/api/models/{up_id}/download", method="GET")
rq_dl.add_header("Authorization", f"Bearer {demo_tok}")
with ur.urlopen(rq_dl, timeout=60) as resp:
    dl_bytes = resp.read()
check("original download byte-identical", dl_bytes == buf.getvalue(), len(dl_bytes))
# admin: broadcast + user detail
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
s, r, _ = req("GET", f"/api/share/{share_tok}")   # public, no token
check("public share card", s == 200 and r["model"]["name"] and r["views"] >= 1)
s, r, _ = req("GET", "/api/share/nonexistent-token-xyz")
check("bad share 404", s == 404)
# reproducible script from the executed run
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

print("== 15. Run & project cleanup ==")
s, r, _ = req("DELETE", f"/api/runs/{run_id}", token=demo_tok)
check("run deleted", s == 200, r)
s, r, _ = req("GET", f"/api/runs/{run_id}", token=demo_tok)
check("deleted run 404", s == 404)
s, r, _ = req("DELETE", f"/api/projects/{proj_id}", token=demo_tok)
check("test project deleted (cascades models/runs/artifacts)", s == 200, r)
s, r, _ = req("GET", f"/api/projects/{proj_id}", token=demo_tok)
check("deleted project 404", s == 404)

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
