"""Worker process entrypoint: ``python -m app.workers [worker_type]``."""

from __future__ import annotations

import argparse
import asyncio
import signal
from typing import Any

from app.core.db import create_engine, create_redis, create_sessionmaker
from app.core.logging import configure_logging, get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

WORKER_TYPES = ("echo", "crawler", "parser", "deduper", "classifier")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run a Hindsight pipeline worker")
    p.add_argument(
        "worker",
        choices=WORKER_TYPES,
        nargs="?",
        default="echo",
        help="Worker type to run (default: echo)",
    )
    return p


async def run() -> None:
    args = _build_parser().parse_args()
    settings = get_settings()
    configure_logging(settings)

    redis_client = create_redis(settings)
    engine = None
    worker: Any = None

    if args.worker == "echo":
        from app.workers.echo import EchoWorker

        worker = EchoWorker(
            redis_client,
            consumer_prefix=settings.redis_consumer_prefix,
        )
    elif args.worker == "crawler":
        engine = create_engine(settings)
        sm = create_sessionmaker(engine)
        from app.workers.crawler import CrawlerWorker

        worker = CrawlerWorker(
            redis_client,
            sessionmaker=sm,
            user_agent=settings.crawler_user_agent,
            timeout=settings.crawler_timeout,
            consumer_prefix=settings.redis_consumer_prefix,
        )
    elif args.worker == "parser":
        engine = create_engine(settings)
        sm = create_sessionmaker(engine)
        from app.workers.parser import ParserWorker

        worker = ParserWorker(
            redis_client,
            sessionmaker=sm,
            consumer_prefix=settings.redis_consumer_prefix,
        )
    elif args.worker == "deduper":
        engine = create_engine(settings)
        sm = create_sessionmaker(engine)
        from app.workers.deduper import DeduperWorker

        worker = DeduperWorker(
            redis_client,
            sessionmaker=sm,
            num_perm=settings.dedup_num_perm,
            band_size=settings.dedup_band_size,
            jaccard_threshold=settings.dedup_jaccard_threshold,
            consumer_prefix=settings.redis_consumer_prefix,
        )

    elif args.worker == "classifier":
        engine = create_engine(settings)
        sm = create_sessionmaker(engine)
        from pathlib import Path

        from app.workers.classifier import ClassifierWorker

        worker = ClassifierWorker(
            redis_client,
            sessionmaker=sm,
            model_dir=Path(settings.classifier_model_dir),
            max_length=settings.classifier_max_length,
            consumer_prefix=settings.redis_consumer_prefix,
        )

    assert worker is not None, f"Unknown worker type: {args.worker}"

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.stop)

    logger.info("worker.boot", env=settings.env, worker=type(worker).__name__)
    try:
        await worker.run()
    finally:
        await redis_client.aclose()
        if engine is not None:
            await engine.dispose()
        logger.info("worker.shutdown_complete")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
