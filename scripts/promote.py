"""Promote DEDUPED documents to incidents.

Usage: python -m scripts.promote [--batch-size 200]
"""

from __future__ import annotations

import argparse
import asyncio

from app.core.db import create_engine, create_sessionmaker
from app.core.logging import configure_logging, get_logger
from app.core.settings import get_settings
from app.models.ingest import DocumentStatus
from app.repositories.document import DocumentRepository
from app.repositories.incident import IncidentRepository
from app.services.license_audit import detect_license
from app.services.promoter import build_summary, estimate_severity, extract_date, extract_org

logger = get_logger(__name__)


async def promote(batch_size: int = 200) -> int:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)

    promoted = 0
    try:
        sm = create_sessionmaker(engine)
        async with sm() as session:
            doc_repo = DocumentRepository(session)
            inc_repo = IncidentRepository(session)

            docs = await doc_repo.list_by_status(DocumentStatus.DEDUPED, limit=batch_size)
            for doc in docs:
                existing = await inc_repo.get_by_content_hash(doc.content_hash)
                if existing is not None:
                    logger.info("promote.skip_existing", document_id=str(doc.id))
                    continue

                org = extract_org(doc.url)
                title = doc.title or "Untitled incident"
                severity = estimate_severity(doc.body or "")
                occurred_on = extract_date(doc.title, doc.body)
                summary = build_summary(doc.body)
                sections_raw = doc.doc_metadata.get("sections", []) if doc.doc_metadata else []
                sections = list(sections_raw) if isinstance(sections_raw, list) else []

                license_id = detect_license(doc.body, doc.url)

                await inc_repo.create(
                    document_id=doc.id,
                    org=org,
                    title=title,
                    url=doc.url,
                    occurred_on=occurred_on,
                    severity=severity,
                    summary=summary,
                    sections=sections,
                    content_hash=doc.content_hash,
                    license=license_id,
                )
                promoted += 1

            await session.commit()
            logger.info("promote.done", promoted=promoted, total_docs=len(docs))
    finally:
        await engine.dispose()

    return promoted


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote deduped documents to incidents")
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()
    count = asyncio.run(promote(batch_size=args.batch_size))
    print(f"Promoted {count} documents to incidents.")


if __name__ == "__main__":
    main()
