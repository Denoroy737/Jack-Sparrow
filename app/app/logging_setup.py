"""Logging setup.

Rules R12: log IDs, stage names, durations, and error types. Never log
transcripts, full report text, or URLs that carry tokens. Callers are
responsible for what they pass to the logger; this module only formats it.
"""

from __future__ import annotations

import logging

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level.upper(), format=_FORMAT, force=True)
