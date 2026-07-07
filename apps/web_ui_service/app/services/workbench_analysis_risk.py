"""Workbench 风险分析视图函数 —— 风险报告、自愈、审查。

提取自 workbench_analysis_service.py 以控制单文件大小在 1000 行以内。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

import yaml

from shared_backend.type_utils import dict_value as _dict_value

from app.core import page_analysis_rules
from app.services.workbench_analysis_service import (
    build_page_analysis_context,
    load_latest_self_healing_result,
)
from app.services.workbench_page_surface_service import (
    _clamp_confidence,
    _dedup_keep_order,
    _list_value,
    _surface_candidate_confidence_index,
    build_surface_element_candidates,
    build_surface_result_from_snapshot,
    extract_page_surface,
    surface_candidate_confidence_index,
    surface_confidence_summary,
)

LOGGER = logging.getLogger(__name__)

def _normalize_risk_factors(
    factors: list[Any] | None,
    *,
    source: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(factors, list):
        return normalized
    for item in factors[:20]:
        if not isinstance(item, dict):
            continue
        factor = str(item.get("factor", item.get("name", ""))).strip() or "factor"
        reason = str(item.get("reason", item.get("detail", ""))).strip() or "-"
        category = str(item.get("category", "")).strip() or "unknown"
        try:
            factor_score = int(float(item.get("score", 0) or 0))
        except (TypeError, ValueError):
            factor_score = 0
        normalized.append(
            {
                "factor": factor,
                "score": factor_score,
                "reason": reason,
                "category": category,
                "source": source,
            }
        )
    return normalized


def normalize_risk_factors(
    factors: list[Any] | None,
    *,
    source: str,
) -> list[dict[str, Any]]:
    return _normalize_risk_factors(factors, source=source)


def _build_risk_evidence(*, factors: list[dict[str, Any]]) -> list[str]:
    evidence: list[str] = []
    for item in factors[:20]:
        if not isinstance(item, dict):
            continue
        factor = str(item.get("factor", "")).strip() or "factor"
        reason = str(item.get("reason", "")).strip() or "-"
        score = int(item.get("score", 0) or 0)
        evidence.append(f"{factor}={score} ({reason})")
    return evidence


def build_risk_evidence(*, factors: list[dict[str, Any]]) -> list[str]:
    return _build_risk_evidence(factors=factors)


def _build_semantic_risk_evidence(
    *,
    page_semantic_summary: dict[str, Any] | None,
) -> list[str]:
    payload = page_semantic_summary if isinstance(page_semantic_summary, dict) else {}
    if not payload:
        return []
    page_type = str(payload.get("page_type", "")).strip() or "unknown"
    business_domain = str(payload.get("business_domain", "")).strip() or "generic"
    primary_goal = str(payload.get("primary_goal", "")).strip() or "inspect_page"
    confidence = _clamp_confidence(payload.get("confidence", 0))
    requires_review = bool(payload.get("requires_review", False))
    return [
        "page_semantic="
        f"type:{page_type},domain:{business_domain},goal:{primary_goal},"
        f"confidence:{confidence:.2f},requires_review:{str(requires_review).lower()}"
    ]


def build_semantic_risk_evidence(
    *,
    page_semantic_summary: dict[str, Any] | None,
) -> list[str]:
    return _build_semantic_risk_evidence(page_semantic_summary=page_semantic_summary)


def _build_risk_factor_summary(*, factors: list[dict[str, Any]]) -> dict[str, Any]:
    if not factors:
        return {
            "factor_count": 0,
            "positive_factor_count": 0,
            "category_counts": {},
            "top_factor": {},
            "total_factor_score": 0,
        }
    category_counts: dict[str, int] = {}
    positive_factor_count = 0
    total_factor_score = 0
    top_factor: dict[str, Any] = {}
    top_score = -1
    for item in factors:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", "")).strip() or "unknown"
        factor_score = int(item.get("score", 0) or 0)
        category_counts[category] = category_counts.get(category, 0) + 1
        total_factor_score += factor_score
        if factor_score > 0:
            positive_factor_count += 1
        if factor_score > top_score:
            top_score = factor_score
            top_factor = {
                "factor": str(item.get("factor", "")).strip() or "factor",
                "score": factor_score,
                "reason": str(item.get("reason", "")).strip() or "-",
                "category": category,
            }
    return {
        "factor_count": len(factors),
        "positive_factor_count": positive_factor_count,
        "category_counts": dict(sorted(category_counts.items())),
            "top_factor": top_factor,
            "total_factor_score": total_factor_score,
        }


def build_risk_factor_summary(*, factors: list[dict[str, Any]]) -> dict[str, Any]:
    return _build_risk_factor_summary(factors=factors)


def build_risk_report_summary(risk_report: dict[str, Any] | None) -> dict[str, Any]:
    payload = risk_report if isinstance(risk_report, dict) else {}
    factor_summary = _dict_value(payload.get("factor_summary"))
    metadata = _dict_value(payload.get("metadata"))
    top_factor = _dict_value(factor_summary.get("top_factor"))
    return {
        "risk_level": str(payload.get("risk_level", "")).strip(),
        "gate_decision": str(payload.get("gate_decision", "")).strip(),
        "requires_review": bool(payload.get("requires_review", False)),
        "risk_score": int(payload.get("risk_score", 0) or 0),
        "factor_count": int(factor_summary.get("factor_count", metadata.get("factor_count", 0)) or 0),
        "positive_factor_count": int(factor_summary.get("positive_factor_count", 0) or 0),
        "top_factor": {
            "factor": str(top_factor.get("factor", "")).strip(),
            "score": int(top_factor.get("score", 0) or 0),
            "reason": str(top_factor.get("reason", "")).strip(),
            "category": str(top_factor.get("category", "")).strip(),
        }
        if top_factor
        else (
            metadata.get("top_factor")
            if isinstance(metadata.get("top_factor"), dict)
            else {}
        ),
        "provider": str(metadata.get("provider", payload.get("source", ""))).strip(),
        "source": str(payload.get("source", "")).strip(),
    }


def build_self_healing_summary(
    *,
    execution_record: dict[str, Any] | None,
    artifacts_dir: str = "",
    load_latest_self_healing_result_fn: Any | None = None,
) -> dict[str, Any]:
    record = execution_record if isinstance(execution_record, dict) else {}
    evidence_index = _dict_value(record.get("evidence_index"))
    artifact_categories = _dict_value(evidence_index.get("artifact_categories"))
    result_file_count = int(artifact_categories.get("self_healing_result_files", 0) or 0)
    attempted = result_file_count > 0
    result_payload = {}
    artifacts_dir_value = str(artifacts_dir or "").strip()
    if artifacts_dir_value and callable(load_latest_self_healing_result_fn):
        result_payload = load_latest_self_healing_result_fn(Path(artifacts_dir_value))
        if result_payload:
            attempted = True

    boundary = _dict_value(result_payload.get("boundary"))
    plan = _dict_value(result_payload.get("plan"))
    if not boundary:
        boundary = _dict_value(plan.get("boundary"))

    summary = {
        "attempted": attempted,
        "result_file_count": result_file_count,
        "status": str(result_payload.get("status", "")).strip(),
        "healed": bool(result_payload.get("healed", False)),
        "rolled_back": bool(result_payload.get("rolled_back", False)),
        "reason": str(result_payload.get("reason", "")).strip(),
        "result_path": str(result_payload.get("_result_path", "")).strip(),
        "plan_path": str(result_payload.get("plan_path", "")).strip(),
        "boundary": {
            "version": str(boundary.get("version", "")).strip(),
            "allowed": bool(boundary.get("allowed", False)),
            "advice_type": str(boundary.get("advice_type", "")).strip(),
            "reason": str(boundary.get("reason", "")).strip(),
        }
        if boundary
        else {},
    }
    if not attempted:
        summary["status"] = summary["status"] or "not_attempted"
    elif attempted and not summary["status"]:
        summary["status"] = "result_detected"
    return summary


def build_failure_analysis_for_risk(*, final_status: str, page_object_summary: dict[str, Any], test_points: dict[str, Any]) -> dict[str, Any]:
    status_value = str(final_status or "").strip().lower() or "unknown"
    point_summary = (test_points or {}).get("review_summary", {}) if isinstance(test_points, dict) else {}
    missing_required_count = int((page_object_summary or {}).get("missing_required_count", 0) or 0)
    skip_suggestions = int(point_summary.get("skip_suggestion_count", 0) or 0)
    if status_value in {"generate_failed", "failed"}:
        risk_level = "high"
        category = "execution_failure"
        summary = "执行失败，需优先人工处理。"
    elif status_value == "coverage_gap":
        risk_level = "medium"
        category = "coverage_gap"
        summary = "存在覆盖缺口，建议人工复核后再放行。"
    elif missing_required_count > 0 or skip_suggestions > 0:
        risk_level = "medium"
        category = "confidence_gap"
        summary = "关键元素或测试点存在不确定性，建议人工复核。"
    else:
        risk_level = "low"
        category = "stable"
        summary = "当前批次未发现高风险信号。"
    return {
        "summary": summary,
        "failure_category": category,
        "failure_source": "page_analysis" if category == "confidence_gap" else ("app_bug" if category == "execution_failure" else "unknown"),
        "failure_source_reason": "auto-generated from execution status and review metadata",
        "failure_source_confidence": 0.72 if category == "confidence_gap" else (0.68 if category == "execution_failure" else 0.55),
        "likely_cause": "auto-generated from execution status and review metadata",
        "risk_level": risk_level,
        "recommended_action": "manual_review" if risk_level in {"medium", "high"} else "allow",
        "confidence": "0.82",
        "requires_manual_review": risk_level in {"medium", "high"},
    }


def evaluate_risk_report(
    *,
    page: str,
    requirement: str,
    quality_gate: dict[str, Any] | None,
    steps: list[dict[str, Any]],
    final_status: str,
    run_id: str,
    project: str,
    page_surface_summary: dict[str, Any],
    page_object_summary: dict[str, Any],
    test_points: dict[str, Any],
    review_state: dict[str, Any],
    page_surface: dict[str, Any] | None = None,
    page_object: dict[str, Any] | None = None,
    requirement_spec: dict[str, Any] | None = None,
    build_page_analysis_context_fn: Any = None,
    build_requirement_spec_for_risk_fn: Any = None,
    build_execution_plan_for_risk_fn: BuildExecutionPlanForRisk = None,
    find_run_item_fn: FindRunItem = None,
    build_runtime_execution_record_fn: BuildRuntimeExecutionRecord = None,
    run_orchestrator_risk_fn: RunOrchestratorRisk = None,
    build_risk_report_fn: BuildRiskReport = None,
    http_exception_cls: type[Exception] = Exception,
) -> dict[str, Any]:
    analysis_context = build_page_analysis_context_fn(
        page=page,
        project=project,
        case_id=str((run_id or "")).strip(),
        page_url="",
        page_surface=page_surface if isinstance(page_surface, dict) else {"confidence_summary": page_surface_summary or {}},
        page_object=page_object if isinstance(page_object, dict) else {"summary": page_object_summary or {}},
        test_points=test_points,
    )
    consumed_surface_summary = analysis_context.get("page_surface_summary") if isinstance(analysis_context.get("page_surface_summary"), dict) else (page_surface_summary or {})
    consumed_page_semantic_summary = _dict_value(analysis_context.get("page_semantic_summary"))
    consumed_page_object_summary = analysis_context.get("page_object_summary") if isinstance(analysis_context.get("page_object_summary"), dict) else (page_object_summary or {})
    consumed_test_points = analysis_context.get("test_points") if isinstance(analysis_context.get("test_points"), dict) else (test_points or {})
    consumed_model_versions = _dict_value(analysis_context.get("model_versions"))
    local_requirement_spec = requirement_spec if isinstance(requirement_spec, dict) and requirement_spec else build_requirement_spec_for_risk_fn(
        page=page,
        requirement=requirement,
        quality_gate=quality_gate,
    )
    execution_plan = build_execution_plan_for_risk_fn(
        page=page,
        steps=steps,
        test_points=consumed_test_points,
        coverage=_dict_value(consumed_test_points.get("coverage")),
        page_surface_summary=consumed_surface_summary,
        page_semantic_summary=consumed_page_semantic_summary,
        page_object_summary=consumed_page_object_summary,
        review_state=review_state,
        final_status=final_status,
    )
    run_item = find_run_item_fn(run_id) if run_id else None
    execution_record = (
        run_item.get("execution_record", {})
        if isinstance(run_item, dict) and isinstance(run_item.get("execution_record"), dict)
        else build_runtime_execution_record_fn(
            run_id=run_id,
            case_id=str((run_item or {}).get("case_id", "")).strip(),
            project=project,
            source="auto-run",
            mode="generate_and_run",
            status=final_status,
            started_at=str((run_item or {}).get("started_at", "")).strip(),
            finished_at=str((run_item or {}).get("finished_at", "")).strip(),
            return_code=(run_item or {}).get("return_code") if isinstance(run_item, dict) else None,
            created_at=str((run_item or {}).get("created_at", "")).strip() if isinstance(run_item, dict) else "",
        )
    )
    failure_analysis = build_failure_analysis_for_risk(
        final_status=final_status,
        page_object_summary=consumed_page_object_summary,
        test_points=consumed_test_points,
    )
    try:
        orchestrator_payload = run_orchestrator_risk_fn(
            requirement_spec=local_requirement_spec,
            execution_plan=execution_plan,
            execution_record=execution_record,
            failure_analysis=failure_analysis,
            failure_triage={},
        )
        risk_report = orchestrator_payload.get("risk_report", {}) if isinstance(orchestrator_payload, dict) else {}
        if isinstance(risk_report, dict) and risk_report:
            factor_rows = _normalize_risk_factors(
                risk_report.get("factors") if isinstance(risk_report.get("factors"), list) else [],
                source="risk-evaluation-agent",
            )
            evidence = _build_risk_evidence(factors=factor_rows)
            evidence.extend(_build_semantic_risk_evidence(page_semantic_summary=consumed_page_semantic_summary))
            pending_sections = int((review_state or {}).get("pending_sections", 0) or 0)
            risk_report["page"] = page
            risk_report["source"] = "risk-evaluation-agent"
            risk_report["factors"] = factor_rows
            risk_report["factor_summary"] = _build_risk_factor_summary(factors=factor_rows)
            risk_report["confidence"] = _clamp_confidence(0.88 if evidence else 0.76)
            risk_report["evidence"] = evidence
            risk_report["requires_review"] = (
                str(risk_report.get("gate_decision", "")).strip().lower() != "allow"
                or pending_sections > 0
                or float(risk_report.get("confidence", 0) or 0) < 0.75
            )
            risk_report["metadata"] = {
                **(risk_report.get("metadata", {}) if isinstance(risk_report.get("metadata"), dict) else {}),
                "final_status": str(final_status or "").strip().lower() or "unknown",
                "pending_review_sections": pending_sections,
                "provider": "orchestrator",
                "semantic_page_type": str((consumed_page_semantic_summary or {}).get("page_type", "")).strip() or "unknown",
                "semantic_business_domain": str((consumed_page_semantic_summary or {}).get("business_domain", "")).strip() or "generic",
                "semantic_primary_goal": str((consumed_page_semantic_summary or {}).get("primary_goal", "")).strip() or "inspect_page",
                "semantic_requires_review": bool((consumed_page_semantic_summary or {}).get("requires_review", False)),
                "semantic_confidence": _clamp_confidence((consumed_page_semantic_summary or {}).get("confidence", 0)),
                "factor_count": int((risk_report.get("factor_summary", {}) or {}).get("factor_count", 0) or 0),
                "top_factor": (risk_report.get("factor_summary", {}) or {}).get("top_factor", {}),
                "consumed_models": {
                    **consumed_model_versions,
                },
            }
            return risk_report
    except http_exception_cls as exc:
        default_report = build_risk_report_fn(
            page=page,
            final_status=final_status,
            page_surface_summary=consumed_surface_summary,
            page_semantic_summary=consumed_page_semantic_summary,
            page_object_summary=consumed_page_object_summary,
            test_points=consumed_test_points,
            review_state=review_state,
        )
        default_report["source"] = "local_default"
        default_report["warnings"] = [f"risk-evaluation-agent unavailable: {getattr(exc, 'detail', str(exc))}"]
        default_report["metadata"] = {
            **(default_report.get("metadata", {}) if isinstance(default_report.get("metadata"), dict) else {}),
            "consumed_models": consumed_model_versions,
        }
        return default_report
    except Exception as exc:  # pragma: no cover - keep risk path non-blocking
        default_report = build_risk_report_fn(
            page=page,
            final_status=final_status,
            page_surface_summary=consumed_surface_summary,
            page_semantic_summary=consumed_page_semantic_summary,
            page_object_summary=consumed_page_object_summary,
            test_points=consumed_test_points,
            review_state=review_state,
        )
        default_report["source"] = "local_default"
        default_report["warnings"] = [f"risk-evaluation-agent failed: {exc}"]
        default_report["metadata"] = {
            **(default_report.get("metadata", {}) if isinstance(default_report.get("metadata"), dict) else {}),
            "consumed_models": consumed_model_versions,
        }
        return default_report

    default_report = build_risk_report_fn(
        page=page,
        final_status=final_status,
        page_surface_summary=consumed_surface_summary,
        page_semantic_summary=consumed_page_semantic_summary,
        page_object_summary=consumed_page_object_summary,
        test_points=consumed_test_points,
        review_state=review_state,
    )
    default_report["metadata"] = {
        **(default_report.get("metadata", {}) if isinstance(default_report.get("metadata"), dict) else {}),
        "consumed_models": consumed_model_versions,
    }
    return default_report


def build_risk_review_items(risk_report: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(risk_report, dict) or not risk_report:
        return []
    evidence = [str(item).strip() for item in risk_report.get("evidence", []) if str(item).strip()] if isinstance(risk_report.get("evidence"), list) else []
    return [
        {
            "key": "risk_decision",
            "label": "风险决策确认",
            "confidence": _clamp_confidence(risk_report.get("confidence", 0)),
            "description": str(risk_report.get("recommendation", "")).strip(),
            "gate_decision": str(risk_report.get("gate_decision", "")).strip(),
            "risk_level": str(risk_report.get("risk_level", "")).strip(),
            "risk_score": int(risk_report.get("risk_score", 0) or 0),
            "warnings": evidence,
        }
    ]


def _reviewer_display_name(entry: dict[str, Any] | None) -> str:
    item = entry if isinstance(entry, dict) else {}
    username = str(item.get("confirmed_by", "")).strip()
    role = str(item.get("confirmed_by_role", "")).strip()
    if username and role and role != "unknown":
        return f"{username} ({role})"
    if username:
        return username
    return "anonymous"


def reviewer_display_name(entry: dict[str, Any] | None) -> str:
    return _reviewer_display_name(entry)


def build_review_section(
    *,
    review_type: str,
    items: list[dict[str, Any]],
    existing_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    candidate_count = len([item for item in items if isinstance(item, dict)])
    if existing_entry:
        status_value = str(existing_entry.get("status", "confirmed")).strip() or "confirmed"
        reviewed_items = existing_entry.get("items") if isinstance(existing_entry.get("items"), list) else items
        return {
            "review_type": review_type,
            "required": candidate_count > 0,
            "status": status_value,
            "candidate_count": candidate_count,
            "items": reviewed_items,
            "updated_at": str(existing_entry.get("updated_at", "")).strip(),
            "note": str(existing_entry.get("note", "")).strip(),
            "confirmed_by": str(existing_entry.get("confirmed_by", "")).strip() or "anonymous",
            "confirmed_by_role": str(existing_entry.get("confirmed_by_role", "")).strip() or "unknown",
            "actor_display": _reviewer_display_name(existing_entry),
        }
    if candidate_count == 0:
        return {
            "review_type": review_type,
            "required": False,
            "status": "not_required",
            "candidate_count": 0,
            "items": [],
            "updated_at": "",
            "note": "",
            "confirmed_by": "",
            "confirmed_by_role": "",
            "actor_display": "",
        }
    return {
        "review_type": review_type,
        "required": True,
        "status": "pending",
        "candidate_count": candidate_count,
        "items": items,
        "updated_at": "",
        "note": "",
        "confirmed_by": "",
        "confirmed_by_role": "",
        "actor_display": "",
    }


def build_risk_report(
    *,
    page: str,
    final_status: str,
    page_surface_summary: dict[str, Any],
    page_semantic_summary: dict[str, Any] | None,
    page_object_summary: dict[str, Any],
    test_points: dict[str, Any],
    review_state: dict[str, Any],
) -> dict[str, Any]:
    status_value = str(final_status or "").strip().lower() or "unknown"
    score = 0
    factors: list[dict[str, Any]] = []

    def append_factor(*, factor: str, factor_score: int, reason: str, category: str) -> None:
        factors.append(
            {
                "factor": str(factor).strip() or "factor",
                "score": int(factor_score),
                "reason": str(reason).strip() or "-",
                "category": str(category).strip() or "unknown",
                "source": "local-rules",
            }
        )

    status_score_map = {
        "generate_failed": 95,
        "failed": 88,
        "coverage_gap": 72,
        "passed": 24,
        "running": 40,
    }
    status_score = status_score_map.get(status_value, 45)
    score += status_score
    append_factor(
        factor="execution_status",
        factor_score=status_score,
        reason=f"执行状态={status_value}",
        category="execution",
    )

    low_confidence_elements = int((page_surface_summary or {}).get("low_confidence_count", 0) or 0)
    if low_confidence_elements:
        element_penalty = min(18, low_confidence_elements * 4)
        score += element_penalty
        append_factor(
            factor="low_confidence_elements",
            factor_score=element_penalty,
            reason=f"低置信度元素 {low_confidence_elements} 个",
            category="page_surface",
        )

    page_object_missing = int((page_object_summary or {}).get("missing_required_count", 0) or 0)
    if page_object_missing:
        po_penalty = min(18, page_object_missing * 6)
        score += po_penalty
        append_factor(
            factor="missing_page_object_elements",
            factor_score=po_penalty,
            reason=f"Page Object 缺失必需元素 {page_object_missing} 个",
            category="page_object",
        )

    point_review_summary = (test_points or {}).get("review_summary", {}) if isinstance(test_points, dict) else {}
    pending_test_points = int(point_review_summary.get("pending_review_count", 0) or 0)
    skip_suggestions = int(point_review_summary.get("skip_suggestion_count", 0) or 0)
    if pending_test_points:
        point_penalty = min(12, pending_test_points * 3)
        score += point_penalty
        append_factor(
            factor="pending_test_points",
            factor_score=point_penalty,
            reason=f"待确认测试点 {pending_test_points} 个",
            category="test_point",
        )
    if skip_suggestions:
        skip_penalty = min(12, skip_suggestions * 4)
        score += skip_penalty
        append_factor(
            factor="skip_suggestions",
            factor_score=skip_penalty,
            reason=f"建议跳过测试点 {skip_suggestions} 个",
            category="test_point",
        )

    pending_sections = int((review_state or {}).get("pending_sections", 0) or 0)
    if pending_sections:
        review_penalty = min(12, pending_sections * 5)
        score += review_penalty
        append_factor(
            factor="pending_review_sections",
            factor_score=review_penalty,
            reason=f"仍有 {pending_sections} 个确认分组待处理",
            category="review",
        )

    score = max(0, min(score, 100))
    if score >= 75:
        risk_level = "high"
    elif score >= 45:
        risk_level = "medium"
    else:
        risk_level = "low"

    if status_value in {"generate_failed", "failed"}:
        gate_decision = "block"
    elif score >= 45 or pending_sections > 0:
        gate_decision = "manual_review"
    else:
        gate_decision = "allow"

    if gate_decision == "block":
        recommendation = "当前运行存在失败或生成阻断，建议先修复后再决定是否放行。"
    elif gate_decision == "manual_review":
        recommendation = "当前风险需要人工确认后再决定是否继续扩大发布或回归范围。"
    else:
        recommendation = "当前风险可控，可继续执行后续回归或放行。"

    confidence_inputs = 4
    confidence_hits = 0
    if isinstance(page_surface_summary, dict) and page_surface_summary:
        confidence_hits += 1
    if isinstance(page_object_summary, dict) and page_object_summary:
        confidence_hits += 1
    if isinstance(test_points, dict) and test_points.get("points"):
        confidence_hits += 1
    if isinstance(review_state, dict):
        confidence_hits += 1
    confidence = _clamp_confidence((confidence_hits / confidence_inputs) * 0.75 + 0.15)
    factor_summary = _build_risk_factor_summary(factors=factors)
    evidence = _build_risk_evidence(factors=factors)
    evidence.extend(_build_semantic_risk_evidence(page_semantic_summary=page_semantic_summary))

    return {
        "version": "RiskReportV1",
        "page": page,
        "risk_score": score,
        "risk_level": risk_level,
        "gate_decision": gate_decision,
        "recommendation": recommendation,
        "confidence": confidence,
        "factors": factors,
        "factor_summary": factor_summary,
        "evidence": evidence,
        "source": "local-rules",
        "warnings": [],
        "requires_review": gate_decision != "allow" or pending_sections > 0 or confidence < 0.75,
        "metadata": {
            "final_status": status_value,
            "low_confidence_elements": low_confidence_elements,
            "missing_page_object_elements": page_object_missing,
            "pending_test_points": pending_test_points,
            "skip_suggestions": skip_suggestions,
            "pending_review_sections": pending_sections,
            "semantic_page_type": str((page_semantic_summary or {}).get("page_type", "")).strip() or "unknown",
            "semantic_business_domain": str((page_semantic_summary or {}).get("business_domain", "")).strip() or "generic",
            "semantic_primary_goal": str((page_semantic_summary or {}).get("primary_goal", "")).strip() or "inspect_page",
            "semantic_requires_review": bool((page_semantic_summary or {}).get("requires_review", False)),
            "semantic_confidence": _clamp_confidence((page_semantic_summary or {}).get("confidence", 0)),
            "factor_count": int(factor_summary.get("factor_count", 0) or 0),
            "top_factor": factor_summary.get("top_factor", {}),
        },
    }


_build_failure_analysis_for_risk = build_failure_analysis_for_risk
_build_risk_review_items = build_risk_review_items
_build_review_section = build_review_section
