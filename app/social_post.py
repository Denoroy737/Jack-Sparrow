"""Community post for WhatsApp or Telegram (approved style, 2026-10-28).

Format: hook, blank line, body, blank line, closing. Plain text, no links,
no hashtags, no category, no creator name. Validated before it is used.
"""

from __future__ import annotations

import re

from app.llm import LLM, AgentError, call_agent
from app.schemas import SocialPost

MAX_TOTAL_CHARS = 600
_FORBIDDEN = re.compile(r"https?://|www\.|\.com\b|#\w+|notion|instagram", re.IGNORECASE)


def render_post(post: SocialPost) -> str:
    return f"{post.hook.strip()}\n\n{post.body.strip()}\n\n{post.closing.strip()}"


def validate_post(text: str) -> list[str]:
    problems: list[str] = []
    if len(text) > MAX_TOTAL_CHARS:
        problems.append("post too long")
    if _FORBIDDEN.search(text):
        problems.append("post contains a link, hashtag, or banned word")
    return problems


def write_post(llm: LLM, title: str, summary: str, transcript_text: str) -> str | None:
    """Return the post text, or None when the agent fails or the output breaks the rules."""
    user = f"Title: {title}\nSummary: {summary}\n\nTranscript:\n{transcript_text}"
    try:
        post = call_agent(llm, "post", user, SocialPost)
    except AgentError:
        return None
    text = render_post(post)
    if validate_post(text):
        return None
    return text
