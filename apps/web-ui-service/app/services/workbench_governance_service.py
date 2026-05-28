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
    from collections import defaultdict

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
