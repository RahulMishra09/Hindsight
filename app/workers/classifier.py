"""ClassifierWorker — doc.deduped → doc.classified via TaxonomyClassifier."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar
import uuid

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.events.consumer import BaseWorker
from app.events.publisher import Publisher
from app.events.schemas import DocClassified, DocDeduped
from app.events.streams import Group, Stream
from app.ml.classifier import TaxonomyClassifier
from app.models.incident_label import TAXONOMY_LABELS
from app.repositories.incident import IncidentRepository
from app.repositories.incident_label import IncidentLabelRepository

logger = get_logger(__name__)

MODEL_VERSION = "hindsight-taxonomy-v1"


class ClassifierWorker(BaseWorker[DocDeduped]):
    stream: ClassVar[str] = Stream.DOC_DEDUPED
    group: ClassVar[str] = Group.CLASSIFIER
    event_model = DocDeduped

    def __init__(
        self,
        client: redis.Redis,
        *,
        sessionmaker: async_sessionmaker[AsyncSession],
        model_dir: Path,
        max_length: int = 512,
        **kwargs: object,
    ) -> None:
        super().__init__(client, **kwargs)  # type: ignore[arg-type]
        self._sessionmaker = sessionmaker
        self._publisher = Publisher(client)
        self._classifier = TaxonomyClassifier(model_dir, max_length=max_length)

    async def handle(self, event: DocDeduped) -> None:
        if event.is_duplicate:
            logger.info("classifier.skip_duplicate", document_id=event.document_id)
            return

        doc_id = event.document_id
        content_hash = event.content_hash

        async with self._sessionmaker() as session:
            inc_repo = IncidentRepository(session)
            label_repo = IncidentLabelRepository(session)

            incident = await inc_repo.get_by_document_id(uuid.UUID(doc_id))
            if incident is None:
                logger.warning("classifier.no_incident", document_id=doc_id)
                return

            existing = await label_repo.get_labels_by_source(incident.id, "model")
            if existing:
                logger.info(
                    "classifier.already_classified",
                    incident_id=str(incident.id),
                    content_hash=content_hash,
                )
                return

            probs, _labels, active_labels = self._classifier.classify_incident(
                title=incident.title,
                summary=incident.summary,
                sections=incident.sections,
            )

            for label_name in active_labels:
                idx = TAXONOMY_LABELS.index(label_name)
                await label_repo.upsert(
                    incident_id=incident.id,
                    label=label_name,
                    source="model",
                    confidence=round(float(probs[idx]), 4),
                    model_version=MODEL_VERSION,
                    annotator_id="classifier-worker",
                )

            await session.commit()

        classified_event = DocClassified(
            document_id=doc_id,
            incident_id=str(incident.id),
            content_hash=content_hash,
            labels=active_labels,
        )
        await self._publisher.publish(Stream.DOC_CLASSIFIED, classified_event)

        logger.info(
            "classifier.classified",
            document_id=doc_id,
            incident_id=str(incident.id),
            labels=active_labels,
            n_labels=len(active_labels),
        )
