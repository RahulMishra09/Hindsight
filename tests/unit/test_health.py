"""Unit tests for the health service and repository layers.

Uses fake implementations — no monkeypatch, no mock (rule #5).
"""

from __future__ import annotations

from app.schemas.health import LivenessResponse, ReadinessReport
from app.services.health import HealthService


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class FakeHealthRepository:
    """In-memory health repo that can be told to fail."""

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def ping(self) -> None:
        if self._fail:
            raise ConnectionError("fake db down")


class FakeRedis:
    """Fake Redis with a configurable ping."""

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def ping(self) -> bool:
        if self._fail:
            raise ConnectionError("fake redis down")
        return True


def _make_service(
    db_fail: bool = False,
    redis_fail: bool = False,
) -> HealthService:
    return HealthService(
        health_repo=FakeHealthRepository(fail=db_fail),  # type: ignore[arg-type]
        redis_client=FakeRedis(fail=redis_fail),  # type: ignore[arg-type]
        service="hindsight",
        version="0.1.0",
        env="test",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_liveness_returns_ok():
    svc = _make_service()
    result = await svc.liveness()
    assert isinstance(result, LivenessResponse)
    assert result.status == "ok"
    assert result.service == "hindsight"


async def test_readiness_all_healthy():
    svc = _make_service()
    report = await svc.readiness()
    assert isinstance(report, ReadinessReport)
    assert report.ready is True
    assert all(c.ok for c in report.components)


async def test_readiness_db_down():
    svc = _make_service(db_fail=True)
    report = await svc.readiness()
    assert report.ready is False
    pg = next(c for c in report.components if c.name == "postgres")
    assert pg.ok is False
    assert "fake db down" in (pg.detail or "")


async def test_readiness_redis_down():
    svc = _make_service(redis_fail=True)
    report = await svc.readiness()
    assert report.ready is False
    r = next(c for c in report.components if c.name == "redis")
    assert r.ok is False


async def test_readiness_both_down():
    svc = _make_service(db_fail=True, redis_fail=True)
    report = await svc.readiness()
    assert report.ready is False
    assert sum(1 for c in report.components if not c.ok) == 2
