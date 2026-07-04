"""Response schemas for the health endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    """Process is up and serving. Never touches downstream dependencies."""

    status: Literal["ok"] = "ok"
    service: str
    version: str
    env: str


class ComponentStatus(BaseModel):
    """Readiness of a single downstream dependency."""

    name: str
    ok: bool
    detail: str | None = None


class ReadinessReport(BaseModel):
    """Aggregate readiness across all downstream dependencies."""

    ready: bool
    components: list[ComponentStatus]
