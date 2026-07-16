"""Unit tests for LLM labeling function — cache, parsing, prompt building."""

from pathlib import Path
import tempfile

from ml.weak_supervision.llm_lf import (
    LLM_CONFIDENCE,
    VALID_LABELS,
    _build_user_prompt,
    _cache_key,
    _parse_llm_response,
    _read_cache,
    _write_cache,
    classify_with_llm,
    llm_results_to_lf_results,
)
from ml.weak_supervision.types import IncidentRecord, Vote


def _record(body: str = "test body", title: str = "test") -> IncidentRecord:
    return IncidentRecord(
        content_hash="abc123",
        title=title,
        summary=body[:200],
        body=body,
        sections={"root_cause": "A DNS issue"},
    )


class TestCacheKeyDeterminism:
    def test_same_hash_same_key(self):
        k1 = _cache_key("abc123")
        k2 = _cache_key("abc123")
        assert k1 == k2

    def test_different_hash_different_key(self):
        k1 = _cache_key("abc123")
        k2 = _cache_key("def456")
        assert k1 != k2


class TestCacheReadWrite:
    def test_write_then_read(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            data = {"labels": ["dns"], "reasoning": "test"}
            _write_cache(cache_dir, "hash1", data)
            result = _read_cache(cache_dir, "hash1")
            assert result == data

    def test_read_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            result = _read_cache(Path(d), "nonexistent")
            assert result is None


class TestParseLLMResponse:
    def test_valid_json(self):
        raw = '{"labels": ["dns", "config-change"], "reasoning": "DNS misconfiguration"}'
        result = _parse_llm_response(raw)
        assert result["labels"] == ["dns", "config-change"]

    def test_filters_invalid_labels(self):
        raw = '{"labels": ["dns", "fake-label", "bad-deploy"], "reasoning": "test"}'
        result = _parse_llm_response(raw)
        assert result["labels"] == ["dns", "bad-deploy"]

    def test_code_block_wrapper(self):
        raw = '```json\n{"labels": ["dns"], "reasoning": "test"}\n```'
        result = _parse_llm_response(raw)
        assert result["labels"] == ["dns"]

    def test_empty_labels(self):
        raw = '{"labels": [], "reasoning": "no matching labels"}'
        result = _parse_llm_response(raw)
        assert result["labels"] == []


class TestBuildUserPrompt:
    def test_includes_title(self):
        r = _record(title="Major DNS Outage")
        prompt = _build_user_prompt(r)
        assert "Major DNS Outage" in prompt

    def test_includes_sections(self):
        r = _record()
        prompt = _build_user_prompt(r)
        assert "[root_cause]" in prompt

    def test_truncates_body(self):
        r = _record(body="x" * 5000)
        prompt = _build_user_prompt(r)
        assert len(prompt) < 5000


class TestClassifyWithLlmCache:
    def test_returns_cached_result(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            cached = {"labels": ["dns"], "reasoning": "cached", "source": "llm"}
            _write_cache(cache_dir, "abc123", cached)
            r = _record()
            result = classify_with_llm(r, cache_dir=cache_dir)
            assert result == cached

    def test_no_api_key_returns_skip(self):
        with tempfile.TemporaryDirectory() as d:
            r = _record()
            result = classify_with_llm(r, api_key="", cache_dir=Path(d))
            assert result["source"] == "llm_skip"


class TestLLMResultsToLFResults:
    def test_positive_labels(self):
        llm_result = {"labels": ["dns", "config-change"]}
        lf_results = llm_results_to_lf_results(llm_result)
        assert lf_results["dns"].vote == Vote.POSITIVE
        assert lf_results["dns"].confidence == LLM_CONFIDENCE
        assert lf_results["config-change"].vote == Vote.POSITIVE

    def test_abstain_labels(self):
        llm_result = {"labels": ["dns"]}
        lf_results = llm_results_to_lf_results(llm_result)
        assert lf_results["bad-deploy"].vote == Vote.ABSTAIN

    def test_all_labels_present(self):
        llm_result = {"labels": []}
        lf_results = llm_results_to_lf_results(llm_result)
        assert set(lf_results.keys()) == VALID_LABELS


class TestValidLabels:
    def test_label_count(self):
        assert len(VALID_LABELS) == 15
