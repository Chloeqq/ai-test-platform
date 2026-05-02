from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import yaml
from fastapi import HTTPException, status
from shared_backend.case_ids import normalize_case_id
from shared_backend.case_rules import enrich_case_metadata, validate_case_payload

from . import workbench_state_store as state_store

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
BuildTestPointAssetTechniqueSummary = Callable[[dict[str, Any]], dict[str, Any]]
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


def _dedup_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _int_value(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_value(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
    covered_count = 0
    partial_count = 0
    gap_count = 0
    orphan_count = 0

    for index, row in enumerate(raw_matrix, start=1):
        if not isinstance(row, dict):
            continue
        status = str(row.get("traceability_status", "unknown")).strip().lower() or "unknown"
        point_keys = [str(item).strip() for item in _list_value(row.get("point_keys")) if str(item).strip()]
        source_ids = [str(item).strip() for item in _list_value(row.get("source_ids")) if str(item).strip()]
        intent_ids = [str(item).strip() for item in _list_value(row.get("intent_ids")) if str(item).strip()]
        if status == "covered":
            covered_count += 1
        elif status == "partial":
            partial_count += 1
        elif status == "gap":
            gap_count += 1
        elif status == "orphan":
            orphan_count += 1
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
            point_metadata = _dict_value(point.get("metadata"))
            traceability = _dict_value(point_metadata.get("traceability"))
            source_ids = [str(item).strip() for item in _list_value(traceability.get("source_ids")) if str(item).strip()]
            intent_ids = [str(item).strip() for item in _list_value(traceability.get("intent_ids")) if str(item).strip()]
            status = "covered" if source_ids or intent_ids else "orphan"
            if status == "covered":
                covered_count += 1
            else:
                orphan_count += 1
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


def _state_test_points_root(state_root: Path | None = None) -> Path:
    return Path(state_root) if state_root is not None else state_store.WEB_UI_STATE_ROOT / "test-points"


def _state_project_dir(project: str, *, state_root: Path | None = None) -> Path:
    return _state_test_points_root(state_root) / _normalize_project(project)


def _state_case_file(project: str, case_id: str, *, state_root: Path | None = None) -> Path:
    return _state_project_dir(project, state_root=state_root) / f"{_safe_case_id(case_id)}.json"


def state_project_dir(project: str, *, state_root: Path | None = None) -> Path:
    return _state_project_dir(project, state_root=state_root)


def state_case_file(project: str, case_id: str, *, state_root: Path | None = None) -> Path:
    return _state_case_file(project, case_id, state_root=state_root)


def state_case_versions_dir(project: str, case_id: str, *, state_root: Path | None = None) -> Path:
    return _state_project_dir(project, state_root=state_root) / "versions" / _safe_case_id(case_id)


def resolve_case_yaml_path(
    project: str,
    case_id: str,
    *,
    state_case_file_fn: Callable[[str, str], Path],
    repo_root: Path,
    assets_cases_root: Path,
    ai_cases_root: Path,
    is_within_fn: Callable[[Path, Path], bool],
) -> Path:
    state_path = state_case_file_fn(project, case_id)
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
        source_ref = str((state or {}).get("source_ref", "")).strip()
        if source_ref:
            candidate = Path(source_ref).expanduser()
            if not candidate.is_absolute():
                candidate = repo_root / candidate
            candidate = candidate.resolve()
            if candidate.exists() and is_within_fn(candidate, assets_cases_root):
                return candidate
    direct_candidate = (ai_cases_root / f"{case_id}.yaml").resolve()
    if direct_candidate.exists():
        return direct_candidate
    for candidate in sorted(assets_cases_root.rglob("*.yaml")):
        try:
            payload = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        except Exception:
            payload = {}
        candidate_id = _safe_case_id(str(payload.get("id", candidate.stem)).strip() or candidate.stem)
        if candidate_id == _safe_case_id(case_id):
            return candidate.resolve()
    return direct_candidate


def collect_case_items(
    project: str,
    *,
    state_project_dir_fn: Callable[[str], Path],
    resolve_case_yaml_path_fn: ResolveCaseYamlPath,
    ai_cases_root: Path,
) -> list[dict[str, Any]]:
    project_dir = state_project_dir_fn(project)
    items: list[dict[str, Any]] = []
    if project_dir.exists():
        for file in sorted(project_dir.glob("*.json")):
            try:
                state = json.loads(file.read_text(encoding="utf-8")) or {}
            except Exception:
                state = {}
            case_id = _safe_case_id(str(state.get("asset_id", file.stem)).strip() or file.stem)
            items.append(
                {
                    "case_id": case_id,
                    "title": str(state.get("title", case_id)).strip() or case_id,
                    "page": str(state.get("page", "product")).strip() or "product",
                    "priority": str(state.get("priority", "P1")).strip() or "P1",
                    "updated_at": str(state.get("updated_at", "")).strip(),
                    "path": str(resolve_case_yaml_path_fn(project, case_id)),
                }
            )

    known_ids = {item["case_id"] for item in items}
    for path in sorted(ai_cases_root.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            payload = {}
        case_id = _safe_case_id(str(payload.get("id", path.stem)).strip() or path.stem)
        if case_id in known_ids:
            continue
        items.append(
            {
                "case_id": case_id,
                "title": str(payload.get("title", case_id)).strip() or case_id,
                "page": str((payload.get("execution") or {}).get("page", payload.get("module", "product"))).strip() or "product",
                "priority": str(payload.get("priority", "P1")).strip() or "P1",
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
                "path": str(path.resolve()),
            }
        )

    items.sort(key=lambda item: (str(item.get("updated_at", "")), str(item.get("case_id", ""))), reverse=True)
    return items


def derive_points(case_yaml: dict[str, Any]) -> dict[str, Any]:
    execution = case_yaml.get("execution") or {}
    steps = execution.get("steps") or []
    if not isinstance(steps, list):
        steps = []
    point_types: list[str] = []
    point_keys: list[str] = []
    counts = {"precondition_count": 0, "navigation_count": 0, "input_count": 0, "assertion_count": 0, "action_count": 0}
    for index, step in enumerate(steps, start=1):
        action = str((step or {}).get("action", "")).strip()
        if action == "login":
            point_type = "precondition"
            counts["precondition_count"] += 1
        elif action in {"click", "goto"}:
            point_type = "navigation"
            counts["navigation_count"] += 1
        elif action in {"fill", "type"}:
            point_type = "input"
            counts["input_count"] += 1
        elif action in {"assert_visible", "assert_url", "wait_for"}:
            point_type = "assertion"
            counts["assertion_count"] += 1
        else:
            point_type = "action"
            counts["action_count"] += 1
        point_types.append(point_type)
        point_keys.append(f"{case_yaml.get('module', 'page')}-{index:02d}")
    return {
        "point_count": len(steps),
        "point_types": sorted(set(point_types)),
        "point_keys": point_keys,
        **counts,
    }


def save_case_state(
    project: str,
    case_yaml: dict[str, Any],
    source_path: Path,
    *,
    safe_case_id_fn: Callable[[str], str],
    now_iso_fn: NowIsoFn,
    derive_points_fn: DerivePoints,
    state_case_file_fn: Callable[[str, str], Path],
    state_case_versions_dir_fn: Callable[[str, str], Path],
) -> dict[str, Any]:
    case_id = safe_case_id_fn(str(case_yaml.get("id", "")).strip())
    case_yaml["id"] = case_id
    state = {
        "asset_id": case_id,
        "version": 1,
        "updated_at": now_iso_fn(),
        "title": str(case_yaml.get("title", "")).strip() or case_id,
        "page": str((case_yaml.get("execution") or {}).get("page", case_yaml.get("module", "product"))).strip() or "product",
        "requirement": case_yaml.get("requirement") if isinstance(case_yaml.get("requirement"), list) else [],
        "priority": str(case_yaml.get("priority", "P1")).strip() or "P1",
        "source_type": "yaml_case",
        "source_name": case_id,
        "source_ref": str(source_path.resolve()),
        "references": [
            {
                "kind": "case_yaml",
                "path": str(source_path.resolve()),
                "case_id": case_id,
            }
        ],
    }
    state.update(derive_points_fn(case_yaml))

    state_file = state_case_file_fn(project, case_id)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    if state_file.exists():
        try:
            previous = json.loads(state_file.read_text(encoding="utf-8")) or {}
        except Exception:
            previous = {}
        if isinstance(previous, dict):
            prev_version = int(previous.get("version", 1) or 1)
            state["version"] = prev_version + 1

    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    versions_dir = state_case_versions_dir_fn(project, case_id)
    versions_dir.mkdir(parents=True, exist_ok=True)
    seq = len(list(versions_dir.glob("*.json"))) + 1
    version_file = versions_dir / f"{seq:04d}.json"
    version_file.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def infer_targets(page_name: str, *, page_objects_root: Path) -> tuple[str, str]:
    page_object_path = page_objects_root / f"{page_name}.page-object.yaml"
    menu_target = f"{page_name}_menu"
    assert_target = f"{page_name}_list_title"
    if not page_object_path.exists():
        return menu_target, assert_target

    try:
        payload = yaml.safe_load(page_object_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return menu_target, assert_target
    elements = payload.get("elements", {})
    if not isinstance(elements, dict) or not elements:
        return menu_target, assert_target

    keys = list(elements.keys())
    for key in keys:
        if key.endswith("_menu") or "menu" in key:
            menu_target = key
            break
    for key in keys:
        if key.endswith("_list_title") or key.endswith("_table") or key.endswith("_list") or "title" in key:
            assert_target = key
            break
    return menu_target, assert_target


def save_test_point_plan(
    *,
    project: str,
    case_id: str,
    page: str,
    page_url: str,
    requirement: str,
    plan: dict[str, Any],
    now_iso_fn: NowIsoFn,
    normalize_test_point_plan_payload: NormalizeTestPointPlanPayload,
    upsert_test_point_asset_snapshot: Callable[..., dict[str, Any]],
    state_root: Path | None = None,
    case_path: Path | None = None,
    page_object_path: Path | None = None,
) -> Path:
    plans_dir = _state_project_dir(project, state_root=state_root) / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    target = plans_dir / f"{_safe_case_id(case_id)}.json"
    normalized_plan = normalize_test_point_plan_payload(
        {
            "version": "TestPointPlanV1",
            "project": project,
            "case_id": case_id,
            "page": page,
            "page_url": page_url,
            "source_type": str(plan.get("source_type", "generate_chain")).strip() if isinstance(plan, dict) else "generate_chain",
            "requirement": [requirement],
            "generated_at": now_iso_fn(),
            "points": (plan or {}).get("points", []) if isinstance(plan, dict) else [],
            "coverage": (plan or {}).get("coverage", {}) if isinstance(plan, dict) else {},
            "review_summary": (plan or {}).get("review_summary", {}) if isinstance(plan, dict) else {},
            "metadata": {
                "saved_by": "web-ui-service",
                "raw_plan_keys": sorted((plan or {}).keys()) if isinstance(plan, dict) else [],
                **((plan or {}).get("metadata", {}) if isinstance((plan or {}).get("metadata"), dict) else {}),
            },
            "involved_elements": (plan or {}).get("involved_elements", []) if isinstance(plan, dict) else [],
            "confidence": (plan or {}).get("confidence") if isinstance(plan, dict) else None,
            "warnings": (plan or {}).get("warnings", []) if isinstance(plan, dict) else [],
            "requires_review": (plan or {}).get("requires_review", False) if isinstance(plan, dict) else False,
        },
        False,
    )
    target.write_text(json.dumps(normalized_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    upsert_test_point_asset_snapshot(
        project=project,
        case_id=case_id,
        page=page,
        requirement=requirement,
        normalized_plan=normalized_plan,
        plan_path=target,
        state_root=state_root,
        case_path=case_path,
        page_object_path=page_object_path,
    )
    return target


def upsert_test_point_asset_snapshot(
    *,
    project: str,
    case_id: str,
    page: str,
    requirement: str,
    normalized_plan: dict[str, Any],
    plan_path: Path,
    case_path: Path | None = None,
    page_object_path: Path | None = None,
    now_iso_fn: NowIsoFn,
    count_test_point_types_fn: CountTestPointTypesFn,
    build_test_point_asset_semantic_summary_fn: BuildSemanticSummaryFn,
    build_test_point_asset_technique_summary_fn: BuildTechniqueSummaryFn,
    merge_reference_items_fn: MergeReferenceItemsFn,
    state_root: Path | None = None,
) -> dict[str, Any]:
    asset_path = _state_case_file(project, case_id, state_root=state_root)
    existing: dict[str, Any] = {}
    if asset_path.exists():
        try:
            existing = json.loads(asset_path.read_text(encoding="utf-8")) or {}
        except Exception:
            existing = {}
    points = _list_value(normalized_plan.get("points"))
    point_types = sorted(
        {
            str(point.get("point_type", "")).strip()
            for point in points
            if isinstance(point, dict) and str(point.get("point_type", "")).strip()
        }
    )
    point_keys = [
        str(point.get("key", "")).strip()
        for point in points
        if isinstance(point, dict) and str(point.get("key", "")).strip()
    ]
    references_existing_raw = _list_value(existing.get("references"))
    references_existing: list[dict[str, Any]] = [item for item in references_existing_raw if isinstance(item, dict)]
    references_new: list[dict[str, Any]] = [
        {
            "kind": "test_point_plan",
            "path": str(plan_path.resolve()),
            "case_id": case_id,
            "page": page,
        }
    ]
    if isinstance(case_path, Path):
        references_new.append(
            {
                "kind": "case_yaml",
                "path": str(case_path.resolve()),
                "case_id": case_id,
                "page": page,
            }
        )
    if isinstance(page_object_path, Path) and page_object_path.exists():
        references_new.append(
            {
                "kind": "page_object",
                "path": str(page_object_path.resolve()),
                "case_id": case_id,
                "page": page,
            }
        )
    type_counts = count_test_point_types_fn([point for point in points if isinstance(point, dict)])
    semantic_summary = build_test_point_asset_semantic_summary_fn(page, normalized_plan)
    technique_summary = build_test_point_asset_technique_summary_fn(normalized_plan)
    requirement_list = _list_value(normalized_plan.get("requirement"))
    if not requirement_list:
        requirement_list = [requirement]
    existing_confidence = _float_value(existing.get("confidence", 0))
    asset = {
        **existing,
        "asset_id": _safe_case_id(case_id),
        "version": int(existing.get("version", 0) or 0) + 1,
        "updated_at": now_iso_fn(),
        "title": str(existing.get("title", "")).strip() or str(normalized_plan.get("title", "")).strip() or case_id,
        "page": str(page).strip() or str(existing.get("page", "")).strip() or "unknown",
        "requirement": [str(item).strip() for item in requirement_list if str(item).strip()],
        "priority": str(normalized_plan.get("priority", existing.get("priority", "P1"))).strip() or "P1",
        "source_type": str(normalized_plan.get("source_type", existing.get("source_type", "generate_chain"))).strip() or "generate_chain",
        "source_name": str(normalized_plan.get("source_name", existing.get("source_name", case_id))).strip() or case_id,
        "source_ref": str(normalized_plan.get("source_ref", existing.get("source_ref", str(plan_path.resolve())))).strip() or str(plan_path.resolve()),
        "plan_path": str(plan_path.resolve()),
        "point_count": len(points),
        "point_types": point_types,
        "point_keys": point_keys,
        "review_summary": _dict_value(normalized_plan.get("review_summary")),
        "coverage": _dict_value(normalized_plan.get("coverage")),
        "semantic_summary": semantic_summary,
        "technique_summary": technique_summary,
        "involved_elements": _list_value(normalized_plan.get("involved_elements")),
        "confidence": max(0.0, min(1.0, _float_value(normalized_plan.get("confidence", existing_confidence)))),
        "warnings": _list_value(normalized_plan.get("warnings")),
        "requires_review": bool(normalized_plan.get("requires_review", existing.get("requires_review", False))),
        "references": merge_reference_items_fn(references_existing, references_new),
        "plan": normalized_plan,
        **type_counts,
    }
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_text(json.dumps(asset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return asset


def load_test_point_asset(project: str, case_id: str) -> dict[str, Any]:
    return load_test_point_asset_with_root(project, case_id)


def load_test_point_asset_with_root(project: str, case_id: str, *, state_root: Path | None = None) -> dict[str, Any]:
    normalized_case_id = _safe_case_id(case_id)
    asset_path = _state_case_file(project, normalized_case_id, state_root=state_root)
    plan_path = _state_project_dir(project, state_root=state_root) / "plans" / f"{normalized_case_id}.json"
    asset: dict[str, Any] = {}
    if asset_path.exists():
        try:
            asset = json.loads(asset_path.read_text(encoding="utf-8")) or {}
        except Exception:
            asset = {}
    if plan_path.exists():
        try:
            plan_payload = json.loads(plan_path.read_text(encoding="utf-8")) or {}
        except Exception:
            plan_payload = {}
        if isinstance(plan_payload, dict) and plan_payload:
            if not asset:
                asset = {
                    "asset_id": normalized_case_id,
                    "page": str(plan_payload.get("page", "")).strip(),
                    "priority": str(plan_payload.get("priority", "P1")).strip() or "P1",
                    "source_type": str(plan_payload.get("source_type", "generate_chain")).strip() or "generate_chain",
                }
            if not isinstance(asset.get("plan"), dict):
                asset["plan"] = plan_payload
            asset.setdefault("plan_path", str(plan_path.resolve()))
            asset.setdefault("point_count", int(plan_payload.get("point_count", len(plan_payload.get("points", []) if isinstance(plan_payload.get("points"), list) else [])) or 0))
            asset.setdefault("review_summary", plan_payload.get("review_summary", {}) if isinstance(plan_payload.get("review_summary"), dict) else {})
            asset.setdefault("coverage", plan_payload.get("coverage", {}) if isinstance(plan_payload.get("coverage"), dict) else {})
            asset.setdefault("involved_elements", plan_payload.get("involved_elements", []) if isinstance(plan_payload.get("involved_elements"), list) else [])
            asset.setdefault("confidence", max(0.0, min(1.0, float(plan_payload.get("confidence", 0) or 0))))
            asset.setdefault("requires_review", bool(plan_payload.get("requires_review", False)))
    if isinstance(asset, dict):
        if str(asset.get("asset_id", "")).strip():
            asset["asset_id"] = _safe_case_id(str(asset.get("asset_id", "")).strip())
        return asset
    return {}


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
    focus_value = _safe_case_id(focus_case_id) if str(focus_case_id).strip() else ""
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
    normalized_case_id = _safe_case_id(case_id)
    case_path = resolve_case_yaml_path(project, normalized_case_id)
    payload, content = read_case_yaml(case_path)
    return {
        "item": {
            "case_id": normalized_case_id,
            "project": project,
            "path": str(case_path.resolve()),
            "title": str(payload.get("title", normalized_case_id)).strip() or normalized_case_id,
            "page": str((payload.get("execution") or {}).get("page", payload.get("module", "product"))).strip() or "product",
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
            (index for index, item in enumerate(items) if _safe_case_id(str(item.get("case_id", "")).strip()) == focus_case_id),
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
    case_path = resolve_case_yaml_path(normalized_project, normalized_case_id)
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
    state_entry = save_case_state(normalized_project, case_yaml, case_path)
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
) -> dict[str, Any]:
    project_dir = state_project_dir(project)
    normalized_page = normalize_page_slug(page) if str(page).strip() else ""
    keyword_value = str(keyword or "").strip().lower()
    source_type_value = str(source_type or "").strip().lower()
    coverage_status_value = str(coverage_status or "").strip().lower()
    review_status_value = str(review_status or "").strip().lower()
    gate_decision_value = str(gate_decision or "").strip().lower()
    selection_state_value = str(selection_state or "").strip().lower()
    case_ids: set[str] = set()
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
        requirement_text = (
            " ".join(str(item).strip() for item in asset.get("requirement", []) if str(item).strip())
            if isinstance(asset.get("requirement"), list)
            else ""
        )
        title_text = str(asset.get("title", "")).strip()
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
                "point_count": int(asset.get("point_count", 0) or 0),
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
    }


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
    normalized_asset_id = _safe_case_id(asset_id)
    asset = load_test_point_asset(project, normalized_asset_id)
    if not asset:
        return {}
    page = str(asset.get("page", "")).strip()
    latest_run = latest_run_snapshot_for_case(project=project, case_id=normalized_asset_id, page=page)
    traceability_summary = build_traceability_summary(asset=asset, latest_run=latest_run)
    coverage_matrix = build_test_point_asset_coverage_matrix(asset=asset, latest_run=latest_run)
    return {
        "item": {
            "asset_id": normalized_asset_id,
            "project": project,
            "title": str(asset.get("title", normalized_asset_id)).strip() or normalized_asset_id,
            "page": page,
            "priority": str(asset.get("priority", "P1")).strip() or "P1",
            "source_type": str(asset.get("source_type", "unknown")).strip() or "unknown",
            "requirement": asset.get("requirement", []) if isinstance(asset.get("requirement"), list) else [],
            "point_count": int(asset.get("point_count", 0) or 0),
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
    asset = load_test_point_asset(project, normalized_case_id)
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
    asset = load_test_point_asset(project, case_id)
    if not asset:
        return {}
    latest_run = latest_run_snapshot_for_case(
        project=project,
        case_id=str(asset.get("asset_id", case_id)).strip() or case_id,
        page=str(asset.get("page", "")).strip(),
    )
    traceability_summary = build_traceability_summary(asset=asset, latest_run=latest_run)
    return {
        "asset_id": str(asset.get("asset_id", case_id)).strip() or case_id,
        "title": str(asset.get("title", case_id)).strip() or case_id,
        "page": str(asset.get("page", "")).strip(),
        "priority": str(asset.get("priority", "P1")).strip() or "P1",
        "source_type": str(asset.get("source_type", "unknown")).strip() or "unknown",
        "point_count": int(asset.get("point_count", 0) or 0),
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
            _dict_value(asset_payload.get("plan"))
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
