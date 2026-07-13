"""ParserWorker — extracts clean text from raw HTML."""

from __future__ import annotations

import hashlib
import re
from typing import ClassVar
import unicodedata
import uuid

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.events.consumer import BaseWorker
from app.events.publisher import Publisher
from app.events.schemas import DocFetched, DocParsed
from app.events.streams import Group, Stream
from app.models.ingest import DocumentStatus
from app.repositories.document import DocumentRepository

logger = get_logger(__name__)

SECTION_PATTERNS = [
    re.compile(r"(?i)\b(impact|blast radius)\b"),
    re.compile(r"(?i)\b(timeline|chronology)\b"),
    re.compile(r"(?i)\b(root\s*cause|cause)\b"),
    re.compile(r"(?i)\b(lessons?\s*learned|takeaways?|action\s*items?)\b"),
    re.compile(r"(?i)\b(mitigation|remediation|resolution|recovery)\b"),
    re.compile(r"(?i)\b(detection|monitoring|alerting)\b"),
    re.compile(r"(?i)\b(prevention|follow[\s-]*up)\b"),
    re.compile(r"(?i)\b(summary|overview|abstract|background)\b"),
]

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def _extract_content(html: str) -> tuple[str | None, str | None]:
    import trafilatura

    result = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        output_format="txt",
    )
    if result:
        return _extract_title_from_html(html), result

    try:
        from readability import Document as ReadabilityDoc

        rdoc = ReadabilityDoc(html)
        title = rdoc.short_title()
        content = trafilatura.extract(
            rdoc.summary(),
            include_comments=False,
            include_tables=True,
            output_format="txt",
        )
        if content:
            return title or None, content
    except Exception:  # noqa: S110
        pass

    return None, None


def _extract_title_from_html(html: str) -> str | None:
    import re as _re

    match = _re.search(r"<title[^>]*>([^<]+)</title>", html, _re.IGNORECASE)
    return match.group(1).strip() if match else None


def _normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _detect_language(text: str) -> str:
    ascii_chars = sum(1 for c in text[:2000] if c.isascii() and c.isalpha())
    alpha_chars = sum(1 for c in text[:2000] if c.isalpha())
    if alpha_chars == 0:
        return "unknown"
    ratio = ascii_chars / alpha_chars
    return "en" if ratio > 0.8 else "non-en"


def _detect_sections(text: str) -> list[str]:
    found: list[str] = []
    for pattern in SECTION_PATTERNS:
        if pattern.search(text):
            match = pattern.search(text)
            if match:
                found.append(match.group(1).lower().strip())
    return found


class ParserWorker(BaseWorker[DocFetched]):
    stream: ClassVar[str] = Stream.DOC_FETCHED
    group: ClassVar[str] = Group.PARSER
    event_model = DocFetched

    def __init__(
        self,
        client: redis.Redis,
        *,
        sessionmaker: async_sessionmaker[AsyncSession],
        **kwargs: object,
    ) -> None:
        super().__init__(client, **kwargs)  # type: ignore[arg-type]
        self._sessionmaker = sessionmaker
        self._publisher = Publisher(client)

    async def handle(self, event: DocFetched) -> None:
        doc_id = event.document_id
        source_id = event.source_id

        async with self._sessionmaker() as session:
            repo = DocumentRepository(session)
            doc = await repo.get_by_id(uuid.UUID(doc_id))
            if doc is None:
                logger.error("parser.doc_not_found", document_id=doc_id)
                return

            if doc.status == DocumentStatus.PARSED:
                logger.info("parser.already_parsed", document_id=doc_id)
                return

            raw_html = doc.body
            if not raw_html:
                logger.error("parser.no_body", document_id=doc_id)
                await repo.update_status(
                    uuid.UUID(doc_id),
                    DocumentStatus.FAILED,
                    failed_stage="parse",
                )
                await session.commit()
                return

            title, content = _extract_content(raw_html)
            if not content:
                logger.warning("parser.extraction_failed", document_id=doc_id)
                await repo.update_status(
                    uuid.UUID(doc_id),
                    DocumentStatus.FAILED,
                    failed_stage="parse",
                )
                await session.commit()
                return

            content = _normalize_text(content)
            lang = _detect_language(content)
            if lang != "en":
                logger.info("parser.non_english", document_id=doc_id, lang=lang)
                await repo.update_status(
                    uuid.UUID(doc_id),
                    DocumentStatus.FAILED,
                    failed_stage="parse",
                    doc_metadata={"rejected_reason": "non_english", "detected_lang": lang},
                )
                await session.commit()
                return

            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            sections = _detect_sections(content)

            meta: dict[str, object] = dict(doc.doc_metadata) if doc.doc_metadata else {}
            meta["sections"] = sections
            if title:
                meta["parsed_title"] = title

            await repo.update_status(
                uuid.UUID(doc_id),
                DocumentStatus.PARSED,
                title=title or doc.title,
                body=content,
                content_hash=content_hash,
                doc_metadata=meta,
            )
            await session.commit()

        parsed_event = DocParsed(
            source_id=source_id,
            document_id=doc_id,
            content_hash=content_hash,
        )
        await self._publisher.publish(Stream.DOC_PARSED, parsed_event)
        logger.info(
            "parser.parsed",
            document_id=doc_id,
            content_hash=content_hash[:12],
            sections=sections,
        )
