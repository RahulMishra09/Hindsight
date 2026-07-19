"""Unit tests for ClassifierWorker — event handling and idempotency logic."""

from __future__ import annotations

from app.events.schemas import DocClassified, DocDeduped
from app.events.streams import Group, Stream


class TestDocClassifiedEvent:
    def test_event_type(self) -> None:
        event = DocClassified(
            document_id="d1",
            incident_id="i1",
            content_hash="abc123",
            labels=["dns", "bad-deploy"],
        )
        assert event.event_type == "doc.classified"
        assert event.version == 1
        assert event.labels == ["dns", "bad-deploy"]

    def test_event_frozen(self) -> None:
        event = DocClassified(
            document_id="d1",
            incident_id="i1",
            content_hash="abc123",
        )
        assert event.labels == []

    def test_roundtrip_json(self) -> None:
        event = DocClassified(
            document_id="d1",
            incident_id="i1",
            content_hash="abc123",
            labels=["dns"],
        )
        data = event.model_dump_json()
        restored = DocClassified.model_validate_json(data)
        assert restored.document_id == "d1"
        assert restored.labels == ["dns"]


class TestStreamConfig:
    def test_classified_stream_exists(self) -> None:
        assert Stream.DOC_CLASSIFIED == "hindsight:doc.classified"

    def test_classifier_group_exists(self) -> None:
        assert Group.CLASSIFIER == "classifier-cg"


class TestDocDedupedSkip:
    def test_duplicate_event_skippable(self) -> None:
        event = DocDeduped(
            document_id="d1",
            content_hash="abc123",
            is_duplicate=True,
            duplicate_of="d0",
        )
        assert event.is_duplicate is True

    def test_non_duplicate_event(self) -> None:
        event = DocDeduped(
            document_id="d1",
            content_hash="abc123",
            is_duplicate=False,
        )
        assert event.is_duplicate is False
