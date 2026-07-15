"""Incident ORM model — promoted from deduplicated documents."""

from __future__ import annotations

from datetime import date
import uuid

from sqlalchemy import Date, ForeignKey, Index, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Incident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_incidents_content_hash"),
        UniqueConstraint("document_id", name="uq_incidents_document_id"),
        Index("ix_incidents_org", "org"),
        Index("ix_incidents_severity", "severity"),
        Index("ix_incidents_occurred_on", "occurred_on"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    org: Mapped[str] = mapped_column(String(256), nullable=False)
    title: Mapped[str] = mapped_column(Text(), nullable=False)
    url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    occurred_on: Mapped[date | None] = mapped_column(Date(), nullable=True)
    severity: Mapped[int | None] = mapped_column(SmallInteger(), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    sections: Mapped[dict[str, object]] = mapped_column(
        JSONB(), nullable=False, default=list, server_default="[]"
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
