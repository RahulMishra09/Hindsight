"""Event publisher — a thin async wrapper around Redis Streams ``XADD``.

Events are serialized to a single JSON ``data`` field. ``event_type`` and
``version`` are duplicated as top-level entry fields so streams can be inspected
(and dead-lettered entries triaged) without deserializing the payload.
"""

from __future__ import annotations

from typing import cast

import redis.asyncio as redis
from redis.typing import EncodableT, FieldT

from app.core.logging import get_logger
from app.events.schemas import BaseEvent

logger = get_logger(__name__)


class Publisher:
    """Publishes typed events to Redis Streams."""

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    async def publish(self, stream: str, event: BaseEvent) -> str:
        """Append ``event`` to ``stream`` and return the generated entry id."""
        fields: dict[FieldT, EncodableT] = {
            "data": event.model_dump_json(),
            "event_type": getattr(event, "event_type", event.__class__.__name__),
            "version": str(getattr(event, "version", 1)),
        }
        entry_id = cast(str, await self._client.xadd(stream, fields))
        logger.debug(
            "event.published",
            stream=stream,
            entry_id=entry_id,
            event_type=fields["event_type"],
            event_id=event.event_id,
        )
        return entry_id
