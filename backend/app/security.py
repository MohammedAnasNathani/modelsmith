"""Security primitives: password hashing, JWT, and at-rest encryption.

- Passwords: PBKDF2-HMAC-SHA256 with per-user salt (stdlib only).
- Tokens:    HS256 JWT with jti + expiry, revocation via `revoked_tokens`.
- Storage:   Fernet (AES-128-CBC + HMAC) for models and artifacts at rest (NFR-06).
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid

from cryptography.fernet import Fernet

from . import config
from .database import db, now

_JWT_KEY, _FERNET_KEY = config.load_or_create_keys()
_fernet = Fernet(_FERNET_KEY)


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), config.PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${config.PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, AttributeError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------- JWT (HS256)
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_token(user_id: str, role: str) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({
        "sub": user_id, "role": role, "jti": uuid.uuid4().hex,
        "iat": int(time.time()), "exp": int(time.time()) + config.TOKEN_TTL_SECONDS,
    }).encode())
    signing_input = f"{header}.{payload}".encode()
    sig = _b64(hmac.new(_JWT_KEY, signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def decode_token(token: str) -> dict | None:
    """Return payload if signature valid, unexpired, not revoked, and issued
    after the user's token watermark (set by password reset/change)."""
    try:
        header, payload, sig = token.split(".")
        signing_input = f"{header}.{payload}".encode()
        expected = _b64(hmac.new(_JWT_KEY, signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_unb64(payload))
        if data.get("exp", 0) < time.time():
            return None
        with db() as conn:
            row = conn.execute(
                "SELECT 1 FROM revoked_tokens WHERE jti=?", (data["jti"],)
            ).fetchone()
            if row:
                return None
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
            if "tokens_valid_after" in cols:
                valid_after = conn.execute(
                    "SELECT tokens_valid_after v FROM users WHERE id=?",
                    (data.get("sub"),),
                ).fetchone()
                # iat is second-granular; tokens issued in the same second as
                # the watermark survive (unavoidable 1s window, not a bug)
                if valid_after and data.get("iat", 0) < int(valid_after["v"]):
                    return None
        return data
    except Exception:
        return None


def revoke_token(token: str) -> None:
    try:
        _, payload, _ = token.split(".")
        data = json.loads(_unb64(payload))
        with db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO revoked_tokens (jti, expires_at) VALUES (?,?)",
                (data["jti"], data.get("exp", now())),
            )
    except Exception:
        pass


# ------------------------------------------------------- encrypted storage
def encrypt_bytes(data: bytes) -> bytes:
    return _fernet.encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    return _fernet.decrypt(data)


def write_encrypted(path, data: bytes) -> int:
    path.write_bytes(encrypt_bytes(data))
    return len(data)
