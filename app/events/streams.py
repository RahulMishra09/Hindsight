"""Canonical Redis Stream names and helpers."""

from __future__ import annotations

from typing import Final


class Stream:
    INGEST_REQUESTED: Final = "hindsight:ingest.requested"
    DOC_DISCOVERED: Final = "hindsight:doc.discovered"
    DOC_FETCHED: Final = "hindsight:doc.fetched"
    DOC_PARSED: Final = "hindsight:doc.parsed"
    DOC_DEDUPED: Final = "hindsight:doc.deduped"
    DOC_CLASSIFIED: Final = "hindsight:doc.classified"


class Group:
    ECHO: Final = "echo-cg"
    CRAWLER: Final = "crawler-cg"
    PARSER: Final = "parser-cg"
    DEDUPER: Final = "deduper-cg"
    CLASSIFIER: Final = "classifier-cg"


def dlq_of(stream: str) -> str:
    return f"{stream}.dlq"
