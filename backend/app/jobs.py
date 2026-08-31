"""NFR-01/02/03: persistent background job runner.

Jobs (analysis, optimization execution) run on a small thread pool so the API
stays responsive. State is persisted in the `jobs` table at every transition,
failed jobs are retried once, and a job only reaches `success` after its
handler completes without error: incomplete work is never marked successful.
Handlers are pure functions of (job, conn) registered in HANDLERS.
"""
from __future__ import annotations

import logging
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

from . import config
from .database import db, j, new_id, now, uj

log = logging.getLogger("modelsmith.jobs")

HANDLERS: dict[str, callable] = {}


def handler(job_type: str):
    def register(fn):
        HANDLERS[job_type] = fn
        return fn
    return register


class JobRunner:
    def __init__(self, workers: int = config.JOB_WORKERS):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="msjob")
        self._wakeup = threading.Event()
        self._stop = False
        self._dispatcher = threading.Thread(target=self._loop, name="msdispatch", daemon=True)

    # ------------------------------------------------------------------ api
    def start(self):
        self._dispatcher.start()
        # recover: jobs caught mid-flight by a restart are re-queued
        with db() as conn:
            conn.execute(
                "UPDATE jobs SET status='queued', message='re-queued after restart' "
                "WHERE status='running'")
        self._wakeup.set()
        log.info("job runner started (workers=%d)", config.JOB_WORKERS)

    def stop(self):
        self._stop = True
        self._wakeup.set()
        self._pool.shutdown(wait=False)

    def submit(self, job_id: str):
        self._wakeup.set()

    # -------------------------------------------------------------- internals
    def _loop(self):
        while not self._stop:
            self._wakeup.wait(timeout=2.0)
            self._wakeup.clear()
            if self._stop:
                return
            while True:
                with db() as conn:
                    row = conn.execute(
                        "SELECT * FROM jobs WHERE status='queued' "
                        "ORDER BY created_at LIMIT 1").fetchone()
                if not row:
                    break
                job = dict(row)
                with db() as conn:
                    conn.execute(
                        "UPDATE jobs SET status='running', started_at=?, attempts=attempts+1 "
                        "WHERE id=? AND status='queued'", (now(), job["id"]))
                    if conn.total_changes == 0:      # another worker took it
                        continue
                self._pool.submit(self._run, job["id"])

    def _run(self, job_id: str):
        with db() as conn:
            job = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
        fn = HANDLERS.get(job["type"])
        try:
            if fn is None:
                raise RuntimeError(f"no handler for job type {job['type']!r}")
            progress = lambda pct, msg: _progress(job_id, pct, msg)  # noqa: E731
            result = fn(job, progress)
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET status='success', progress=100, result=?, "
                    "finished_at=?, message='completed' WHERE id=?",
                    (j(result or {}), now(), job_id))
            log.info("job %s (%s) success", job_id, job["type"])
        except Exception as exc:                       # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            log.warning("job %s (%s) failed: %s\n%s", job_id, job["type"], err,
                        traceback.format_exc())
            with db() as conn:
                fresh = conn.execute("SELECT attempts FROM jobs WHERE id=?", (job_id,)).fetchone()
            attempts = fresh["attempts"] if fresh else job["attempts"]
            retry = attempts < config.JOB_MAX_ATTEMPTS
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET status=?, error=?, message=? WHERE id=?",
                    ("queued" if retry else "failed", err,
                     "retrying after failure" if retry else "failed permanently", job_id))
            if retry:
                self._wakeup.set()


def _progress(job_id: str, pct: int, message: str):
    with db() as conn:
        conn.execute("UPDATE jobs SET progress=?, message=? WHERE id=?",
                     (max(0, min(100, int(pct))), message, job_id))


def enqueue(job_type: str, ref_id: str, model_id: str | None, user_id: str,
            runner: JobRunner) -> str:
    job_id = new_id("job")
    with db() as conn:
        conn.execute(
            "INSERT INTO jobs (id, type, ref_id, model_id, user_id, status, progress, "
            "message, attempts, created_at) VALUES (?, ?, ?, ?, ?, 'queued', 0, 'waiting', 0, ?)",
            (job_id, job_type, ref_id, model_id, user_id, now()))
    runner.submit(job_id)
    return job_id


def notify(conn, user_id: str, kind: str, title: str, body: str = "") -> None:
    conn.execute(
        "INSERT INTO notifications (id, user_id, kind, title, body, is_read, created_at) "
        "VALUES (?,?,?,?,?,0,?)",
        (new_id("n"), user_id, kind, title, body, now()))
