"""create incidents table

Revision ID: 0003_incidents
Revises: 0002_pipeline
Create Date: 2026-07-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_incidents"
down_revision: str | None = "0002_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("org", sa.String(256), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("occurred_on", sa.Date(), nullable=True),
        sa.Column("severity", sa.SmallInteger(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("sections", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
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
            ["document_id"],
            ["documents.id"],
            name="fk_incidents_document_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash", name="uq_incidents_content_hash"),
        sa.UniqueConstraint("document_id", name="uq_incidents_document_id"),
    )
    op.create_index("ix_incidents_org", "incidents", ["org"])
    op.create_index("ix_incidents_severity", "incidents", ["severity"])
    op.create_index("ix_incidents_occurred_on", "incidents", ["occurred_on"])


def downgrade() -> None:
    op.drop_index("ix_incidents_occurred_on", table_name="incidents")
    op.drop_index("ix_incidents_severity", table_name="incidents")
    op.drop_index("ix_incidents_org", table_name="incidents")
    op.drop_table("incidents")
