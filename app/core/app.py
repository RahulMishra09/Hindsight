"""FastAPI application factory and lifespan (SAD §6.2).

The lifespan owns the process-wide resources — the SQLAlchemy engine/sessionmaker
and the Redis client — creating them on startup and disposing them on shutdown.
They are stashed on ``app.state`` and reached only through ``Depends`` factories,
so there are no module-level connections (architecture rule #4).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.v1 import api_router
from app.core.db import create_engine, create_redis, create_sessionmaker
from app.core.logging import configure_logging, get_logger
from app.core.settings import Settings, get_settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings: Settings = app.state.settings
    configure_logging(settings)

    engine = create_engine(settings)
    app.state.engine = engine
    app.state.sessionmaker = create_sessionmaker(engine)
    app.state.redis = create_redis(settings)
    logger.info("api.startup", env=settings.env, version=__version__)

    try:
        yield
    finally:
        await app.state.redis.aclose()
        await engine.dispose()
        logger.info("api.shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the FastAPI application."""
    settings = settings or get_settings()

    app = FastAPI(
        title="Hindsight API",
        version=__version__,
        docs_url="/v1/docs",
        openapi_url="/v1/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(api_router)
    return app
