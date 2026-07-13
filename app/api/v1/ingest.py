"""Ingest admin endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_ingest_service
from app.schemas.ingest import SourceCreateRequest, SourceResponse
from app.services.ingest import DuplicateSourceError, IngestService

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/sources", response_model=SourceResponse, status_code=201)
async def create_source(
    payload: SourceCreateRequest,
    service: IngestService = Depends(get_ingest_service),
) -> SourceResponse:
    try:
        source = await service.create_source(name=payload.name, kind=payload.kind, uri=payload.uri)
    except DuplicateSourceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SourceResponse(
        id=str(source.id),
        name=source.name,
        kind=source.kind,
        uri=source.uri,
        active=source.active,
        created_at=source.created_at,
    )
