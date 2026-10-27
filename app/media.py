"""Media Agent (Phase 3, tasks 3.1 and 3.2).

Downloads only the audio of a reel with yt-dlp, then converts it to a mono
16 kHz WAV with ffmpeg. No video is kept (PRD FR-5). Error messages shown to
the user are chosen here; raw yt-dlp text is never sent to Telegram.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import yt_dlp

log = logging.getLogger("jack_sparrow.media")

_MESSAGES = (
    (("private", "login", "log in", "sign in", "authenticate"),
     "This reel is private or needs a login. I can only process public reels."),
    (("rate limit", "too many requests", "429"),
     "Instagram is limiting requests right now. Try again in a little while."),
    (("not available", "removed", "does not exist", "no longer", "404", "unavailable"),
     "This reel is not available. It may have been deleted."),
)
DEFAULT_MESSAGE = "Could not access this reel."
NO_AUDIO_MESSAGE = "This reel has no audio I can read."


class MediaError(Exception):
    """A media step failed. `user_message` is safe to show in Telegram."""

    def __init__(self, stage: str, user_message: str, detail: str = "") -> None:
        super().__init__(f"{stage}: {detail or user_message}")
        self.stage = stage
        self.user_message = user_message
        self.detail = detail


def classify_download_error(message: str) -> str:
    """Map a yt-dlp error message to a short, user-facing reason."""
    lowered = message.lower()
    for needles, user_text in _MESSAGES:
        if any(n in lowered for n in needles):
            return user_text
    return DEFAULT_MESSAGE


def download_audio(url: str, workdir: Path) -> Path:
    """Download the best audio stream of `url` into `workdir`. Returns the file path."""
    workdir.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(workdir / "source.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
    except yt_dlp.utils.DownloadError as exc:
        raise MediaError("download", classify_download_error(str(exc)), type(exc).__name__) from exc
    except Exception as exc:  # noqa: BLE001 - yt-dlp can raise several types
        raise MediaError("download", DEFAULT_MESSAGE, type(exc).__name__) from exc

    if not path.exists():
        raise MediaError("download", DEFAULT_MESSAGE, "output file missing")
    from app.context import meta_from_info

    (workdir / "meta.json").write_text(
        json.dumps(meta_from_info(info), ensure_ascii=False), encoding="utf-8"
    )
    log.info("downloaded audio source (%s)", path.suffix)
    return path


def convert_to_wav(src: Path, dst: Path) -> Path:
    """Convert any audio/video container to mono 16 kHz WAV with ffmpeg."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-loglevel", "error",
        "-i", str(src),
        "-vn", "-ac", "1", "-ar", "16000", "-f", "wav",
        str(dst),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaError("convert", "Could not prepare the audio.", type(exc).__name__) from exc
    if result.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        raise MediaError("convert", NO_AUDIO_MESSAGE, f"ffmpeg exit {result.returncode}")
    return dst


def default_fetch_audio(url: str, workdir: Path) -> Path:
    """Download, convert to WAV, and delete the raw download. Returns the WAV path."""
    src = download_audio(url, workdir)
    wav = convert_to_wav(src, workdir / "audio.wav")
    src.unlink(missing_ok=True)
    return wav
