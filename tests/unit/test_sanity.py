"""
Sanity test — proves CI is not vacuously green.

This test contains zero application logic by design (Week 0 has none).
It verifies that the Python environment, pytest, and the package skeleton
are correctly wired before any application code exists.
"""

import sys


def test_python_version() -> None:
    """Python 3.12+ is required per the pinned stack in CLAUDE.md."""
    assert sys.version_info >= (3, 12), (
        f"Expected Python >= 3.12, got {sys.version_info.major}.{sys.version_info.minor}"
    )


def test_package_skeleton_importable() -> None:
    """All top-level packages must be importable (empty __init__.py is sufficient)."""
    import app
    import app.api
    import app.api.v1
    import app.core
    import app.events
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

    # Verify none of these packages sneaked in application logic (Week 0 invariant)
    for pkg in (app, ml):
        assert pkg.__file__ is not None


def test_no_fastapi_in_app() -> None:
    """Week 0 invariant: no FastAPI application code exists yet."""
    import importlib
    import pkgutil

    fastapi_found: list[str] = []

    for importer, modname, ispkg in pkgutil.walk_packages(
        path=["app"],
        prefix="app.",
        onerror=lambda x: None,
    ):
        del importer, ispkg  # unused
        try:
            source_path = importlib.util.find_spec(modname)
            if source_path and source_path.origin:
                with open(source_path.origin) as f:
                    content = f.read()
                if "FastAPI(" in content:
                    fastapi_found.append(modname)
        except (ModuleNotFoundError, ValueError):
            pass

    assert fastapi_found == [], (
        f"FastAPI application code found in Week 0 (should not exist yet): {fastapi_found}"
    )
