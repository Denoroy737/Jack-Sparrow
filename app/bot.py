"""Telegram bot wiring with aiogram 3 (MIT). Phase 2.

Long polling only: no public URL is needed (Architecture.md section 7).
All decisions live in app/intake.py. This file moves messages in and out.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

from aiogram import Bot, Dispatcher, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from app.analysis import Analyzer
from app.intake import Intake
from app.media import default_fetch_audio
from app.schemas import Report
from app.store import Job, set_status_message
from app.transcribe import Transcriber
from app.worker import run_worker

log = logging.getLogger("jack_sparrow.bot")

router = Router(name="jack_sparrow")


@router.message()
async def on_message(message: Message, intake: Intake, db_path: Path) -> None:
    user_id = message.from_user.id if message.from_user else 0
    result = intake.handle(user_id, message.chat.id, message.text or "")
    if result is None:
        return  # non-owner: silent

    sent = await message.answer(result.reply)
    if result.job_id and result.is_new:
        set_status_message(db_path, result.job_id, sent.message_id)


async def update_status_message(bot: Bot, chat_id: int, message_id: int, text: str) -> None:
    """Edit the status message in place (task 2.6). Used by later phases.

    Telegram rejects an edit with identical text; that case is ignored.
    """
    try:
        await bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            log.warning("status edit failed: %s", type(exc).__name__)


def build_dispatcher(intake: Intake) -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    dp["intake"] = intake
    dp["db_path"] = intake.db_path
    return dp


async def run_polling(
    token: str,
    intake: Intake,
    *,
    data_dir: Path,
    transcriber: Transcriber,
    analyze: Analyzer | None = None,
    publish: Callable[[str, Report, str], tuple[str, str | None]] | None = None,
) -> None:
    bot = Bot(token=token)
    dp = build_dispatcher(intake)

    async def notify_status(job: Job, text: str) -> None:
        if job.status_message_id is None:
            return
        await update_status_message(bot, job.chat_id, job.status_message_id, text)

    async def send_post(job: Job, text: str) -> None:
        await bot.send_message(chat_id=job.chat_id, text=text)

    worker = asyncio.create_task(
        run_worker(
            db_path=intake.db_path,
            jobs_dir=data_dir / "jobs",
            media_dir=data_dir / "media",
            fetch_audio=default_fetch_audio,
            transcriber=transcriber,
            notify_status=notify_status,
            analyze=analyze,
            send_post=send_post,
            publish=publish,
        )
    )
    log.info("bot starting (long polling)")
    try:
        await dp.start_polling(bot)
    finally:
        worker.cancel()
