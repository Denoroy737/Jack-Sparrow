"""Notion page body for reports (Phase 5, tasks 5.2 and 5.5).

Layout v2 (approved 2026-10-28): Summary, Key points with bold labels, and
Tools and links as a Name | Link | Status table. Empty sections are left out
(Design.md section 5). Charts are a table, not an image: see notion_writer and
the Phases.md note on chart images.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from app.schemas import ChartSpec, Report

RICH_TEXT_LIMIT = 1900  # Notion caps one text run at 2000 characters
TRANSCRIPT_BLOCK_CHARS = 1800
MAX_TRANSCRIPT_BLOCKS = 40
MAX_LINK_ROWS = 40
LABEL_MAX_CHARS = 40


def _runs(text: str, link: str | None = None, bold: bool = False) -> list[dict[str, Any]]:
    """Split text into rich-text runs under Notion's length limit."""
    text = text or " "
    runs = []
    for i in range(0, len(text), RICH_TEXT_LIMIT):
        content = text[i:i + RICH_TEXT_LIMIT]
        item: dict[str, Any] = {"type": "text", "text": {"content": content}}
        if link:
            item["text"]["link"] = {"url": link}
        if bold:
            item["annotations"] = {"bold": True}
        runs.append(item)
    return runs


def _labelled_runs(text: str) -> list[dict[str, Any]]:
    """'Label: explanation' -> bold label, then the explanation. Plain text otherwise."""
    head, sep, rest = text.partition(": ")
    if sep and 0 < len(head) <= LABEL_MAX_CHARS and rest:
        return _runs(head, bold=True) + _runs(" " + rest)
    return _runs(text)


def _block(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"object": "block", "type": kind, kind: payload}


def paragraph(text: str, link: str | None = None) -> dict[str, Any]:
    return _block("paragraph", {"rich_text": _runs(text, link)})


def heading(text: str) -> dict[str, Any]:
    return _block("heading_2", {"rich_text": _runs(text)})


def bullet(text: str, link: str | None = None) -> dict[str, Any]:
    return _block("bulleted_list_item", {"rich_text": _runs(text, link)})


def labelled_bullet(text: str) -> dict[str, Any]:
    return _block("bulleted_list_item", {"rich_text": _labelled_runs(text)})


def numbered(text: str) -> dict[str, Any]:
    return _block("numbered_list_item", {"rich_text": _runs(text)})


Cell = str | tuple[str, str | None]  # plain text, or (text, link)


def _cell_runs(cell: Cell) -> list[dict[str, Any]]:
    if isinstance(cell, tuple):
        text, link = cell
        return _runs(text, link)
    return _runs(cell)


def table(rows: list[list[Cell]]) -> dict[str, Any]:
    width = len(rows[0])
    children = [
        {"object": "block", "type": "table_row",
         "table_row": {"cells": [_cell_runs(cell) for cell in row]}}
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
    rows: list[list[Cell]] = [["Label", "Value"]]
    rows += [[label, f"{value:g}"] for label, value in pairs]
    return table(rows)


def _host(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.") or url


def _status_text(resource: dict[str, Any]) -> str:
    if resource.get("status") == "verified":
        return "verified (official)" if resource.get("tier") == "official" else "verified"
    return "needs review"


def tools_and_links_rows(report: Report) -> list[list[Cell]]:
    """One row per tool or link: Name, Link, Status. Matches tool names to research results."""
    resources = [dict(r) for r in report.resources if r.get("url")]
    used: set[int] = set()
    rows: list[list[Cell]] = [["Name", "Link", "Status"]]
    seen_urls: set[str] = set()

    for tool in report.tools:
        key = tool.casefold()
        match = None
        for i, res in enumerate(resources):
            if i in used:
                continue
            name = str(res.get("name", "")).casefold()
            if name and (name == key or key in name or name in key):
                match = i
                break
        if match is None:
            rows.append([tool, "no link found", "needs review"])
            continue
        used.add(match)
        res = resources[match]
        seen_urls.add(res["url"])
        rows.append([tool, (res["url"], res["url"]), _status_text(res)])

    for i, res in enumerate(resources):
        if i in used or res["url"] in seen_urls:
            continue
        seen_urls.add(res["url"])
        rows.append([str(res.get("name") or _host(res["url"])), (res["url"], res["url"]),
                     _status_text(res)])

    for link in report.links:
        if link in seen_urls:
            continue
        seen_urls.add(link)
        rows.append([_host(link), (link, link), "from the reel"])

    return rows[:MAX_LINK_ROWS + 1]


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
    if report.source_url.startswith(("http://", "https://")):
        blocks.append(paragraph("Source: open reel", link=report.source_url))

    blocks.append(heading("Summary"))
    blocks.append(paragraph(report.summary or report.tldr))

    if report.key_points:
        blocks.append(heading("Key points"))
        blocks.extend(labelled_bullet(p) for p in report.key_points)

    if report.steps:
        blocks.append(heading("Steps"))
        blocks.extend(numbered(s) for s in report.steps)

    rows = tools_and_links_rows(report)
    if len(rows) > 1:
        blocks.append(heading("Tools and links"))
        blocks.append(table(rows))

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
