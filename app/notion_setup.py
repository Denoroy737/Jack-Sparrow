"""Creates the Notion reports database automatically (Phase 5, task 5.1 revised 2026-10-28).

Notion only creates a database under a page that the integration can access. If
NOTION_PARENT_PAGE_ID is not set, the page is found only when exactly one page is
shared with the integration. Otherwise the bot asks for NOTION_PARENT_PAGE_ID.
The new database ID is saved in the data folder so restarts reuse it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.notion_client import NotionClient
from app.notion_writer import REQUIRED_PROPERTIES

DATABASE_TITLE = "Jack Sparrow Reports"
ID_FILE = "notion_database_id.txt"


class NotionSetupError(Exception):
    pass


def _property_definitions() -> dict[str, Any]:
    kinds = {
        "title": {"title": {}},
        "select": {"select": {"options": []}},
        "multi_select": {"multi_select": {"options": []}},
        "url": {"url": {}},
        "rich_text": {"rich_text": {}},
        "date": {"date": {}},
    }
    return {name: kinds[kind] for name, kind in REQUIRED_PROPERTIES.items()}


def find_parent_page(client: NotionClient, configured: str | None = None) -> str:
    if configured:
        return configured
    result = client.request("POST", "/search", {
        "filter": {"property": "object", "value": "page"},
        "page_size": 10,
    })
    pages = result.get("results", [])
    if len(pages) == 1:
        return pages[0]["id"]
    if not pages:
        raise NotionSetupError(
            "No Notion page is shared with the integration. Open a page in Notion, "
            "click ... > Connections, add your integration, then restart the bot."
        )
    raise NotionSetupError(
        f"{len(pages)} pages are shared with the integration. Set NOTION_PARENT_PAGE_ID "
        "to the ID of the page where the database should go."
    )


def ensure_database(
    client: NotionClient,
    data_dir: Path,
    configured_id: str | None,
    parent_page_id: str | None,
) -> str:
    """Return the database ID to use, creating the database if needed."""
    if configured_id:
        return configured_id
    id_file = data_dir / ID_FILE
    if id_file.exists():
        saved = id_file.read_text(encoding="utf-8").strip()
        if saved:
            return saved
    parent = find_parent_page(client, parent_page_id)
    db = client.request("POST", "/databases", {
        "parent": {"type": "page_id", "page_id": parent},
        "title": [{"type": "text", "text": {"content": DATABASE_TITLE}}],
        "properties": _property_definitions(),
    })
    data_dir.mkdir(parents=True, exist_ok=True)
    id_file.write_text(db["id"], encoding="utf-8")
    return db["id"]
