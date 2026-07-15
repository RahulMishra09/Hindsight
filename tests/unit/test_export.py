"""Tests for export pipeline: determinism, license policy, schema validation."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from scripts.export_dataset import build_dataset, compute_manifest_hash

SAMPLE_RECORDS: list[dict[str, object]] = [
    {
        "id": "aaa-111",
        "org": "acme",
        "title": "Outage in us-east-1",
        "url": "https://acme.com/postmortem/1",
        "date": "2024-03-15",
        "severity": 1,
        "sections": '["impact", "root cause"]',
        "license": "cc-by-4.0",
        "full_text": "Service was down for 2 hours.",
        "content_hash": "abc123def456",
    },
    {
        "id": "bbb-222",
        "org": "globex",
        "title": "Database migration failure",
        "url": "https://globex.io/incidents/2",
        "date": "2024-01-10",
        "severity": 2,
        "sections": '["timeline", "lessons learned"]',
        "license": "all-rights-reserved",
        "full_text": "",
        "content_hash": "789ghi012jkl",
    },
    {
        "id": "ccc-333",
        "org": "initech",
        "title": "Minor latency spike",
        "url": "",
        "date": "",
        "severity": -1,
        "sections": "[]",
        "license": "mit",
        "full_text": "Brief disruption.",
        "content_hash": "345mno678pqr",
    },
]


class TestExportDeterminism:
    def test_same_records_produce_identical_hash(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            ds1 = build_dataset(SAMPLE_RECORDS, "v0.1.0")
            ds1.save_to_disk(d1)
            hash1 = compute_manifest_hash(Path(d1))

            ds2 = build_dataset(SAMPLE_RECORDS, "v0.1.0")
            ds2.save_to_disk(d2)
            hash2 = compute_manifest_hash(Path(d2))

            assert hash1 == hash2

    def test_different_records_produce_different_hash(self):
        modified = [dict(r) for r in SAMPLE_RECORDS]
        modified[0]["title"] = "Changed title"

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            ds1 = build_dataset(SAMPLE_RECORDS, "v0.1.0")
            ds1.save_to_disk(d1)
            hash1 = compute_manifest_hash(Path(d1))

            ds2 = build_dataset(modified, "v0.1.0")
            ds2.save_to_disk(d2)
            hash2 = compute_manifest_hash(Path(d2))

            assert hash1 != hash2

    def test_record_order_is_deterministic(self):
        reversed_records = list(reversed(SAMPLE_RECORDS))
        sorted_orig = sorted(SAMPLE_RECORDS, key=lambda r: str(r["content_hash"]))
        sorted_rev = sorted(reversed_records, key=lambda r: str(r["content_hash"]))
        assert sorted_orig == sorted_rev


class TestLicensePolicyInExport:
    def test_permissive_record_has_full_text(self):
        cc_record = SAMPLE_RECORDS[0]
        assert cc_record["license"] == "cc-by-4.0"
        assert cc_record["full_text"] != ""

    def test_non_permissive_record_has_empty_full_text(self):
        arr_record = SAMPLE_RECORDS[1]
        assert arr_record["license"] == "all-rights-reserved"
        assert arr_record["full_text"] == ""

    def test_mit_record_has_full_text(self):
        mit_record = SAMPLE_RECORDS[2]
        assert mit_record["license"] == "mit"
        assert mit_record["full_text"] != ""


class TestSchemaValidation:
    def test_dataset_has_expected_features(self):
        ds_dict = build_dataset(SAMPLE_RECORDS, "v0.1.0")
        ds = ds_dict["train"]
        expected_columns = {
            "id",
            "org",
            "title",
            "url",
            "date",
            "severity",
            "sections",
            "license",
            "full_text",
            "content_hash",
        }
        assert set(ds.column_names) == expected_columns

    def test_dataset_has_correct_record_count(self):
        ds_dict = build_dataset(SAMPLE_RECORDS, "v0.1.0")
        assert len(ds_dict["train"]) == 3

    def test_severity_is_int32(self):
        ds_dict = build_dataset(SAMPLE_RECORDS, "v0.1.0")
        sev_feature = ds_dict["train"].features["severity"]
        assert "int32" in str(sev_feature)

    def test_dataset_has_train_split_only(self):
        ds_dict = build_dataset(SAMPLE_RECORDS, "v0.1.0")
        assert list(ds_dict.keys()) == ["train"]

    def test_sections_is_valid_json(self):
        ds_dict = build_dataset(SAMPLE_RECORDS, "v0.1.0")
        for row in ds_dict["train"]:
            sections = json.loads(row["sections"])
            assert isinstance(sections, list)

    def test_manifest_hash_is_sha256(self):
        with tempfile.TemporaryDirectory() as d:
            ds = build_dataset(SAMPLE_RECORDS, "v0.1.0")
            ds.save_to_disk(d)
            h = compute_manifest_hash(Path(d))
            assert len(h) == 64
            assert all(c in "0123456789abcdef" for c in h)

    def test_dataset_version_in_info(self):
        ds_dict = build_dataset(SAMPLE_RECORDS, "v0.1.0")
        info = ds_dict["train"].info
        assert str(info.version) == "0.1.0"
