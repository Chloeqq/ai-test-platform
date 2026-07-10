from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from shared_backend.case_ids import normalize_case_id
from shared_backend.type_utils import (
    dict_value as _dict_value,
)
from shared_backend.type_utils import (
    int_value as _int_value,
)
from shared_backend.type_utils import (
    list_value as _list_value,
)

NormalizeTestPointPlanPayload = Callable[[dict[str, Any], bool], dict[str, Any]]
NowIsoFn = Callable[[], str]
CountTestPointTypesFn = Callable[[list[dict[str, Any]]], dict[str, int]]
MergeReferenceItemsFn = Callable[[list[dict[str, Any]], list[dict[str, Any]]], list[dict[str, Any]]]
BuildSemanticSummaryFn = Callable[[str, dict[str, Any]], dict[str, Any]]
BuildTechniqueSummaryFn = Callable[[dict[str, Any]], dict[str, Any]]
CollectCaseItems = Callable[[str], list[dict[str, Any]]]
PaginateCaseItems = Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]]
ResolveCaseYamlPath = Callable[[str, str], Path]
ReadCaseYaml = Callable[[Path], tuple[dict[str, Any], str]]
LoadTestPointAsset = Callable[[str, str], dict[str, Any]]
LatestRunSnapshotForCase = Callable[..., dict[str, Any]]
BuildTraceabilitySummary = Callable[..., dict[str, Any]]
BuildSelectionSummary = Callable[..., dict[str, Any]]
BuildCoverageSummary = Callable[..., dict[str, Any]]
NormalizePageSlug = Callable[[str], str]
ClampConfidence = Callable[[Any], float]
WriteCaseYaml = Callable[[Path, dict[str, Any]], str]
SaveCaseState = Callable[[str, dict[str, Any], Path], dict[str, Any]]
AppendHistory = Callable[[dict[str, Any]], None]
EnsureProjectWritable = Callable[[str], str]
DerivePoints = Callable[[dict[str, Any]], dict[str, Any]]
BuildReviewAuditSummary = Callable[[dict[str, Any]], dict[str, Any]]
BuildTestPointAssetTechniqueSummary = Callable[..., dict[str, Any]]
BuildPageSemanticSummary = Callable[[dict[str, Any]], dict[str, Any]]
BuildRiskReportSummary = Callable[[dict[str, Any] | None], dict[str, Any]]
BuildExecutionGate = Callable[..., dict[str, Any]]
BuildExecutionGateAuditSnapshot = Callable[[dict[str, Any] | None], dict[str, Any]]
RuntimeViewWithExecutionRecordPreferred = Callable[[dict[str, Any]], dict[str, Any]]
ReadJsonList = Callable[[Path], list[dict[str, Any]]]


def _normalize_project(project: str) -> str:
    normalized = str(project or "mall").strip()
    return normalized or "mall"


def _safe_case_id(raw: str) -> str:
    text = str(raw).strip()
    return normalize_case_id(text) if text else "atp-web-common-core-fn-ai-0001"


from shared_backend.type_utils import dedup_keep_order as _dedup_keep_order

_SOURCE_TYPE_LABELS = {
    "selection_save": "来自 AI 生成",
    "generate_chain": "AI 生成链路",
    "requirement_intents": "AI 需求解析",
    "manual": "手动保存",
    "yaml_case": "YAML 用例同步",
    "fallback": "系统兜底生成",
    "openapi_spec": "OpenAPI 导入",
}
_TECHNICAL_ASSET_ID_RE = re.compile(r"^[a-z0-9]+-web-[a-z0-9][a-z0-9-]*-(?:fn|sm|api|e2e)-ai-\d{4}$", re.IGNORECASE)


def source_type_label(source_type: str) -> str:
    normalized = str(source_type or "").strip().lower()
    return _SOURCE_TYPE_LABELS.get(normalized, normalized or "未知来源")


def _looks_like_asset_identifier(value: Any, *, asset_id: str = "") -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    asset = str(asset_id or "").strip()
    if asset and text == asset:
        return True
    if asset and text == _safe_case_id(asset):
        return True
    return bool(_TECHNICAL_ASSET_ID_RE.match(text))


def _candidate_rows_from_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for point in _list_value(plan.get("points")):
        if not isinstance(point, dict):
            continue
        rows.append(point)
    if rows:
        return rows
    metadata = _dict_value(plan.get("metadata"))
    candidates_raw = _list_value(metadata.get("selected_candidates"))
    candidates = [item for item in candidates_raw if isinstance(item, dict)]
    if candidates:
        return candidates
    for point in _list_value(plan.get("points")):
        if not isinstance(point, dict):
            continue
        point_metadata = _dict_value(point.get("metadata"))
        snapshot = _dict_value(point_metadata.get("candidate_snapshot"))
        if snapshot:
            rows.append(snapshot)
    return rows


def _derive_asset_title(asset: dict[str, Any], *, fallback_id: str) -> str:
    """推导资产展示标题。优先 metadata 中的页面级标题，其次候选标题。"""
    plan = _dict_value(asset.get("plan"))
    metadata = _dict_value(plan.get("metadata"))
    # tier 1: metadata 中的页面级资产标题（如 "login 页面测试点资产集"）
    metadata_title = str(metadata.get("asset_title", "")).strip()
    if metadata_title and not _looks_like_asset_identifier(metadata_title, asset_id=fallback_id):
        return metadata_title
    # tier 2: asset 自身标题
    existing_title = str(asset.get("title", "")).strip()
    if existing_title and not _looks_like_asset_identifier(existing_title, asset_id=fallback_id):
        return existing_title
    # tier 3: plan 标题
    plan_title = str(plan.get("title", "")).strip()
    if plan_title and not _looks_like_asset_identifier(plan_title, asset_id=fallback_id):
        return plan_title
    # tier 4: 候选标题
    for row in _candidate_rows_from_plan(plan):
        title = str(row.get("title") or row.get("summary") or row.get("description") or "").strip()
        if title and not _looks_like_asset_identifier(title, asset_id=fallback_id):
            return title
    # tier 5: 页面级兜底
    page = str(asset.get("page", "")).strip()
    if page:
        return f"{page} 页面测试点资产集"
    return existing_title or fallback_id


def _derive_requirement_list(asset: dict[str, Any]) -> list[str]:
    plan = _dict_value(asset.get("plan"))
    metadata = _dict_value(plan.get("metadata"))
    for key in ("normalized_requirement", "raw_requirement", "original_requirement"):
        value = str(metadata.get(key, "")).strip()
        if value:
            return [value]
    requirement = asset.get("requirement")
    if isinstance(requirement, list):
        rows = [str(item).strip() for item in requirement if str(item).strip()]
        if rows:
            return rows
    plan_requirement = plan.get("requirement")
    if isinstance(plan_requirement, list):
        return [str(item).strip() for item in plan_requirement if str(item).strip()]
    if isinstance(plan_requirement, str) and plan_requirement.strip():
        return [plan_requirement.strip()]
    return []


def _derive_intent_count(asset: dict[str, Any]) -> int:
    plan = _dict_value(asset.get("plan"))
    metadata = _dict_value(plan.get("metadata"))
    point_ids = _dedup_keep_order(
        [
            str(point.get("intent_id") or point.get("key") or "").strip()
            for point in _list_value(plan.get("points"))
            if isinstance(point, dict)
        ]
    )
    if point_ids:
        return len(point_ids)
    selected_ids = _dedup_keep_order([str(item).strip() for item in _list_value(metadata.get("selected_intent_ids"))])
    if selected_ids:
        return len(selected_ids)
    selected_candidates = [item for item in _list_value(metadata.get("selected_candidates")) if isinstance(item, dict)]
    if selected_candidates:
        return len(selected_candidates)
    return int(asset.get("point_count", 0) or 0)


def count_test_point_types(points: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"precondition_count": 0, "navigation_count": 0, "input_count": 0, "assertion_count": 0, "action_count": 0}
    for point in points:
        if not isinstance(point, dict):
            continue
        point_type = str(point.get("point_type", "")).strip().lower()
        action = str(point.get("action", "")).strip().lower()
        if point_type == "precondition" or action == "login":
            counts["precondition_count"] += 1
        elif point_type == "navigation" or action in {"click", "goto"}:
            counts["navigation_count"] += 1
        elif point_type == "input" or action in {"fill", "type"}:
            counts["input_count"] += 1
        elif point_type == "assertion" or action in {"assert_visible", "assert_url", "wait_for"}:
            counts["assertion_count"] += 1
        else:
            counts["action_count"] += 1
    return counts


def build_test_point_asset_semantic_summary(
    *,
    page: str,
    normalized_plan: dict[str, Any],
    normalize_page_slug_fn: NormalizePageSlug,
    clamp_confidence: ClampConfidence,
) -> dict[str, Any]:
    page_value = normalize_page_slug_fn(page) if str(page).strip() else "unknown"
    source_type = str(normalized_plan.get("source_type", "")).strip().lower()
    point_types = {
        str(point.get("point_type", "")).strip().lower()
        for point in normalized_plan.get("points", [])
        if isinstance(point, dict) and str(point.get("point_type", "")).strip()
    }
    actions = {
        str(point.get("action", "")).strip().lower()
        for point in normalized_plan.get("points", [])
        if isinstance(point, dict) and str(point.get("action", "")).strip()
    }
    involved_elements = {
        str(item).strip().lower()
        for item in (normalized_plan.get("involved_elements") or [])
        if str(item).strip()
    }

    if page_value in {"product", "order", "returnapply"}:
        page_type = "list"
    elif page_value in {"addproduct"}:
        page_type = "form"
    elif "input" in point_types or "fill" in actions or "type" in actions:
        page_type = "form"
    elif "navigation" in point_types or "assertion" in point_types:
        page_type = "list"
    else:
        page_type = "unknown"

    if page_value in {"product", "addproduct"}:
        business_domain = "product"
    elif page_value == "order":
        business_domain = "order"
    elif page_value == "returnapply":
        business_domain = "aftersales"
    else:
        business_domain = "generic"

    primary_actions: list[str] = []
    if {"search_input", "search_button"} & involved_elements:
        primary_actions.append("search")
    if "assert_visible" in actions or page_type == "list":
        primary_actions.append("view_results")
    if {"fill", "type"} & actions or page_type == "form":
        primary_actions.append("edit_form")
    if {"click", "submit"} & actions and page_type == "form":
        primary_actions.append("submit")
    primary_actions = _dedup_keep_order(primary_actions)

    if page_type == "list" and "search" in primary_actions:
        primary_goal = "query_and_browse"
    elif page_type == "form" and ("edit_form" in primary_actions or "submit" in primary_actions):
        primary_goal = "edit_and_submit"
    elif page_type == "list":
        primary_goal = "browse_list"
    elif page_type == "form":
        primary_goal = "fill_form"
    else:
        primary_goal = "inspect_page"

    reason_codes: list[str] = [f"asset_page={page_value}", f"asset_source_type={source_type or 'unknown'}"]
    warnings: list[str] = []
    confidence = 0.82
    if page_type == "unknown":
        confidence -= 0.18
        warnings.append("测试点资产未能稳定映射到明确页面类型。")
        reason_codes.append("asset_page_type_unknown")
    if business_domain == "generic":
        confidence -= 0.1
        warnings.append("测试点资产业务域仍偏泛化。")
        reason_codes.append("asset_domain_generic")
    if bool(normalized_plan.get("requires_review", False)):
        confidence -= 0.08
        warnings.append("测试点资产自身仍要求人工复核。")
        reason_codes.append("asset_requires_review")

    requires_review = confidence < 0.75 or bool(normalized_plan.get("requires_review", False))
    return {
        "page_type": page_type,
        "business_domain": business_domain,
        "primary_goal": primary_goal,
        "primary_actions": primary_actions,
        "reason_codes": _dedup_keep_order(reason_codes),
        "confidence": clamp_confidence(confidence),
        "warnings": _dedup_keep_order(warnings),
        "requires_review": requires_review,
        "source": "asset_plan",
    }


def build_test_point_asset_technique_summary(
    *,
    normalized_plan: dict[str, Any],
) -> dict[str, Any]:
    plan = normalized_plan if isinstance(normalized_plan, dict) else {}
    review_summary = _dict_value(plan.get("review_summary"))
    points = _list_value(plan.get("points"))
    total_points = _int_value(review_summary.get("total_points", len(points)))
    mainline_point_count = _int_value(review_summary.get("mainline_point_count", 0))
    design_only_point_count = _int_value(review_summary.get("design_only_point_count", 0))
    technique_distribution_raw = _dict_value(review_summary.get("technique_distribution"))
    technique_distribution = {
        str(key).strip() or "normal": int(value or 0)
        for key, value in technique_distribution_raw.items()
        if str(key).strip()
    }
    if not technique_distribution:
        for point in points:
            if not isinstance(point, dict):
                continue
            technique_type = str(point.get("technique_type", "normal")).strip() or "normal"
            technique_distribution[technique_type] = technique_distribution.get(technique_type, 0) + 1
    if total_points <= 0:
        total_points = len([point for point in points if isinstance(point, dict)])
    if mainline_point_count <= 0 and total_points:
        mainline_point_count = len(
            [
                point
                for point in points
                if isinstance(point, dict)
                and str(point.get("execution_scope", "mainline")).strip().lower() != "design_only"
            ]
        )
    if design_only_point_count <= 0 and total_points:
        design_only_point_count = len(
            [
                point
                for point in points
                if isinstance(point, dict)
                and str(point.get("execution_scope", "mainline")).strip().lower() == "design_only"
            ]
        )
    return {
        "total_points": int(total_points),
        "mainline_point_count": int(mainline_point_count),
        "design_only_point_count": int(design_only_point_count),
        "technique_distribution": dict(sorted(technique_distribution.items())),
        "has_design_only_points": bool(design_only_point_count > 0),
        "mainline_ready": bool(mainline_point_count > 0),
    }


def merge_reference_items(*reference_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for reference_list in reference_lists:
        for item in reference_list:
            if not isinstance(item, dict):
                continue
            normalized = {
                "kind": str(item.get("kind", "")).strip() or "reference",
                "path": str(item.get("path", "")).strip(),
                "case_id": str(item.get("case_id", "")).strip(),
                "page": str(item.get("page", "")).strip(),
            }
            identity = (normalized["kind"], normalized["path"], normalized["case_id"])
            if identity in seen:
                continue
            seen.add(identity)
            merged.append({key: value for key, value in normalized.items() if value})
    return merged


def build_test_point_asset_coverage_matrix(
    *,
    asset: dict[str, Any],
    latest_run: dict[str, Any] | None,
) -> dict[str, Any]:
    asset_payload = asset if isinstance(asset, dict) else {}
    latest_run_payload = latest_run if isinstance(latest_run, dict) else {}
    plan = _dict_value(asset_payload.get("plan"))
    metadata = _dict_value(plan.get("metadata"))
    raw_matrix = _list_value(metadata.get("coverage_matrix"))
    points = _list_value(plan.get("points"))
    point_key_set = {
        str(point.get("key", "")).strip()
        for point in points
        if isinstance(point, dict) and str(point.get("key", "")).strip()
    }
    coverage_payload = _dict_value(latest_run_payload.get("coverage"))
    rows: list[dict[str, Any]] = []

    for index, row in enumerate(raw_matrix, start=1):
        if not isinstance(row, dict):
            continue
        status = str(row.get("traceability_status", "unknown")).strip().lower() or "unknown"
        point_keys = [str(item).strip() for item in _list_value(row.get("point_keys")) if str(item).strip()]
        source_ids = [str(item).strip() for item in _list_value(row.get("source_ids")) if str(item).strip()]
        intent_ids = [str(item).strip() for item in _list_value(row.get("intent_ids")) if str(item).strip()]
        rows.append(
            {
                "row_id": str(row.get("row_id", "")).strip() or f"coverage-row-{index:02d}",
                "traceability_status": status,
                "source_ids": source_ids,
                "intent_ids": intent_ids,
                "point_keys": point_keys,
                "has_point_links": bool(point_keys),
                "missing_point_keys": [key for key in point_keys if key and key not in point_key_set],
                "changed_areas": [str(item).strip() for item in _list_value(row.get("changed_areas")) if str(item).strip()],
                "explanation": str(row.get("explanation", "")).strip(),
            }
        )

    if not rows:
        for index, point in enumerate(points, start=1):
            if not isinstance(point, dict):
                continue
            point_key = str(point.get("key", "")).strip() or f"point-{index:02d}"
            point_intent_id = str(point.get("intent_id", "")).strip() or point_key
            point_metadata = _dict_value(point.get("metadata"))
            traceability = _dict_value(point_metadata.get("traceability"))
            raw_source_ids = [str(item).strip() for item in _list_value(traceability.get("source_ids")) if str(item).strip()]
            intent_ids = [str(item).strip() for item in _list_value(traceability.get("intent_ids")) if str(item).strip()]
            if not intent_ids and point_intent_id:
                intent_ids = [point_intent_id]
            # Older saved assets used the intent id itself as source_id. Treat those as one
            # requirement source so the coverage view stays human-readable instead of 1 row per intent.
            real_source_ids = [
                source_id
                for source_id in raw_source_ids
                if source_id.lower().startswith(("source-", "req-", "requirement-"))
            ]
            source_ids = real_source_ids or (["source-01"] if intent_ids else [])
            status = "covered" if source_ids or intent_ids else "orphan"
            rows.append(
                {
                    "row_id": f"derived-{point_key}",
                    "traceability_status": status,
                    "source_ids": source_ids,
                    "intent_ids": intent_ids,
                    "point_keys": [point_key],
                    "has_point_links": True,
                    "missing_point_keys": [],
                    "changed_areas": [],
                    "explanation": "derived from test point traceability metadata",
                }
            )

    grouped_rows: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for index, row in enumerate(rows, start=1):
        status = str(row.get("traceability_status", "unknown")).strip().lower() or "unknown"
        source_ids = _dedup_keep_order([str(item).strip() for item in _list_value(row.get("source_ids"))])
        group_key = (status, tuple(source_ids))
        existing_row = grouped_rows.get(group_key)
        if existing_row is None:
            existing_row = {
                "row_id": f"coverage-{status}-{index:02d}",
                "traceability_status": status,
                "source_ids": source_ids,
                "intent_ids": [],
                "point_keys": [],
                "has_point_links": False,
                "missing_point_keys": [],
                "changed_areas": [],
                "explanation": "",
            }
            grouped_rows[group_key] = existing_row
        existing_row["intent_ids"] = _dedup_keep_order(
            [*existing_row["intent_ids"], *[str(item).strip() for item in _list_value(row.get("intent_ids"))]]
        )
        existing_row["point_keys"] = _dedup_keep_order(
            [*existing_row["point_keys"], *[str(item).strip() for item in _list_value(row.get("point_keys"))]]
        )
        existing_row["missing_point_keys"] = _dedup_keep_order(
            [*existing_row["missing_point_keys"], *[str(item).strip() for item in _list_value(row.get("missing_point_keys"))]]
        )
        existing_row["changed_areas"] = _dedup_keep_order(
            [*existing_row["changed_areas"], *[str(item).strip() for item in _list_value(row.get("changed_areas"))]]
        )
        explanations = _dedup_keep_order(
            [
                str(existing_row.get("explanation", "")).strip(),
                str(row.get("explanation", "")).strip(),
            ]
        )
        existing_row["explanation"] = "；".join(explanations)
        existing_row["has_point_links"] = bool(existing_row["point_keys"])

    rows = list(grouped_rows.values())
    covered_count = 0
    partial_count = 0
    gap_count = 0
    orphan_count = 0
    for row in rows:
        status = str(row.get("traceability_status", "unknown")).strip().lower() or "unknown"
        item_count = len(_list_value(row.get("intent_ids"))) or len(_list_value(row.get("point_keys"))) or 1
        if status == "covered":
            covered_count += item_count
        elif status == "partial":
            partial_count += item_count
        elif status == "gap":
            gap_count += item_count
        elif status == "orphan":
            orphan_count += item_count

    latest_run_status = str(coverage_payload.get("status", "")).strip() or "unknown"
    matrix_status = "covered"
    if gap_count > 0:
        matrix_status = "gap"
    elif partial_count > 0:
        matrix_status = "partial"
    elif orphan_count > 0:
        matrix_status = "orphan"

    return {
        "asset_id": _safe_case_id(str(asset_payload.get("asset_id", "")).strip()),
        "page": str(asset_payload.get("page", "")).strip(),
        "row_count": len(rows),
        "rows": rows,
        "summary": {
            "covered_count": covered_count,
            "partial_count": partial_count,
            "gap_count": gap_count,
            "orphan_count": orphan_count,
            "status": matrix_status,
            "latest_run_status": latest_run_status,
            "latest_run_missing_count": int(coverage_payload.get("missing_count", 0) or 0),
        },
    }



# ---- 以下函数体已移至 workbench_asset_state.py 和 workbench_asset_views.py ----
# 导入放在文件末尾以避免循环依赖

from app.services.workbench_asset_state import (  # noqa: E402
    collect_case_items,
    derive_points,
    infer_targets,
    load_test_point_asset,
    load_test_point_asset_with_root,
    resolve_case_yaml_path,
    save_case_state,
    save_test_point_plan,
    state_case_file,
    state_case_versions_dir,
    state_project_dir,
    upsert_test_point_asset_snapshot,
)
from app.services.workbench_asset_views import (  # noqa: E402
    build_case_detail,
    build_cases_payload,
    build_saved_case_payload,
    build_test_point_asset_coverage_summary,
    build_test_point_asset_detail,
    build_test_point_asset_gate_context,
    build_test_point_asset_items,
    build_test_point_asset_selection_summary,
    build_test_point_asset_summary,
    build_test_point_asset_traceability_summary,
    latest_run_snapshot_for_case,
    paginate_case_items,
    read_case_yaml,
    write_case_yaml,
)
