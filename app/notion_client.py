"""Minimal Notion REST client (Phase 5), standard library only.

Notion API version is pinned in NOTION_VERSION. Confirm it during Phase 0 task 0.5.
Errors never include the token or response bodies.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionError(Exception):
    pass


class NotionClient:
    def __init__(self, token: str, timeout: float = 30.0) -> None:
        self._token = token
        self._timeout = timeout

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            NOTION_API + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            endpoint = path.split("?")[0]
            raise NotionError(f"Notion returned HTTP {exc.code} for {method} {endpoint}") from None
        except Exception as exc:  # noqa: BLE001
            raise NotionError(type(exc).__name__) from None

    def retrieve_database(self, database_id: str) -> dict[str, Any]:
        return self.request("GET", f"/databases/{database_id}")

    def query_database(self, database_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", f"/databases/{database_id}/query", body)

    def create_page(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/pages", body)

    def update_page(self, page_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PATCH", f"/pages/{page_id}", body)

    def append_blocks(self, block_id: str, children: list[dict[str, Any]]) -> dict[str, Any]:
        return self.request("PATCH", f"/blocks/{block_id}/children", {"children": children})
