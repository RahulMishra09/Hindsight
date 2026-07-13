#!/usr/bin/env python3
"""Pipeline report — per-stage counts, DLQ depth, duplicate rate, top failures.

Usage: python scripts/pipeline_report.py
"""

from __future__ import annotations

import asyncio

import redis.asyncio as redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import create_engine, create_redis, create_sessionmaker
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.events.streams import Stream, dlq_of
from app.models.ingest import Document, DocumentStatus


async def _document_counts(session: AsyncSession) -> dict[str, int]:
    stmt = select(Document.status, func.count()).group_by(Document.status)
    result = await session.execute(stmt)
    return {str(row[0]): int(row[1]) for row in result.all()}


async def _failure_breakdown(session: AsyncSession) -> list[tuple[str | None, int]]:
    stmt = (
        select(Document.failed_stage, func.count())
        .where(Document.status == DocumentStatus.FAILED)
        .group_by(Document.failed_stage)
        .order_by(func.count().desc())
    )
    result = await session.execute(stmt)
    return [(str(row[0]) if row[0] else "unknown", int(row[1])) for row in result.all()]


async def _total_documents(session: AsyncSession) -> int:
    stmt = select(func.count()).select_from(Document)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def _dlq_depth(client: redis.Redis, stream: str) -> int:  # type: ignore[type-arg]
    try:
        info = await client.xinfo_stream(dlq_of(stream))
        return int(info.get("length", 0))  # type: ignore[arg-type]
    except Exception:
        return 0


async def run() -> None:
    settings = get_settings()
    configure_logging(settings)

    engine = create_engine(settings)
    sm = create_sessionmaker(engine)
    rc = create_redis(settings)

    try:
        async with sm() as session:
            total = await _total_documents(session)
            counts = await _document_counts(session)
            failures = await _failure_breakdown(session)

        dlq_streams = [
            Stream.DOC_DISCOVERED,
            Stream.DOC_FETCHED,
            Stream.DOC_PARSED,
            Stream.DOC_DEDUPED,
        ]
        dlq_depths: dict[str, int] = {}
        for s in dlq_streams:
            dlq_depths[s] = await _dlq_depth(rc, s)

        print("\n" + "=" * 60)
        print("  HINDSIGHT PIPELINE REPORT")
        print("=" * 60)

        print(f"\n  Total documents: {total}\n")

        print("  Status Breakdown:")
        print("  " + "-" * 40)
        for status in DocumentStatus:
            count = counts.get(status.value, 0)
            pct = (count / total * 100) if total > 0 else 0
            print(f"    {status.value:<14} {count:>6}  ({pct:5.1f}%)")

        duplicate_count = counts.get("duplicate", 0)
        deduped_count = counts.get("deduped", 0)
        processed = duplicate_count + deduped_count
        dup_rate = (duplicate_count / processed * 100) if processed > 0 else 0
        print(f"\n  Duplicate rate: {dup_rate:.1f}% ({duplicate_count}/{processed})")

        print("\n  DLQ Depths:")
        print("  " + "-" * 40)
        for s, depth in dlq_depths.items():
            print(f"    {s:<40} {depth:>4}")

        if failures:
            print("\n  Top Failure Reasons:")
            print("  " + "-" * 40)
            for stage, count in failures[:10]:
                print(f"    {stage:<20} {count:>6}")

        print("\n" + "=" * 60 + "\n")

    finally:
        await engine.dispose()
        await rc.aclose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
