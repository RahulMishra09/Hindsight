"""Versioned event schemas carried on Redis Streams.

Every event is an immutable Pydantic model that self-describes its ``event_type``
and ``version`` so consumers can evolve payloads without breaking older
producers. Wire format is a single JSON string stored under the ``data`` field of
a stream entry (see :mod:`app.events.publisher`).

Adding a breaking change to a payload = bump ``version`` and, if consumers must
distinguish, branch on it. Backward-compatible additions keep the same version.
"""

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
    """Common metadata shared by every event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(default_factory=_new_event_id)
    occurred_at: datetime = Field(default_factory=_utcnow)
    # ``content_hash`` is the pipeline-wide idempotency key (SAD §15). It may be
    # absent at the very first hop (before the body is fetched/normalized).
    content_hash: str | None = None


class IngestRequested(BaseEvent):
    """Emitted when ingestion of a source is requested. First hop in the pipeline."""

    event_type: Literal["ingest.requested"] = "ingest.requested"
    version: Literal[1] = 1

    source_id: str
    uri: str | None = None


class DocFetched(BaseEvent):
    """Emitted once a document's raw body has been fetched for a source."""

    event_type: Literal["doc.fetched"] = "doc.fetched"
    version: Literal[1] = 1

    source_id: str
    document_id: str
    # Fetched docs always carry a content_hash; narrow the optional base field.
    content_hash: Annotated[str, Field()]
