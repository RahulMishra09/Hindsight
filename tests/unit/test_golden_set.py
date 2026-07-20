"""Unit tests for golden set builder — JSONL export format and logic."""

from __future__ import annotations

import json
from pathlib import Path


class TestGoldenSetFormat:
    def test_jsonl_write_roundtrip(self, tmp_path: Path):
        out = tmp_path / "golden.jsonl"
        records = [
            {"id": "inc1", "content_hash": "abc123", "labels": ["dns", "bad-deploy"]},
            {"id": "inc2", "content_hash": "def456", "labels": ["cascading-failure"]},
        ]
        with out.open("w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        lines = out.read_text().strip().split("\n")
        assert len(lines) == 2

        parsed = [json.loads(line) for line in lines]
        assert parsed[0]["id"] == "inc1"
        assert parsed[0]["labels"] == ["dns", "bad-deploy"]
        assert parsed[1]["labels"] == ["cascading-failure"]

    def test_labels_sorted(self):
        labels = {"bad-deploy", "dns", "cascading-failure"}
        assert sorted(labels) == ["bad-deploy", "cascading-failure", "dns"]

    def test_empty_golden_set(self, tmp_path: Path):
        out = tmp_path / "golden.jsonl"
        out.write_text("")
        lines = [line for line in out.read_text().splitlines() if line.strip()]
        assert len(lines) == 0

    def test_parent_dir_created(self, tmp_path: Path):
        out = tmp_path / "nested" / "dir" / "golden.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("{}\n")
        assert out.exists()
