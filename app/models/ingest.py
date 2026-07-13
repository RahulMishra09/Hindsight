"""Ingestion-domain ORM models: sources, documents, ingest_jobs."""

from __future__ import annotations

from datetime import datetime
import enum
import uuid

from sqlalchemy import (
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IngestJobStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DocumentStatus(enum.StrEnum):
    DISCOVERED = "discovered"
    FETCHED = "fetched"
    PARSED = "parsed"
    DEDUPED = "deduped"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    uri: Mapped[str | None] = mapped_column(Text(), nullable=True)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)

    documents: Mapped[list[Document]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )
    ingest_jobs: Mapped[list[IngestJob]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_documents_content_hash"),
        Index("ix_documents_source_id", "source_id"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_url", "url"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(Text(), nullable=True)
    body: Mapped[str | None] = mapped_column(Text(), nullable=True)
    url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        String(16),
        nullable=False,
        default=DocumentStatus.DISCOVERED,
        server_default=DocumentStatus.DISCOVERED.value,
    )
    failed_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    doc_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB(), nullable=False, default=dict, server_default="{}"
    )

    source: Mapped[Source] = relationship(back_populates="documents")


class IngestJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ingest_jobs"
    __table_args__ = (Index("ix_ingest_jobs_source_id_status", "source_id", "status"),)

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[IngestJobStatus] = mapped_column(
        String(16),
        nullable=False,
        default=IngestJobStatus.PENDING,
        server_default=IngestJobStatus.PENDING.value,
    )
    attempts: Mapped[int] = mapped_column(SmallInteger(), nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    source: Mapped[Source] = relationship(back_populates="ingest_jobs")
