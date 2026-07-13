"""Ingest service — orchestrates source creation and event emission."""

from __future__ import annotations

import hashlib
import uuid

from app.events.publisher import Publisher
from app.events.schemas import DocDiscovered
from app.events.streams import Stream
from app.models.ingest import Document, DocumentStatus, Source
from app.repositories.document import DocumentRepository
from app.repositories.source import SourceRepository


class DuplicateSourceError(Exception):
    pass


class IngestService:
    def __init__(
        self,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        publisher: Publisher,
    ) -> None:
        self._source_repo = source_repo
        self._document_repo = document_repo
        self._publisher = publisher

    async def create_source(self, *, name: str, kind: str, uri: str | None = None) -> Source:
        existing = await self._source_repo.get_by_name(name)
        if existing is not None:
            raise DuplicateSourceError(f"Source '{name}' already exists")
        return await self._source_repo.create(name=name, kind=kind, uri=uri)

    async def discover_url(self, *, source_id: uuid.UUID, url: str) -> Document:
        existing = await self._document_repo.get_by_url(url)
        if existing is not None:
            return existing

        placeholder_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        doc = await self._document_repo.create(
            source_id=source_id,
            content_hash=placeholder_hash,
            url=url,
            status=DocumentStatus.DISCOVERED,
        )

        event = DocDiscovered(
            source_id=str(source_id),
            document_id=str(doc.id),
            url=url,
        )
        await self._publisher.publish(Stream.DOC_DISCOVERED, event)
        return doc
