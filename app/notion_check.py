"""Diagnostic for the Notion database setup (Phase 5). Never prints the token."""

from __future__ import annotations

from typing import Any

from app.notion_client import NotionClient
from app.notion_writer import schema_problems

NO_PROPERTIES_HINT = (
    "Notion returned no properties. Check that NOTION_DATABASE_ID is a database ID "
    "(not a page), and that the integration is connected to that database: "
    "open the database in Notion, click ... > Connections, and add your integration."
)


def _plain(rich: list[dict[str, Any]] | None) -> str:
    return "".join(part.get("plain_text", "") for part in rich or [])


def describe_database(client: NotionClient, database_id: str) -> list[str]:
    db = client.retrieve_database(database_id)
    props: dict[str, Any] = db.get("properties") or {}
    lines = [
        f"object: {db.get('object')}",
        f"name: {_plain(db.get('title')) or '(untitled)'}",
        f"properties found: {len(props)}",
    ]
    lines += [f"  - {name}: {spec.get('type')}" for name, spec in props.items()]
    problems = schema_problems(db)
    if problems:
        lines.append("problems:")
        lines += [f"  * {p}" for p in problems]
    else:
        lines.append("schema: OK")
    if db.get("object") != "database":
        lines.append("hint: the ID does not point to a database.")
    elif not props:
        lines.append(f"hint: {NO_PROPERTIES_HINT}")
    return lines
