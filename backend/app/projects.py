"""FR-02 Project Management: create, list, view, edit, delete projects.

Project ownership scopes every downstream query (models, runs, artifacts),
which is how NFR-06/NFR-14 isolation between users is enforced.
"""
from fastapi import APIRouter, Depends, HTTPException

from . import config
from .auth import current_user
from .database import audit, db, new_id, now, uj

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_or_404(conn, project_id: str, user: dict) -> dict:
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Project not found")
    p = dict(row)
    if p["owner_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "You do not have access to this project")
    return p


def _with_counts(conn, p: dict) -> dict:
    n_models = conn.execute(
        "SELECT COUNT(*) c FROM models WHERE project_id=?", (p["id"],)
    ).fetchone()["c"]
    n_runs = conn.execute(
        "SELECT COUNT(*) c FROM runs r JOIN models m ON m.id=r.model_id "
        "WHERE m.project_id=?", (p["id"],)
    ).fetchone()["c"]
    p["model_count"] = n_models
    p["run_count"] = n_runs
    return p


@router.post("")
def create_project(body: dict, user: dict = Depends(current_user)):
    name = str(body.get("name", "")).strip()
    if not name:
        raise HTTPException(422, "Project name is required")
    if len(name) > 120:
        raise HTTPException(422, "Project name must be 120 characters or fewer")
    description = str(body.get("description", "")).strip()
    if len(description) > 500:
        raise HTTPException(422, "Description must be 500 characters or fewer")
    pid = new_id("p")
    with db() as conn:
        conn.execute(
            "INSERT INTO projects (id, owner_id, name, description, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (pid, user["id"], name, description, now(), now()),
        )
        audit(conn, user["id"], "create", "project", pid, name)
    return {"id": pid, "name": name}


@router.get("")
def list_projects(user: dict = Depends(current_user)):
    include_archived = False
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM projects WHERE owner_id=? "
            "ORDER BY archived ASC, updated_at DESC", (user["id"],)
        ).fetchall()
        projects = []
        for r in rows:
            p = _with_counts(conn, dict(r))
            if p.get("archived"):
                include_archived = True
            # status breakdown per project
            st_rows = conn.execute(
                "SELECT status, COUNT(*) c FROM models WHERE project_id=? GROUP BY status",
                (p["id"],)).fetchall()
            p["status_breakdown"] = {r2["status"]: r2["c"] for r2 in st_rows}
            # total bytes
            tb = conn.execute(
                "SELECT COALESCE(SUM(size_bytes),0) FROM models WHERE project_id=?",
                (p["id"],)).fetchone()[0]
            p["total_bytes"] = tb
            # latest activity
            latest = conn.execute(
                "SELECT MAX(updated_at) la FROM models WHERE project_id=?", (p["id"],)).fetchone()["la"]
            p["latest_activity"] = latest or p["updated_at"]
            projects.append(p)
        return {"projects": projects, "has_archived": include_archived}


@router.get("/export/{format}")
def export_projects(format: str, user: dict = Depends(current_user)):
    """Export all project/model data as JSON or CSV."""
    import csv, io, json as _json
    if format not in ("json", "csv"):
        raise HTTPException(422, "format must be json or csv")
    with db() as conn:
        rows = conn.execute(
            "SELECT p.id, p.name, p.description, p.created_at, p.updated_at, "
            "m.id AS model_id, m.name AS model_name, m.framework, m.status, "
            "m.size_bytes, m.created_at AS model_created "
            "FROM projects p LEFT JOIN models m ON m.project_id=p.id "
            "WHERE p.owner_id=? ORDER BY p.updated_at DESC, m.created_at DESC",
            (user["id"],)).fetchall()
    data = [dict(r) for r in rows]
    if format == "json":
        return {"data": data}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=data[0].keys() if data else [])
    if data:
        w.writeheader()
        w.writerows(data)
    return {"csv": buf.getvalue(), "filename": "modelsmith_export.csv"}


@router.get("/{project_id}")
def get_project(project_id: str, user: dict = Depends(current_user)):
    with db() as conn:
        p = _project_or_404(conn, project_id, user)
        models = conn.execute(
            "SELECT id, name, framework, status, size_bytes, created_at, sha256 "
            "FROM models WHERE project_id=? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
        p["models"] = [dict(m) | {"analyzed": m["status"] == "analyzed"} for m in models]
        return _with_counts(conn, p)


@router.put("/{project_id}")
def update_project(project_id: str, body: dict, user: dict = Depends(current_user)):
    with db() as conn:
        _project_or_404(conn, project_id, user)
        sets, args = ["updated_at=?"], [now()]
        if "name" in body:
            name = str(body.get("name", "")).strip()
            if not name or len(name) > 80:
                raise HTTPException(422, "Name must be 1-80 characters")
            sets.append("name=?"); args.append(name)
        if "description" in body:
            description = str(body["description"]).strip()
            if len(description) > 500:
                raise HTTPException(422, "Description must be 500 characters or fewer")
            sets.append("description=?"); args.append(description)
        if "archived" in body:
            sets.append("archived=?"); args.append(1 if body["archived"] else 0)
        args.append(project_id)
        conn.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id=?", args)
        audit(conn, user["id"], "update", "project", project_id)
    return {"ok": True}


@router.get("/{project_id}/stats")
def project_stats(project_id: str, user: dict = Depends(current_user)):
    """Per-project aggregates: bytes, params, best win, busiest model."""
    with db() as conn:
        _project_or_404(conn, project_id, user)
        agg = conn.execute(
            "SELECT COUNT(*) models, COALESCE(SUM(size_bytes),0) bytes, "
            "COALESCE(SUM(json_extract(m.analysis,'$.total_params')),0) params "
            "FROM models m WHERE m.project_id=?", (project_id,)).fetchone()
        best = conn.execute(
            "SELECT r.plan_name, json_extract(r.benchmark,'$.size_saved_pct') saved, "
            "json_extract(r.benchmark,'$.optimized.size_mb') opt_mb, m.name model "
            "FROM runs r JOIN models m ON m.id=r.model_id "
            "WHERE m.project_id=? AND r.status='success' "
            "ORDER BY saved DESC LIMIT 1", (project_id,)).fetchone()
        heaviest = conn.execute(
            "SELECT name, size_bytes FROM models WHERE project_id=? "
            "ORDER BY size_bytes DESC LIMIT 1", (project_id,)).fetchone()
    return {
        "models": agg["models"], "total_bytes": agg["bytes"],
        "total_params": agg["params"],
        "best_run": dict(best) if best else None,
        "heaviest_model": dict(heaviest) if heaviest else None,
    }


@router.post("/{project_id}/archive")
def archive_project(project_id: str, user: dict = Depends(current_user)):
    """Soft-archive: hidden from the default list, data fully intact."""
    with db() as conn:
        _project_or_404(conn, project_id, user)
        conn.execute("UPDATE projects SET archived=1, updated_at=? WHERE id=?",
                     (now(), project_id))
        audit(conn, user["id"], "archive", "project", project_id)
    return {"ok": True, "archived": True}


@router.post("/{project_id}/unarchive")
def unarchive_project(project_id: str, user: dict = Depends(current_user)):
    with db() as conn:
        _project_or_404(conn, project_id, user)
        conn.execute("UPDATE projects SET archived=0, updated_at=? WHERE id=?",
                     (now(), project_id))
        audit(conn, user["id"], "unarchive", "project", project_id)
    return {"ok": True, "archived": False}


@router.delete("/{project_id}")
def delete_project(project_id: str, user: dict = Depends(current_user)):
    """Delete a project and cascade: models, uploads, runs, artifacts, jobs."""
    import shutil
    with db() as conn:
        p = _project_or_404(conn, project_id, user)
        model_rows = conn.execute(
            "SELECT id, filename FROM models WHERE project_id=?",
            (project_id,)).fetchall()
        for m in model_rows:
            if m["filename"]:
                (config.UPLOADS_DIR / m["filename"]).unlink(missing_ok=True)
            for r in conn.execute(
                    "SELECT id FROM runs WHERE model_id=?", (m["id"],)).fetchall():
                shutil.rmtree(config.ARTIFACTS_DIR / r["id"], ignore_errors=True)
        conn.execute(
            "DELETE FROM runs WHERE model_id IN "
            "(SELECT id FROM models WHERE project_id=?)", (project_id,))
        conn.execute(
            "DELETE FROM jobs WHERE model_id IN "
            "(SELECT id FROM models WHERE project_id=?)", (project_id,))
        conn.execute("DELETE FROM models WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        audit(conn, user["id"], "delete", "project", project_id, p["name"])
    return {"ok": True}
