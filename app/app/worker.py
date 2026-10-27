"""Background worker: picks queued jobs and runs the pipeline one at a time.

Single worker on purpose: free-tier limits and a small host do not need
parallel downloads. Phase 6 adds resume-after-restart for stuck jobs.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.analysis import Analyzer
from app.pipeline import AudioFetcher, process_job
from app.schemas import Report
from app.store import Job, claim_next_queued, set_status
from app.transcribe import Transcriber

log = logging.getLogger("jack_sparrow.worker")

StatusNotifier = Callable[[Job, str], Awaitable[None]]
PostSender = Callable[[Job, str], Awaitable[None]]


async def run_worker(
    *,
    db_path: Path,
    jobs_dir: Path,
    media_dir: Path,
    fetch_audio: AudioFetcher,
    transcriber: Transcriber,
    notify_status: StatusNotifier,
    analyze: Analyzer | None = None,
    send_post: PostSender | None = None,
    publish: Callable[[str, Report, str], tuple[str, str | None]] | None = None,
    poll_seconds: float = 3.0,
) -> None:
    log.info("worker started")
    while True:
        job = await asyncio.to_thread(claim_next_queued, db_path)
        if job is None:
            await asyncio.sleep(poll_seconds)
            continue

        async def notify(text: str, _job: Job = job) -> None:
            await notify_status(_job, text)

        try:
            await process_job(
                job,
                db_path=db_path,
                jobs_dir=jobs_dir,
                media_dir=media_dir,
                fetch_audio=fetch_audio,
                transcriber=transcriber,
                notify=notify,
                analyze=analyze,
                send_post=send_post,
                publish=publish,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - keep the worker alive
            # Log the exception type only: messages may contain request details.
            log.error("job %s crashed: %s", job.id, type(exc).__name__)
            set_status(
                db_path, job.id, "failed", failed_stage="internal", error="Unexpected error."
            )
            await notify("Could not finish: unexpected error. Send the link again to retry.")
