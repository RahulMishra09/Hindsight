"""Label reconciliation: majority/confidence voting across labeling functions.

Combines keyword LFs and LLM LFs into silver labels using confidence-weighted
voting. A label is assigned if the weighted sum of POSITIVE votes exceeds
a threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.incident_label import TAXONOMY_LABELS
from ml.weak_supervision.types import IncidentRecord, LFResult, Vote


@dataclass(frozen=True, slots=True)
class SilverLabel:
    label: str
    confidence: float
    positive_voters: tuple[str, ...]
    abstain_voters: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VoteResult:
    silver_labels: list[SilverLabel]
    all_votes: dict[str, dict[str, LFResult]]


@dataclass
class LabelVoter:
    """Aggregates votes from multiple labeling functions per label."""

    threshold: float = 0.5
    min_voters: int = 1
    lf_registry: dict[str, list[tuple[str, object]]] = field(default_factory=dict)

    def register_keyword_votes(
        self,
        record: IncidentRecord,
        keyword_lfs: list[Any],
    ) -> dict[str, dict[str, LFResult]]:
        all_votes: dict[str, dict[str, LFResult]] = {lb: {} for lb in TAXONOMY_LABELS}
        for lf in keyword_lfs:
            result: LFResult = lf(record)
            label: str = lf.label
            name: str = lf.name
            all_votes[label][name] = result
        return all_votes

    def register_llm_votes(
        self,
        all_votes: dict[str, dict[str, LFResult]],
        llm_per_label: dict[str, LFResult],
    ) -> None:
        for label, result in llm_per_label.items():
            if label in all_votes:
                all_votes[label]["llm_groq"] = result

    def vote(
        self,
        all_votes: dict[str, dict[str, LFResult]],
    ) -> VoteResult:
        silver_labels: list[SilverLabel] = []
        for label in TAXONOMY_LABELS:
            label_votes = all_votes.get(label, {})
            positive_voters: list[str] = []
            abstain_voters: list[str] = []
            confidence_sum = 0.0
            total_weight = 0.0

            for name, result in label_votes.items():
                if result.vote == Vote.POSITIVE:
                    positive_voters.append(name)
                    confidence_sum += result.confidence
                    total_weight += 1.0
                else:
                    abstain_voters.append(name)

            if len(positive_voters) >= self.min_voters and total_weight > 0:
                avg_confidence = confidence_sum / total_weight
                if avg_confidence >= self.threshold:
                    silver_labels.append(
                        SilverLabel(
                            label=label,
                            confidence=round(avg_confidence, 4),
                            positive_voters=tuple(sorted(positive_voters)),
                            abstain_voters=tuple(sorted(abstain_voters)),
                        )
                    )

        return VoteResult(silver_labels=silver_labels, all_votes=all_votes)


def build_conflict_matrix(
    records_votes: list[dict[str, dict[str, LFResult]]],
) -> dict[str, dict[str, float]]:
    """Compute per-label-pair agreement rate across records."""
    labels = list(TAXONOMY_LABELS)
    co_positive: dict[str, dict[str, int]] = {a: dict.fromkeys(labels, 0) for a in labels}
    total = len(records_votes)

    for all_votes in records_votes:
        positive_labels = set()
        for label in labels:
            label_votes = all_votes.get(label, {})
            has_positive = any(v.vote == Vote.POSITIVE for v in label_votes.values())
            if has_positive:
                positive_labels.add(label)

        for a in positive_labels:
            for b in positive_labels:
                co_positive[a][b] += 1

    matrix: dict[str, dict[str, float]] = {}
    for a in labels:
        matrix[a] = {}
        for b in labels:
            matrix[a][b] = round(co_positive[a][b] / total, 4) if total > 0 else 0.0

    return matrix


def compute_coverage(
    all_silver: list[list[SilverLabel]],
) -> dict[str, int]:
    """Count silver positives per label across all records."""
    counts: dict[str, int] = dict.fromkeys(TAXONOMY_LABELS, 0)
    for record_labels in all_silver:
        for sl in record_labels:
            counts[sl.label] += 1
    return counts
