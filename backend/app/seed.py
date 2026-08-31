"""Demo seed: two users, one project, three models (queued for analysis).

Runs at startup in a background thread so the server is immediately
available while demo models are generated and analyzed.
"""
from __future__ import annotations

import logging
import threading

from . import analysis as an
from . import config, security
from .database import audit, db, j, new_id, now
from .jobs import enqueue, notify

log = logging.getLogger("modelsmith.seed")

DEMO_ADMIN = {"email": "admin@modelsmith.io", "password": "admin12345",
              "full_name": "Platform Admin"}
DEMO_USER = {"email": "demo@modelsmith.io", "password": "demo12345",
             "full_name": "Demo Engineer"}


def seed(runner) -> None:
    def _go():
        try:
            _seed(runner)
        except Exception:                               # noqa: BLE001
            log.exception("demo seed failed")

    threading.Thread(target=_go, name="msseed", daemon=True).start()


def _seed(runner) -> None:
    with db() as conn:
        if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            return                                      # already seeded
        admin_id = new_id("u")
        conn.execute(
            "INSERT INTO users (id, email, full_name, password_hash, role, is_active, created_at)"
            " VALUES (?,?,?,?, 'admin', 1, ?)",
            (admin_id, DEMO_ADMIN["email"], DEMO_ADMIN["full_name"],
             security.hash_password(DEMO_ADMIN["password"]), now()))
        demo_id = new_id("u")
        conn.execute(
            "INSERT INTO users (id, email, full_name, password_hash, role, is_active, created_at)"
            " VALUES (?,?,?,?, 'member', 1, ?)",
            (demo_id, DEMO_USER["email"], DEMO_USER["full_name"],
             security.hash_password(DEMO_USER["password"]), now()))
        audit(conn, admin_id, "seed", "user", None, "created demo users")

    with db() as conn:
        pid = new_id("p")
        conn.execute(
            "INSERT INTO projects (id, owner_id, name, description, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (pid, demo_id, "Demo Optimization Lab",
             "Sample project seeded with three models of different shapes "
             "to explore the full ModelSmith workflow.", now(), now()))
        audit(conn, demo_id, "seed", "project", pid, "Demo Optimization Lab")

    specs = [
        ("mnist_cnn", "MNIST Digit CNN (MLP-tail)", an.MnistCnn),
        ("cifar_cnn", "CIFAR-10 CNN", an.CifarCnn),
        ("resnet18", "ResNet-18 (random init)", an._build_resnet18),
    ]
    for _, label, builder in specs:
        import torch
        import io

        model = builder()
        model.eval()
        buf = io.BytesIO()
        torch.save(model, buf)
        data = buf.getvalue()

        mid = new_id("m")
        stored = f"{mid}.pt.enc"
        config.UPLOADS_DIR.joinpath(stored).write_bytes(security.encrypt_bytes(data))
        with db() as conn:
            conn.execute(
                "INSERT INTO models (id, project_id, name, framework, filename, orig_name, "
                "size_bytes, sha256, status, uploaded_by, created_at, updated_at) "
                "VALUES (?, ?, ?, 'pytorch', ?, ?, ?, ?, 'analyzing', ?, ?, ?)",
                (mid, pid, label, stored, "demo_model.pt", len(data),
                 _sha256(data), demo_id, now(), now()))
            job_id = enqueue("analyze", mid, mid, demo_id, runner)
            notify(conn, demo_id, "info", "Demo model queued", f"'{label}' → analysis")
        log.info("seeded %s (%.1f KB, job %s)", label, len(data) / 1024, job_id)


def _sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()
