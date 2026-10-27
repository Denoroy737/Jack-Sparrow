"""Notion page body for reports (Phase 5, tasks 5.2 and 5.5). Layout approved 2026-10-28.

Section order follows docs/design/notion_report_preview.html. Empty sections are
left out (Design.md section 5). Charts are a table, not an image: see notion_writer
and the Phases.md note on chart images.
"""

from __future__ import annotations

from typing import Any

from app.schemas import ChartSpec, Report

RICH_TEXT_LIMIT = 1900  # Notion caps one text run at 2000 characters
TRANSCRIPT_BLOCK_CHARS = 1800
MAX_TRANSCRIPT_BLOCKS = 40


def _runs(text: str, link: str | None = None) -> list[dict[str, Any]]:
    """Split text into rich-text runs under Notion's length limit."""
    text = text or " "
    runs = []
    for i in range(0, len(text), RICH_TEXT_LIMIT):
        content = text[i:i + RICH_TEXT_LIMIT]
        item: dict[str, Any] = {"type": "text", "text": {"content": content}}
        if link:
            item["text"]["link"] = {"url": link}
        runs.append(item)
    return runs


def _block(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"object": "block", "type": kind, kind: payload}


def paragraph(text: str, link: str | None = None) -> dict[str, Any]:
    return _block("paragraph", {"rich_text": _runs(text, link)})


def heading(text: str) -> dict[str, Any]:
    return _block("heading_2", {"rich_text": _runs(text)})


def bullet(text: str, link: str | None = None) -> dict[str, Any]:
    return _block("bulleted_list_item", {"rich_text": _runs(text, link)})


def numbered(text: str) -> dict[str, Any]:
    return _block("numbered_list_item", {"rich_text": _runs(text)})


def callout(text: str, emoji: str) -> dict[str, Any]:
    return _block("callout", {"rich_text": _runs(text), "icon": {"type": "emoji", "emoji": emoji}})


def table(rows: list[list[str]]) -> dict[str, Any]:
    width = len(rows[0])
    children = [
        {"object": "block", "type": "table_row",
         "table_row": {"cells": [_runs(cell) for cell in row]}}
        for row in rows
    ]
    return _block("table", {
        "table_width": width,
        "has_column_header": True,
        "has_row_header": False,
        "children": children,
    })


def toggle(title: str, children: list[dict[str, Any]]) -> dict[str, Any]:
    return _block("toggle", {"rich_text": _runs(title), "children": children})


def _chart_table(chart: ChartSpec) -> dict[str, Any]:
    pairs = zip(chart.labels, chart.values, strict=True)
    rows = [["Label", "Value"]] + [[label, f"{value:g}"] for label, value in pairs]
    return table(rows)


def _chunks(text: str, size: int, limit: int) -> list[str]:
    parts = [text[i:i + size] for i in range(0, len(text), size)] or [""]
    return parts[:limit]


def build_blocks(report: Report, transcript_text: str, date_saved: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []

    meta = (
        f"Category: {report.category} · Tags: {', '.join(report.tags) or 'none'} · "
        f"Creator: {report.creator or 'not stated'} · Saved: {date_saved} · "
        f"Confidence: {report.confidence}"
    )
    blocks.append(paragraph(meta))
    blocks.append(paragraph("Source: open reel", link=report.source_url))

    blocks.append(callout(report.tldr, "💡"))

    if report.key_points:
        blocks.append(heading("Key points"))
        blocks.extend(bullet(p) for p in report.key_points)

    if report.steps:
        blocks.append(heading("Steps"))
        blocks.extend(numbered(s) for s in report.steps)

    link_items = [(u, None) for u in report.links]
    if report.tools or link_items:
        blocks.append(heading("Tools and links"))
        blocks.extend(bullet(t) for t in report.tools)
        blocks.extend(bullet(u, link=u) for u, _ in link_items)

    if report.chart is not None:
        blocks.append(heading("Graphs"))
        blocks.append(paragraph(report.chart.title))
        blocks.append(_chart_table(report.chart))
        blocks.append(paragraph(report.chart.source_note))

    if report.claims:
        blocks.append(heading("Claims"))
        for claim in report.claims:
            if claim.status == "sourced" and claim.source:
                blocks.append(bullet(f"{claim.text} (sourced)", link=claim.source))
            else:
                blocks.append(bullet(f"{claim.text} (unverified)"))

    if report.papers:
        blocks.append(heading("Sources and papers"))
        blocks.extend(bullet(p.title, link=p.url) for p in report.papers)

    blocks.append(heading("Agent notes"))
    notes = list(report.notes)
    if report.open_questions:
        notes.append("Open questions: " + "; ".join(report.open_questions))
    blocks.append(paragraph(" ".join(notes) if notes else "No issues found."))

    chunks = _chunks(transcript_text, TRANSCRIPT_BLOCK_CHARS, MAX_TRANSCRIPT_BLOCKS)
    transcript_children = [paragraph(chunk) for chunk in chunks]
    blocks.append(toggle("Transcript", transcript_children))
    return blocks
