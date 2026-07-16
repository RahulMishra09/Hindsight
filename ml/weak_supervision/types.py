"""Shared types for weak-supervision labeling functions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class Vote(Enum):
    ABSTAIN = 0
    POSITIVE = 1


@dataclass(frozen=True, slots=True)
class LFResult:
    vote: Vote
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class IncidentRecord:
    """Lightweight view of an incident for labeling functions."""

    content_hash: str
    title: str
    summary: str
    body: str
    sections: dict[str, str] = field(default_factory=dict)
    url: str = ""
    org: str = ""


class LabelingFunction(Protocol):
    """Protocol for all labeling functions."""

    @property
    def name(self) -> str: ...

    @property
    def label(self) -> str: ...

    def __call__(self, record: IncidentRecord) -> LFResult: ...
