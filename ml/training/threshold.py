"""Per-label threshold tuning — maximize F1 on validation set."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.models.incident_label import TAXONOMY_LABELS
from ml.training.config import ThresholdConfig
from ml.training.data import DatasetSplit


def predict_logits(
    model_dir: Path,
    texts: list[str],
    max_length: int = 512,
    batch_size: int = 32,
) -> np.ndarray:
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))  # type: ignore[no-untyped-call]
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.eval()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    all_logits: list[np.ndarray] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        enc = tokenizer(
            batch,
            padding="max_length",
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        ).to(device)
        with torch.no_grad():
            outputs = model(**enc)
        all_logits.append(outputs.logits.cpu().numpy())

    return np.concatenate(all_logits, axis=0)


def tune_thresholds(
    model_dir: Path,
    val: DatasetSplit,
    cfg: ThresholdConfig,
    max_length: int = 512,
) -> dict[str, float]:
    logits = predict_logits(model_dir, val.texts, max_length)
    probs = 1 / (1 + np.exp(-logits))
    y_true = val.label_matrix

    lo, hi = cfg.search_range
    candidates = np.linspace(lo, hi, cfg.search_steps)

    thresholds: dict[str, float] = {}
    for i, label in enumerate(TAXONOMY_LABELS):
        best_f1 = -1.0
        best_t = 0.5
        y_col = y_true[:, i]
        p_col = probs[:, i]

        for t in candidates:
            preds = (p_col >= t).astype(np.float32)
            tp = float((preds * y_col).sum())
            fp = float((preds * (1 - y_col)).sum())
            fn = float(((1 - preds) * y_col).sum())
            p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
            if f1 > best_f1:
                best_f1 = f1
                best_t = float(t)

        thresholds[label] = round(best_t, 4)

    return thresholds


def save_thresholds(thresholds: dict[str, float], model_dir: Path) -> Path:
    out = model_dir / "thresholds.json"
    out.write_text(json.dumps(thresholds, indent=2))
    return out
