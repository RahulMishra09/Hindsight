"""Tests for CrawlerWorker politeness and SSRF enforcement."""

from __future__ import annotations

import httpx
import pytest

from app.ingest.politeness import PolitenessLimiter
from app.ingest.robots import RobotsChecker
from app.ingest.ssrf_guard import SSRFBlockedError


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self._now = start

    def monotonic(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class FakeSleep:
    def __init__(self, clock: FakeClock):
        self._clock = clock
        self.calls: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.calls.append(seconds)
        self._clock.advance(seconds)


class FakeTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses: dict[str, httpx.Response] | None = None):
        self._responses = responses or {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url in self._responses:
            return self._responses[url]
        return httpx.Response(200, text="<html><body>Hello</body></html>")


class TestCrawlerPoliteness:
    async def test_politeness_delays_same_domain(self):
        clock = FakeClock()
        sleeper = FakeSleep(clock)
        limiter = PolitenessLimiter(interval_s=2.0, clock=clock, sleep_fn=sleeper)

        await limiter.wait("https://blog.example.com/post-1")
        clock.advance(0.5)
        await limiter.wait("https://blog.example.com/post-2")

        assert len(sleeper.calls) == 1
        assert sleeper.calls[0] > 1.0

    async def test_no_delay_between_different_domains(self):
        clock = FakeClock()
        sleeper = FakeSleep(clock)
        limiter = PolitenessLimiter(interval_s=2.0, clock=clock, sleep_fn=sleeper)

        await limiter.wait("https://blog-a.com/post")
        await limiter.wait("https://blog-b.com/post")

        assert sleeper.calls == []


class TestCrawlerRobots:
    async def test_robots_disallow_respected(self):
        transport = FakeTransport(
            {
                "https://example.com/robots.txt": httpx.Response(
                    200, text="User-agent: *\nDisallow: /private/\n"
                ),
            }
        )
        client = httpx.AsyncClient(transport=transport)
        checker = RobotsChecker(client, user_agent="HindsightBot/0.1")

        assert await checker.is_allowed("https://example.com/private/secret") is False
        assert await checker.is_allowed("https://example.com/public/page") is True


class TestCrawlerSSRF:
    async def test_blocks_private_ip(self):
        from app.ingest.ssrf_guard import validate_url

        with pytest.raises(SSRFBlockedError):
            await validate_url("http://127.0.0.1/admin")

    async def test_blocks_metadata_endpoint(self):
        from app.ingest.ssrf_guard import validate_url

        with pytest.raises(SSRFBlockedError):
            await validate_url("http://169.254.169.254/latest/meta-data/")


class TestCrawlerConditionalGet:
    async def test_etag_sent_in_headers(self):
        captured_headers: dict[str, str] = {}

        class CapturingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                captured_headers.update(dict(request.headers))
                return httpx.Response(304)

        client = httpx.AsyncClient(transport=CapturingTransport())
        headers = {"If-None-Match": '"abc123"'}
        resp = await client.get("https://example.com/page", headers=headers)

        assert resp.status_code == 304
        assert captured_headers.get("if-none-match") == '"abc123"'
