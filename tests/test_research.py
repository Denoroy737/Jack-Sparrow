import json
from pathlib import Path

from app.context import ReelContext, load_context, meta_from_info
from app.research import (
    domain_tier,
    normalize_url,
    rank_hit,
    run_research,
)
from app.web_search import SearchError, SearchHit


class Plan:
    def __init__(self, queries):
        self.payload = json.dumps({"queries": queries})

    def complete_json(self, system, user):
        return self.payload


class Search:
    def __init__(self, by_query=None, fail=False):
        self.by_query = by_query or {}
        self.fail = fail
        self.calls = []

    def search(self, query, num_results=3):
        self.calls.append(query)
        if self.fail:
            raise SearchError("offline")
        return self.by_query.get(query, [])


AIOGRAM_HIT = SearchHit(
    title="aiogram documentation",
    url="https://docs.aiogram.dev/en/latest/",
    excerpt="aiogram is a modern Telegram Bot framework.",
)
RANDOM_HIT = SearchHit(title="aiogram tips", url="https://random-blog.example/post",
                       excerpt="Some aiogram tips.")


def test_official_domain_for_entity() -> None:
    assert domain_tier("https://docs.aiogram.dev/", "aiogram") == "official"


def test_government_and_education_are_official() -> None:
    assert domain_tier("https://www.nasa.gov/x", "Something") == "official"


def test_reliable_hosts() -> None:
    assert domain_tier("https://arxiv.org/abs/1706.03762", "Transformer") == "reliable"
    assert domain_tier("https://github.com/someone/project", "project") == "reliable"


def test_unknown_domain_is_other() -> None:
    assert domain_tier("https://random-blog.example/post", "aiogram") == "other"


def test_normalize_url_removes_www_and_trailing_slash() -> None:
    assert normalize_url("https://www.Example.com/docs/") == normalize_url("https://example.com/docs")


def test_verified_official_source() -> None:
    item = rank_hit("aiogram", AIOGRAM_HIT, inferred=False)
    assert item is not None
    assert item.status == "verified" and item.tier == "official"


def test_inferred_entity_always_needs_review() -> None:
    item = rank_hit("aiogram", AIOGRAM_HIT, inferred=True)
    assert item is not None
    assert item.status == "needs_review"
    assert "inferred" in item.reason


def test_unrelated_page_needs_review() -> None:
    item = rank_hit("aiogram", SearchHit("Cooking", "https://recipes.example/", "Pasta."), False)
    assert item is not None and item.status == "needs_review"


def test_run_research_dedupes_and_ranks() -> None:
    llm = Plan([
        {"query": "aiogram Telegram bot library", "entity": "aiogram",
         "kind": "tool", "inferred": False},
        {"query": "aiogram bot tips", "entity": "aiogram tips",
         "kind": "resource", "inferred": False},
    ])
    search = Search({
        "aiogram Telegram bot library": [AIOGRAM_HIT, AIOGRAM_HIT],
        "aiogram bot tips": [AIOGRAM_HIT, RANDOM_HIT],
    })
    notes: list[str] = []
    items = run_research(llm, search, "summary", ["aiogram"], notes)
    urls = [i.url for i in items]
    assert urls.count("https://docs.aiogram.dev/en/latest/") == 1  # duplicate removed
    assert items[0].status == "verified"
    assert notes == []


def test_failed_search_is_noted_not_fatal() -> None:
    llm = Plan([{"query": "aiogram library", "entity": "aiogram",
                 "kind": "tool", "inferred": False}])
    notes: list[str] = []
    items = run_research(llm, Search(fail=True), "s", ["aiogram"], notes)
    assert items == []
    assert any("failed" in n for n in notes)


def test_empty_plan_returns_nothing() -> None:
    items = run_research(Plan([]), Search(), "s", [], [])
    assert items == []


def test_meta_keeps_only_public_fields() -> None:
    info = {"title": "T", "description": "caption", "uploader": "@u", "duration": 30,
            "upload_date": "20261028", "http_headers": {"Cookie": "secret"}, "cookies": "x"}
    meta = meta_from_info(info)
    assert set(meta) == {"title", "caption", "creator", "duration_seconds", "upload_date"}
    assert "secret" not in json.dumps(meta)


def test_load_context_missing_file_is_empty(tmp_path: Path) -> None:
    assert load_context(tmp_path) == ReelContext()


def test_load_context_reads_caption(tmp_path: Path) -> None:
    meta = {"title": "T", "caption": "Use X"}
    (tmp_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    ctx = load_context(tmp_path)
    assert ctx.caption == "Use X"
    assert "Caption:" in ctx.as_prompt()
