"""Async consumer workers (SAD §6.8). Each subclasses ``BaseWorker`` unchanged."""

from app.workers.echo import EchoWorker

__all__ = ["EchoWorker"]
