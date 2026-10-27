"""Connects the pipeline to Notion (Phase 5). Sync, so the pipeline runs it in a thread."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from app.notion_client import NotionClient
from app.notion_writer import validate_database, write_report
from app.schemas import Report

Publisher = Callable[[str, Report, str], tuple[str, str | None]]


def build_publisher(token: str, database_id: str) -> Publisher:
    client = NotionClient(token)

    def publish(job_id: str, report: Report, transcript_text: str) -> tuple[str, str | None]:
        today = datetime.now(UTC).date().isoformat()
        return write_report(client, database_id, report, job_id, today, transcript_text)

    return publish


def check_database(token: str, database_id: str) -> None:
    validate_database(NotionClient(token), database_id)
