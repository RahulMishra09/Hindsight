"""DeduperWorker — near-duplicate detection via MinHash LSH."""

from __future__ import annotations

import hashlib
from typing import ClassVar
import uuid

import redis.asyncio as redis

from app.core.db import SessionFactory
from app.core.logging import get_logger
from app.events.consumer import BaseWorker
from app.events.publisher import Publisher
from app.events.schemas import DocDeduped, DocParsed
from app.events.streams import Group, Stream
from app.models.ingest import DocumentStatus
from app.repositories.document import DocumentRepository
from app.repositories.minhash import MinHashRepository

logger = get_logger(__name__)


def _shingle(text: str, k: int = 5) -> set[str]:
    words = text.lower().split()
    if len(words) < k:
        return {" ".join(words)}
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def _compute_minhash(shingles: set[str], num_perm: int = 128) -> list[int]:
    from datasketch import MinHash

    m = MinHash(num_perm=num_perm)
    for s in shingles:
        m.update(s.encode("utf-8"))
    return m.hashvalues.tolist()  # type: ignore[no-any-return]


def _compute_band_hashes(hashvalues: list[int], band_size: int = 4) -> list[str]:
    bands: list[str] = []
    for i in range(0, len(hashvalues), band_size):
        band = hashvalues[i : i + band_size]
        h = hashlib.md5(str(band).encode()).hexdigest()  # noqa: S324
        bands.append(f"b{i // band_size}:{h}")
    return bands


def _jaccard_from_hashvalues(h1: list[int], h2: list[int]) -> float:
    if len(h1) != len(h2):
        return 0.0
    equal = sum(1 for a, b in zip(h1, h2, strict=True) if a == b)
    return equal / len(h1)


class DeduperWorker(BaseWorker[DocParsed]):
    stream: ClassVar[str] = Stream.DOC_PARSED
    group: ClassVar[str] = Group.DEDUPER
    event_model = DocParsed

    def __init__(
        self,
        client: redis.Redis,
        *,
        sessionmaker: SessionFactory,
        num_perm: int = 128,
        band_size: int = 4,
        jaccard_threshold: float = 0.85,
        **kwargs: object,
    ) -> None:
        super().__init__(client, **kwargs)  # type: ignore[arg-type]
        self._sessionmaker = sessionmaker
        self._publisher = Publisher(client)
        self._num_perm = num_perm
        self._band_size = band_size
        self._jaccard_threshold = jaccard_threshold

    async def handle(self, event: DocParsed) -> None:
        doc_id = event.document_id
        content_hash = event.content_hash

        async with self._sessionmaker() as session:
            doc_repo = DocumentRepository(session)
            minhash_repo = MinHashRepository(session)

            doc = await doc_repo.get_by_id(uuid.UUID(doc_id))
            if doc is None:
                logger.error("deduper.doc_not_found", document_id=doc_id)
                return

            if doc.status in (DocumentStatus.DEDUPED, DocumentStatus.DUPLICATE):
                logger.info("deduper.already_processed", document_id=doc_id)
                return

            body = doc.body
            if not body:
                logger.error("deduper.no_body", document_id=doc_id)
                await doc_repo.update_status(
                    uuid.UUID(doc_id),
                    DocumentStatus.FAILED,
                    failed_stage="dedup",
                )
                await session.commit()
                return

            shingles = _shingle(body)
            hashvalues = _compute_minhash(shingles, self._num_perm)
            band_hashes = _compute_band_hashes(hashvalues, self._band_size)

            candidates = await minhash_repo.find_candidates_by_bands(
                band_hashes, exclude_doc_id=uuid.UUID(doc_id)
            )

            duplicate_of: str | None = None
            for candidate in candidates:
                jaccard = _jaccard_from_hashvalues(hashvalues, candidate.hashvalues)
                if jaccard >= self._jaccard_threshold:
                    duplicate_of = str(candidate.document_id)
                    break

            await minhash_repo.upsert(
                document_id=uuid.UUID(doc_id),
                num_perm=self._num_perm,
                band_hashes=band_hashes,
                hashvalues=hashvalues,
                band_size=self._band_size,
                canonical_id=duplicate_of,
            )

            if duplicate_of:
                meta = dict(doc.doc_metadata) if doc.doc_metadata else {}
                meta["duplicate_of"] = duplicate_of
                await doc_repo.update_status(
                    uuid.UUID(doc_id),
                    DocumentStatus.DUPLICATE,
                    doc_metadata=meta,
                )
                logger.info(
                    "deduper.duplicate_found",
                    document_id=doc_id,
                    duplicate_of=duplicate_of,
                )
            else:
                await doc_repo.update_status(
                    uuid.UUID(doc_id),
                    DocumentStatus.DEDUPED,
                )
                logger.info("deduper.unique", document_id=doc_id)

            await session.commit()

        deduped_event = DocDeduped(
            document_id=doc_id,
            content_hash=content_hash,
            is_duplicate=duplicate_of is not None,
            duplicate_of=duplicate_of,
        )
        await self._publisher.publish(Stream.DOC_DEDUPED, deduped_event)
