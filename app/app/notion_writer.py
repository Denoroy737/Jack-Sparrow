"""Notion report writer (Phase 5, tasks 5.1, 5.3, 5.4).

Page body layout (tasks 5.2 and 5.5) waits for owner approval of the design
preview (docs/design/notion_report_preview.html). See notion_layout.py.

Rules:
- The database is created once by the owner. This code only validates it (5.1).
- Each job writes at most one page. The Job ID property finds an existing page,
  and that page's properties are updated instead of creating a duplicate (5.4, R30).
"""

from __future__ import annotations

from typing import Any

from app.notion_client import NotionClient
from app.schemas import Report

# property name -> required Notion type (PRD FR-14)
REQUIRED_PROPERTIES: dict[str, str] = {
    "Title": "title",
    "Category": "select",
    "Tags": "multi_select",
    "Source URL": "url",
    "Creator": "rich_text",
    "Date saved": "date",
    "Status": "select",
    "Confidence": "select",
    "Job ID": "rich_text",
}


class NotionSchemaError(Exception):
    pass


def schema_problems(database: dict[str, Any]) -> list[str]:
    """Return a list of problems with the database schema. Empty list means it is valid."""
    actual = database.get("properties", {}) or {}
    problems: list[str] = []
    for name, wanted in REQUIRED_PROPERTIES.items():
        if name not in actual:
            problems.append(f"missing property '{name}'")
        elif actual[name].get("type") != wanted:
            problems.append(f"'{name}' must be type {wanted}")
    return problems


def validate_database(client: NotionClient, database_id: str) -> None:
    db = client.retrieve_database(database_id)
    problems = schema_problems(db)
    if problems:
        message = "Notion database: " + "; ".join(problems)
        if db.get("object") != "database" or not db.get("properties"):
            message += (
                ". Notion returned no properties: check NOTION_DATABASE_ID is a "
                "database ID and the integration is connected to it"
            )
        raise NotionSchemaError(message)


def build_properties(report: Report, job_id: str, date_saved: str, status: str) -> dict[str, Any]:
    creator = report.creator or ""
    return {
        "Title": {"title": [{"text": {"content": report.title[:200]}}]},
        "Category": {"select": {"name": report.category}},
        "Tags": {"multi_select": [{"name": t[:100]} for t in report.tags]},
        "Source URL": {"url": report.source_url},
        "Creator": {"rich_text": [{"text": {"content": creator[:200]}}] if creator else []},
        "Date saved": {"date": {"start": date_saved}},
        "Status": {"select": {"name": status}},
        "Confidence": {"select": {"name": report.confidence}},
        "Job ID": {"rich_text": [{"text": {"content": job_id}}]},
    }


def find_page_by_job(client: NotionClient, database_id: str, job_id: str) -> str | None:
    result = client.query_database(
        database_id,
        {"filter": {"property": "Job ID", "rich_text": {"equals": job_id}}, "page_size": 1},
    )
    results = result.get("results", [])
    return results[0]["id"] if results else None


def write_report(
    client: NotionClient,
    database_id: str,
    report: Report,
    job_id: str,
    date_saved: str,
    transcript_text: str,
    status: str = "Ready",
) -> tuple[str, str | None]:
    """Create the report page (properties and body), or update properties if it exists.

    Returns (page_id, page_url). Body is written only on first create, so reruns
    never duplicate content. Body repair for half-written pages is Phase 6.
    """
    from app.notion_layout import build_blocks

    props = build_properties(report, job_id, date_saved, status)
    existing = find_page_by_job(client, database_id, job_id)
    if existing:
        result = client.update_page(existing, {"properties": props})
        return existing, result.get("url")
    children = build_blocks(report, transcript_text, date_saved)[:100]
    page = client.create_page({
        "parent": {"database_id": database_id},
        "properties": props,
        "children": children,
    })
    return page["id"], page.get("url")
