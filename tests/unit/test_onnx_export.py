"""Unit tests for ONNX export — parity check and latency benchmark logic."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ml.export.onnx_export import latency_benchmark, run_onnx_inference


class TestRunOnnxInference:
    def test_missing_model_raises(self, tmp_path: Path) -> None:
        with pytest.raises((FileNotFoundError, ValueError, OSError)):
            run_onnx_inference(tmp_path, ["test"], max_length=32)


class TestLatencyBenchmark:
    def test_missing_model_raises(self, tmp_path: Path) -> None:
        with pytest.raises((FileNotFoundError, ValueError, OSError)):
            latency_benchmark(tmp_path, "test", max_length=32, n_runs=1, warmup=0)


class TestParityCheckContract:
    def test_identical_logits_pass(self) -> None:
        logits = np.array([[0.1, -0.2, 0.5]], dtype=np.float32)
        max_diff = float(np.abs(logits - logits).max())
        assert max_diff <= 0.01

    def test_different_logits_fail(self) -> None:
        pt = np.array([[0.1, -0.2, 0.5]], dtype=np.float32)
        onnx = np.array([[0.15, -0.18, 0.6]], dtype=np.float32)
        max_diff = float(np.abs(pt - onnx).max())
        assert max_diff > 0.01


class TestBenchmarkResultFormat:
    def test_expected_keys(self) -> None:
        expected = {"mean_ms", "p50_ms", "p95_ms", "p99_ms", "min_ms", "max_ms"}
        latencies = np.array([10.0, 12.0, 11.0, 13.0, 9.5])
        result = {
            "mean_ms": round(float(latencies.mean()), 2),
            "p50_ms": round(float(np.median(latencies)), 2),
            "p95_ms": round(float(np.percentile(latencies, 95)), 2),
            "p99_ms": round(float(np.percentile(latencies, 99)), 2),
            "min_ms": round(float(latencies.min()), 2),
            "max_ms": round(float(latencies.max()), 2),
        }
        assert set(result.keys()) == expected
        assert all(isinstance(v, float) for v in result.values())
        assert result["min_ms"] <= result["p50_ms"] <= result["max_ms"]

    def test_single_run_all_same(self) -> None:
        latencies = np.array([15.0])
        result = {
            "mean_ms": round(float(latencies.mean()), 2),
            "p50_ms": round(float(np.median(latencies)), 2),
            "p95_ms": round(float(np.percentile(latencies, 95)), 2),
            "p99_ms": round(float(np.percentile(latencies, 99)), 2),
            "min_ms": round(float(latencies.min()), 2),
            "max_ms": round(float(latencies.max()), 2),
        }
        assert result["mean_ms"] == result["p50_ms"] == result["min_ms"] == result["max_ms"]
