"""In-process lease-based job queue backed by SQLite.

Retryable work only (search, fetch, import, match). Campaign controllers may
orchestrate progress but must never enqueue email submission. Non-retryable
send intents live in studio.mailer_studio.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from typing import Any, Callable

from studio.db import connect

JobHandler = Callable[[dict[str, Any], Callable[[int], None]], Any]

_HANDLERS: dict[str, JobHandler] = {}
_WORKER_STARTED = False
_LOCK = threading.Lock()
LEASE_MS = 30_000


def register_handler(kind: str, handler: JobHandler) -> None:
    _HANDLERS[kind] = handler


def enqueue(conn, kind: str, payload: dict | None = None) -> int:
    """Enqueue a job. If one is already running for this kind, return that id."""
    running = conn.execute(
        "SELECT id FROM job WHERE kind = ? AND status = 'running' LIMIT 1",
        (kind,),
    ).fetchone()
    if running:
        return int(running["id"])
    queued = conn.execute(
        "SELECT id FROM job WHERE kind = ? AND status = 'queued' LIMIT 1",
        (kind,),
    ).fetchone()
    if queued:
        return int(queued["id"])
    cur = conn.execute(
        """
        INSERT INTO job(kind, status, progress, payload, run_at)
        VALUES (?, 'queued', 0, ?, ?)
        """,
        (kind, json.dumps(payload or {}), time.time()),
    )
    return int(cur.lastrowid)


def get_job(conn, job_id: int):
    return conn.execute("SELECT * FROM job WHERE id = ?", (job_id,)).fetchone()


def cancel_job(conn, job_id: int) -> None:
    conn.execute(
        """
        UPDATE job SET status = 'cancelled', finished_at = datetime('now')
        WHERE id = ? AND status IN ('queued', 'running')
        """,
        (job_id,),
    )


def _claim(conn) -> dict | None:
    token = secrets.token_hex(8)
    now = time.time()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            """
            SELECT id FROM job
            WHERE status IN ('queued', 'running')
              AND run_at <= ?
              AND attempts < max_attempts
            ORDER BY id
            LIMIT 1
            """,
            (now,),
        ).fetchone()
        if not row:
            conn.execute("COMMIT")
            return None
        # Reclaim only if lease expired for running, or claim queued
        claimed = conn.execute(
            """
            UPDATE job
            SET status = 'running',
                attempts = attempts + 1,
                lease_owner = ?,
                run_at = ?,
                started_at = COALESCE(started_at, datetime('now'))
            WHERE id = ?
              AND (
                status = 'queued'
                OR (status = 'running' AND run_at <= ?)
              )
            """,
            (token, now + LEASE_MS / 1000.0, row["id"], now),
        )
        if claimed.rowcount == 0:
            conn.execute("COMMIT")
            return None
        job = conn.execute("SELECT * FROM job WHERE id = ?", (row["id"],)).fetchone()
        conn.execute("COMMIT")
        return dict(job) if job else None
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _finish(conn, job_id: int, token: str, ok: bool, error: str | None = None) -> None:
    status = "done" if ok else "failed"
    conn.execute(
        """
        UPDATE job
        SET status = ?, error = ?, finished_at = datetime('now'),
            progress = CASE WHEN ? THEN 100 ELSE progress END,
            lease_owner = NULL
        WHERE id = ? AND lease_owner = ?
        """,
        (status, error, 1 if ok else 0, job_id, token),
    )


def _set_progress(conn, job_id: int, token: str, progress: int) -> None:
    conn.execute(
        """
        UPDATE job SET progress = ?, run_at = ?
        WHERE id = ? AND lease_owner = ?
        """,
        (max(0, min(100, progress)), time.time() + LEASE_MS / 1000.0, job_id, token),
    )


def worker_loop(db_file: str, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        conn = connect(__import__("pathlib").Path(db_file))
        try:
            job = _claim(conn)
            if not job:
                stop_event.wait(0.2)
                continue
            if job["status"] == "cancelled":
                continue
            kind = job["kind"]
            token = job["lease_owner"]
            payload = json.loads(job["payload"] or "{}")
            handler = _HANDLERS.get(kind)
            if handler is None:
                _finish(conn, job["id"], token, False, f"No handler for {kind}")
                continue
            try:

                def progress(p: int, _id=job["id"], _tok=token) -> None:
                    c = connect(__import__("pathlib").Path(db_file))
                    try:
                        _set_progress(c, _id, _tok, p)
                    finally:
                        c.close()

                handler(payload, progress)
                # refresh connection in case handler used its own
                conn.close()
                conn = connect(__import__("pathlib").Path(db_file))
                row = get_job(conn, job["id"])
                if row and row["status"] == "cancelled":
                    continue
                _finish(conn, job["id"], token, True)
            except Exception as exc:  # noqa: BLE001
                conn = connect(__import__("pathlib").Path(db_file))
                _finish(conn, job["id"], token, False, str(exc))
        finally:
            conn.close()


def ensure_worker(db_file: str) -> None:
    global _WORKER_STARTED
    with _LOCK:
        if _WORKER_STARTED:
            return
        stop = threading.Event()
        thread = threading.Thread(
            target=worker_loop, args=(db_file, stop), daemon=True, name="studio-jobs"
        )
        thread.start()
        _WORKER_STARTED = True


def start_worker(db_file: str | None = None) -> None:
    from studio.paths import db_path

    ensure_worker(str(db_file or db_path()))
