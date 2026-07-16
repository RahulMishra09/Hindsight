"""IncidentLabel repository — async CRUD for the incident_labels table."""

from __future__ import annotations

from collections.abc import Sequence
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident_label import IncidentLabel


class IncidentLabelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        incident_id: uuid.UUID,
        label: str,
        source: str,
        confidence: float | None = None,
        model_version: str | None = None,
        annotator_id: str = "system",
        annotation_round: int | None = None,
    ) -> IncidentLabel:
        stmt = (
            insert(IncidentLabel)
            .values(
                incident_id=incident_id,
                label=label,
                source=source,
                confidence=confidence,
                model_version=model_version,
                annotator_id=annotator_id,
                annotation_round=annotation_round,
            )
            .on_conflict_do_update(
                constraint="uq_incident_labels_incident_label_annotator",
                set_={
                    "confidence": confidence,
                    "model_version": model_version,
                    "source": source,
                    "annotation_round": annotation_round,
                },
            )
            .returning(IncidentLabel)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_labels_for_incident(self, incident_id: uuid.UUID) -> Sequence[IncidentLabel]:
        stmt = (
            select(IncidentLabel)
            .where(IncidentLabel.incident_id == incident_id)
            .order_by(IncidentLabel.label)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_labels_by_source(
        self, incident_id: uuid.UUID, source: str
    ) -> Sequence[IncidentLabel]:
        stmt = (
            select(IncidentLabel)
            .where(
                IncidentLabel.incident_id == incident_id,
                IncidentLabel.source == source,
            )
            .order_by(IncidentLabel.label)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_by_label(self, source: str | None = None) -> Sequence[tuple[str, int]]:
        stmt = (
            select(
                IncidentLabel.label,
                func.count().label("cnt"),
            )
            .group_by(IncidentLabel.label)
            .order_by(IncidentLabel.label)
        )
        if source is not None:
            stmt = stmt.where(IncidentLabel.source == source)
        result = await self._session.execute(stmt)
        return [(str(row[0]), int(row[1])) for row in result.all()]

    async def delete_by_source(self, incident_id: uuid.UUID, source: str) -> int:
        stmt = delete(IncidentLabel).where(
            IncidentLabel.incident_id == incident_id,
            IncidentLabel.source == source,
        )
        result = await self._session.execute(stmt)
        rc: int = getattr(result, "rowcount", 0) or 0
        return rc

    async def get_annotators_for_incident(self, incident_id: uuid.UUID) -> Sequence[str]:
        stmt = (
            select(IncidentLabel.annotator_id)
            .where(
                IncidentLabel.incident_id == incident_id,
                IncidentLabel.source == "human",
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return [str(row[0]) for row in result.all()]
