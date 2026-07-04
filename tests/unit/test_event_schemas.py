"""Unit tests for app.events.schemas."""

import json

from pydantic import ValidationError
import pytest

from app.events.schemas import DocFetched, IngestRequested


def test_ingest_requested_defaults():
    """IngestRequested auto-generates event_id and occurred_at."""
    evt = IngestRequested(source_id="src-1")
    assert evt.event_type == "ingest.requested"
    assert evt.version == 1
    assert evt.source_id == "src-1"
    assert evt.event_id  # auto-generated UUID string
    assert evt.occurred_at is not None
    assert evt.content_hash is None


def test_doc_fetched_requires_content_hash():
    """DocFetched narrows content_hash to required."""
    evt = DocFetched(source_id="s", document_id="d", content_hash="abc123")
    assert evt.content_hash == "abc123"


def test_events_are_frozen():
    """Events are immutable (Pydantic frozen=True)."""
    evt = IngestRequested(source_id="src-1")
    with pytest.raises(ValidationError):
        evt.source_id = "changed"  # type: ignore[misc]


def test_events_forbid_extra_fields():
    """Extra fields are rejected (extra='forbid')."""
    with pytest.raises(ValidationError):
        IngestRequested(source_id="src-1", bogus="field")  # type: ignore[call-arg]


def test_roundtrip_json():
    """Events serialize to JSON and back."""
    evt = IngestRequested(source_id="src-1", uri="https://example.com")
    payload = evt.model_dump_json()
    restored = IngestRequested.model_validate_json(payload)
    assert restored.source_id == evt.source_id
    assert restored.event_id == evt.event_id


def test_base_event_content_hash_optional():
    """BaseEvent allows None content_hash."""
    data = json.loads(IngestRequested(source_id="x").model_dump_json())
    assert data["content_hash"] is None
