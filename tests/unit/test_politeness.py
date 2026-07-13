"""Tests for PolitenessLimiter."""

from __future__ import annotations

from app.ingest.politeness import PolitenessLimiter


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self._now = start

    def monotonic(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class FakeSleeper:
    def __init__(self, clock: FakeClock):
        self._clock = clock
        self.calls: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.calls.append(seconds)
        self._clock.advance(seconds)


class TestPolitenessLimiter:
    async def test_first_request_no_wait(self):
        clock = FakeClock()
        sleeper = FakeSleeper(clock)
        limiter = PolitenessLimiter(interval_s=2.0, clock=clock, sleep_fn=sleeper)

        await limiter.wait("https://example.com/page1")
        assert sleeper.calls == []

    async def test_second_request_within_interval_waits(self):
        clock = FakeClock()
        sleeper = FakeSleeper(clock)
        limiter = PolitenessLimiter(interval_s=2.0, clock=clock, sleep_fn=sleeper)

        await limiter.wait("https://example.com/page1")
        clock.advance(0.5)
        await limiter.wait("https://example.com/page2")
        assert len(sleeper.calls) == 1
        assert abs(sleeper.calls[0] - 1.5) < 0.01

    async def test_different_domains_independent(self):
        clock = FakeClock()
        sleeper = FakeSleeper(clock)
        limiter = PolitenessLimiter(interval_s=2.0, clock=clock, sleep_fn=sleeper)

        await limiter.wait("https://example.com/page1")
        await limiter.wait("https://other.com/page1")
        assert sleeper.calls == []

    async def test_request_after_interval_no_wait(self):
        clock = FakeClock()
        sleeper = FakeSleeper(clock)
        limiter = PolitenessLimiter(interval_s=2.0, clock=clock, sleep_fn=sleeper)

        await limiter.wait("https://example.com/page1")
        clock.advance(2.5)
        await limiter.wait("https://example.com/page2")
        assert sleeper.calls == []
