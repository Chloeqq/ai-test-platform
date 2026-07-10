"""Workbench 治理视图函数 —— 趋势、概览、flaky、仪表盘。

提取自 workbench_governance_service.py 以控制单文件大小在 1000 行以内。
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.api.workbench._helpers import default_overview, to_utc
from app.models.test_case import TestCase, TestCaseExecution
from app.repositories.test_case_repository import TestCaseRepository
from app.services import test_case_service
from app.services.workbench_governance_service import (
    _build_action_items,
    _build_execution_strategy,
    _build_failure_cluster_analysis,
    _build_flaky_analysis,
    _build_governance_item_score_breakdown,
    _build_manager_summary,
    _build_risk_score_breakdown,
    _build_strict_manifest_policy,
    _default_gate_recommendation,
    _issue_status,
    _parse_timestamp,
    _query_href,
    _risk_level,
    _risk_summary,
)
from datetime_compat import UTC
from shared_backend.type_utils import dict_value as _dict_value
from shared_backend.type_utils import float_value as _float_value
from shared_backend.type_utils import int_value as _int_value
from shared_backend.type_utils import list_value as _list_value

LOGGER = logging.getLogger(__name__)

def build_governance_trend(
    *,
    history_items: list[dict[str, Any]],
    resolve_governance_snapshot: Any,
    quality_gate_summary: dict[str, Any] | None = None,
    now: datetime | None = None,
    days: int = 14,
) -> dict[str, Any]:
    normalized_days = max(7, int(days or 14))
    anchor = (now or datetime.now(UTC)).astimezone(UTC)
    end_date = anchor.date()
    start_date = end_date - timedelta(days=normalized_days - 1)
    bucket_map: dict[str, dict[str, Any]] = {}
    for index in range(normalized_days):
        day = start_date + timedelta(days=index)
        bucket_map[day.isoformat()] = {
            "date": day.isoformat(),
            "history_events": 0,
            "quality_gate_allow": 0,
            "quality_gate_block": 0,
            "_risk_blocked_run_ids": set(),
            "_review_required_run_ids": set(),
            "_self_healing_attention_run_ids": set(),
        }

    quality_gate = quality_gate_summary if isinstance(quality_gate_summary, dict) else {}
    decision_trend = _list_value(quality_gate.get("decision_trend"))
    for item in decision_trend:
        if not isinstance(item, dict):
            continue
        day_key = str(item.get("date", "")).strip()
        if day_key not in bucket_map:
            continue
        bucket_map[day_key]["quality_gate_allow"] = _int_value(item.get("allow"))
        bucket_map[day_key]["quality_gate_block"] = _int_value(item.get("block"))

    snapshot_cache: dict[str, dict[str, Any]] = {}
    for entry in history_items:
        if not isinstance(entry, dict):
            continue
        timestamp = _parse_timestamp(entry.get("timestamp"))
        if timestamp is None:
            continue
        day_key = timestamp.date().isoformat()
        bucket = bucket_map.get(day_key)
        if bucket is None:
            continue
        bucket["history_events"] += 1

        run_id = str(entry.get("run_id", "")).strip()
        if not run_id:
            continue
        snapshot = snapshot_cache.get(run_id)
        if snapshot is None:
            snapshot = resolve_governance_snapshot(run_id) if callable(resolve_governance_snapshot) else {}
            snapshot_cache[run_id] = snapshot if isinstance(snapshot, dict) else {}
        risk_summary = _dict_value(snapshot.get("risk_summary"))
        if str(risk_summary.get("gate_decision", "")).strip().lower() == "block":
            bucket["_risk_blocked_run_ids"].add(run_id)
        if bool(risk_summary.get("requires_review", False)):
            bucket["_review_required_run_ids"].add(run_id)
        self_healing_summary = _dict_value(snapshot.get("self_healing_summary"))
        boundary = _dict_value(self_healing_summary.get("boundary"))
        healing_status = str(self_healing_summary.get("status", "")).strip().lower()
        if healing_status in {"rejected", "rolled_back"} or (boundary and boundary.get("allowed") is False):
            bucket["_self_healing_attention_run_ids"].add(run_id)

    rows: list[dict[str, Any]] = []
    for day_key in sorted(bucket_map):
        bucket = bucket_map[day_key]
        risk_blocked_runs = len(bucket.pop("_risk_blocked_run_ids"))
        review_required_runs = len(bucket.pop("_review_required_run_ids"))
        self_healing_attention_runs = len(bucket.pop("_self_healing_attention_run_ids"))
        quality_gate_allow = _int_value(bucket.get("quality_gate_allow"))
        quality_gate_block = _int_value(bucket.get("quality_gate_block"))
        quality_gate_total = quality_gate_allow + quality_gate_block
        pressure_score = int(
            min(
                100,
                quality_gate_block * 10
                + risk_blocked_runs * 12
                + review_required_runs * 7
                + self_healing_attention_runs * 5,
            )
        )
        rows.append(
            {
                "date": day_key,
                "history_events": _int_value(bucket.get("history_events")),
                "quality_gate_allow": quality_gate_allow,
                "quality_gate_block": quality_gate_block,
                "quality_gate_total": quality_gate_total,
                "risk_blocked_runs": risk_blocked_runs,
                "review_required_runs": review_required_runs,
                "self_healing_attention_runs": self_healing_attention_runs,
                "pressure_score": pressure_score,
            }
        )

    recent_rows = rows[-7:]
    previous_rows = rows[-14:-7] if len(rows) > 7 else []
    recent_pressure_avg = round(
        sum(_int_value(item.get("pressure_score")) for item in recent_rows) / max(1, len(recent_rows)),
        1,
    ) if recent_rows else 0.0
    previous_pressure_avg = round(
        sum(_int_value(item.get("pressure_score")) for item in previous_rows) / max(1, len(previous_rows)),
        1,
    ) if previous_rows else 0.0
    pressure_delta = round(recent_pressure_avg - previous_pressure_avg, 1) if previous_rows else recent_pressure_avg
    if pressure_delta >= 8:
        direction = "worsening"
    elif pressure_delta <= -8:
        direction = "improving"
    else:
        direction = "stable"

    summary_7d = {
        "quality_gate_blocked": sum(_int_value(item.get("quality_gate_block")) for item in recent_rows),
        "risk_blocked_runs": sum(_int_value(item.get("risk_blocked_runs")) for item in recent_rows),
        "review_required_runs": sum(_int_value(item.get("review_required_runs")) for item in recent_rows),
        "self_healing_attention_runs": sum(
            _int_value(item.get("self_healing_attention_runs")) for item in recent_rows
        ),
        "average_pressure_score": recent_pressure_avg,
        "max_pressure_score": max((_int_value(item.get("pressure_score")) for item in recent_rows), default=0),
        "direction": direction,
        "pressure_delta": pressure_delta,
    }
    return {
        "items": rows,
        "summary_7d": summary_7d,
    }


def build_governance_overview(
    *,
    quality_gate_summary: dict[str, Any] | None,
    task_snapshot: dict[str, Any] | None,
    cluster_payload: dict[str, Any] | None,
    flaky_payload: dict[str, Any] | None = None,
    governance_trend: dict[str, Any] | None = None,
    degraded_sources: list[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    timestamp = now or datetime.now(UTC)
    quality_gate = quality_gate_summary if isinstance(quality_gate_summary, dict) else {}
    task_data = task_snapshot if isinstance(task_snapshot, dict) else {}
    task_summary = _dict_value(task_data.get("summary"))
    cluster_data = cluster_payload if isinstance(cluster_payload, dict) else {}
    flaky_data = flaky_payload if isinstance(flaky_payload, dict) else {}
    trend_payload = governance_trend if isinstance(governance_trend, dict) else {}
    cluster_rows = [item for item in _list_value(cluster_data.get("clusters")) if isinstance(item, dict)]
    flaky_rows = [item for item in _list_value(flaky_data.get("top_flaky")) if isinstance(item, dict)]
    summary_24h = _dict_value(quality_gate.get("summary_24h"))
    trend_items = [item for item in _list_value(trend_payload.get("items")) if isinstance(item, dict)]
    trend_summary_7d = _dict_value(trend_payload.get("summary_7d"))

    total_tasks = _int_value(task_summary.get("total_tasks"))
    governance_risk_counts = _dict_value(task_summary.get("governance_risk_counts"))
    critical_count = _int_value(governance_risk_counts.get("critical"))
    high_count = _int_value(governance_risk_counts.get("high"))
    medium_count = _int_value(governance_risk_counts.get("medium"))
    low_count = _int_value(governance_risk_counts.get("low"))
    blocked_24h = _int_value(summary_24h.get("blocked_events"))
    total_events_24h = _int_value(summary_24h.get("total_events"))
    block_rate_24h = _float_value(summary_24h.get("block_rate"))
    top_alert_code = str(summary_24h.get("top_alert_code", "")).strip()
    total_clusters = _int_value(cluster_data.get("total_clusters"))
    total_failed_reports = _int_value(cluster_data.get("total_failed_reports"))
    manual_review_cluster_count = sum(
        1 for item in cluster_rows if _int_value(item.get("requires_manual_review_count")) > 0
    )
    manifest_backfill_candidate_count = _int_value(task_summary.get("manifest_backfill_candidate_count"))
    no_manifest_task_count = _int_value(task_summary.get("no_manifest_task_count"))
    multisource_task_count = _int_value(task_summary.get("multisource_task_count"))
    traceability_gap_task_count = _int_value(task_summary.get("traceability_gap_task_count"))
    strict_mode_ready_task_count = _int_value(task_summary.get("strict_mode_ready_task_count"))
    strict_mode_caution_task_count = _int_value(task_summary.get("strict_mode_caution_task_count"))
    strict_mode_blocked_task_count = _int_value(task_summary.get("strict_mode_blocked_task_count"))
    strict_mode_status_counts = _dict_value(task_summary.get("strict_mode_status_counts"))
    multisource_source_type_counts = _dict_value(task_summary.get("multisource_source_type_counts"))
    strict_mode_readiness = _dict_value(task_summary.get("strict_mode_readiness"))
    if not strict_mode_readiness:
        execution_meta = _dict_value(task_summary.get("execution_meta"))
        strict_mode_readiness = _dict_value(execution_meta.get("strict_mode_readiness"))
    top_cluster = cluster_rows[0] if cluster_rows else {}

    total_tasks_safe = max(total_tasks, 1)
    critical_ratio = critical_count / total_tasks_safe
    high_ratio = high_count / total_tasks_safe
    medium_ratio = medium_count / total_tasks_safe
    no_manifest_ratio = no_manifest_task_count / total_tasks_safe
    backfill_ratio = manifest_backfill_candidate_count / total_tasks_safe

    severity_weight = {"S0": 8, "S1": 6, "S2": 4, "S3": 2, "S4": 1}
    top_cluster_severity = str(top_cluster.get("severity", "S4")).strip().upper()
    top_cluster_weight = severity_weight.get(top_cluster_severity, 0)
    top_cluster_manual_ratio = _float_value(top_cluster.get("manual_review_ratio"))

    risk_score = int(
        min(
            100,
            round(
                critical_ratio * 45
                + high_ratio * 28
                + medium_ratio * 12
                + block_rate_24h * 20
                + no_manifest_ratio * 12
                + backfill_ratio * 8
                + min(total_clusters, 10) * 1.5
                + top_cluster_weight
                + top_cluster_manual_ratio * 8
            )
        )
    )
    level = _risk_level(risk_score)
    risk_summary = _risk_summary(
        level=level,
        critical_count=critical_count,
        high_count=high_count,
        blocked_24h=blocked_24h,
        block_rate_24h=block_rate_24h,
        top_alert_code=top_alert_code,
        manifest_backfill_candidate_count=manifest_backfill_candidate_count,
        total_clusters=total_clusters,
    )

    top_governance_risks = []
    governance_risk_top_items = _list_value(task_summary.get("governance_risk_top_items"))
    for item in governance_risk_top_items[:5]:
        if not isinstance(item, dict):
            continue
        level_code = str(item.get("governance_risk_level", "")).strip().lower() or "unknown"
        gate_recommendation = str(item.get("gate_recommendation", "")).strip()
        gate_recommendation_reason = str(item.get("gate_recommendation_reason", "")).strip()
        if not gate_recommendation:
            gate_recommendation, gate_recommendation_reason = _default_gate_recommendation(item)
        score_breakdown = _build_governance_item_score_breakdown(item)
        top_governance_risks.append(
            {
                "task_id": str(item.get("task_id", "")).strip(),
                "run_id": str(item.get("run_id", "")).strip(),
                "case_id": str(item.get("case_id", "")).strip(),
                "page": str(item.get("page", "")).strip(),
                "queue_status": str(item.get("queue_status", "")).strip(),
                "manifest_action": str(item.get("manifest_action", "")).strip(),
                "evidence_health_status": str(item.get("evidence_health_status", "")).strip(),
                "governance_risk_level": level_code,
                "governance_risk_score": _int_value(item.get("governance_risk_score")),
                "governance_risk_reason": str(item.get("governance_risk_reason", "")).strip(),
                "source_count": _int_value(item.get("source_count")),
                "source_types": [str(value).strip() for value in (item.get("source_types") or []) if str(value).strip()],
                "traceability_completeness": _float_value(item.get("traceability_completeness")),
                "has_traceability_gap": bool(item.get("has_traceability_gap", False)),
                "changed_areas": [str(value).strip() for value in (item.get("changed_areas") or []) if str(value).strip()],
                "top_factor": item.get("top_factor", {}) if isinstance(item.get("top_factor"), dict) else {},
                "recommended_regression_scope": item.get("recommended_regression_scope", []) if isinstance(item.get("recommended_regression_scope"), list) else [],
                "gate_recommendation": gate_recommendation,
                "gate_recommendation_reason": gate_recommendation_reason,
                "risk_score_breakdown": score_breakdown,
                "status": _issue_status(level_code),
                "href": _query_href(
                    "/execution/runs",
                    task_id=str(item.get("task_id", "")).strip() or None,
                    run_id=str(item.get("run_id", "")).strip() or None,
                    case_id=str(item.get("case_id", "")).strip() or None,
                    page=str(item.get("page", "")).strip() or None,
                    risk_levels=level_code,
                    traceability_gap=1 if bool(item.get("has_traceability_gap", False)) else None,
                    changed_area=[
                        str(value).strip()
                        for value in (item.get("changed_areas") or [])
                        if str(value).strip()
                    ],
                ),
            }
        )

    top_clusters = []
    for item in cluster_rows[:5]:
        if not isinstance(item, dict):
            continue
        top_clusters.append(
            {
                "cluster_id": str(item.get("cluster_id", "")).strip(),
                "failure_class": str(item.get("failure_class", "")).strip(),
                "queue": str(item.get("queue", "")).strip(),
                "severity": str(item.get("severity", "")).strip(),
                "occurrence_count": _int_value(item.get("occurrence_count")),
                "manual_review_ratio": _float_value(item.get("manual_review_ratio")),
                "latest_case_id": str(item.get("latest_case_id", "")).strip(),
                "href": _query_href(
                    "/quality/failure-clusters",
                    cluster_id=str(item.get("cluster_id", "")).strip() or None,
                    failure_class=str(item.get("failure_class", "")).strip() or None,
                    queue=str(item.get("queue", "")).strip() or None,
                    severity=str(item.get("severity", "")).strip() or None,
                    manual_review=1 if _float_value(item.get("manual_review_ratio")) > 0 else None,
                ),
            }
        )

    degraded = [str(item).strip() for item in (degraded_sources or []) if str(item).strip()]
    failure_cluster_analysis = _build_failure_cluster_analysis(
        cluster_rows=cluster_rows,
        top_risks=top_governance_risks,
        trend_summary_7d=trend_summary_7d,
        flaky_rows=flaky_rows,
    )
    flaky_analysis = _build_flaky_analysis(
        flaky_rows=flaky_rows,
        top_risks=top_governance_risks,
    )
    execution_strategy = _build_execution_strategy(
        task_summary=task_summary,
        top_risks=top_governance_risks,
        risk_level=level,
        manual_review_cluster_count=manual_review_cluster_count,
        block_rate_24h=block_rate_24h,
    )
    summary_links = {
        "high_risk_tasks": _query_href(
            "/execution/runs",
            risk_levels="critical,high",
            sort="governance_risk",
            traceability_gap=1 if traceability_gap_task_count > 0 else None,
        ),
        "no_manifest_tasks": _query_href(
            "/execution/runs",
            manifest="no_manifest,backfill_candidate",
            sort="evidence_health",
        ),
        "failure_clusters": _query_href(
            "/quality/failure-clusters",
            severity=str(top_cluster.get("severity", "")).strip() or None,
            failure_class=str(top_cluster.get("failure_class", "")).strip() or None,
        ),
        "manual_review_clusters": _query_href(
            "/quality/failure-clusters",
            manual_review=1,
            alert_code=top_alert_code or None,
            cluster_id=str(top_cluster.get("cluster_id", "")).strip() or None,
        ),
    }
    trend_links = {
        "quality_gate_blocked": _query_href(
            "/quality/failure-clusters",
            manual_review=1 if manual_review_cluster_count > 0 else None,
            alert_code=top_alert_code or None,
            severity=str(top_cluster.get("severity", "")).strip() or None,
        ),
        "risk_blocked_runs": _query_href(
            "/quality/trends",
            view="governance",
            direction="risk_blocked",
            window="7d",
            alert_code=top_alert_code or None,
        ),
        "review_required_runs": _query_href(
            "/execution/runs",
            review_required=1,
            sort="governance_risk",
            risk_levels="critical,high" if critical_count + high_count > 0 else None,
        ),
        "direction": _query_href(
            "/quality/trends",
            view="governance",
            direction=str(trend_summary_7d.get("direction", "stable")).strip() or "stable",
            window="14d",
            alert_code=top_alert_code or None,
        ),
    }
    manager_summary = _build_manager_summary(
        level=level,
        risk_score=risk_score,
        blocked_24h=blocked_24h,
        block_rate_24h=block_rate_24h,
        total_clusters=total_clusters,
        manual_review_cluster_count=manual_review_cluster_count,
        multisource_task_count=multisource_task_count,
        traceability_gap_task_count=traceability_gap_task_count,
        no_manifest_task_count=no_manifest_task_count,
        manifest_backfill_candidate_count=manifest_backfill_candidate_count,
        critical_count=critical_count,
        high_count=high_count,
        top_alert_code=top_alert_code,
        multisource_source_type_counts=multisource_source_type_counts,
        strict_mode_readiness=strict_mode_readiness,
        strict_mode_blocked_task_count=strict_mode_blocked_task_count,
        strict_mode_caution_task_count=strict_mode_caution_task_count,
    )
    strict_manifest_policy = _build_strict_manifest_policy(
        strict_mode_readiness=strict_mode_readiness,
        strict_mode_ready_task_count=strict_mode_ready_task_count,
        strict_mode_caution_task_count=strict_mode_caution_task_count,
        strict_mode_blocked_task_count=strict_mode_blocked_task_count,
    )
    risk_score_breakdown = _build_risk_score_breakdown(
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        block_rate_24h=block_rate_24h,
        no_manifest_task_count=no_manifest_task_count,
        manifest_backfill_candidate_count=manifest_backfill_candidate_count,
        total_tasks=total_tasks,
        total_clusters=total_clusters,
        top_cluster_weight=top_cluster_weight,
        top_cluster_manual_ratio=top_cluster_manual_ratio,
    )
    return {
        "as_of": timestamp.isoformat(),
        "risk": {
            "score": risk_score,
            "level": level,
            "summary": risk_summary,
            "score_breakdown": risk_score_breakdown,
            "detail_url": "/quality/trends",
        },
        "summary": {
            "total_tasks": total_tasks,
            "high_risk_task_count": critical_count + high_count,
            "critical_risk_task_count": critical_count,
            "medium_risk_task_count": medium_count,
            "low_risk_task_count": low_count,
            "blocked_events_24h": blocked_24h,
            "total_gate_events_24h": total_events_24h,
            "block_rate_24h": round(block_rate_24h, 3),
            "failure_cluster_count": total_clusters,
            "manual_review_cluster_count": manual_review_cluster_count,
            "manifest_backfill_candidate_count": manifest_backfill_candidate_count,
            "no_manifest_task_count": no_manifest_task_count,
            "multisource_task_count": multisource_task_count,
            "traceability_gap_task_count": traceability_gap_task_count,
            "multisource_source_type_counts": dict(sorted(multisource_source_type_counts.items())),
            "strict_mode_status_counts": dict(sorted(strict_mode_status_counts.items())),
            "strict_mode_ready_task_count": strict_mode_ready_task_count,
            "strict_mode_caution_task_count": strict_mode_caution_task_count,
            "strict_mode_blocked_task_count": strict_mode_blocked_task_count,
            "strict_mode_readiness": strict_mode_readiness,
            "strict_manifest_policy": strict_manifest_policy,
            "top_alert_code": top_alert_code,
            "top_alert_count": _int_value(summary_24h.get("top_alert_count")),
            "as_of": timestamp.isoformat(),
            "links": summary_links,
        },
        "quality_gate": {
            "summary_24h": summary_24h,
            "blocker_distribution": (quality_gate.get("blocker_distribution") or [])[:5],
            "recent_blocked": (quality_gate.get("recent_blocked") or [])[:5],
        },
        "failure_clusters": {
            "total_clusters": total_clusters,
            "total_failed_reports": total_failed_reports,
            "top_clusters": top_clusters,
            "analysis": failure_cluster_analysis,
        },
        "flaky_analysis": flaky_analysis,
        "execution_strategy": execution_strategy,
        "trend_14d": trend_items,
        "trend_summary_7d": {
            **trend_summary_7d,
            "links": trend_links,
        },
        "tasks": {
            "summary": task_summary,
        },
        "top_governance_risks": top_governance_risks,
        "action_items": _build_action_items(
            critical_count=critical_count,
            high_count=high_count,
            blocked_24h=blocked_24h,
            block_rate_24h=block_rate_24h,
            top_alert_code=top_alert_code,
            manifest_backfill_candidate_count=manifest_backfill_candidate_count,
            no_manifest_task_count=no_manifest_task_count,
            traceability_gap_task_count=traceability_gap_task_count,
            multisource_task_count=multisource_task_count,
            total_clusters=total_clusters,
            top_cluster=top_cluster if isinstance(top_cluster, dict) else {},
            strict_mode_readiness=strict_mode_readiness,
            strict_mode_blocked_task_count=strict_mode_blocked_task_count,
            strict_mode_caution_task_count=strict_mode_caution_task_count,
        ),
        "metric_definitions": {
            "high_risk_task_count": "critical + high 级执行治理风险任务数量。",
            "block_rate_24h": "最近 24 小时 quality gate 阻断率，分母为同窗口内全部门禁评估事件。",
            "manual_review_cluster_count": "当前失败聚类中仍需人工确认归因的聚类数量。",
            "no_manifest_task_count": "缺失 evidence manifest 的执行任务数量，会影响证据可信度与审计回放。",
            "multisource_task_count": "已消费 OpenAPI、Git Diff、JIRA 等多输入源的执行任务数量。",
            "traceability_gap_task_count": "多源任务中 traceability 不完整的任务数量。",
            "top_alert_code": "最近 24 小时 quality gate 命中次数最高的告警码。",
            "pressure_score": "按门禁阻断、风险阻断、需复核和自愈关注度聚合的治理压力指标。",
            "strict_mode_readiness": "manifest-first 稳定度指标，用于评估是否适合收紧 execution_record compat_scan。",
            "strict_mode_blocked_task_count": "当前不适合关闭 compat_scan 的任务数量，通常包含缺失 manifest 或 compat scan 命中。",
            "strict_manifest_policy": "strict manifest-first 当前建议策略，包含是否建议关闭 compat_scan 以及下一步动作。",
            "recommended_regression_pack": "根据变更影响、多源追溯状态与治理风险生成的推荐执行范围。",
            "gate_recommendation": "治理服务建议采用的执行门禁等级，取值为 allow / manual_review / block。",
        },
        "manager_summary": manager_summary,
        "degraded": bool(degraded),
        "degraded_sources": degraded,
    }


def build_flaky_top5(
    cases: list[TestCase],
    executions: list[TestCaseExecution],
) -> list[dict[str, Any]]:
    """从用例和执行记录中计算 flaky top5 排行。

    算法：transition_ratio * 70 + failed_ratio * 30（≥2 次执行时），
    否则基于 case_id 种子值降级估算。
    """

    case_runs: dict[int, list[TestCaseExecution]] = defaultdict(list)
    for item in executions:
        case_runs[item.case_id].append(item)

    flaky_rows: list[dict[str, Any]] = []
    for case in cases:
        runs = sorted(case_runs.get(case.id, []), key=lambda item: (to_utc(item.executed_at), item.id))
        statuses = [(item.status or "unknown").lower() for item in runs]
        total_runs = len(statuses)
        if total_runs >= 2:
            transitions = sum(1 for idx in range(1, total_runs) if statuses[idx] != statuses[idx - 1])
            failed = sum(1 for value in statuses if value == "failed")
            transition_ratio = transitions / (total_runs - 1)
            failed_ratio = failed / total_runs
            flaky_rate = round(min(100.0, transition_ratio * 70 + failed_ratio * 30), 1)
            unstable_runs = transitions
        else:
            seed = ((case.id * 17) % 25) + 8
            last = (case.last_execution_result or "unknown").lower()
            if last == "failed":
                flaky_rate = min(98.0, float(seed + 24))
            elif last == "skipped":
                flaky_rate = min(90.0, float(seed + 12))
            else:
                flaky_rate = float(seed)
            unstable_runs = 0
        flaky_rows.append(
            {
                "case_id": case.id,
                "name": case.name,
                "module": case.module,
                "flaky_rate": flaky_rate,
                "total_runs": total_runs,
                "unstable_runs": unstable_runs,
                "last_result": case.last_execution_result or "unknown",
            }
        )
    return sorted(flaky_rows, key=lambda item: item["flaky_rate"], reverse=True)[:5]


def build_dashboard_overview(db: Session) -> dict[str, Any]:
    """聚合 dashboard 概览数据：24h 趋势、flaky top5、门禁事件、待确认 issues、风险评分。"""
    now = datetime.now(UTC)
    try:
        test_case_service.ensure_seed_data(db)
        repo = TestCaseRepository(db)
        cases = repo.list_all()
        executions = repo.list_all_executions_ordered()
        case_map = {item.id: item for item in cases}

        base = (now - timedelta(hours=23)).replace(minute=0, second=0, microsecond=0)
        buckets: dict[datetime, dict[str, int]] = {
            base + timedelta(hours=i): {"total": 0, "passed": 0}
            for i in range(24)
        }
        for item in executions:
            executed_at = to_utc(item.executed_at).replace(minute=0, second=0, microsecond=0)
            if executed_at not in buckets:
                continue
            buckets[executed_at]["total"] += 1
            if (item.status or "").lower() == "passed":
                buckets[executed_at]["passed"] += 1

        total = sum(v["total"] for v in buckets.values())
        passed = sum(v["passed"] for v in buckets.values())
        base_pass_rate = round((passed / total * 100) if total > 0 else 100.0, 1)

        trend: list[dict[str, Any]] = []
        for i in range(24):
            hour = base + timedelta(hours=i)
            total_runs = buckets[hour]["total"]
            pass_rate = round((buckets[hour]["passed"] / total_runs * 100), 1) if total_runs > 0 else base_pass_rate
            trend.append(
                {
                    "hour": hour.strftime("%H:%M"),
                    "pass_rate": pass_rate,
                    "execution_count": total_runs,
                }
            )

        flaky_rows = build_flaky_top5(list(cases), list(executions))

        sorted_runs = sorted(executions, key=lambda item: (to_utc(item.executed_at), item.id), reverse=True)[:10]
        gate_rows: list[dict[str, Any]] = []
        for item in sorted_runs:
            item_status = (item.status or "unknown").lower()
            if item_status == "failed":
                gate_status = "intercepted"
                reason = "失败率超过门禁阈值"
            elif item_status == "passed":
                gate_status = "passed"
                reason = "门禁规则校验通过"
            else:
                gate_status = "warning"
                reason = "前置数据不足，需人工复核"
            case = case_map.get(item.case_id)
            gate_rows.append(
                {
                    "execution_id": item.id,
                    "pr_key": f"PR-{6800 + item.id}",
                    "branch": f"feature/case-{item.case_id}",
                    "gate_rule": "主分支质量门禁",
                    "gate_status": gate_status,
                    "reason": reason,
                    "case_name": case.name if case else f"用例#{item.case_id}",
                    "executed_at": to_utc(item.executed_at).isoformat(),
                }
            )
        if len(gate_rows) < 10:
            for index in range(len(gate_rows), 10):
                gate_rows.append(
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

        sorted_runs_desc = sorted(executions, key=lambda item: (to_utc(item.executed_at), item.id), reverse=True)
        pending_issues: list[dict[str, Any]] = []
        for item in sorted_runs_desc:
            item_status = (item.status or "unknown").lower()
            if item_status not in {"failed", "skipped"}:
                continue
            case = case_map.get(item.case_id)
            if item_status == "failed":
                recommendation = "疑似断言与页面状态不一致，建议先复核选择器和等待策略。"
                confidence = 0.82 + ((item.id % 7) * 0.01)
            else:
                recommendation = "疑似环境前置条件未满足，建议检查测试数据和依赖服务健康度。"
                confidence = 0.68 + ((item.id % 5) * 0.01)
            pending_issues.append(
                {
                    "issue_key": f"ISS-{9000 + item.id}",
                    "title": f"{case.name if case else f'用例#{item.case_id}'} 待确认",
                    "agent": "失败归因 Agent",
                    "confidence": round(min(confidence, 0.95), 2),
                    "status": "待确认",
                    "recommendation": recommendation,
                    "detail_url": f"/cases/{item.case_id}",
                }
            )
            if len(pending_issues) >= 6:
                break
        if not pending_issues:
            for idx, row in enumerate(flaky_rows[:3], start=1):
                pending_issues.append(
                    {
                        "issue_key": f"ISS-F{idx:03d}",
                        "title": f"{row['name']} 波动风险复核",
                        "agent": "失败归因 Agent",
                        "confidence": round(min(0.6 + row["flaky_rate"] / 200, 0.93), 2),
                        "status": "待确认",
                        "recommendation": "建议补充稳定性断言并提高重试与隔离策略。",
                        "detail_url": f"/cases/{row['case_id']}",
                    }
                )

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
                "as_of": now.isoformat(),
            },
            "trend_24h": trend,
            "top_flaky": flaky_rows,
            "gate_last10": gate_rows,
            "pending_issues": pending_issues,
        }
    except Exception:
        LOGGER.exception("dashboard overview degraded due to backend error")
        return default_overview(now, reason="dashboard_backend_error")
