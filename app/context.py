"""Reel context: caption, creator, title, and duration from the public Instagram page.

Comments and DMs are NOT read (Rules R15). Only the public metadata that yt-dlp
returns with the download is used. Missing fields are fine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

META_FILE = "meta.json"
MAX_CAPTION_CHARS = 2000


@dataclass(frozen=True)
class ReelContext:
    title: str = ""
    caption: str = ""
    creator: str = ""
    duration_seconds: float | None = None
    upload_date: str = ""

    def as_prompt(self) -> str:
        parts = []
        if self.title:
            parts.append(f"Title: {self.title}")
        if self.creator:
            parts.append(f"Creator: {self.creator}")
        if self.upload_date:
            parts.append(f"Posted: {self.upload_date}")
        if self.caption:
            parts.append(f"Caption:\n{self.caption[:MAX_CAPTION_CHARS]}")
        return "\n".join(parts)


def meta_from_info(info: dict) -> dict:
    """Keep only the public fields we use. Never store cookies or request headers."""
    return {
        "title": str(info.get("title") or "")[:300],
        "caption": str(info.get("description") or "")[:MAX_CAPTION_CHARS],
        "creator": str(info.get("uploader") or info.get("channel") or "")[:120],
        "duration_seconds": info.get("duration"),
        "upload_date": str(info.get("upload_date") or ""),
    }


def load_context(folder: Path) -> ReelContext:
    path = folder / META_FILE
    if not path.exists():
        return ReelContext()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ReelContext()
    return ReelContext(
        title=str(data.get("title") or ""),
        caption=str(data.get("caption") or ""),
        creator=str(data.get("creator") or ""),
        duration_seconds=data.get("duration_seconds"),
        upload_date=str(data.get("upload_date") or ""),
    )
