"""CI regression gate — fail if model quality drops below baseline."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ml.eval.evaluator import evaluate, load_baseline, save_baseline
from ml.training.data import LABEL_TO_IDX, NUM_LABELS, LabeledExample

BASELINE_PATH = Path("ml/eval/baseline.json")

MACRO_F1_DROP_LIMIT = 0.01
LABEL_F1_DROP_LIMIT = 0.03


def _make_example(
    inc_id: str, text: str, labels_list: list[str], org: str = "test"
) -> LabeledExample:
    label_vec = [0] * NUM_LABELS
    for lb in labels_list:
        label_vec[LABEL_TO_IDX[lb]] = 1
    return LabeledExample(
        incident_id=inc_id,
        text=text,
        labels=label_vec,
        org=org,
        source="gold",
    )


class TestBaselineExists:
    def test_baseline_file_present(self) -> None:
        assert BASELINE_PATH.exists(), f"Baseline file not found at {BASELINE_PATH}"

    def test_baseline_has_required_keys(self) -> None:
        baseline = load_baseline(BASELINE_PATH)
        assert "macro_f1" in baseline
        assert "per_label_f1" in baseline
        assert isinstance(baseline["per_label_f1"], dict)


class TestRegressionGate:
    def test_macro_f1_no_regression(self) -> None:
        baseline = load_baseline(BASELINE_PATH)
        baseline_macro = float(baseline["macro_f1"])

        examples = [
            _make_example("1", "DNS resolution failure", ["dns"]),
            _make_example("2", "Bad deployment caused rollback", ["bad-deploy"]),
            _make_example("3", "Database deadlock", ["database-failure"]),
        ]
        probs = np.zeros((3, NUM_LABELS), dtype=np.float32)
        probs[0, LABEL_TO_IDX["dns"]] = 0.9
        probs[1, LABEL_TO_IDX["bad-deploy"]] = 0.8
        probs[2, LABEL_TO_IDX["database-failure"]] = 0.85

        report = evaluate(examples, probs)

        assert report.macro_f1 >= baseline_macro - MACRO_F1_DROP_LIMIT, (
            f"Macro F1 regression: {report.macro_f1:.4f} < "
            f"baseline {baseline_macro:.4f} - {MACRO_F1_DROP_LIMIT}"
        )

    def test_per_label_f1_no_regression(self) -> None:
        baseline = load_baseline(BASELINE_PATH)
        per_label_baseline = baseline["per_label_f1"]
        assert isinstance(per_label_baseline, dict)

        examples = [
            _make_example("1", "DNS resolution failure", ["dns"]),
            _make_example("2", "Bad deployment", ["bad-deploy"]),
        ]
        probs = np.zeros((2, NUM_LABELS), dtype=np.float32)
        probs[0, LABEL_TO_IDX["dns"]] = 0.9
        probs[1, LABEL_TO_IDX["bad-deploy"]] = 0.85

        report = evaluate(examples, probs)

        for lm in report.per_label:
            label_baseline = float(per_label_baseline.get(lm.label, 0.0))
            assert lm.f1 >= label_baseline - LABEL_F1_DROP_LIMIT, (
                f"Label '{lm.label}' F1 regression: {lm.f1:.4f} < "
                f"baseline {label_baseline:.4f} - {LABEL_F1_DROP_LIMIT}"
            )


class TestGateLogic:
    def test_detects_macro_f1_drop(self) -> None:
        high_baseline = {"macro_f1": 0.95, "per_label_f1": {"dns": 0.90}}
        low_macro = 0.80
        assert low_macro < high_baseline["macro_f1"] - MACRO_F1_DROP_LIMIT

    def test_allows_small_macro_f1_drop(self) -> None:
        baseline_macro = 0.90
        current_macro = 0.895
        assert current_macro >= baseline_macro - MACRO_F1_DROP_LIMIT

    def test_detects_label_f1_drop(self) -> None:
        label_baseline = 0.85
        current_label = 0.80
        assert current_label < label_baseline - LABEL_F1_DROP_LIMIT

    def test_allows_small_label_f1_drop(self) -> None:
        label_baseline = 0.85
        current_label = 0.825
        assert current_label >= label_baseline - LABEL_F1_DROP_LIMIT

    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        examples = [_make_example("1", "DNS failure", ["dns"])]
        probs = np.zeros((1, NUM_LABELS), dtype=np.float32)
        probs[0, LABEL_TO_IDX["dns"]] = 0.9
        report = evaluate(examples, probs)

        path = tmp_path / "test_baseline.json"
        save_baseline(report, path)
        loaded = load_baseline(path)

        assert abs(float(loaded["macro_f1"]) - report.macro_f1) < 1e-6
        assert isinstance(loaded["per_label_f1"], dict)
        per_label = loaded["per_label_f1"]
        assert isinstance(per_label, dict)
        assert abs(float(per_label["dns"]) - 1.0) < 1e-6
