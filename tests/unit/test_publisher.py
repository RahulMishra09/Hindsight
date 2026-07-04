"""Unit tests for app.events.publisher — uses a fake Redis client."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.events.publisher import Publisher
from app.events.schemas import IngestRequested


class FakeRedis:
    """Minimal fake implementing only the xadd method used by Publisher."""

    def __init__(self) -> None:
        self.streams: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._counter = 0

    async def xadd(self, stream: str, fields: dict[str, Any]) -> str:
        self._counter += 1
        entry_id = f"1-{self._counter}"
        self.streams[stream].append(fields)
        return entry_id


async def test_publish_adds_to_stream():
    """Publishing an event writes to the correct stream."""
    fake = FakeRedis()
    pub = Publisher(fake)  # type: ignore[arg-type]
    event = IngestRequested(source_id="src-1", uri="https://example.com")
    entry_id = await pub.publish("test-stream", event)
    assert entry_id == "1-1"
    assert len(fake.streams["test-stream"]) == 1


async def test_publish_includes_metadata_fields():
    """The stream entry includes event_type and version as top-level fields."""
    fake = FakeRedis()
    pub = Publisher(fake)  # type: ignore[arg-type]
    event = IngestRequested(source_id="src-1")
    await pub.publish("test-stream", event)
    entry = fake.streams["test-stream"][0]
    assert entry["event_type"] == "ingest.requested"
    assert entry["version"] == "1"
    assert "data" in entry


async def test_publish_data_is_deserializable():
    """The 'data' field can be parsed back to the original event."""
    fake = FakeRedis()
    pub = Publisher(fake)  # type: ignore[arg-type]
    event = IngestRequested(source_id="src-42")
    await pub.publish("s", event)
    data_json = fake.streams["s"][0]["data"]
    restored = IngestRequested.model_validate_json(data_json)
    assert restored.source_id == "src-42"
    assert restored.event_id == event.event_id
