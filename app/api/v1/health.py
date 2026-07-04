"""Health routers: liveness (``/v1/healthz``) and readiness (``/v1/readyz``).

Routers contain zero business logic (architecture rule #1): each handler calls
exactly one service method. The readiness router translates ``ready=False`` into
a 503 status — this is HTTP-layer concern, not business logic.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.dependencies import get_health_service
from app.schemas.health import LivenessResponse, ReadinessReport
from app.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=LivenessResponse)
async def healthz(service: HealthService = Depends(get_health_service)) -> LivenessResponse:
    """Liveness probe: the process is up. Does not touch downstream dependencies."""
    return await service.liveness()


@router.get("/readyz", response_model=ReadinessReport)
async def readyz(
    service: HealthService = Depends(get_health_service),
) -> ReadinessReport | JSONResponse:
    """Readiness probe: Postgres and Redis are reachable (else 503)."""
    report = await service.readiness()
    if not report.ready:
        return JSONResponse(status_code=503, content=report.model_dump())
    return report
