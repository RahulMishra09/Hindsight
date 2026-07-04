"""ORM models. Importing this package makes every model visible on ``Base.metadata``.

Alembic imports ``app.models`` so autogenerate sees all tables.
"""

from app.models.base import Base
from app.models.ingest import Document, IngestJob, IngestJobStatus, Source

__all__ = [
    "Base",
    "Document",
    "IngestJob",
    "IngestJobStatus",
    "Source",
]
