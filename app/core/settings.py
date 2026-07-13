"""Application configuration.

Single source of truth for all runtime configuration (SAD §12). Every field maps
1:1 to an environment variable enumerated in ``.env.example`` and is loaded via
``pydantic-settings``. No YAML, no scattered ``os.getenv`` calls.

Only the infrastructure settings needed by the Week 1 chassis are declared here.
Extra environment variables (JWT, ML, W&B, ... — reserved for later weeks) are
ignored rather than rejected, so a fuller ``.env`` still validates.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings sourced from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- Application -------------------------------------------------------
    env: Literal["development", "staging", "production"] = "development"

    # -- PostgreSQL --------------------------------------------------------
    # Async DSN used by the API and workers (SQLAlchemy + asyncpg).
    database_url: str = Field(
        default="postgresql+asyncpg://hindsight:hindsight@localhost:5432/hindsight",
    )
    # Sync DSN used by Alembic migrations (psycopg).
    database_url_sync: str = Field(
        default="postgresql+psycopg://hindsight:hindsight@localhost:5432/hindsight",
    )
    db_pool_size: int = 10
    db_pool_max_overflow: int = 20

    # -- Redis Streams -----------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    # Consumer id prefix; the worker appends its PID for per-process uniqueness.
    redis_consumer_prefix: str = "hindsight"

    # -- Crawler -----------------------------------------------------------
    crawler_politeness_interval: float = 2.0
    crawler_timeout: int = 30
    crawler_user_agent: str = "HindsightBot/0.1"
    crawler_max_concurrency: int = 20

    # -- Deduper -----------------------------------------------------------
    dedup_jaccard_threshold: float = 0.85
    dedup_num_perm: int = 128
    dedup_band_size: int = 4

    # -- Observability -----------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "text"


@lru_cache
def get_settings() -> Settings:
    """Return a process-cached :class:`Settings` instance.

    Cached so configuration is parsed once per process. Tests override
    configuration by clearing this cache or injecting a ``Settings`` instance
    directly into factories / FastAPI ``dependency_overrides``.
    """
    return Settings()
