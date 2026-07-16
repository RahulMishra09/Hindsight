"""create incident_labels table

Revision ID: 0004_incident_labels
Revises: 0003_incidents
Create Date: 2026-07-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_incident_labels"
down_revision: str | None = "0003_incidents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incident_labels",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("annotator_id", sa.String(64), nullable=False, server_default="system"),
        sa.Column("annotation_round", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name="fk_incident_labels_incident_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "incident_id",
            "label",
            "annotator_id",
            name="uq_incident_labels_incident_label_annotator",
        ),
    )
    op.create_index("ix_incident_labels_incident_id", "incident_labels", ["incident_id"])
    op.create_index("ix_incident_labels_label", "incident_labels", ["label"])
    op.create_index("ix_incident_labels_source", "incident_labels", ["source"])


def downgrade() -> None:
    op.drop_index("ix_incident_labels_source", table_name="incident_labels")
    op.drop_index("ix_incident_labels_label", table_name="incident_labels")
    op.drop_index("ix_incident_labels_incident_id", table_name="incident_labels")
    op.drop_table("incident_labels")
