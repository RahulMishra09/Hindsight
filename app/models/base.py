"""SQLAlchemy declarative base and shared column mixins.

``Base.metadata`` is the single source of truth imported by ``alembic/env.py``
for autogenerate. Models live under ``app/models/`` and contain mapped columns
only — no business logic, no DB-touching classmethods (SAD §6.3).
"""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class UUIDPrimaryKeyMixin:
    """Adds a server-generated UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` timestamp columns (UTC, server-set)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
