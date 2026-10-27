"""Research step: find official and reliable sources for what a reel mentions.

Flow: the LLM plans up to 4 queries -> Exa search -> rank sources by domain tier
-> verify each candidate against its entity name -> remove duplicates.
Anything not verified, or inferred, is marked needs_review for a human to check.

Comments and DMs are never read. Only public web results are used.
"""

from __future__ import annotations

import logging
import re
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field

from app.llm import LLM, AgentError, call_agent
from app.web_search import SearchError, SearchHit, WebSearch

log = logging.getLogger("jack_sparrow.research")

MAX_QUERIES = 4
RESULTS_PER_QUERY = 5
MAX_RESOURCES = 8

RELIABLE_HOSTS = {
    "arxiv.org", "github.com", "en.wikipedia.org", "wikipedia.org",
    "developer.mozilla.org", "docs.python.org", "stackoverflow.com", "pypi.org",
    "npmjs.com", "huggingface.co", "nature.com", "ieee.org", "acm.org", "doi.org",
}

Kind = Literal["tool", "product", "person", "paper", "resource", "tutorial", "idea", "other"]


class ResearchQuery(BaseModel):
    query: str = Field(min_length=3, max_length=120)
    entity: str = Field(min_length=2, max_length=80)
    kind: Kind = "other"
    inferred: bool = False


class ResearchPlan(BaseModel):
    queries: list[ResearchQuery] = Field(default_factory=list, max_length=MAX_QUERIES)


class ResourceItem(BaseModel):
    name: str
    kind: str
    url: str
    tier: Literal["official", "reliable", "other"]
    status: Literal["verified", "needs_review"]
    inferred: bool = False
    reason: str = ""


def _host(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def domain_tier(url: str, entity: str) -> Literal["official", "reliable", "other"]:
    host = _host(url)
    if not host:
        return "other"
    if host.endswith((".gov", ".edu")):
        return "official"
    label_text = re.sub(r"[^a-z0-9]", "", host)
    tokens = [t for t in re.findall(r"[a-z0-9]+", entity.lower()) if len(t) >= 4]
    if any(t in label_text for t in tokens):
        return "official"
    if host in RELIABLE_HOSTS or any(host.endswith("." + h) for h in RELIABLE_HOSTS):
        return "reliable"
    return "other"


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), _host(url), path, "", "")).lower()


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 3}


def entity_matches(entity: str, hit: SearchHit) -> bool:
    needed = _words(entity)
    if not needed:
        return False
    found = _words(hit.title + " " + hit.excerpt)
    return len(needed & found) >= max(1, (len(needed) + 1) // 2)


def rank_hit(entity: str, hit: SearchHit, inferred: bool) -> ResourceItem | None:
    tier = domain_tier(hit.url, entity)
    matches = entity_matches(entity, hit)
    verified = matches and tier in ("official", "reliable") and not inferred
    if verified:
        reason = f"{tier} source names '{entity}'"
    elif inferred:
        reason = "inferred from the reel, not named in it"
    elif not matches:
        reason = "the page does not clearly mention this name"
    else:
        reason = "not an official or reliable domain"
    return ResourceItem(
        name=entity[:80],
        kind="other",
        url=hit.url,
        tier=tier,
        status="verified" if verified else "needs_review",
        inferred=inferred,
        reason=reason,
    )


def run_research(
    llm: LLM,
    search: WebSearch,
    summary: str,
    mentions: list[str],
    notes: list[str],
) -> list[ResourceItem]:
    user = f"Summary: {summary}\nMentioned: {', '.join(mentions[:20])}"
    try:
        plan = call_agent(llm, "researcher", user, ResearchPlan)
    except AgentError:
        notes.append("Resource research could not plan searches.")
        return []

    items: list[ResourceItem] = []
    seen_urls: set[str] = set()
    seen_names: set[str] = set()
    failed = False
    for q in plan.queries[:MAX_QUERIES]:
        if q.entity.lower() in seen_names:
            continue
        try:
            hits = search.search(q.query, num_results=RESULTS_PER_QUERY)
        except SearchError:
            failed = True
            continue
        best: ResourceItem | None = None
        for hit in hits:
            key = normalize_url(hit.url)
            if key in seen_urls:
                continue
            item = rank_hit(q.entity, hit, q.inferred)
            if item is None:
                continue
            if best is None or (item.status, item.tier) > (best.status, best.tier):
                best = item
        if best is not None:
            seen_urls.add(normalize_url(best.url))
            seen_names.add(q.entity.lower())
            best.kind = q.kind
            items.append(best)
    if failed:
        notes.append("Some resource searches failed; those items are missing.")
    items.sort(key=lambda i: (i.status != "verified", i.tier != "official"))
    return items[:MAX_RESOURCES]
