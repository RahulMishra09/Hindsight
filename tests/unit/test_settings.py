"""Unit tests for app.core.settings."""

from app.core.settings import Settings


def test_defaults():
    """Settings loads defaults when no env vars are set."""
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
    )
    assert s.env == "development"
    assert "asyncpg" in s.database_url
    assert s.db_pool_size == 10
    assert s.log_level == "INFO"
    assert s.log_format == "text"


def test_override_via_kwargs():
    """Settings can be overridden via constructor kwargs (used in tests)."""
    s = Settings(
        env="production",
        log_level="DEBUG",
        redis_url="redis://custom:6380/1",
        _env_file=None,  # type: ignore[call-arg]
    )
    assert s.env == "production"
    assert s.log_level == "DEBUG"
    assert s.redis_url == "redis://custom:6380/1"


def test_extra_fields_ignored():
    """Settings ignores unknown env vars (extra='ignore')."""
    s = Settings(
        SOME_UNKNOWN_VAR="hello",  # type: ignore[call-arg]
        _env_file=None,  # type: ignore[call-arg]
    )
    assert not hasattr(s, "SOME_UNKNOWN_VAR")
