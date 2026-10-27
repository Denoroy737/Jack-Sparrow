import shutil
import subprocess
from pathlib import Path

import pytest
import yt_dlp

from app import media
from app.media import MediaError, classify_download_error, convert_to_wav, download_audio

HAS_FFMPEG = shutil.which("ffmpeg") is not None


@pytest.mark.parametrize(
    "raw, expected_fragment",
    [
        ("ERROR: This is a private account. Log in to see it", "private"),
        ("HTTP Error 429: Too Many Requests", "limiting"),
        ("Video unavailable. This content isn't available", "not available"),
        ("something strange happened", "Could not access"),
    ],
)
def test_error_messages_are_user_friendly(raw: str, expected_fragment: str) -> None:
    assert expected_fragment in classify_download_error(raw)


def test_download_error_is_mapped_without_raw_text(monkeypatch, tmp_path: Path) -> None:
    class FakeYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download):
            raise yt_dlp.utils.DownloadError("Private video. Log in with cookie=SECRET123")

    monkeypatch.setattr(media.yt_dlp, "YoutubeDL", FakeYDL)
    with pytest.raises(MediaError) as info:
        download_audio("https://www.instagram.com/reel/X/", tmp_path)
    assert info.value.stage == "download"
    assert "private" in info.value.user_message
    assert "SECRET123" not in info.value.user_message


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_convert_to_wav_produces_mono_16k(tmp_path: Path) -> None:
    src = tmp_path / "tone.mp3"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-ac", "2", str(src)],
        check=True,
    )
    wav = convert_to_wav(src, tmp_path / "out.wav")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=channels,sample_rate", "-of", "csv=p=0", str(wav)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert probe == "16000,1"  # ffprobe prints sample_rate before channels


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_convert_rejects_file_without_audio(tmp_path: Path) -> None:
    bogus = tmp_path / "not_media.bin"
    bogus.write_bytes(b"this is not audio at all" * 10)
    with pytest.raises(MediaError) as info:
        convert_to_wav(bogus, tmp_path / "out.wav")
    assert info.value.user_message == media.NO_AUDIO_MESSAGE
