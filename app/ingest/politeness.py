"""Per-domain politeness limiter — enforces minimum delay between requests."""

from __future__ import annotations

import asyncio
import time
from typing import Protocol
from urllib.parse import urlparse


class Clock(Protocol):
    def monotonic(self) -> float: ...


class Sleeper(Protocol):
    async def sleep(self, seconds: float) -> None: ...


class _DefaultClock:
    def monotonic(self) -> float:
        return time.monotonic()


class _DefaultSleeper:
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class PolitenessLimiter:
    def __init__(
        self,
        interval_s: float = 2.0,
        *,
        clock: Clock | None = None,
        sleep_fn: Sleeper | None = None,
    ) -> None:
        self._interval_s = interval_s
        self._last_request: dict[str, float] = {}
        self._clock: Clock = clock or _DefaultClock()
        self._sleep: Sleeper = sleep_fn or _DefaultSleeper()
        self._locks: dict[str, asyncio.Lock] = {}

    def _domain(self, url: str) -> str:
        return urlparse(url).netloc

    async def wait(self, url: str) -> None:
        domain = self._domain(url)
        if domain not in self._locks:
            self._locks[domain] = asyncio.Lock()

        async with self._locks[domain]:
            now = self._clock.monotonic()
            last = self._last_request.get(domain, 0.0)
            elapsed = now - last
            if elapsed < self._interval_s:
                await self._sleep.sleep(self._interval_s - elapsed)
            self._last_request[domain] = self._clock.monotonic()
