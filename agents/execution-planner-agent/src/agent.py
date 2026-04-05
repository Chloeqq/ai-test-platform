# mypy: ignore-errors

from __future__ import annotations

from typing import Any

from .schema import ExecutionPlan, ExecutionStage


class ExecutionPlannerAgent:
    def plan(
        self,
        *,
        case: dict[str, Any],
        execution_requested: bool,
        source: str = "manual",
        execution_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        execution = case.get("execution", {}) if isinstance(case, dict) else {}
        steps = execution.get("steps", [])
        if not isinstance(steps, list):
            steps = []

        config = execution_config if isinstance(execution_config, dict) else {}
        priority = str(case.get("priority", "P1")).strip() or "P1"
        environment = str(config.get("environment", "test")).strip() or "test"
        parallelism = int(config.get("parallelism", 1) or 1)
        parallelism = max(1, min(parallelism, 16))
        retry_limit = int(config.get("retry_limit", 1) or 1)
        retry_limit = max(0, min(retry_limit, 5))

        estimated_seconds = self._estimate_duration_seconds(steps)
        run_mode = "generate_and_run" if execution_requested else "generate_only"

        stages: list[ExecutionStage] = [
            ExecutionStage(
                stage_id="stage-prepare",
                stage_name="prepare_artifacts",
                runner="orchestrator",
                estimated_seconds=10,
                retry_limit=0,
            )
        ]

        if execution_requested:
            stages.append(
                ExecutionStage(
                    stage_id="stage-runner",
                    stage_name="runner_execute",
                    runner=str(execution.get("runner", "playwright")).strip() or "playwright",
                    estimated_seconds=estimated_seconds,
                    retry_limit=retry_limit,
                    depends_on=["stage-prepare"],
                )
            )
            stages.append(
                ExecutionStage(
                    stage_id="stage-report",
                    stage_name="report_build",
                    runner="orchestrator",
                    estimated_seconds=8,
                    retry_limit=0,
                    depends_on=["stage-runner"],
                )
            )
        else:
            stages.append(
                ExecutionStage(
                    stage_id="stage-report",
                    stage_name="report_build",
                    runner="orchestrator",
                    estimated_seconds=5,
                    retry_limit=0,
                    depends_on=["stage-prepare"],
                )
            )

        plan = ExecutionPlan(
            version="ExecutionPlanV1",
            run_mode=run_mode,
            source=source,
            priority=priority,
            environment=environment,
            parallelism=parallelism,
            retry_policy={
                "enabled": retry_limit > 0 and execution_requested,
                "max_retries": retry_limit,
                "backoff_seconds": 5,
            },
            stages=stages,
            scheduling_hints={
                "queue": self._queue_name(priority),
                "expected_total_seconds": sum(stage.estimated_seconds for stage in stages),
                "resource_profile": self._resource_profile(steps),
            },
        )
        return plan.to_dict()

    @staticmethod
    def _estimate_duration_seconds(steps: list[dict[str, Any]]) -> int:
        step_count = len(steps)
        return max(20, min(900, 12 + step_count * 8))

    @staticmethod
    def _queue_name(priority: str) -> str:
        mapping = {"P0": "critical", "P1": "high", "P2": "normal", "P3": "low"}
        return mapping.get(priority.upper(), "normal")

    @staticmethod
    def _resource_profile(steps: list[dict[str, Any]]) -> str:
        actions = {str((step or {}).get("action", "")).strip() for step in steps}
        if "goto" in actions and "fill" in actions:
            return "browser-heavy"
        if "assert_url" in actions and len(actions) <= 3:
            return "smoke-light"
        return "default"
