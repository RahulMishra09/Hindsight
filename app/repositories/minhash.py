"""MinHash signature repository — persist and query LSH signatures."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.minhash_signature import MinHashSignature


class MinHashRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        document_id: uuid.UUID,
        num_perm: int,
        band_hashes: list[str],
        hashvalues: list[int],
        band_size: int = 4,
        canonical_id: str | None = None,
    ) -> MinHashSignature:
        stmt = select(MinHashSignature).where(MinHashSignature.document_id == document_id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.num_perm = num_perm
            existing.band_hashes = band_hashes
            existing.hashvalues = hashvalues
            existing.band_size = band_size
            existing.canonical_id = canonical_id
            await self._session.flush()
            return existing
        sig = MinHashSignature(
            document_id=document_id,
            num_perm=num_perm,
            band_hashes=band_hashes,
            hashvalues=hashvalues,
            band_size=band_size,
            canonical_id=canonical_id,
        )
        self._session.add(sig)
        await self._session.flush()
        return sig

    async def get_by_document_id(self, document_id: uuid.UUID) -> MinHashSignature | None:
        stmt = select(MinHashSignature).where(MinHashSignature.document_id == document_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_candidates_by_bands(
        self, band_hashes: list[str], *, exclude_doc_id: uuid.UUID | None = None
    ) -> list[MinHashSignature]:
        """Find signatures that share at least one band hash."""
        from sqlalchemy.dialects.postgresql import array
        from sqlalchemy.types import ARRAY, Text

        band_array = array(band_hashes, type_=ARRAY(Text))
        stmt = select(MinHashSignature).where(MinHashSignature.band_hashes.op("?|")(band_array))
        if exclude_doc_id is not None:
            stmt = stmt.where(MinHashSignature.document_id != exclude_doc_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_all(self) -> list[MinHashSignature]:
        stmt = select(MinHashSignature)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
