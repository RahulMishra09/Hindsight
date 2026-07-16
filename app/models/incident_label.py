"""IncidentLabel ORM model — multi-label taxonomy labels for incidents."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Index, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

TAXONOMY_LABELS: tuple[str, ...] = (
    "config-change",
    "retry-storm",
    "cascading-failure",
    "dns",
    "certificate-expiry",
    "capacity-exhaustion",
    "bad-deploy",
    "dependency-failure",
    "network-partition",
    "database-failure",
    "thundering-herd",
    "monitoring-gap",
    "human-error",
    "data-corruption",
    "quota-limit",
)


class IncidentLabel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "incident_labels"
    __table_args__ = (
        UniqueConstraint(
            "incident_id",
            "label",
            "annotator_id",
            name="uq_incident_labels_incident_label_annotator",
        ),
        Index("ix_incident_labels_incident_id", "incident_id"),
        Index("ix_incident_labels_label", "label"),
        Index("ix_incident_labels_source", "source"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float(), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    annotator_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="system",
        server_default="system",
    )
    annotation_round: Mapped[int | None] = mapped_column(SmallInteger(), nullable=True)
