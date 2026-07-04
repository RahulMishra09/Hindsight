"""FastAPI dependency-injection factories (SAD §14).

The API's lifespan populates ``app.state`` with the shared engine, sessionmaker,
and Redis client. These provider functions expose those handles to routers and
services via ``Depends``. There are no module-level singletons or global
connections (architecture rule #4).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, Request
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import Settings, get_settings
from app.events.publisher import Publisher
from app.repositories.health import HealthRepository
from app.services.health import HealthService


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    """Return the process-wide async session factory from app state."""
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    return sessionmaker


async def get_db(
    sessionmaker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped ``AsyncSession`` that is always closed."""
    async with sessionmaker() as session:
        yield session


def get_redis(request: Request) -> redis.Redis:
    """Return the process-wide Redis client from app state."""
    client: redis.Redis = request.app.state.redis
    return client


def get_publisher(redis_client: redis.Redis = Depends(get_redis)) -> Publisher:
    """Return an event Publisher bound to the shared Redis client."""
    return Publisher(redis_client)


def get_health_service(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> HealthService:
    """Assemble the HealthService from a request-scoped session + Redis client."""
    from app import __version__

    return HealthService(
        HealthRepository(db),
        redis_client,
        service="hindsight",
        version=__version__,
        env=settings.env,
    )
