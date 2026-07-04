"""Unit tests for app.core.app — app factory and router wiring."""

from app.core.app import create_app
from app.core.settings import Settings


def test_create_app_returns_fastapi():
    """create_app produces a FastAPI instance with the expected routes."""
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
    )
    application = create_app(settings)
    # Build the OpenAPI schema which resolves all sub-routers
    schema = application.openapi()
    paths = list(schema["paths"].keys())
    assert "/v1/healthz" in paths
    assert "/v1/readyz" in paths


def test_openapi_url_set():
    """OpenAPI docs are served under /v1/."""
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    application = create_app(settings)
    assert application.openapi_url == "/v1/openapi.json"
