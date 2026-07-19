"""ONNX export — convert PyTorch model to ONNX with int8 dynamic quantization.

Usage:
    uv run python -m ml.export.onnx_export --model models/deberta-taxonomy/best
    uv run python -m ml.export.onnx_export --model models/deberta-taxonomy/best \
        --out models/deberta-taxonomy/onnx
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import time

import numpy as np
import onnxruntime as ort
from optimum.onnxruntime import ORTModelForSequenceClassification, ORTQuantizer
from optimum.onnxruntime.configuration import AutoQuantizationConfig
from transformers import AutoTokenizer


def export_onnx(model_dir: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    ort_model = ORTModelForSequenceClassification.from_pretrained(str(model_dir), export=True)
    ort_model.save_pretrained(str(out_dir))

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))  # type: ignore[no-untyped-call]
    tokenizer.save_pretrained(str(out_dir))

    thresholds_src = model_dir / "thresholds.json"
    if thresholds_src.exists():
        shutil.copy2(thresholds_src, out_dir / "thresholds.json")

    return out_dir


def quantize_int8(onnx_dir: Path) -> Path:
    quantizer = ORTQuantizer.from_pretrained(str(onnx_dir))
    qconfig = AutoQuantizationConfig.avx2(is_static=False)
    quantizer.quantize(save_dir=str(onnx_dir), quantization_config=qconfig)
    return onnx_dir


def run_onnx_inference(
    onnx_dir: Path,
    texts: list[str],
    max_length: int = 512,
    batch_size: int = 32,
) -> np.ndarray:
    tokenizer = AutoTokenizer.from_pretrained(str(onnx_dir))  # type: ignore[no-untyped-call]

    onnx_files = list(onnx_dir.glob("*.onnx"))
    model_path = None
    for f in onnx_files:
        if "quantized" in f.name or "model" in f.name:
            model_path = f
            break
    if model_path is None and onnx_files:
        model_path = onnx_files[0]
    if model_path is None:
        raise FileNotFoundError(f"No ONNX model found in {onnx_dir}")

    session = ort.InferenceSession(
        str(model_path),
        providers=["CPUExecutionProvider"],
    )

    all_logits: list[np.ndarray] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        enc = tokenizer(
            batch,
            padding="max_length",
            truncation=True,
            max_length=max_length,
            return_tensors="np",
        )
        feeds = {k: v for k, v in enc.items() if k in [inp.name for inp in session.get_inputs()]}
        outputs = session.run(None, feeds)
        all_logits.append(outputs[0])

    return np.concatenate(all_logits, axis=0)


def parity_check(
    pytorch_dir: Path,
    onnx_dir: Path,
    texts: list[str],
    max_length: int = 512,
    atol: float = 0.01,
) -> tuple[bool, float]:
    from ml.training.threshold import predict_logits

    pt_logits = predict_logits(pytorch_dir, texts, max_length)
    onnx_logits = run_onnx_inference(onnx_dir, texts, max_length)

    max_diff = float(np.abs(pt_logits - onnx_logits).max())
    return max_diff <= atol, max_diff


def latency_benchmark(
    onnx_dir: Path,
    text: str,
    max_length: int = 512,
    n_runs: int = 50,
    warmup: int = 5,
) -> dict[str, float]:
    tokenizer = AutoTokenizer.from_pretrained(str(onnx_dir))  # type: ignore[no-untyped-call]

    onnx_files = list(onnx_dir.glob("*.onnx"))
    model_path = None
    for f in onnx_files:
        if "quantized" in f.name or "model" in f.name:
            model_path = f
            break
    if model_path is None and onnx_files:
        model_path = onnx_files[0]
    if model_path is None:
        raise FileNotFoundError(f"No ONNX model found in {onnx_dir}")

    session = ort.InferenceSession(
        str(model_path),
        providers=["CPUExecutionProvider"],
    )

    enc = tokenizer(
        [text],
        padding="max_length",
        truncation=True,
        max_length=max_length,
        return_tensors="np",
    )
    feeds = {k: v for k, v in enc.items() if k in [inp.name for inp in session.get_inputs()]}

    for _ in range(warmup):
        session.run(None, feeds)

    latencies: list[float] = []
    for _ in range(n_runs):
        start = time.perf_counter()
        session.run(None, feeds)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

    arr = np.array(latencies)
    return {
        "mean_ms": round(float(arr.mean()), 2),
        "p50_ms": round(float(np.median(arr)), 2),
        "p95_ms": round(float(np.percentile(arr, 95)), 2),
        "p99_ms": round(float(np.percentile(arr, 99)), 2),
        "min_ms": round(float(arr.min()), 2),
        "max_ms": round(float(arr.max()), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export and quantize ONNX model")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--skip-quantize", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--parity", action="store_true")
    args = parser.parse_args()

    out_dir = args.out or args.model.parent / "onnx"

    print(f"Exporting ONNX to {out_dir}...")
    export_onnx(args.model, out_dir)
    print("ONNX export complete.")

    if not args.skip_quantize:
        print("Applying int8 dynamic quantization...")
        quantize_int8(out_dir)
        print("Quantization complete.")

    if args.parity:
        test_texts = [
            "DNS resolution failure caused a major outage affecting all services.",
            "A bad deployment was rolled back after 30 minutes of downtime.",
        ]
        passed, max_diff = parity_check(args.model, out_dir, test_texts)
        status = "PASSED" if passed else "FAILED"
        print(f"Parity check: {status} (max diff: {max_diff:.6f})")

    if args.benchmark:
        sample = "DNS resolution failure caused a major outage affecting all services."
        results = latency_benchmark(out_dir, sample)
        print("Latency benchmark (CPU, single doc):")
        for k, v in results.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
