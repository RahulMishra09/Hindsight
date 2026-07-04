"""Generic Redis Streams consumer.

:class:`BaseWorker` is the reusable chassis every pipeline worker subclasses
(architecture: it must be generic — Week 2 workers subclass it *unchanged*). It
implements:

* consumer-group creation (idempotent, ``MKSTREAM``);
* the ``XREADGROUP`` poll loop with graceful stop;
* per-message exponential-backoff retry (1s / 2s / 4s + jitter, max 3 retries);
* dead-lettering to ``<stream>.dlq`` + ``XACK`` when retries are exhausted or a
  message is unparseable;
* an ``XAUTOCLAIM`` reaper that reclaims entries left pending (a crashed
  consumer) for longer than ``reaper_min_idle_ms`` (default 5 minutes).

A subclass supplies only ``stream``, ``group``, ``event_model``, and
:meth:`handle`. All delivery semantics live here.

Idempotency note: an entry is ``XACK``-ed only after it is either handled or
dead-lettered. A process that dies mid-handle never acks, so the entry stays
pending and is later reclaimed by the reaper (at-least-once delivery).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Awaitable, Callable, Mapping
import os
import random
import time
from typing import ClassVar, Generic, TypeVar, cast

from pydantic import ValidationError
import redis.asyncio as redis
from redis.exceptions import ResponseError

from app.core.logging import get_logger
from app.events.schemas import BaseEvent
from app.events.streams import dlq_of

logger = get_logger(__name__)

TEvent = TypeVar("TEvent", bound=BaseEvent)

# Redis stream entry as returned with decode_responses=True.
Entry = tuple[str, Mapping[str, str]]


class BaseWorker(ABC, Generic[TEvent]):
    """Base class for all stream-consuming workers."""

    # -- Subclass contract (override these) --------------------------------
    stream: ClassVar[str]
    group: ClassVar[str]
    event_model: type[TEvent]

    def __init__(
        self,
        client: redis.Redis,
        *,
        consumer_name: str | None = None,
        consumer_prefix: str = "hindsight",
        batch_size: int = 10,
        block_ms: int = 5_000,
        max_retries: int = 3,
        base_backoff_s: float = 1.0,
        backoff_factor: float = 2.0,
        reaper_min_idle_ms: int = 300_000,
        reaper_interval_s: float = 60.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[float], float] | None = None,
    ) -> None:
        self._client = client
        self.consumer_name = consumer_name or f"{consumer_prefix}-{os.getpid()}"
        self.batch_size = batch_size
        self.block_ms = block_ms
        self.max_retries = max_retries
        self.base_backoff_s = base_backoff_s
        self.backoff_factor = backoff_factor
        self.reaper_min_idle_ms = reaper_min_idle_ms
        self.reaper_interval_s = reaper_interval_s
        self._sleep = sleep
        # Additive jitter in [0, base_backoff_s) unless overridden (tests inject 0).
        self._jitter = jitter if jitter is not None else (lambda cap: random.uniform(0, cap))  # noqa: S311
        self._running = False
        self._last_reap_monotonic = 0.0

    # -- Subclass hook -----------------------------------------------------
    @abstractmethod
    async def handle(self, event: TEvent) -> None:
        """Process a single event. Raising triggers retry / dead-lettering."""

    @property
    def dlq_stream(self) -> str:
        """The dead-letter stream for this worker's source stream."""
        return dlq_of(self.stream)

    # -- Lifecycle ---------------------------------------------------------
    async def ensure_group(self) -> None:
        """Create the consumer group if it does not exist (idempotent)."""
        try:
            await self._client.xgroup_create(self.stream, self.group, id="0", mkstream=True)
            logger.info("worker.group_created", stream=self.stream, group=self.group)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def run(self) -> None:
        """Run the poll loop until :meth:`stop` is called."""
        await self.ensure_group()
        self._running = True
        logger.info(
            "worker.started",
            worker=type(self).__name__,
            stream=self.stream,
            group=self.group,
            consumer=self.consumer_name,
        )
        try:
            while self._running:
                await self._reap_if_due()
                await self._poll_once()
        finally:
            logger.info("worker.stopped", worker=type(self).__name__, consumer=self.consumer_name)

    def stop(self) -> None:
        """Signal the poll loop to exit after the current iteration."""
        self._running = False

    async def _poll_once(self) -> int:
        """Read and dispatch one batch of new entries. Returns count dispatched."""
        response = await self._client.xreadgroup(
            self.group,
            self.consumer_name,
            {self.stream: ">"},
            count=self.batch_size,
            block=self.block_ms,
        )
        if not response:
            return 0
        dispatched = 0
        for _stream_name, entries in cast(list[tuple[str, list[Entry]]], response):
            for entry_id, fields in entries:
                await self._dispatch(entry_id, fields)
                dispatched += 1
        return dispatched

    # -- Reaper ------------------------------------------------------------
    async def _reap_if_due(self) -> None:
        now = time.monotonic()
        if now - self._last_reap_monotonic < self.reaper_interval_s:
            return
        self._last_reap_monotonic = now
        reclaimed = await self.reap()
        if reclaimed:
            logger.info("worker.reaped", worker=type(self).__name__, reclaimed=reclaimed)

    async def reap(self) -> int:
        """Reclaim and re-dispatch entries pending longer than the idle threshold.

        Uses ``XAUTOCLAIM`` to transfer ownership of stale pending entries (from a
        crashed consumer) to this consumer, then dispatches them through the same
        retry/DLQ path as fresh entries.
        """
        cursor = "0-0"
        reclaimed = 0
        while True:
            result = await self._client.xautoclaim(
                self.stream,
                self.group,
                self.consumer_name,
                self.reaper_min_idle_ms,
                start_id=cursor,
                count=self.batch_size,
            )
            # redis-py returns [next_cursor, claimed_entries, deleted_ids].
            cursor = cast(str, result[0])
            entries = cast(list[Entry], result[1])
            for entry_id, fields in entries:
                await self._dispatch(entry_id, fields)
                reclaimed += 1
            if not entries or cursor == "0-0":
                break
        return reclaimed

    # -- Dispatch + retry + DLQ -------------------------------------------
    async def _dispatch(self, entry_id: str, fields: Mapping[str, str]) -> None:
        """Parse, handle-with-retry, and ack (or dead-letter) one entry."""
        try:
            event = self._parse(fields)
        except (ValidationError, KeyError, ValueError) as exc:
            logger.error(
                "worker.unparseable", worker=type(self).__name__, entry_id=entry_id, error=str(exc)
            )
            await self._to_dlq(entry_id, fields, error=f"parse_error: {exc}", attempts=0)
            await self._ack(entry_id)
            return

        try:
            await self._handle_with_retry(event)
        except Exception as exc:  # retries exhausted → dead-letter
            logger.error(
                "worker.exhausted",
                worker=type(self).__name__,
                entry_id=entry_id,
                event_id=event.event_id,
                error=str(exc),
            )
            await self._to_dlq(entry_id, fields, error=str(exc), attempts=self.max_retries)

        await self._ack(entry_id)

    def _parse(self, fields: Mapping[str, str]) -> TEvent:
        return self.event_model.model_validate_json(fields["data"])

    async def _handle_with_retry(self, event: TEvent) -> None:
        """Call :meth:`handle`, retrying on failure with backoff. Re-raises on exhaustion."""
        attempt = 0
        while True:
            try:
                await self.handle(event)
                return
            except Exception as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise
                delay = self._backoff_delay(attempt)
                logger.warning(
                    "worker.retry",
                    worker=type(self).__name__,
                    event_id=event.event_id,
                    attempt=attempt,
                    max_retries=self.max_retries,
                    delay=round(delay, 3),
                    error=str(exc),
                )
                await self._sleep(delay)

    def _backoff_delay(self, attempt: int) -> float:
        """Delay before retry ``attempt`` (1-indexed): base * factor**(n-1) + jitter."""
        base = self.base_backoff_s * (self.backoff_factor ** (attempt - 1))
        return base + self._jitter(self.base_backoff_s)

    async def _ack(self, entry_id: str) -> None:
        await self._client.xack(self.stream, self.group, entry_id)

    async def _to_dlq(
        self, entry_id: str, fields: Mapping[str, str], *, error: str, attempts: int
    ) -> None:
        payload: dict[str, str] = dict(fields)
        payload["error"] = error
        payload["attempts"] = str(attempts)
        payload["origin_stream"] = self.stream
        payload["origin_entry_id"] = entry_id
        await self._client.xadd(self.dlq_stream, payload)  # type: ignore[arg-type]
        logger.warning(
            "worker.dead_lettered",
            worker=type(self).__name__,
            entry_id=entry_id,
            dlq=self.dlq_stream,
            error=error,
        )
