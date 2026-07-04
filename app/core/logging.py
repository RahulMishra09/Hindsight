"""Structured logging setup.

Configures ``structlog`` to emit either line-delimited JSON (production) or a
human-friendly console format (development), selected by ``LOG_FORMAT``. Stdlib
logging (uvicorn, SQLAlchemy, ...) is routed through the same processor chain so
the whole process emits one consistent log stream.
"""

import logging
import sys

import structlog

from app.core.settings import Settings


def configure_logging(settings: Settings) -> None:
    """Configure structlog + stdlib logging for the current process.

    Idempotent: safe to call once at API startup and once per worker process.
    """
    level = logging.getLevelNamesMapping()[settings.log_level]

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through structlog so third-party libraries share the
    # same output format and level.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
            foreign_pre_chain=shared_processors,
        )
    )
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # uvicorn installs its own handlers; clear them so records propagate to root.
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(noisy)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True


def get_logger(*args: object, **kwargs: object) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(*args, **kwargs)
    return logger
