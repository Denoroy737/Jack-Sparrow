import asyncio
import json
from pathlib import Path

from app.analysis import AnalysisError
from app.pipeline import process_job
from app.schemas import Report
from app.store import claim_next_queued, create_job, get_job, init_db
from app.transcribe import Transcript


class Recorder:
    def __init__(self):
        self.messages: list[str] = []

    async def __call__(self, text: str) -> None:
        self.messages.append(text)


class FakeTranscriber:
    def __init__(self, text: str):
        self._t = Transcript(text, "en", (), "fake")

    def transcribe(self, path):
        return self._t


def _fetch(url: str, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    wav = workdir / "audio.wav"
    wav.write_bytes(b"RIFF")
    return wav


def _report() -> Report:
    return Report(
        title="A useful reel", category="tools", tags=["x"], source_url="https://u",
        creator=None, tldr="Short summary that is long enough.", key_points=["one"],
        steps=[], tools=[], links=[], claims=[], papers=[], chart=None,
        open_questions=[], confidence="medium",
    )


def _setup(tmp_path: Path):
    db = tmp_path / "jobs.db"
    init_db(db)
    create_job(db, "https://www.instagram.com/reel/Z/", "ig:Z", chat_id=1)
    job = claim_next_queued(db)
    return db, job, tmp_path / "jobs", tmp_path / "media"


def _run(db, job, jobs_dir, media_dir, text, analyze, notify):
    return asyncio.run(process_job(
        job, db_path=db, jobs_dir=jobs_dir, media_dir=media_dir,
        fetch_audio=_fetch, transcriber=FakeTranscriber(text), notify=notify, analyze=analyze,
    ))


def test_analysis_saves_report_and_sets_status(tmp_path: Path) -> None:
    db, job, jobs_dir, media_dir = _setup(tmp_path)
    notify = Recorder()
    seen = {}

    def analyze(transcript, url, ctx=None):
        seen["text"] = transcript.text
        return _report()

    _run(db, job, jobs_dir, media_dir, "some real speech here", analyze, notify)
    assert get_job(db, job.id).status == "analyzed"
    saved = json.loads((jobs_dir / job.id / "report.json").read_text(encoding="utf-8"))
    assert saved["title"] == "A useful reel"
    assert "Report analyzed: A useful reel" in notify.messages[-1]


def test_analysis_failure_marks_job_failed(tmp_path: Path) -> None:
    db, job, jobs_dir, media_dir = _setup(tmp_path)

    def analyze(transcript, url, ctx=None):
        raise AnalysisError("extractor: bad json")

    notify = Recorder()
    _run(db, job, jobs_dir, media_dir, "speech", analyze, notify)
    stored = get_job(db, job.id)
    assert stored.status == "failed" and stored.failed_stage == "analyze"
    assert (jobs_dir / job.id / "transcript.txt").exists()  # transcript kept


def test_no_speech_skips_analysis(tmp_path: Path) -> None:
    db, job, jobs_dir, media_dir = _setup(tmp_path)
    called = []

    def analyze(transcript, url, ctx=None):
        called.append(True)
        return _report()

    _run(db, job, jobs_dir, media_dir, "", analyze, Recorder())
    assert called == []
    assert get_job(db, job.id).status == "transcribed"


def test_no_analyzer_keeps_transcribed_status(tmp_path: Path) -> None:
    db, job, jobs_dir, media_dir = _setup(tmp_path)
    _run(db, job, jobs_dir, media_dir, "speech", None, Recorder())
    assert get_job(db, job.id).status == "transcribed"
