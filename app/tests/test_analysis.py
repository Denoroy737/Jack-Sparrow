import json

import pytest
from pydantic import ValidationError

from app.analysis import AnalysisError, analyze, plan_chart
from app.categories import validate_category
from app.llm import AgentError, call_agent
from app.paper_search import PaperSearchError, parse_arxiv_atom
from app.schemas import Classification, Extraction
from app.transcribe import Transcript

DEFAULT_POST = (
    '{"hook": "A quick way to find any limit fast.", '
    '"body": "Split the range in half each time and keep the side with the answer.", '
    '"closing": "Save this for later."}'
)


class FakeLLM:
    """Returns a scripted response per agent. A response may be a list (used in order)."""

    def __init__(self, scripts: dict[str, list[str] | str]):
        self.scripts = {k: (v if isinstance(v, list) else [v]) for k, v in scripts.items()}
        self.calls: list[str] = []

    def complete_json(self, system: str, user: str) -> str:
        for name in self.scripts:
            if name in system.lower():
                self.calls.append(name)
                queue = self.scripts[name]
                return queue.pop(0) if len(queue) > 1 else queue[0]
        if "eye-catching post" in system.lower():
            return DEFAULT_POST
        raise AssertionError("no script for this agent")


EXTRACTION = {
    "title": "Build a Telegram bot in 10 minutes",
    "tldr": "A creator shows a quick way to build a bot with a library.",
    "key_points": ["Install the library", "Create a token"],
    "steps": ["pip install aiogram", "Run the script"],
    "tools": ["aiogram", "BotFather"],
    "links": ["https://example.com/docs", "not a link"],
    "claims": ["The library is free"],
    "paper_dependency": False,
    "paper_query": None,
    "open_questions": [],
    "creator": "@maker",
}
CLASSIFICATION = {"category": "coding", "tags": ["Telegram", "bot"], "confidence": "high"}
NO_CHART = {"chart": None}
TRANSCRIPT = Transcript(
    text="We spend 3 hours on setup and 30 minutes on testing in this demo.",
    language="en",
    segments=(),
    engine="fake",
)


def run(llm, **kwargs):
    return analyze(TRANSCRIPT, llm=llm, source_url="https://www.instagram.com/reel/A/",
                   paper_search=kwargs.pop("paper_search", None), **kwargs)


def test_happy_path_builds_report() -> None:
    llm = FakeLLM({"extractor": json.dumps(EXTRACTION),
                   "classifier": json.dumps(CLASSIFICATION),
                   "chart": json.dumps(NO_CHART)})
    report = run(llm)
    assert report.title == "Build a Telegram bot in 10 minutes"
    assert report.category == "coding"
    assert report.tags == ["telegram", "bot"]
    assert report.links == ["https://example.com/docs"]  # non-http removed
    assert report.confidence == "high"
    assert report.partial is False
    assert all(c.status == "unverified" for c in report.claims)
    assert any("not verified" in n for n in report.notes)


def test_extractor_failure_is_fatal() -> None:
    llm = FakeLLM({"extractor": "not json"})
    with pytest.raises(AnalysisError):
        run(llm)


def test_classifier_failure_is_partial_not_fatal() -> None:
    llm = FakeLLM({"extractor": json.dumps(EXTRACTION), "classifier": "nope",
                   "chart": json.dumps(NO_CHART)})
    report = run(llm)
    assert report.partial is True
    assert report.category == "other"
    assert report.confidence == "low"


def test_chart_with_value_not_in_transcript_is_dropped() -> None:
    chart = {"chart": {"kind": "bar", "title": "Time spent", "labels": ["setup", "testing"],
                       "values": [3, 99], "source_note": "from transcript"}}
    notes: list[str] = []
    llm = FakeLLM({"chart": json.dumps(chart)})
    assert plan_chart(TRANSCRIPT.text, llm, notes) is None
    assert any("value" in n for n in notes)


def test_chart_with_supported_numbers_is_kept() -> None:
    chart = {"chart": {"kind": "bar", "title": "Time spent", "labels": ["setup", "testing"],
                       "values": [3, 30], "source_note": "from transcript"}}
    result = plan_chart(TRANSCRIPT.text, FakeLLM({"chart": json.dumps(chart)}), [])
    assert result is not None and result.values == [3, 30]


def test_paper_found_when_dependency_flagged() -> None:
    ext = dict(EXTRACTION, paper_dependency=True, paper_query="attention is all you need")
    llm = FakeLLM({"extractor": json.dumps(ext), "classifier": json.dumps(CLASSIFICATION),
                   "chart": json.dumps(NO_CHART)})
    from app.schemas import PaperRef

    fake = lambda q: [PaperRef(title="Attention Is All You Need", url="https://arxiv.org/abs/1706.03762")]  # noqa: E731
    report = run(llm, paper_search=fake)
    assert report.papers[0].title == "Attention Is All You Need"


def test_paper_search_failure_is_partial() -> None:
    ext = dict(EXTRACTION, paper_dependency=True, paper_query="x y z")
    llm = FakeLLM({"extractor": json.dumps(ext), "classifier": json.dumps(CLASSIFICATION),
                   "chart": json.dumps(NO_CHART)})

    def broken(q):
        raise PaperSearchError("offline")

    report = run(llm, paper_search=broken)
    assert report.partial is True and report.papers == []


def test_call_agent_retries_then_succeeds() -> None:
    llm = FakeLLM({"classifier": ["bad json", json.dumps(CLASSIFICATION)]})
    result = call_agent(llm, "classifier", "x", Classification)
    assert result.category == "coding"
    assert len(llm.calls) == 2


def test_call_agent_gives_up_after_retries() -> None:
    llm = FakeLLM({"classifier": "still bad"})
    with pytest.raises(AgentError):
        call_agent(llm, "classifier", "x", Classification, retries=2)
    assert len(llm.calls) == 3


@pytest.mark.parametrize("proposed, expected", [
    ("Coding", "coding"),
    ("AI", "ai/ml"),
    ("machine learning", "ai/ml"),
    ("woodworking", "woodworking"),
    ("home lab setup", "other"),
    ("", "other"),
    ("<script>", "other"),
])
def test_category_validation(proposed: str, expected: str) -> None:
    assert validate_category(proposed) == expected


def test_extraction_schema_rejects_missing_title() -> None:
    with pytest.raises(ValidationError):
        Extraction.model_validate({"tldr": "long enough summary text here"})


ARXIV_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <title>Attention Is All
      You Need</title>
    <author><name>Ashish Vaswani</name></author>
  </entry>
  <entry>
    <id>not-a-url</id>
    <title>Dropped</title>
  </entry>
</feed>"""


def test_arxiv_parser_keeps_valid_entries() -> None:
    papers = parse_arxiv_atom(ARXIV_SAMPLE)
    assert len(papers) == 1
    assert papers[0].title == "Attention Is All You Need"
    assert papers[0].authors == ["Ashish Vaswani"]
