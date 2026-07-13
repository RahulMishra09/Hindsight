"""API v1 router aggregation. All v1 routers mount under ``/v1``."""

from fastapi import APIRouter

from app.api.v1 import health, ingest

api_router = APIRouter(prefix="/v1")
api_router.include_router(health.router)
api_router.include_router(ingest.router)

__all__ = ["api_router"]
