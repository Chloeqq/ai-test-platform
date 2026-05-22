"""单次测试运行的步骤级执行追踪（时间戳与 PASS/FAIL 状态）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StepTrace:
    """单步执行的追踪记录。"""
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
    """一次 run 的聚合追踪；finalize 时根据各步 PASS 判定整体 passed/failed。"""
    run_id: str
    status: str = "running"
    started_at: str = field(default_factory=_utc_now_iso)
    finished_at: str = ""
    steps: list[StepTrace] = field(default_factory=list)

    def add_step(self, trace: StepTrace) -> None:
        self.steps.append(trace)

    def finalize(self) -> None:
        self.finished_at = _utc_now_iso()
        # 任一步非 PASS 则整次 run 记为 failed
        self.status = "passed" if all(step.status == "PASS" for step in self.steps) else "failed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "steps": [step.to_dict() for step in self.steps],
        }
