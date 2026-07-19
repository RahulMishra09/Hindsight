"""TaxonomyClassifier — long-doc handling with per-section inference and max-pool."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.models.incident_label import TAXONOMY_LABELS
from ml.training.data import NUM_LABELS

MAX_SECTION_CHARS = 100_000


class TaxonomyClassifier:
    def __init__(
        self,
        model_dir: Path,
        max_length: int = 512,
        batch_size: int = 32,
    ) -> None:
        self.model_dir = model_dir
        self.max_length = max_length
        self.batch_size = batch_size

        self.tokenizer = AutoTokenizer.from_pretrained(str(model_dir))  # type: ignore[no-untyped-call]
        self.model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
        self.model.eval()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        thresholds_path = model_dir / "thresholds.json"
        if thresholds_path.exists():
            raw = json.loads(thresholds_path.read_text())
            self.thresholds = np.array(
                [raw.get(lb, 0.5) for lb in TAXONOMY_LABELS], dtype=np.float32
            )
        else:
            self.thresholds = np.full(NUM_LABELS, 0.5, dtype=np.float32)

    def _predict_logits_batch(self, texts: list[str]) -> np.ndarray:
        all_logits: list[np.ndarray] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            enc = self.tokenizer(
                batch,
                padding="max_length",
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            ).to(self.device)
            with torch.no_grad():
                outputs = self.model(**enc)
            all_logits.append(outputs.logits.cpu().numpy())
        return np.concatenate(all_logits, axis=0)

    @staticmethod
    def split_sections(
        title: str | None,
        summary: str | None,
        sections: dict[str, object] | list[str] | None,
    ) -> list[str]:
        chunks: list[str] = []

        header_parts: list[str] = []
        if title:
            header_parts.append(title)
        if summary:
            header_parts.append(summary)
        if header_parts:
            chunks.append("\n\n".join(header_parts))

        if isinstance(sections, dict):
            for val in sections.values():
                if isinstance(val, str) and val.strip():
                    chunks.append(val[:MAX_SECTION_CHARS])
        elif isinstance(sections, list):
            for item in sections:
                if isinstance(item, str) and item.strip():
                    chunks.append(item[:MAX_SECTION_CHARS])

        if not chunks:
            fallback = " ".join(filter(None, [title, summary]))
            if fallback.strip():
                chunks.append(fallback)

        return chunks

    def classify_sections(self, chunks: list[str]) -> tuple[np.ndarray, np.ndarray]:
        if not chunks:
            return (
                np.zeros(NUM_LABELS, dtype=np.float32),
                np.zeros(NUM_LABELS, dtype=np.float32),
            )

        logits = self._predict_logits_batch(chunks)
        probs = 1.0 / (1.0 + np.exp(-logits))

        pooled_probs = probs.max(axis=0)
        labels = (pooled_probs >= self.thresholds).astype(np.float32)
        return pooled_probs, labels

    def classify_text(self, text: str) -> tuple[np.ndarray, np.ndarray]:
        logits = self._predict_logits_batch([text])
        probs = 1.0 / (1.0 + np.exp(-logits))
        pooled_probs = probs[0]
        labels = (pooled_probs >= self.thresholds).astype(np.float32)
        return pooled_probs, labels

    def classify_incident(
        self,
        title: str | None,
        summary: str | None,
        sections: dict[str, object] | list[str] | None,
    ) -> tuple[np.ndarray, np.ndarray, list[str]]:
        chunks = self.split_sections(title, summary, sections)
        probs, labels = self.classify_sections(chunks)
        active_labels = [TAXONOMY_LABELS[i] for i in range(NUM_LABELS) if labels[i] > 0.5]
        return probs, labels, active_labels
