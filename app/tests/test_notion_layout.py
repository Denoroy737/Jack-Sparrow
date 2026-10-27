import asyncio
from pathlib import Path

from app.notion_layout import RICH_TEXT_LIMIT, build_blocks
from app.pipeline import process_job
from app.schemas import ChartSpec, PaperRef, Report, VerifiedClaim
from app.store import claim_next_queued, create_job, get_job, init_db
from app.transcribe import Transcript


def make_report(**kw) -> Report:
    base = dict(
        title="Binary search", category="coding", tags=["binary search", "algorithm"],
        source_url="https://www.instagram.com/reel/A/", creator=None,
        tldr="The speaker halves the range each day to find a limit.",
        key_points=["Test the middle", "Keep one half"], steps=[], tools=[], links=[],
        claims=[], papers=[], chart=None, open_questions=[], confidence="high",
    )
    base.update(kw)
    return Report(**base)


def headings(blocks):
    return [
        b["heading_2"]["rich_text"][0]["text"]["content"]
        for b in blocks
        if b["type"] == "heading_2"
    ]


def test_minimal_report_has_only_core_sections() -> None:
    blocks = build_blocks(make_report(), "speech text", "2026-10-28")
    assert headings(blocks) == ["Key points", "Agent notes"]
    assert blocks[-1]["type"] == "toggle"
    assert blocks[-1]["toggle"]["rich_text"][0]["text"]["content"] == "Transcript"


def test_section_order_matches_preview() -> None:
    report = make_report(
        steps=["Pick the middle"], tools=["Python"], links=["https://docs.example.org"],
        chart=ChartSpec(kind="bar", title="Days", labels=["20 minutes", "30 minutes"],
                        values=[20, 30], source_note="From the reel"),
        claims=[VerifiedClaim(text="Six tries", status="sourced", source="https://s.example")],
        papers=[PaperRef(title="A paper", url="https://arxiv.org/abs/1")],
    )
    order = headings(build_blocks(report, "x", "2026-10-28"))
    assert order == ["Key points", "Steps", "Tools and links", "Graphs", "Claims",
                     "Sources and papers", "Agent notes"]


def test_chart_is_a_table_with_the_values() -> None:
    chart = ChartSpec(kind="bar", title="Days", labels=["20 minutes", "30 minutes"],
                      values=[20, 30], source_note="From the reel")
    blocks = build_blocks(make_report(chart=chart), "x", "2026-10-28")
    table = next(b for b in blocks if b["type"] == "table")["table"]
    cells = [[c[0]["text"]["content"] for c in row["table_row"]["cells"]]
             for row in table["children"]]
    assert cells == [["Label", "Value"], ["20 minutes", "20"], ["30 minutes", "30"]]


def test_unverified_claims_are_labelled() -> None:
    report = make_report(claims=[VerifiedClaim(text="A claim")])
    blocks = build_blocks(report, "x", "2026-10-28")
    bullets = [b for b in blocks if b["type"] == "bulleted_list_item"]
    assert any("(unverified)" in b["bulleted_list_item"]["rich_text"][0]["text"]["content"]
               for b in bullets)


def test_long_transcript_is_split_under_notion_limits() -> None:
    blocks = build_blocks(make_report(), "word " * 5000, "2026-10-28")
    toggle_children = blocks[-1]["toggle"]["children"]
    assert len(toggle_children) > 1
    for child in toggle_children:
        assert len(child["paragraph"]["rich_text"][0]["text"]["content"]) <= RICH_TEXT_LIMIT


def test_pipeline_publishes_and_marks_done(tmp_path: Path) -> None:
    db = tmp_path / "jobs.db"
    init_db(db)
    create_job(db, "https://www.instagram.com/reel/N/", "ig:N", chat_id=3)
    job = claim_next_queued(db)

    async def notify(text):
        pass

    def fetch(url, workdir):
        workdir.mkdir(parents=True, exist_ok=True)
        wav = workdir / "a.wav"
        wav.write_bytes(b"RIFF")
        return wav

    class T:
        def transcribe(self, path):
            return Transcript("some speech", "en", (), "f")

    def analyze_fn(t, url):
        return make_report(source_url=url)

    published = []

    def publish(job_id, report, transcript_text):
        published.append((job_id, report.title, transcript_text))
        return "page-123", "https://notion.example/page-123"

    asyncio.run(process_job(job, db_path=db, jobs_dir=tmp_path / "jobs", media_dir=tmp_path / "m",
                            fetch_audio=fetch, transcriber=T(), notify=notify,
                            analyze=analyze_fn, publish=publish))
    stored = get_job(db, job.id)
    assert stored.status == "done"
    assert stored.notion_page_id == "page-123"
    assert published == [(job.id, "Binary search", "some speech")]


def test_notion_failure_marks_job_failed_and_keeps_report(tmp_path: Path) -> None:
    db = tmp_path / "jobs.db"
    init_db(db)
    create_job(db, "https://www.instagram.com/reel/M/", "ig:M", chat_id=3)
    job = claim_next_queued(db)

    async def notify(text):
        pass

    def fetch(url, workdir):
        workdir.mkdir(parents=True, exist_ok=True)
        wav = workdir / "a.wav"
        wav.write_bytes(b"RIFF")
        return wav

    class T:
        def transcribe(self, path):
            return Transcript("some speech", "en", (), "f")

    def publish(job_id, report, transcript_text):
        raise RuntimeError("token sk-SECRET leaked")

    asyncio.run(process_job(job, db_path=db, jobs_dir=tmp_path / "jobs", media_dir=tmp_path / "m",
                            fetch_audio=fetch, transcriber=T(), notify=notify,
                            analyze=lambda t, u: make_report(source_url=u), publish=publish))
    stored = get_job(db, job.id)
    assert stored.status == "failed" and stored.failed_stage == "notion"
    assert "sk-SECRET" not in (stored.error or "")
    assert (tmp_path / "jobs" / job.id / "report.json").exists()
