"""
Sanity test — proves CI is not vacuously green.

Verifies that the Python environment, pytest, and the package skeleton
are correctly wired.
"""

import sys


def test_python_version() -> None:
    """Python 3.12+ is required per the pinned stack in CLAUDE.md."""
    assert sys.version_info >= (3, 12), (
        f"Expected Python >= 3.12, got {sys.version_info.major}.{sys.version_info.minor}"
    )


def test_package_skeleton_importable() -> None:
    """All top-level packages must be importable."""
    import app
    import app.api
    import app.api.v1
    import app.core
    import app.events
    import app.ingest
    import app.ml
    import app.models
    import app.repositories
    import app.schemas
    import app.services
    import app.workers
    import ml
    import ml.annotation
    import ml.eval
    import ml.training
    import ml.weak_supervision

    for pkg in (app, ml):
        assert pkg.__file__ is not None
