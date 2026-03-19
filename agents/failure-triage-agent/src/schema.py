from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TriageAction:
    action: str
    owner: str
    reason: str


@dataclass
class FailureTriage:
    version: str
    triage_label: str
    failure_class: str
    severity: str
    owner_team: str
    queue: str
    bucket_key: str
    duplicate_of: str
    requires_manual_review: bool
    confidence: float
    signals: dict[str, Any] = field(default_factory=dict)
    actions: list[TriageAction] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
