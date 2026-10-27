import sqlite3
from pathlib import Path

import pytest

from app.store import (
    SCHEMA_VERSION,
    DuplicateJobError,
    create_job,
    get_job,
    get_job_by_dedupe_key,
    init_db,
    set_status,
)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    return path


def test_init_db_creates_tables_and_version(db: Path) -> None:
    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    assert {"jobs", "stages"} <= tables
    assert version == SCHEMA_VERSION


def test_init_db_is_idempotent(db: Path) -> None:
    init_db(db)
    init_db(db)  # must not raise or drop data
    create_job(db, "https://instagram.com/reel/abc/", "abc", chat_id=1)
    init_db(db)
    assert get_job_by_dedupe_key(db, "abc") is not None


def test_create_job_starts_queued(db: Path) -> None:
    job = create_job(db, "https://instagram.com/reel/abc/", "abc", chat_id=1)
    assert job.status == "queued"
    assert job.dedupe_key == "abc"
    assert job.notion_page_id is None


def test_duplicate_dedupe_key_is_rejected(db: Path) -> None:
    create_job(db, "https://instagram.com/reel/abc/", "abc", chat_id=1)
    with pytest.raises(DuplicateJobError):
        create_job(db, "https://instagram.com/reel/abc/", "abc", chat_id=1)


def test_set_status_updates_row(db: Path) -> None:
    job = create_job(db, "https://instagram.com/reel/xyz/", "xyz", chat_id=1)
    set_status(db, job.id, "failed", failed_stage="download", error="private reel")
    updated = get_job(db, job.id)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.failed_stage == "download"
    assert updated.error == "private reel"


def test_set_status_rejects_unknown_status(db: Path) -> None:
    job = create_job(db, "https://instagram.com/reel/xyz/", "xyz", chat_id=1)
    with pytest.raises(ValueError):
        set_status(db, job.id, "exploded")


def test_set_status_unknown_job_raises(db: Path) -> None:
    with pytest.raises(KeyError):
        set_status(db, "no-such-id", "done")


def test_claim_next_queued_takes_oldest_once(db: Path) -> None:
    from app.store import claim_next_queued

    a = create_job(db, "https://instagram.com/reel/A/", "a", chat_id=1)
    create_job(db, "https://instagram.com/reel/B/", "b", chat_id=1)
    first = claim_next_queued(db)
    assert first is not None and first.id == a.id
    assert first.status == "downloading"
    second = claim_next_queued(db)
    assert second is not None and second.dedupe_key == "b"
    assert claim_next_queued(db) is None


def test_record_stage_increments_attempts(db: Path) -> None:
    import sqlite3

    from app.store import now_iso, record_stage

    job = create_job(db, "https://instagram.com/reel/C/", "c", chat_id=1)
    record_stage(db, job.id, "download", False, "private", now_iso())
    record_stage(db, job.id, "download", True, "ok", now_iso())
    conn = sqlite3.connect(db)
    attempts = [r[0] for r in conn.execute(
        "SELECT attempt FROM stages WHERE job_id = ? ORDER BY id", (job.id,))]
    conn.close()
    assert attempts == [1, 2]
