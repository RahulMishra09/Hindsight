"""Training configuration loader — reads YAML, validates, provides typed access."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ModelConfig:
    name: str = "microsoft/deberta-v3-base"
    max_length: int = 512
    num_labels: int = 15


@dataclass(frozen=True)
class DataConfig:
    silver_weight: float = 0.7
    gold_weight: float = 1.0
    val_fraction: float = 0.15
    test_fraction: float = 0.15
    min_positives_per_label: int = 5
    seed: int = 42


@dataclass(frozen=True)
class TrainingConfig:
    batch_size: int = 16
    eval_batch_size: int = 32
    learning_rate: float = 2e-5
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    num_epochs: int = 10
    early_stopping_patience: int = 3
    fp16: bool = True
    gradient_accumulation_steps: int = 2
    max_grad_norm: float = 1.0
    seed: int = 42


@dataclass(frozen=True)
class LossConfig:
    type: str = "bce_with_pos_weight"
    pos_weight_cap: float = 10.0


@dataclass(frozen=True)
class ThresholdConfig:
    method: str = "per_label_f1"
    search_range: list[float] = field(default_factory=lambda: [0.1, 0.9])
    search_steps: int = 81


@dataclass(frozen=True)
class OutputConfig:
    dir: str = "models/deberta-taxonomy"
    save_total_limit: int = 2


@dataclass(frozen=True)
class TrackerConfig:
    backend: str = "wandb"
    project: str = "hindsight-taxonomy"
    offline: bool = True


@dataclass(frozen=True)
class TrainPipelineConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    loss: LossConfig = field(default_factory=LossConfig)
    threshold: ThresholdConfig = field(default_factory=ThresholdConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    tracker: TrackerConfig = field(default_factory=TrackerConfig)


def load_config(path: Path | None = None) -> TrainPipelineConfig:
    if path is None:
        path = Path(__file__).parent / "config.yaml"
    if not path.exists():
        return TrainPipelineConfig()

    raw = yaml.safe_load(path.read_text())
    if not raw:
        return TrainPipelineConfig()

    return TrainPipelineConfig(
        model=ModelConfig(**raw.get("model", {})),
        data=DataConfig(**raw.get("data", {})),
        training=TrainingConfig(**raw.get("training", {})),
        loss=LossConfig(**raw.get("loss", {})),
        threshold=ThresholdConfig(**raw.get("threshold", {})),
        output=OutputConfig(**raw.get("output", {})),
        tracker=TrackerConfig(**raw.get("tracker", {})),
    )
