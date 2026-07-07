from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from datetime_compat import UTC
from sqlalchemy.orm import Session

from app.api.workbench._helpers import default_overview, to_utc
from app.models.test_case import TestCase, TestCaseExecution
from app.repositories.test_case_repository import TestCaseRepository
from app.services import test_case_service
from shared_backend.type_utils import dict_value as _dict_value, float_value as _float_value, int_value as _int_value, list_value as _list_value

LOGGER = logging.getLogger(__name__)



def _risk_level(score: int) -> str:
    if score >= 70:
        return "高"
    if score >= 40:
        return "中"
    return "低"


def _risk_summary(
    *,
    level: str,
    critical_count: int,
    high_count: int,
    blocked_24h: int,
    block_rate_24h: float,
    top_alert_code: str,
    manifest_backfill_candidate_count: int,
    total_clusters: int,
) -> str:
    if critical_count > 0:
        return "存在关键治理风险任务，建议优先处理高风险执行与证据缺口。"
    if blocked_24h > 0 and block_rate_24h >= 0.30:
        return f"质量门禁近期阻断偏高，优先关注告警 {top_alert_code or '-'}。"
    if manifest_backfill_candidate_count > 0:
        return "执行证据存在待回填任务，建议先补齐 manifest 与 execution record。"
    if total_clusters > 0:
        return "失败聚类已形成集中热点，建议按聚类优先级推进归因和修复。"
    if level == "中" and high_count > 0:
        return "治理风险可控，但需要持续跟踪高风险任务和门禁阻断。"
    return "治理态势整体稳定，可以继续推进回归与发布节奏。"


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _issue_status(level: str) -> str:
    normalized = str(level or "").strip().lower()
    if normalized in {"critical", "high"}:
        return "待优先处理"
    if normalized == "medium":
        return "持续跟进"
    return "观察中"


def _query_href(path: str, **params: Any) -> str:
    query: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            if value:
                query[key] = "1"
            continue
        if isinstance(value, (list, tuple, set)):
            items = [str(item).strip() for item in value if str(item).strip()]
            if items:
                query[key] = ",".join(items)
            continue
        text = str(value).strip()
        if text:
            query[key] = text
    if not query:
        return path
    return f"{path}?{urlencode(query)}"


def _severity_score(value: Any) -> int:
    normalized = str(value or "").strip().upper()
    return {"S0": 10, "S1": 8, "S2": 6, "S3": 3, "S4": 1}.get(normalized, 0)


def _build_governance_item_score_breakdown(item: dict[str, Any]) -> dict[str, Any]:
    level = str(item.get("governance_risk_level", "")).strip().lower()
    source_count = _int_value(item.get("source_count"))
    traceability_completeness = _float_value(item.get("traceability_completeness"))
    changed_area_count = len([value for value in (item.get("changed_areas") or []) if str(value).strip()])
    manifest_action = str(item.get("manifest_action", "")).strip().lower()
    evidence_health_status = str(item.get("evidence_health_status", "")).strip().lower()
    top_factor = _dict_value(item.get("top_factor"))
    top_factor_name = str(top_factor.get("factor", "")).strip().lower()
    level_score = {"critical": 40, "high": 28, "medium": 16, "low": 6}.get(level, 0)
    traceability_score = 18 if bool(item.get("has_traceability_gap", False)) else int(round((1 - traceability_completeness) * 10))
    multisource_score = min(15, source_count * 4)
    change_impact_score = min(15, changed_area_count * 5)
    manifest_score = 10 if manifest_action in {"backfill_manifest", "await_runtime_flush"} else 0
    evidence_score = 8 if evidence_health_status in {"degraded", "critical"} else 0
    factor_score = 8 if top_factor_name in {"api_contract", "business_rule", "permission"} else 3 if top_factor_name else 0
    total = level_score + traceability_score + multisource_score + change_impact_score + manifest_score + evidence_score + factor_score
    if total >= 70:
        priority_band = "critical"
    elif total >= 45:
        priority_band = "high"
    elif total >= 20:
        priority_band = "medium"
    else:
        priority_band = "low"
    return {
        "model_version": "governance-risk-v2",
        "priority_band": priority_band,
        "total_score": total,
        "components": {
            "level_score": level_score,
            "traceability_score": traceability_score,
            "multisource_score": multisource_score,
            "change_impact_score": change_impact_score,
            "manifest_score": manifest_score,
            "evidence_score": evidence_score,
            "factor_score": factor_score,
        },
    }


def _build_strict_manifest_policy(
    *,
    strict_mode_readiness: dict[str, Any],
    strict_mode_ready_task_count: int,
    strict_mode_caution_task_count: int,
    strict_mode_blocked_task_count: int,
) -> dict[str, Any]:
    readiness = strict_mode_readiness if isinstance(strict_mode_readiness, dict) else {}
    mode = str(readiness.get("status", "")).strip() or "unknown"
    if strict_mode_blocked_task_count > 0:
        next_action = "优先消化 blocked 任务，再考虑关闭 compat_scan。"
    elif strict_mode_caution_task_count > 0:
        next_action = "优先推动 runtime flush / manifest 落盘，继续观察 caution 任务。"
    elif strict_mode_ready_task_count > 0:
        next_action = "可以选择小范围禁用 compat_scan，验证 strict manifest-first。"
    else:
        next_action = "当前暂无足够样本，继续积累 manifest-first 任务。"
    return {
        "mode": mode,
        "score": round(_float_value(readiness.get("score")), 3),
        "can_disable_compat_scan": bool(readiness.get("can_disable_compat_scan", False)),
        "ready_task_count": strict_mode_ready_task_count,
        "caution_task_count": strict_mode_caution_task_count,
        "blocked_task_count": strict_mode_blocked_task_count,
        "next_action": next_action,
        "reason": str(readiness.get("reason", "")).strip(),
    }


def _build_risk_score_breakdown(
    *,
    critical_count: int,
    high_count: int,
    medium_count: int,
    block_rate_24h: float,
    no_manifest_task_count: int,
    manifest_backfill_candidate_count: int,
    total_tasks: int,
    total_clusters: int,
    top_cluster_weight: int,
    top_cluster_manual_ratio: float,
) -> dict[str, Any]:
    total_tasks_safe = max(total_tasks, 1)
    critical_component = round((critical_count / total_tasks_safe) * 45, 1)
    high_component = round((high_count / total_tasks_safe) * 28, 1)
    medium_component = round((medium_count / total_tasks_safe) * 12, 1)
    block_rate_component = round(block_rate_24h * 20, 1)
    manifest_gap_component = round((no_manifest_task_count / total_tasks_safe) * 12, 1)
    manifest_backfill_component = round((manifest_backfill_candidate_count / total_tasks_safe) * 8, 1)
    cluster_component = round(min(total_clusters, 10) * 1.5 + top_cluster_weight + top_cluster_manual_ratio * 8, 1)
    return {
        "model_version": "governance-score-v2",
        "components": {
            "critical_component": critical_component,
            "high_component": high_component,
            "medium_component": medium_component,
            "block_rate_component": block_rate_component,
            "manifest_gap_component": manifest_gap_component,
            "manifest_backfill_component": manifest_backfill_component,
            "cluster_component": cluster_component,
        },
    }


def _build_failure_cluster_analysis(
    *,
    cluster_rows: list[dict[str, Any]],
    top_risks: list[dict[str, Any]],
    trend_summary_7d: dict[str, Any],
    flaky_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    risk_pages = {
        str(item.get("page", "")).strip()
        for item in top_risks
        if isinstance(item, dict) and str(item.get("page", "")).strip()
    }
    risk_factors = {
        str((item.get("top_factor") or {}).get("factor", "")).strip()
        for item in top_risks
        if isinstance(item, dict) and isinstance(item.get("top_factor"), dict)
    }
    flaky_modules = {
        str(item.get("module", "")).strip()
        for item in flaky_rows
        if isinstance(item, dict) and str(item.get("module", "")).strip()
    }

    prioritized: list[dict[str, Any]] = []
    for cluster in cluster_rows:
        if not isinstance(cluster, dict):
            continue
        occurrence_count = _int_value(cluster.get("occurrence_count"))
        manual_review_ratio = _float_value(cluster.get("manual_review_ratio"))
        latest_case_id = str(cluster.get("latest_case_id", "")).strip()
        queue = str(cluster.get("queue", "")).strip()
        failure_class = str(cluster.get("failure_class", "")).strip()
        matched_pages = [page for page in risk_pages if page and (page in latest_case_id.lower() or page == queue)]
        matched_factors = [
            factor
            for factor in risk_factors
            if factor and (factor in failure_class.lower() or (factor == "ui_selector" and "selector" in failure_class.lower()))
        ]
        matched_flaky_modules = [module for module in flaky_modules if module and module in latest_case_id.lower()]
        priority_score = (
            occurrence_count * 4
            + _severity_score(cluster.get("severity"))
            + int(round(manual_review_ratio * 10))
            + len(matched_pages) * 5
            + len(matched_factors) * 5
            + len(matched_flaky_modules) * 4
        )
        if occurrence_count >= 5:
            stability = "persistent"
        elif occurrence_count >= 3:
            stability = "recurring"
        else:
            stability = "emerging"
        if priority_score >= 30:
            repair_yield = "high"
        elif priority_score >= 16:
            repair_yield = "medium"
        else:
            repair_yield = "low"
        trend_pressure = _int_value(trend_summary_7d.get("quality_gate_blocked")) + _int_value(trend_summary_7d.get("risk_blocked_runs"))
        overlap_count = len(matched_pages) + len(matched_factors)
        reasons: list[str] = []
        if matched_factors:
            reasons.append(f"与变更影响因子 {', '.join(matched_factors)} 重合")
        if matched_pages:
            reasons.append(f"与高风险页面 {', '.join(matched_pages)} 重合")
        if matched_flaky_modules:
            reasons.append(f"与 Flaky 模块 {', '.join(matched_flaky_modules)} 重合")
        if manual_review_ratio > 0:
            reasons.append(f"人工复核占比 {round(manual_review_ratio * 100)}%")
        reasons.append(f"近窗口累计出现 {occurrence_count} 次")
        prioritized.append(
            {
                "cluster_id": str(cluster.get("cluster_id", "")).strip(),
                "severity": str(cluster.get("severity", "")).strip(),
                "failure_class": failure_class,
                "queue": queue,
                "occurrence_count": occurrence_count,
                "priority_score": priority_score,
                "stability": stability,
                "repair_yield_estimate": repair_yield,
                "trend_pressure": trend_pressure,
                "risk_overlap_count": overlap_count,
                "flaky_overlap_count": len(matched_flaky_modules),
                "reason": "；".join(item for item in reasons if item),
                "href": _query_href(
                    "/quality/failure-clusters",
                    cluster_id=str(cluster.get("cluster_id", "")).strip() or None,
                    failure_class=failure_class or None,
                    queue=queue or None,
                    severity=str(cluster.get("severity", "")).strip() or None,
                    manual_review=1 if _int_value(cluster.get("requires_manual_review_count")) > 0 else None,
                ),
            }
        )
    prioritized.sort(
        key=lambda item: (
            -_int_value(item.get("priority_score")),
            -_int_value(item.get("occurrence_count")),
            str(item.get("cluster_id", "")),
        )
    )
    focus_cluster = prioritized[0] if prioritized else {}
    pressure_direction = str(trend_summary_7d.get("direction", "stable")).strip() or "stable"
    return {
        "focus_cluster": focus_cluster,
        "top_priority_clusters": prioritized[:3],
        "trend_direction": pressure_direction,
        "summary": (
            f"当前最值得优先治理的 cluster 是 {str(focus_cluster.get('cluster_id', '')).strip() or '-'}，"
            f"原因是 {str(focus_cluster.get('reason', '')).strip() or '暂无明显热点'}。"
            if focus_cluster
            else "当前暂无可优先排序的失败聚类热点。"
        ),
    }


def _build_flaky_analysis(
    *,
    flaky_rows: list[dict[str, Any]],
    top_risks: list[dict[str, Any]],
) -> dict[str, Any]:
    linked_items: list[dict[str, Any]] = []
    for flaky in flaky_rows[:5]:
        if not isinstance(flaky, dict):
            continue
        module = str(flaky.get("module", "")).strip()
        matched_risks = [
            risk
            for risk in top_risks
            if isinstance(risk, dict) and module and str(risk.get("page", "")).strip() == module
        ]
        factors = sorted(
            {
                str((risk.get("top_factor") or {}).get("factor", "")).strip()
                for risk in matched_risks
                if isinstance(risk.get("top_factor"), dict) and str((risk.get("top_factor") or {}).get("factor", "")).strip()
            }
        )
        changed_areas = sorted(
            {
                str(area).strip()
                for risk in matched_risks
                for area in (risk.get("changed_areas") or [])
                if str(area).strip()
            }
        )
        if matched_risks:
            reason = (
                f"模块 {module or '-'} 同时出现在高风险执行任务中，"
                f"关联因子 {', '.join(factors) if factors else '-'}，"
                f"变更域 {', '.join(changed_areas) if changed_areas else '-'}。"
            )
        else:
            reason = f"模块 {module or '-'} 当前为独立 Flaky 热点，建议先补稳定性断言。"
        linked_items.append(
            {
                "case_id": _int_value(flaky.get("case_id")),
                "name": str(flaky.get("name", "")).strip(),
                "module": module,
                "flaky_rate": _float_value(flaky.get("flaky_rate")),
                "matched_risk_task_count": len(matched_risks),
                "risk_overlap_ratio": round(len(matched_risks) / max(1, len(top_risks)), 3),
                "matched_factors": factors,
                "changed_areas": changed_areas,
                "stability_score": max(0, 100 - int(round(_float_value(flaky.get("flaky_rate"))))),
                "reason": reason,
                "href": _query_href("/execution/runs", page=module or None, changed_area=changed_areas),
            }
        )
    linked_count = sum(1 for item in linked_items if _int_value(item.get("matched_risk_task_count")) > 0)
    return {
        "linked_count": linked_count,
        "items": linked_items[:3],
        "summary": (
            f"Top Flaky 用例中有 {linked_count} 个已与多源变更风险形成重合。"
            if linked_items
            else "当前暂无可分析的 Flaky 用例。"
        ),
    }


def _build_execution_strategy(
    *,
    task_summary: dict[str, Any],
    top_risks: list[dict[str, Any]],
    risk_level: str,
    manual_review_cluster_count: int,
    block_rate_24h: float,
) -> dict[str, Any]:
    scope_counts_raw = _dict_value(task_summary.get("recommended_regression_scope_counts"))
    scope_counts = {
        str(key).strip(): _int_value(value)
        for key, value in scope_counts_raw.items()
        if str(key).strip()
    }
    gate_counts_raw = _dict_value(task_summary.get("gate_recommendation_counts"))
    gate_counts = {
        str(key).strip(): _int_value(value)
        for key, value in gate_counts_raw.items()
        if str(key).strip()
    }
    if not gate_counts:
        for risk in top_risks:
            if not isinstance(risk, dict):
                continue
            gate_key = str(risk.get("gate_recommendation", "")).strip()
            if gate_key:
                gate_counts[gate_key] = gate_counts.get(gate_key, 0) + 1
    recommended_pack = str(task_summary.get("recommended_regression_pack", "")).strip() or "targeted_regression"
    if gate_counts.get("block", 0) > 0 or risk_level == "高":
        gate_recommendation = "block"
    elif gate_counts.get("manual_review", 0) > 0 or manual_review_cluster_count > 0 or block_rate_24h >= 0.25:
        gate_recommendation = "manual_review"
    else:
        gate_recommendation = "allow"
    if gate_recommendation == "block":
        gate_reason = "当前存在 critical 风险或治理压力过高，建议先阻断并完成治理。"
    elif gate_recommendation == "manual_review":
        gate_reason = "当前风险可控但存在人工复核信号，建议提升为 manual review。"
    else:
        gate_reason = "当前治理风险可控，可沿默认门禁策略继续推进。"
    if not scope_counts:
        for risk in top_risks[:3]:
            if not isinstance(risk, dict):
                continue
            for scope in risk.get("recommended_regression_scope", []) if isinstance(risk.get("recommended_regression_scope"), list) else []:
                normalized_scope = str(scope).strip()
                if normalized_scope:
                    scope_counts[normalized_scope] = scope_counts.get(normalized_scope, 0) + 1
    recommended_scopes = [
        {"scope": scope, "count": count}
        for scope, count in sorted(scope_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    if recommended_pack == "broad_regression":
        pack_reason = "高风险任务或 block 建议较多，建议执行广覆盖回归包。"
    elif recommended_pack == "smoke_plus_impacted":
        pack_reason = "建议先跑 impacted 范围，再叠加关键 smoke，兼顾速度与风险。"
    else:
        pack_reason = "当前可按 targeted regression 执行，优先覆盖变更相关域。"
    return {
        "recommended_pack": recommended_pack,
        "recommended_scopes": recommended_scopes[:5],
        "gate_recommendation": gate_recommendation,
        "gate_reason": gate_reason,
        "pack_reason": pack_reason,
        "href": _query_href("/execution/runs", risk_levels="critical,high" if gate_recommendation != "allow" else None),
    }


def _default_gate_recommendation(item: dict[str, Any]) -> tuple[str, str]:
    level = str(item.get("governance_risk_level", "")).strip().lower()
    has_gap = bool(item.get("has_traceability_gap", False))
    source_count = _int_value(item.get("source_count"))
    factor = str((item.get("top_factor") or {}).get("factor", "")).strip().lower() if isinstance(item.get("top_factor"), dict) else ""
    if level == "critical":
        return "block", "critical 治理风险任务默认提升为 block，先治理再放行。"
    if level == "high":
        return "manual_review", "high 治理风险任务默认进入人工复核。"
    if has_gap and source_count > 0:
        return "manual_review", "多源任务存在 traceability 缺口，建议先人工复核。"
    if factor in {"api_contract", "business_rule", "permission"}:
        return "manual_review", f"{factor} 变更影响较大，建议提升到人工复核。"
    return "allow", "当前治理信号可控，可按默认门禁策略执行。"


def _build_manager_summary(
    *,
    level: str,
    risk_score: int,
    blocked_24h: int,
    block_rate_24h: float,
    total_clusters: int,
    manual_review_cluster_count: int,
    multisource_task_count: int,
    traceability_gap_task_count: int,
    no_manifest_task_count: int,
    manifest_backfill_candidate_count: int,
    critical_count: int,
    high_count: int,
    top_alert_code: str,
    multisource_source_type_counts: dict[str, Any],
    strict_mode_readiness: dict[str, Any] | None = None,
    strict_mode_blocked_task_count: int = 0,
    strict_mode_caution_task_count: int = 0,
) -> dict[str, Any]:
    readiness = strict_mode_readiness if isinstance(strict_mode_readiness, dict) else {}
    release_readiness = "可继续推进"
    if level == "高" or critical_count > 0 or block_rate_24h >= 0.35:
        release_readiness = "建议先治理再推进"
    elif level == "中" or high_count > 0 or blocked_24h > 0:
        release_readiness = "可推进但需盯紧"

    traceability_status = "追溯稳定"
    if traceability_gap_task_count > 0 or no_manifest_task_count > 0:
        traceability_status = "追溯存在缺口"
    elif manifest_backfill_candidate_count > 0:
        traceability_status = "追溯待补齐"

    multisource_status = "多源输入稳定"
    if multisource_task_count == 0:
        multisource_status = "暂无多源任务"
    elif traceability_gap_task_count > 0:
        multisource_status = "多源已接入但需补追溯"

    top_theme = "保持治理稳定度"
    if blocked_24h > 0 and block_rate_24h >= 0.25:
        top_theme = "优先降低门禁阻断"
    elif strict_mode_blocked_task_count > 0:
        top_theme = "优先稳定 manifest-first 路径"
    elif traceability_gap_task_count > 0 or no_manifest_task_count > 0:
        top_theme = "优先补齐追溯链路"
    elif manual_review_cluster_count > 0:
        top_theme = "优先消化人工复核积压"
    elif multisource_task_count > 0:
        top_theme = "持续验证多源变更覆盖"

    weekly_focus = "保持回归节奏并持续观察。"
    if blocked_24h > 0 and top_alert_code:
        weekly_focus = f"优先收敛门禁阻断，重点跟进 {top_alert_code}。"
    elif strict_mode_blocked_task_count > 0:
        weekly_focus = "优先清理 compat_scan 任务，提升 strict-mode readiness。"
    elif strict_mode_caution_task_count > 0:
        weekly_focus = "优先推动 runtime flush 与 manifest 落盘，降低 strict-mode 风险。"
    elif traceability_gap_task_count > 0:
        weekly_focus = "优先补齐 traceability 与 execution record 追溯链。"
    elif manual_review_cluster_count > 0:
        weekly_focus = "优先消化需人工复核的失败聚类，降低治理积压。"

    highlights = [
        f"当前治理风险 {level}，综合评分 {risk_score} 分。",
        f"最近 24 小时门禁阻断 {blocked_24h} 次，阻断率 {round(block_rate_24h * 100)}%。",
        f"当前失败聚类 {total_clusters} 个，其中需人工复核 {manual_review_cluster_count} 个。",
        f"多源任务 {multisource_task_count} 个，追溯缺口 {traceability_gap_task_count} 个。",
    ]
    if no_manifest_task_count > 0 or manifest_backfill_candidate_count > 0:
        highlights.append(
            f"证据索引待补齐：缺失 manifest {no_manifest_task_count} 个，待回填 {manifest_backfill_candidate_count} 个。"
        )
    if readiness:
        highlights.append(
            f"Strict-mode readiness {str(readiness.get('status', '-')).strip() or '-'}，score={round(_float_value(readiness.get('score')), 3)}。"
        )
    if strict_mode_blocked_task_count > 0 or strict_mode_caution_task_count > 0:
        highlights.append(
            f"strict-mode 任务状态：blocked {strict_mode_blocked_task_count} 个，caution {strict_mode_caution_task_count} 个。"
        )
    if multisource_source_type_counts:
        summary = " / ".join(
            f"{source}:{_int_value(count)}" for source, count in sorted(multisource_source_type_counts.items())
        )
        highlights.append(f"多源结构分布：{summary}。")

    return {
        "headline": "治理视角已覆盖门禁、风险、聚类与追溯四条主线。",
        "release_readiness": release_readiness,
        "traceability_status": traceability_status,
        "multisource_status": multisource_status,
        "top_theme": top_theme,
        "weekly_focus": weekly_focus,
        "highlights": highlights[:5],
    }


def _build_action_items(
    *,
    critical_count: int,
    high_count: int,
    blocked_24h: int,
    block_rate_24h: float,
    top_alert_code: str,
    manifest_backfill_candidate_count: int,
    no_manifest_task_count: int,
    traceability_gap_task_count: int,
    multisource_task_count: int,
    total_clusters: int,
    top_cluster: dict[str, Any],
    strict_mode_readiness: dict[str, Any] | None = None,
    strict_mode_blocked_task_count: int = 0,
    strict_mode_caution_task_count: int = 0,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    readiness = strict_mode_readiness if isinstance(strict_mode_readiness, dict) else {}
    if critical_count > 0 or high_count > 0:
        items.append(
            {
                "title": "优先清理高风险执行任务",
                "status": "待优先处理",
                "level": "high" if critical_count == 0 else "critical",
                "summary": f"当前存在 {critical_count} 个 critical、{high_count} 个 high 治理风险任务，建议先复核失败证据和门禁状态。",
                "href": _query_href("/execution/runs", risk_levels="critical,high", sort="governance_risk"),
            }
        )
    if blocked_24h > 0:
        items.append(
            {
                "title": "降低质量门禁阻断率",
                "status": "持续跟进",
                "level": "medium" if block_rate_24h < 0.30 else "high",
                "summary": f"最近 24 小时 quality gate 阻断 {blocked_24h} 次，阻断率 {round(block_rate_24h * 100)}%。",
                "href": _query_href("/quality/failure-clusters", alert_code=top_alert_code or None, manual_review=1),
            }
        )
    if manifest_backfill_candidate_count > 0 or no_manifest_task_count > 0:
        items.append(
            {
                "title": "补齐执行证据与 manifest",
                "status": "持续跟进",
                "level": "medium",
                "summary": f"待回填 manifest 任务 {manifest_backfill_candidate_count} 个，缺失 manifest 任务 {no_manifest_task_count} 个。",
                "href": _query_href(
                    "/execution/runs",
                    manifest="no_manifest,backfill_candidate",
                    sort="evidence_health",
                ),
            }
        )
    if multisource_task_count > 0 and traceability_gap_task_count > 0:
        items.append(
            {
                "title": "补齐多源追溯缺口",
                "status": "持续跟进",
                "level": "medium",
                "summary": f"当前多源任务 {multisource_task_count} 个，其中 {traceability_gap_task_count} 个仍存在 traceability 缺口。",
                "href": _query_href("/execution/runs", source_type="multisource", traceability_gap=1),
            }
        )
    if str(readiness.get("status", "")).strip() in {"blocked", "caution"} or strict_mode_blocked_task_count > 0 or strict_mode_caution_task_count > 0:
        items.append(
            {
                "title": "提升 strict-mode readiness",
                "status": "持续跟进",
                "level": "high" if strict_mode_blocked_task_count > 0 else "medium",
                "summary": (
                    f"当前 strict-mode readiness={str(readiness.get('status', '-')).strip() or '-'}，"
                    f"blocked 任务 {strict_mode_blocked_task_count} 个，caution 任务 {strict_mode_caution_task_count} 个。"
                ),
                "href": _query_href(
                    "/execution/runs",
                    strict_mode_status="blocked" if strict_mode_blocked_task_count > 0 else "caution",
                    manifest="no_manifest,backfill_candidate" if strict_mode_blocked_task_count > 0 else None,
                    sort="evidence_health",
                ),
            }
        )
    if total_clusters > 0:
        items.append(
            {
                "title": "按失败聚类推进归因治理",
                "status": "持续跟进",
                "level": "medium",
                "summary": f"当前聚合出 {total_clusters} 个失败聚类，热点聚类 {str(top_cluster.get('cluster_id', '')).strip() or '-'} 已出现 {int(top_cluster.get('occurrence_count', 0) or 0)} 次。",
                "href": _query_href(
                    "/quality/failure-clusters",
                    cluster_id=str(top_cluster.get("cluster_id", "")).strip() or None,
                    failure_class=str(top_cluster.get("failure_class", "")).strip() or None,
                    queue=str(top_cluster.get("queue", "")).strip() or None,
                    severity=str(top_cluster.get("severity", "")).strip() or None,
                    manual_review=1 if _int_value(top_cluster.get("requires_manual_review_count")) > 0 else None,
                ),
            }
        )
    if not items:
        items.append(
            {
                "title": "治理态势稳定",
                "status": "观察中",
                "level": "low",
                "summary": "当前没有显著的治理阻断，可继续保持门禁与证据留痕的稳定性。",
                "href": _query_href("/quality/trends", view="governance"),
            }
        )
    return items[:5]


# build_governance_trend / build_governance_overview / build_flaky_top5 / build_dashboard_overview
# → 移至 workbench_governance_views.py
# 以下 import 保持向后兼容：所有外部调用者通过 workbench_governance_service 访问这些函数。
from app.services.workbench_governance_views import (  # noqa: E402
    build_governance_trend,
    build_governance_overview,
    build_flaky_top5,
    build_dashboard_overview,
)


