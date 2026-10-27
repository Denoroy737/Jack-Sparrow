"""Analysis pipeline (Phase 4): transcript -> Report.

Agents that call the LLM: Extractor (also does the cleaning step), Classifier,
Chart Planner. Other steps are rule-based to save free-tier calls:
- Verifier: no web search provider is configured yet, so claims stay "unverified".
- Paper Finder: arXiv API, only when the extractor flags a paper dependency.
- Assembler: builds the report from the agent outputs (Architecture "Editor").
- Critic: rule checks on the assembled report.

Failure rules: the Extractor is required (AnalysisError if it fails). Other
steps that fail set partial=True and the report says what is missing.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.categories import validate_category
from app.context import ReelContext
from app.llm import LLM, AgentError, call_agent
from app.paper_search import PaperSearchError, search_arxiv
from app.schemas import (
    ChartPlan,
    ChartSpec,
    Classification,
    Extraction,
    PaperRef,
    Report,
    VerifiedClaim,
)
from app.social_post import write_post
from app.transcribe import Transcript
from app.web_search import SearchError, WebSearch

log = logging.getLogger("jack_sparrow.analysis")

PaperSearch = Callable[[str], list[PaperRef]]


class AnalysisError(Exception):
    user_message = "Could not analyze this reel."


def analyze(
    transcript: Transcript,
    *,
    llm: LLM,
    source_url: str,
    paper_search: PaperSearch | None = search_arxiv,
    search: WebSearch | None = None,
    context: ReelContext | None = None,
) -> Report:
    notes: list[str] = []
    partial = False
    context = context or ReelContext()
    context_text = context.as_prompt()

    try:
        extraction = call_agent(
            llm,
            "extractor",
            (f"Public context:\n{context_text}\n\n" if context_text else "")
            + f"Transcript:\n{transcript.text}",
            Extraction,
        )
    except AgentError as exc:
        raise AnalysisError(str(exc)) from exc

    try:
        classification = call_agent(
            llm,
            "classifier",
            f"Title: {extraction.title}\nSummary: {extraction.tldr}\n"
            f"Key points: {'; '.join(extraction.key_points)}",
            Classification,
        )
        category = validate_category(classification.category)
        tags = [t.strip().lower() for t in classification.tags if t.strip()][:5]
        confidence = classification.confidence
    except AgentError:
        partial = True
        notes.append("Category could not be chosen automatically; set to other.")
        category, tags, confidence = "other", [], "low"

    claims = verify_claims(extraction.claims, notes, search=search)

    papers: list[PaperRef] = []
    if extraction.paper_dependency and extraction.paper_query and paper_search:
        try:
            papers = paper_search(extraction.paper_query)
            if not papers:
                notes.append("The reel refers to a paper, but no matching paper was found.")
        except PaperSearchError:
            partial = True
            notes.append("Paper search failed; the paper link is missing.")

    chart = plan_chart(transcript.text, llm, notes)
    if chart is False:  # chart planning failed
        partial = True
        chart = None

    post_text = write_post(llm, extraction.title, extraction.tldr, transcript.text)
    if post_text is None:
        partial = True
        notes.append("Community post could not be written.")

    report = Report(
        title=extraction.title,
        category=category,
        tags=tags,
        source_url=source_url,
        creator=extraction.creator,
        tldr=extraction.tldr,
        summary=extraction.summary or extraction.tldr,
        key_points=extraction.key_points,
        steps=extraction.steps,
        tools=extraction.tools,
        links=[u for u in extraction.links if u.startswith(("http://", "https://"))],
        claims=claims,
        papers=papers,
        chart=chart,
        open_questions=extraction.open_questions,
        confidence="low" if partial else confidence,
        partial=partial,
        notes=notes,
        post=post_text,
    )
    if search is not None:
        from app.research import run_research

        mentions = list(dict.fromkeys(extraction.tools + [extraction.title]))
        summary = f"{extraction.tldr} {' '.join(extraction.key_points)[:600]}"
        resources = run_research(llm, search, summary, mentions, notes)
        report.resources = [r.model_dump() for r in resources]
        pending = sum(1 for r in resources if r.status == "needs_review")
        if pending:
            notes.append(f"{pending} resource(s) need manual review.")
    report.notes.extend(critique(report))
    return report


MAX_CLAIMS_TO_SEARCH = 3  # free-tier quota guard
_STOPWORDS = {
    "that", "this", "with", "from", "have", "will", "they", "their", "there", "what",
    "when", "your", "about", "which", "would", "could", "should", "just", "than", "then",
}


def _words(text: str) -> set[str]:
    import re

    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3 and w not in _STOPWORDS}


def verify_claims(
    claims: list[str],
    notes: list[str],
    *,
    search: WebSearch | None = None,
) -> list[VerifiedClaim]:
    """Verifier: search each claim (up to MAX_CLAIMS_TO_SEARCH) and attach a matching source.

    A claim is 'sourced' only when a result's excerpt shares at least half of the
    claim's key words. This is a word-overlap check, not a verdict on truth.
    """
    if search is None:
        if claims:
            notes.append("Claims are not verified: no web search is configured.")
        return [VerifiedClaim(text=c) for c in claims]

    results: list[VerifiedClaim] = []
    failed = False
    for i, claim in enumerate(claims):
        if i >= MAX_CLAIMS_TO_SEARCH:
            results.append(VerifiedClaim(text=claim))
            continue
        needed = _words(claim)
        try:
            hits = search.search(claim, num_results=3)
        except SearchError:
            failed = True
            results.append(VerifiedClaim(text=claim))
            continue
        match = None
        for hit in hits:
            overlap = needed & _words(hit.title + " " + hit.excerpt)
            if len(needed) >= 2 and len(overlap) >= max(2, len(needed) // 2):
                match = hit
                break
        if match:
            results.append(VerifiedClaim(text=claim, status="sourced", source=match.url))
        else:
            results.append(VerifiedClaim(text=claim))
    if failed:
        notes.append("Some claims could not be searched; they are marked unverified.")
    if len(claims) > MAX_CLAIMS_TO_SEARCH:
        notes.append(
            f"Only the first {MAX_CLAIMS_TO_SEARCH} claims were searched (free-tier limit)."
        )
    return results


def plan_chart(transcript_text: str, llm: LLM, notes: list[str]) -> ChartSpec | None | bool:
    """Return a checked ChartSpec, None (no chart), or False (agent failed)."""
    try:
        plan = call_agent(llm, "chart", f"Transcript:\n{transcript_text}", ChartPlan)
    except AgentError:
        return False
    spec = plan.chart
    if spec is None:
        return None
    if len(spec.labels) != len(spec.values):
        notes.append("Chart skipped: labels and values do not match.")
        return None
    text = transcript_text.lower()
    if not all(label.lower() in text for label in spec.labels):
        notes.append("Chart skipped: a label is not in the transcript.")
        return None
    for value in spec.values:
        number = f"{value:g}"
        if number not in transcript_text:
            notes.append("Chart skipped: a value is not in the transcript.")
            return None
    return spec


def critique(report: Report) -> list[str]:
    """Rule-based checks. Returns notes for the report, never raises."""
    issues: list[str] = []
    if report.title.lower().startswith("untitled"):
        issues.append("Title is generic; check the report.")
    if not report.key_points and not report.steps:
        issues.append("No key points or steps were found in the speech.")
    if report.confidence != "high" and not report.notes and report.partial:
        issues.append("Some analysis steps were incomplete.")
    return issues


Analyzer = Callable[[Transcript, str, ReelContext], Report]


def build_analyzer(
    groq_api_key: str | None,
    exa_api_key: str | None = None,
    groq_model: str | None = None,
) -> Analyzer | None:
    """Return an analyzer bound to Groq (and Exa when a key is set). None when no Groq key."""
    if not groq_api_key:
        return None
    from app.llm import GROQ_CHAT_MODEL, GroqLLM
    from app.web_search import ExaSearch

    llm = GroqLLM(api_key=groq_api_key, model=groq_model or GROQ_CHAT_MODEL)
    search = ExaSearch(exa_api_key) if exa_api_key else None

    def run(transcript: Transcript, source_url: str, context: ReelContext) -> Report:
        return analyze(
            transcript, llm=llm, source_url=source_url, search=search, context=context
        )

    return run
