"""Unit tests for inter-annotator agreement metrics."""

from __future__ import annotations

from scripts.agreement import _compute_agreement, cohens_kappa, krippendorffs_alpha


class TestCohensKappa:
    def test_perfect_agreement(self) -> None:
        y1 = [1, 0, 1, 0, 1]
        y2 = [1, 0, 1, 0, 1]
        assert cohens_kappa(y1, y2) == 1.0

    def test_no_agreement_beyond_chance(self) -> None:
        y1 = [1, 1, 0, 0]
        y2 = [0, 0, 1, 1]
        kappa = cohens_kappa(y1, y2)
        assert kappa < 0.0

    def test_moderate_agreement(self) -> None:
        y1 = [1, 1, 0, 0, 1, 0]
        y2 = [1, 0, 0, 0, 1, 0]
        kappa = cohens_kappa(y1, y2)
        assert 0.4 < kappa < 1.0

    def test_empty_input(self) -> None:
        assert cohens_kappa([], []) == 0.0

    def test_all_same_class(self) -> None:
        y1 = [0, 0, 0]
        y2 = [0, 0, 0]
        assert cohens_kappa(y1, y2) == 1.0


class TestKrippendorffsAlpha:
    def test_perfect_agreement(self) -> None:
        units = {
            "u1": {"a1": 1, "a2": 1},
            "u2": {"a1": 0, "a2": 0},
            "u3": {"a1": 1, "a2": 1},
        }
        assert krippendorffs_alpha(units) == 1.0

    def test_no_agreement(self) -> None:
        units = {
            "u1": {"a1": 1, "a2": 0},
            "u2": {"a1": 0, "a2": 1},
        }
        alpha = krippendorffs_alpha(units)
        assert alpha < 0.0

    def test_empty_input(self) -> None:
        assert krippendorffs_alpha({}) == 0.0

    def test_single_annotator_units_excluded(self) -> None:
        units = {
            "u1": {"a1": 1},
            "u2": {"a1": 0},
        }
        assert krippendorffs_alpha(units) == 0.0

    def test_three_annotators(self) -> None:
        units = {
            "u1": {"a1": 1, "a2": 1, "a3": 1},
            "u2": {"a1": 0, "a2": 0, "a3": 0},
        }
        assert krippendorffs_alpha(units) == 1.0


class TestComputeAgreement:
    def test_no_doubly_annotated(self) -> None:
        annotations: dict[str, dict[str, set[str]]] = {
            "inc1": {"user1": {"dns"}},
            "inc2": {"user1": {"bad-deploy"}},
        }
        kappa, alpha = _compute_agreement(annotations)
        assert kappa == {}
        assert alpha == 0.0

    def test_perfect_overlap(self) -> None:
        annotations: dict[str, dict[str, set[str]]] = {
            "inc1": {"user1": {"dns"}, "user2": {"dns"}},
            "inc2": {"user1": {"bad-deploy"}, "user2": {"bad-deploy"}},
        }
        kappa, alpha = _compute_agreement(annotations)
        assert kappa["dns"] == 1.0
        assert kappa["bad-deploy"] == 1.0
        assert alpha == 1.0

    def test_partial_disagreement(self) -> None:
        annotations: dict[str, dict[str, set[str]]] = {
            "inc1": {"user1": {"dns"}, "user2": {"bad-deploy"}},
            "inc2": {"user1": {"dns"}, "user2": {"dns"}},
        }
        kappa, alpha = _compute_agreement(annotations)
        assert kappa["dns"] < 1.0
        assert alpha < 1.0
