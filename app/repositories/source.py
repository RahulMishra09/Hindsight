"""Source repository — async CRUD for the sources table."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingest import Source


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str,
        kind: str,
        uri: str | None = None,
        active: bool = True,
    ) -> Source:
        source = Source(name=name, kind=kind, uri=uri, active=active)
        self._session.add(source)
        await self._session.flush()
        return source

    async def get_by_id(self, source_id: uuid.UUID) -> Source | None:
        return await self._session.get(Source, source_id)

    async def get_by_name(self, name: str) -> Source | None:
        stmt = select(Source).where(Source.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Source]:
        stmt = select(Source).where(Source.active.is_(True)).order_by(Source.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
