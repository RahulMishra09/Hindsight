"""EchoWorker — a toy worker that proves the consumer loop end-to-end.

It consumes ``hindsight:ingest.requested`` and simply logs each event. It exists
to demonstrate the chassis (group creation, poll loop, ack, reaper) works before
any real pipeline worker is written. Real workers (Week 2+) subclass
:class:`BaseWorker` the same way — supplying ``stream``, ``group``,
``event_model``, and :meth:`handle`.
"""

from __future__ import annotations

from typing import ClassVar

from app.core.logging import get_logger
from app.events.consumer import BaseWorker
from app.events.schemas import IngestRequested
from app.events.streams import Group, Stream

logger = get_logger(__name__)


class EchoWorker(BaseWorker[IngestRequested]):
    """Logs every ``IngestRequested`` event it receives."""

    stream: ClassVar[str] = Stream.INGEST_REQUESTED
    group: ClassVar[str] = Group.ECHO
    event_model = IngestRequested

    async def handle(self, event: IngestRequested) -> None:
        logger.info(
            "echo.received",
            event_id=event.event_id,
            source_id=event.source_id,
            uri=event.uri,
            occurred_at=event.occurred_at.isoformat(),
        )
