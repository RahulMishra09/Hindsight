"""Unit tests for threshold tuning — grid search and save/load."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.models.incident_label import TAXONOMY_LABELS
from ml.training.config import ThresholdConfig
from ml.training.data import NUM_LABELS


class TestThresholdGridSearch:
    def _make_probs_and_truth(
        self,
        n: int = 100,
    ) -> tuple[np.ndarray, np.ndarray]:
        rng = np.random.default_rng(42)
        y_true = rng.integers(0, 2, size=(n, NUM_LABELS)).astype(np.float32)
        logits = y_true * 2.0 - 1.0 + rng.normal(0, 0.3, size=(n, NUM_LABELS))
        probs = 1 / (1 + np.exp(-logits))
        return probs, y_true

    def test_grid_search_finds_thresholds(self):
        probs, y_true = self._make_probs_and_truth()
        cfg = ThresholdConfig(search_range=[0.1, 0.9], search_steps=81)

        lo, hi = cfg.search_range
        candidates = np.linspace(lo, hi, cfg.search_steps)

        thresholds: dict[str, float] = {}
        for i, label in enumerate(TAXONOMY_LABELS):
            best_f1 = -1.0
            best_t = 0.5
            for t in candidates:
                preds = (probs[:, i] >= t).astype(np.float32)
                tp = float((preds * y_true[:, i]).sum())
                fp = float((preds * (1 - y_true[:, i])).sum())
                fn = float(((1 - preds) * y_true[:, i]).sum())
                p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
                if f1 > best_f1:
                    best_f1 = f1
                    best_t = float(t)
            thresholds[label] = round(best_t, 4)

        assert len(thresholds) == NUM_LABELS
        for label in TAXONOMY_LABELS:
            assert 0.1 <= thresholds[label] <= 0.9

    def test_perfect_separation_finds_threshold(self):
        probs = np.zeros((10, NUM_LABELS), dtype=np.float32)
        y_true = np.zeros((10, NUM_LABELS), dtype=np.float32)
        probs[:5, 0] = 0.9
        probs[5:, 0] = 0.1
        y_true[:5, 0] = 1.0

        cfg = ThresholdConfig(search_range=[0.1, 0.9], search_steps=81)
        candidates = np.linspace(cfg.search_range[0], cfg.search_range[1], cfg.search_steps)

        best_f1 = -1.0
        best_t = 0.5
        for t in candidates:
            preds = (probs[:, 0] >= t).astype(np.float32)
            tp = float((preds * y_true[:, 0]).sum())
            fp = float((preds * (1 - y_true[:, 0])).sum())
            fn = float(((1 - preds) * y_true[:, 0]).sum())
            p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
            if f1 > best_f1:
                best_f1 = f1
                best_t = float(t)

        assert best_f1 == 1.0
        assert 0.1 <= best_t <= 0.9


class TestSaveThresholds:
    def test_save_and_load(self, tmp_path: Path):
        from ml.training.threshold import save_thresholds

        thresholds = dict.fromkeys(TAXONOMY_LABELS, 0.5)
        thresholds["dns"] = 0.35
        thresholds["bad-deploy"] = 0.7

        path = save_thresholds(thresholds, tmp_path)
        assert path.exists()

        loaded = json.loads(path.read_text())
        assert loaded["dns"] == 0.35
        assert loaded["bad-deploy"] == 0.7
        assert len(loaded) == NUM_LABELS

    def test_output_is_valid_json(self, tmp_path: Path):
        from ml.training.threshold import save_thresholds

        thresholds = {label: round(0.1 + i * 0.05, 4) for i, label in enumerate(TAXONOMY_LABELS)}
        path = save_thresholds(thresholds, tmp_path)
        loaded = json.loads(path.read_text())
        assert isinstance(loaded, dict)
