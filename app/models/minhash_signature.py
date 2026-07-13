"""MinHash signature storage for near-duplicate detection."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MinHashSignature(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "minhash_signatures"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    num_perm: Mapped[int] = mapped_column(SmallInteger(), nullable=False)
    band_hashes: Mapped[list[str]] = mapped_column(JSONB(), nullable=False)
    hashvalues: Mapped[list[int]] = mapped_column(JSONB(), nullable=False)
    band_size: Mapped[int] = mapped_column(
        SmallInteger(), nullable=False, default=4, server_default="4"
    )
    canonical_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
