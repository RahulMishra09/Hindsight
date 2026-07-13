"""Pydantic request/response schemas for the ingest API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceCreateRequest(BaseModel):
    name: str
    kind: str
    uri: str | None = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    kind: str
    uri: str | None
    active: bool
    created_at: datetime
