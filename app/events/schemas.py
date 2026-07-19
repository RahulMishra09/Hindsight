"""Versioned event schemas carried on Redis Streams."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field


def _new_event_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class BaseEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(default_factory=_new_event_id)
    occurred_at: datetime = Field(default_factory=_utcnow)
    content_hash: str | None = None


class IngestRequested(BaseEvent):
    event_type: Literal["ingest.requested"] = "ingest.requested"
    version: Literal[1] = 1

    source_id: str
    uri: str | None = None


class DocDiscovered(BaseEvent):
    event_type: Literal["doc.discovered"] = "doc.discovered"
    version: Literal[1] = 1

    source_id: str
    document_id: str
    url: str


class DocFetched(BaseEvent):
    event_type: Literal["doc.fetched"] = "doc.fetched"
    version: Literal[1] = 1

    source_id: str
    document_id: str
    content_hash: Annotated[str, Field()]


class DocParsed(BaseEvent):
    event_type: Literal["doc.parsed"] = "doc.parsed"
    version: Literal[1] = 1

    source_id: str
    document_id: str
    content_hash: Annotated[str, Field()]


class DocDeduped(BaseEvent):
    event_type: Literal["doc.deduped"] = "doc.deduped"
    version: Literal[1] = 1

    document_id: str
    content_hash: Annotated[str, Field()]
    is_duplicate: bool = False
    duplicate_of: str | None = None


class DocClassified(BaseEvent):
    event_type: Literal["doc.classified"] = "doc.classified"
    version: Literal[1] = 1

    document_id: str
    incident_id: str
    content_hash: Annotated[str, Field()]
    labels: list[str] = Field(default_factory=list)
