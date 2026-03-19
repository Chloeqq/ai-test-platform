from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RiskFactor:
    factor: str
    score: int
    reason: str


@dataclass
class RiskReport:
    version: str
    risk_score: int
    risk_level: str
    gate_decision: str
    recommendation: str
    factors: list[RiskFactor] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
