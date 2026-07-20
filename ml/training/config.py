"""Training configuration — pydantic-settings with env-var overrides."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAIN_MODEL_", extra="ignore")

    name: str = "microsoft/deberta-v3-base"
    max_length: int = 512
    num_labels: int = 15


class DataConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAIN_DATA_", extra="ignore")

    silver_weight: float = 0.7
    gold_weight: float = 1.0
    val_fraction: float = 0.15
    test_fraction: float = 0.15
    min_positives_per_label: int = 5
    seed: int = 42


class TrainingHyperConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAIN_", extra="ignore")

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


class LossConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAIN_LOSS_", extra="ignore")

    type: str = "bce_with_pos_weight"
    pos_weight_cap: float = 10.0


class ThresholdConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAIN_THRESHOLD_", extra="ignore")

    method: str = "per_label_f1"
    search_range: list[float] = Field(default_factory=lambda: [0.1, 0.9])
    search_steps: int = 81


class OutputConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAIN_OUTPUT_", extra="ignore")

    dir: str = "models/deberta-taxonomy"
    save_total_limit: int = 2


class TrackerConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAIN_TRACKER_", extra="ignore")

    backend: str = "wandb"
    project: str = "hindsight-taxonomy"
    offline: bool = True


class TrainPipelineConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    model: ModelConfig = Field(default_factory=ModelConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    training: TrainingHyperConfig = Field(default_factory=TrainingHyperConfig)
    loss: LossConfig = Field(default_factory=LossConfig)
    threshold: ThresholdConfig = Field(default_factory=ThresholdConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    tracker: TrackerConfig = Field(default_factory=TrackerConfig)


def load_config() -> TrainPipelineConfig:
    return TrainPipelineConfig()
