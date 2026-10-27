from pathlib import Path

import pytest

from app.intake import (
    ALREADY_DONE_TEXT,
    HELP_TEXT,
    NOT_A_REEL_TEXT,
    QUEUED_TEXT,
    Intake,
)
from app.store import get_job_by_dedupe_key, init_db, set_status

OWNER = 1001
REEL = "https://www.instagram.com/reel/ABC123/"


@pytest.fixture
def intake(tmp_path: Path) -> Intake:
    db = tmp_path / "jobs.db"
    init_db(db)
    return Intake(db_path=db, owner_id=OWNER)


def test_non_owner_gets_no_reply_and_no_job(intake: Intake) -> None:
    assert intake.handle(user_id=999, chat_id=5, text=REEL) is None
    assert get_job_by_dedupe_key(intake.db_path, "ig:ABC123") is None


def test_owner_reel_link_queues_job(intake: Intake) -> None:
    result = intake.handle(OWNER, 5, REEL)
    assert result is not None
    assert result.reply == QUEUED_TEXT
    assert result.is_new is True
    assert result.job_id is not None
    job = get_job_by_dedupe_key(intake.db_path, "ig:ABC123")
    assert job is not None
    assert job.status == "queued"
    assert job.chat_id == 5
    assert job.source_url == "https://www.instagram.com/reel/ABC123/"


def test_same_reel_twice_does_not_duplicate(intake: Intake) -> None:
    first = intake.handle(OWNER, 5, REEL)
    second = intake.handle(OWNER, 5, "https://instagram.com/reel/ABC123/?igsh=x")
    assert first is not None and second is not None
    assert second.is_new is False
    assert second.job_id == first.job_id


def test_done_reel_reports_already_processed(intake: Intake) -> None:
    first = intake.handle(OWNER, 5, REEL)
    assert first is not None and first.job_id is not None
    set_status(intake.db_path, first.job_id, "done")
    again = intake.handle(OWNER, 5, REEL)
    assert again is not None
    assert again.reply == ALREADY_DONE_TEXT
    assert again.is_new is False


def test_in_progress_reel_shows_status(intake: Intake) -> None:
    first = intake.handle(OWNER, 5, REEL)
    assert first is not None and first.job_id is not None
    set_status(intake.db_path, first.job_id, "transcribing")
    again = intake.handle(OWNER, 5, REEL)
    assert again is not None
    assert "transcribing" in again.reply
    assert again.is_new is False


def test_failed_reel_is_requeued_on_resend(intake: Intake) -> None:
    first = intake.handle(OWNER, 5, REEL)
    assert first is not None and first.job_id is not None
    set_status(intake.db_path, first.job_id, "failed", failed_stage="download", error="private")
    retry = intake.handle(OWNER, 5, REEL)
    assert retry is not None
    assert retry.is_new is True
    assert retry.job_id == first.job_id
    assert "download" in retry.reply
    job = get_job_by_dedupe_key(intake.db_path, "ig:ABC123")
    assert job is not None and job.status == "queued"


def test_text_without_reel_gets_guidance(intake: Intake) -> None:
    result = intake.handle(OWNER, 5, "hello")
    assert result is not None
    assert result.reply == NOT_A_REEL_TEXT
    assert result.job_id is None


@pytest.mark.parametrize("text", ["/start", "/help", "/unknown", ""])
def test_commands_and_empty_show_help(intake: Intake, text: str) -> None:
    result = intake.handle(OWNER, 5, text)
    assert result is not None
    assert result.reply == HELP_TEXT
    assert result.job_id is None
