"""Database and Redis connection factories.

These are *factory functions* only — no connections are opened at import time
(architecture rule #4). The API creates these during its lifespan and stores the
handles on ``app.state``; workers create them in their process ``main``. Both
dispose of them on shutdown.
"""

from __future__ import annotations

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create an async SQLAlchemy engine from settings."""
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_max_overflow,
        pool_pre_ping=True,
        future=True,
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to ``engine``."""
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )


def create_redis(settings: Settings) -> redis.Redis:
    """Create an async Redis client from settings.

    ``decode_responses=True`` so stream payloads come back as ``str`` rather than
    ``bytes``, keeping event (de)serialization simple.
    """
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        health_check_interval=30,
    )
