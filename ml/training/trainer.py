"""DeBERTa multi-label trainer — wraps HuggingFace Trainer with BCE loss."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset as TorchDataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    PreTrainedTokenizerBase,
    Trainer,
    TrainingArguments,
)

from app.models.incident_label import TAXONOMY_LABELS
from ml.training.config import TrainPipelineConfig
from ml.training.data import DatasetSplit, compute_pos_weights


class MultiLabelDataset(TorchDataset):  # type: ignore[type-arg]
    def __init__(
        self,
        texts: list[str],
        labels: np.ndarray,
        weights: np.ndarray,
        tokenizer: PreTrainedTokenizerBase,
        max_length: int = 512,
    ) -> None:
        self.encodings = tokenizer(
            texts,
            padding="max_length",
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        )
        self.labels = torch.tensor(labels, dtype=torch.float32)
        self.weights = torch.tensor(weights, dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        item = {k: v[idx] for k, v in self.encodings.items()}
        item["labels"] = self.labels[idx]
        item["sample_weight"] = self.weights[idx]
        return item


class WeightedBCETrainer(Trainer):
    def __init__(self, pos_weight: torch.Tensor | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.pos_weight = pos_weight

    def compute_loss(  # type: ignore[override]
        self,
        model: Any,
        inputs: dict[str, Any],
        return_outputs: bool = False,
        **kwargs: Any,
    ) -> Any:
        labels = inputs.pop("labels")
        sample_weight = inputs.pop("sample_weight", None)
        outputs = model(**inputs)
        logits = outputs.logits

        pw = self.pos_weight.to(logits.device) if self.pos_weight is not None else None
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=pw, reduction="none")
        loss = loss_fn(logits, labels)

        if sample_weight is not None:
            loss = loss * sample_weight.unsqueeze(1)

        loss = loss.mean()
        return (loss, outputs) if return_outputs else loss


def build_datasets(
    train: DatasetSplit,
    val: DatasetSplit,
    tokenizer: PreTrainedTokenizerBase,
    max_length: int,
) -> tuple[MultiLabelDataset, MultiLabelDataset]:
    train_ds = MultiLabelDataset(
        train.texts,
        train.label_matrix,
        train.weights,
        tokenizer,
        max_length,
    )
    val_ds = MultiLabelDataset(
        val.texts,
        val.label_matrix,
        val.weights,
        tokenizer,
        max_length,
    )
    return train_ds, val_ds


def compute_metrics(eval_pred: Any) -> dict[str, float]:
    logits, labels = eval_pred
    probs = 1 / (1 + np.exp(-logits))
    preds = (probs > 0.5).astype(np.float32)

    tp = (preds * labels).sum(axis=0)
    fp = (preds * (1 - labels)).sum(axis=0)
    fn = ((1 - preds) * labels).sum(axis=0)

    precision = np.where(tp + fp > 0, tp / (tp + fp), 0.0)
    recall = np.where(tp + fn > 0, tp / (tp + fn), 0.0)
    f1 = np.where(
        precision + recall > 0,
        2 * precision * recall / (precision + recall),
        0.0,
    )

    micro_tp = tp.sum()
    micro_fp = fp.sum()
    micro_fn = fn.sum()
    micro_p = micro_tp / (micro_tp + micro_fp) if (micro_tp + micro_fp) > 0 else 0.0
    micro_r = micro_tp / (micro_tp + micro_fn) if (micro_tp + micro_fn) > 0 else 0.0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0

    metrics: dict[str, float] = {
        "micro_f1": float(micro_f1),
        "macro_f1": float(f1.mean()),
    }
    for i, label in enumerate(TAXONOMY_LABELS):
        metrics[f"f1_{label}"] = float(f1[i])

    return metrics


def run_training(
    cfg: TrainPipelineConfig,
    train_split: DatasetSplit,
    val_split: DatasetSplit,
) -> Path:
    output_dir = Path(cfg.output.dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(cfg.model.name)  # type: ignore[no-untyped-call]
    model = AutoModelForSequenceClassification.from_pretrained(
        cfg.model.name,
        num_labels=cfg.model.num_labels,
        problem_type="multi_label_classification",
    )

    train_ds, val_ds = build_datasets(train_split, val_split, tokenizer, cfg.model.max_length)

    pos_weights = compute_pos_weights(train_split, cap=cfg.loss.pos_weight_cap)
    pos_weight_tensor = torch.tensor(pos_weights, dtype=torch.float32)

    report_to = "none"
    if cfg.tracker.backend == "wandb":
        try:
            import wandb  # noqa: F401

            report_to = "wandb"
        except ImportError:
            report_to = "none"

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=cfg.training.num_epochs,
        per_device_train_batch_size=cfg.training.batch_size,
        per_device_eval_batch_size=cfg.training.eval_batch_size,
        learning_rate=cfg.training.learning_rate,
        weight_decay=cfg.training.weight_decay,
        warmup_ratio=cfg.training.warmup_ratio,
        fp16=cfg.training.fp16 and torch.cuda.is_available(),
        gradient_accumulation_steps=cfg.training.gradient_accumulation_steps,
        max_grad_norm=cfg.training.max_grad_norm,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=cfg.output.save_total_limit,
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        seed=cfg.training.seed,
        report_to=report_to,
        logging_steps=10,
        dataloader_num_workers=0,
    )

    callbacks = [
        EarlyStoppingCallback(early_stopping_patience=cfg.training.early_stopping_patience)
    ]

    trainer = WeightedBCETrainer(
        pos_weight=pos_weight_tensor,
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
        callbacks=callbacks,
    )

    trainer.train()

    best_dir = output_dir / "best"
    best_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(best_dir))
    tokenizer.save_pretrained(str(best_dir))

    label_names = list(TAXONOMY_LABELS)
    id2label = {str(i): label for i, label in enumerate(label_names)}
    label2id = {label: str(i) for i, label in enumerate(label_names)}

    model.config.id2label = id2label
    model.config.label2id = label2id
    model.config.save_pretrained(str(best_dir))

    return best_dir
