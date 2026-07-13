"""FastAPI dependency-injection factories (SAD §14)."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, Request
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import Settings, get_settings
from app.events.publisher import Publisher
from app.repositories.document import DocumentRepository
from app.repositories.health import HealthRepository
from app.repositories.source import SourceRepository
from app.services.health import HealthService
from app.services.ingest import IngestService


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    return sessionmaker


async def get_db(
    sessionmaker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
) -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker() as session:
        yield session


def get_redis(request: Request) -> redis.Redis:
    client: redis.Redis = request.app.state.redis
    return client


def get_publisher(redis_client: redis.Redis = Depends(get_redis)) -> Publisher:
    return Publisher(redis_client)


def get_source_repository(db: AsyncSession = Depends(get_db)) -> SourceRepository:
    return SourceRepository(db)


def get_document_repository(db: AsyncSession = Depends(get_db)) -> DocumentRepository:
    return DocumentRepository(db)


def get_health_service(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> HealthService:
    from app import __version__

    return HealthService(
        HealthRepository(db),
        redis_client,
        service="hindsight",
        version=__version__,
        env=settings.env,
    )


def get_ingest_service(
    source_repo: SourceRepository = Depends(get_source_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    publisher: Publisher = Depends(get_publisher),
) -> IngestService:
    return IngestService(source_repo, document_repo, publisher)
