"""Unit tests for app.events.consumer — BaseWorker retry, DLQ, and reaper.

Uses a fake Redis client to verify delivery semantics without I/O.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, ClassVar

import pytest

from app.events.consumer import BaseWorker
from app.events.schemas import IngestRequested


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class FakeRedis:
    """Fake Redis supporting the subset of commands BaseWorker uses."""

    def __init__(self) -> None:
        self.groups_created: list[tuple[str, str]] = []
        self.acked: list[tuple[str, str, str]] = []
        self.dlq_entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._read_queue: list[list[tuple[str, list[tuple[str, dict[str, str]]]]]] = []
        self._autoclaim_results: list[tuple[str, list[tuple[str, dict[str, str]]], list[str]]] = []

    async def xgroup_create(self, stream: str, group: str, **kwargs: Any) -> None:
        self.groups_created.append((stream, group))

    async def xreadgroup(self, group: str, consumer: str, streams: dict[str, str], **kw: Any):
        if self._read_queue:
            return self._read_queue.pop(0)
        return None

    async def xack(self, stream: str, group: str, entry_id: str) -> None:
        self.acked.append((stream, group, entry_id))

    async def xadd(self, stream: str, fields: dict[str, Any]) -> str:
        self.dlq_entries[stream].append(fields)
        return "dlq-1"

    async def xautoclaim(self, stream: str, group: str, consumer: str, min_idle: int, **kw: Any):
        if self._autoclaim_results:
            return self._autoclaim_results.pop(0)
        return ("0-0", [], [])

    def enqueue_entries(self, stream: str, entries: list[tuple[str, dict[str, str]]]) -> None:
        """Queue up entries for the next xreadgroup call."""
        self._read_queue.append([(stream, entries)])


# ---------------------------------------------------------------------------
# Concrete worker for testing
# ---------------------------------------------------------------------------
class StubWorker(BaseWorker[IngestRequested]):
    stream: ClassVar[str] = "test:stream"
    group: ClassVar[str] = "test-cg"
    event_model = IngestRequested

    def __init__(self, client: Any, **kwargs: Any) -> None:
        super().__init__(client, jitter=lambda _: 0.0, **kwargs)
        self.handled: list[IngestRequested] = []
        self.fail_count = 0  # raise on first N calls to handle

    async def handle(self, event: IngestRequested) -> None:
        if self.fail_count > 0:
            self.fail_count -= 1
            raise RuntimeError("simulated failure")
        self.handled.append(event)


def _make_entry(source_id: str = "src-1") -> tuple[str, dict[str, str]]:
    event = IngestRequested(source_id=source_id)
    fields = {
        "data": event.model_dump_json(),
        "event_type": "ingest.requested",
        "version": "1",
    }
    return ("1-1", fields)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_ensure_group_creates_group():
    fake = FakeRedis()
    worker = StubWorker(fake)
    await worker.ensure_group()
    assert ("test:stream", "test-cg") in fake.groups_created


async def test_successful_dispatch_acks():
    """A successfully handled message is ACK-ed."""
    fake = FakeRedis()
    entry_id, fields = _make_entry()
    fake.enqueue_entries("test:stream", [(entry_id, fields)])
    worker = StubWorker(fake)
    await worker._poll_once()
    assert len(worker.handled) == 1
    assert any(entry_id in ack for ack in fake.acked)


async def test_retry_exhaustion_sends_to_dlq():
    """After max_retries, the message goes to the DLQ."""
    fake = FakeRedis()
    worker = StubWorker(fake, max_retries=2)
    worker.fail_count = 100  # always fail

    # Simulate the no-sleep path for testing
    sleeps: list[float] = []

    async def fake_sleep(t: float) -> None:
        sleeps.append(t)

    worker._sleep = fake_sleep

    entry_id, fields = _make_entry()
    fake.enqueue_entries("test:stream", [(entry_id, fields)])
    await worker._poll_once()

    # Should have retried max_retries times (2 retries = 2 sleeps)
    assert len(sleeps) == 2
    # Message should be dead-lettered
    dlq_name = "test:stream.dlq"
    assert len(fake.dlq_entries[dlq_name]) == 1
    dlq_entry = fake.dlq_entries[dlq_name][0]
    assert dlq_entry["error"] == "simulated failure"
    # And ACK-ed (so it doesn't stay pending)
    assert any(entry_id in ack for ack in fake.acked)


async def test_retry_succeeds_on_second_attempt():
    """If handle succeeds after one retry, no DLQ."""
    fake = FakeRedis()
    worker = StubWorker(fake, max_retries=3)
    worker.fail_count = 1  # fail once, then succeed

    async def fake_sleep(t: float) -> None:
        pass

    worker._sleep = fake_sleep

    entry_id, fields = _make_entry()
    fake.enqueue_entries("test:stream", [(entry_id, fields)])
    await worker._poll_once()

    assert len(worker.handled) == 1
    assert len(fake.dlq_entries) == 0


async def test_unparseable_message_goes_to_dlq():
    """A message that can't be parsed goes straight to DLQ without retries."""
    fake = FakeRedis()
    worker = StubWorker(fake)
    bad_entry = ("1-bad", {"data": "not-valid-json{{{", "event_type": "x", "version": "1"})
    fake.enqueue_entries("test:stream", [bad_entry])
    await worker._poll_once()

    assert len(worker.handled) == 0
    dlq_name = "test:stream.dlq"
    assert len(fake.dlq_entries[dlq_name]) == 1
    assert "parse_error" in fake.dlq_entries[dlq_name][0]["error"]


async def test_reaper_reclaims_entries():
    """XAUTOCLAIM reaper dispatches reclaimed entries."""
    fake = FakeRedis()
    worker = StubWorker(fake)

    entry_id, fields = _make_entry(source_id="reaped-src")
    fake._autoclaim_results.append(("0-0", [(entry_id, fields)], []))

    reclaimed = await worker.reap()
    assert reclaimed == 1
    assert len(worker.handled) == 1
    assert worker.handled[0].source_id == "reaped-src"


async def test_backoff_delay_increases():
    """Backoff delay increases exponentially."""
    fake = FakeRedis()
    worker = StubWorker(fake, base_backoff_s=1.0, backoff_factor=2.0)
    d1 = worker._backoff_delay(1)
    d2 = worker._backoff_delay(2)
    d3 = worker._backoff_delay(3)
    # With zero jitter: 1*2^0=1, 1*2^1=2, 1*2^2=4
    assert d1 == pytest.approx(1.0)
    assert d2 == pytest.approx(2.0)
    assert d3 == pytest.approx(4.0)


async def test_stop_terminates_run_loop():
    """Calling stop() causes run() to exit after the current iteration."""
    fake = FakeRedis()
    worker = StubWorker(fake)
    # run() sets _running=True after ensure_group, so we stop inside
    # the first poll_once call (the fake returns None → loop checks _running).
    poll_count = 0
    original_poll = worker._poll_once

    async def stop_on_first_poll() -> int:
        nonlocal poll_count
        poll_count += 1
        worker.stop()
        return await original_poll()

    worker._poll_once = stop_on_first_poll  # type: ignore[assignment]
    await worker.run()  # should return, not hang
    assert poll_count == 1
