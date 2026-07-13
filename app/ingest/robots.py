"""Robots.txt checker with per-domain TTL cache."""

from __future__ import annotations

import time
from typing import Protocol
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


class Clock(Protocol):
    def monotonic(self) -> float: ...


class _DefaultClock:
    def monotonic(self) -> float:
        return time.monotonic()


class RobotsChecker:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        user_agent: str = "HindsightBot/0.1",
        cache_ttl_s: float = 3600.0,
        clock: Clock | None = None,
    ) -> None:
        self._client = client
        self._user_agent = user_agent
        self._cache_ttl_s = cache_ttl_s
        self._cache: dict[str, tuple[RobotFileParser, float]] = {}
        self._clock: Clock = clock or _DefaultClock()

    def _origin(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def _fetch_parser(self, origin: str) -> RobotFileParser:
        rp = RobotFileParser()
        robots_url = f"{origin}/robots.txt"
        try:
            resp = await self._client.get(robots_url, timeout=10, follow_redirects=True)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            else:
                rp.allow_all = True  # type: ignore[attr-defined]
        except httpx.HTTPError:
            rp.allow_all = True  # type: ignore[attr-defined]
        return rp

    async def is_allowed(self, url: str) -> bool:
        origin = self._origin(url)
        now = self._clock.monotonic()

        cached = self._cache.get(origin)
        if cached is not None:
            parser, fetched_at = cached
            if now - fetched_at < self._cache_ttl_s:
                return parser.can_fetch(self._user_agent, url)

        parser = await self._fetch_parser(origin)
        self._cache[origin] = (parser, now)
        return parser.can_fetch(self._user_agent, url)
