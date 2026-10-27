"""Category validation (Architecture.md section 5, PRD FR-10).

Agents may propose categories. A proposal is kept only if it is short and
specific. Otherwise it maps to the closest preferred category or "other".
"""

from __future__ import annotations

import re

PREFERRED = (
    "projects",
    "software",
    "hardware",
    "tools",
    "tricks",
    "startup",
    "ideas",
    "tech",
    "ai/ml",
    "coding",
    "other",
)

_ALIASES = {
    "ai": "ai/ml",
    "ml": "ai/ml",
    "machine learning": "ai/ml",
    "artificial intelligence": "ai/ml",
    "ai ml": "ai/ml",
    "programming": "coding",
    "code": "coding",
    "developer tools": "tools",
    "hacks": "tricks",
    "tips": "tricks",
    "business": "startup",
    "idea": "ideas",
    "project": "projects",
    "gadgets": "hardware",
}

_NEW_OK = re.compile(r"^[a-z0-9/+\- ]{2,24}$")


def validate_category(proposed: str) -> str:
    """Return a category from the preferred list, or an accepted new category."""
    name = re.sub(r"\s+", " ", proposed.strip().lower())
    if name in PREFERRED:
        return name
    if name in _ALIASES:
        return _ALIASES[name]
    if name.replace("-", " ") in _ALIASES:
        return _ALIASES[name.replace("-", " ")]
    words = name.split(" ")
    if len(words) <= 2 and _NEW_OK.match(name):
        return name
    return "other"
