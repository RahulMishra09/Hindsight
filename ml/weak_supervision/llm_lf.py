"""LLM-based labeling function using the Groq API (Llama 3.3 70B).

Batched zero-shot classification with strict JSON schema output.
Results are cached to disk keyed on (content_hash, prompt_version) so
re-runs are free. Rate-limit aware with exponential backoff.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any

from ml.weak_supervision.types import IncidentRecord, LFResult, Vote

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You are an incident post-mortem classifier. Given an incident report,
classify it using these labels. A report can have MULTIPLE labels.

Labels:
- config-change: caused by a configuration change (feature flag, env var, infra param)
- retry-storm: retry amplification loop overwhelming a service
- cascading-failure: failure propagating across dependent components
- dns: DNS resolution failures, misconfigurations, propagation issues
- certificate-expiry: expired/invalid/misconfigured TLS/SSL certificates
- capacity-exhaustion: resource exhaustion (disk, memory, CPU, connections, OOM)
- bad-deploy: software deployment containing a bug or regression
- dependency-failure: external or third-party service became unavailable
- network-partition: network connectivity failure, split-brain, BGP issues
- database-failure: database-specific issues (replication, deadlock, failover)
- thundering-herd: simultaneous resource access after unavailability period
- monitoring-gap: insufficient monitoring/alerting delayed detection
- human-error: manual operator mistake
- data-corruption: data integrity compromised (records lost, corrupted, inconsistent)
- quota-limit: hit a rate limit, quota, or usage cap

Respond ONLY with a JSON object:
{"labels": ["label1", "label2"], "reasoning": "brief one-line reason"}

If no labels apply, return {"labels": [], "reasoning": "no matching labels"}.
Do NOT include labels you are uncertain about — only include labels with clear evidence."""

VALID_LABELS = frozenset(
    [
        "config-change",
        "retry-storm",
        "cascading-failure",
        "dns",
        "certificate-expiry",
        "capacity-exhaustion",
        "bad-deploy",
        "dependency-failure",
        "network-partition",
        "database-failure",
        "thundering-herd",
        "monitoring-gap",
        "human-error",
        "data-corruption",
        "quota-limit",
    ]
)

DEFAULT_CACHE_DIR = Path("data/llm_cache")
LLM_CONFIDENCE = 0.85


def _cache_key(content_hash: str) -> str:
    return hashlib.sha256(f"{content_hash}:{PROMPT_VERSION}".encode()).hexdigest()[:32]


def _read_cache(cache_dir: Path, content_hash: str) -> dict[str, Any] | None:
    key = _cache_key(content_hash)
    path = cache_dir / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())  # type: ignore[no-any-return]
    return None


def _write_cache(cache_dir: Path, content_hash: str, result: dict[str, Any]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(content_hash)
    path = cache_dir / f"{key}.json"
    path.write_text(json.dumps(result, indent=2) + "\n")


def _build_user_prompt(record: IncidentRecord) -> str:
    parts = [f"Title: {record.title}"]
    if record.summary:
        parts.append(f"Summary: {record.summary[:500]}")
    body_excerpt = record.body[:2000] if record.body else ""
    if body_excerpt:
        parts.append(f"Body:\n{body_excerpt}")
    if record.sections:
        for section_name, text in record.sections.items():
            parts.append(f"[{section_name}]: {str(text)[:500]}")
    return "\n\n".join(parts)


def _parse_llm_response(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw
    parsed: dict[str, Any] = json.loads(raw)
    labels = parsed.get("labels", [])
    filtered = [lb for lb in labels if lb in VALID_LABELS]
    parsed["labels"] = filtered
    return parsed


def classify_with_llm(
    record: IncidentRecord,
    *,
    api_key: str | None = None,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    model: str = "llama-3.3-70b-versatile",
    max_retries: int = 3,
) -> dict[str, Any]:
    """Classify a single incident using the Groq API. Returns cached result if available."""
    cached = _read_cache(cache_dir, record.content_hash)
    if cached is not None:
        return cached

    resolved_key = api_key or os.environ.get("GROQ_API_KEY", "")
    if not resolved_key:
        return {"labels": [], "reasoning": "no_api_key", "source": "llm_skip"}

    import httpx

    user_prompt = _build_user_prompt(record)

    for attempt in range(max_retries):
        try:
            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {resolved_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 256,
                    "response_format": {"type": "json_object"},
                },
                timeout=30.0,
            )

            if response.status_code == 429:
                retry_after = float(response.headers.get("retry-after", str(2 ** (attempt + 1))))
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            result = _parse_llm_response(content)
            result["source"] = "llm"
            result["model"] = model
            result["prompt_version"] = PROMPT_VERSION
            _write_cache(cache_dir, record.content_hash, result)
            return result

        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            if attempt < max_retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            return {"labels": [], "reasoning": "api_error", "source": "llm_error"}

    return {"labels": [], "reasoning": "max_retries_exceeded", "source": "llm_error"}


def llm_results_to_lf_results(
    llm_result: dict[str, Any],
) -> dict[str, LFResult]:
    """Convert an LLM classification result to per-label LFResult objects."""
    out: dict[str, LFResult] = {}
    labels = llm_result.get("labels", [])
    for label in VALID_LABELS:
        if label in labels:
            out[label] = LFResult(vote=Vote.POSITIVE, confidence=LLM_CONFIDENCE)
        else:
            out[label] = LFResult(vote=Vote.ABSTAIN)
    return out
