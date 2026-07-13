"""Document repository — async CRUD for the documents table."""

from __future__ import annotations

from collections.abc import Sequence
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingest import Document, DocumentStatus


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        source_id: uuid.UUID,
        content_hash: str,
        url: str | None = None,
        title: str | None = None,
        body: str | None = None,
        status: DocumentStatus = DocumentStatus.DISCOVERED,
        doc_metadata: dict[str, object] | None = None,
    ) -> Document:
        doc = Document(
            source_id=source_id,
            content_hash=content_hash,
            url=url,
            title=title,
            body=body,
            status=status,
            doc_metadata=doc_metadata or {},
        )
        self._session.add(doc)
        await self._session.flush()
        return doc

    async def get_by_id(self, doc_id: uuid.UUID) -> Document | None:
        return await self._session.get(Document, doc_id)

    async def get_by_content_hash(self, content_hash: str) -> Document | None:
        stmt = select(Document).where(Document.content_hash == content_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> Document | None:
        stmt = select(Document).where(Document.url == url)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        doc_id: uuid.UUID,
        status: DocumentStatus,
        *,
        failed_stage: str | None = None,
        title: str | None = None,
        body: str | None = None,
        content_hash: str | None = None,
        doc_metadata: dict[str, object] | None = None,
    ) -> Document | None:
        doc = await self.get_by_id(doc_id)
        if doc is None:
            return None
        doc.status = status
        if failed_stage is not None:
            doc.failed_stage = failed_stage
        if title is not None:
            doc.title = title
        if body is not None:
            doc.body = body
        if content_hash is not None:
            doc.content_hash = content_hash
        if doc_metadata is not None:
            doc.doc_metadata = doc_metadata
        await self._session.flush()
        return doc

    async def list_by_status(
        self, status: DocumentStatus, *, limit: int = 100
    ) -> Sequence[Document]:
        stmt = (
            select(Document)
            .where(Document.status == status)
            .order_by(Document.created_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_by_status(self) -> dict[str, int]:
        stmt = select(Document.status, func.count()).group_by(Document.status)
        result = await self._session.execute(stmt)
        return {str(row[0]): int(row[1]) for row in result.all()}
