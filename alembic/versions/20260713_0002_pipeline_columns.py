"""add pipeline state columns and minhash_signatures table

Revision ID: 0002_pipeline
Revises: 0001_initial
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_pipeline"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("url", sa.Text(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="discovered",
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("failed_stage", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_url", "documents", ["url"])

    op.create_table(
        "minhash_signatures",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("num_perm", sa.SmallInteger(), nullable=False),
        sa.Column(
            "band_hashes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "hashvalues",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("band_size", sa.SmallInteger(), server_default="4", nullable=False),
        sa.Column("canonical_id", sa.String(length=36), nullable=True),
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
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_minhash_signatures_document_id"),
    )


def downgrade() -> None:
    op.drop_table("minhash_signatures")
    op.drop_index("ix_documents_url", table_name="documents")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_column("documents", "failed_stage")
    op.drop_column("documents", "status")
    op.drop_column("documents", "url")
