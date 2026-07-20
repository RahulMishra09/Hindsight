"""CrawlerWorker — fetches raw HTML from discovered URLs."""

from __future__ import annotations

import hashlib
from typing import ClassVar
import uuid

import httpx
import redis.asyncio as redis

from app.core.db import SessionFactory
from app.core.logging import get_logger
from app.events.consumer import BaseWorker
from app.events.publisher import Publisher
from app.events.schemas import DocDiscovered, DocFetched
from app.events.streams import Group, Stream
from app.ingest.politeness import PolitenessLimiter
from app.ingest.robots import RobotsChecker
from app.ingest.ssrf_guard import validate_url
from app.models.ingest import DocumentStatus
from app.repositories.document import DocumentRepository

logger = get_logger(__name__)


class CrawlerWorker(BaseWorker[DocDiscovered]):
    stream: ClassVar[str] = Stream.DOC_DISCOVERED
    group: ClassVar[str] = Group.CRAWLER
    event_model = DocDiscovered

    def __init__(
        self,
        client: redis.Redis,
        *,
        sessionmaker: SessionFactory,
        http_client: httpx.AsyncClient | None = None,
        robots_checker: RobotsChecker | None = None,
        politeness: PolitenessLimiter | None = None,
        user_agent: str = "HindsightBot/0.1",
        timeout: int = 30,
        **kwargs: object,
    ) -> None:
        super().__init__(client, **kwargs)  # type: ignore[arg-type]
        self._sessionmaker = sessionmaker
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.AsyncClient(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
        )
        self._robots = robots_checker or RobotsChecker(self._http_client, user_agent=user_agent)
        self._politeness = politeness or PolitenessLimiter()
        self._publisher = Publisher(client)

    async def handle(self, event: DocDiscovered) -> None:
        url = event.url
        doc_id = event.document_id
        source_id = event.source_id

        await validate_url(url)

        if not await self._robots.is_allowed(url):
            logger.info("crawler.robots_disallowed", url=url)
            async with self._sessionmaker() as session:
                repo = DocumentRepository(session)
                await repo.update_status(
                    uuid.UUID(doc_id),
                    DocumentStatus.FAILED,
                    failed_stage="crawl",
                )
                await session.commit()
            return

        await self._politeness.wait(url)

        headers: dict[str, str] = {}
        async with self._sessionmaker() as session:
            repo = DocumentRepository(session)
            doc = await repo.get_by_id(uuid.UUID(doc_id))
            if doc and doc.doc_metadata:
                etag = doc.doc_metadata.get("etag")
                if isinstance(etag, str):
                    headers["If-None-Match"] = etag
                last_mod = doc.doc_metadata.get("last_modified")
                if isinstance(last_mod, str):
                    headers["If-Modified-Since"] = last_mod

        try:
            resp = await self._http_client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            logger.error("crawler.fetch_failed", url=url, error=str(exc))
            async with self._sessionmaker() as session:
                repo = DocumentRepository(session)
                await repo.update_status(
                    uuid.UUID(doc_id),
                    DocumentStatus.FAILED,
                    failed_stage="crawl",
                )
                await session.commit()
            raise

        if resp.status_code == 304:
            logger.info("crawler.not_modified", url=url)
            return

        resp.raise_for_status()

        raw_html = resp.text
        content_hash = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()

        meta: dict[str, object] = {}
        if "etag" in resp.headers:
            meta["etag"] = resp.headers["etag"]
        if "last-modified" in resp.headers:
            meta["last_modified"] = resp.headers["last-modified"]

        async with self._sessionmaker() as session:
            repo = DocumentRepository(session)
            existing = await repo.get_by_content_hash(content_hash)
            if existing and str(existing.id) != doc_id:
                logger.info("crawler.duplicate_hash", url=url, content_hash=content_hash)
                await repo.update_status(
                    uuid.UUID(doc_id),
                    DocumentStatus.DUPLICATE,
                    doc_metadata={"duplicate_of": str(existing.id)},
                )
                await session.commit()
                return

            await repo.update_status(
                uuid.UUID(doc_id),
                DocumentStatus.FETCHED,
                content_hash=content_hash,
                body=raw_html,
                doc_metadata=meta,
            )
            await session.commit()

        fetched_event = DocFetched(
            source_id=source_id,
            document_id=doc_id,
            content_hash=content_hash,
        )
        await self._publisher.publish(Stream.DOC_FETCHED, fetched_event)
        logger.info("crawler.fetched", url=url, content_hash=content_hash[:12])
