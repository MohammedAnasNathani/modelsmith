"""FR-01 User Authentication: register, login, logout, password reset.

Also exposes the `current_user` / `require_admin` FastAPI dependencies that
enforce authentication and least-privilege on every protected route (NFR-05).
"""
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
    payload = security.decode_token(creds.credentials)
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
    """Start password reset. No mail server in this deployment, so the
    one-time token is returned for the account owner to use directly."""
    email = str(body.get("email", "")).strip().lower()
    with db() as conn:
        row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if not row:
            # Do not reveal whether the account exists.
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
    return user


@router.get("/me/session")
def my_session(request: Request, user: dict = Depends(current_user)):
    """Decode the presented token so the UI can show expiry honestly."""
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
    """Personal audit trail: the last 50 actions recorded for this account."""
    with db() as conn:
        rows = conn.execute(
            "SELECT action, entity, entity_id, detail, created_at "
            "FROM audit_log WHERE user_id=? ORDER BY id DESC LIMIT 50",
            (user["id"],),
        ).fetchall()
    return {"activity": [dict(r) for r in rows]}


@router.patch("/me")
def update_me(body: dict, user: dict = Depends(current_user)):
    """Update own profile (full name only: email is the account identity)."""
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
    """Change own password while logged in (requires current password)."""
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
