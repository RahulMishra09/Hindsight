"""Dataset preparation — loads labels from DB, merges silver+gold, stratified split."""

from __future__ import annotations

from dataclasses import dataclass, field

from iterstrat.ml_stratifiers import MultilabelStratifiedShuffleSplit
import numpy as np

from app.models.incident_label import TAXONOMY_LABELS

LABEL_TO_IDX: dict[str, int] = {label: i for i, label in enumerate(TAXONOMY_LABELS)}
NUM_LABELS = len(TAXONOMY_LABELS)


@dataclass
class LabeledExample:
    incident_id: str
    text: str
    labels: list[int]
    weight: float = 1.0
    org: str = ""
    source: str = "silver"


@dataclass
class DatasetSplit:
    examples: list[LabeledExample] = field(default_factory=list)

    @property
    def texts(self) -> list[str]:
        return [ex.text for ex in self.examples]

    @property
    def label_matrix(self) -> np.ndarray:
        return np.array([ex.labels for ex in self.examples], dtype=np.float32)

    @property
    def weights(self) -> np.ndarray:
        return np.array([ex.weight for ex in self.examples], dtype=np.float32)

    def __len__(self) -> int:
        return len(self.examples)


def merge_silver_gold(
    silver: dict[str, set[str]],
    gold: dict[str, set[str]],
    texts: dict[str, str],
    orgs: dict[str, str],
    silver_weight: float = 0.7,
    gold_weight: float = 1.0,
) -> list[LabeledExample]:
    all_ids = set(silver.keys()) | set(gold.keys())
    examples: list[LabeledExample] = []

    for inc_id in sorted(all_ids):
        text = texts.get(inc_id, "")
        if not text.strip():
            continue

        has_gold = inc_id in gold and len(gold[inc_id]) > 0
        has_silver = inc_id in silver and len(silver[inc_id]) > 0

        if has_gold:
            label_set = gold[inc_id]
            weight = gold_weight
            source = "gold"
        elif has_silver:
            label_set = silver[inc_id]
            weight = silver_weight
            source = "silver"
        else:
            continue

        label_vec = [0] * NUM_LABELS
        for lb in label_set:
            if lb in LABEL_TO_IDX and lb != "__reviewed__":
                label_vec[LABEL_TO_IDX[lb]] = 1

        if sum(label_vec) == 0:
            continue

        examples.append(
            LabeledExample(
                incident_id=inc_id,
                text=text,
                labels=label_vec,
                weight=weight,
                org=orgs.get(inc_id, ""),
                source=source,
            )
        )

    return examples


def stratified_split(
    examples: list[LabeledExample],
    val_fraction: float = 0.15,
    test_fraction: float = 0.15,
    seed: int = 42,
) -> tuple[DatasetSplit, DatasetSplit, DatasetSplit]:
    if len(examples) < 10:
        return DatasetSplit(examples), DatasetSplit(), DatasetSplit()

    y = np.array([ex.labels for ex in examples], dtype=np.float32)
    n = len(examples)
    indices = np.arange(n)

    holdout_fraction = val_fraction + test_fraction
    if holdout_fraction >= 1.0:
        holdout_fraction = 0.3

    splitter1 = MultilabelStratifiedShuffleSplit(
        n_splits=1,
        test_size=holdout_fraction,
        random_state=seed,
    )
    train_idx, holdout_idx = next(splitter1.split(indices, y))

    val_ratio_in_holdout = val_fraction / holdout_fraction
    if len(holdout_idx) >= 4 and 0.1 < val_ratio_in_holdout < 0.9:
        y_holdout = y[holdout_idx]
        holdout_indices = np.arange(len(holdout_idx))
        splitter2 = MultilabelStratifiedShuffleSplit(
            n_splits=1,
            test_size=1.0 - val_ratio_in_holdout,
            random_state=seed,
        )
        val_local, test_local = next(splitter2.split(holdout_indices, y_holdout))
        val_idx = holdout_idx[val_local]
        test_idx = holdout_idx[test_local]
    else:
        mid = len(holdout_idx) // 2
        val_idx = holdout_idx[:mid]
        test_idx = holdout_idx[mid:]

    train = DatasetSplit([examples[i] for i in train_idx])
    val = DatasetSplit([examples[i] for i in val_idx])
    test = DatasetSplit([examples[i] for i in test_idx])

    return train, val, test


def compute_pos_weights(
    train: DatasetSplit,
    cap: float = 10.0,
) -> list[float]:
    y = train.label_matrix
    n = y.shape[0]
    if n == 0:
        return [1.0] * NUM_LABELS
    pos_counts = y.sum(axis=0)
    neg_counts = n - pos_counts
    weights: list[float] = []
    for i in range(NUM_LABELS):
        if pos_counts[i] == 0:
            weights.append(cap)
        else:
            w = float(neg_counts[i] / pos_counts[i])
            weights.append(min(w, cap))
    return weights
