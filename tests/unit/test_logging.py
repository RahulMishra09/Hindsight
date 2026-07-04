"""Unit tests for app.core.logging."""

from app.core.logging import configure_logging, get_logger
from app.core.settings import Settings


def test_configure_logging_idempotent():
    """configure_logging can be called twice without error."""
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    configure_logging(s)
    configure_logging(s)  # second call should not raise


def test_get_logger_returns_bound_logger():
    """get_logger returns a structlog logger instance."""
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    configure_logging(s)
    log = get_logger("test")
    assert log is not None
    # Should have standard logging methods
    assert callable(getattr(log, "info", None))
    assert callable(getattr(log, "warning", None))
    assert callable(getattr(log, "error", None))
