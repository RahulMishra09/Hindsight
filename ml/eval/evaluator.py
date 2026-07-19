"""Evaluation — micro/macro-F1, per-label P/R/F1, calibration (ECE), slice metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import numpy as np

from app.models.incident_label import TAXONOMY_LABELS
from ml.training.data import LabeledExample


@dataclass(frozen=True)
class LabelMetrics:
    label: str
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True)
class EvalReport:
    micro_f1: float
    macro_f1: float
    micro_precision: float
    micro_recall: float
    per_label: list[LabelMetrics]
    ece: float
    slice_metrics: dict[str, dict[str, float]] = field(default_factory=dict)


def compute_label_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> tuple[list[LabelMetrics], float, float, float, float]:
    tp = (y_pred * y_true).sum(axis=0)
    fp = (y_pred * (1 - y_true)).sum(axis=0)
    fn = ((1 - y_pred) * y_true).sum(axis=0)

    precision = np.where(tp + fp > 0, tp / (tp + fp), 0.0)
    recall = np.where(tp + fn > 0, tp / (tp + fn), 0.0)
    f1 = np.where(
        precision + recall > 0,
        2 * precision * recall / (precision + recall),
        0.0,
    )
    support = y_true.sum(axis=0).astype(int)

    per_label = [
        LabelMetrics(
            label=TAXONOMY_LABELS[i],
            precision=float(precision[i]),
            recall=float(recall[i]),
            f1=float(f1[i]),
            support=int(support[i]),
        )
        for i in range(len(TAXONOMY_LABELS))
    ]

    micro_tp = float(tp.sum())
    micro_fp = float(fp.sum())
    micro_fn = float(fn.sum())
    micro_p = micro_tp / (micro_tp + micro_fp) if (micro_tp + micro_fp) > 0 else 0.0
    micro_r = micro_tp / (micro_tp + micro_fn) if (micro_tp + micro_fn) > 0 else 0.0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0
    macro_f1 = float(f1.mean())

    return per_label, micro_f1, macro_f1, micro_p, micro_r


def compute_ece(
    y_true: np.ndarray,
    probs: np.ndarray,
    n_bins: int = 10,
) -> float:
    flat_true = y_true.flatten()
    flat_probs = probs.flatten()

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n_total = len(flat_true)

    for i in range(n_bins):
        lo = bin_boundaries[i]
        hi = bin_boundaries[i + 1]
        if i > 0:
            mask = (flat_probs > lo) & (flat_probs <= hi)
        else:
            mask = (flat_probs >= lo) & (flat_probs <= hi)
        n_bin = int(mask.sum())
        if n_bin == 0:
            continue
        avg_conf = float(flat_probs[mask].mean())
        avg_acc = float(flat_true[mask].mean())
        ece += (n_bin / n_total) * abs(avg_acc - avg_conf)

    return float(ece)


def compute_slice_metrics(
    examples: list[LabeledExample],
    y_pred: np.ndarray,
    thresholds: dict[str, float] | None = None,
) -> dict[str, dict[str, float]]:
    slices: dict[str, dict[str, float]] = {}

    orgs: dict[str, list[int]] = {}
    for i, ex in enumerate(examples):
        org = ex.org or "unknown"
        if org not in orgs:
            orgs[org] = []
        orgs[org].append(i)

    y_true = np.array([ex.labels for ex in examples], dtype=np.float32)

    for org, indices in orgs.items():
        if len(indices) < 3:
            continue
        idx = np.array(indices)
        org_true = y_true[idx]
        org_pred = y_pred[idx]

        tp = float((org_pred * org_true).sum())
        fp = float((org_pred * (1 - org_true)).sum())
        fn = float(((1 - org_pred) * org_true).sum())
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        slices[f"org:{org}"] = {"f1": round(f1, 4), "n": len(indices)}

    lengths = [len(ex.text) for ex in examples]
    median_len = float(np.median(lengths)) if lengths else 500

    short_idx = [i for i, ex in enumerate(examples) if len(ex.text) <= median_len]
    long_idx = [i for i, ex in enumerate(examples) if len(ex.text) > median_len]

    for name, indices in [("doc:short", short_idx), ("doc:long", long_idx)]:
        if len(indices) < 3:
            continue
        idx = np.array(indices)
        s_true = y_true[idx]
        s_pred = y_pred[idx]
        tp = float((s_pred * s_true).sum())
        fp = float((s_pred * (1 - s_true)).sum())
        fn = float(((1 - s_pred) * s_true).sum())
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        slices[name] = {"f1": round(f1, 4), "n": len(indices)}

    return slices


def evaluate(
    examples: list[LabeledExample],
    probs: np.ndarray,
    thresholds: dict[str, float] | None = None,
) -> EvalReport:
    y_true = np.array([ex.labels for ex in examples], dtype=np.float32)

    if thresholds:
        thresh_vec = np.array([thresholds.get(lb, 0.5) for lb in TAXONOMY_LABELS])
        y_pred = (probs >= thresh_vec).astype(np.float32)
    else:
        y_pred = (probs >= 0.5).astype(np.float32)

    per_label, micro_f1, macro_f1, micro_p, micro_r = compute_label_metrics(y_true, y_pred)
    ece = compute_ece(y_true, probs)
    slices = compute_slice_metrics(examples, y_pred, thresholds)

    return EvalReport(
        micro_f1=round(micro_f1, 4),
        macro_f1=round(macro_f1, 4),
        micro_precision=round(micro_p, 4),
        micro_recall=round(micro_r, 4),
        per_label=per_label,
        ece=round(ece, 4),
        slice_metrics=slices,
    )


def generate_report(report: EvalReport) -> str:
    lines = [
        "# Evaluation Report",
        "",
        "## Summary",
        "",
        f"- **Micro F1:** {report.micro_f1:.4f}",
        f"- **Macro F1:** {report.macro_f1:.4f}",
        f"- **Micro Precision:** {report.micro_precision:.4f}",
        f"- **Micro Recall:** {report.micro_recall:.4f}",
        f"- **ECE (calibration):** {report.ece:.4f}",
        "",
        "## Per-Label Metrics",
        "",
        "| Label | Precision | Recall | F1 | Support |",
        "|-------|-----------|--------|-----|---------|",
    ]

    for lm in report.per_label:
        lines.append(
            f"| {lm.label} | {lm.precision:.4f} | {lm.recall:.4f} | {lm.f1:.4f} | {lm.support} |"
        )

    if report.slice_metrics:
        lines.append("")
        lines.append("## Slice Metrics")
        lines.append("")
        lines.append("| Slice | F1 | N |")
        lines.append("|-------|-----|---|")
        for name, metrics in sorted(report.slice_metrics.items()):
            lines.append(f"| {name} | {metrics['f1']:.4f} | {int(metrics['n'])} |")

    lines.append("")
    return "\n".join(lines)


def save_baseline(report: EvalReport, path: Path) -> None:
    baseline = {
        "micro_f1": report.micro_f1,
        "macro_f1": report.macro_f1,
        "per_label_f1": {lm.label: lm.f1 for lm in report.per_label},
    }
    path.write_text(json.dumps(baseline, indent=2))


def load_baseline(path: Path) -> dict[str, float | dict[str, float]]:
    return json.loads(path.read_text())  # type: ignore[no-any-return]
