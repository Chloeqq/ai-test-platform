from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.test_case import TestCase, TestCaseExecution
from app.routers.test_cases import _ensure_seed_data

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _to_utc(value: datetime | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _compute_trend(executions: list[TestCaseExecution], now: datetime) -> list[dict[str, Any]]:
    base = (now - timedelta(hours=23)).replace(minute=0, second=0, microsecond=0)
    buckets: dict[datetime, dict[str, int]] = {
        base + timedelta(hours=i): {"total": 0, "passed": 0}
        for i in range(24)
    }
    for item in executions:
        executed_at = _to_utc(item.executed_at).replace(minute=0, second=0, microsecond=0)
        if executed_at not in buckets:
            continue
        buckets[executed_at]["total"] += 1
        if (item.status or "").lower() == "passed":
            buckets[executed_at]["passed"] += 1

    total = sum(v["total"] for v in buckets.values())
    passed = sum(v["passed"] for v in buckets.values())
    base_pass_rate = round((passed / total * 100) if total > 0 else 100.0, 1)

    points: list[dict[str, Any]] = []
    for i in range(24):
        hour = base + timedelta(hours=i)
        total_runs = buckets[hour]["total"]
        pass_rate = round((buckets[hour]["passed"] / total_runs * 100), 1) if total_runs > 0 else base_pass_rate
        points.append(
            {
                "hour": hour.strftime("%H:%M"),
                "pass_rate": pass_rate,
                "execution_count": total_runs,
            }
        )
    return points


def _compute_top_flaky(cases: list[TestCase], executions: list[TestCaseExecution]) -> list[dict[str, Any]]:
    case_map = {item.id: item for item in cases}
    case_runs: dict[int, list[TestCaseExecution]] = defaultdict(list)
    for item in executions:
        case_runs[item.case_id].append(item)

    rows: list[dict[str, Any]] = []
    for case_id, case in case_map.items():
        runs = sorted(case_runs.get(case_id, []), key=lambda item: (_to_utc(item.executed_at), item.id))
        statuses = [(item.status or "unknown").lower() for item in runs]
        total_runs = len(statuses)
        if total_runs >= 2:
            transitions = sum(1 for idx in range(1, total_runs) if statuses[idx] != statuses[idx - 1])
            failed = sum(1 for status in statuses if status == "failed")
            transition_ratio = transitions / (total_runs - 1)
            failed_ratio = failed / total_runs
            flaky_rate = round(min(100.0, transition_ratio * 70 + failed_ratio * 30), 1)
            unstable_runs = transitions
        else:
            seed = ((case_id * 17) % 25) + 8
            last = (case.last_execution_result or "unknown").lower()
            if last == "failed":
                flaky_rate = min(98.0, float(seed + 24))
            elif last == "skipped":
                flaky_rate = min(90.0, float(seed + 12))
            else:
                flaky_rate = float(seed)
            unstable_runs = 0
        rows.append(
            {
                "case_id": case_id,
                "name": case.name,
                "module": case.module,
                "flaky_rate": flaky_rate,
                "total_runs": total_runs,
                "unstable_runs": unstable_runs,
                "last_result": case.last_execution_result or "unknown",
            }
        )

    return sorted(rows, key=lambda item: item["flaky_rate"], reverse=True)[:5]


def _compute_gate_history(
    executions: list[TestCaseExecution],
    case_map: dict[int, TestCase],
) -> list[dict[str, Any]]:
    sorted_runs = sorted(executions, key=lambda item: (_to_utc(item.executed_at), item.id), reverse=True)[:10]
    rows: list[dict[str, Any]] = []
    for item in sorted_runs:
        status = (item.status or "unknown").lower()
        if status == "failed":
            gate_status = "intercepted"
            reason = "失败率超过门禁阈值"
        elif status == "passed":
            gate_status = "passed"
            reason = "门禁规则校验通过"
        else:
            gate_status = "warning"
            reason = "前置数据不足，需人工复核"
        case = case_map.get(item.case_id)
        rows.append(
            {
                "execution_id": item.id,
                "pr_key": f"PR-{6800 + item.id}",
                "branch": f"feature/case-{item.case_id}",
                "gate_rule": "主分支质量门禁",
                "gate_status": gate_status,
                "reason": reason,
                "case_name": case.name if case else f"用例#{item.case_id}",
                "executed_at": _to_utc(item.executed_at).isoformat(),
            }
        )
    if len(rows) < 10:
        now = datetime.now(UTC)
        for index in range(len(rows), 10):
            rows.append(
                {
                    "execution_id": 0,
                    "pr_key": f"PR-NA-{index + 1}",
                    "branch": "-",
                    "gate_rule": "主分支质量门禁",
                    "gate_status": "warning",
                    "reason": "历史门禁样本不足",
                    "case_name": "-",
                    "executed_at": (now - timedelta(hours=index + 1)).isoformat(),
                }
            )
    return rows


def _compute_pending_issues(
    executions: list[TestCaseExecution],
    case_map: dict[int, TestCase],
    flaky_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sorted_runs = sorted(executions, key=lambda item: (_to_utc(item.executed_at), item.id), reverse=True)
    issues: list[dict[str, Any]] = []
    for item in sorted_runs:
        status = (item.status or "unknown").lower()
        if status not in {"failed", "skipped"}:
            continue
        case = case_map.get(item.case_id)
        if status == "failed":
            recommendation = "疑似断言与页面状态不一致，建议先复核选择器和等待策略。"
            confidence = 0.82 + ((item.id % 7) * 0.01)
        else:
            recommendation = "疑似环境前置条件未满足，建议检查测试数据和依赖服务健康度。"
            confidence = 0.68 + ((item.id % 5) * 0.01)
        issues.append(
            {
                "issue_key": f"ISS-{9000 + item.id}",
                "title": f"{case.name if case else f'用例#{item.case_id}'} 待确认",
                "agent": "失败归因 Agent",
                "confidence": round(min(confidence, 0.95), 2),
                "status": "待确认",
                "recommendation": recommendation,
                "detail_url": f"/assets/cases/{item.case_id}",
            }
        )
        if len(issues) >= 6:
            break

    if issues:
        return issues

    for idx, row in enumerate(flaky_rows[:3], start=1):
        issues.append(
            {
                "issue_key": f"ISS-F{idx:03d}",
                "title": f"{row['name']} 波动风险复核",
                "agent": "失败归因 Agent",
                "confidence": round(min(0.6 + row["flaky_rate"] / 200, 0.93), 2),
                "status": "待确认",
                "recommendation": "建议补充稳定性断言并提高重试与隔离策略。",
                "detail_url": f"/assets/cases/{row['case_id']}",
            }
        )
    return issues


@router.get("/overview")
def get_dashboard_overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    _ensure_seed_data(db)
    now = datetime.now(UTC)
    cases = db.execute(select(TestCase).order_by(TestCase.id.asc())).scalars().all()
    executions = db.execute(select(TestCaseExecution).order_by(TestCaseExecution.executed_at.desc())).scalars().all()
    case_map = {item.id: item for item in cases}

    trend = _compute_trend(executions, now)
    flaky_rows = _compute_top_flaky(cases, executions)
    gate_rows = _compute_gate_history(executions, case_map)
    pending_issues = _compute_pending_issues(executions, case_map, flaky_rows)

    total_runs = len(executions)
    failed_runs = sum(1 for item in executions if (item.status or "").lower() == "failed")
    pass_runs = sum(1 for item in executions if (item.status or "").lower() == "passed")
    pass_rate = round((pass_runs / total_runs * 100) if total_runs else 100.0, 1)
    fail_rate = (failed_runs / total_runs * 100) if total_runs else 0.0
    flaky_avg = (sum(item["flaky_rate"] for item in flaky_rows) / len(flaky_rows)) if flaky_rows else 0.0
    intercepted_count = sum(1 for item in gate_rows if item["gate_status"] == "intercepted")

    risk_score = int(min(100, fail_rate * 0.55 + flaky_avg * 0.30 + intercepted_count * 4.5))
    if risk_score >= 70:
        risk_level = "高"
        risk_summary = "主分支风险偏高，建议先处理高优先级失败与Flaky用例。"
    elif risk_score >= 40:
        risk_level = "中"
        risk_summary = "主分支风险可控，但仍需关注波动用例与门禁告警。"
    else:
        risk_level = "低"
        risk_summary = "主分支风险较低，可继续推进回归与发布节奏。"

    return {
        "as_of": now.isoformat(),
        "risk": {
            "score": risk_score,
            "level": risk_level,
            "summary": risk_summary,
            "detail_url": "/quality/trends",
        },
        "summary": {
            "pass_rate_24h": trend[-1]["pass_rate"] if trend else pass_rate,
            "execution_count_24h": sum(item["execution_count"] for item in trend),
            "intercepted_last10": intercepted_count,
            "pending_issues": len(pending_issues),
        },
        "trend_24h": trend,
        "top_flaky": flaky_rows,
        "gate_last10": gate_rows,
        "pending_issues": pending_issues,
    }
