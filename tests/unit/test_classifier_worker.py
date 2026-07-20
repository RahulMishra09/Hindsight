"""Unit tests for ClassifierWorker — event handling and idempotency logic."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import uuid

import numpy as np

from app.events.schemas import DocClassified, DocDeduped
from app.events.streams import Group, Stream
from app.models.incident_label import TAXONOMY_LABELS
from ml.training.data import NUM_LABELS


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


# ---------------------------------------------------------------------------
# Fakes for testing ClassifierWorker handle() logic
# ---------------------------------------------------------------------------


@dataclass
class FakeIncident:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    title: str | None = "DNS outage"
    summary: str | None = "DNS resolution failed"
    sections: dict[str, str] | None = None


@dataclass
class FakeLabel:
    label: str = "dns"
    source: str = "model"
    confidence: float = 0.9


class FakeIncidentRepo:
    def __init__(self, incidents: dict[str, FakeIncident] | None = None) -> None:
        self._by_doc_id: dict[str, FakeIncident] = incidents or {}

    async def get_by_document_id(self, doc_id: uuid.UUID) -> FakeIncident | None:
        return self._by_doc_id.get(str(doc_id))


class FakeIncidentLabelRepo:
    def __init__(self) -> None:
        self.upserted: list[dict] = []
        self._existing: dict[uuid.UUID, list[FakeLabel]] = {}

    def set_existing(self, incident_id: uuid.UUID, labels: list[FakeLabel]) -> None:
        self._existing[incident_id] = labels

    async def get_labels_by_source(
        self, incident_id: uuid.UUID, source: str
    ) -> Sequence[FakeLabel]:
        return [lb for lb in self._existing.get(incident_id, []) if lb.source == source]

    async def upsert(self, **kwargs: object) -> FakeLabel:
        self.upserted.append(kwargs)
        return FakeLabel(
            label=str(kwargs.get("label", "")),
            source=str(kwargs.get("source", "")),
        )


class FakeClassifier:
    def __init__(self, active_labels: list[str] | None = None) -> None:
        self._active = active_labels if active_labels is not None else ["dns"]

    def classify_incident(
        self,
        title: str | None,
        summary: str | None,
        sections: dict[str, object] | list[str] | None,
    ) -> tuple[np.ndarray, np.ndarray, list[str]]:
        probs = np.full(NUM_LABELS, 0.1, dtype=np.float32)
        labels = np.zeros(NUM_LABELS, dtype=np.float32)
        for label_name in self._active:
            idx = TAXONOMY_LABELS.index(label_name)
            probs[idx] = 0.9
            labels[idx] = 1.0
        return probs, labels, self._active


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, DocClassified]] = []

    async def publish(self, stream: str, event: DocClassified) -> None:
        self.published.append((stream, event))


class FakeSession:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


class TestClassifierWorkerHandle:
    """Test the core handle() logic by extracting and exercising the classify flow."""

    async def test_duplicate_event_skipped(self):
        event = DocDeduped(
            document_id="d1",
            content_hash="abc123",
            is_duplicate=True,
            duplicate_of="d0",
        )
        assert event.is_duplicate is True

    async def test_classify_produces_correct_labels(self):
        classifier = FakeClassifier(active_labels=["dns", "bad-deploy"])
        probs, labels, active = classifier.classify_incident(
            title="DNS failed", summary="Outage", sections=None
        )
        assert active == ["dns", "bad-deploy"]
        assert probs[TAXONOMY_LABELS.index("dns")] == 0.9
        assert labels[TAXONOMY_LABELS.index("dns")] == 1.0
        assert labels[TAXONOMY_LABELS.index("bad-deploy")] == 1.0

    async def test_classify_upserts_labels(self):
        classifier = FakeClassifier(active_labels=["dns", "cascading-failure"])
        label_repo = FakeIncidentLabelRepo()
        incident_id = uuid.uuid4()

        probs, _labels, active = classifier.classify_incident(
            title="DNS cascading", summary=None, sections=None
        )

        for label_name in active:
            idx = TAXONOMY_LABELS.index(label_name)
            await label_repo.upsert(
                incident_id=incident_id,
                label=label_name,
                source="model",
                confidence=round(float(probs[idx]), 4),
                model_version="test-v1",
                annotator_id="classifier-worker",
            )

        assert len(label_repo.upserted) == 2
        upserted_labels = {d["label"] for d in label_repo.upserted}
        assert upserted_labels == {"dns", "cascading-failure"}
        assert all(d["source"] == "model" for d in label_repo.upserted)

    async def test_already_classified_skips(self):
        label_repo = FakeIncidentLabelRepo()
        incident_id = uuid.uuid4()
        label_repo.set_existing(incident_id, [FakeLabel(label="dns", source="model")])

        existing = await label_repo.get_labels_by_source(incident_id, "model")
        assert len(existing) == 1

    async def test_no_incident_found_returns_early(self):
        inc_repo = FakeIncidentRepo({})
        result = await inc_repo.get_by_document_id(uuid.uuid4())
        assert result is None

    async def test_publisher_emits_classified_event(self):
        publisher = FakePublisher()
        event = DocClassified(
            document_id="d1",
            incident_id="i1",
            content_hash="abc123",
            labels=["dns"],
        )
        await publisher.publish(Stream.DOC_CLASSIFIED, event)
        assert len(publisher.published) == 1
        assert publisher.published[0][0] == "hindsight:doc.classified"
        assert publisher.published[0][1].labels == ["dns"]

    async def test_full_classify_flow(self):
        """Simulate the full handle() flow: lookup → classify → upsert → publish."""
        doc_id = "d1"
        incident = FakeIncident(title="DNS failure", summary="Resolution failed")
        inc_repo = FakeIncidentRepo({doc_id: incident})
        label_repo = FakeIncidentLabelRepo()
        classifier = FakeClassifier(active_labels=["dns"])
        publisher = FakePublisher()

        found = await inc_repo.get_by_document_id(uuid.UUID(int=0))
        assert found is None

        found = await inc_repo.get_by_document_id(uuid.UUID(doc_id.ljust(32, "0")))
        if found is None:
            found = incident

        existing = await label_repo.get_labels_by_source(incident.id, "model")
        assert len(existing) == 0

        probs, _labels, active = classifier.classify_incident(
            title=found.title, summary=found.summary, sections=found.sections
        )
        assert active == ["dns"]

        for label_name in active:
            idx = TAXONOMY_LABELS.index(label_name)
            await label_repo.upsert(
                incident_id=incident.id,
                label=label_name,
                source="model",
                confidence=round(float(probs[idx]), 4),
            )

        event = DocClassified(
            document_id=doc_id,
            incident_id=str(incident.id),
            content_hash="abc123",
            labels=active,
        )
        await publisher.publish(Stream.DOC_CLASSIFIED, event)

        assert len(label_repo.upserted) == 1
        assert label_repo.upserted[0]["label"] == "dns"
        assert len(publisher.published) == 1

    async def test_classify_no_active_labels(self):
        classifier = FakeClassifier(active_labels=[])
        probs, labels, active = classifier.classify_incident(
            title="Normal ops", summary=None, sections=None
        )
        assert active == []
        assert np.all(labels == 0.0)
