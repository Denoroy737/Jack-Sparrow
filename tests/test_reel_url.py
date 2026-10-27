import pytest

from app.reel_url import parse_reel_url


@pytest.mark.parametrize(
    "text, key, kind",
    [
        ("https://www.instagram.com/reel/C8xYz12AbC/", "C8xYz12AbC", "post"),
        ("https://instagram.com/reels/C8xYz12AbC/?igsh=abc", "C8xYz12AbC", "post"),
        ("http://m.instagram.com/p/Abc_-123/", "Abc_-123", "post"),
        ("https://www.instagram.com/tv/XYZ987/", "XYZ987", "post"),
        ("see this https://www.instagram.com/reel/AAA111/ great tips", "AAA111", "post"),
        ("https://www.instagram.com/share/BAAtoken123/", "BAAtoken123", "share"),
        ("https://www.instagram.com/share/reel/BAAtoken123/", "BAAtoken123", "share"),
    ],
)
def test_supported_links(text: str, key: str, kind: str) -> None:
    ref = parse_reel_url(text)
    assert ref is not None
    assert ref.key == key
    assert ref.kind == kind


def test_dedupe_key_is_stable_across_query_strings() -> None:
    a = parse_reel_url("https://www.instagram.com/reel/SAME123/?igsh=one")
    b = parse_reel_url("https://instagram.com/reel/SAME123/")
    assert a is not None and b is not None
    assert a.dedupe_key == b.dedupe_key == "ig:SAME123"


def test_share_and_post_keys_do_not_collide() -> None:
    share = parse_reel_url("https://www.instagram.com/share/X1/")
    assert share is not None
    assert share.dedupe_key == "ig-share:X1"


def test_canonical_url_for_post() -> None:
    ref = parse_reel_url("https://instagram.com/p/ABC/?utm=x")
    assert ref is not None
    assert ref.canonical_url == "https://www.instagram.com/reel/ABC/"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "hello there",
        "https://www.youtube.com/shorts/abc123",
        "https://www.tiktok.com/@user/video/123",
        "https://www.instagram.com/someuser/",
    ],
)
def test_unsupported_text_returns_none(text: str) -> None:
    assert parse_reel_url(text) is None
