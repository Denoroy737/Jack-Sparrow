"""SQLite job store.

Schema follows docs/Architecture.md section 6. Migrations are tracked with
PRAGMA user_version, so running init_db() repeatedly is safe (Rules R30).

Schema history:
- v1: jobs, stages (Phase 1)
- v2: jobs.status_message_id, the Telegram message to edit with status (Phase 2)
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 2

STATUSES = (
    "queued",
    "downloading",
    "transcribing",
    "transcribed",
    "analyzing",
    "analyzed",
    "writing",
    "done",
    "failed",
)


class DuplicateJobError(Exception):
    """A job with the same dedupe key already exists."""


@dataclass(frozen=True)
class Job:
    id: str
    source_url: str
    dedupe_key: str
    chat_id: int
    status: str
    failed_stage: str | None
    error: str | None
    notion_page_id: str | None
    status_message_id: int | None
    created_at: str
    updated_at: str


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _now() -> str:
    return now_iso()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path) -> None:
    """Create or upgrade the database to SCHEMA_VERSION."""
    with _connect(path) as conn:
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        if current >= SCHEMA_VERSION:
            return
        if current < 1:
            conn.executescript(
                """
                CREATE TABLE jobs (
                    id              TEXT PRIMARY KEY,
                    source_url      TEXT NOT NULL,
                    dedupe_key      TEXT NOT NULL UNIQUE,
                    chat_id         INTEGER NOT NULL,
                    status          TEXT NOT NULL,
                    failed_stage    TEXT,
                    error           TEXT,
                    notion_page_id  TEXT,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL
                );

                CREATE TABLE stages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id      TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    stage       TEXT NOT NULL,
                    attempt     INTEGER NOT NULL DEFAULT 1,
                    started_at  TEXT NOT NULL,
                    finished_at TEXT,
                    ok          INTEGER,
                    detail      TEXT
                );

                CREATE INDEX idx_stages_job ON stages(job_id);
                """
            )
        if current < 2:
            conn.execute("ALTER TABLE jobs ADD COLUMN status_message_id INTEGER")
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def create_job(path: Path, source_url: str, dedupe_key: str, chat_id: int) -> Job:
    """Insert a queued job. Raises DuplicateJobError if dedupe_key already exists."""
    job_id = str(uuid.uuid4())
    now = _now()
    try:
        with _connect(path) as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, source_url, dedupe_key, chat_id, status,
                                  created_at, updated_at)
                VALUES (?, ?, ?, ?, 'queued', ?, ?)
                """,
                (job_id, source_url, dedupe_key, chat_id, now, now),
            )
    except sqlite3.IntegrityError as exc:
        raise DuplicateJobError(dedupe_key) from exc
    job = get_job(path, job_id)
    assert job is not None
    return job


def get_job(path: Path, job_id: str) -> Job | None:
    with _connect(path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _to_job(row) if row else None


def get_job_by_dedupe_key(path: Path, dedupe_key: str) -> Job | None:
    with _connect(path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE dedupe_key = ?", (dedupe_key,)).fetchone()
    return _to_job(row) if row else None


def set_status(
    path: Path,
    job_id: str,
    status: str,
    *,
    failed_stage: str | None = None,
    error: str | None = None,
) -> None:
    """Update a job's status. `error` should be a short reason, never transcript text."""
    if status not in STATUSES:
        raise ValueError(f"Unknown status: {status}")
    with _connect(path) as conn:
        cur = conn.execute(
            """
            UPDATE jobs
               SET status = ?, failed_stage = ?, error = ?, updated_at = ?
             WHERE id = ?
            """,
            (status, failed_stage, error, _now(), job_id),
        )
        if cur.rowcount == 0:
            raise KeyError(job_id)


def set_status_message(path: Path, job_id: str, message_id: int) -> None:
    """Remember which Telegram message shows this job's status (task 2.6)."""
    with _connect(path) as conn:
        cur = conn.execute(
            "UPDATE jobs SET status_message_id = ?, updated_at = ? WHERE id = ?",
            (message_id, _now(), job_id),
        )
        if cur.rowcount == 0:
            raise KeyError(job_id)


def _to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        source_url=row["source_url"],
        dedupe_key=row["dedupe_key"],
        chat_id=row["chat_id"],
        status=row["status"],
        failed_stage=row["failed_stage"],
        error=row["error"],
        notion_page_id=row["notion_page_id"],
        status_message_id=row["status_message_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def claim_next_queued(path: Path) -> Job | None:
    """Atomically take the oldest queued job and mark it 'downloading'."""
    conn = _connect(path)
    try:
        conn.isolation_level = None  # manual transaction control
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at, rowid LIMIT 1"
        ).fetchone()
        if row is None:
            conn.execute("COMMIT")
            return None
        conn.execute(
            "UPDATE jobs SET status = 'downloading', updated_at = ? WHERE id = ?",
            (_now(), row["id"]),
        )
        conn.execute("COMMIT")
        job_id = row["id"]
    finally:
        conn.close()
    return get_job(path, job_id)


def record_stage(
    path: Path,
    job_id: str,
    stage: str,
    ok: bool,
    detail: str,
    started_at: str,
) -> None:
    """Append one row to the stages table (Architecture.md section 6)."""
    with _connect(path) as conn:
        attempt = conn.execute(
            "SELECT COUNT(*) FROM stages WHERE job_id = ? AND stage = ?", (job_id, stage)
        ).fetchone()[0] + 1
        conn.execute(
            """
            INSERT INTO stages (job_id, stage, attempt, started_at, finished_at, ok, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, stage, attempt, started_at, _now(), int(ok), detail),
        )


def set_notion_page(path: Path, job_id: str, page_id: str) -> None:
    with _connect(path) as conn:
        cur = conn.execute(
            "UPDATE jobs SET notion_page_id = ?, updated_at = ? WHERE id = ?",
            (page_id, _now(), job_id),
        )
        if cur.rowcount == 0:
            raise KeyError(job_id)
