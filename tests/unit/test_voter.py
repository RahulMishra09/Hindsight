"""Unit tests for voter: majority/confidence voting and conflict matrix."""

from ml.weak_supervision.types import LFResult, Vote
from ml.weak_supervision.voter import (
    LabelVoter,
    SilverLabel,
    build_conflict_matrix,
    compute_coverage,
)


def _make_votes(
    label: str,
    votes: dict[str, tuple[Vote, float]],
) -> dict[str, dict[str, LFResult]]:
    return {label: {name: LFResult(vote=v, confidence=c) for name, (v, c) in votes.items()}}


class TestLabelVoter:
    def test_single_positive_above_threshold(self):
        voter = LabelVoter(threshold=0.5, min_voters=1)
        all_votes = _make_votes("dns", {"kw_dns": (Vote.POSITIVE, 0.9)})
        result = voter.vote(all_votes)
        assert len(result.silver_labels) == 1
        assert result.silver_labels[0].label == "dns"
        assert result.silver_labels[0].confidence == 0.9

    def test_single_positive_below_threshold(self):
        voter = LabelVoter(threshold=0.8, min_voters=1)
        all_votes = _make_votes("dns", {"kw_dns": (Vote.POSITIVE, 0.3)})
        result = voter.vote(all_votes)
        assert len(result.silver_labels) == 0

    def test_all_abstain(self):
        voter = LabelVoter(threshold=0.5, min_voters=1)
        all_votes = _make_votes("dns", {"kw_dns": (Vote.ABSTAIN, 1.0)})
        result = voter.vote(all_votes)
        assert len(result.silver_labels) == 0

    def test_multiple_positive_average_confidence(self):
        voter = LabelVoter(threshold=0.5, min_voters=1)
        all_votes = _make_votes(
            "dns",
            {
                "kw_dns": (Vote.POSITIVE, 0.7),
                "llm_groq": (Vote.POSITIVE, 0.85),
            },
        )
        result = voter.vote(all_votes)
        assert len(result.silver_labels) == 1
        assert result.silver_labels[0].confidence == round((0.7 + 0.85) / 2, 4)

    def test_min_voters_not_met(self):
        voter = LabelVoter(threshold=0.5, min_voters=2)
        all_votes = _make_votes("dns", {"kw_dns": (Vote.POSITIVE, 0.9)})
        result = voter.vote(all_votes)
        assert len(result.silver_labels) == 0

    def test_min_voters_met(self):
        voter = LabelVoter(threshold=0.5, min_voters=2)
        all_votes = _make_votes(
            "dns",
            {
                "kw_dns": (Vote.POSITIVE, 0.7),
                "llm_groq": (Vote.POSITIVE, 0.85),
            },
        )
        result = voter.vote(all_votes)
        assert len(result.silver_labels) == 1

    def test_positive_voters_tracked(self):
        voter = LabelVoter(threshold=0.5, min_voters=1)
        all_votes = _make_votes(
            "dns",
            {
                "kw_dns": (Vote.POSITIVE, 0.9),
                "llm_groq": (Vote.ABSTAIN, 1.0),
            },
        )
        result = voter.vote(all_votes)
        assert result.silver_labels[0].positive_voters == ("kw_dns",)
        assert result.silver_labels[0].abstain_voters == ("llm_groq",)


class TestConflictMatrix:
    def test_single_record_co_occurrence(self):
        all_votes = {
            "dns": {"kw": LFResult(vote=Vote.POSITIVE, confidence=0.9)},
            "config-change": {"kw": LFResult(vote=Vote.POSITIVE, confidence=0.7)},
            "bad-deploy": {"kw": LFResult(vote=Vote.ABSTAIN, confidence=1.0)},
        }
        matrix = build_conflict_matrix([all_votes])
        assert matrix["dns"]["config-change"] == 1.0
        assert matrix["config-change"]["dns"] == 1.0
        assert matrix["dns"]["bad-deploy"] == 0.0

    def test_empty_records(self):
        matrix = build_conflict_matrix([])
        for a in matrix:
            for b in matrix[a]:
                assert matrix[a][b] == 0.0


class TestComputeCoverage:
    def test_counts_per_label(self):
        all_silver = [
            [SilverLabel("dns", 0.9, ("kw",), ()), SilverLabel("bad-deploy", 0.8, ("kw",), ())],
            [SilverLabel("dns", 0.7, ("kw",), ())],
        ]
        cov = compute_coverage(all_silver)
        assert cov["dns"] == 2
        assert cov["bad-deploy"] == 1
        assert cov["config-change"] == 0

    def test_empty_records(self):
        cov = compute_coverage([])
        assert all(v == 0 for v in cov.values())
