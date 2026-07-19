"""Backfill classification — run TaxonomyClassifier on all unclassified incidents.

Usage:
    uv run python scripts/backfill_classify.py --model models/deberta-taxonomy/best
    uv run python scripts/backfill_classify.py --model models/deberta-taxonomy/onnx --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import func, select

from app.core.db import create_engine, create_sessionmaker
from app.core.settings import get_settings
from app.ml.classifier import TaxonomyClassifier
from app.models.incident import Incident
from app.models.incident_label import TAXONOMY_LABELS, IncidentLabel
from app.repositories.incident_label import IncidentLabelRepository

MODEL_VERSION = "hindsight-taxonomy-v1"


async def _backfill(model_dir: Path, max_length: int, batch_size: int, dry_run: bool) -> int:
    settings = get_settings()
    engine = create_engine(settings)
    sm = create_sessionmaker(engine)

    classifier = TaxonomyClassifier(model_dir, max_length=max_length)

    classified_count = 0

    async with sm() as session:
        classified_ids_stmt = (
            select(IncidentLabel.incident_id).where(IncidentLabel.source == "model").distinct()
        )
        classified_result = await session.execute(classified_ids_stmt)
        already_classified = {row[0] for row in classified_result.all()}

        total_stmt = select(func.count()).select_from(Incident)
        total = int((await session.execute(total_stmt)).scalar_one())

        print(f"Total incidents: {total}, already classified: {len(already_classified)}")

        offset = 0
        while True:
            stmt = select(Incident).order_by(Incident.created_at).limit(batch_size).offset(offset)
            result = await session.execute(stmt)
            incidents = result.scalars().all()
            if not incidents:
                break

            for incident in incidents:
                if incident.id in already_classified:
                    continue

                probs, _labels, active_labels = classifier.classify_incident(
                    title=incident.title,
                    summary=incident.summary,
                    sections=incident.sections,
                )

                if dry_run:
                    print(f"  [dry-run] {incident.id}: {active_labels}")
                    classified_count += 1
                    continue

                label_repo = IncidentLabelRepository(session)
                for label_name in active_labels:
                    idx = TAXONOMY_LABELS.index(label_name)
                    await label_repo.upsert(
                        incident_id=incident.id,
                        label=label_name,
                        source="model",
                        confidence=round(float(probs[idx]), 4),
                        model_version=MODEL_VERSION,
                        annotator_id="backfill",
                    )

                classified_count += 1

            if not dry_run:
                await session.commit()

            offset += batch_size
            print(f"  Processed {offset} incidents, classified {classified_count} so far")

    await engine.dispose()
    return classified_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill classification for all incidents")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    count = asyncio.run(_backfill(args.model, args.max_length, args.batch_size, args.dry_run))
    print(f"\nBackfill complete: {count} incidents classified")


if __name__ == "__main__":
    main()
