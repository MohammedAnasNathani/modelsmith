"""FR-15 Administration + NFR-04/13 health & observability.

/api/health is public (availability probing); everything under /api/admin
requires the admin role (least privilege, NFR-05).
"""
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from . import config
from .auth import current_user, require_admin
from .database import audit, db, new_id, uj

router = APIRouter(prefix="/api", tags=["admin"])
_STARTED = time.time()


@router.get("/health")
def health():
    """NFR-04: liveness + dependency + queue snapshot."""
    checks = {}
    try:
        with db() as conn:
            users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            models = conn.execute("SELECT COUNT(*) c FROM models").fetchone()["c"]
            jobs = conn.execute(
                "SELECT status, COUNT(*) c FROM jobs GROUP BY status").fetchall()
            queue_depth = conn.execute(
                "SELECT COUNT(*) c FROM jobs WHERE status='queued'").fetchone()["c"]
        checks["database"] = {"ok": True}
        counts = {r["status"]: r["c"] for r in jobs}
    except Exception as e:                              # noqa: BLE001
        checks["database"] = {"ok": False, "error": str(e)}
        users = models = queue_depth = 0
        counts = {}

    versions = {}
    try:
        import torch
        versions["torch"] = torch.__version__
    except ImportError:
        versions["torch"] = None
    try:
        import onnxruntime
        versions["onnxruntime"] = onnxruntime.__version__
    except ImportError:
        versions["onnxruntime"] = None

    data_bytes = sum(
        f.stat().st_size for f in config.DATA_DIR.rglob("*") if f.is_file())
    with db() as conn:
        oldest = conn.execute(
            "SELECT MIN(created_at) t FROM jobs WHERE status='queued'").fetchone()["t"]
    import time as _t
    queue_lag = round(_t.time() - oldest, 1) if oldest else 0.0
    return {
        "status": "ok" if checks["database"]["ok"] else "degraded",
        "service": "modelsmith", "version": config.APP_VERSION,
        "uptime_seconds": round(time.time() - _STARTED, 1),
        "checks": checks,
        "counts": {"users": users, "models": models, "jobs": counts},
        "queue_depth": queue_depth,
        "queue_lag_seconds": queue_lag,
        "data_dir_mb": round(data_bytes / 1e6, 1),
        "versions": versions,
    }


@router.get("/dashboard")
def dashboard(user: dict = Depends(current_user)):
    """Personalized landing data: the user's projects/models/runs, recent
    activity and system health in one call."""
    with db() as conn:
        projects = conn.execute(
            "SELECT COUNT(*) c FROM projects WHERE owner_id=?", (user["id"],)).fetchone()["c"]
        models = conn.execute(
            "SELECT COUNT(*) c FROM models m JOIN projects p ON p.id=m.project_id "
            "WHERE p.owner_id=?", (user["id"],)).fetchone()["c"]
        analyzed = conn.execute(
            "SELECT COUNT(*) c FROM models m JOIN projects p ON p.id=m.project_id "
            "WHERE p.owner_id=? AND m.status='analyzed'", (user["id"],)).fetchone()["c"]
        runs = conn.execute(
            "SELECT COUNT(*) c FROM runs r JOIN models m ON m.id=r.model_id "
            "JOIN projects p ON p.id=m.project_id WHERE p.owner_id=? "
            "AND r.status='success'", (user["id"],)).fetchone()["c"]
        saved_mb = conn.execute(
            "SELECT COALESCE(SUM(json_extract(r.benchmark,'$.baseline.size_mb') - "
            "json_extract(r.benchmark,'$.optimized.size_mb')),0) s FROM runs r "
            "JOIN models m ON m.id=r.model_id JOIN projects p ON p.id=m.project_id "
            "WHERE p.owner_id=? AND r.status='success'", (user["id"],)).fetchone()["s"]
        recent_jobs = conn.execute(
            "SELECT j.id, j.type, j.status, j.progress, j.message, j.created_at "
            "FROM jobs j WHERE j.user_id=? ORDER BY j.created_at DESC LIMIT 8",
            (user["id"],)).fetchall()
        recent_models = conn.execute(
            "SELECT m.id, m.name, m.status, m.framework, m.size_bytes, m.created_at "
            "FROM models m JOIN projects p ON p.id=m.project_id WHERE p.owner_id=? "
            "ORDER BY m.created_at DESC LIMIT 5", (user["id"],)).fetchall()
    total_bytes = sum(f.stat().st_size for f in config.UPLOADS_DIR.glob("*.enc"))
    return {
        "stats": {"projects": projects, "models": models, "analyzed": analyzed,
                  "runs": runs, "saved_mb": round(saved_mb or 0, 2),
                  "storage_mb": round(total_bytes / 1e6, 1)},
        "recent_jobs": [dict(r) for r in recent_jobs],
        "recent_models": [dict(r) for r in recent_models],
        "health": health(),
    }


@router.get("/dashboard/activity")
def dashboard_activity(user: dict = Depends(current_user)):
    """30-day job activity for dashboard sparkline."""
    with db() as conn:
        rows = conn.execute(
            "SELECT date(created_at, 'unixepoch', 'localtime') AS day, "
            "COUNT(*) AS cnt FROM jobs WHERE user_id=? "
            "AND created_at > (strftime('%s','now') - 30*86400) "
            "GROUP BY day ORDER BY day", (user["id"],)).fetchall()
    return {"days": [dict(r) for r in rows]}


@router.get("/dashboard/stats")
def dashboard_top_stats(user: dict = Depends(current_user)):
    """Rich stats: model status breakdown, framework distribution, total params."""
    with db() as conn:
        status_rows = conn.execute(
            "SELECT m.status, COUNT(*) c FROM models m JOIN projects p ON p.id=m.project_id "
            "WHERE p.owner_id=? GROUP BY m.status", (user["id"],)).fetchall()
        fw_rows = conn.execute(
            "SELECT m.framework, COUNT(*) c FROM models m JOIN projects p ON p.id=m.project_id "
            "WHERE p.owner_id=? GROUP BY m.framework", (user["id"],)).fetchall()
        total_params = conn.execute(
            "SELECT COALESCE(SUM(json_extract(m.analysis,'$.total_params')),0) tp "
            "FROM models m JOIN projects p ON p.id=m.project_id "
            "WHERE p.owner_id=? AND m.status='analyzed'", (user["id"],)).fetchone()["tp"]
        total_saved = conn.execute(
            "SELECT COALESCE(SUM(json_extract(r.benchmark,'$.size_saved_pct')),0) ts "
            "FROM runs r JOIN models m ON m.id=r.model_id JOIN projects p ON p.id=m.project_id "
            "WHERE p.owner_id=? AND r.status='success'", (user["id"],)).fetchone()["ts"]
    return {
        "status_breakdown": {r["status"]: r["c"] for r in status_rows},
        "frameworks": {r["framework"]: r["c"] for r in fw_rows},
        "total_params": total_params or 0,
        "avg_saved_pct": round(total_saved / max(1, len(status_rows)), 1),
    }


@router.get("/admin/overview")
def overview(admin: dict = Depends(require_admin)):
    with db() as conn:
        users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        projects = conn.execute("SELECT COUNT(*) c FROM projects").fetchone()["c"]
        models = conn.execute("SELECT COUNT(*) c FROM models").fetchone()["c"]
        runs = conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"]
        jobs = conn.execute(
            "SELECT status, COUNT(*) c FROM jobs GROUP BY status").fetchall()
        recent_jobs = conn.execute(
            "SELECT j.id, j.type, j.status, j.progress, j.message, j.created_at, u.email "
            "FROM jobs j LEFT JOIN users u ON u.id=j.user_id "
            "ORDER BY j.created_at DESC LIMIT 15").fetchall()
        audit_rows = conn.execute(
            "SELECT a.*, u.email FROM audit_log a LEFT JOIN users u ON u.id=a.user_id "
            "ORDER BY a.id DESC LIMIT 30").fetchall()
    return {
        "totals": {"users": users, "projects": projects, "models": models,
                   "runs": runs,
                   "jobs": {r["status"]: r["c"] for r in jobs}},
        "recent_jobs": [dict(r) for r in recent_jobs],
        "audit_log": [dict(r) for r in audit_rows],
        "storage": {
            "uploads_dir": str(config.UPLOADS_DIR),
            "artifacts_dir": str(config.ARTIFACTS_DIR),
            "encryption_at_rest": True,
        },
    }


@router.get("/admin/users")
def list_users(admin: dict = Depends(require_admin)):
    with db() as conn:
        rows = conn.execute(
            "SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.created_at, "
            "COUNT(p.id) AS projects FROM users u "
            "LEFT JOIN projects p ON p.owner_id = u.id "
            "GROUP BY u.id ORDER BY u.created_at").fetchall()
    return {"users": [dict(r) for r in rows]}


@router.patch("/admin/users/{user_id}")
def update_user(user_id: str, body: dict, admin: dict = Depends(require_admin)):
    action = body.get("action")
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, "User not found")
        if row["id"] == admin["id"] and action in ("disable", "demote"):
            raise HTTPException(400, "You cannot disable/demote your own admin account")
        if action == "disable":
            conn.execute("UPDATE users SET is_active=0 WHERE id=?", (user_id,))
        elif action == "enable":
            conn.execute("UPDATE users SET is_active=1 WHERE id=?", (user_id,))
        elif action == "promote":
            conn.execute("UPDATE users SET role='admin' WHERE id=?", (user_id,))
        elif action == "demote":
            conn.execute("UPDATE users SET role='member' WHERE id=?", (user_id,))
        else:
            raise HTTPException(422, "action must be enable|disable|promote|demote")
        from .database import audit, now
        audit(conn, admin["id"], f"user_{action}", "user", user_id, row["email"])
    return {"ok": True}


@router.get("/dashboard/insights")
def dashboard_insights(user: dict = Depends(current_user)):
    """Three computed observations worth showing off on the dashboard."""
    with db() as conn:
        heaviest = conn.execute(
            "SELECT m.id, m.name, m.size_bytes, m.status FROM models m "
            "JOIN projects p ON p.id=m.project_id WHERE p.owner_id=? "
            "ORDER BY m.size_bytes DESC LIMIT 1", (user["id"],)).fetchone()
        best = conn.execute(
            "SELECT r.id, r.plan_name, m.id AS model_id, m.name AS model_name, "
            "json_extract(r.benchmark,'$.size_saved_pct') saved, "
            "json_extract(r.benchmark,'$.optimized.size_mb') opt_mb "
            "FROM runs r JOIN models m ON m.id=r.model_id "
            "JOIN projects p ON p.id=m.project_id "
            "WHERE p.owner_id=? AND r.status='success' "
            "ORDER BY saved DESC LIMIT 1", (user["id"],)).fetchone()
        most_active = conn.execute(
            "SELECT p.id, p.name, COUNT(j.id) jobs FROM projects p "
            "LEFT JOIN models m ON m.project_id=p.id "
            "LEFT JOIN jobs j ON j.model_id=m.id "
            "WHERE p.owner_id=? GROUP BY p.id ORDER BY jobs DESC LIMIT 1",
            (user["id"],)).fetchone()
        pending = conn.execute(
            "SELECT COUNT(*) c FROM jobs j WHERE j.user_id=? "
            "AND j.status IN ('queued','running')", (user["id"],)).fetchone()["c"]
    return {
        "heaviest_model": dict(heaviest) if heaviest else None,
        "best_run": dict(best) if best else None,
        "most_active_project": dict(most_active) if most_active else None,
        "pending_jobs": pending,
    }


@router.get("/metrics")
def prometheus_metrics():
    """NFR-13: text exposition format, scrape-ready."""
    with db() as conn:
        users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        models = conn.execute("SELECT COUNT(*) c FROM models").fetchone()["c"]
        runs = conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"]
        jobs = conn.execute(
            "SELECT status, COUNT(*) c FROM jobs GROUP BY status").fetchall()
        uptime = time.time() - _STARTED
    lines = [
        "# HELP modelsmith_uptime_seconds Process uptime in seconds",
        "# TYPE modelsmith_uptime_seconds gauge",
        f"modelsmith_uptime_seconds {uptime:.1f}",
        "# HELP modelsmith_users_total Total registered users",
        "# TYPE modelsmith_users_total gauge",
        f"modelsmith_users_total {users}",
        "# HELP modelsmith_models_total Total models",
        "# TYPE modelsmith_models_total gauge",
        f"modelsmith_models_total {models}",
        "# HELP modelsmith_runs_total Total optimization runs",
        "# TYPE modelsmith_runs_total gauge",
        f"modelsmith_runs_total {runs}",
    ]
    for r in jobs:
        lines.append(f'modelsmith_jobs{{status="{r["status"]}"}} {r["c"]}')
    return Response(content="\n".join(lines) + "\n", media_type="text/plain")


@router.get("/config")
def public_config():
    """Safe, unauthenticated capability info for clients and the playground."""
    return {
        "max_upload_mb": config.MAX_UPLOAD_MB,
        "benchmark_runs": config.BENCHMARK_RUNS,
        "token_ttl_hours": round(config.TOKEN_TTL_SECONDS / 3600, 1),
        "job_workers": config.JOB_WORKERS,
        "version": config.APP_VERSION,
        "rate_limits": {"general_per_min": 300, "auth_failed_per_min": 20},
    }


@router.get("/admin/jobs")
def all_jobs(admin: dict = Depends(require_admin)):
    with db() as conn:
        rows = conn.execute(
            "SELECT j.*, u.email FROM jobs j LEFT JOIN users u ON u.id=j.user_id "
            "ORDER BY j.created_at DESC LIMIT 50").fetchall()
    return {"jobs": [dict(r) | {"result": uj(r["result"])} for r in rows]}


@router.post("/admin/broadcast")
def broadcast(body: dict, admin: dict = Depends(require_admin)):
    """Send a notification to every active user. Use sparingly."""
    from .database import new_id
    title = str(body.get("title", "")).strip()[:80]
    message = str(body.get("message", "")).strip()[:280]
    if not title or not message:
        raise HTTPException(422, "title and message are both required")
    with db() as conn:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM users WHERE is_active=1").fetchall()]
        for uid in ids:
            conn.execute(
                "INSERT INTO notifications (id, user_id, kind, title, body, is_read, created_at) "
                "VALUES (?,?,?,?,?,0,?)",
                (new_id("n"), uid, "info", title, message, time.time()))
        audit(conn, admin["id"], "broadcast", "system", None,
              f"to {len(ids)} users: {title}")
    return {"ok": True, "delivered": len(ids)}


@router.get("/admin/users/{user_id}/detail")
def user_detail(user_id: str, admin: dict = Depends(require_admin)):
    """One user's whole footprint: projects, models, runs."""
    with db() as conn:
        u = conn.execute("SELECT id, email, full_name, role, is_active, created_at "
                         "FROM users WHERE id=?", (user_id,)).fetchone()
        if not u:
            raise HTTPException(404, "User not found")
        projects = conn.execute(
            "SELECT id, name, created_at, archived FROM projects "
            "WHERE owner_id=? ORDER BY updated_at DESC", (user_id,)).fetchall()
        projs = []
        for p in projects:
            models = conn.execute(
                "SELECT id, name, status, size_bytes FROM models WHERE project_id=?",
                (p["id"],)).fetchall()
            runs = conn.execute(
                "SELECT COUNT(*) c FROM runs r JOIN models m ON m.id=r.model_id "
                "WHERE m.project_id=?", (p["id"],)).fetchone()["c"]
            projs.append(dict(p) | {"models": [dict(m) for m in models], "runs": runs})
        jobs = conn.execute(
            "SELECT COUNT(*) c FROM jobs WHERE user_id=?", (user_id,)).fetchone()["c"]
        audit(conn, admin["id"], "admin_view", "user", user_id, u["email"])
    return {"user": dict(u), "projects": projs, "total_jobs": jobs}


@router.get("/admin/backup")
def backup_database(admin: dict = Depends(require_admin)):
    """Consistent SQLite snapshot via VACUUM INTO (NFR-03 disaster recovery)."""
    import tempfile
    from fastapi.responses import FileResponse
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    os.unlink(path)
    with db() as conn:
        conn.execute("VACUUM INTO ?", (path,))
    with db() as conn:
        from .database import audit as _audit
        _audit(conn, admin["id"], "backup", "system", None, "database snapshot")
    return FileResponse(
        path, media_type="application/octet-stream",
        filename="modelsmith_backup.db",
        headers={"Content-Disposition": 'attachment; filename="modelsmith_backup.db"'})


@router.get("/admin/stats/storage")
def storage_stats(admin: dict = Depends(require_admin)):
    """Where the bytes live: encrypted uploads, artifacts, database."""
    uploads = list(config.UPLOADS_DIR.glob("*.enc"))
    artifacts = list(config.ARTIFACTS_DIR.glob("*/*.enc"))
    up_bytes = sum(f.stat().st_size for f in uploads)
    art_bytes = sum(f.stat().st_size for f in artifacts)
    db_bytes = config.DB_PATH.stat().st_size if config.DB_PATH.exists() else 0
    total = up_bytes + art_bytes + db_bytes
    return {
        "uploads": {"files": len(uploads), "bytes": up_bytes},
        "artifacts": {"files": len(artifacts), "bytes": art_bytes},
        "database_bytes": db_bytes,
        "total_bytes": total,
        "encrypted_share_pct": round(100 * (up_bytes + art_bytes) / total, 1) if total else 0,
    }


@router.get("/admin/audit/export")
def audit_export(admin: dict = Depends(require_admin)):
    """Full audit trail as CSV (NFR-08: tamper-evident history, portable)."""
    import csv
    import io
    with db() as conn:
        rows = conn.execute(
            "SELECT a.id, a.action, a.entity, a.entity_id, u.email, a.detail, "
            "a.created_at FROM audit_log a LEFT JOIN users u ON u.id=a.user_id "
            "ORDER BY a.id").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "action", "entity", "entity_id", "user", "detail",
                "created_at_unix"])
    for r in rows:
        w.writerow([r["id"], r["action"], r["entity"], r["entity_id"],
                    r["email"] or "", r["detail"] or "", r["created_at"]])
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="modelsmith_audit_log.csv"'},
    )
