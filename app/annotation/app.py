"""Annotation app — FastAPI + HTMX for multi-label incident annotation.

Run with: uvicorn app.annotation.app:app --port 8001 --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
import uuid

from fastapi import Depends, FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.annotation.templates import (
    render_done_page,
    render_incident_card,
    render_index_page,
)
from app.core.db import create_engine, create_sessionmaker
from app.core.settings import get_settings
from app.models.incident_label import TAXONOMY_LABELS
from app.repositories.incident import IncidentRepository
from app.repositories.incident_label import IncidentLabelRepository

app = FastAPI(title="Hindsight Annotation Tool", version="0.1.0")

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _get_sm() -> async_sessionmaker[AsyncSession]:
    global _engine, _sessionmaker
    if _sessionmaker is None:
        settings = get_settings()
        _engine = create_engine(settings)
        _sessionmaker = create_sessionmaker(_engine)
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    sm = _get_sm()
    async with sm() as session:
        yield session


@app.get("/", response_class=HTMLResponse)
async def index(
    annotator_id: str = Query(default="default"),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    inc_repo = IncidentRepository(session)
    label_repo = IncidentLabelRepository(session)
    incidents = await inc_repo.list_all(limit=1000)
    total = len(incidents)

    annotated_count = 0
    next_incident = None
    for inc in incidents:
        annotators = await label_repo.get_annotators_for_incident(inc.id)
        if annotator_id in annotators:
            annotated_count += 1
        elif next_incident is None:
            next_incident = inc

    if next_incident is None:
        return HTMLResponse(render_done_page(annotated_count, total, annotator_id))

    silver_labels = await label_repo.get_labels_by_source(next_incident.id, "weak")
    silver_set = {lb.label for lb in silver_labels}
    human_labels = await label_repo.get_labels_by_source(next_incident.id, "human")

    return HTMLResponse(
        render_index_page(
            incident=next_incident,
            annotator_id=annotator_id,
            annotated=annotated_count,
            total=total,
            silver_labels=silver_set,
            existing_human_labels={
                lb.label for lb in human_labels if lb.annotator_id == annotator_id
            },
        )
    )


@app.post("/annotate", response_class=HTMLResponse)
async def annotate(
    request: Request,
    incident_id: str = Form(...),
    annotator_id: str = Form(default="default"),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    form = await request.form()
    selected_labels: list[str] = []
    for label in TAXONOMY_LABELS:
        if form.get(f"label_{label}"):
            selected_labels.append(label)

    label_repo = IncidentLabelRepository(session)
    inc_id = uuid.UUID(incident_id)

    await label_repo.delete_by_source(inc_id, "human")
    for label in selected_labels:
        await label_repo.upsert(
            incident_id=inc_id,
            label=label,
            source="human",
            confidence=1.0,
            annotator_id=annotator_id,
        )
    # Write a marker even if no labels selected (annotator reviewed and chose none)
    if not selected_labels:
        await label_repo.upsert(
            incident_id=inc_id,
            label="__reviewed__",
            source="human",
            confidence=1.0,
            annotator_id=annotator_id,
        )
    await session.commit()

    inc_repo = IncidentRepository(session)
    incidents = await inc_repo.list_all(limit=1000)
    total = len(incidents)

    annotated_count = 0
    next_incident = None
    for inc in incidents:
        annotators = await label_repo.get_annotators_for_incident(inc.id)
        if annotator_id in annotators:
            annotated_count += 1
        elif next_incident is None:
            next_incident = inc

    if next_incident is None:
        return HTMLResponse(render_done_page(annotated_count, total, annotator_id))

    silver_labels = await label_repo.get_labels_by_source(next_incident.id, "weak")
    return HTMLResponse(
        render_incident_card(
            incident=next_incident,
            annotator_id=annotator_id,
            annotated=annotated_count,
            total=total,
            silver_labels={lb.label for lb in silver_labels},
            existing_human_labels=set(),
        )
    )
