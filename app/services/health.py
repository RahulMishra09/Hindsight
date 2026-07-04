"""Health service — orchestrates liveness and readiness checks.

Returns data objects only. The router decides HTTP status codes
(architecture rule #1 — no web-framework coupling in services).
"""

from __future__ import annotations

import redis.asyncio as redis

from app.repositories.health import HealthRepository
from app.schemas.health import ComponentStatus, LivenessResponse, ReadinessReport


class HealthService:
    """Business logic for the ``/v1/healthz`` and ``/v1/readyz`` endpoints."""

    def __init__(
        self,
        health_repo: HealthRepository,
        redis_client: redis.Redis,
        *,
        service: str,
        version: str,
        env: str,
    ) -> None:
        self._repo = health_repo
        self._redis = redis_client
        self._service = service
        self._version = version
        self._env = env

    async def liveness(self) -> LivenessResponse:
        """Return process liveness without touching downstream dependencies."""
        return LivenessResponse(service=self._service, version=self._version, env=self._env)

    async def readiness(self) -> ReadinessReport:
        """Probe Postgres and Redis; return report with ready=False if either is down."""
        components = [await self._check_postgres(), await self._check_redis()]
        return ReadinessReport(ready=all(c.ok for c in components), components=components)

    async def _check_postgres(self) -> ComponentStatus:
        try:
            await self._repo.ping()
        except Exception as exc:
            return ComponentStatus(name="postgres", ok=False, detail=str(exc))
        return ComponentStatus(name="postgres", ok=True)

    async def _check_redis(self) -> ComponentStatus:
        try:
            await self._redis.ping()
        except Exception as exc:
            return ComponentStatus(name="redis", ok=False, detail=str(exc))
        return ComponentStatus(name="redis", ok=True)
