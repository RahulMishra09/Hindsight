"""Unit tests for model push script — bundle building and model card."""

from __future__ import annotations

from pathlib import Path

from scripts.push_model_to_hub import MODEL_CARD_TEMPLATE, _build_bundle


class TestModelCard:
    def test_card_has_required_sections(self) -> None:
        assert "# Hindsight Taxonomy Classifier" in MODEL_CARD_TEMPLATE
        assert "## Labels" in MODEL_CARD_TEMPLATE
        assert "## Training" in MODEL_CARD_TEMPLATE
        assert "## Usage" in MODEL_CARD_TEMPLATE
        assert "## Limitations" in MODEL_CARD_TEMPLATE

    def test_card_has_all_labels(self) -> None:
        from app.models.incident_label import TAXONOMY_LABELS

        for label in TAXONOMY_LABELS:
            assert label in MODEL_CARD_TEMPLATE, f"Label {label} missing from model card"

    def test_card_has_yaml_frontmatter(self) -> None:
        assert MODEL_CARD_TEMPLATE.startswith("---")
        assert "pipeline_tag: text-classification" in MODEL_CARD_TEMPLATE


class TestBuildBundle:
    def test_creates_readme(self, tmp_path: Path) -> None:
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "model.onnx").write_bytes(b"fake-onnx")
        (model_dir / "thresholds.json").write_text('{"dns": 0.5}')
        (model_dir / "tokenizer.json").write_text('{"key": "val"}')

        out_dir = tmp_path / "bundle"
        _build_bundle(model_dir, out_dir)

        assert (out_dir / "README.md").exists()
        assert (out_dir / "model.onnx").exists()
        assert (out_dir / "thresholds.json").exists()
        assert (out_dir / "tokenizer.json").exists()

    def test_empty_model_dir(self, tmp_path: Path) -> None:
        model_dir = tmp_path / "empty"
        model_dir.mkdir()
        out_dir = tmp_path / "bundle"
        _build_bundle(model_dir, out_dir)
        assert (out_dir / "README.md").exists()
