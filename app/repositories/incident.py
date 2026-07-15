"""Incident repository — async CRUD for the incidents table."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident


class IncidentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        document_id: uuid.UUID,
        org: str,
        title: str,
        url: str | None = None,
        occurred_on: date | None = None,
        severity: int | None = None,
        summary: str | None = None,
        sections: list[str] | None = None,
        content_hash: str,
        license: str = "all-rights-reserved",
    ) -> Incident:
        incident = Incident(
            document_id=document_id,
            org=org,
            title=title,
            url=url,
            occurred_on=occurred_on,
            severity=severity,
            summary=summary,
            sections=sections or [],
            content_hash=content_hash,
            license=license,
        )
        self._session.add(incident)
        await self._session.flush()
        return incident

    async def get_by_id(self, incident_id: uuid.UUID) -> Incident | None:
        return await self._session.get(Incident, incident_id)

    async def get_by_document_id(self, document_id: uuid.UUID) -> Incident | None:
        stmt = select(Incident).where(Incident.document_id == document_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_content_hash(self, content_hash: str) -> Incident | None:
        stmt = select(Incident).where(Incident.content_hash == content_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, *, limit: int = 200, offset: int = 0) -> Sequence[Incident]:
        stmt = select(Incident).order_by(Incident.created_at).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        stmt = select(func.count()).select_from(Incident)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
