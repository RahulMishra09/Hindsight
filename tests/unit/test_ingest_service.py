"""Tests for IngestService."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import uuid

import pytest

from app.events.schemas import DocDiscovered
from app.models.ingest import DocumentStatus
from app.services.ingest import DuplicateSourceError, IngestService


@dataclass
class FakeSource:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    name: str = ""
    kind: str = ""
    uri: str | None = None
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass
class FakeDocument:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    source_id: uuid.UUID = field(default_factory=uuid.uuid4)
    content_hash: str = ""
    url: str | None = None
    title: str | None = None
    body: str | None = None
    status: DocumentStatus = DocumentStatus.DISCOVERED
    doc_metadata: dict = field(default_factory=dict)


class FakeSourceRepository:
    def __init__(self):
        self._sources: dict[str, FakeSource] = {}

    async def get_by_name(self, name: str) -> FakeSource | None:
        return self._sources.get(name)

    async def create(self, *, name: str, kind: str, uri: str | None = None, active: bool = True):
        source = FakeSource(name=name, kind=kind, uri=uri, active=active)
        self._sources[name] = source
        return source


class FakeDocumentRepository:
    def __init__(self):
        self._docs: dict[str, FakeDocument] = {}

    async def get_by_url(self, url: str) -> FakeDocument | None:
        for doc in self._docs.values():
            if doc.url == url:
                return doc
        return None

    async def create(
        self,
        *,
        source_id,
        content_hash,
        url=None,
        status=DocumentStatus.DISCOVERED,
        title=None,
        body=None,
        doc_metadata=None,
    ):
        doc = FakeDocument(
            source_id=source_id,
            content_hash=content_hash,
            url=url,
            status=status,
            title=title,
            body=body,
            doc_metadata=doc_metadata or {},
        )
        self._docs[str(doc.id)] = doc
        return doc


class FakePublisher:
    def __init__(self):
        self.published: list[tuple[str, object]] = []

    async def publish(self, stream: str, event: object) -> str:
        self.published.append((stream, event))
        return "fake-entry-id"


class TestIngestService:
    async def test_create_source_success(self):
        service = IngestService(FakeSourceRepository(), FakeDocumentRepository(), FakePublisher())
        source = await service.create_source(
            name="test", kind="github-list", uri="https://example.com"
        )
        assert source.name == "test"
        assert source.kind == "github-list"

    async def test_create_duplicate_source_raises(self):
        service = IngestService(FakeSourceRepository(), FakeDocumentRepository(), FakePublisher())
        await service.create_source(name="test", kind="github-list")
        with pytest.raises(DuplicateSourceError):
            await service.create_source(name="test", kind="github-list")

    async def test_discover_url_creates_doc_and_emits_event(self):
        publisher = FakePublisher()
        service = IngestService(FakeSourceRepository(), FakeDocumentRepository(), publisher)
        source = await service.create_source(name="test", kind="github-list")
        doc = await service.discover_url(source_id=source.id, url="https://example.com/pm")

        assert doc.url == "https://example.com/pm"
        assert doc.status == DocumentStatus.DISCOVERED
        assert len(publisher.published) == 1

        stream, event = publisher.published[0]
        assert stream == "hindsight:doc.discovered"
        assert isinstance(event, DocDiscovered)
        assert event.url == "https://example.com/pm"

    async def test_discover_url_deduplicates(self):
        publisher = FakePublisher()
        service = IngestService(FakeSourceRepository(), FakeDocumentRepository(), publisher)
        source = await service.create_source(name="test", kind="github-list")
        doc1 = await service.discover_url(source_id=source.id, url="https://example.com/pm")
        doc2 = await service.discover_url(source_id=source.id, url="https://example.com/pm")

        assert doc1.id == doc2.id
        assert len(publisher.published) == 1
