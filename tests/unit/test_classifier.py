"""Unit tests for TaxonomyClassifier — section splitting and max-pooling logic."""

from __future__ import annotations

import numpy as np

from app.ml.classifier import TaxonomyClassifier
from ml.training.data import NUM_LABELS


class TestSplitSections:
    def test_title_and_summary(self) -> None:
        chunks = TaxonomyClassifier.split_sections("Title", "Summary", None)
        assert len(chunks) == 1
        assert "Title" in chunks[0]
        assert "Summary" in chunks[0]

    def test_dict_sections(self) -> None:
        sections = {"root_cause": "DNS failure", "impact": "Outage for 2h"}
        chunks = TaxonomyClassifier.split_sections("Title", None, sections)
        assert len(chunks) == 3
        assert chunks[0] == "Title"
        assert "DNS failure" in chunks[1]
        assert "Outage for 2h" in chunks[2]

    def test_list_sections(self) -> None:
        sections = ["First section", "Second section"]
        chunks = TaxonomyClassifier.split_sections("Title", None, sections)
        assert len(chunks) == 3

    def test_empty_everything(self) -> None:
        chunks = TaxonomyClassifier.split_sections(None, None, None)
        assert chunks == []

    def test_empty_string_title_no_sections(self) -> None:
        chunks = TaxonomyClassifier.split_sections("", None, None)
        assert chunks == []

    def test_only_sections_no_title(self) -> None:
        sections = {"cause": "Config change"}
        chunks = TaxonomyClassifier.split_sections(None, None, sections)
        assert len(chunks) == 1
        assert "Config change" in chunks[0]

    def test_long_section_truncated(self) -> None:
        sections = {"cause": "x" * 200_000}
        chunks = TaxonomyClassifier.split_sections("T", None, sections)
        assert len(chunks[1]) == 100_000

    def test_empty_section_values_skipped(self) -> None:
        sections = {"cause": "", "impact": "   "}
        chunks = TaxonomyClassifier.split_sections("Title", None, sections)
        assert len(chunks) == 1


class TestMaxPooling:
    def test_max_pool_picks_highest(self) -> None:
        probs = np.array(
            [
                [0.1, 0.9, 0.3] + [0.0] * (NUM_LABELS - 3),
                [0.8, 0.2, 0.4] + [0.0] * (NUM_LABELS - 3),
            ],
            dtype=np.float32,
        )
        pooled = probs.max(axis=0)
        assert abs(pooled[0] - 0.8) < 1e-6
        assert abs(pooled[1] - 0.9) < 1e-6
        assert abs(pooled[2] - 0.4) < 1e-6

    def test_single_chunk_no_change(self) -> None:
        probs = np.array(
            [[0.5, 0.6, 0.7] + [0.0] * (NUM_LABELS - 3)],
            dtype=np.float32,
        )
        pooled = probs.max(axis=0)
        np.testing.assert_array_almost_equal(pooled[:3], [0.5, 0.6, 0.7])


class TestThresholdApplication:
    def test_above_threshold_is_positive(self) -> None:
        thresholds = np.full(NUM_LABELS, 0.5, dtype=np.float32)
        probs = np.array([0.6] + [0.0] * (NUM_LABELS - 1), dtype=np.float32)
        labels = (probs >= thresholds).astype(np.float32)
        assert labels[0] == 1.0

    def test_below_threshold_is_negative(self) -> None:
        thresholds = np.full(NUM_LABELS, 0.5, dtype=np.float32)
        probs = np.array([0.4] + [0.0] * (NUM_LABELS - 1), dtype=np.float32)
        labels = (probs >= thresholds).astype(np.float32)
        assert labels[0] == 0.0

    def test_per_label_thresholds(self) -> None:
        thresholds = np.array([0.3, 0.7] + [0.5] * (NUM_LABELS - 2), dtype=np.float32)
        probs = np.array([0.5, 0.5] + [0.0] * (NUM_LABELS - 2), dtype=np.float32)
        labels = (probs >= thresholds).astype(np.float32)
        assert labels[0] == 1.0
        assert labels[1] == 0.0
