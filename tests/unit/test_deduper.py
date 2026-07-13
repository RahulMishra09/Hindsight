"""Tests for deduper helper functions."""

from __future__ import annotations

from app.workers.deduper import (
    _compute_band_hashes,
    _compute_minhash,
    _jaccard_from_hashvalues,
    _shingle,
)


class TestShingle:
    def test_basic_shingling(self):
        text = "the quick brown fox jumps over the lazy dog"
        shingles = _shingle(text, k=3)
        assert "the quick brown" in shingles
        assert "quick brown fox" in shingles
        assert len(shingles) == 7

    def test_short_text(self):
        text = "hello world"
        shingles = _shingle(text, k=5)
        assert shingles == {"hello world"}

    def test_single_word(self):
        shingles = _shingle("hello", k=5)
        assert shingles == {"hello"}


class TestComputeMinHash:
    def test_produces_correct_length(self):
        shingles = {"hello world", "world foo", "foo bar"}
        hv = _compute_minhash(shingles, num_perm=64)
        assert len(hv) == 64

    def test_identical_shingles_produce_same_hash(self):
        s1 = {"a b c", "b c d", "c d e"}
        s2 = {"a b c", "b c d", "c d e"}
        h1 = _compute_minhash(s1, num_perm=128)
        h2 = _compute_minhash(s2, num_perm=128)
        assert h1 == h2

    def test_different_shingles_produce_different_hash(self):
        s1 = {"a b c", "b c d", "c d e"}
        s2 = {"x y z", "y z w", "z w v"}
        h1 = _compute_minhash(s1, num_perm=128)
        h2 = _compute_minhash(s2, num_perm=128)
        assert h1 != h2


class TestComputeBandHashes:
    def test_correct_number_of_bands(self):
        hv = list(range(128))
        bands = _compute_band_hashes(hv, band_size=4)
        assert len(bands) == 32

    def test_band_prefix_format(self):
        hv = list(range(8))
        bands = _compute_band_hashes(hv, band_size=4)
        assert bands[0].startswith("b0:")
        assert bands[1].startswith("b1:")


class TestJaccardFromHashvalues:
    def test_identical_gives_one(self):
        h = [1, 2, 3, 4, 5]
        assert _jaccard_from_hashvalues(h, h) == 1.0

    def test_completely_different_gives_low(self):
        h1 = [1, 2, 3, 4, 5]
        h2 = [6, 7, 8, 9, 10]
        assert _jaccard_from_hashvalues(h1, h2) == 0.0

    def test_partial_overlap(self):
        h1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        h2 = [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]
        assert _jaccard_from_hashvalues(h1, h2) == 0.5

    def test_different_lengths(self):
        assert _jaccard_from_hashvalues([1, 2], [1, 2, 3]) == 0.0

    def test_near_duplicate_detection(self):
        base_text = "this is a long postmortem about a server outage that caused significant"
        near_dup = "this is a long postmortem about a server outage that caused major"

        s1 = _shingle(base_text, k=3)
        s2 = _shingle(near_dup, k=3)
        h1 = _compute_minhash(s1, num_perm=128)
        h2 = _compute_minhash(s2, num_perm=128)

        jaccard = _jaccard_from_hashvalues(h1, h2)
        assert jaccard > 0.5

    def test_completely_different_documents(self):
        t1 = "the server experienced a cascading failure in the database layer"
        t2 = "kubernetes pods were evicted due to memory pressure on worker nodes"

        s1 = _shingle(t1, k=3)
        s2 = _shingle(t2, k=3)
        h1 = _compute_minhash(s1, num_perm=128)
        h2 = _compute_minhash(s2, num_perm=128)

        jaccard = _jaccard_from_hashvalues(h1, h2)
        assert jaccard < 0.5
