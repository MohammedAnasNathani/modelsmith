"""SQLite persistence layer: schema, helpers, and audit trail.

Plain sqlite3 (WAL mode) keeps the project dependency-light while remaining
fully relational and inspectable. Every entity that NFR-08/NFR-09 require to
stay traceably linked (model -> analysis -> plan -> run -> artifacts) is
keyed explicitly in the schema.
"""
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager

from . import config

_local = threading.local()


def get_db() -> sqlite3.Connection:
    """Thread-local connection (jobs run on worker threads)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


@contextmanager
def db():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    full_name     TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'member',   -- member | admin
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS password_resets (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT UNIQUE NOT NULL,
    expires_at REAL NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti       TEXT PRIMARY KEY,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    owner_id    TEXT NOT NULL REFERENCES users(id),
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS models (
    id           TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    framework    TEXT NOT NULL,               -- pytorch | onnx
    filename     TEXT NOT NULL,               -- encrypted file in uploads dir
    orig_name    TEXT NOT NULL DEFAULT '',
    size_bytes   INTEGER NOT NULL,
    sha256       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'uploaded',  -- uploaded|analyzing|analyzed|failed
    error        TEXT,
    analysis     TEXT,                        -- JSON: layers, flops, benchmark...
    goals        TEXT,                        -- JSON: FR-06 deployment goals
    plans        TEXT,                        -- JSON: ranked plans + predictions
    uploaded_by  TEXT NOT NULL REFERENCES users(id),
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id           TEXT PRIMARY KEY,
    model_id     TEXT NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    plan_id      TEXT NOT NULL,
    plan_name    TEXT NOT NULL,
    user_id      TEXT NOT NULL REFERENCES users(id),
    status       TEXT NOT NULL DEFAULT 'queued', -- queued|running|success|failed
    steps        TEXT,                        -- JSON pipeline steps with per-step results
    benchmark    TEXT,                        -- JSON original-vs-optimized comparison
    artifacts    TEXT,                        -- JSON [{name, path, size, sha256}]
    repro        TEXT,                        -- JSON versions/hw/seeds (NFR-09)
    error        TEXT,
    created_at   REAL NOT NULL,
    finished_at  REAL
);
CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    type         TEXT NOT NULL,               -- analyze | execute
    ref_id       TEXT NOT NULL,               -- model id or run id
    model_id     TEXT,
    user_id      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued', -- queued|running|success|failed
    progress     INTEGER NOT NULL DEFAULT 0,  -- 0..100
    message      TEXT,
    attempts     INTEGER NOT NULL DEFAULT 0,
    error        TEXT,
    result       TEXT,
    created_at   REAL NOT NULL,
    started_at   REAL,
    finished_at  REAL
);
CREATE TABLE IF NOT EXISTS notifications (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL,                 -- info | success | error
    title      TEXT NOT NULL,
    body       TEXT NOT NULL DEFAULT '',
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT,
    action     TEXT NOT NULL,
    entity     TEXT NOT NULL,
    entity_id  TEXT,
    detail     TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_models_project ON models(project_id);
CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model_id);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read);
CREATE TABLE IF NOT EXISTS shares (
    id         TEXT PRIMARY KEY,
    token      TEXT UNIQUE NOT NULL,
    model_id   TEXT NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    created_by TEXT NOT NULL REFERENCES users(id),
    views      INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
"""


def init_db() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)
        # migrations for pre-existing databases
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
        if "tokens_valid_after" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN tokens_valid_after REAL NOT NULL DEFAULT 0")
        mcols = {r["name"] for r in conn.execute("PRAGMA table_info(models)")}
        if "notes" not in mcols:
            conn.execute("ALTER TABLE models ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
        if "tags" not in mcols:
            conn.execute("ALTER TABLE models ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
        pcols = {r["name"] for r in conn.execute("PRAGMA table_info(projects)")}
        if "archived" not in pcols:
            conn.execute("ALTER TABLE projects ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now() -> float:
    return time.time()


# ---- tiny helpers used everywhere ----------------------------------------
def j(obj) -> str:
    return json.dumps(obj, default=str)


def uj(text, default=None):
    if not text:
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default


def audit(conn, user_id: str | None, action: str, entity: str,
          entity_id: str | None = None, detail: str | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_log (user_id, action, entity, entity_id, detail, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (user_id, action, entity, entity_id, detail, now()),
    )
