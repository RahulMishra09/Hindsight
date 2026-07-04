"""Unit tests for app.models — verify ORM model definitions."""

from app.models.base import Base
from app.models.ingest import Document, IngestJobStatus, Source


def test_all_models_registered_on_base():
    """All table models appear in Base.metadata."""
    table_names = set(Base.metadata.tables.keys())
    assert "sources" in table_names
    assert "documents" in table_names
    assert "ingest_jobs" in table_names


def test_document_has_content_hash_column():
    """Document model defines the content_hash idempotency key."""
    col = Document.__table__.columns["content_hash"]
    assert not col.nullable
    assert col.type.length == 64  # type: ignore[union-attr]


def test_ingest_job_status_values():
    """IngestJobStatus enum has the expected members."""
    assert IngestJobStatus.PENDING == "pending"
    assert IngestJobStatus.RUNNING == "running"
    assert IngestJobStatus.SUCCEEDED == "succeeded"
    assert IngestJobStatus.FAILED == "failed"


def test_source_has_unique_name():
    """Source.name has a unique constraint."""
    col = Source.__table__.columns["name"]
    assert col.unique


def test_document_content_hash_unique_constraint():
    """Document table has a unique constraint on content_hash."""
    constraints = [c.name for c in Document.__table__.constraints if hasattr(c, "name")]
    assert "uq_documents_content_hash" in constraints
