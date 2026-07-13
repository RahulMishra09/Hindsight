"""Seed loader — discovers postmortem URLs from curated GitHub lists.

Parses danluu/post-mortems and hjacobs/kubernetes-failure-stories READMEs,
extracts URLs, creates sources and documents, and emits DocDiscovered events.

Usage: python -m app.ingest.seed_loader
"""

from __future__ import annotations

import asyncio
import hashlib
import re

import httpx
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.events.publisher import Publisher
from app.events.schemas import DocDiscovered
from app.events.streams import Stream
from app.models.ingest import DocumentStatus
from app.repositories.document import DocumentRepository
from app.repositories.source import SourceRepository

logger = get_logger(__name__)

SEED_SOURCES = [
    {
        "name": "danluu/post-mortems",
        "kind": "github-list",
        "uri": "https://raw.githubusercontent.com/danluu/post-mortems/master/README.md",
    },
    {
        "name": "hjacobs/kubernetes-failure-stories",
        "kind": "github-list",
        "uri": "https://raw.githubusercontent.com/hjacobs/kubernetes-failure-stories/master/README.md",
    },
]

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def extract_urls(markdown: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for _text, url in MARKDOWN_LINK_RE.findall(markdown):
        normalized = url.strip().rstrip("/")
        if normalized not in seen and _is_likely_postmortem_url(normalized):
            seen.add(normalized)
            urls.append(normalized)
    return urls


def _is_likely_postmortem_url(url: str) -> bool:
    skip_patterns = [
        "github.com/danluu",
        "github.com/hjacobs",
        "creativecommons.org",
        "shields.io",
        "badge",
        "#",
    ]
    return not any(p in url for p in skip_patterns)


async def load_seeds(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis_client: redis.Redis,
) -> int:
    publisher = Publisher(redis_client)
    total_discovered = 0

    async with httpx.AsyncClient(timeout=30) as http:
        for seed in SEED_SOURCES:
            logger.info("seed_loader.fetching", source=seed["name"], uri=seed["uri"])
            resp = await http.get(seed["uri"])
            resp.raise_for_status()

            urls = extract_urls(resp.text)
            logger.info("seed_loader.urls_found", source=seed["name"], count=len(urls))

            async with sessionmaker() as session:
                source_repo = SourceRepository(session)
                doc_repo = DocumentRepository(session)

                source = await source_repo.get_by_name(seed["name"])
                if source is None:
                    source = await source_repo.create(
                        name=seed["name"],
                        kind=seed["kind"],
                        uri=seed["uri"],
                    )
                    await session.commit()

                source_id = source.id

                for url in urls:
                    existing = await doc_repo.get_by_url(url)
                    if existing is not None:
                        continue

                    placeholder_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
                    doc = await doc_repo.create(
                        source_id=source_id,
                        content_hash=placeholder_hash,
                        url=url,
                        status=DocumentStatus.DISCOVERED,
                    )
                    await session.commit()

                    event = DocDiscovered(
                        source_id=str(source_id),
                        document_id=str(doc.id),
                        url=url,
                    )
                    await publisher.publish(Stream.DOC_DISCOVERED, event)
                    total_discovered += 1

    logger.info("seed_loader.complete", total_discovered=total_discovered)
    return total_discovered


async def run() -> None:
    from app.core.db import create_engine, create_redis, create_sessionmaker
    from app.core.logging import configure_logging
    from app.core.settings import get_settings

    settings = get_settings()
    configure_logging(settings)

    engine = create_engine(settings)
    sm = create_sessionmaker(engine)
    rc = create_redis(settings)

    try:
        count = await load_seeds(sm, rc)
        logger.info("seed_loader.done", discovered=count)
    finally:
        await engine.dispose()
        await rc.aclose()


def main() -> None:
    asyncio.run(run())
