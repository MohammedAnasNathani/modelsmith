"""Model lifecycle API: upload (FR-03), goals (FR-06), plans & comparison
(FR-07–10), execution (FR-11), runs/benchmarks (FR-12), artifacts & reports
(FR-13), job status + notifications (FR-14).

Access control: every route resolves the model through its project and the
authenticated user (NFR-05/06/14). Uploads and artifacts are encrypted at
rest and validated before acceptance (NFR-06/07).
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from . import analysis as an
from . import config, executor, planner, reports, security
from .auth import current_user
from .database import audit, db, j, new_id, now, uj
from .jobs import enqueue, handler, notify
from .projects import _project_or_404

router = APIRouter(prefix="/api", tags=["models"])

ALLOWED_EXTS = {".pt", ".pth", ".onnx"}
RUNNER = None          # injected by main.py at startup


# ------------------------------------------------------------------ accessors
def _model_or_404(conn, model_id: str, user: dict) -> dict:
    row = conn.execute("SELECT * FROM models WHERE id=?", (model_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Model not found")
    m = dict(row)
    _project_or_404(conn, m["project_id"], user)
    return m


def _run_or_404(conn, run_id: str, user: dict) -> dict:
    row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Run not found")
    r = dict(row)
    _model_or_404(conn, r["model_id"], user)
    return r


# ------------------------------------------------------------------- FR-03
@router.post("/models/upload")
async def upload_model(
    project_id: str = Form(...),
    name: str = Form(...),
    input_shape: str = Form(""),
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
):
    orig_name = Path(file.filename or "model.pt").name
    ext = Path(orig_name).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(422, f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTS)}")
    name = name.strip()
    if not name:
        raise HTTPException(422, "Model name is required")
    if len(name) > 120:
        raise HTTPException(422, "Model name must be 120 characters or fewer")

    shape = None
    if input_shape.strip():
        try:
            shape = tuple(int(x) for x in re.split(r"[,xX*\s]+", input_shape.strip()) if x)
        except ValueError:
            raise HTTPException(422, "Input shape must be comma-separated integers")

    data = await file.read()
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {config.MAX_UPLOAD_MB} MB limit")
    if len(data) == 0:
        raise HTTPException(422, "Empty file")
    digest = _sha(data)

    # duplicate detection: same bytes already in this project (NFR-08)
    with db() as conn:
        _project_or_404(conn, project_id, user)
        dup = conn.execute(
            "SELECT id, name FROM models WHERE project_id=? AND sha256=?",
            (project_id, digest)).fetchone()
        if dup:
            raise HTTPException(
                409, {"message": "This exact file already exists in the project",
                      "existing_model_id": dup["id"], "existing_name": dup["name"]})
        model_id = new_id("m")
        stored_name = f"{model_id}{ext}.enc"
        config.UPLOADS_DIR.joinpath(stored_name).write_bytes(security.encrypt_bytes(data))
        conn.execute(
            "INSERT INTO models (id, project_id, name, framework, filename, orig_name, "
            "size_bytes, sha256, status, uploaded_by, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?, 'analyzing', ?, ?, ?)",
            (model_id, project_id, name.strip(), "onnx" if ext == ".onnx" else "pytorch",
             stored_name, orig_name, len(data), digest,
             user["id"], now(), now()),
        )
        audit(conn, user["id"], "upload", "model", model_id, f"{name} ({len(data)} bytes)")
        job_id = enqueue("analyze", model_id, model_id, user["id"], RUNNER)
        notify(conn, user["id"], "info", "Analysis started",
               f"Model '{name.strip()}' queued for analysis")
    return {"model_id": model_id, "job_id": job_id, "status": "analyzing"}


def _sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


# ----------------------------------------------------- analyze job (FR-04/05)
@handler("analyze")
def _analyze_job(job: dict, progress):
    with db() as conn:
        m = dict(conn.execute("SELECT * FROM models WHERE id=?", (job["ref_id"],)).fetchone())
    if not m:
        raise RuntimeError("model disappeared")

    progress(10, "Decrypting uploaded model")
    plain = config.TMP_DIR / f"an_{m['id']}{Path(m['orig_name']).suffix}"
    plain.write_bytes(security.decrypt_bytes(
        config.UPLOADS_DIR.joinpath(m["filename"]).read_bytes()))
    try:
        progress(30, "Extracting graph, layers, FLOPs and memory profile")
        runs = config.BENCHMARK_RUNS
        if m["framework"] == "onnx":
            analysis = an.analyze_onnx(plain, runs)
        else:
            analysis = an.analyze_torch(plain, None, runs)

        progress(70, "Generating ranked optimization plans")
        goals = uj(m.get("goals"), planner.DEFAULT_GOALS)
        plans = planner.generate_plans(analysis, goals)

        progress(90, "Storing analysis")
        with db() as conn:
            conn.execute(
                "UPDATE models SET status='analyzed', analysis=?, plans=?, "
                "updated_at=? WHERE id=?",
                (j(analysis), j(plans), now(), m["id"]),
            )
            notify(conn, m["uploaded_by"], "success", "Analysis complete",
                   f"'{m['name']}' analyzed: {len(plans['valid'])} valid plans ranked")
            audit(conn, m["uploaded_by"], "analyze", "model", m["id"],
                  f"arch={analysis.get('arch')}")
        return {"arch": analysis.get("arch"),
                "valid_plans": len(plans["valid"])}
    finally:
        plain.unlink(missing_ok=True)


# ----------------------------------------------------------------- read APIs
@router.get("/search")
def search_models(q: str = "", status: str = "", user: dict = Depends(current_user)):
    """Server-side search across all of the caller's models."""
    with db() as conn:
        rows = conn.execute(
            "SELECT m.id, m.name, m.framework, m.status, m.size_bytes, m.created_at, "
            "m.project_id, p.name AS project FROM models m "
            "JOIN projects p ON p.id=m.project_id WHERE p.owner_id=? "
            "ORDER BY m.created_at DESC", (user["id"],)).fetchall()
    ql = (q or "").strip().lower()
    hits = [dict(r) for r in rows
            if (not ql or ql in r["name"].lower() or ql in r["framework"].lower()
                or ql in r["project"].lower())
            and (not status or r["status"] == status)]
    return {"results": hits, "total": len(hits), "scanned": len(rows)}


@router.patch("/models/{model_id}")
def rename_model(model_id: str, body: dict, user: dict = Depends(current_user)):
    """Update name, notes and free-form tags. Only provided fields change."""
    name = str(body.get("name", "")).strip()
    notes = str(body.get("notes", "")).strip()[:4000]
    tags = body.get("tags")
    if "name" in body and (not name or len(name) > 80):
        raise HTTPException(422, "Name must be 1-80 characters")
    if tags is not None:
        if not isinstance(tags, list) or len(tags) > 8 \
                or any(not isinstance(t, str) or len(t) > 24 for t in tags):
            raise HTTPException(422, "tags must be a list of up to 8 short strings")
    with db() as conn:
        m = _model_or_404(conn, model_id, user)
        sets, args = ["updated_at=?"], [now()]
        if "name" in body:
            sets.append("name=?"); args.append(name)
        if "notes" in body:
            sets.append("notes=?"); args.append(notes)
        if tags is not None:
            sets.append("tags=?"); args.append(j([t.strip() for t in tags if t.strip()]))
        args.append(model_id)
        conn.execute(f"UPDATE models SET {', '.join(sets)} WHERE id=?", args)
        audit(conn, user["id"], "update", "model", model_id,
              f"{m['name']}: metadata" if "name" not in body else f"{m['name']} -> {name}")
    return {"ok": True, "name": name or m["name"], "notes": notes or m.get("notes", ""),
            "tags": tags if tags is not None else uj(m.get("tags"))}


@router.get("/models/{model_id}/history")
def model_history(model_id: str, user: dict = Depends(current_user)):
    """Full run timeline: size/latency progression across executions."""
    with db() as conn:
        m = _model_or_404(conn, model_id, user)
        runs = conn.execute(
            "SELECT id, plan_id, plan_name, status, created_at, finished_at, benchmark "
            "FROM runs WHERE model_id=? ORDER BY created_at ASC", (model_id,)).fetchall()
    base = (uj(m.get("analysis")) or {}).get("benchmark", {})
    series = [{
        "label": "original", "kind": "baseline",
        "size_mb": round((base.get("size_mb") or m["size_bytes"] / 1e6), 2),
        "latency_ms": base.get("latency_ms"),
        "ts": m["created_at"],
    }]
    for r in runs:
        bm = uj(r["benchmark"]) or {}
        opt = bm.get("optimized") or {}
        series.append({
            "label": r["plan_name"], "kind": r["status"], "run_id": r["id"],
            "size_mb": opt.get("size_mb"),
            "latency_ms": opt.get("latency_ms"),
            "size_saved_pct": bm.get("size_saved_pct"),
            "latency_gain_pct": bm.get("latency_gain_pct"),
            "ts": r["created_at"],
        })
    return {"history": series, "run_count": len(runs),
            "best_size_mb": min((s["size_mb"] for s in series
                                 if s["size_mb"] is not None), default=None)}


@router.get("/models/{model_id}/download")
def download_original(model_id: str, user: dict = Depends(current_user)):
    """Stream back the original upload, decrypted, exactly as it arrived."""
    with db() as conn:
        m = _model_or_404(conn, model_id, user)
    enc = config.UPLOADS_DIR / m["filename"]
    if not enc.exists():
        raise HTTPException(410, "Original file missing on server")
    data = security.decrypt_bytes(enc.read_bytes())
    return Response(
        content=data, media_type="application/octet-stream",
        headers={"Content-Disposition":
                 f'attachment; filename="{m["orig_name"] or m["id"]}"'},
    )


@router.get("/jobs")
def my_jobs(status: str = "", user: dict = Depends(current_user)):
    """Everything the job runner is doing (or did) for this account."""
    q = ("SELECT id, type, ref_id, model_id, status, progress, message, error, "
         "attempts, created_at, started_at, finished_at FROM jobs WHERE user_id=?")
    args = [user["id"]]
    if status:
        q += " AND status=?"; args.append(status)
    q += " ORDER BY created_at DESC LIMIT 60"
    with db() as conn:
        rows = conn.execute(q, args).fetchall()
    return {"jobs": [dict(r) for r in rows]}


@router.get("/models/{model_id}/suggestions")
def model_suggestions(model_id: str, user: dict = Depends(current_user)):
    """Advice derived from the stored analysis: what to do next and why."""
    with db() as conn:
        m = _model_or_404(conn, model_id, user)
    if m["status"] != "analyzed":
        raise HTTPException(409, "Model must be analyzed first")
    a = uj(m.get("analysis")) or {}
    plans = (uj(m.get("plans")) or {})
    valid = plans.get("valid") or []
    bench = a.get("benchmark") or {}

    tips: list[dict] = []
    conv_share = a.get("conv_param_share_pct") or 0
    if a.get("arch") == "mlp":
        tips.append({"title": "Dense layers dominate",
                     "body": "MLPs compress beautifully. INT8 alone usually halves the "
                             "footprint with no measurable agreement loss.",
                     "action": "Run the INT8 dynamic plan first, then compare."})
    if conv_share >= 50:
        tips.append({"title": f"{conv_share:.0f}% of parameters live in convolutions",
                     "body": "Conv-heavy networks respond well to channel pruning "
                             "combined with INT8. The planner ranks both.",
                     "action": "Compare the prune+quantize plans side by side."})
    if (bench.get("latency_ms") or 0) > 10:
        tips.append({"title": f"Baseline latency is {bench['latency_ms']:.1f} ms",
                     "body": "Above 10 ms, interactive serving gets awkward. Export to "
                             "ONNX Runtime typically cuts CPU latency 30-50%.",
                     "action": "Prefer plans that include ONNX export."})
    if valid:
        best = valid[0]
        tips.append({"title": f"Best ranked plan: {best['plan_id']}",
                     "body": best.get("tagline", ""),
                     "action": f"Predicted {best['predicted']['size_saved_pct']}% smaller, "
                               f"{best['predicted']['latency_gain_pct']}% faster."})
    if (a.get("param_size_mb") or 0) * 1e6 < m["size_bytes"] * 0.5:
        tips.append({"title": "File is much larger than its parameters",
                     "body": "The checkpoint carries optimizer state or buffers. A clean "
                             "export can shrink it even before quantization.",
                     "action": "Any export-based plan will strip the dead weight."})
    return {"suggestions": tips[:5]}


@router.get("/models/compare")
def compare_models(
    model_a: str, model_b: str, user: dict = Depends(current_user)
):
    """Compare two analyzed models side by side."""
    with db() as conn:
        ma = _model_or_404(conn, model_a, user)
        mb = _model_or_404(conn, model_b, user)
    if ma["status"] != "analyzed" or mb["status"] != "analyzed":
        raise HTTPException(409, "Both models must be analyzed before comparison")
    return {
        "model_a": {"id": ma["id"], "name": ma["name"], "framework": ma["framework"],
                     "size_bytes": ma["size_bytes"], "analysis": uj(ma["analysis"])},
        "model_b": {"id": mb["id"], "name": mb["name"], "framework": mb["framework"],
                     "size_bytes": mb["size_bytes"], "analysis": uj(mb["analysis"])},
    }


@router.get("/models/{model_id}")
def get_model(model_id: str, user: dict = Depends(current_user)):
    with db() as conn:
        m = _model_or_404(conn, model_id, user)
        runs = conn.execute(
            "SELECT * FROM runs WHERE model_id=? ORDER BY created_at DESC",
            (model_id,)).fetchall()
        jobs = conn.execute(
            "SELECT id, type, status, progress, message, created_at FROM jobs "
            "WHERE model_id=? ORDER BY created_at DESC LIMIT 5", (model_id,)).fetchall()
    m.pop("filename", None)
    m["tags"] = uj(m.get("tags")) or []
    # deployment readiness: honest heuristic, 0-100, lower is heavier
    a = uj(m.get("analysis")) or {}
    lat = (a.get("benchmark") or {}).get("latency_ms") or 0
    size_mb = m["size_bytes"] / 1e6
    m["efficiency_score"] = round(max(1, min(100,
        100 - min(55, lat * 4) - min(35, size_mb / 8) - 10)))
    return m | {
        "analysis": uj(m.get("analysis")), "goals": uj(m.get("goals")),
        "plans": uj(m.get("plans")),
        "runs": [dict(r) | {"steps": uj(r["steps"]), "benchmark": uj(r["benchmark"]),
                            "artifacts": uj(r["artifacts"]), "repro": uj(r["repro"])}
                 for r in runs],
        "jobs": [dict(x) for x in jobs],
    }


@router.delete("/models/{model_id}")
def delete_model(model_id: str, user: dict = Depends(current_user)):
    import shutil
    with db() as conn:
        m = _model_or_404(conn, model_id, user)
        config.UPLOADS_DIR.joinpath(m["filename"]).unlink(missing_ok=True)
        for r in conn.execute("SELECT id FROM runs WHERE model_id=?", (model_id,)).fetchall():
            shutil.rmtree(config.ARTIFACTS_DIR / r["id"], ignore_errors=True)
        conn.execute("DELETE FROM runs WHERE model_id=?", (model_id,))
        conn.execute("DELETE FROM jobs WHERE model_id=?", (model_id,))
        conn.execute("DELETE FROM models WHERE id=?", (model_id,))
        audit(conn, user["id"], "delete", "model", model_id, m["name"])
    return {"ok": True}


# ------------------------------------------------------------------- FR-06
@router.put("/models/{model_id}/goals")
def set_goals(model_id: str, body: dict, user: dict = Depends(current_user)):
    with db() as conn:
        m = _model_or_404(conn, model_id, user)
    if m["status"] != "analyzed":
        raise HTTPException(409, "Model must finish analysis before setting goals")

    goals = planner.DEFAULT_GOALS | {k: v for k, v in body.items() if v is not None}
    if goals["objective"] not in ("min_size", "min_latency", "min_memory", "balanced"):
        raise HTTPException(422, "objective must be min_size|min_latency|min_memory|balanced")
    if goals["target_hardware"] not in planner.HARDWARE_PROFILES:
        raise HTTPException(422, f"target_hardware must be one of "
                                 f"{sorted(planner.HARDWARE_PROFILES)}")

    analysis = uj(m.get("analysis")) or {}
    plans = planner.generate_plans(analysis, goals)
    with db() as conn:
        conn.execute("UPDATE models SET goals=?, plans=?, updated_at=? WHERE id=?",
                     (j(goals), j(plans), now(), model_id))
        audit(conn, user["id"], "set_goals", "model", model_id, goals["objective"])
    return {"goals": goals, "plans": plans}


# ------------------------------------------------- FR-11 execute + FR-12/13
@router.post("/models/{model_id}/execute")
def execute_plan(model_id: str, body: dict, user: dict = Depends(current_user)):
    plan_id = str(body.get("plan_id", ""))
    with db() as conn:
        m = _model_or_404(conn, model_id, user)
    if m["status"] != "analyzed":
        raise HTTPException(409, "Model is not analyzed yet")
    plans = uj(m.get("plans")) or {}
    plan = next((p for p in plans.get("valid", []) if p["plan_id"] == plan_id), None)
    if not plan:
        raise HTTPException(404, f"Plan '{plan_id}' not found or not valid for this model")

    run_id = new_id("run")
    with db() as conn:
        conn.execute(
            "INSERT INTO runs (id, model_id, plan_id, plan_name, user_id, status, "
            "created_at) VALUES (?,?,?,?,?,'queued',?)",
            (run_id, model_id, plan_id, plan["tagline"], user["id"], now()))
        job_id = enqueue("execute", run_id, model_id, user["id"], RUNNER)
        notify(conn, user["id"], "info", "Optimization started",
               f"Plan '{plan['tagline']}' executing on '{m['name']}'")
        audit(conn, user["id"], "execute", "run", run_id, plan_id)
    return {"run_id": run_id, "job_id": job_id}


@handler("execute")
def _execute_job(job: dict, progress):
    with db() as conn:
        run = dict(conn.execute("SELECT * FROM runs WHERE id=?", (job["ref_id"],)).fetchone())
        m = dict(conn.execute("SELECT * FROM models WHERE id=?", (run["model_id"],)).fetchone())
        plan = next(p for p in (uj(m.get("plans")) or {}).get("valid", [])
                    if p["plan_id"] == run["plan_id"])
        conn.execute("UPDATE runs SET status='running' WHERE id=?", (run["id"],))

    try:
        result = executor.run_plan_pipeline(m, plan, run["id"], progress)
        with db() as conn:
            conn.execute(
                "UPDATE runs SET status='success', steps=?, benchmark=?, artifacts=?, "
                "repro=?, finished_at=? WHERE id=?",
                (j(result["steps"]), j(result["benchmark"]), j(result["artifacts"]),
                 j(result["repro"]), now(), run["id"]))
            notify(conn, m["uploaded_by"], "success", "Optimization complete",
                   f"'{plan['tagline']}' on '{m['name']}': size −"
                   f"{result['benchmark']['size_saved_pct']}%")
            audit(conn, m["uploaded_by"], "execute_done", "run", run["id"], "success")
        return {"benchmark": result["benchmark"]}
    except Exception as e:                              # noqa: BLE001
        with db() as conn:
            conn.execute("UPDATE runs SET status='failed', error=?, finished_at=? "
                         "WHERE id=?", (f"{type(e).__name__}: {e}", now(), run["id"]))
            notify(conn, m["uploaded_by"], "error", "Optimization failed",
                   f"'{plan['tagline']}': {type(e).__name__}: {e}")
        raise


# ------------------------------------------------------------------- FR-13
@router.get("/runs/{run_id}")
def get_run(run_id: str, user: dict = Depends(current_user)):
    with db() as conn:
        r = _run_or_404(conn, run_id, user)
        job = conn.execute("SELECT * FROM jobs WHERE ref_id=?", (run_id,)).fetchone()
    r |= {"steps": uj(r["steps"]), "benchmark": uj(r["benchmark"]),
          "artifacts": uj(r["artifacts"]), "repro": uj(r["repro"])}
    if job:
        r["job"] = {"id": job["id"], "status": job["status"],
                    "progress": job["progress"], "message": job["message"]}
    return r


@router.delete("/runs/{run_id}")
def delete_run(run_id: str, user: dict = Depends(current_user)):
    """Remove a run and its encrypted artifacts."""
    import shutil
    with db() as conn:
        r = _run_or_404(conn, run_id, user)
        conn.execute("DELETE FROM runs WHERE id=?", (run_id,))
        conn.execute("DELETE FROM jobs WHERE ref_id=?", (run_id,))
        audit(conn, user["id"], "delete", "run", run_id, r.get("plan_name", ""))
    shutil.rmtree(config.ARTIFACTS_DIR / run_id, ignore_errors=True)
    return {"ok": True}


@router.get("/runs/{run_id}/artifacts/{name}/download")
def download_artifact(run_id: str, name: str, user: dict = Depends(current_user)):
    if "/" in name or ".." in name or not name.endswith((".pt", ".onnx")):
        raise HTTPException(400, "Invalid artifact name")
    with db() as conn:
        r = _run_or_404(conn, run_id, user)
        arts = uj(r.get("artifacts")) or []
    if not any(a["name"] == name for a in arts):
        raise HTTPException(404, "Artifact not part of this run")
    enc = config.ARTIFACTS_DIR / run_id / f"{name}.enc"
    if not enc.exists():
        raise HTTPException(410, "Artifact file missing on server")
    data = security.decrypt_bytes(enc.read_bytes())
    media = "application/octet-stream"
    return Response(
        content=data, media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/models/{model_id}/report")
def download_report(model_id: str, user: dict = Depends(current_user)):
    with db() as conn:
        m = _model_or_404(conn, model_id, user)
        runs = conn.execute("SELECT * FROM runs WHERE model_id=? "
                            "ORDER BY created_at DESC", (model_id,)).fetchall()
    md = reports.model_report(m, [dict(r) for r in runs])
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", m["name"])
    return Response(
        content=md, media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition":
                 f'attachment; filename="modelsmith_{safe_name}_report.md"'},
    )




# ------------------------------------------------------------- V7: diff
@router.get("/models/{model_id}/diff")
def model_diff(model_id: str, user: dict = Depends(current_user)):
    """Original vs best successful run: what changed, by how much."""
    with db() as conn:
        m = _model_or_404(conn, model_id, user)
        runs = conn.execute(
            "SELECT * FROM runs WHERE model_id=? AND status='success' "
            "ORDER BY json_extract(benchmark,'$.size_saved_pct') DESC",
            (model_id,)).fetchall()
    if not runs:
        raise HTTPException(409, "No successful run to compare against yet")
    r = dict(runs[0])
    a = uj(m.get("analysis")) or {}
    bm = uj(r.get("benchmark")) or {}
    base, opt = bm.get("baseline") or {}, bm.get("optimized") or {}
    rows = []
    def add(label, before, after, unit="", better="lower"):
        if before is None and after is None: return
        delta = None
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            delta = round(after - before, 3)
        rows.append({"metric": label, "before": before, "after": after,
                     "delta": delta, "unit": unit, "better": better})
    add("Size (MB)", base.get("size_mb"), opt.get("size_mb"))
    add("Latency (ms)", base.get("latency_ms"), opt.get("latency_ms"))
    add("p95 latency (ms)", base.get("p95_ms"), opt.get("p95_ms"))
    add("Throughput (inf/s)", base.get("throughput_fps"), opt.get("throughput_fps"),
        better="higher")
    ag = (bm.get("output_agreement") or {})
    return {
        "run": {"id": r["id"], "plan_name": r["plan_name"], "created_at": r["created_at"]},
        "agreement_pct": ag.get("agreement_pct"),
        "rows": rows,
        "summary": {"size_saved_pct": bm.get("size_saved_pct"),
                     "latency_gain_pct": bm.get("latency_gain_pct")},
    }


# ------------------------------------------------------------- V6: shares
@router.post("/models/{model_id}/share")
def create_share(model_id: str, user: dict = Depends(current_user)):
    """Mint a public, read-only link for this model's report card."""
    import secrets
    with db() as conn:
        _model_or_404(conn, model_id, user)
        token = secrets.token_urlsafe(9)
        conn.execute(
            "INSERT INTO shares (id, token, model_id, created_by, views, created_at) "
            "VALUES (?,?,?,?,0,?)",
            (new_id("shr"), token, model_id, user["id"], now()))
        audit(conn, user["id"], "share", "model", model_id, token[:6])
    return {"share_url": f"/#/share/{token}", "token": token}


@router.get("/share/{token}")
def public_share(token: str):
    """Unauthenticated report card: who, what, and how well it optimized."""
    with db() as conn:
        row = conn.execute("SELECT * FROM shares WHERE token=?", (token,)).fetchone()
        if not row:
            raise HTTPException(404, "Share link not found or revoked")
        m = conn.execute("SELECT * FROM models WHERE id=?", (row["model_id"],)).fetchone()
        if not m:
            raise HTTPException(410, "The shared model no longer exists")
        m = dict(m)
        runs = conn.execute(
            "SELECT plan_name, status, benchmark, created_at FROM runs "
            "WHERE model_id=? ORDER BY created_at DESC", (m["id"],)).fetchall()
        conn.execute("UPDATE shares SET views=views+1 WHERE id=?", (row["id"],))
    a = uj(m.get("analysis")) or {}
    best = None
    for r in runs:
        bm = uj(r["benchmark"]) or {}
        if r["status"] == "success" and (best is None or
                (bm.get("size_saved_pct") or 0) > (best.get("size_saved_pct") or 0)):
            best = bm | {"plan_name": r["plan_name"]}
    return {
        "model": {"name": m["name"], "framework": m["framework"],
                  "size_bytes": m["size_bytes"], "created_at": m["created_at"],
                  "sha256": m["sha256"]},
        "analysis_summary": {
            "total_params": a.get("total_params"), "layer_count": a.get("layer_count"),
            "total_flops": a.get("total_flops"),
            "latency_ms": (a.get("benchmark") or {}).get("latency_ms"),
        },
        "best_run": best,
        "run_count": len(runs),
        "views": row["views"] + 1,
        "shared_at": row["created_at"],
    }


# ------------------------------------------------- V6: reproducible script
@router.get("/runs/{run_id}/script")
def repro_script(run_id: str, user: dict = Depends(current_user)):
    """A standalone Python script that mirrors what this run did, using the
    versions and plan recorded at execution time."""
    with db() as conn:
        r = _run_or_404(conn, run_id, user)
        m = dict(conn.execute("SELECT * FROM models WHERE id=?", (r["model_id"],)).fetchone())
    repro = uj(r.get("repro")) or {}
    bm = uj(r.get("benchmark")) or {}
    steps = uj(r.get("steps")) or []
    tech = r.get("plan_id", "")
    base_name = m.get("orig_name") or "model.pt"
    lines = [
        '"""Reproduces ModelSmith run ' + r["id"] + ' on ' + repr(m["name"]) + '.',
        '',
        'Recorded environment: python ' + str((repro.get("versions") or {}).get("python", "?")) +
        ', torch ' + str((repro.get("versions") or {}).get("torch", "?")) +
        ', onnxruntime ' + str((repro.get("versions") or {}).get("onnxruntime") or "?") + '.',
        'Plan: ' + r.get("plan_name", tech) + '.',
        'Original size: ' + str(round(bm.get("baseline", {}).get("size_mb", 0), 2)) + ' MB'
        if bm.get("baseline") else 'Original size: unknown',
        '"""',
        'import torch',
        'import torch.quantization as tq',
        '',
        'MODEL_PATH = "' + base_name + '"   # the original upload',
        '',
        'model = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)',
        'model.eval()',
        '',
    ]
    if "int8" in tech or "quant" in tech.lower():
        lines += [
            '# dynamic INT8 quantization (same as the recorded run)',
            'q = tq.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)',
            'torch.save(q, "optimized_int8.pt")',
            '',
            '# optional: export to ONNX and quantize there instead',
            '# dummy = torch.zeros(1, *model.__dict__.get("_ms_shape", [1, 784]))',
            '# torch.onnx.export(q, dummy, "model.onnx", opset_version=13)',
        ]
    if "prune" in tech.lower():
        lines += [
            '',
            '# magnitude pruning was part of this plan;',
            '# re-run ModelSmith for the exact mask and sparsity accounting',
        ]
    lines += [
        '',
        'print("done. compare sizes with:")',
        'import os; print(round(os.path.getsize(MODEL_PATH)/1e6, 2), "MB ->",',
        '      round(os.path.getsize("optimized_int8.pt")/1e6, 2), "MB")',
    ]
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in m["name"])
    return Response(
        content="\n".join(lines), media_type="text/x-python",
        headers={"Content-Disposition":
                 f'attachment; filename="repro_{safe}_{run_id}.py"'})


# ------------------------------------------------------- V6: achievements
ACHIEVEMENT_DEFS = [
    ("first_blood", "First Steps", "Upload your first model", "◈"),
    ("reader", "Know Your Layers", "Complete a full analysis", "◎"),
    ("operator", "Pipeline Operator", "Execute a plan end to end", "⚙"),
    ("half_way", "The 50% Club", "Cut a model's size by half or more", "✂"),
    ("eighty_club", "The 80% Club", "Ship something 80% smaller", "★"),
    ("collector", "Collector", "Hold five models at once", "▤"),
    ("forge_master", "Forge Master", "Land ten successful runs", "♜"),
    ("polyglot", "Polyglot", "Work in both PyTorch and ONNX", "⇄"),
    ("night_owl", "Night Shift", "Run a job between midnight and 5am", "☾"),
    ("repeat_customer", "Trust but Verify", "Execute the same plan twice", "↻"),
    ("librarian", "Librarian", "Leave notes on a model", "✎"),
    ("tagger", "Tag, You're It", "Tag a model for later", "🏷"),
]


@router.get("/achievements")
def achievements(user: dict = Depends(current_user)):
    """Twelve badges, earned from real history, never granted on faith."""
    uid = user["id"]
    with db() as conn:
        def one(q, *a):
            return conn.execute(q, a).fetchone()[0]
        mine = "FROM models m JOIN projects p ON p.id=m.project_id WHERE p.owner_id=?"
        runs = ("FROM runs r JOIN models m ON m.id=r.model_id "
                "JOIN projects p ON p.id=m.project_id WHERE p.owner_id=?")
        state = {
            "first_blood": one(f"SELECT COUNT(*) {mine}", uid) >= 1,
            "reader": one(f"SELECT COUNT(*) {mine} AND m.status='analyzed'", uid) >= 1,
            "operator": one(f"SELECT COUNT(*) {runs} AND r.status='success'", uid) >= 1,
            "half_way": one(f"SELECT COUNT(*) {runs} AND r.status='success' "
                            "AND json_extract(r.benchmark,'$.size_saved_pct') >= 50", uid) >= 1,
            "eighty_club": one(f"SELECT COUNT(*) {runs} AND r.status='success' "
                               "AND json_extract(r.benchmark,'$.size_saved_pct') >= 80", uid) >= 1,
            "collector": one(f"SELECT COUNT(*) {mine}", uid) >= 5,
            "forge_master": one(f"SELECT COUNT(*) {runs} AND r.status='success'", uid) >= 10,
            "polyglot": one(f"SELECT COUNT(DISTINCT m.framework) {mine}", uid) >= 2,
            "night_owl": one("SELECT COUNT(*) FROM jobs WHERE user_id=? "
                             "AND strftime('%H', created_at, 'unixepoch', 'localtime') "
                             "BETWEEN '00' AND '04'", uid) >= 1,
            "repeat_customer": one(f"SELECT COUNT(*) FROM (SELECT r.model_id, r.plan_id "
                                   f"FROM runs r JOIN models m ON m.id=r.model_id "
                                   f"JOIN projects p ON p.id=m.project_id "
                                   f"WHERE p.owner_id=? GROUP BY r.model_id, r.plan_id "
                                   f"HAVING COUNT(*) >= 2)", uid) >= 1,
            "librarian": one(f"SELECT COUNT(*) {mine} AND m.notes != ''", uid) >= 1,
            "tagger": one(f"SELECT COUNT(*) {mine} AND m.tags != '[]'", uid) >= 1,
        }
        counters = {
            "models": one(f"SELECT COUNT(*) {mine}", uid),
            "analyzed": one(f"SELECT COUNT(*) {mine} AND m.status='analyzed'", uid),
            "runs": one(f"SELECT COUNT(*) {runs} AND r.status='success'", uid),
            "best_save": one(f"SELECT COALESCE(MAX(json_extract(r.benchmark,"
                             f"'$.size_saved_pct')),0) {runs} AND r.status='success'", uid),
        }
    out = [{"id": i, "name": n, "desc": d, "icon": ic, "earned": state[i]}
           for i, n, d, ic in ACHIEVEMENT_DEFS]
    return {"achievements": out,
            "earned_count": sum(state.values()),
            "total": len(ACHIEVEMENT_DEFS), "counters": counters}

# ------------------------------------------------------ FR-14 jobs + notifs
@router.get("/jobs/{job_id}")
def job_status(job_id: str, user: dict = Depends(current_user)):
    with db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    job = dict(row)
    if job["user_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "Not your job")
    return job | {"result": uj(job.get("result"))}


def _own_job_or_404(conn, job_id: str, user: dict) -> dict:
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    job = dict(row)
    if job["user_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "Not your job")
    return job


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, user: dict = Depends(current_user)):
    """Cancel a queued job. Running work cannot be interrupted safely,
    so those are reported back honestly instead of fake-cancelled."""
    with db() as conn:
        job = _own_job_or_404(conn, job_id, user)
        if job["status"] != "queued":
            raise HTTPException(409, f"Only queued jobs can be cancelled "
                                     f"(this one is {job['status']})")
        conn.execute(
            "UPDATE jobs SET status='failed', error='cancelled by user', "
            "message='cancelled', finished_at=? WHERE id=?", (now(), job_id))
        if job["type"] == "execute":
            conn.execute("UPDATE runs SET status='failed', error='cancelled by user' "
                         "WHERE id=? AND status='queued'", (job["ref_id"],))
        audit(conn, user["id"], "cancel", "job", job_id, job["type"])
    if RUNNER:
        RUNNER.submit(job_id)      # no-op for failed jobs; keeps dispatcher tidy
    return {"ok": True, "status": "cancelled"}


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, user: dict = Depends(current_user)):
    """Requeue a failed job with a fresh attempt counter."""
    with db() as conn:
        job = _own_job_or_404(conn, job_id, user)
        if job["status"] != "failed":
            raise HTTPException(409, f"Only failed jobs can be retried "
                                     f"(this one is {job['status']})")
        conn.execute(
            "UPDATE jobs SET status='queued', attempts=0, error=NULL, "
            "progress=0, message='requeued by user' WHERE id=?", (job_id,))
        if job["type"] == "execute":
            conn.execute("UPDATE runs SET status='queued', error=NULL "
                         "WHERE id=? AND status='failed'", (job["ref_id"],))
        audit(conn, user["id"], "retry", "job", job_id, job["type"])
    if RUNNER:
        RUNNER.submit(job_id)
    return {"ok": True, "status": "queued"}


@router.get("/notifications")
def list_notifications(user: dict = Depends(current_user)):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 30",
            (user["id"],)).fetchall()
        unread = conn.execute(
            "SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0",
            (user["id"],)).fetchone()["c"]
    return {"notifications": [dict(r) for r in rows], "unread": unread}


@router.post("/notifications/read")
def mark_read(user: dict = Depends(current_user)):
    with db() as conn:
        conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user["id"],))
    return {"ok": True}
