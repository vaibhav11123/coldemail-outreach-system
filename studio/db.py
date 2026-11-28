"""SQLite schema, migrations, and connection helpers."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from studio.paths import db_path

SCHEMA_V1 = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS applicant (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    degree_level TEXT NOT NULL DEFAULT 'undergraduate',
    degree_year TEXT,
    countries TEXT,
    funding_need TEXT NOT NULL DEFAULT 'no_preference',
    dates_free TEXT,
    github_url TEXT,
    portfolio_url TEXT,
    mode TEXT NOT NULL DEFAULT 'internship',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS profile_fact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id INTEGER NOT NULL DEFAULT 1 REFERENCES applicant(id),
    kind TEXT NOT NULL,
    body TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'typed',
    confirmed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS researcher (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,
    email TEXT,
    origin TEXT NOT NULL DEFAULT 'manual',
    stale INTEGER NOT NULL DEFAULT 0,
    professor_key TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS researcher_id (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    researcher_id INTEGER NOT NULL REFERENCES researcher(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS affiliation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    researcher_id INTEGER NOT NULL REFERENCES researcher(id) ON DELETE CASCADE,
    institution TEXT NOT NULL,
    start_year TEXT,
    end_year TEXT,
    is_current INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS publication (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    researcher_id INTEGER NOT NULL REFERENCES researcher(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    year INTEGER,
    url TEXT,
    abstract TEXT
);

CREATE TABLE IF NOT EXISTS opportunity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    researcher_id INTEGER REFERENCES researcher(id) ON DELETE SET NULL,
    kind TEXT NOT NULL DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'unknown',
    funding TEXT NOT NULL DEFAULT 'unknown',
    eligibility TEXT NOT NULL DEFAULT 'unknown',
    deadline TEXT,
    apply_url TEXT,
    email_invited TEXT NOT NULL DEFAULT 'unknown',
    checked_at TEXT,
    origin TEXT NOT NULL DEFAULT 'manual',
    demo INTEGER NOT NULL DEFAULT 0,
    note TEXT
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER REFERENCES opportunity(id) ON DELETE CASCADE,
    publication_id INTEGER REFERENCES publication(id) ON DELETE CASCADE,
    quote TEXT NOT NULL,
    url TEXT,
    captured_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS identity_conflict (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    left_id INTEGER NOT NULL REFERENCES researcher(id),
    right_id INTEGER NOT NULL REFERENCES researcher(id),
    reason TEXT NOT NULL,
    resolution TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS merge_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kept_id INTEGER NOT NULL,
    removed_id INTEGER NOT NULL,
    payload TEXT NOT NULL,
    undone INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS shortlist_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunity(id) ON DELETE CASCADE,
    rank_score REAL NOT NULL DEFAULT 0,
    rank_explanation TEXT NOT NULL DEFAULT '[]',
    UNIQUE(opportunity_id)
);

CREATE TABLE IF NOT EXISTS draft (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunity(id) ON DELETE CASCADE,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    approved_hash TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS application (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunity(id) ON DELETE CASCADE,
    channel TEXT NOT NULL DEFAULT 'email',
    state TEXT NOT NULL DEFAULT 'drafted',
    notes TEXT,
    deadline TEXT,
    link TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS application_file (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES application(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    local_path TEXT,
    requested INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS send_intent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id INTEGER NOT NULL REFERENCES draft(id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    provider TEXT,
    provider_message_id TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(content_hash)
);

CREATE TABLE IF NOT EXISTS suppression (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    researcher_id INTEGER REFERENCES researcher(id),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    progress INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    payload TEXT,
    lease_owner TEXT,
    run_at REAL NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    started_at TEXT,
    finished_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS job_one_running
ON job(kind) WHERE status = 'running';

CREATE TABLE IF NOT EXISTS reminder (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER REFERENCES application(id) ON DELETE CASCADE,
    due_on TEXT NOT NULL,
    kind TEXT NOT NULL,
    dismissed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hosted_account (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS profile_slot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES hosted_account(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    applicant_mode TEXT NOT NULL DEFAULT 'internship',
    is_active INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = FULL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    # executescript auto-commits, so run DDL outside an explicit transaction.
    conn.executescript(SCHEMA_V1)
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT version FROM schema_migrations WHERE version = 1"
        ).fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_migrations(version) VALUES (1)")
            conn.execute(
                "INSERT OR IGNORE INTO applicant(id, degree_level) VALUES (1, 'undergraduate')"
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    # v2: FTS5 + embedding tables (idempotent)
    from studio.search.embeddings import ensure_embedding_table
    from studio.search.fts import ensure_fts

    ensure_fts(conn)
    ensure_embedding_table(conn)
    v2 = conn.execute(
        "SELECT version FROM schema_migrations WHERE version = 2"
    ).fetchone()
    if v2 is None:
        conn.execute("INSERT INTO schema_migrations(version) VALUES (2)")


def recover_intents_on_startup(conn: sqlite3.Connection) -> int:
    """Abandoned submitted intents become unknown_delivery. Never pending."""
    cur = conn.execute(
        """
        UPDATE send_intent
        SET state = 'unknown_delivery', updated_at = datetime('now')
        WHERE state = 'submitted'
        """
    )
    return cur.rowcount


def interrupt_running_jobs(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """
        UPDATE job
        SET status = 'interrupted', finished_at = datetime('now'), lease_owner = NULL
        WHERE status = 'running'
        """
    )
    return cur.rowcount


@contextmanager
def db_session(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        migrate(conn)
        recover_intents_on_startup(conn)
        interrupt_running_jobs(conn)
        yield conn
    finally:
        conn.close()


def backup_database(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with connect(src) as source, sqlite3.connect(str(dest)) as target:
        source.backup(target)
