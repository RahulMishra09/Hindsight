"""Run evaluation on the test split or golden set.

Usage:
    uv run python -m ml.eval.run --model models/deberta-taxonomy/best
    uv run python -m ml.eval.run --model models/deberta-taxonomy/best \\
        --golden ml/eval/golden/golden.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ml.eval.evaluator import evaluate, generate_report, save_baseline
from ml.training.data import LABEL_TO_IDX, NUM_LABELS, LabeledExample
from ml.training.threshold import predict_logits


def _load_golden(
    golden_path: Path,
    model_dir: Path,
    max_length: int = 512,
) -> tuple[list[LabeledExample], np.ndarray]:
    """Load golden set and run inference."""
    import asyncio

    from sqlalchemy import select

    from app.core.db import create_engine, create_sessionmaker
    from app.core.settings import get_settings
    from app.models.incident import Incident

    golden_records = []
    for line in golden_path.read_text().splitlines():
        if line.strip():
            golden_records.append(json.loads(line))

    inc_ids = [r["id"] for r in golden_records]
    label_map = {r["id"]: r["labels"] for r in golden_records}

    async def _fetch_texts() -> dict[str, tuple[str, str]]:
        settings = get_settings()
        engine = create_engine(settings)
        sm = create_sessionmaker(engine)
        texts: dict[str, tuple[str, str]] = {}
        async with sm() as session:
            result = await session.execute(select(Incident).where(Incident.id.in_(inc_ids)))
            for inc in result.scalars().all():
                parts: list[str] = []
                if inc.title:
                    parts.append(inc.title)
                if inc.summary:
                    parts.append(inc.summary)
                if inc.sections and isinstance(inc.sections, dict):
                    for st in inc.sections.values():
                        if isinstance(st, str):
                            parts.append(st)
                texts[str(inc.id)] = ("\n\n".join(parts), inc.org or "")
        await engine.dispose()
        return texts

    texts = asyncio.run(_fetch_texts())

    examples: list[LabeledExample] = []
    for inc_id in inc_ids:
        if inc_id not in texts:
            continue
        text, org = texts[inc_id]
        if not text.strip():
            continue
        label_vec = [0] * NUM_LABELS
        for lb in label_map.get(inc_id, []):
            if lb in LABEL_TO_IDX:
                label_vec[LABEL_TO_IDX[lb]] = 1
        if sum(label_vec) == 0:
            continue
        examples.append(
            LabeledExample(
                incident_id=inc_id,
                text=text,
                labels=label_vec,
                weight=1.0,
                org=org,
                source="gold",
            )
        )

    all_texts = [ex.text for ex in examples]
    logits = predict_logits(model_dir, all_texts, max_length)
    probs = 1 / (1 + np.exp(-logits))
    return examples, probs


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate classifier")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--golden", type=Path, default=None)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--out-report", type=Path, default=None)
    parser.add_argument("--save-baseline", action="store_true")
    args = parser.parse_args()

    thresholds_path = args.model / "thresholds.json"
    thresholds = None
    if thresholds_path.exists():
        thresholds = json.loads(thresholds_path.read_text())

    if args.golden and args.golden.exists():
        examples, probs = _load_golden(args.golden, args.model, args.max_length)
    else:
        print("No golden set provided; evaluation requires --golden or test split data.")
        return

    report = evaluate(examples, probs, thresholds)
    md = generate_report(report)
    print(md)

    if args.out_report:
        args.out_report.parent.mkdir(parents=True, exist_ok=True)
        args.out_report.write_text(md)
        print(f"\nReport written to {args.out_report}")

    if args.save_baseline:
        baseline_path = Path("ml/eval/baseline.json")
        save_baseline(report, baseline_path)
        print(f"Baseline saved to {baseline_path}")


if __name__ == "__main__":
    main()
