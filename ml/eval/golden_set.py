"""Golden set builder — exports gold-annotated incident IDs + hashes for frozen eval.

Usage:
    uv run python -m ml.eval.golden_set
    uv run python -m ml.eval.golden_set --out ml/eval/golden/golden.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
import json
from pathlib import Path


async def _export_golden(out: Path) -> int:
    from sqlalchemy import select

    from app.core.db import create_engine, create_sessionmaker
    from app.core.settings import get_settings
    from app.models.incident import Incident
    from app.models.incident_label import IncidentLabel

    settings = get_settings()
    engine = create_engine(settings)
    sm = create_sessionmaker(engine)

    gold_labels: dict[str, set[str]] = defaultdict(set)

    async with sm() as session:
        stmt = select(IncidentLabel).where(
            IncidentLabel.source == "human",
            IncidentLabel.label != "__reviewed__",
        )
        result = await session.execute(stmt)
        for row in result.scalars().all():
            gold_labels[str(row.incident_id)].add(row.label)

        incidents_stmt = select(Incident).where(
            Incident.id.in_(list(gold_labels)),
        )
        incidents_result = await session.execute(incidents_stmt)
        incidents = {str(inc.id): inc for inc in incidents_result.scalars().all()}

    await engine.dispose()

    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out.open("w") as f:
        for inc_id in sorted(gold_labels.keys()):
            inc = incidents.get(inc_id)
            if not inc:
                continue
            record = {
                "id": inc_id,
                "content_hash": inc.content_hash,
                "labels": sorted(gold_labels[inc_id]),
            }
            f.write(json.dumps(record) + "\n")
            count += 1

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Export golden evaluation set")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("ml/eval/golden/golden.jsonl"),
    )
    args = parser.parse_args()
    count = asyncio.run(_export_golden(args.out))
    print(f"Exported {count} golden examples to {args.out}")


if __name__ == "__main__":
    main()
