"""Web search for the Verifier (Phase 4), using Exa (free tier).

Endpoint and auth per Exa's quickstart: POST https://api.exa.ai/search with the
x-api-key header. Uses only the standard library, so no new dependency.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Protocol

EXA_SEARCH_URL = "https://api.exa.ai/search"


class SearchError(Exception):
    pass


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    excerpt: str


class WebSearch(Protocol):
    def search(self, query: str, num_results: int = 3) -> list[SearchHit]: ...


class ExaSearch:
    def __init__(self, api_key: str, timeout: float = 20.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def search(self, query: str, num_results: int = 3) -> list[SearchHit]:
        body = json.dumps({
            "query": query[:300],
            "numResults": max(1, min(num_results, 10)),
            "contents": {"highlights": True},
        }).encode("utf-8")
        req = urllib.request.Request(
            EXA_SEARCH_URL,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "x-api-key": self._api_key},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - never echo the key or the response
            raise SearchError(type(exc).__name__) from exc
        return parse_exa_results(payload)


def parse_exa_results(payload: dict) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for item in payload.get("results", []) or []:
        url = str(item.get("url") or "")
        if not url.startswith(("http://", "https://")):
            continue
        highlights = item.get("highlights") or []
        if highlights:
            excerpt = " ".join(str(h) for h in highlights)
        else:
            excerpt = str(item.get("text") or "")
        hits.append(SearchHit(
            title=str(item.get("title") or url)[:200],
            url=url,
            excerpt=excerpt[:1000],
        ))
    return hits
