"""Push trained model + thresholds + model card to Hugging Face Hub.

Usage:
    uv run python scripts/push_model_to_hub.py \
        --repo RahuL0009/hindsight-taxonomy \
        --model-dir models/deberta-taxonomy/onnx \
        --tag v1.0.0

    uv run python scripts/push_model_to_hub.py \
        --repo RahuL0009/hindsight-taxonomy \
        --model-dir models/deberta-taxonomy/onnx \
        --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

MODEL_CARD_TEMPLATE = """---
language: en
license: apache-2.0
tags:
  - incident-classification
  - deberta-v3
  - onnx
  - multi-label
  - taxonomy
datasets:
  - RahuL0009/hindsight-corpus
metrics:
  - f1
pipeline_tag: text-classification
library_name: onnxruntime
---

# Hindsight Taxonomy Classifier

Multi-label incident taxonomy classifier based on DeBERTa-v3-base,
exported to ONNX with int8 dynamic quantization.

## Model Details

- **Architecture:** DeBERTa-v3-base + sigmoid classification head
- **Task:** Multi-label text classification (15 incident categories)
- **Export:** ONNX int8 dynamic quantization via optimum
- **Max sequence length:** 512 tokens
- **Inference target:** <30ms/doc on CPU

## Labels (15-class taxonomy)

| Label | Description |
|-------|-------------|
| config-change | Misconfiguration or feature flag change |
| retry-storm | Cascading retries amplifying load |
| cascading-failure | Failure propagating across services |
| dns | DNS resolution or routing issue |
| certificate-expiry | TLS/SSL certificate expiry or error |
| capacity-exhaustion | OOM, disk full, resource exhaustion |
| bad-deploy | Faulty deployment or rollback |
| dependency-failure | Third-party or cloud provider failure |
| network-partition | Network split, firewall, connectivity |
| database-failure | DB deadlock, replication lag, corruption |
| thundering-herd | Cache stampede or thundering herd |
| monitoring-gap | Missing or delayed alerting |
| human-error | Manual mistake or wrong environment |
| data-corruption | Data integrity or race condition |
| quota-limit | Rate limiting or quota breach |

## Training

- **Base model:** microsoft/deberta-v3-base
- **Loss:** BCE with per-label pos_weight
- **Optimizer:** AdamW, lr=2e-5
- **Epochs:** 10 (early stopping, patience 3)
- **Mixed precision:** fp16
- **Data:** Silver labels (weak supervision) + gold labels (human annotation)

## Usage

```python
import onnxruntime as ort
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("RahuL0009/hindsight-taxonomy")
session = ort.InferenceSession("model_quantized.onnx")

inputs = tokenizer("DNS resolution failure caused outage",
                    return_tensors="np", padding="max_length",
                    truncation=True, max_length=512)
outputs = session.run(None, dict(inputs))
logits = outputs[0]
```

## Limitations

- Trained on English-language incident reports only
- Best performance on structured postmortem/incident documents
- May underperform on very short texts (<50 tokens)

## Citation

```
@software{{hindsight-taxonomy,
  title = {{Hindsight Taxonomy Classifier}},
  author = {{Hindsight Contributors}},
  year = {{2026}},
  url = {{https://github.com/RahulMishra09/Hindsight}}
}}
```
"""


def _build_bundle(model_dir: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    for ext in ("*.onnx", "*.json", "*.txt", "*.model"):
        for f in model_dir.glob(ext):
            shutil.copy2(f, out_dir / f.name)

    (out_dir / "README.md").write_text(MODEL_CARD_TEMPLATE)
    return out_dir


def _push_to_hub(bundle_dir: Path, repo_id: str, tag: str) -> None:
    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(repo_id, repo_type="model", exist_ok=True)
    api.upload_folder(
        folder_path=str(bundle_dir),
        repo_id=repo_id,
        repo_type="model",
        commit_message=f"Upload model {tag}",
    )
    api.create_tag(repo_id, tag=tag, repo_type="model")
    print(f"Model pushed to https://huggingface.co/{repo_id} with tag {tag}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Push model to Hugging Face Hub")
    parser.add_argument("--repo", type=str, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--tag", type=str, default="v1.0.0")
    parser.add_argument("--bundle-dir", type=Path, default=Path("models/hub-bundle"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Building bundle from {args.model_dir}...")
    bundle = _build_bundle(args.model_dir, args.bundle_dir)
    print(f"Bundle ready at {bundle}")

    if args.dry_run:
        print("[dry-run] Would push to HF Hub. Files in bundle:")
        for f in sorted(bundle.iterdir()):
            print(f"  {f.name} ({f.stat().st_size:,} bytes)")
        return

    _push_to_hub(bundle, args.repo, args.tag)


if __name__ == "__main__":
    main()
