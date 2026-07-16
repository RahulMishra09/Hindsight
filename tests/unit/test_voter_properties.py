"""Property-based tests for the voting logic."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.incident_label import TAXONOMY_LABELS
from ml.weak_supervision.types import LFResult, Vote
from ml.weak_supervision.voter import LabelVoter, SilverLabel, compute_coverage

label_st = st.sampled_from(list(TAXONOMY_LABELS))
confidence_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
vote_st = st.sampled_from([Vote.POSITIVE, Vote.ABSTAIN])


def _lf_result_st() -> st.SearchStrategy[LFResult]:
    return st.builds(LFResult, vote=vote_st, confidence=confidence_st)


def _votes_st() -> st.SearchStrategy[dict[str, dict[str, LFResult]]]:
    inner = st.dictionaries(
        keys=st.text(min_size=1, max_size=10, alphabet="abcdefghij"),
        values=_lf_result_st(),
        min_size=0,
        max_size=5,
    )
    return st.fixed_dictionaries(dict.fromkeys(TAXONOMY_LABELS, inner))


class TestVoterProperties:
    @given(votes=_votes_st(), threshold=confidence_st, min_voters=st.integers(1, 5))
    @settings(max_examples=100)
    def test_silver_labels_are_valid_taxonomy(
        self,
        votes: dict[str, dict[str, LFResult]],
        threshold: float,
        min_voters: int,
    ) -> None:
        voter = LabelVoter(threshold=threshold, min_voters=min_voters)
        result = voter.vote(votes)
        for sl in result.silver_labels:
            assert sl.label in TAXONOMY_LABELS

    @given(votes=_votes_st(), threshold=confidence_st, min_voters=st.integers(1, 5))
    @settings(max_examples=100)
    def test_confidence_in_valid_range(
        self,
        votes: dict[str, dict[str, LFResult]],
        threshold: float,
        min_voters: int,
    ) -> None:
        voter = LabelVoter(threshold=threshold, min_voters=min_voters)
        result = voter.vote(votes)
        for sl in result.silver_labels:
            assert 0.0 <= sl.confidence <= 1.0

    @given(votes=_votes_st(), threshold=confidence_st, min_voters=st.integers(1, 5))
    @settings(max_examples=100)
    def test_no_duplicate_labels(
        self,
        votes: dict[str, dict[str, LFResult]],
        threshold: float,
        min_voters: int,
    ) -> None:
        voter = LabelVoter(threshold=threshold, min_voters=min_voters)
        result = voter.vote(votes)
        labels = [sl.label for sl in result.silver_labels]
        assert len(labels) == len(set(labels))

    @given(votes=_votes_st())
    @settings(max_examples=50)
    def test_threshold_zero_accepts_any_positive(
        self,
        votes: dict[str, dict[str, LFResult]],
    ) -> None:
        voter = LabelVoter(threshold=0.0, min_voters=1)
        result = voter.vote(votes)
        for label in TAXONOMY_LABELS:
            has_positive = any(v.vote == Vote.POSITIVE for v in votes[label].values())
            if has_positive:
                assert any(sl.label == label for sl in result.silver_labels)

    @given(votes=_votes_st())
    @settings(max_examples=50)
    def test_threshold_one_rejects_low_confidence(
        self,
        votes: dict[str, dict[str, LFResult]],
    ) -> None:
        voter = LabelVoter(threshold=1.0, min_voters=1)
        result = voter.vote(votes)
        for sl in result.silver_labels:
            assert sl.confidence >= 1.0

    @given(votes=_votes_st())
    @settings(max_examples=50)
    def test_positive_voters_are_nonempty_for_silver(
        self,
        votes: dict[str, dict[str, LFResult]],
    ) -> None:
        voter = LabelVoter(threshold=0.0, min_voters=1)
        result = voter.vote(votes)
        for sl in result.silver_labels:
            assert len(sl.positive_voters) >= 1

    @given(votes=_votes_st())
    @settings(max_examples=50)
    def test_deterministic(
        self,
        votes: dict[str, dict[str, LFResult]],
    ) -> None:
        voter = LabelVoter(threshold=0.5, min_voters=1)
        r1 = voter.vote(votes)
        r2 = voter.vote(votes)
        assert r1.silver_labels == r2.silver_labels


class TestCoverageProperties:
    @given(
        n_records=st.integers(0, 20),
        n_labels=st.integers(0, 5),
    )
    @settings(max_examples=50)
    def test_coverage_sums_correctly(
        self,
        n_records: int,
        n_labels: int,
    ) -> None:
        labels = list(TAXONOMY_LABELS)[:n_labels]
        all_silver: list[list[SilverLabel]] = []
        for _ in range(n_records):
            all_silver.append(
                [
                    SilverLabel(
                        label=lb,
                        confidence=0.8,
                        positive_voters=("kw",),
                        abstain_voters=(),
                    )
                    for lb in labels
                ]
            )
        counts = compute_coverage(all_silver)
        for lb in labels:
            assert counts[lb] == n_records
        for lb in TAXONOMY_LABELS:
            if lb not in labels:
                assert counts[lb] == 0
