"""Instagram link parsing (Phase 2, tasks 2.3 and 2.4).

Accepted forms:
- https://www.instagram.com/reel/SHORTCODE/
- https://www.instagram.com/reels/SHORTCODE/
- https://www.instagram.com/p/SHORTCODE/
- https://www.instagram.com/tv/SHORTCODE/
- https://www.instagram.com/share/... (share links; key is the token in the URL)

The dedupe key is "ig:<shortcode>" for post-style links, and "ig-share:<token>"
for share links. Share tokens are not always the same as the shortcode, so a
share link and its canonical reel link may be stored as two jobs. This is a
known limitation, noted in docs/Phases.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_POST_RE = re.compile(
    r"https?://(?:www\.|m\.)?instagram\.com/(?:reels?|p|tv)/([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
_SHARE_RE = re.compile(
    r"https?://(?:www\.|m\.)?instagram\.com/share/(?:reels?/|p/)?([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReelRef:
    key: str  # shortcode or share token
    kind: str  # "post" or "share"
    canonical_url: str

    @property
    def dedupe_key(self) -> str:
        prefix = "ig" if self.kind == "post" else "ig-share"
        return f"{prefix}:{self.key}"


def parse_reel_url(text: str) -> ReelRef | None:
    """Find the first supported Instagram link in `text`. Returns None if there is none."""
    if not text:
        return None
    share = _SHARE_RE.search(text)
    if share:
        key = share.group(1)
        return ReelRef(
            key=key,
            kind="share",
            canonical_url=f"https://www.instagram.com/share/{key}/",
        )
    post = _POST_RE.search(text)
    if post:
        key = post.group(1)
        return ReelRef(
            key=key,
            kind="post",
            canonical_url=f"https://www.instagram.com/reel/{key}/",
        )
    return None
