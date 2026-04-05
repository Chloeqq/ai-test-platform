from __future__ import annotations

from collections import defaultdict
from typing import Any


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _environment_pool_for_task(item: dict[str, Any]) -> str:
    runner = str(item.get("runner", "")).strip().lower()
    resource_profile = str(item.get("resource_profile", "")).strip().lower()
    if runner == "mobile":
        return "mobile-device-farm"
    if runner == "api":
        return "api-sandbox"
    if resource_profile in {"heavy", "browser-heavy"}:
        return "web-browser-heavy"
    return "web-browser-default"


def build_scheduler_summary(*, items: list[dict[str, Any]], task_summary: dict[str, Any]) -> dict[str, Any]:
    queue_distribution: dict[str, dict[str, Any]] = {}
    environment_pool_distribution: dict[str, int] = defaultdict(int)
    resource_profile_distribution: dict[str, int] = defaultdict(int)
    runner_distribution: dict[str, int] = defaultdict(int)
    queued_count = 0
    running_count = 0
    active_count = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        queue = str(item.get("queue", "default")).strip() or "default"
        queue_status = str(item.get("queue_status", "unknown")).strip() or "unknown"
        runner = str(item.get("runner", "playwright")).strip() or "playwright"
        resource_profile = str(item.get("resource_profile", "default")).strip() or "default"
        expected_total_seconds = _int_value(item.get("expected_total_seconds"))
        environment_pool = _environment_pool_for_task(item)
        queue_bucket = queue_distribution.setdefault(
            queue,
            {
                "queue": queue,
                "queued": 0,
                "running": 0,
                "completed": 0,
                "expected_total_seconds": 0,
                "resource_profiles": defaultdict(int),
                "environment_pools": defaultdict(int),
            },
        )
        if queue_status == "queued":
            queue_bucket["queued"] += 1
            queued_count += 1
            active_count += 1
        elif queue_status == "running":
            queue_bucket["running"] += 1
            running_count += 1
            active_count += 1
        else:
            queue_bucket["completed"] += 1
        queue_bucket["expected_total_seconds"] += expected_total_seconds
        queue_bucket["resource_profiles"][resource_profile] += 1
        queue_bucket["environment_pools"][environment_pool] += 1
        environment_pool_distribution[environment_pool] += 1
        resource_profile_distribution[resource_profile] += 1
        runner_distribution[runner] += 1

    queue_rows = []
    for queue, bucket in queue_distribution.items():
        queued = _int_value(bucket.get("queued"))
        running = _int_value(bucket.get("running"))
        expected = _int_value(bucket.get("expected_total_seconds"))
        if queued >= 5:
            pressure = "high"
        elif queued >= 2 or queued + running >= 3:
            pressure = "medium"
        else:
            pressure = "low"
        queue_rows.append(
            {
                "queue": queue,
                "queued": queued,
                "running": running,
                "completed": _int_value(bucket.get("completed")),
                "expected_total_seconds": expected,
                "pressure": pressure,
                "resource_profiles": dict(sorted(bucket.get("resource_profiles", {}).items())),
                "environment_pools": dict(sorted(bucket.get("environment_pools", {}).items())),
            }
        )
    queue_rows.sort(key=lambda row: (-_int_value(row.get("queued")), -_int_value(row.get("running")), str(row.get("queue", ""))))

    recommendations: list[dict[str, Any]] = []
    if queued_count > 0:
        recommendations.append(
            {
                "title": "优先消化排队任务",
                "summary": f"当前 queued={queued_count}，建议先关注高 pressure 队列与 heavy 资源画像。",
                "focus": queue_rows[:3],
            }
        )
    blocked = _int_value(task_summary.get("strict_mode_blocked_task_count"))
    if blocked > 0:
        recommendations.append(
            {
                "title": "避免将 strict-mode blocked 任务推入高优先级队列",
                "summary": f"当前 blocked 任务 {blocked} 个，建议先补齐 manifest-first 再提升调度优先级。",
                "focus": [],
            }
        )

    return {
        "total_tasks": len(items),
        "active_task_count": active_count,
        "queued_task_count": queued_count,
        "running_task_count": running_count,
        "queue_distribution": queue_rows,
        "environment_pool_distribution": dict(sorted(environment_pool_distribution.items())),
        "resource_profile_distribution": dict(sorted(resource_profile_distribution.items())),
        "runner_distribution": dict(sorted(runner_distribution.items())),
        "recommendations": recommendations,
    }


def build_scheduler_dispatch_plan(*, items: list[dict[str, Any]]) -> dict[str, Any]:
    lanes: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        queue_status = str(item.get("queue_status", "")).strip().lower()
        if queue_status != "queued":
            continue
        queue = str(item.get("queue", "default")).strip() or "default"
        runner = str(item.get("runner", "playwright")).strip() or "playwright"
        resource_profile = str(item.get("resource_profile", "default")).strip() or "default"
        environment_pool = _environment_pool_for_task(item)
        key = (queue, runner, resource_profile, environment_pool)
        lane = lanes.setdefault(
            key,
            {
                "queue": queue,
                "runner": runner,
                "resource_profile": resource_profile,
                "environment_pool": environment_pool,
                "task_ids": [],
                "expected_total_seconds": 0,
            },
        )
        lane["task_ids"].append(str(item.get("task_id", "")).strip())
        lane["expected_total_seconds"] += _int_value(item.get("expected_total_seconds"))

    lane_rows = []
    for lane in lanes.values():
        resource_profile = str(lane.get("resource_profile", "default")).strip().lower()
        recommended_concurrency = 1 if resource_profile in {"heavy", "browser-heavy"} else 2
        lane_rows.append(
            {
                **lane,
                "task_count": len(lane.get("task_ids", [])),
                "recommended_concurrency": recommended_concurrency,
            }
        )
    lane_rows.sort(
        key=lambda lane: (-_int_value(lane.get("task_count")), -_int_value(lane.get("expected_total_seconds")), str(lane.get("queue", "")))
    )
    return {
        "lane_count": len(lane_rows),
        "dispatch_lanes": lane_rows,
    }
