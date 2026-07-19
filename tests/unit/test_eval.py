"""Unit tests for evaluation module."""

import numpy as np

from ml.eval.evaluator import (
    EvalReport,
    compute_ece,
    compute_label_metrics,
    evaluate,
    generate_report,
    load_baseline,
    save_baseline,
)
from ml.training.data import LABEL_TO_IDX, NUM_LABELS, LabeledExample


def _make_example(inc_id, text, labels_list, org="test"):
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


class TestLabelMetrics:
    def _pad(self, rows):
        return np.array(
            [row + [0] * (NUM_LABELS - len(row)) for row in rows],
            dtype=np.float32,
        )

    def test_perfect_predictions(self):
        y_true = self._pad([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        y_pred = self._pad([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        _per_label, micro_f1, macro_f1, _, _ = compute_label_metrics(y_true, y_pred)
        assert micro_f1 == 1.0
        assert macro_f1 > 0.0

    def test_no_predictions(self):
        y_true = self._pad([[1, 0], [0, 1]])
        y_pred = self._pad([[0, 0], [0, 0]])
        _per_label, micro_f1, _, _, _ = compute_label_metrics(y_true, y_pred)
        assert micro_f1 == 0.0


class TestECE:
    def test_perfect_calibration(self):
        y_true = np.array([[1, 0], [0, 1]], dtype=np.float32)
        probs = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        ece = compute_ece(y_true, probs)
        assert ece < 0.05

    def test_poor_calibration(self):
        y_true = np.array([[1, 0], [1, 0]], dtype=np.float32)
        probs = np.array([[0.1, 0.9], [0.1, 0.9]], dtype=np.float32)
        ece = compute_ece(y_true, probs)
        assert ece > 0.3


class TestEvaluate:
    def test_evaluate_with_thresholds(self):
        examples = [
            _make_example("1", "DNS failure", ["dns"]),
            _make_example("2", "Bad deploy", ["bad-deploy"]),
        ]
        probs = np.zeros((2, NUM_LABELS), dtype=np.float32)
        probs[0, LABEL_TO_IDX["dns"]] = 0.8
        probs[1, LABEL_TO_IDX["bad-deploy"]] = 0.6

        thresholds = dict.fromkeys(LABEL_TO_IDX, 0.5)
        report = evaluate(examples, probs, thresholds)
        assert report.micro_f1 == 1.0
        assert isinstance(report, EvalReport)

    def test_evaluate_without_thresholds(self):
        examples = [_make_example("1", "DNS failure", ["dns"])]
        probs = np.zeros((1, NUM_LABELS), dtype=np.float32)
        probs[0, LABEL_TO_IDX["dns"]] = 0.9
        report = evaluate(examples, probs)
        assert report.micro_f1 == 1.0


class TestReport:
    def test_generate_report_format(self):
        examples = [_make_example("1", "text", ["dns"])]
        probs = np.zeros((1, NUM_LABELS), dtype=np.float32)
        probs[0, LABEL_TO_IDX["dns"]] = 0.9
        report = evaluate(examples, probs)
        md = generate_report(report)
        assert "# Evaluation Report" in md
        assert "Micro F1" in md
        assert "dns" in md


class TestBaseline:
    def test_save_and_load(self, tmp_path):
        examples = [_make_example("1", "text", ["dns"])]
        probs = np.zeros((1, NUM_LABELS), dtype=np.float32)
        probs[0, LABEL_TO_IDX["dns"]] = 0.9
        report = evaluate(examples, probs)

        path = tmp_path / "baseline.json"
        save_baseline(report, path)
        loaded = load_baseline(path)
        assert "macro_f1" in loaded
        assert "per_label_f1" in loaded
        assert isinstance(loaded["per_label_f1"], dict)
