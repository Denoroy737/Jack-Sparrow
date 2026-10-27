"""Transcribe Agent (Phase 3, tasks 3.3 and 3.4).

Primary: Groq hosted Whisper (free tier, Architecture.md section 4).
Fallback: faster-whisper running locally on CPU (MIT), so transcription works
offline and when the hosted free tier is used up.

Model names are constants here and should be confirmed against Groq's
current model list during Phase 0 (task 0.3).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger("jack_sparrow.transcribe")

GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"
LOCAL_WHISPER_MODEL = "small"
NO_SPEECH_PROB = 0.6  # segments above this are treated as non-speech


class TranscribeError(Exception):
    user_message = "Could not transcribe this reel."

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str
    no_speech_prob: float = 0.0


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str | None
    segments: tuple[Segment, ...]
    engine: str

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def has_speech(self) -> bool:
        """Task 3.6: decide whether the reel actually contains speech."""
        if not self.text.strip():
            return False
        if not self.segments:
            return True
        return any(s.text and s.no_speech_prob < NO_SPEECH_PROB for s in self.segments)


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> Transcript: ...


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a dict or an object (SDKs differ)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class GroqTranscriber:
    engine = "groq-whisper"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = GROQ_WHISPER_MODEL,
        client: Any = None,
    ) -> None:
        if client is None:
            from groq import Groq

            client = Groq(api_key=api_key, timeout=120.0, max_retries=2)
        self._client = client
        self._model = model

    def transcribe(self, audio_path: Path) -> Transcript:
        try:
            with audio_path.open("rb") as handle:
                resp = self._client.audio.transcriptions.create(
                    file=(audio_path.name, handle.read()),
                    model=self._model,
                    response_format="verbose_json",
                )
        except Exception as exc:  # noqa: BLE001 - SDK exception types vary
            raise TranscribeError(f"groq call failed: {type(exc).__name__}") from exc

        segments = tuple(
            Segment(
                start=float(_get(s, "start", 0.0) or 0.0),
                end=float(_get(s, "end", 0.0) or 0.0),
                text=str(_get(s, "text", "") or "").strip(),
                no_speech_prob=float(_get(s, "no_speech_prob", 0.0) or 0.0),
            )
            for s in (_get(resp, "segments") or [])
        )
        text = str(_get(resp, "text", "") or "").strip()
        return Transcript(
            text=text,
            language=_get(resp, "language"),
            segments=segments,
            engine=self.engine,
        )


class LocalTranscriber:
    engine = "faster-whisper"

    def __init__(self, model_size: str = LOCAL_WHISPER_MODEL, model: Any = None) -> None:
        self._model_size = model_size
        self._model = model  # loaded lazily so no model download happens until needed

    def _load(self) -> Any:
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio_path: Path) -> Transcript:
        try:
            raw_segments, info = self._load().transcribe(str(audio_path), vad_filter=True)
            segments = tuple(
                Segment(
                    start=float(s.start),
                    end=float(s.end),
                    text=s.text.strip(),
                    no_speech_prob=float(getattr(s, "no_speech_prob", 0.0) or 0.0),
                )
                for s in raw_segments
            )
        except Exception as exc:  # noqa: BLE001
            raise TranscribeError(f"local whisper failed: {type(exc).__name__}") from exc

        text = " ".join(s.text for s in segments if s.text).strip()
        return Transcript(
            text=text,
            language=getattr(info, "language", None),
            segments=segments,
            engine=self.engine,
        )


class FallbackTranscriber:
    def __init__(self, primary: Transcriber, fallback: Transcriber) -> None:
        self._primary = primary
        self._fallback = fallback

    def transcribe(self, audio_path: Path) -> Transcript:
        try:
            return self._primary.transcribe(audio_path)
        except TranscribeError as exc:
            log.warning("primary transcriber failed (%s); using local fallback", exc.detail)
            return self._fallback.transcribe(audio_path)


def build_transcriber(groq_api_key: str | None) -> Transcriber:
    """Hosted Whisper with local fallback when a Groq key exists; local only otherwise."""
    local = LocalTranscriber()
    if not groq_api_key:
        return local
    return FallbackTranscriber(GroqTranscriber(api_key=groq_api_key), local)
