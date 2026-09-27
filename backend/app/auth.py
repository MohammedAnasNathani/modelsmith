import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config, security
from .database import audit, db, new_id, now

router = APIRouter(prefix="/api/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)

def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if creds is None:
        raise HTTPException(401, "Not authenticated")
    token = creds.credentials

    if token.startswith("msk_"):
        return _user_for_api_key(token)
    payload = security.decode_token(token)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    with db() as conn:
        row = conn.execute(
            "SELECT id, email, full_name, role, is_active, created_at FROM users WHERE id=?",
            (payload["sub"],),
        ).fetchone()
    if not row or not row["is_active"]:
        raise HTTPException(401, "Account disabled")
    return dict(row)

def _user_for_api_key(token: str) -> dict:
    import hashlib
    digest = hashlib.sha256(token.encode()).hexdigest()
    with db() as conn:
        row = conn.execute(
            "SELECT k.id AS key_id, k.last_used_at, u.id, u.email, u.full_name, "
            "u.role, u.is_active, u.created_at FROM api_keys k "
            "JOIN users u ON u.id=k.user_id WHERE k.token_hash=? "
            "AND k.revoked_at IS NULL",
            (digest,)).fetchone()
        if not row:
            raise HTTPException(401, "Invalid or expired token")
        if row["is_active"] is None or not row["is_active"]:
            raise HTTPException(401, "Account disabled")
        if row["last_used_at"] is None or now() - row["last_used_at"] > 60:
            conn.execute("UPDATE api_keys SET last_used_at=? WHERE id=?",
                         (now(), row["key_id"]))
    return {k: row[k] for k in ("id", "email", "full_name", "role",
                                "is_active", "created_at")}

def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Admin privileges required")
    return user

@router.post("/register")
def register(body: dict):
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    full_name = str(body.get("full_name", "")).strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(422, "Enter a valid email address")
    if len(password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters")
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise HTTPException(409, "An account with this email already exists")
        uid = new_id("u")
        conn.execute(
            "INSERT INTO users (id, email, full_name, password_hash, role, is_active, created_at)"
            " VALUES (?,?,?,?,?,1,?)",
            (uid, email, full_name or email.split("@")[0],
             security.hash_password(password), "member", now()),
        )
        audit(conn, uid, "register", "user", uid, email)
    return {"id": uid, "email": email, "message": "Account created: you can log in now"}

@router.post("/login")
def login(body: dict):
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not row or not security.verify_password(password, row["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    if not row["is_active"]:
        raise HTTPException(403, "Account is disabled")
    token = security.create_token(row["id"], row["role"])
    with db() as conn:
        audit(conn, row["id"], "login", "user", row["id"])
    return {
        "token": token,
        "user": {"id": row["id"], "email": row["email"],
                 "full_name": row["full_name"], "role": row["role"]},
    }

@router.post("/logout")
def logout(request: Request, user: dict = Depends(current_user)):
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        security.revoke_token(auth[7:])
    with db() as conn:
        audit(conn, user["id"], "logout", "user", user["id"])
    return {"message": "Logged out"}

@router.post("/password/reset-request")
def reset_request(body: dict):
    email = str(body.get("email", "")).strip().lower()
    with db() as conn:
        row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if not row:

            return {"message": "If that account exists, a reset token was issued"}
        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO password_resets (id, user_id, token_hash, expires_at, used) "
            "VALUES (?,?,?,?,0)",
            (new_id("rst"), row["id"], security.hash_token(token),
             now() + config.RESET_TOKEN_TTL_SECONDS),
        )
        audit(conn, row["id"], "password_reset_request", "user", row["id"])
    return {
        "message": "Reset token issued (valid 30 minutes)",
        "reset_token": token,
        "note": "Delivered in-response because this deployment has no email service",
    }

@router.post("/password/reset-confirm")
def reset_confirm(body: dict):
    token = str(body.get("reset_token", ""))
    password = str(body.get("password", ""))
    if len(password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters")
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM password_resets WHERE token_hash=? AND used=0",
            (security.hash_token(token),),
        ).fetchone()
        if not row or row["expires_at"] < now():
            raise HTTPException(400, "Reset token is invalid or expired")
        conn.execute(
            "UPDATE users SET password_hash=?, tokens_valid_after=? WHERE id=?",
            (security.hash_password(password), now(), row["user_id"]),
        )
        conn.execute("UPDATE password_resets SET used=1 WHERE id=?", (row["id"],))
        audit(conn, row["user_id"], "password_reset", "user", row["user_id"])
    return {"message": "Password updated: all previous sessions revoked"}

@router.get("/me")
def me(user: dict = Depends(current_user)):
    with db() as conn:
        row = conn.execute("SELECT webhook_url FROM users WHERE id=?",
                           (user["id"],)).fetchone()
    return user | {"webhook_url": (row["webhook_url"] if row else "") or ""}

@router.get("/me/session")
def my_session(request: Request, user: dict = Depends(current_user)):
    import time
    auth = request.headers.get("authorization", "")
    payload = {}
    if auth.startswith("Bearer "):
        payload = security.decode_token(auth[7:]) or {}
    exp = payload.get("exp")
    return {
        "issued_at": payload.get("iat"),
        "expires_at": exp,
        "seconds_remaining": max(0, int(exp - time.time())) if exp else None,
        "ttl_hours": round(config.TOKEN_TTL_SECONDS / 3600, 1),
    }

@router.get("/me/activity")
def my_activity(user: dict = Depends(current_user)):
    with db() as conn:
        rows = conn.execute(
            "SELECT action, entity, entity_id, detail, created_at "
            "FROM audit_log WHERE user_id=? ORDER BY id DESC LIMIT 50",
            (user["id"],),
        ).fetchall()
    return {"activity": [dict(r) for r in rows]}

@router.patch("/me")
def update_me(body: dict, user: dict = Depends(current_user)):
    full_name = str(body.get("full_name", "")).strip()
    if not full_name:
        raise HTTPException(422, "Name cannot be empty")
    if len(full_name) > 80:
        raise HTTPException(422, "Name too long (max 80 chars)")
    with db() as conn:
        conn.execute("UPDATE users SET full_name=? WHERE id=?", (full_name, user["id"]))
        audit(conn, user["id"], "profile_update", "user", user["id"], full_name)
    return {"message": "Profile updated", "full_name": full_name}

@router.post("/password/change")
def change_password(body: dict, user: dict = Depends(current_user)):
    current = str(body.get("current_password", ""))
    new = str(body.get("new_password", ""))
    if len(new) < 8:
        raise HTTPException(422, "New password must be at least 8 characters")
    with db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id=?", (user["id"],)
        ).fetchone()
        if not security.verify_password(current, row["password_hash"]):
            raise HTTPException(401, "Current password is incorrect")
        conn.execute(
            "UPDATE users SET password_hash=?, tokens_valid_after=? WHERE id=?",
            (security.hash_password(new), now(), user["id"]),
        )
        audit(conn, user["id"], "password_change", "user", user["id"])
    return {"message": "Password changed: other sessions revoked",
            "token": security.create_token(user["id"], user["role"])}

@router.get("/me/keys")
def list_keys(user: dict = Depends(current_user)):
    with db() as conn:
        rows = conn.execute(
            "SELECT id, name, prefix, created_at, last_used_at, revoked_at "
            "FROM api_keys WHERE user_id=? ORDER BY created_at DESC", (user["id"],)
        ).fetchall()
    return {"keys": [dict(r) for r in rows]}

@router.post("/me/keys")
def create_key(body: dict, user: dict = Depends(current_user)):
    import hashlib
    name = str(body.get("name", "")).strip() or "Untitled key"
    if len(name) > 60:
        raise HTTPException(422, "Key name must be 60 characters or fewer")
    with db() as conn:
        n = conn.execute("SELECT COUNT(*) FROM api_keys WHERE user_id=? "
                         "AND revoked_at IS NULL", (user["id"],)).fetchone()[0]
        if n >= 10:
            raise HTTPException(409, "Ten active keys is the limit. Revoke one first.")
        secret = "msk_" + secrets.token_hex(24)
        kid = new_id("key")
        conn.execute(
            "INSERT INTO api_keys (id, user_id, name, prefix, token_hash, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (kid, user["id"], name, secret[:12],
             hashlib.sha256(secret.encode()).hexdigest(), now()))
        audit(conn, user["id"], "api_key_create", "api_key", kid, name)
    return {"id": kid, "name": name, "prefix": secret[:12],
            "token": secret,
            "note": "Shown once. Copy it now; only its hash is stored."}

@router.delete("/me/keys/{key_id}")
def revoke_key(key_id: str, user: dict = Depends(current_user)):
    with db() as conn:
        row = conn.execute("SELECT id FROM api_keys WHERE id=? AND user_id=?",
                           (key_id, user["id"])).fetchone()
        if not row:
            raise HTTPException(404, "Key not found")
        conn.execute("UPDATE api_keys SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
                     (now(), key_id))
        audit(conn, user["id"], "api_key_revoke", "api_key", key_id)
    return {"ok": True}

@router.put("/me/webhook")
def set_webhook(body: dict, user: dict = Depends(current_user)):
    url = str(body.get("webhook_url", "")).strip()
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(422, "Webhook URL must start with http:// or https://")
    if len(url) > 300:
        raise HTTPException(422, "Webhook URL too long (max 300 chars)")
    with db() as conn:
        conn.execute("UPDATE users SET webhook_url=? WHERE id=?", (url, user["id"]))
        audit(conn, user["id"], "webhook_set", "user", user["id"], url or "(cleared)")
    return {"ok": True, "webhook_url": url}

@router.post("/me/webhook/test")
def test_webhook(user: dict = Depends(current_user)):
    import json as _json
    import urllib.request

    with db() as conn:
        row = conn.execute("SELECT webhook_url FROM users WHERE id=?",
                           (user["id"],)).fetchone()
    url = (row["webhook_url"] or "").strip() if row else ""
    if not url:
        raise HTTPException(409, "No webhook URL configured yet")
    payload = _json.dumps({
        "event": "webhook_test", "message": "ModelSmith webhook test ping",
        "sent_at": now(), "user": user["email"]}).encode()
    req = urllib.request.Request(url, data=payload, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "X-ModelSmith-Event": "webhook_test"})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            return {"ok": True, "status": resp.status,
                    "detail": f"Delivered: your endpoint answered {resp.status}"}
    except Exception as e:
        return {"ok": False, "status": None,
                "detail": f"Delivery failed: {type(e).__name__}. "
                          "Check the URL and that the endpoint is reachable."}

def fire_webhook(user_id: str, payload: dict) -> None:
    import json as _json
    import logging
    import threading
    import urllib.request

    log = logging.getLogger("modelsmith.webhook")

    def _send():
        try:
            with db() as conn:
                row = conn.execute("SELECT webhook_url FROM users WHERE id=?",
                                   (user_id,)).fetchone()
            url = (row["webhook_url"] or "").strip() if row else ""
            if not url:
                return
            body = _json.dumps(payload).encode()
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Content-Type": "application/json",
                         "X-ModelSmith-Event": payload.get("event", "run")})
            with urllib.request.urlopen(req, timeout=6) as resp:
                log.info("webhook %s -> %s", url, resp.status)
        except Exception as e:
            log.warning("webhook delivery failed: %s", e)

    threading.Thread(target=_send, name="mswebhook", daemon=True).start()

@router.post("/logout-all")
def logout_everywhere(user: dict = Depends(current_user)):
    with db() as conn:
        conn.execute("UPDATE users SET tokens_valid_after=? WHERE id=?",
                     (now(), user["id"]))
        audit(conn, user["id"], "logout_all", "user", user["id"])
    return {"message": "Every session revoked. Log in again.",
            "token": None}

@router.get("/me/export")
def export_my_data(user: dict = Depends(current_user)):
    import json as _json
    with db() as conn:
        profile = dict(conn.execute(
            "SELECT id, email, full_name, role, created_at FROM users WHERE id=?",
            (user["id"],)).fetchone())
        projects = [dict(r) for r in conn.execute(
            "SELECT * FROM projects WHERE owner_id=?", (user["id"],)).fetchall()]
        pids = [p["id"] for p in projects]
        models, runs = [], []
        for pid in pids:
            mrows = [dict(r) for r in conn.execute(
                "SELECT id, project_id, name, framework, status, size_bytes, sha256, "
                "notes, tags, created_at FROM models WHERE project_id=?", (pid,)).fetchall()]
            for m in mrows:
                m["runs"] = [dict(r) for r in conn.execute(
                    "SELECT id, plan_id, plan_name, status, benchmark, steps, "
                    "repro, execution_mode, created_at, finished_at FROM runs "
                    "WHERE model_id=?", (m["id"],)).fetchall()]
            models.extend(mrows)
        keys = [dict(r) for r in conn.execute(
            "SELECT name, prefix, created_at, last_used_at, revoked_at FROM api_keys "
            "WHERE user_id=?", (user["id"],)).fetchall()]
        activity = [dict(r) for r in conn.execute(
            "SELECT action, entity, entity_id, detail, created_at FROM audit_log "
            "WHERE user_id=? ORDER BY id DESC LIMIT 200", (user["id"],)).fetchall()]
    from .database import uj
    for m in models:
        for r in m["runs"]:
            r["benchmark"] = uj(r.get("benchmark"))
            r["steps"] = uj(r.get("steps"))
            r["repro"] = uj(r.get("repro"))
    payload = {
        "exported_at": now(), "format": "modelsmith-account-export/1",
        "profile": profile, "projects": projects, "models": models,
        "api_keys": keys, "recent_activity": activity,
    }
    from fastapi.responses import Response as _Resp
    return _Resp(
        content=_json.dumps(payload, indent=1, default=str),

        media_type="application/octet-stream",
        headers={"Content-Disposition":
                 'attachment; filename="modelsmith_account_export.json"'})
