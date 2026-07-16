"""Compute inter-annotator agreement over doubly-annotated incidents.

Metrics:
  - Per-label Cohen's kappa (for each pair of annotators)
  - Overall Krippendorff's alpha (nominal, multi-annotator)

Usage:
    uv run python -m scripts.agreement
    uv run python -m scripts.agreement --out docs/agreement_report.md
"""

from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from app.models.incident_label import TAXONOMY_LABELS


def cohens_kappa(
    y1: Sequence[int],
    y2: Sequence[int],
) -> float:
    n = len(y1)
    if n == 0:
        return 0.0
    agree = sum(1 for a, b in zip(y1, y2, strict=True) if a == b)
    p_o = agree / n
    pos1 = sum(y1) / n
    pos2 = sum(y2) / n
    p_e = pos1 * pos2 + (1 - pos1) * (1 - pos2)
    if p_e == 1.0:
        return 1.0
    return (p_o - p_e) / (1 - p_e)


def krippendorffs_alpha(
    units: dict[str, dict[str, int]],
) -> float:
    """Compute Krippendorff's alpha for nominal data.

    Args:
        units: mapping of unit_id → {annotator_id → value}.
               Only units with >= 2 annotators are included.
    """
    pairable = {u: anns for u, anns in units.items() if len(anns) >= 2}
    if not pairable:
        return 0.0

    n_total = 0
    observed_disagree = 0.0
    value_counts: defaultdict[int, int] = defaultdict(int)

    for _uid, anns in pairable.items():
        values = list(anns.values())
        m = len(values)
        n_total += m
        for v in values:
            value_counts[v] += 1
        for i in range(m):
            for j in range(i + 1, m):
                if values[i] != values[j]:
                    observed_disagree += 1.0 / (m - 1)

    if n_total <= 1:
        return 0.0

    d_o = observed_disagree / len(pairable)

    n_vals = sum(value_counts.values())
    d_e = 0.0
    vals = list(value_counts.keys())
    for i in range(len(vals)):
        for j in range(i + 1, len(vals)):
            n_i = value_counts[vals[i]]
            n_j = value_counts[vals[j]]
            d_e += n_i * n_j
    d_e = d_e * 2 / (n_vals * (n_vals - 1)) if n_vals > 1 else 0.0

    if d_e == 0.0:
        return 1.0
    return 1.0 - d_o / d_e


async def _load_annotations() -> dict[str, dict[str, set[str]]]:
    """Load human annotations grouped by incident_id → annotator_id → set of labels."""
    from sqlalchemy import select

    from app.core.db import create_engine, create_sessionmaker
    from app.core.settings import get_settings
    from app.models.incident_label import IncidentLabel

    settings = get_settings()
    engine = create_engine(settings)
    sm = create_sessionmaker(engine)

    result: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    async with sm() as session:
        stmt = select(IncidentLabel).where(
            IncidentLabel.source == "human",
            IncidentLabel.label != "__reviewed__",
        )
        rows = await session.execute(stmt)
        for row in rows.scalars().all():
            result[str(row.incident_id)][row.annotator_id].add(row.label)

    await engine.dispose()
    return dict(result)


def _compute_agreement(
    annotations: dict[str, dict[str, set[str]]],
) -> tuple[dict[str, float], float]:
    """Return (per_label_kappa, overall_alpha)."""
    doubly = {uid: anns for uid, anns in annotations.items() if len(anns) >= 2}

    if not doubly:
        return {}, 0.0

    annotator_ids: set[str] = set()
    for anns in doubly.values():
        annotator_ids.update(anns.keys())
    annotator_list = sorted(annotator_ids)

    if len(annotator_list) < 2:
        return {}, 0.0

    a1, a2 = annotator_list[0], annotator_list[1]

    per_label_kappa: dict[str, float] = {}
    for label in TAXONOMY_LABELS:
        y1: list[int] = []
        y2: list[int] = []
        for _uid, anns in doubly.items():
            if a1 in anns and a2 in anns:
                y1.append(1 if label in anns[a1] else 0)
                y2.append(1 if label in anns[a2] else 0)
        if y1:
            per_label_kappa[label] = cohens_kappa(y1, y2)

    alpha_units: dict[str, dict[str, int]] = {}
    for label in TAXONOMY_LABELS:
        for uid, anns in doubly.items():
            unit_key = f"{uid}::{label}"
            unit_anns: dict[str, int] = {}
            for aid, labels in anns.items():
                unit_anns[aid] = 1 if label in labels else 0
            alpha_units[unit_key] = unit_anns

    alpha = krippendorffs_alpha(alpha_units)
    return per_label_kappa, alpha


def _generate_report(
    per_label_kappa: dict[str, float],
    alpha: float,
    n_doubly: int,
    n_total: int,
) -> str:
    lines = [
        "# Inter-Annotator Agreement Report",
        "",
        f"- **Total annotated incidents:** {n_total}",
        f"- **Doubly-annotated incidents:** {n_doubly}",
        f"- **Overall Krippendorff's alpha:** {alpha:.4f}",
        "",
        "## Per-Label Cohen's Kappa",
        "",
        "| Label | Kappa | Interpretation |",
        "|-------|-------|----------------|",
    ]

    for label in TAXONOMY_LABELS:
        kappa = per_label_kappa.get(label, float("nan"))
        if kappa >= 0.8:
            interp = "Almost perfect"
        elif kappa >= 0.6:
            interp = "Substantial"
        elif kappa >= 0.4:
            interp = "Moderate"
        elif kappa >= 0.2:
            interp = "Fair"
        elif kappa >= 0.0:
            interp = "Slight"
        else:
            interp = "Poor"
        lines.append(f"| {label} | {kappa:.4f} | {interp} |")

    lines.append("")
    lines.append("## Interpretation Guide")
    lines.append("")
    lines.append("| Range | Interpretation |")
    lines.append("|-------|----------------|")
    lines.append("| 0.81-1.00 | Almost perfect |")
    lines.append("| 0.61-0.80 | Substantial |")
    lines.append("| 0.41-0.60 | Moderate |")
    lines.append("| 0.21-0.40 | Fair |")
    lines.append("| 0.00-0.20 | Slight |")
    lines.append("| < 0.00 | Poor |")
    lines.append("")
    return "\n".join(lines)


async def main(out: Path | None = None) -> None:
    annotations = await _load_annotations()
    n_total = len(annotations)
    doubly = {uid: anns for uid, anns in annotations.items() if len(anns) >= 2}
    n_doubly = len(doubly)

    per_label_kappa, alpha = _compute_agreement(annotations)

    report = _generate_report(per_label_kappa, alpha, n_doubly, n_total)
    print(report)

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
        print(f"\nReport written to {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute inter-annotator agreement metrics")
    parser.add_argument("--out", type=Path, default=None, help="Output markdown file")
    args = parser.parse_args()
    asyncio.run(main(out=args.out))
