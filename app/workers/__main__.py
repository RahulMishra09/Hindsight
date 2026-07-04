"""Worker process entrypoint: ``python -m app.workers``.

Boots a single worker (the Week 1 skeleton runs :class:`EchoWorker`), wiring it
to Redis and installing signal handlers for graceful shutdown. Later weeks select
the worker class via an argument / env var; for now there is exactly one.
"""

from __future__ import annotations

import asyncio
import signal

from app.core.db import create_redis
from app.core.logging import configure_logging, get_logger
from app.core.settings import get_settings
from app.workers.echo import EchoWorker

logger = get_logger(__name__)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings)

    client = create_redis(settings)
    worker = EchoWorker(
        client,
        consumer_prefix=settings.redis_consumer_prefix,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.stop)

    logger.info("worker.boot", env=settings.env, worker=type(worker).__name__)
    try:
        await worker.run()
    finally:
        await client.aclose()
        logger.info("worker.shutdown_complete")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
