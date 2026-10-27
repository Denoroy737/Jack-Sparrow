"""Output schemas for each agent (Phase 4, task 4.1).

Every agent must return JSON that validates against one of these models.
Invalid output is retried, then the analysis continues with a partial flag.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]


class Extraction(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    tldr: str = Field(min_length=10, max_length=600)
    key_points: list[str] = Field(default_factory=list, max_length=7)
    steps: list[str] = Field(default_factory=list, max_length=15)
    tools: list[str] = Field(default_factory=list, max_length=20)
    links: list[str] = Field(default_factory=list, max_length=20)
    claims: list[str] = Field(default_factory=list, max_length=15)
    paper_dependency: bool = False
    paper_query: str | None = None
    open_questions: list[str] = Field(default_factory=list, max_length=5)
    creator: str | None = None


class Classification(BaseModel):
    category: str = Field(min_length=2, max_length=24)
    tags: list[str] = Field(default_factory=list, max_length=5)
    confidence: Confidence = "medium"


class ChartSpec(BaseModel):
    kind: Literal["bar", "line", "table"]
    title: str = Field(min_length=3, max_length=120)
    labels: list[str] = Field(min_length=2, max_length=8)
    values: list[float] = Field(min_length=2, max_length=8)
    source_note: str = Field(min_length=3, max_length=200)


class ChartPlan(BaseModel):
    chart: ChartSpec | None = None


class VerifiedClaim(BaseModel):
    """sourced: a web source overlaps the claim's key words. Not a model-checked verdict."""

    text: str
    status: Literal["sourced", "unverified"] = "unverified"
    source: str | None = None


class SocialPost(BaseModel):
    hook: str = Field(min_length=10, max_length=90)
    body: str = Field(min_length=20, max_length=350)
    closing: str = Field(min_length=5, max_length=80)


class PaperRef(BaseModel):
    title: str
    url: str
    authors: list[str] = Field(default_factory=list)


class Report(BaseModel):
    """Everything the Phase 5 Notion writer needs. Built by the analysis pipeline."""

    title: str
    category: str
    tags: list[str]
    source_url: str
    creator: str | None
    tldr: str
    key_points: list[str]
    steps: list[str]
    tools: list[str]
    links: list[str]
    claims: list[VerifiedClaim]
    papers: list[PaperRef]
    chart: ChartSpec | None
    open_questions: list[str]
    confidence: Confidence
    partial: bool = False
    notes: list[str] = Field(default_factory=list)
    post: str | None = None  # community post text (plain, no links)
