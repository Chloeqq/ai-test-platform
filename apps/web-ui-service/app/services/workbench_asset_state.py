"""Workbench 资产状态管理 —— YAML 文件读写、case 管理。

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

def _state_test_points_root(state_root: Path | None = None) -> Path:
    return Path(state_root) if state_root is not None else state_store.WEB_UI_STATE_ROOT / "test-points"


def _state_project_dir(project: str, *, state_root: Path | None = None) -> Path:
    return _state_test_points_root(state_root) / _svc()._normalize_project(project)


def _state_case_file(project: str, case_id: str, *, state_root: Path | None = None) -> Path:
    return _state_project_dir(project, state_root=state_root) / f"{_svc()._safe_case_id(case_id)}.json"


def state_project_dir(project: str, *, state_root: Path | None = None) -> Path:
    return _state_project_dir(project, state_root=state_root)


def state_case_file(project: str, case_id: str, *, state_root: Path | None = None) -> Path:
    return _state_case_file(project, case_id, state_root=state_root)


def state_case_versions_dir(project: str, case_id: str, *, state_root: Path | None = None) -> Path:
    return _state_project_dir(project, state_root=state_root) / "versions" / _svc()._safe_case_id(case_id)


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
        except (json.JSONDecodeError, ValueError):
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
        except yaml.YAMLError:
            payload = {}
        candidate_id = _svc()._safe_case_id(str(payload.get("id", candidate.stem)).strip() or candidate.stem)
        if candidate_id == _svc()._safe_case_id(case_id):
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
            except (json.JSONDecodeError, ValueError):
                state = {}
            case_id = _svc()._safe_case_id(str(state.get("asset_id", file.stem)).strip() or file.stem)
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
        except yaml.YAMLError:
            payload = {}
        case_id = _svc()._safe_case_id(str(payload.get("id", path.stem)).strip() or path.stem)
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
        elif action in {"fill", "type", "input"}:
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
    raw_requirement = case_yaml.get("requirement")
    if isinstance(raw_requirement, list):
        requirement_payload = raw_requirement
    elif isinstance(raw_requirement, dict):
        requirement_payload = [
            str(raw_requirement.get(key, "")).strip()
            for key in ("title", "intent_id", "type", "precondition", "source_asset_id")
            if str(raw_requirement.get(key, "")).strip()
        ]
    else:
        requirement_payload = []
    state = {
        "asset_id": case_id,
        "version": 1,
        "updated_at": now_iso_fn(),
        "title": str(case_yaml.get("title", "")).strip() or case_id,
        "page": str((case_yaml.get("execution") or {}).get("page", case_yaml.get("module", "product"))).strip() or "product",
        "requirement": requirement_payload,
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
        except (json.JSONDecodeError, ValueError):
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
    except yaml.YAMLError:
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
    target = plans_dir / f"{_svc()._safe_case_id(case_id)}.json"
    normalized_plan = normalize_test_point_plan_payload(
        {
            "version": "TestPointPlanV1",
            "project": project,
            "case_id": case_id,
            "page": page,
            "page_url": page_url,
            "title": str(plan.get("title", "")).strip() if isinstance(plan, dict) else "",
            "priority": str(plan.get("priority", "")).strip() if isinstance(plan, dict) else "",
            "source_name": str(plan.get("source_name", "")).strip() if isinstance(plan, dict) else "",
            "source_ref": str(plan.get("source_ref", "")).strip() if isinstance(plan, dict) else "",
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
        except (json.JSONDecodeError, ValueError):
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
    technique_summary = build_test_point_asset_technique_summary_fn(normalized_plan=normalized_plan)
    requirement_list = _list_value(normalized_plan.get("requirement"))
    if not requirement_list:
        requirement_list = [requirement]
    existing_confidence = _float_value(existing.get("confidence", 0))
    provisional_asset = {
        **existing,
        "plan": normalized_plan,
        "requirement": [str(item).strip() for item in requirement_list if str(item).strip()],
    }
    title = _svc()._derive_asset_title(provisional_asset, fallback_id=case_id)
    source_type = str(normalized_plan.get("source_type", existing.get("source_type", "generate_chain"))).strip() or "generate_chain"
    asset = {
        **existing,
        "asset_id": _svc()._safe_case_id(case_id),
        "version": int(existing.get("version", 0) or 0) + 1,
        "updated_at": now_iso_fn(),
        "title": title,
        "page": str(page).strip() or str(existing.get("page", "")).strip() or "unknown",
        "requirement": [str(item).strip() for item in requirement_list if str(item).strip()],
        "priority": str(normalized_plan.get("priority", existing.get("priority", "P1"))).strip() or "P1",
        "source_type": source_type,
        "source_label": _svc().source_type_label(source_type),
        "source_name": str(normalized_plan.get("source_name", existing.get("source_name", case_id))).strip() or case_id,
        "source_ref": str(normalized_plan.get("source_ref", existing.get("source_ref", str(plan_path.resolve())))).strip() or str(plan_path.resolve()),
        "plan_path": str(plan_path.resolve()),
        "point_count": len(points),
        "intent_count": 0,
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
    asset["intent_count"] = _svc()._derive_intent_count(asset)
    asset["requirement"] = _svc()._derive_requirement_list(asset)
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_text(json.dumps(asset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return asset


def load_test_point_asset(project: str, case_id: str) -> dict[str, Any]:
    return load_test_point_asset_with_root(project, case_id)


def load_test_point_asset_with_root(project: str, case_id: str, *, state_root: Path | None = None) -> dict[str, Any]:
    raw_case_id = str(case_id or "").strip()
    normalized_case_id = _svc()._safe_case_id(case_id)
    project_dir = _state_project_dir(project, state_root=state_root)
    candidate_ids = [normalized_case_id]
    if raw_case_id and raw_case_id not in candidate_ids:
        candidate_ids.append(raw_case_id)
    asset_path = next(
        (project_dir / f"{candidate_id}.json" for candidate_id in candidate_ids if (project_dir / f"{candidate_id}.json").exists()),
        project_dir / f"{normalized_case_id}.json",
    )
    plan_path = next(
        (
            project_dir / "plans" / f"{candidate_id}.json"
            for candidate_id in candidate_ids
            if (project_dir / "plans" / f"{candidate_id}.json").exists()
        ),
        project_dir / "plans" / f"{normalized_case_id}.json",
    )
    asset: dict[str, Any] = {}
    if asset_path.exists():
        try:
            asset = json.loads(asset_path.read_text(encoding="utf-8")) or {}
        except (json.JSONDecodeError, ValueError):
            asset = {}
    if plan_path.exists():
        try:
            plan_payload = json.loads(plan_path.read_text(encoding="utf-8")) or {}
        except (json.JSONDecodeError, ValueError):
            plan_payload = {}
        if isinstance(plan_payload, dict) and plan_payload:
            if not asset:
                asset = {
                    "asset_id": normalized_case_id,
                    "page": str(plan_payload.get("page", "")).strip(),
                    "priority": str(plan_payload.get("priority", "P1")).strip() or "P1",
                    "source_type": str(plan_payload.get("source_type", "generate_chain")).strip() or "generate_chain",
                }
            plan_points = plan_payload.get("points", []) if isinstance(plan_payload.get("points"), list) else []
            # Canonical source of truth: the standalone plan file always wins over
            # the embedded asset copy. The root asset is a derived container only.
            asset["plan"] = plan_payload
            asset["plan_path"] = str(plan_path.resolve())
            if str(plan_payload.get("page", "")).strip():
                asset["page"] = str(plan_payload.get("page", "")).strip()
            if str(plan_payload.get("priority", "")).strip():
                asset["priority"] = str(plan_payload.get("priority", "")).strip()
            if str(plan_payload.get("source_type", "")).strip():
                asset["source_type"] = str(plan_payload.get("source_type", "")).strip()
            asset["point_count"] = int(plan_payload.get("point_count", len(plan_points)) or len(plan_points))
            asset["review_summary"] = plan_payload.get("review_summary", {}) if isinstance(plan_payload.get("review_summary"), dict) else {}
            asset["coverage"] = plan_payload.get("coverage", {}) if isinstance(plan_payload.get("coverage"), dict) else {}
            asset["involved_elements"] = plan_payload.get("involved_elements", []) if isinstance(plan_payload.get("involved_elements"), list) else []
            asset["confidence"] = max(0.0, min(1.0, float(plan_payload.get("confidence", 0) or 0)))
            asset["requires_review"] = bool(plan_payload.get("requires_review", False))
    if isinstance(asset, dict):
        if str(asset.get("asset_id", "")).strip():
            asset["asset_id"] = _svc()._safe_case_id(str(asset.get("asset_id", "")).strip())
        fallback_id = str(asset.get("asset_id", normalized_case_id)).strip() or normalized_case_id
        source_type = str(asset.get("source_type", "unknown")).strip() or "unknown"
        asset["title"] = _svc()._derive_asset_title(asset, fallback_id=fallback_id)
        asset["source_label"] = _svc().source_type_label(source_type)
        asset["intent_count"] = _svc()._derive_intent_count(asset)
        asset["requirement"] = _svc()._derive_requirement_list(asset)
        return asset
    return {}


