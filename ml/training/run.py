"""Main training entry point — orchestrates data load, train, threshold tune.

Usage:
    uv run python -m ml.training.run
    uv run python -m ml.training.run --config ml/training/config.yaml
"""

from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
import json
from pathlib import Path

from ml.training.config import load_config
from ml.training.data import merge_silver_gold, stratified_split
from ml.training.threshold import save_thresholds, tune_thresholds
from ml.training.trainer import run_training


async def _load_from_db() -> tuple[
    dict[str, set[str]], dict[str, set[str]], dict[str, str], dict[str, str]
]:
    """Load silver labels, gold labels, texts, and orgs from the database."""
    from sqlalchemy import select

    from app.core.db import create_engine, create_sessionmaker
    from app.core.settings import get_settings
    from app.models.incident import Incident
    from app.models.incident_label import IncidentLabel

    settings = get_settings()
    engine = create_engine(settings)
    sm = create_sessionmaker(engine)

    silver: dict[str, set[str]] = defaultdict(set)
    gold: dict[str, set[str]] = defaultdict(set)
    texts: dict[str, str] = {}
    orgs: dict[str, str] = {}

    async with sm() as session:
        labels_result = await session.execute(select(IncidentLabel))
        for row in labels_result.scalars().all():
            inc_id = str(row.incident_id)
            if row.label == "__reviewed__":
                continue
            if row.source == "human":
                gold[inc_id].add(row.label)
            elif row.source == "weak":
                silver[inc_id].add(row.label)

        incidents_result = await session.execute(select(Incident))
        for inc in incidents_result.scalars().all():
            inc_id = str(inc.id)
            parts: list[str] = []
            if inc.title:
                parts.append(inc.title)
            if inc.summary:
                parts.append(inc.summary)
            if inc.sections and isinstance(inc.sections, dict):
                for section_text in inc.sections.values():
                    if isinstance(section_text, str):
                        parts.append(section_text)
            texts[inc_id] = "\n\n".join(parts)
            orgs[inc_id] = inc.org or ""

    await engine.dispose()
    return dict(silver), dict(gold), texts, orgs


def _load_from_jsonl(
    path: Path,
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, str], dict[str, str]]:
    """Load from a JSONL export file for offline training."""
    silver: dict[str, set[str]] = defaultdict(set)
    gold: dict[str, set[str]] = defaultdict(set)
    texts: dict[str, str] = {}
    orgs: dict[str, str] = {}

    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        inc_id = record["id"]
        texts[inc_id] = record.get("text", "")
        orgs[inc_id] = record.get("org", "")
        for lb in record.get("silver_labels", []):
            silver[inc_id].add(lb)
        for lb in record.get("gold_labels", []):
            gold[inc_id].add(lb)

    return dict(silver), dict(gold), texts, orgs


def main() -> None:
    parser = argparse.ArgumentParser(description="Train hindsight-taxonomy classifier")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--data-jsonl", type=Path, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.data_jsonl and args.data_jsonl.exists():
        silver, gold, texts, orgs = _load_from_jsonl(args.data_jsonl)
    else:
        silver, gold, texts, orgs = asyncio.run(_load_from_db())

    examples = merge_silver_gold(
        silver,
        gold,
        texts,
        orgs,
        silver_weight=cfg.data.silver_weight,
        gold_weight=cfg.data.gold_weight,
    )
    n_gold = sum(1 for e in examples if e.source == "gold")
    n_silver = sum(1 for e in examples if e.source == "silver")
    print(f"Loaded {len(examples)} labeled examples ({n_gold} gold, {n_silver} silver)")

    train, val, test = stratified_split(
        examples,
        val_fraction=cfg.data.val_fraction,
        test_fraction=cfg.data.test_fraction,
        seed=cfg.data.seed,
    )
    print(f"Split: train={len(train)}, val={len(val)}, test={len(test)}")

    best_dir = run_training(cfg, train, val)
    print(f"Best model saved to {best_dir}")

    thresholds = tune_thresholds(best_dir, val, cfg.threshold, cfg.model.max_length)
    save_thresholds(thresholds, best_dir)
    print(f"Thresholds: {thresholds}")

    test_meta = {
        "train_size": len(train),
        "val_size": len(val),
        "test_size": len(test),
        "gold_count": sum(1 for e in examples if e.source == "gold"),
        "silver_count": sum(1 for e in examples if e.source == "silver"),
    }
    (best_dir / "training_meta.json").write_text(json.dumps(test_meta, indent=2))


if __name__ == "__main__":
    main()
