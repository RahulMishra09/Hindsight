"""ASGI entrypoint. ``uvicorn app.main:app`` serves the API."""

from __future__ import annotations

from app.core.app import create_app

app = create_app()
