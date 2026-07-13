"""Tests for RobotsChecker."""

from __future__ import annotations

import httpx

from app.ingest.robots import RobotsChecker


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self._now = start

    def monotonic(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class FakeTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses: dict[str, httpx.Response]):
        self._responses = responses

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url in self._responses:
            return self._responses[url]
        return httpx.Response(404)


class TestRobotsChecker:
    async def test_allowed_path(self):
        transport = FakeTransport(
            {
                "https://example.com/robots.txt": httpx.Response(
                    200,
                    text="User-agent: *\nAllow: /\n",
                ),
            }
        )
        client = httpx.AsyncClient(transport=transport)
        checker = RobotsChecker(client, user_agent="TestBot")
        assert await checker.is_allowed("https://example.com/postmortem") is True

    async def test_disallowed_path(self):
        transport = FakeTransport(
            {
                "https://example.com/robots.txt": httpx.Response(
                    200,
                    text="User-agent: *\nDisallow: /private/\n",
                ),
            }
        )
        client = httpx.AsyncClient(transport=transport)
        checker = RobotsChecker(client, user_agent="TestBot")
        assert await checker.is_allowed("https://example.com/private/secret") is False

    async def test_cache_reuses_parsed_result(self):
        call_count = 0

        class CountingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                nonlocal call_count
                call_count += 1
                return httpx.Response(200, text="User-agent: *\nAllow: /\n")

        clock = FakeClock()
        client = httpx.AsyncClient(transport=CountingTransport())
        checker = RobotsChecker(client, user_agent="TestBot", clock=clock)

        await checker.is_allowed("https://example.com/page1")
        await checker.is_allowed("https://example.com/page2")
        assert call_count == 1

    async def test_cache_expires(self):
        call_count = 0

        class CountingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                nonlocal call_count
                call_count += 1
                return httpx.Response(200, text="User-agent: *\nAllow: /\n")

        clock = FakeClock()
        client = httpx.AsyncClient(transport=CountingTransport())
        checker = RobotsChecker(client, user_agent="TestBot", cache_ttl_s=60.0, clock=clock)

        await checker.is_allowed("https://example.com/page1")
        clock.advance(61.0)
        await checker.is_allowed("https://example.com/page2")
        assert call_count == 2

    async def test_missing_robots_allows_all(self):
        transport = FakeTransport({})
        client = httpx.AsyncClient(transport=transport)
        checker = RobotsChecker(client, user_agent="TestBot")
        assert await checker.is_allowed("https://example.com/anything") is True
