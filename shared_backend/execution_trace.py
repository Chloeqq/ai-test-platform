from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StepTrace:
    index: int
    action: str
    target: str
    selector: str
    status: str
    started_at: str = field(default_factory=_utc_now_iso)
    finished_at: str = field(default_factory=_utc_now_iso)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "action": self.action,
            "target": self.target,
            "selector": self.selector,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }


@dataclass
class ExecutionTrace:
    run_id: str
    status: str = "running"
    started_at: str = field(default_factory=_utc_now_iso)
    finished_at: str = ""
    steps: list[StepTrace] = field(default_factory=list)

    def add_step(self, trace: StepTrace) -> None:
        self.steps.append(trace)

    def finalize(self) -> None:
        self.finished_at = _utc_now_iso()
        self.status = "passed" if all(step.status == "PASS" for step in self.steps) else "failed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "steps": [step.to_dict() for step in self.steps],
        }
