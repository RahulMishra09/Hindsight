"""Unit tests for training pipeline — data preparation and config."""

import numpy as np

from ml.training.config import TrainPipelineConfig, load_config
from ml.training.data import (
    LABEL_TO_IDX,
    NUM_LABELS,
    DatasetSplit,
    LabeledExample,
    compute_pos_weights,
    merge_silver_gold,
    stratified_split,
)


class TestConfig:
    def test_load_default_config(self):
        cfg = load_config()
        assert cfg.model.name == "microsoft/deberta-v3-base"
        assert cfg.model.num_labels == 15
        assert cfg.training.batch_size == 16
        assert cfg.data.seed == 42

    def test_load_nonexistent_path(self, tmp_path):
        cfg = load_config(tmp_path / "no_such_file.yaml")
        assert isinstance(cfg, TrainPipelineConfig)

    def test_load_yaml(self, tmp_path):
        yaml_content = """
model:
  name: "test-model"
  max_length: 256
  num_labels: 15
data:
  seed: 99
training:
  batch_size: 8
  num_epochs: 3
"""
        f = tmp_path / "test_config.yaml"
        f.write_text(yaml_content)
        cfg = load_config(f)
        assert cfg.model.name == "test-model"
        assert cfg.model.max_length == 256
        assert cfg.data.seed == 99
        assert cfg.training.batch_size == 8


class TestMergeSilverGold:
    def test_gold_overrides_silver(self):
        silver = {"inc1": {"dns", "bad-deploy"}}
        gold = {"inc1": {"dns"}}
        texts = {"inc1": "Some text about DNS failure"}
        orgs = {"inc1": "acme"}
        result = merge_silver_gold(silver, gold, texts, orgs)
        assert len(result) == 1
        ex = result[0]
        assert ex.labels[LABEL_TO_IDX["dns"]] == 1
        assert ex.labels[LABEL_TO_IDX["bad-deploy"]] == 0
        assert ex.source == "gold"
        assert ex.weight == 1.0

    def test_silver_used_when_no_gold(self):
        silver = {"inc1": {"retry-storm"}}
        gold = {}
        texts = {"inc1": "Retry storm happened"}
        orgs = {"inc1": "foo"}
        result = merge_silver_gold(silver, gold, texts, orgs)
        assert len(result) == 1
        assert result[0].source == "silver"
        assert result[0].weight == 0.7

    def test_empty_text_excluded(self):
        silver = {"inc1": {"dns"}}
        gold = {}
        texts = {"inc1": "   "}
        orgs = {"inc1": "x"}
        result = merge_silver_gold(silver, gold, texts, orgs)
        assert len(result) == 0

    def test_reviewed_marker_excluded(self):
        silver = {}
        gold = {"inc1": {"__reviewed__"}}
        texts = {"inc1": "Some text"}
        orgs = {"inc1": "x"}
        result = merge_silver_gold(silver, gold, texts, orgs)
        assert len(result) == 0

    def test_multiple_labels(self):
        silver = {}
        gold = {"inc1": {"dns", "cascading-failure", "network-partition"}}
        texts = {"inc1": "DNS caused cascade and partition"}
        orgs = {"inc1": "y"}
        result = merge_silver_gold(silver, gold, texts, orgs)
        assert len(result) == 1
        assert sum(result[0].labels) == 3


class TestStratifiedSplit:
    def _make_examples(self, n=50):
        examples = []
        labels_cycle = list(LABEL_TO_IDX.keys())
        for i in range(n):
            label_vec = [0] * NUM_LABELS
            label_vec[i % NUM_LABELS] = 1
            examples.append(
                LabeledExample(
                    incident_id=str(i),
                    text=f"Text for incident {i} about {labels_cycle[i % NUM_LABELS]}",
                    labels=label_vec,
                    org="test",
                )
            )
        return examples

    def test_split_sizes(self):
        examples = self._make_examples(100)
        train, val, test = stratified_split(examples, 0.15, 0.15)
        assert len(train) + len(val) + len(test) == 100
        assert len(val) > 0
        assert len(test) > 0

    def test_deterministic(self):
        examples = self._make_examples(60)
        t1, v1, _ = stratified_split(examples, 0.15, 0.15, seed=42)
        t2, v2, _ = stratified_split(examples, 0.15, 0.15, seed=42)
        assert [e.incident_id for e in t1.examples] == [e.incident_id for e in t2.examples]
        assert [e.incident_id for e in v1.examples] == [e.incident_id for e in v2.examples]

    def test_small_dataset_returns_all_train(self):
        examples = self._make_examples(5)
        train, val, test = stratified_split(examples)
        assert len(train) == 5
        assert len(val) == 0
        assert len(test) == 0


class TestPosWeights:
    def test_balanced(self):
        labels = [[1, 0] + [0] * 13, [0, 1] + [0] * 13, [1, 0] + [0] * 13, [0, 1] + [0] * 13]
        examples = [
            LabeledExample(incident_id=str(i), text="t", labels=labels[i]) for i in range(4)
        ]
        split = DatasetSplit(examples)
        weights = compute_pos_weights(split, cap=10.0)
        assert weights[0] == 1.0
        assert weights[1] == 1.0

    def test_cap_applied(self):
        labels = [[1] + [0] * 14] + [[0] * 15] * 99
        examples = [
            LabeledExample(incident_id=str(i), text="t", labels=labels[i]) for i in range(100)
        ]
        split = DatasetSplit(examples)
        weights = compute_pos_weights(split, cap=10.0)
        assert weights[0] == 10.0

    def test_empty_split(self):
        split = DatasetSplit([])
        weights = compute_pos_weights(split)
        assert len(weights) == NUM_LABELS
        assert all(w == 1.0 for w in weights)


class TestDatasetSplit:
    def test_properties(self):
        examples = [
            LabeledExample(incident_id="1", text="hello", labels=[1, 0, 0] + [0] * 12, weight=0.8),
            LabeledExample(incident_id="2", text="world", labels=[0, 1, 0] + [0] * 12, weight=1.0),
        ]
        split = DatasetSplit(examples)
        assert split.texts == ["hello", "world"]
        assert split.label_matrix.shape == (2, NUM_LABELS)
        assert split.weights.dtype == np.float32
        assert len(split) == 2
