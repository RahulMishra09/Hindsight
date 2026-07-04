"""Canonical Redis Stream names and helpers.

Stream names follow ``hindsight:<step>``; the dead-letter stream for any stream
is that name suffixed with ``.dlq``. Consumer group names follow ``<step>-cg``
(SAD §9). Centralized here so producers, consumers, and tests never disagree on
a literal string.
"""

from __future__ import annotations

from typing import Final


class Stream:
    """Stream name constants."""

    INGEST_REQUESTED: Final = "hindsight:ingest.requested"
    DOC_FETCHED: Final = "hindsight:doc.fetched"


class Group:
    """Consumer-group name constants (one group per worker type — rule #3)."""

    ECHO: Final = "echo-cg"


def dlq_of(stream: str) -> str:
    """Return the dead-letter stream name for ``stream``."""
    return f"{stream}.dlq"
