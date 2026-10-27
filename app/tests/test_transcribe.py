from pathlib import Path
from types import SimpleNamespace

import pytest

from app.transcribe import (
    FallbackTranscriber,
    GroqTranscriber,
    Segment,
    TranscribeError,
    Transcript,
)


def test_has_speech_false_for_empty_text() -> None:
    assert not Transcript("   ", None, (), "x").has_speech


def test_has_speech_false_when_all_segments_are_non_speech() -> None:
    segs = (Segment(0, 1, "music", no_speech_prob=0.9),)
    assert not Transcript("music", None, segs, "x").has_speech


def test_has_speech_true_when_any_segment_has_speech() -> None:
    segs = (Segment(0, 1, "noise", 0.9), Segment(1, 2, "hello there", 0.1))
    assert Transcript("noise hello there", "en", segs, "x").has_speech


def test_word_count() -> None:
    assert Transcript("one two  three", None, (), "x").word_count == 3


class FakeGroqClient:
    def __init__(self, response=None, error: Exception | None = None):
        self._response = response
        self._error = error
        self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        if self._error:
            raise self._error
        return self._response


def test_groq_parses_verbose_json_dict(tmp_path: Path) -> None:
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF")
    response = {
        "text": " hello world ",
        "language": "en",
        "segments": [{"start": 0.0, "end": 1.5, "text": " hello world ", "no_speech_prob": 0.05}],
    }
    t = GroqTranscriber(client=FakeGroqClient(response)).transcribe(audio)
    assert t.text == "hello world"
    assert t.language == "en"
    assert t.segments[0].no_speech_prob == pytest.approx(0.05)
    assert t.has_speech


def test_groq_error_becomes_transcribe_error_without_secrets(tmp_path: Path) -> None:
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF")
    client = FakeGroqClient(error=RuntimeError("bad key sk-SECRET"))
    with pytest.raises(TranscribeError) as info:
        GroqTranscriber(client=client).transcribe(audio)
    assert "RuntimeError" in info.value.detail
    assert "sk-SECRET" not in info.value.detail


class Failing:
    def transcribe(self, path):
        raise TranscribeError("primary down")


class Works:
    def __init__(self):
        self.calls = 0

    def transcribe(self, path):
        self.calls += 1
        return Transcript("local text", "en", (), "local")


def test_fallback_used_when_primary_fails(tmp_path: Path) -> None:
    fallback = Works()
    t = FallbackTranscriber(Failing(), fallback).transcribe(tmp_path / "a.wav")
    assert t.engine == "local"
    assert fallback.calls == 1


def test_primary_used_when_it_works(tmp_path: Path) -> None:
    fallback = Works()
    primary = Works()
    t = FallbackTranscriber(primary, fallback).transcribe(tmp_path / "a.wav")
    assert primary.calls == 1 and fallback.calls == 0
    assert t.text == "local text"


def test_error_raised_when_both_fail(tmp_path: Path) -> None:
    with pytest.raises(TranscribeError):
        FallbackTranscriber(Failing(), Failing()).transcribe(tmp_path / "a.wav")
