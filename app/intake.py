"""Intake logic (Phase 2): owner gating, link checks, duplicates, job creation.

This module has no Telegram imports, so it can be tested directly. The bot
layer (app/bot.py) only moves messages in and out.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.reel_url import parse_reel_url
from app.store import (
    DuplicateJobError,
    Job,
    create_job,
    get_job_by_dedupe_key,
    set_status,
)

log = logging.getLogger("jack_sparrow.intake")

HELP_TEXT = (
    "Send me an Instagram reel link and I will turn it into a structured report.\n\n"
    "Supported links: instagram.com/reel/..., instagram.com/p/..., and share links.\n"
    "I process one reel at a time. Each reel is saved only once."
)

QUEUED_TEXT = "Queued. Reel saved for processing."
NOT_A_REEL_TEXT = (
    "That does not look like an Instagram reel link. Send a link like "
    "https://www.instagram.com/reel/... to start."
)
ALREADY_DONE_TEXT = "This reel was already processed. Your report is ready."
IN_PROGRESS_TEXT = "This reel is already being processed (status: {status})."
RETRY_TEXT = "The last attempt failed at {stage}: {error}. Trying again now."


@dataclass(frozen=True)
class IntakeResult:
    reply: str
    job_id: str | None
    is_new: bool  # True when a new job was queued by this message


class Intake:
    def __init__(self, db_path: Path, owner_id: int) -> None:
        self.db_path = db_path
        self.owner_id = owner_id

    def handle(self, user_id: int, chat_id: int, text: str) -> IntakeResult | None:
        """Handle one incoming message. Returns None when the sender is not the owner.

        Non-owner messages get no reply and create no job (task 2.2).
        """
        if user_id != self.owner_id:
            log.debug("ignored message from non-owner")
            return None

        stripped = (text or "").strip()
        if stripped in ("", "/start", "/help") or stripped.startswith("/"):
            return IntakeResult(reply=HELP_TEXT, job_id=None, is_new=False)

        ref = parse_reel_url(stripped)
        if ref is None:
            return IntakeResult(reply=NOT_A_REEL_TEXT, job_id=None, is_new=False)

        existing = get_job_by_dedupe_key(self.db_path, ref.dedupe_key)
        if existing is not None:
            return self._existing_reply(existing)

        try:
            job = create_job(self.db_path, ref.canonical_url, ref.dedupe_key, chat_id)
        except DuplicateJobError:
            # Another message created it between the check and the insert.
            existing = get_job_by_dedupe_key(self.db_path, ref.dedupe_key)
            assert existing is not None
            return self._existing_reply(existing)

        log.info("queued job %s (%s)", job.id, ref.kind)
        return IntakeResult(reply=QUEUED_TEXT, job_id=job.id, is_new=True)

    def _existing_reply(self, job: Job) -> IntakeResult:
        if job.status == "done":
            return IntakeResult(reply=ALREADY_DONE_TEXT, job_id=job.id, is_new=False)
        if job.status == "failed":
            # Sending the link again is the documented retry path (Design.md section 7).
            set_status(self.db_path, job.id, "queued")
            log.info("retrying failed job %s", job.id)
            reply = RETRY_TEXT.format(
                stage=job.failed_stage or "an unknown stage",
                error=job.error or "no details",
            )
            return IntakeResult(reply=reply, job_id=job.id, is_new=True)
        return IntakeResult(
            reply=IN_PROGRESS_TEXT.format(status=job.status),
            job_id=job.id,
            is_new=False,
        )
