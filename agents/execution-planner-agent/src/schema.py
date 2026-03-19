from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExecutionStage:
    stage_id: str
    stage_name: str
    runner: str
    estimated_seconds: int
    retry_limit: int
    depends_on: list[str] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    version: str
    run_mode: str
    source: str
    priority: str
    environment: str
    parallelism: int
    retry_policy: dict[str, Any]
    stages: list[ExecutionStage]
    scheduling_hints: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
