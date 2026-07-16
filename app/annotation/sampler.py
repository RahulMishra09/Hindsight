"""Stratified sampling for annotation — ensures rare labels get coverage."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
import random
from typing import Any


def stratified_sample(
    incidents: Sequence[Any],
    silver_labels: dict[str, list[str]],
    n: int,
    *,
    seed: int = 42,
    annotated_ids: set[str] | None = None,
) -> list[Any]:
    """Sample incidents stratified by silver label so rare labels appear more often.

    Args:
        incidents: Sequence of incident objects with an `id` attribute.
        silver_labels: Mapping of incident_id → list of silver label strings.
        n: Target sample size.
        seed: RNG seed for reproducibility.
        annotated_ids: Set of already-annotated incident ids to exclude.

    Returns:
        Sampled incidents, up to `n`.
    """
    rng = random.Random(seed)  # noqa: S311
    annotated = annotated_ids or set()
    eligible = [inc for inc in incidents if str(inc.id) not in annotated]

    if not eligible:
        return []

    label_to_incidents: dict[str, list[Any]] = defaultdict(list)
    unlabeled: list[Any] = []

    for inc in eligible:
        inc_id = str(inc.id)
        labels = silver_labels.get(inc_id, [])
        if labels:
            for lb in labels:
                label_to_incidents[lb].append(inc)
        else:
            unlabeled.append(inc)

    selected_ids: set[str] = set()
    selected: list[Any] = []

    sorted_labels = sorted(label_to_incidents.keys(), key=lambda lb: len(label_to_incidents[lb]))
    while len(selected) < n and sorted_labels:
        prev_count = len(selected)
        for lb in sorted_labels:
            if len(selected) >= n:
                break
            candidates = [inc for inc in label_to_incidents[lb] if str(inc.id) not in selected_ids]
            if candidates:
                pick = rng.choice(candidates)
                selected_ids.add(str(pick.id))
                selected.append(pick)

        if len(selected) == prev_count:
            break
        sorted_labels = [
            lb
            for lb in sorted_labels
            if any(str(inc.id) not in selected_ids for inc in label_to_incidents[lb])
        ]

    if len(selected) < n and unlabeled:
        remaining_unlabeled = [inc for inc in unlabeled if str(inc.id) not in selected_ids]
        rng.shuffle(remaining_unlabeled)
        for inc in remaining_unlabeled[: n - len(selected)]:
            selected.append(inc)

    return selected[:n]
