"""Paper Finder (Phase 4, task 4.5). Uses the free arXiv API (no key needed).

Runs only when the extractor sets paper_dependency = true (PRD FR-12).
"""

from __future__ import annotations

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from app.schemas import PaperRef

ARXIV_API = "https://export.arxiv.org/api/query"
_ATOM = "{http://www.w3.org/2005/Atom}"
MAX_RESULTS = 3


class PaperSearchError(Exception):
    pass


def search_arxiv(query: str, timeout: float = 15.0) -> list[PaperRef]:
    """Return up to MAX_RESULTS papers matching `query`. Raises PaperSearchError on failure."""
    query = query.strip()[:200]
    if not query:
        return []
    params = urllib.parse.urlencode({"search_query": f"all:{query}", "max_results": MAX_RESULTS})
    try:
        with urllib.request.urlopen(f"{ARXIV_API}?{params}", timeout=timeout) as resp:  # noqa: S310
            body = resp.read()
    except Exception as exc:  # noqa: BLE001
        raise PaperSearchError(type(exc).__name__) from exc
    return parse_arxiv_atom(body)


def parse_arxiv_atom(body: bytes) -> list[PaperRef]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise PaperSearchError("bad xml") from exc
    papers: list[PaperRef] = []
    for entry in root.findall(f"{_ATOM}entry"):
        title = " ".join((entry.findtext(f"{_ATOM}title") or "").split())
        url = (entry.findtext(f"{_ATOM}id") or "").strip()
        authors = [
            (a.findtext(f"{_ATOM}name") or "").strip()
            for a in entry.findall(f"{_ATOM}author")
        ]
        if title and url.startswith("http"):
            papers.append(PaperRef(title=title, url=url, authors=[a for a in authors if a][:4]))
    return papers[:MAX_RESULTS]
