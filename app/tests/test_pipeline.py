import asyncio
from pathlib import Path

import pytest

from app.media import MediaError
from app.pipeline import process_job
from app.store import claim_next_queued, create_job, get_job, init_db
from app.transcribe import TranscribeError, Transcript


class Recorder:
    def __init__(self):
        self.messages: list[str] = []

    async def __call__(self, text: str) -> None:
        self.messages.append(text)


class FakeTranscriber:
    def __init__(self, transcript=None, error=None):
        self._t = transcript
        self._e = error

    def transcribe(self, path):
        if self._e:
            raise self._e
        return self._t


@pytest.fixture
def setup(tmp_path: Path):
    db = tmp_path / "jobs.db"
    init_db(db)
    job = create_job(db, "https://www.instagram.com/reel/ABC/", "ig:ABC", chat_id=5)
    claimed = claim_next_queued(db)
    assert claimed is not None and claimed.id == job.id
    return db, claimed, tmp_path / "jobs", tmp_path / "media"


def _fetch_ok(url: str, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    wav = workdir / "audio.wav"
    wav.write_bytes(b"RIFF fake wav")
    return wav


def _fetch_private(url: str, workdir: Path) -> Path:
    raise MediaError("download", "This reel is private or needs a login.", "private")


def _run(setup, fetch, transcriber, notify):
    db, job, jobs_dir, media_dir = setup
    return asyncio.run(
        process_job(
            job,
            db_path=db,
            jobs_dir=jobs_dir,
            media_dir=media_dir,
            fetch_audio=fetch,
            transcriber=transcriber,
            notify=notify,
        )
    )


def test_success_saves_transcript_and_removes_media(setup) -> None:
    db, job, jobs_dir, media_dir = setup
    t = Transcript("hello from the reel", "en", (), "fake")
    notify = Recorder()
    outcome = _run(setup, _fetch_ok, FakeTranscriber(t), notify)

    assert outcome.status == "transcribed"
    assert (jobs_dir / job.id / "transcript.txt").read_text(encoding="utf-8").strip() == \
        "hello from the reel"
    assert not (media_dir / job.id).exists()  # R13
    assert get_job(db, job.id).status == "transcribed"
    assert "Transcript ready (4 words)" in notify.messages[-1]


def test_no_speech_reports_clearly(setup) -> None:
    db, job, *_ = setup
    t = Transcript("", None, (), "fake")
    notify = Recorder()
    outcome = _run(setup, _fetch_ok, FakeTranscriber(t), notify)
    assert outcome.has_speech is False
    assert "No speech detected" in notify.messages[-1]
    assert get_job(db, job.id).status == "transcribed"


def test_download_failure_marks_job_failed_with_stage(setup) -> None:
    db, job, *_ = setup
    notify = Recorder()
    outcome = _run(setup, _fetch_private, FakeTranscriber(None), notify)
    assert outcome.status == "failed"
    stored = get_job(db, job.id)
    assert stored.status == "failed"
    assert stored.failed_stage == "download"
    assert "private" in (stored.error or "")
    assert notify.messages[-1].startswith("Could not finish at download:")
    assert "Send the link again" in notify.messages[-1]


def test_transcribe_failure_marks_job_failed(setup) -> None:
    db, job, *_ = setup
    notify = Recorder()
    outcome = _run(setup, _fetch_ok, FakeTranscriber(error=TranscribeError("x")), notify)
    assert outcome.status == "failed"
    assert get_job(db, job.id).failed_stage == "transcribe"


def test_stages_are_recorded(setup) -> None:
    import sqlite3

    db, job, *_ = setup
    _run(setup, _fetch_ok, FakeTranscriber(Transcript("a b", None, (), "f")), Recorder())
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT stage, ok FROM stages WHERE job_id = ? ORDER BY id", (job.id,)
    ).fetchall()
    conn.close()
    assert rows == [("download", 1), ("transcribe", 1)]
