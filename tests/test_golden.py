"""Golden test on a real reel transcript (binary search explainer).

The transcript has speech-recognition errors ("debat threshold", "debaard sexual").
The Extractor is expected to fix them. The offline test below uses a canned
extraction, so it checks the pipeline on this exact text. The live test (below)
runs the real Groq model and is skipped unless RUN_LIVE=1 and GROQ_API_KEY are set.
"""

import json
import os
from pathlib import Path

import pytest

from app.analysis import analyze
from app.transcribe import Transcript
from app.web_search import SearchHit, parse_exa_results

GOLDEN = Path(__file__).parent / "golden" / "binary_search_transcript.txt"


def transcript_text() -> str:
    return GOLDEN.read_text(encoding="utf-8")


def numbers_in(text: str) -> set[str]:
    import re

    return set(re.findall(r"\b\d+\b", text))


DEFAULT_POST = (
    '{"hook": "A quick way to find any limit fast.", '
    '"body": "Split the range in half each time and keep the side with the answer.", '
    '"closing": "Save this for later."}'
)


class CannedLLM:
    def __init__(self, responses: dict[str, str]):
        self._responses = responses

    def complete_json(self, system: str, user: str) -> str:
        for key, value in self._responses.items():
            if key in system.lower():
                return value
        if "eye-catching post" in system.lower():
            return DEFAULT_POST
        if "plan web research" in system.lower():
            return '{"queries": []}'
        raise AssertionError("unexpected agent")


EXPECTED_EXTRACTION = {
    "title": "Binary search explained with a late-arrival example",
    "tldr": "The speaker finds a hidden threshold by halving the search range each day, "
            "which is binary search.",
    "key_points": [
        "Test the middle of the range each time",
        "Keep the half where the answer must be",
        "Six tries are enough for a range of 40 minutes",
    ],
    "steps": [],
    "tools": [],
    "links": [],
    "claims": [
        "Binary search finds a threshold in at most 6 days for a 40 minute range",
        "The method is binary search",
    ],
    "paper_dependency": False,
    "paper_query": None,
    "open_questions": [],
    "creator": None,
}
EXPECTED_CLASSIFICATION = {"category": "coding", "tags": ["binary search", "algorithm"],
                           "confidence": "high"}
EXPECTED_CHART = {"chart": {
    "kind": "bar",
    "title": "Late arrival tests",
    "labels": ["20 minutes", "30 minutes", "25 minutes"],
    "values": [20, 30, 25],
    "source_note": "Day-by-day tests in the transcript",
}}


def test_golden_transcript_source_numbers_are_present() -> None:
    text = transcript_text()
    for needed in ("40", "20", "30", "25", "6"):
        assert needed in numbers_in(text), needed


def test_golden_pipeline_offline() -> None:
    llm = CannedLLM({
        "extractor": json.dumps(EXPECTED_EXTRACTION),
        "classifier": json.dumps(EXPECTED_CLASSIFICATION),
        "chart": json.dumps(EXPECTED_CHART),
    })
    transcript = Transcript(text=transcript_text(), language="en", segments=(), engine="golden")
    report = analyze(transcript, llm=llm, source_url="https://www.instagram.com/reel/G/",
                     paper_search=None, search=None)
    assert "binary search" in report.title.lower()
    assert report.category == "coding"
    assert report.chart is not None and report.chart.values == [20, 30, 25]
    assert report.partial is False
    assert all(c.status == "unverified" for c in report.claims)


def test_verifier_marks_sourced_claims_with_overlap() -> None:
    class StubSearch:
        def search(self, query, num_results=3):
            return [SearchHit(
                title="Binary search algorithm",
                url="https://example.org/binary-search",
                excerpt="Binary search halves the range at each step to find a target.",
            )]

    llm = CannedLLM({
        "extractor": json.dumps(EXPECTED_EXTRACTION),
        "classifier": json.dumps(EXPECTED_CLASSIFICATION),
        "chart": json.dumps({"chart": None}),
    })
    transcript = Transcript(text=transcript_text(), language="en", segments=(), engine="golden")
    report = analyze(transcript, llm=llm, source_url="https://u", paper_search=None,
                     search=StubSearch())
    sourced = [c for c in report.claims if c.status == "sourced"]
    assert sourced and sourced[0].source == "https://example.org/binary-search"


def test_verifier_leaves_unrelated_claims_unverified() -> None:
    class Unrelated:
        def search(self, query, num_results=3):
            return [SearchHit(title="Cooking pasta", url="https://example.org/pasta",
                              excerpt="Boil water and add salt.")]

    llm = CannedLLM({
        "extractor": json.dumps(EXPECTED_EXTRACTION),
        "classifier": json.dumps(EXPECTED_CLASSIFICATION),
        "chart": json.dumps({"chart": None}),
    })
    transcript = Transcript(text=transcript_text(), language="en", segments=(), engine="golden")
    report = analyze(transcript, llm=llm, source_url="https://u", paper_search=None,
                     search=Unrelated())
    assert all(c.status == "unverified" for c in report.claims)


def test_parse_exa_results_keeps_only_http_urls() -> None:
    payload = {"results": [
        {"title": "Good", "url": "https://a.example/x", "highlights": ["one", "two"]},
        {"title": "Bad", "url": "ftp://nope"},
        {"title": "Text only", "url": "https://b.example/y", "text": "body"},
    ]}
    hits = parse_exa_results(payload)
    assert [h.url for h in hits] == ["https://a.example/x", "https://b.example/y"]
    assert hits[0].excerpt == "one two"
    assert hits[1].excerpt == "body"


@pytest.mark.skipif(
    not (os.getenv("RUN_LIVE") == "1" and os.getenv("GROQ_API_KEY")),
    reason="live test: set RUN_LIVE=1 and GROQ_API_KEY",
)
def test_golden_live_groq() -> None:
    from app.llm import GroqLLM

    llm = GroqLLM(api_key=os.environ["GROQ_API_KEY"])
    transcript = Transcript(text=transcript_text(), language="en", segments=(), engine="live")
    report = analyze(transcript, llm=llm, source_url="https://u", paper_search=None, search=None)
    assert "binary" in report.title.lower()
    assert report.category in {"coding", "tricks", "tech", "tools", "ai/ml", "other"}
    assert report.key_points
