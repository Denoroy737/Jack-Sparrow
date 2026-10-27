"""Job pipeline for Phase 3: download -> transcribe -> save.

The pipeline takes its audio fetcher and transcriber as arguments, so tests can
replace the network and model parts. Status changes go to the store; the user
sees progress through `notify`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.analysis import AnalysisError, Analyzer
from app.context import META_FILE, load_context
from app.media import MediaError
from app.schemas import Report
from app.store import Job, now_iso, record_stage, set_notion_page, set_status
from app.transcribe import TranscribeError, Transcriber, Transcript

log = logging.getLogger("jack_sparrow.pipeline")

Notify = Callable[[str], Awaitable[None]]


class AudioFetcher(Protocol):
    def __call__(self, url: str, workdir: Path) -> Path: ...


@dataclass(frozen=True)
class Outcome:
    status: str
    transcript_dir: Path | None
    has_speech: bool
    error: str | None


async def process_job(
    job: Job,
    *,
    db_path: Path,
    jobs_dir: Path,
    media_dir: Path,
    fetch_audio: AudioFetcher,
    transcriber: Transcriber,
    notify: Notify,
    analyze: Analyzer | None = None,
    send_post: Callable[[Job, str], Awaitable[None]] | None = None,
    publish: Callable[[str, Report, str], tuple[str, str | None]] | None = None,
) -> Outcome:
    """Run one job from 'downloading' to 'transcribed' (or 'failed')."""
    workdir = media_dir / job.id

    await notify("Downloading audio...")
    started, t0 = now_iso(), time.monotonic()
    try:
        wav = await asyncio.to_thread(fetch_audio, job.source_url, workdir)
    except MediaError as exc:
        return await _fail(db_path, job, exc.stage, exc.user_message, exc.detail, notify)
    record_stage(db_path, job.id, "download", True, f"{time.monotonic() - t0:.1f}s", started)

    set_status(db_path, job.id, "transcribing")
    await notify("Transcribing...")
    started, t0 = now_iso(), time.monotonic()
    try:
        transcript: Transcript = await asyncio.to_thread(transcriber.transcribe, wav)
    except TranscribeError as exc:
        return await _fail(db_path, job, "transcribe", exc.user_message, exc.detail, notify)
    record_stage(db_path, job.id, "transcribe", True, f"{time.monotonic() - t0:.1f}s", started)

    out_dir = jobs_dir / job.id
    _save_transcript(out_dir, job.id, transcript)

    # Keep the public metadata (caption, creator), then remove the media (R13).
    if (workdir / META_FILE).exists():
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(workdir / META_FILE, out_dir / META_FILE)
    shutil.rmtree(workdir, ignore_errors=True)
    set_status(db_path, job.id, "transcribed")

    if not transcript.has_speech:
        await notify("No speech detected in this reel. Nothing to report from the audio.")
        log.info("job %s transcribed (no speech)", job.id)
        return Outcome("transcribed", out_dir, False, None)

    if analyze is None:
        await notify(
            f"Transcript ready ({transcript.word_count} words). "
            "Analysis is not configured (no Groq key)."
        )
        return Outcome("transcribed", out_dir, True, None)

    set_status(db_path, job.id, "analyzing")
    await notify("Analyzing the content...")
    started, t0 = now_iso(), time.monotonic()
    try:
        context = load_context(out_dir)
        report = await asyncio.to_thread(analyze, transcript, job.source_url, context)
    except AnalysisError as exc:
        return await _fail(db_path, job, "analyze", exc.user_message, str(exc), notify)
    record_stage(db_path, job.id, "analyze", True, f"{time.monotonic() - t0:.1f}s", started)
    (out_dir / "report.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    if report.post:
        (out_dir / "post.txt").write_text(report.post + "\n", encoding="utf-8")
        if send_post is not None:
            try:
                await send_post(job, report.post)
            except Exception as exc:  # noqa: BLE001 - the report is saved even if sending fails
                log.warning("post delivery failed: %s", type(exc).__name__)
    if publish is not None:
        set_status(db_path, job.id, "writing")
        started, t0 = now_iso(), time.monotonic()
        try:
            page_id, page_url = await asyncio.to_thread(publish, job.id, report, transcript.text)
        except Exception as exc:  # noqa: BLE001 - Notion errors are reported, never printed in full
            detail = type(exc).__name__
            return await _fail(db_path, job, "notion", "Could not save to Notion.", detail, notify)
        record_stage(db_path, job.id, "notion", True, f"{time.monotonic() - t0:.1f}s", started)
        set_notion_page(db_path, job.id, page_id)
        set_status(db_path, job.id, "done")
        link_note = f" Link: {page_url}" if page_url else ""
        await notify(f"Saved to Notion: {report.title}.{link_note}")
        log.info("job %s saved to Notion", job.id)
        return Outcome("done", out_dir, True, None)

    set_status(db_path, job.id, "analyzed")
    partial_note = " Some steps were incomplete." if report.partial else ""
    await notify(
        f"Report analyzed: {report.title} (category: {report.category}).{partial_note} "
        "Saving to Notion is not built yet."
    )
    log.info("job %s analyzed (partial=%s)", job.id, report.partial)
    return Outcome("analyzed", out_dir, True, None)


async def _fail(
    db_path: Path,
    job: Job,
    stage: str,
    user_message: str,
    detail: str,
    notify: Notify,
) -> Outcome:
    set_status(db_path, job.id, "failed", failed_stage=stage, error=user_message)
    record_stage(db_path, job.id, stage, False, detail[:200], now_iso())
    log.info("job %s failed at %s (%s)", job.id, stage, detail[:80])
    await notify(f"Could not finish at {stage}: {user_message} Send the link again to retry.")
    return Outcome("failed", None, False, user_message)


def _save_transcript(out_dir: Path, job_id: str, transcript: Transcript) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "job_id": job_id,
        "engine": transcript.engine,
        "language": transcript.language,
        "has_speech": transcript.has_speech,
        "text": transcript.text,
        "segments": [
            {"start": s.start, "end": s.end, "text": s.text, "no_speech_prob": s.no_speech_prob}
            for s in transcript.segments
        ],
    }
    (out_dir / "transcript.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "transcript.txt").write_text(transcript.text + "\n", encoding="utf-8")
