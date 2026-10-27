import asyncio
import json
from pathlib import Path

from app.analysis import analyze
from app.pipeline import process_job
from app.schemas import SocialPost
from app.social_post import render_post, validate_post, write_post
from app.store import claim_next_queued, create_job, get_job, init_db
from app.transcribe import Transcript

APPROVED = SocialPost(
    hook="You can find any limit in 6 tries, not 35 days.",
    body="Test the middle of the range. If the answer is past it, keep the upper half. "
         "A 40-minute range takes at most 6 tries.",
    closing="Save this for your next problem 👇",
)


class CannedLLM:
    def __init__(self, responses):
        self._r = responses

    def complete_json(self, system, user):
        for key, value in self._r.items():
            if key in system.lower():
                return value
        raise AssertionError("unexpected agent")


def test_render_matches_approved_layout() -> None:
    text = render_post(APPROVED)
    assert text.split("\n\n") == [APPROVED.hook, APPROVED.body, APPROVED.closing]


def test_no_links_hashtags_or_category_in_post() -> None:
    assert validate_post(render_post(APPROVED)) == []
    assert validate_post("Read more at https://example.com") != []
    assert validate_post("Great tip #coding") != []
    assert validate_post("Full report in Notion") != []


def test_write_post_returns_none_when_post_breaks_rules() -> None:
    bad = {"hook": "See https://x.example for more", "body": "Some useful body text here.",
           "closing": "Save it"}
    llm = CannedLLM({"post": json.dumps(bad)})
    assert write_post(llm, "t", "s", "transcript") is None


def test_write_post_happy_path() -> None:
    llm = CannedLLM({"post": APPROVED.model_dump_json()})
    text = write_post(llm, "t", "s", "transcript")
    assert text is not None and text.startswith(APPROVED.hook)


def test_analysis_includes_post_and_stays_link_free() -> None:
    from app.schemas import Extraction

    extraction = {
        "title": "Binary search explained", "tldr": "Halving the range finds the limit fast.",
        "key_points": ["Test the middle"], "steps": [], "tools": [],
        "links": ["https://example.com"], "claims": [], "paper_dependency": False,
        "paper_query": None, "open_questions": [], "creator": "@someone",
    }
    llm = CannedLLM({
        "extractor": json.dumps(extraction),
        "classifier": json.dumps({"category": "coding", "tags": [], "confidence": "high"}),
        "chart": json.dumps({"chart": None}),
        "post": APPROVED.model_dump_json(),
    })
    t = Transcript("some speech about binary search and 40 minutes", "en", (), "fake")
    report = analyze(t, llm=llm, source_url="https://u", paper_search=None, search=None)
    assert report.post is not None
    assert "https://" not in report.post and "@someone" not in report.post
    assert Extraction  # schema imported and used


def test_post_is_sent_and_saved(tmp_path: Path) -> None:
    db = tmp_path / "jobs.db"
    init_db(db)
    create_job(db, "https://www.instagram.com/reel/P/", "ig:P", chat_id=7)
    job = claim_next_queued(db)
    sent = []

    async def notify(text):
        pass

    async def send_post(j, text):
        sent.append(text)

    def fetch(url, workdir):
        workdir.mkdir(parents=True, exist_ok=True)
        wav = workdir / "a.wav"
        wav.write_bytes(b"RIFF")
        return wav

    class T:
        def transcribe(self, path):
            return Transcript("speech here", "en", (), "f")

    def analyze_fn(t, url, ctx=None):
        from app.schemas import Report
        return Report(title="A", category="tools", tags=[], source_url=url, creator=None,
                      tldr="Long enough summary text.", key_points=["x"], steps=[], tools=[],
                      links=[], claims=[], papers=[], chart=None, open_questions=[],
                      confidence="medium", post=render_post(APPROVED))

    asyncio.run(process_job(job, db_path=db, jobs_dir=tmp_path / "jobs", media_dir=tmp_path / "m",
                            fetch_audio=fetch, transcriber=T(), notify=notify,
                            analyze=analyze_fn, send_post=send_post))
    assert sent == [render_post(APPROVED)]
    assert (tmp_path / "jobs" / job.id / "post.txt").exists()
    assert get_job(db, job.id).status == "analyzed"
