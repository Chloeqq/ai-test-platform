"""Workbench 资产视图函数 —— case、test-point-asset 的视图构建。

提取自 workbench_asset_service.py 以控制单文件大小在 1000 行以内。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException, status
from shared_backend.case_ids import normalize_case_id
from shared_backend.case_rules import enrich_case_metadata, validate_case_payload
from shared_backend.datetime_compat import UTC
from shared_backend.type_utils import (
    dedup_keep_order as _dedup_keep_order,
    dict_value as _dict_value,
    float_value as _float_value,
    int_value as _int_value,
    list_value as _list_value,
)

from app.services import workbench_state_store as state_store

import logging
LOGGER = logging.getLogger(__name__)


def _svc():
    """惰性导入以避免循环依赖。"""
    from app.services import workbench_asset_service as _svc_mod
    return _svc_mod


def _state_svc():
    """惰性导入 state 模块。"""
    from app.services import workbench_asset_state as _state_mod
    return _state_mod

def build_cases_payload(
    *,
    project: str,
    page: int,
    page_size: int,
    focus_case_id: str,
    collect_case_items: CollectCaseItems,
    paginate_case_items: PaginateCaseItems,
) -> dict[str, Any]:
    items = collect_case_items(project)
    focus_value = _svc()._safe_case_id(focus_case_id) if str(focus_case_id).strip() else ""
    page_items, pagination = paginate_case_items(
        items,
        page=page,
        page_size=page_size,
        focus_case_id=focus_value,
    )
    return {
        "items": page_items,
        "pagination": pagination,
        "filters": {
            "project": project,
            "focus_case_id": focus_value,
        },
        "sort": {
            "field": "updated_at",
            "order": "desc",
        },
    }


def build_case_detail(
    *,
    project: str,
    case_id: str,
    resolve_case_yaml_path: ResolveCaseYamlPath,
    read_case_yaml: ReadCaseYaml,
) -> dict[str, Any]:
    normalized_case_id = _svc()._safe_case_id(case_id)
    case_path = resolve_case_yaml_path(project, normalized_case_id)
    payload, content = read_case_yaml(case_path)
    execution = payload.get("execution") or {}
    return {
        "item": {
            "case_id": normalized_case_id,
            "project": project,
            "path": str(case_path.resolve()),
            "title": str(payload.get("title", normalized_case_id)).strip() or normalized_case_id,
            "page": str(execution.get("page", payload.get("module", "product"))).strip() or "product",
            "page_url": str(execution.get("page_url", "")).strip(),
            "priority": str(payload.get("priority", "P1")).strip() or "P1",
            "yaml_content": content,
            "updated_at": datetime.fromtimestamp(case_path.stat().st_mtime, tz=UTC).isoformat(),
        }
    }


def read_case_yaml(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"case file not found: {path}")
    content = path.read_text(encoding="utf-8")
    try:
        payload = yaml.safe_load(content) or {}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid yaml: {exc}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="yaml root must be an object")
    return payload, content


def write_case_yaml(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    path.write_text(text, encoding="utf-8")
    return text


def paginate_case_items(
    items: list[dict[str, Any]],
    *,
    page: int,
    page_size: int,
    focus_case_id: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    total_items = len(items)
    total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1
    selected_page = page
    if focus_case_id:
        focus_index = next(
            (index for index, item in enumerate(items) if _svc()._safe_case_id(str(item.get("case_id", "")).strip()) == focus_case_id),
            -1,
        )
        if focus_index >= 0:
            selected_page = (focus_index // page_size) + 1
    selected_page = max(1, min(selected_page, total_pages))
    start = (selected_page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    pagination = {
        "page": selected_page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_prev": selected_page > 1,
        "has_next": selected_page < total_pages,
        "prev_page": selected_page - 1 if selected_page > 1 else None,
        "next_page": selected_page + 1 if selected_page < total_pages else None,
    }
    return page_items, pagination


def build_saved_case_payload(
    *,
    case_id: str,
    project: str,
    yaml_content: str,
    safe_case_id: Callable[[str], str],
    resolve_case_yaml_path: ResolveCaseYamlPath,
    write_case_yaml: WriteCaseYaml,
    save_case_state: SaveCaseState,
    append_history: AppendHistory,
    now_iso: NowIsoFn,
    ensure_project_writable: EnsureProjectWritable,
) -> dict[str, Any]:
    normalized_case_id = safe_case_id(case_id)
    normalized_project = ensure_project_writable(project)
    case_path = _state_svc().resolve_case_yaml_path(normalized_project, normalized_case_id)
    try:
        case_yaml = yaml.safe_load(yaml_content) or {}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid yaml: {exc}") from exc
    if not isinstance(case_yaml, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="yaml root must be an object")
    case_yaml["id"] = normalized_case_id
    case_yaml = enrich_case_metadata(case_yaml)
    validation_errors = validate_case_payload(case_yaml)
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(validation_errors),
        )
    final_text = write_case_yaml(case_path, case_yaml)
    state_entry = _state_svc().save_case_state(normalized_project, case_yaml, case_path)
    append_history(
        {
            "timestamp": now_iso(),
            "action": "save_case",
            "case_id": normalized_case_id,
            "title": str(case_yaml.get("title", normalized_case_id)),
            "path": str(case_path.resolve()),
        }
    )
    return {
        "message": "case saved",
        "item": {
            "case_id": normalized_case_id,
            "project": normalized_project,
            "path": str(case_path.resolve()),
            "yaml_content": final_text,
            "state": state_entry,
        },
    }


def _build_list_quality_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Phase 3: 聚合列表中所有资产的质量数据。

    纯消费已有 quality_report 结果，不新增质量判断。
    """
    if not items:
        return {"total_assets": 0, "avg_score": 100, "decision_counts": {}, "lowest": []}
    scores = []
    decisions: dict[str, int] = {}
    for item in items:
        qr = item.get("quality_report") if isinstance(item.get("quality_report"), dict) else {}
        s = int(qr.get("score", 0))
        d = str(qr.get("decision", "PASS"))
        scores.append(s)
        decisions[d] = decisions.get(d, 0) + 1
    avg = sum(scores) // len(scores) if scores else 100
    return {
        "total_assets": len(items),
        "avg_score": avg,
        "decision_counts": decisions,
        "lowest": sorted(items, key=lambda i: (
            i.get("quality_report", {}).get("score", 100)
            if isinstance(i.get("quality_report"), dict) else 100
        ))[:3],
    }


def build_test_point_asset_items(
    *,
    project: str,
    page: str,
    keyword: str,
    source_type: str,
    coverage_status: str,
    review_status: str,
    gate_decision: str,
    selection_state: str,
    state_project_dir: Callable[[str], Path],
    normalize_page_slug: NormalizePageSlug,
    load_test_point_asset: LoadTestPointAsset,
    latest_run_snapshot_for_case: LatestRunSnapshotForCase,
    build_traceability_summary: BuildTraceabilitySummary,
    build_selection_summary: BuildSelectionSummary,
    build_coverage_summary: BuildCoverageSummary,
    clamp_confidence: ClampConfidence,
    db_asset_ids: set[str] | None = None,
) -> dict[str, Any]:
    project_dir = _state_svc().state_project_dir(project)
    normalized_page = normalize_page_slug(page) if str(page).strip() else ""
    keyword_value = str(keyword or "").strip().lower()
    source_type_value = str(source_type or "").strip().lower()
    coverage_status_value = str(coverage_status or "").strip().lower()
    review_status_value = str(review_status or "").strip().lower()
    gate_decision_value = str(gate_decision or "").strip().lower()
    selection_state_value = str(selection_state or "").strip().lower()
    case_ids: set[str] = set(db_asset_ids) if db_asset_ids else set()
    if project_dir.exists():
        case_ids.update(file.stem for file in project_dir.glob("*.json") if file.is_file())
        plans_dir = project_dir / "plans"
        if plans_dir.exists():
            case_ids.update(file.stem for file in plans_dir.glob("*.json") if file.is_file())

    items: list[dict[str, Any]] = []
    for case_id in sorted(case_ids):
        asset = load_test_point_asset(project, case_id)
        if not asset:
            continue
        asset_page = normalize_page_slug(str(asset.get("page", "")).strip()) if str(asset.get("page", "")).strip() else ""
        if normalized_page and asset_page != normalized_page:
            continue
        asset_source_type = str(asset.get("source_type", "")).strip().lower()
        if source_type_value and asset_source_type != source_type_value:
            continue
        requirement_rows = _svc()._derive_requirement_list(asset)
        requirement_text = " ".join(requirement_rows)
        title_text = _svc()._derive_asset_title(asset, fallback_id=case_id)
        haystack = " ".join([case_id, title_text, requirement_text, asset_page, asset_source_type]).lower()
        if keyword_value and keyword_value not in haystack:
            continue
        latest_run = latest_run_snapshot_for_case(project=project, case_id=case_id, page=asset_page)
        traceability_summary = build_traceability_summary(asset=asset, latest_run=latest_run)
        selection_summary = build_selection_summary(traceability_summary=traceability_summary)
        review_payload = traceability_summary.get("review", {}) if isinstance(traceability_summary.get("review"), dict) else {}
        gate_payload = traceability_summary.get("gate", {}) if isinstance(traceability_summary.get("gate"), dict) else {}
        coverage_payload = traceability_summary.get("coverage", {}) if isinstance(traceability_summary.get("coverage"), dict) else {}
        if coverage_status_value and str(coverage_payload.get("latest_run_status", "")).strip().lower() != coverage_status_value:
            continue
        if review_status_value and str(review_payload.get("test_point_status", "")).strip().lower() != review_status_value:
            continue
        if gate_decision_value and str(gate_payload.get("effective_decision", "")).strip().lower() != gate_decision_value:
            continue
        if selection_state_value and str(selection_summary.get("selection_state", "")).strip().lower() != selection_state_value:
            continue
        items.append(
            {
                "asset_id": str(asset.get("asset_id", case_id)).strip() or case_id,
                "project": project,
                "title": title_text or case_id,
                "page": asset_page,
                "priority": str(asset.get("priority", "P1")).strip() or "P1",
                "source_type": asset_source_type or "unknown",
                "source_label": _svc().source_type_label(asset_source_type),
                "point_count": int(asset.get("point_count", 0) or 0),
                "intent_count": _svc()._derive_intent_count(asset),
                "updated_at": str(asset.get("updated_at", "")).strip(),
                "requires_review": bool(asset.get("requires_review", False)),
                "confidence": clamp_confidence(asset.get("confidence", 0)),
                "plan_path": str(asset.get("plan_path", "")).strip(),
                "references": asset.get("references", []) if isinstance(asset.get("references"), list) else [],
                "review_summary": asset.get("review_summary", {}) if isinstance(asset.get("review_summary"), dict) else {},
                "coverage": asset.get("coverage", {}) if isinstance(asset.get("coverage"), dict) else {},
                "semantic_summary": asset.get("semantic_summary", {}) if isinstance(asset.get("semantic_summary"), dict) else {},
                "technique_summary": asset.get("technique_summary", {}) if isinstance(asset.get("technique_summary"), dict) else {},
                "latest_run": latest_run,
                "traceability_summary": traceability_summary,
                "selection_summary": selection_summary,
            }
        )

    items.sort(
        key=lambda item: (str(item.get("updated_at", "")).strip(), str(item.get("asset_id", "")).strip()),
        reverse=True,
    )
    filter_snapshot = {
        "page": normalized_page,
        "keyword": keyword_value,
        "source_type": source_type_value,
        "coverage_status": coverage_status_value,
        "review_status": review_status_value,
        "gate_decision": gate_decision_value,
        "selection_state": selection_state_value,
    }
    return {
        "items": items,
        "selection_summary": {
            "total_assets": len(items),
            "ready_count": sum(
                1
                for item in items
                if str((item.get("selection_summary") or {}).get("selection_state", "")).strip() == "ready"
            ),
            "needs_review_count": sum(
                1
                for item in items
                if str((item.get("selection_summary") or {}).get("selection_state", "")).strip() == "needs_review"
            ),
            "blocked_count": sum(
                1
                for item in items
                if str((item.get("selection_summary") or {}).get("selection_state", "")).strip() == "blocked"
            ),
            "filter_snapshot": filter_snapshot,
        },
        "coverage_summary": build_coverage_summary(items=items, filter_snapshot=filter_snapshot),
        "quality_summary": _build_list_quality_summary(items),
    }


def _build_quality_report(asset: dict[str, Any]) -> dict[str, Any]:
    """从资产数据构建质量报告 (P0-4: 审核页展示 Gate 报告)。

    完全基于 asset 已有字段计算，不查询 DB，不新增字段。

    P0-1: candidate_step 不计入 zero_assert（本质是"未结构化"而非"缺断言"）。
    P0-2: data_warnings（数据补全提示）不影响 quality decision。
    """
    plan = asset.get("plan", {}) if isinstance(asset.get("plan"), dict) else {}
    points = plan.get("points", []) if isinstance(plan.get("points"), list) else []
    requires_review = bool(asset.get("requires_review", False))

    # 按 point_type 统计断言质量（candidate_step 且无断言的 point 不计入 zero_assert）
    candidate_step_count = 0
    unprocessed_count = 0
    by_type: dict[str, dict[str, int]] = {}
    for p in points:
        pt = str(p.get("point_type", "unknown")).strip() or "unknown"
        if pt not in by_type:
            by_type[pt] = {"total": 0, "zero_assertion": 0}
        by_type[pt]["total"] += 1
        steps = p.get("steps", []) if isinstance(p.get("steps"), list) else []
        actions = [str(s.get("action", "")) for s in steps]
        has_assertion = any(a.startswith("assert_") for a in actions)
        has_candidate = "candidate_step" in actions

        if has_candidate:
            candidate_step_count += 1
            if not has_assertion:
                unprocessed_count += 1
                # 不计入 zero_assertion — candidate_step 的本质是未结构化，而非缺断言
            # 有 candidate_step 但同时有断言：仍计 candidate_step，但断言存在所以不计 zero_assert
        else:
            if not has_assertion:
                by_type[pt]["zero_assertion"] += 1

    # 聚合 warnings：仅从 plan.points[].warnings（去重），不依赖 asset 顶层 warnings
    seen_warnings: set[str] = set()
    all_warnings: list[str] = []
    for p in points:
        pw_list = p.get("warnings", []) if isinstance(p.get("warnings"), list) else []
        for w in pw_list:
            key = str(w).strip()
            if key and key not in seen_warnings:
                seen_warnings.add(key)
                all_warnings.append(key)

    # 分类 warnings
    assertion_warnings = [w for w in all_warnings if "assertion" in str(w).lower()]
    other_warnings = [w for w in all_warnings if w not in assertion_warnings]

    # P0-2: 数据补全提示不影响 quality decision
    _DATA_HINT_KEYWORDS = ("空格输入", "缺少明确测试数据", "无法无损表达")
    data_warnings = [w for w in all_warnings if any(kw in str(w) for kw in _DATA_HINT_KEYWORDS)]
    quality_warnings = [w for w in all_warnings if w not in data_warnings]

    # Gate-expected decision: 基于领域规则 (非硬编码)
    total_points = len(points)
    zero_assert_count = sum(v["zero_assertion"] for v in by_type.values())
    if total_points == 0:
        decision = "PASS"
        score = 100
    elif zero_assert_count > 0:
        decision = "REJECT"
        score = max(0, 100 - zero_assert_count * 10)
    elif candidate_step_count > 0:
        decision = "REVIEW"
        score = 75
    elif quality_warnings:
        decision = "REVIEW"
        score = 75
    elif requires_review:
        decision = "REVIEW"
        score = 80
    else:
        decision = "PASS"
        score = 90

    # 单点质量评分 (Phase 3: point_level_quality)
    per_point: list[dict[str, Any]] = []
    for p in points:
        psteps = p.get("steps", []) if isinstance(p.get("steps"), list) else []
        pactions = [str(s.get("action", "")) for s in psteps]
        passertions = [a for a in pactions if a.startswith("assert_")]
        per_point.append({
            "intent_id": str(p.get("intent_id", "")).strip(),
            "point_type": str(p.get("point_type", "unknown")).strip(),
            "has_assertion": len(passertions) > 0,
            "assertion_types": list(set(passertions)),
            "has_candidate_step": "candidate_step" in pactions,
            "warning_count": len(p.get("warnings", []) if isinstance(p.get("warnings"), list) else []),
        })

    return {
        "score": score,
        "decision": decision,
        "requires_review": requires_review,
        "total_points": total_points,
        "zero_assertion_count": zero_assert_count,
        "candidate_step_count": candidate_step_count,
        "unprocessed_count": unprocessed_count,
        "assertion_warnings": assertion_warnings,
        "other_warnings": other_warnings,
        "quality_warnings": quality_warnings,
        "data_warnings": data_warnings,
        "by_point_type": by_type,
        "per_point": per_point,
    }


def get_quality_gate_violations(asset: dict[str, Any]) -> list[dict[str, Any]]:
    """返回 Quality Gate violation 列表。只负责发现，不负责阻断。

    基于 _build_quality_report 的输出，逐条件检查。
    """
    qr = _build_quality_report(asset)
    violations: list[dict[str, Any]] = []
    per_point = qr.get("per_point", []) if isinstance(qr.get("per_point"), list) else []

    zero_count = int(qr.get("zero_assertion_count", 0) or 0)
    unprocessed_count = int(qr.get("unprocessed_count", 0) or 0)
    candidate_count = int(qr.get("candidate_step_count", 0) or 0)
    quality_warnings = qr.get("quality_warnings", []) if isinstance(qr.get("quality_warnings"), list) else []

    if zero_count > 0:
        ids = [str(p.get("intent_id", "")) for p in per_point if not p.get("has_assertion") and not p.get("has_candidate_step")]
        violations.append({
            "code": "zero_assertion",
            "severity": "block",
            "message": f"{zero_count} 个测试点缺少可执行断言，无法验证业务结果。",
            "intent_ids": ids,
        })

    if unprocessed_count > 0:
        ids = [str(p.get("intent_id", "")) for p in per_point if p.get("has_candidate_step") and not p.get("has_assertion")]
        violations.append({
            "code": "unprocessed",
            "severity": "block",
            "message": f"{unprocessed_count} 个测试点存在 candidate_step 且未生成断言步骤。",
            "intent_ids": ids,
        })

    if candidate_count > 0 and unprocessed_count == 0:
        ids = [str(p.get("intent_id", "")) for p in per_point if p.get("has_candidate_step")]
        violations.append({
            "code": "candidate_step",
            "severity": "review",
            "message": f"{candidate_count} 个测试点存在 candidate_step（已有断言）。",
            "intent_ids": ids,
        })

    if quality_warnings:
        violations.append({
            "code": "quality_warning",
            "severity": "review",
            "message": f"{len(quality_warnings)} 条质量问题需人工确认。",
            "intent_ids": [],
        })

    return violations


def check_generate_gate(asset: dict[str, Any]) -> None:
    """Generate Case 前的质量门禁检查。存在 block 级 violation 时抛 422。"""
    violations = get_quality_gate_violations(asset)
    blocking = [v for v in violations if v.get("severity") == "block"]
    if blocking:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "quality_gate_blocked",
                "message": "质量门禁阻断，无法生成用例。请先修复阻断项后再生成。",
                "violations": blocking,
            },
        )


def build_test_point_asset_detail(
    *,
    project: str,
    asset_id: str,
    load_test_point_asset: LoadTestPointAsset,
    latest_run_snapshot_for_case: LatestRunSnapshotForCase,
    build_traceability_summary: BuildTraceabilitySummary,
    build_selection_summary: BuildSelectionSummary,
    clamp_confidence: ClampConfidence,
) -> dict[str, Any]:
    normalized_asset_id = _svc()._safe_case_id(asset_id)
    asset = _state_svc().load_test_point_asset(project, normalized_asset_id)
    if not asset:
        return {}
    page = str(asset.get("page", "")).strip()
    latest_run = latest_run_snapshot_for_case(project=project, case_id=normalized_asset_id, page=page)
    traceability_summary = build_traceability_summary(asset=asset, latest_run=latest_run)
    coverage_matrix = _svc().build_test_point_asset_coverage_matrix(asset=asset, latest_run=latest_run)
    source_type = str(asset.get("source_type", "unknown")).strip() or "unknown"
    return {
        "item": {
            "asset_id": normalized_asset_id,
            "project": project,
            "title": _svc()._derive_asset_title(asset, fallback_id=normalized_asset_id),
            "page": page,
            "priority": str(asset.get("priority", "P1")).strip() or "P1",
            "source_type": source_type,
            "source_label": _svc().source_type_label(source_type),
            "requirement": _svc()._derive_requirement_list(asset),
            "point_count": int(asset.get("point_count", 0) or 0),
            "intent_count": _svc()._derive_intent_count(asset),
            "point_types": asset.get("point_types", []) if isinstance(asset.get("point_types"), list) else [],
            "point_keys": asset.get("point_keys", []) if isinstance(asset.get("point_keys"), list) else [],
            "coverage": asset.get("coverage", {}) if isinstance(asset.get("coverage"), dict) else {},
            "semantic_summary": asset.get("semantic_summary", {}) if isinstance(asset.get("semantic_summary"), dict) else {},
            "technique_summary": asset.get("technique_summary", {}) if isinstance(asset.get("technique_summary"), dict) else {},
            "review_summary": asset.get("review_summary", {}) if isinstance(asset.get("review_summary"), dict) else {},
            "involved_elements": asset.get("involved_elements", []) if isinstance(asset.get("involved_elements"), list) else [],
            "confidence": clamp_confidence(asset.get("confidence", 0)),
            "requires_review": bool(asset.get("requires_review", False)),
            "warnings": asset.get("warnings", []) if isinstance(asset.get("warnings"), list) else [],
            "references": asset.get("references", []) if isinstance(asset.get("references"), list) else [],
            "plan_path": str(asset.get("plan_path", "")).strip(),
            "updated_at": str(asset.get("updated_at", "")).strip(),
            "plan": asset.get("plan", {}) if isinstance(asset.get("plan"), dict) else {},
            "latest_run": latest_run,
            "coverage_matrix": coverage_matrix,
            "traceability_summary": traceability_summary,
            "selection_summary": build_selection_summary(traceability_summary=traceability_summary),
            "quality_report": _build_quality_report(asset),
        }
    }


def build_test_point_asset_selection_summary(
    *,
    traceability_summary: dict[str, Any],
) -> dict[str, Any]:
    summary = traceability_summary if isinstance(traceability_summary, dict) else {}
    coverage = summary.get("coverage", {}) if isinstance(summary.get("coverage"), dict) else {}
    review = summary.get("review", {}) if isinstance(summary.get("review"), dict) else {}
    gate = summary.get("gate", {}) if isinstance(summary.get("gate"), dict) else {}
    risk = summary.get("risk", {}) if isinstance(summary.get("risk"), dict) else {}
    semantic = summary.get("semantic", {}) if isinstance(summary.get("semantic"), dict) else {}
    technique = summary.get("technique", {}) if isinstance(summary.get("technique"), dict) else {}

    reasons: list[str] = []
    selection_state = "ready"
    gate_decision = str(gate.get("effective_decision", gate.get("decision", "allow"))).strip() or "allow"
    asset_review_required = bool(summary.get("asset_review_required", False))
    coverage_asset_status = str(coverage.get("asset_status", "unknown")).strip() or "unknown"
    coverage_run_status = str(coverage.get("latest_run_status", "unknown")).strip() or "unknown"
    pending_sections = int(review.get("pending_sections", 0) or 0)
    review_requires = bool(review.get("requires_review", False))
    risk_requires = bool(risk.get("requires_review", False))
    semantic_requires = bool(semantic.get("requires_review", False))
    semantic_page_type = str(semantic.get("page_type", "")).strip() or "unknown"
    semantic_business_domain = str(semantic.get("business_domain", "")).strip() or "generic"
    design_only_point_count = int(technique.get("design_only_point_count", 0) or 0)
    mainline_point_count = int(technique.get("mainline_point_count", 0) or 0)

    if gate_decision == "block":
        selection_state = "blocked"
        reasons.append(str(gate.get("gate_reason_summary", "")).strip() or "执行门禁阻断。")
    else:
        if gate_decision == "manual_review":
            selection_state = "needs_review"
            reasons.append(str(gate.get("gate_reason_summary", "")).strip() or "执行门禁要求人工复核。")
        if asset_review_required:
            selection_state = "needs_review"
            reasons.append("测试点资产自身仍要求复核。")
        if review_requires or pending_sections > 0:
            selection_state = "needs_review"
            reasons.append(f"仍有待确认分组 {pending_sections} 个。")
        if coverage_asset_status != "full":
            selection_state = "needs_review"
            reasons.append(f"测试点资产 coverage={coverage_asset_status}。")
        if coverage_run_status not in {"full", "unknown"}:
            selection_state = "needs_review"
            reasons.append(f"最近运行 coverage={coverage_run_status}。")
        if risk_requires:
            selection_state = "needs_review"
            reasons.append("风险评估仍要求人工决策。")
        if semantic_requires:
            selection_state = "needs_review"
            reasons.append(f"页面语义仍需复核（type={semantic_page_type}, domain={semantic_business_domain}）。")
        if design_only_point_count > 0 and mainline_point_count <= 0:
            selection_state = "needs_review"
            reasons.append("当前仅有 design_only 设计点，尚未形成可执行主链测试点。")

    return {
        "selection_state": selection_state,
        "ready_for_regression": selection_state == "ready",
        "effective_gate_decision": gate_decision,
        "reasons": _dedup_keep_order([reason for reason in reasons if reason]),
    }


def build_test_point_asset_gate_context(
    *,
    project: str,
    case_id: str,
    page: str,
    coverage: dict[str, Any],
    review_state: dict[str, Any],
    risk_report: dict[str, Any] | None = None,
    safe_case_id_fn: Callable[[str], str],
    load_test_point_asset: LoadTestPointAsset,
    build_review_audit_summary_fn: BuildReviewAuditSummary,
    build_traceability_summary: BuildTraceabilitySummary,
    build_selection_summary: BuildSelectionSummary,
) -> dict[str, Any]:
    normalized_case_id = safe_case_id_fn(case_id)
    if not normalized_case_id:
        return {}
    asset = _state_svc().load_test_point_asset(project, normalized_case_id)
    if not asset:
        return {}

    normalized_review_state = review_state if isinstance(review_state, dict) else {}
    latest_run = {
        "run_id": "",
        "status": "",
        "page": page,
        "review_state": normalized_review_state,
        "review_audit_summary": build_review_audit_summary_fn(normalized_review_state),
        "coverage": coverage if isinstance(coverage, dict) else {},
        "execution_gate": {},
        "execution_gate_summary": {},
        "risk_report": risk_report if isinstance(risk_report, dict) else {},
    }
    traceability_summary = build_traceability_summary(asset=asset, latest_run=latest_run)
    return {
        "asset_id": str(asset.get("asset_id", normalized_case_id)).strip() or normalized_case_id,
        "page": str(asset.get("page", page)).strip() or page,
        "requires_review": bool(asset.get("requires_review", False)),
        "review_summary": asset.get("review_summary", {}) if isinstance(asset.get("review_summary"), dict) else {},
        "coverage": asset.get("coverage", {}) if isinstance(asset.get("coverage"), dict) else {},
        "technique_summary": asset.get("technique_summary", {}) if isinstance(asset.get("technique_summary"), dict) else {},
        "traceability_summary": traceability_summary,
        "selection_summary": build_selection_summary(traceability_summary=traceability_summary),
    }


def build_test_point_asset_summary(
    *,
    project: str,
    case_id: str,
    load_test_point_asset: LoadTestPointAsset,
    latest_run_snapshot_for_case: LatestRunSnapshotForCase,
    build_traceability_summary: BuildTraceabilitySummary,
    build_selection_summary: BuildSelectionSummary,
    clamp_confidence: ClampConfidence,
) -> dict[str, Any]:
    asset = _state_svc().load_test_point_asset(project, case_id)
    if not asset:
        return {}
    latest_run = latest_run_snapshot_for_case(
        project=project,
        case_id=str(asset.get("asset_id", case_id)).strip() or case_id,
        page=str(asset.get("page", "")).strip(),
    )
    traceability_summary = build_traceability_summary(asset=asset, latest_run=latest_run)
    source_type = str(asset.get("source_type", "unknown")).strip() or "unknown"
    return {
        "asset_id": str(asset.get("asset_id", case_id)).strip() or case_id,
        "title": _svc()._derive_asset_title(asset, fallback_id=case_id),
        "page": str(asset.get("page", "")).strip(),
        "priority": str(asset.get("priority", "P1")).strip() or "P1",
        "source_type": source_type,
        "source_label": _svc().source_type_label(source_type),
        "point_count": int(asset.get("point_count", 0) or 0),
        "intent_count": _svc()._derive_intent_count(asset),
        "confidence": clamp_confidence(asset.get("confidence", 0)),
        "requires_review": bool(asset.get("requires_review", False)),
        "plan_path": str(asset.get("plan_path", "")).strip(),
        "review_summary": asset.get("review_summary", {}) if isinstance(asset.get("review_summary"), dict) else {},
        "coverage": asset.get("coverage", {}) if isinstance(asset.get("coverage"), dict) else {},
        "semantic_summary": asset.get("semantic_summary", {}) if isinstance(asset.get("semantic_summary"), dict) else {},
        "technique_summary": asset.get("technique_summary", {}) if isinstance(asset.get("technique_summary"), dict) else {},
        "latest_run": latest_run,
        "traceability_summary": traceability_summary,
        "selection_summary": build_selection_summary(traceability_summary=traceability_summary),
    }


def build_test_point_asset_coverage_summary(
    *,
    items: list[dict[str, Any]],
    filter_snapshot: dict[str, Any],
) -> dict[str, Any]:
    coverage_status_counts: dict[str, int] = {}
    latest_run_coverage_status_counts: dict[str, int] = {}
    selection_state_counts: dict[str, int] = {}
    page_counts: dict[str, int] = {}
    source_type_counts: dict[str, int] = {}
    total_points = 0
    regression_ready_points = 0

    def _count(bucket: dict[str, int], key: str) -> None:
        bucket[key] = int(bucket.get(key, 0) or 0) + 1

    for item in items:
        if not isinstance(item, dict):
            continue
        total_points += int(item.get("point_count", 0) or 0)
        coverage_payload = item.get("coverage", {}) if isinstance(item.get("coverage"), dict) else {}
        traceability_summary = item.get("traceability_summary", {}) if isinstance(item.get("traceability_summary"), dict) else {}
        selection_summary = item.get("selection_summary", {}) if isinstance(item.get("selection_summary"), dict) else {}
        traceability_coverage = traceability_summary.get("coverage", {}) if isinstance(traceability_summary.get("coverage"), dict) else {}
        coverage_status = str(coverage_payload.get("status", "unknown")).strip() or "unknown"
        latest_run_coverage_status = str(traceability_coverage.get("latest_run_status", "unknown")).strip() or "unknown"
        selection_state = str(selection_summary.get("selection_state", "unknown")).strip() or "unknown"
        page_value = str(item.get("page", "")).strip() or "unknown"
        source_type_value = str(item.get("source_type", "")).strip() or "unknown"
        _count(coverage_status_counts, coverage_status)
        _count(latest_run_coverage_status_counts, latest_run_coverage_status)
        _count(selection_state_counts, selection_state)
        _count(page_counts, page_value)
        _count(source_type_counts, source_type_value)
        if bool(selection_summary.get("ready_for_regression", False)):
            regression_ready_points += int(item.get("point_count", 0) or 0)

    return {
        "total_assets": len(items),
        "total_points": total_points,
        "regression_ready_asset_count": int(selection_state_counts.get("ready", 0) or 0),
        "regression_ready_point_count": regression_ready_points,
        "coverage_status_counts": dict(sorted(coverage_status_counts.items())),
        "latest_run_coverage_status_counts": dict(sorted(latest_run_coverage_status_counts.items())),
        "selection_state_counts": dict(sorted(selection_state_counts.items())),
        "page_counts": dict(sorted(page_counts.items())),
        "source_type_counts": dict(sorted(source_type_counts.items())),
        "filter_snapshot": filter_snapshot,
    }


def build_test_point_asset_traceability_summary(
    *,
    asset: dict[str, Any],
    latest_run: dict[str, Any] | None,
    build_test_point_asset_technique_summary_fn: BuildTestPointAssetTechniqueSummary,
    build_review_audit_summary_fn: BuildReviewAuditSummary,
    build_page_semantic_summary_fn: BuildPageSemanticSummary,
    build_risk_report_summary_fn: BuildRiskReportSummary,
    build_execution_gate_fn: BuildExecutionGate,
    build_execution_gate_audit_snapshot_fn: BuildExecutionGateAuditSnapshot,
    clamp_confidence: ClampConfidence,
) -> dict[str, Any]:
    asset_payload = asset if isinstance(asset, dict) else {}
    latest_run_payload = latest_run if isinstance(latest_run, dict) else {}
    asset_semantic_summary = _dict_value(asset_payload.get("semantic_summary"))
    asset_coverage = _dict_value(asset_payload.get("coverage"))
    asset_review_summary = _dict_value(asset_payload.get("review_summary"))
    asset_technique_summary = (
        _dict_value(asset_payload.get("technique_summary"))
        if isinstance(asset_payload.get("technique_summary"), dict)
        else build_test_point_asset_technique_summary_fn(
            normalized_plan=_dict_value(asset_payload.get("plan"))
        )
    )
    run_review_state = _dict_value(latest_run_payload.get("review_state"))
    run_review_audit_summary = (
        _dict_value(latest_run_payload.get("review_audit_summary"))
        if isinstance(latest_run_payload.get("review_audit_summary"), dict)
        else build_review_audit_summary_fn(run_review_state)
    )
    run_execution_gate = _dict_value(latest_run_payload.get("execution_gate"))
    run_page_semantic_summary = (
        _dict_value(latest_run_payload.get("page_semantic_summary"))
        if isinstance(latest_run_payload.get("page_semantic_summary"), dict)
        else build_page_semantic_summary_fn(
            _dict_value(latest_run_payload.get("page_semantic"))
        )
    )
    semantic_summary = (
        run_page_semantic_summary
        if isinstance(run_page_semantic_summary, dict) and run_page_semantic_summary
        else asset_semantic_summary
    )
    run_coverage = _dict_value(latest_run_payload.get("coverage"))
    risk_report = _dict_value(latest_run_payload.get("risk_report"))
    risk_summary = (
        _dict_value(latest_run_payload.get("risk_summary"))
        if isinstance(latest_run_payload.get("risk_summary"), dict)
        else build_risk_report_summary_fn(risk_report)
    )
    derived_execution_gate_summary: dict[str, Any] = {}
    run_page = str(latest_run_payload.get("page", "")).strip() or str(asset_payload.get("page", "")).strip()
    if run_page:
        derived_execution_gate_summary = build_execution_gate_fn(
            page=run_page,
            final_status=str(latest_run_payload.get("status", "")).strip(),
            coverage=run_coverage,
            page_surface_summary=latest_run_payload.get("page_surface_summary")
            if isinstance(latest_run_payload.get("page_surface_summary"), dict)
            else {},
            page_semantic_summary=run_page_semantic_summary,
            page_object_summary=latest_run_payload.get("page_object_summary")
            if isinstance(latest_run_payload.get("page_object_summary"), dict)
            else {},
            test_points=latest_run_payload.get("test_points") if isinstance(latest_run_payload.get("test_points"), dict) else {},
            review_state=run_review_state,
            risk_report=risk_report if isinstance(risk_report, dict) else {},
            test_point_asset_context={},
        )
    derived_execution_gate_audit_summary = (
        build_execution_gate_audit_snapshot_fn(derived_execution_gate_summary)
        if isinstance(derived_execution_gate_summary, dict) and derived_execution_gate_summary
        else {}
    )
    run_execution_gate_summary = _dict_value(
        latest_run_payload.get("execution_gate_summary")
        if isinstance(latest_run_payload.get("execution_gate_summary"), dict)
        else build_execution_gate_audit_snapshot_fn(run_execution_gate)
    )
    gate_summary_payload = derived_execution_gate_audit_summary if derived_execution_gate_audit_summary else run_execution_gate_summary
    gate_reason_summary = str(gate_summary_payload.get("gate_reason_summary", "")).strip()
    semantic_summary_payload = _dict_value(semantic_summary)
    return {
        "asset_review_required": bool(asset_payload.get("requires_review", False)),
        "asset_coverage_status": str(asset_coverage.get("status", "unknown")).strip() or "unknown",
        "asset_pending_review_count": int(asset_review_summary.get("pending_review_count", 0) or 0),
        "latest_run_id": str(latest_run_payload.get("run_id", "")).strip(),
        "latest_run_status": str(latest_run_payload.get("status", "")).strip(),
        "latest_run_at": str(latest_run_payload.get("finished_at", "")).strip()
        or str(latest_run_payload.get("started_at", "")).strip(),
        "coverage": {
            "asset_status": str(asset_coverage.get("status", "unknown")).strip() or "unknown",
            "latest_run_status": str(run_coverage.get("status", "unknown")).strip() or "unknown",
            "missing_count": int(
                run_coverage.get(
                    "missing_count",
                    len(run_coverage.get("missing", []) if isinstance(run_coverage.get("missing"), list) else []),
                )
                or 0
            ),
        },
        "review": {
            "requires_review": bool(run_review_state.get("requires_review", False)),
            "pending_sections": int(run_review_state.get("pending_sections", 0) or 0),
            "confirmed_sections": int(run_review_state.get("confirmed_sections", 0) or 0),
            "element_status": str(
                (run_review_state.get("element", {}) if isinstance(run_review_state.get("element"), dict) else {}).get(
                    "status", "not_required"
                )
            ).strip()
            or "not_required",
            "test_point_status": str(
                (run_review_state.get("test_point", {}) if isinstance(run_review_state.get("test_point"), dict) else {}).get(
                    "status", "not_required"
                )
            ).strip()
            or "not_required",
            "risk_status": str(
                (run_review_state.get("risk", {}) if isinstance(run_review_state.get("risk"), dict) else {}).get(
                    "status", "not_required"
                )
            ).strip()
            or "not_required",
            "latest_actor_display": str(run_review_audit_summary.get("latest_actor_display", "")).strip(),
            "latest_updated_at": str(run_review_audit_summary.get("latest_updated_at", "")).strip(),
        },
        "gate": {
            "decision": str(run_execution_gate.get("decision", "")).strip() or "allow",
            "effective_decision": str(run_execution_gate.get("effective_decision", "")).strip()
            or str(run_execution_gate.get("decision", "")).strip()
            or "allow",
            "decision_source": str(run_execution_gate.get("decision_source", "")).strip() or "system",
            "approval_status": str(run_execution_gate.get("approval_status", "")).strip(),
            "record_status": str(run_execution_gate.get("record_status", "")).strip(),
            "requires_review": bool(run_execution_gate.get("requires_review", False)),
            "gate_reason_summary": gate_reason_summary,
        },
        "risk": {
            "risk_level": str(risk_report.get("risk_level", "")).strip(),
            "gate_decision": str(risk_report.get("gate_decision", "")).strip(),
            "requires_review": bool(risk_report.get("requires_review", False)),
            "factor_count": int(risk_summary.get("factor_count", 0) or 0),
            "top_factor": risk_summary.get("top_factor", {}) if isinstance(risk_summary.get("top_factor"), dict) else {},
            "provider": str(risk_summary.get("provider", "")).strip(),
        },
        "semantic": {
            "page_type": str(semantic_summary_payload.get("page_type", "")).strip(),
            "business_domain": str(semantic_summary_payload.get("business_domain", "")).strip(),
            "primary_goal": str(semantic_summary_payload.get("primary_goal", "")).strip(),
            "primary_actions": _list_value(semantic_summary_payload.get("primary_actions")),
            "confidence": clamp_confidence(semantic_summary_payload.get("confidence", 0)),
            "requires_review": bool(semantic_summary_payload.get("requires_review", False)),
            "source": str(
                semantic_summary_payload.get("source", "run_snapshot" if run_page_semantic_summary else "asset_plan")
            ).strip()
            or ("run_snapshot" if run_page_semantic_summary else "asset_plan"),
        },
        "technique": {
            "total_points": int(asset_technique_summary.get("total_points", 0) or 0),
            "mainline_point_count": int(asset_technique_summary.get("mainline_point_count", 0) or 0),
            "design_only_point_count": int(asset_technique_summary.get("design_only_point_count", 0) or 0),
            "technique_distribution": _dict_value(asset_technique_summary.get("technique_distribution")),
            "has_design_only_points": bool(asset_technique_summary.get("has_design_only_points", False)),
            "mainline_ready": bool(asset_technique_summary.get("mainline_ready", False)),
            "source": "asset_plan",
        },
    }


def latest_run_snapshot_for_case(
    *,
    project: str,
    case_id: str,
    page: str = "",
    safe_case_id_fn: Callable[[str], str],
    normalize_page_slug_fn: NormalizePageSlug,
    runtime_jobs: list[dict[str, Any]],
    runtime_runs_file: Path,
    runtime_view_with_execution_record_preferred_fn: RuntimeViewWithExecutionRecordPreferred,
    read_json_list_fn: ReadJsonList,
    build_review_audit_summary_fn: BuildReviewAuditSummary,
    build_page_semantic_summary_fn: BuildPageSemanticSummary,
    build_execution_gate_audit_snapshot_fn: BuildExecutionGateAuditSnapshot,
    build_risk_report_summary_fn: BuildRiskReportSummary,
) -> dict[str, Any]:
    normalized_project = str(project or "mall").strip() or "mall"
    normalized_case_id = safe_case_id_fn(case_id)
    normalized_page = normalize_page_slug_fn(page) if str(page).strip() else ""
    candidates: list[dict[str, Any]] = []
    candidates.extend(runtime_view_with_execution_record_preferred_fn(dict(item)) for item in runtime_jobs)
    candidates.extend(runtime_view_with_execution_record_preferred_fn(item) for item in read_json_list_fn(runtime_runs_file))
    matched: list[dict[str, Any]] = []
    for item in candidates:
        if str(item.get("project", "mall")).strip() != normalized_project:
            continue
        if safe_case_id_fn(str(item.get("case_id", "")).strip()) != normalized_case_id:
            continue
        item_page = normalize_page_slug_fn(str(item.get("page", "")).strip()) if str(item.get("page", "")).strip() else ""
        if normalized_page and item_page and item_page != normalized_page:
            continue
        matched.append(item)
    if not matched:
        return {}
    matched.sort(
        key=lambda item: (
            str(item.get("finished_at", "")).strip(),
            str(item.get("started_at", "")).strip(),
            str(item.get("run_id", "")).strip(),
        ),
        reverse=True,
    )
    latest = matched[0]
    review_state = _dict_value(latest.get("review_state"))
    review_audit_summary = (
        _dict_value(latest.get("review_audit_summary"))
        if isinstance(latest.get("review_audit_summary"), dict)
        else build_review_audit_summary_fn(review_state)
    )
    execution_gate = _dict_value(latest.get("execution_gate"))
    risk_report = _dict_value(latest.get("risk_report"))
    page_semantic_summary = (
        _dict_value(latest.get("page_semantic_summary"))
        if isinstance(latest.get("page_semantic_summary"), dict)
        else build_page_semantic_summary_fn(_dict_value(latest.get("page_semantic")))
    )
    return {
        "run_id": str(latest.get("run_id", "")).strip(),
        "status": str(latest.get("status", "")).strip(),
        "page": str(latest.get("page", "")).strip(),
        "started_at": str(latest.get("started_at", "")).strip(),
        "finished_at": str(latest.get("finished_at", "")).strip(),
        "page_semantic_summary": page_semantic_summary if isinstance(page_semantic_summary, dict) else {},
        "review_state": review_state,
        "review_audit_summary": review_audit_summary,
        "coverage": _dict_value(latest.get("coverage")),
        "execution_gate": execution_gate,
        "execution_gate_summary": build_execution_gate_audit_snapshot_fn(execution_gate),
        "risk_report": risk_report,
        "risk_summary": build_risk_report_summary_fn(risk_report),
    }
