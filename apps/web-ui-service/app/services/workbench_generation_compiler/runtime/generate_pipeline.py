from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable, Protocol
import yaml

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.page_object import PageElement, PageObject

from ..debug import debug_enabled, log_debug_event
from shared_backend.observability import summarize_http_context
from shared_backend.execution_compiler import ExecutionCompilerError, compile_execution_steps
from shared_backend.page_object_assets import merge_page_object_with_yaml
from shared_backend.schemas.contracts import normalize_test_point_plan_v1
from shared_backend.schemas.validator import ContractValidator

_YAML_PAGE_OBJECT_ROOT = Path(__file__).resolve().parents[6] / "assets" / "page-objects" / "web"


class RunOrchestratorGenerate(Protocol):
    def __call__(self, requirement: str, *, page: str, **kwargs: Any) -> dict[str, Any]: ...


class ExtractQualityGate(Protocol):
    def __call__(self, result: dict[str, Any] | None) -> dict[str, Any] | None: ...


class WriteCaseYaml(Protocol):
    def __call__(self, case_id: str, data: dict[str, Any], **kwargs: Any) -> str: ...


class AllocateCaseId(Protocol):
    def __call__(self, prefix: str, **kwargs: Any) -> str: ...


SafeCaseId = Callable[[str], str]
InferTargets = Callable[[str], tuple[str, str]]
SaveCaseState = Callable[[str, dict[str, Any], Any], dict[str, Any]]
AppendHistory = Callable[[dict[str, Any]], None]
NowIso = Callable[[], str]
IsQualityGateBlocked = Callable[[Any], tuple[bool, dict[str, Any] | None]]


_LOGGER = logging.getLogger(__name__)
_COMPILER_ERROR_CODES = {
    "execution_compiler_missing_test_points",
    "execution_compiler_empty_test_points",
    "execution_compiler_invalid_point",
    "execution_compiler_missing_intent_id",
    "execution_compiler_unrecognized_step",
    "execution_compiler_invalid_dsl_action",
    "execution_compiler_intent_coverage_failed",
    "execution_ir_empty_steps",
    "page_object_not_found",
    "page_object_empty_elements",
    "target_binding_failed",
    "execution_render_failed",
}


def _log_generation_failure(
    *,
    level: int,
    stage: str,
    trace_id: str,
    error: Any,
    payload: Any = None,
    extra: dict[str, Any] | None = None,
) -> None:
    message = summarize_http_context(
        method="POST",
        path="workbench_generation_pipeline",
        request_id=trace_id,
        status_code=None,
        payload=payload,
        error=error,
    )
    if isinstance(extra, dict) and extra:
        message = f"{message} {summarize_http_context(method='POST', path=stage, payload=extra)}"
    _LOGGER.log(level, "runtime.generate.failed %s", message)


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fa5]+", "", _normalized_text(value).lower())


def _looks_like_generic_recorded_name(value: str) -> bool:
    return bool(re.fullmatch(r"录制元素\d+", _normalized_text(value)))


def _looks_like_password_toggle_element(
    *,
    page: str,
    element_code: str,
    element_name: str,
    locator_value: str,
    role: str,
) -> bool:
    normalized_page = _normalized_text(page).lower()
    if normalized_page != "login":
        return False

    code_key = _normalized_key(element_code)
    blob = f"{element_code} {element_name} {locator_value} {role}"
    blob_key = _normalized_key(blob)
    lowered_blob = blob.lower()
    if (
        "密码显隐" in lowered_blob
        or "显示密码" in lowered_blob
        or "隐藏密码" in lowered_blob
        or "明文" in lowered_blob
        or "密文" in lowered_blob
        or "ipath3" in code_key
        or "passwordvisibility" in blob_key
        or "showpassword" in blob_key
        or "hidepassword" in blob_key
        or "visibilitytoggle" in blob_key
        or "eyetoggle" in blob_key
    ):
        return True
    return False


def _infer_element_aliases(
    *,
    page: str,
    element_code: str,
    element_name: str,
    locator_value: str,
    role: str,
    business_type: str = "",
    aliases: list[str] | None = None,
) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()

    for raw in aliases or []:
        value = _normalized_text(raw)
        key = _normalized_key(value)
        if not value or not key or key in seen:
            continue
        seen.add(key)
        deduped.append(value)

    locator_text = _normalized_text(locator_value)
    role_text = _normalized_text(role).lower()
    if locator_text:
        for raw in [locator_text, _normalized_text(element_name)]:
            key = _normalized_key(raw)
            if key and key not in seen:
                seen.add(key)
                deduped.append(raw)
        role_suffix = ""
        if role_text == "button":
            role_suffix = "按钮"
        elif role_text in {"textbox", "searchbox", "combobox", "spinbutton"}:
            role_suffix = "输入框"
        elif role_text == "link":
            role_suffix = "链接"
        elif role_text == "menuitem":
            role_suffix = "菜单项"
        elif role_text == "checkbox":
            role_suffix = "复选框"
        elif role_text == "radio":
            role_suffix = "单选框"
        elif role_text == "switch":
            role_suffix = "开关"
        if role_suffix:
            for raw in [f"{locator_text}{role_suffix}", f"{role_suffix}{locator_text}"]:
                key = _normalized_key(raw)
                if key and key not in seen:
                    seen.add(key)
                    deduped.append(raw)

    if _looks_like_password_toggle_element(
        page=page,
        element_code=element_code,
        element_name=element_name,
        locator_value=locator_value,
        role=role,
    ) or _normalized_text(business_type).lower() == "password_toggle":
        for raw in [
            "密码显隐",
            "密码明文切换",
            "密码可见性切换",
            "密码隐藏",
            "密码明文显示",
            "password_visibility_toggle",
            "show_hide_password",
            "eye_toggle",
        ]:
            key = _normalized_key(raw)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(raw)
    return deduped


def _normalize_json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_normalized_text(item) for item in value if _normalized_text(item)]
    if isinstance(value, str):
        text = _normalized_text(value)
        return [text] if text else []
    return []


def _is_qualified_formal_element(element: PageElement) -> bool:
    status = _normalized_text(getattr(element, "status", "")).lower() or "active"
    review_status = _normalized_text(getattr(element, "review_status", "")).lower()
    stability_level = _normalized_text(getattr(element, "stability_level", "")).lower()
    if status != "active":
        return False
    if review_status != "approved":
        return False
    return stability_level in {"high", "medium"}


def _element_display_name(
    *,
    page: str,
    element_code: str,
    element_name: str,
    locator_value: str,
    role: str,
) -> str:
    normalized_name = _normalized_text(element_name)
    normalized_locator = _normalized_text(locator_value)
    normalized_role = _normalized_text(role).lower()

    if _looks_like_password_toggle_element(
        page=page,
        element_code=element_code,
        element_name=element_name,
        locator_value=locator_value,
        role=role,
    ) and (not normalized_name or _looks_like_generic_recorded_name(normalized_name)):
        return "密码显隐开关"

    if normalized_name and not _looks_like_generic_recorded_name(normalized_name):
        return normalized_name

    if normalized_locator:
        if normalized_role == "button":
            return normalized_locator if normalized_locator.endswith("按钮") else f"{normalized_locator}按钮"
        if normalized_role in {"textbox", "searchbox", "combobox", "spinbutton"}:
            return normalized_locator if normalized_locator.endswith("输入框") else f"{normalized_locator}输入框"
        if normalized_role == "link":
            return normalized_locator if normalized_locator.endswith("链接") else f"{normalized_locator}链接"
        return normalized_locator

    if normalized_role == "button":
        return "按钮"
    if normalized_role in {"textbox", "searchbox", "combobox", "spinbutton"}:
        return "输入框"
    return normalized_name


def _is_precondition_point(point: dict[str, Any]) -> bool:
    point_type = _normalized_text(point.get("point_type")).lower()
    action = _normalized_text(point.get("action")).lower()
    return point_type == "precondition" or action == "login"


def _extract_selected_intent_ids(*, payload: Any, selected_candidate: dict[str, Any] | None) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()

    def _add(value: Any) -> None:
        normalized = _normalized_text(value)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        deduped.append(normalized)

    selected_ids_raw = getattr(payload, "selected_intent_ids", None)
    if isinstance(selected_ids_raw, list):
        for item in selected_ids_raw:
            _add(item)

    if not deduped and isinstance(selected_candidate, dict):
        _add(selected_candidate.get("intent_id"))

    if not deduped:
        selected_candidates_raw = getattr(payload, "selected_candidates", None)
        if isinstance(selected_candidates_raw, list):
            for item in selected_candidates_raw:
                if not isinstance(item, dict):
                    continue
                _add(item.get("intent_id"))

    return deduped


def _filter_requirement_spec_by_selected_intents(requirement_spec: dict[str, Any], selected_intent_ids: set[str]) -> dict[str, Any]:
    if not isinstance(requirement_spec, dict) or not selected_intent_ids:
        return requirement_spec if isinstance(requirement_spec, dict) else {}

    filtered_spec = dict(requirement_spec)
    intents = filtered_spec.get("test_intents")
    if isinstance(intents, list):
        filtered_spec["test_intents"] = [
            item
            for item in intents
            if isinstance(item, dict) and _normalized_text(item.get("intent_id")) in selected_intent_ids
        ]

    coverage_matrix = filtered_spec.get("coverage_matrix")
    if isinstance(coverage_matrix, list):
        filtered_rows: list[dict[str, Any]] = []
        for row in coverage_matrix:
            if not isinstance(row, dict):
                continue
            raw_intent_ids = row.get("intent_ids")
            if not isinstance(raw_intent_ids, list):
                continue
            scoped_intent_ids = [
                _normalized_text(item)
                for item in raw_intent_ids
                if _normalized_text(item) in selected_intent_ids
            ]
            if not scoped_intent_ids:
                continue
            row_copy = dict(row)
            row_copy["intent_ids"] = scoped_intent_ids
            filtered_rows.append(row_copy)
        filtered_spec["coverage_matrix"] = filtered_rows

    return filtered_spec


def _scope_points_to_selected_intents(
    points: list[dict[str, Any]],
    selected_intent_ids: set[str],
) -> tuple[list[dict[str, Any]], set[str], list[str]]:
    if not selected_intent_ids:
        return points, set(), []

    scoped_points: list[dict[str, Any]] = []
    resolved_intent_ids: set[str] = set()
    for point in points:
        if not isinstance(point, dict):
            continue
        intent_id = _normalized_text(point.get("intent_id"))
        if _is_precondition_point(point):
            scoped_points.append(point)
            continue
        if intent_id and intent_id in selected_intent_ids:
            scoped_points.append(point)
            resolved_intent_ids.add(intent_id)
    missing_intent_ids = sorted(selected_intent_ids - resolved_intent_ids)
    return scoped_points, resolved_intent_ids, missing_intent_ids


def _list_text(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for raw in value:
        text = _normalized_text(raw)
        if text:
            rows.append(text)
    return rows


def _candidate_steps(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for raw in value:
        if isinstance(raw, str):
            text = _normalized_text(raw)
        elif isinstance(raw, dict):
            text = _normalized_text(raw.get("raw_text") or raw.get("value") or raw.get("description") or raw.get("action"))
        else:
            text = ""
        if text:
            rows.append(text)
    return rows


def _normalize_candidate_snapshot(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "intent_id": _normalized_text(candidate.get("intent_id")),
        "title": _normalized_text(candidate.get("title")),
        "summary": _normalized_text(candidate.get("summary")) or _normalized_text(candidate.get("title")),
        "intent_type": _normalized_text(candidate.get("intent_type")) or "functional",
        "priority": _normalized_text(candidate.get("priority")) or "P1",
        "precondition": _normalized_text(candidate.get("precondition")),
        "steps": _candidate_steps(candidate.get("steps")),
        "steps_hint": _list_text(candidate.get("steps_hint")),
        "expected": _normalized_text(candidate.get("expected") or candidate.get("expected_result")),
        "involved_elements": _list_text(candidate.get("involved_elements")),
    }
    if not normalized["intent_id"]:
        normalized["intent_id"] = _normalized_text(candidate.get("key"))
    return normalized


def _extract_candidate_snapshots(*, payload: Any, selected_candidate: dict[str, Any] | None) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _append(raw: Any) -> None:
        if not isinstance(raw, dict):
            return
        normalized = _normalize_candidate_snapshot(raw)
        intent_id = _normalized_text(normalized.get("intent_id"))
        title = _normalized_text(normalized.get("title"))
        identity = intent_id or f"title:{title}"
        if not identity:
            return
        if identity in seen:
            return
        seen.add(identity)
        snapshots.append(normalized)

    selected_candidates_raw = getattr(payload, "selected_candidates", None)
    if isinstance(selected_candidates_raw, list):
        for item in selected_candidates_raw:
            _append(item)
    if isinstance(selected_candidate, dict):
        _append(selected_candidate)
    return snapshots


def _enrich_test_points_with_candidate_snapshots(
    *,
    points: list[dict[str, Any]],
    candidate_snapshots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not points or not candidate_snapshots:
        return points
    by_intent_id: dict[str, dict[str, Any]] = {}
    for candidate in candidate_snapshots:
        intent_id = _normalized_text(candidate.get("intent_id"))
        if intent_id:
            by_intent_id[intent_id] = candidate
    if not by_intent_id:
        return points

    enriched: list[dict[str, Any]] = []
    for raw_point in points:
        if not isinstance(raw_point, dict):
            continue
        point = dict(raw_point)
        intent_id = _normalized_text(point.get("intent_id"))
        candidate = by_intent_id.get(intent_id)
        if not candidate:
            enriched.append(point)
            continue
        point["point_type"] = _normalized_text(candidate.get("intent_type")) or _normalized_text(point.get("point_type")) or "functional"
        point["description"] = _normalized_text(candidate.get("summary")) or _normalized_text(candidate.get("title")) or _normalized_text(point.get("description"))
        point["precondition"] = _normalized_text(candidate.get("precondition")) or _normalized_text(point.get("precondition"))
        point["expected_result"] = _normalized_text(candidate.get("expected")) or _normalized_text(point.get("expected_result"))
        point["priority"] = _normalized_text(candidate.get("priority")) or _normalized_text(point.get("priority")) or "P1"
        candidate_elements = _list_text(candidate.get("involved_elements"))
        if candidate_elements:
            point["involved_elements"] = candidate_elements
        candidate_steps = _list_text(candidate.get("steps"))
        if candidate_steps:
            point["steps"] = [
                {
                    "action": "candidate_step",
                    "target": "",
                    "value": row,
                    "raw_text": row,
                }
                for row in candidate_steps
            ]
        candidate_steps_hint = _list_text(candidate.get("steps_hint"))
        if candidate_steps_hint:
            point["steps_hint"] = candidate_steps_hint
        point_metadata = point.get("metadata") if isinstance(point.get("metadata"), dict) else {}
        point["metadata"] = {
            **point_metadata,
            "candidate_snapshot": candidate,
        }
        enriched.append(point)
    return enriched


def _resolve_page_object_from_db(project: str, page: str) -> dict[str, Any] | None:
    """Attempt to load page object elements from the database. Returns None on miss."""
    try:
        with SessionLocal() as db:
            page_object = db.execute(
                select(PageObject).where(
                    PageObject.project_code == project,
                    PageObject.client == "web",
                    PageObject.page_code == page,
                )
            ).scalar_one_or_none()
            if page_object is None:
                return None
            elements = (
                db.execute(
                    select(PageElement)
                    .where(PageElement.page_object_id == int(page_object.id))
                    .order_by(PageElement.id.asc())
                )
                .scalars()
                .all()
            )
    except ExecutionCompilerError:
        raise
    except Exception as exc:
        _LOGGER.debug("DB page-object lookup failed for %s/%s", project, page, exc_info=True)
        raise ExecutionCompilerError(
            code="page_object_db_lookup_failed",
            message="page object DB lookup failed",
            reason=f"{project}/web/{page}: {type(exc).__name__}",
            stage="resolve_page_object",
        ) from exc
    if not elements:
        raise ExecutionCompilerError(
            code="page_object_empty_elements",
            message="page object has no formal elements",
            reason=f"{project}/web/{page} has no page_elements rows",
            stage="resolve_page_object",
        )
    mapping: dict[str, dict[str, Any]] = {}
    for element in elements:
        if not _is_qualified_formal_element(element):
            continue
        code = _normalized_text(getattr(element, "element_code", ""))
        selector = _normalized_text(getattr(element, "locator_value", ""))
        if not code or not selector:
            continue
        role = _normalized_text(getattr(element, "role", ""))
        element_name = _normalized_text(getattr(element, "element_name", ""))
        business_type = _normalized_text(getattr(element, "business_type", "")).lower()
        aliases_json = _normalize_json_list(getattr(element, "aliases_json", []))
        semantic_tags_json = _normalize_json_list(getattr(element, "semantic_tags_json", []))
        aliases = _infer_element_aliases(
            page=page,
            element_code=code,
            element_name=element_name,
            locator_value=selector,
            role=role,
            business_type=business_type,
            aliases=aliases_json,
        )
        mapping[code] = {
            "selector": selector,
            "type": _normalized_text(getattr(element, "locator_type", "")) or "css",
            "role": role,
            "name": _element_display_name(
                page=page,
                element_code=code,
                element_name=element_name,
                locator_value=selector,
                role=role,
            ),
            "aliases": aliases,
            "business_type": business_type,
            "business_domain": _normalized_text(getattr(element, "business_domain", "")).lower(),
            "semantic_tags": semantic_tags_json,
            "review_status": _normalized_text(getattr(element, "review_status", "")).lower(),
            "stability_level": _normalized_text(getattr(element, "stability_level", "")).lower(),
            "status": _normalized_text(getattr(element, "status", "")).lower() or "active",
        }
    if not mapping:
        raise ExecutionCompilerError(
            code="page_object_empty_elements",
            message="page object has no qualified elements for test point mapping",
            reason=(
                f"{project}/web/{page} has {len(elements)} formal element(s), "
                "but none match status=active + review_status=approved + stability_level in high/medium"
            ),
            stage="resolve_page_object",
        )
    # Governance path must not reintroduce legacy YAML-only elements once a DB
    # page object exists. YAML fallback is only for pages not yet modeled in DB.
    return {"page": page, "elements": mapping}


def _resolve_page_object_from_assets(page: str) -> dict[str, Any] | None:
    asset_path = _YAML_PAGE_OBJECT_ROOT / f"{page}.page-object.yaml"
    if not asset_path.exists():
        return None
    try:
        raw = yaml.safe_load(asset_path.read_text(encoding="utf-8")) or {}
    except Exception:
        _LOGGER.debug("asset page-object lookup failed for %s", page, exc_info=True)
        return None
    if not isinstance(raw, dict):
        return None
    elements_raw = raw.get("elements")
    if not isinstance(elements_raw, dict):
        return None
    mapping: dict[str, dict[str, Any]] = {}
    for code, item in elements_raw.items():
        element_code = _normalized_text(code)
        if not element_code:
            continue
        selector = ""
        locator_type = "css"
        role = ""
        if isinstance(item, dict):
            selector = _normalized_text(item.get("locator_value") or item.get("selector"))
            locator_type = _normalized_text(item.get("locator_type")) or "css"
            role = _normalized_text(item.get("role"))
            name = _normalized_text(item.get("element_name") or item.get("name"))
            aliases_raw = item.get("aliases")
        elif isinstance(item, str):
            selector = _normalized_text(item)
            name = ""
            aliases_raw = []
        if not selector:
            continue
        aliases: list[str] = []
        if isinstance(aliases_raw, list):
            aliases = [_normalized_text(value) for value in aliases_raw if _normalized_text(value)]
        elif isinstance(aliases_raw, str):
            alias_value = _normalized_text(aliases_raw)
            if alias_value:
                aliases = [alias_value]
        aliases = _infer_element_aliases(
            page=page,
            element_code=element_code,
            element_name=name,
            locator_value=selector,
            role=role,
            aliases=aliases,
        )
        name = _element_display_name(
            page=page,
            element_code=element_code,
            element_name=name,
            locator_value=selector,
            role=role,
        )
        mapping[element_code] = {
            "selector": selector,
            "type": locator_type,
            "role": role,
            "name": name,
            "aliases": aliases,
        }
    return {"page": page, "elements": mapping} if mapping else None


def resolve_page_object(project: str, page: str, *, strict_governance: bool = True) -> dict[str, Any]:
    normalized_project = _normalized_text(project)
    normalized_page = _normalized_text(page).lower()
    if not normalized_project or not normalized_page:
        raise ExecutionCompilerError(
            code="page_object_not_found",
            message="page object identity is required",
            reason="project/page is empty",
            stage="resolve_page_object",
        )

    db_result = _resolve_page_object_from_db(normalized_project, normalized_page)
    if db_result is not None:
        return db_result

    if strict_governance:
        raise ExecutionCompilerError(
            code="page_object_not_governed",
            message="page object is not governed for test point mapping",
            reason=(
                f"{normalized_project}/web/{normalized_page} has no governed DB page object; "
                "YAML fallback is disabled for new test point mapping"
            ),
            stage="resolve_page_object",
        )

    asset_result = _resolve_page_object_from_assets(normalized_page)
    if asset_result is not None:
        return asset_result

    raise ExecutionCompilerError(
        code="page_object_not_found",
        message="page object not found in DB",
        reason=f"{normalized_project}/web/{normalized_page}",
        stage="resolve_page_object",
    )


def run_generate_pipeline(
    *,
    payload: Any,
    normalized_page: str,
    effective_requirement: str,
    multisource_enabled: bool,
    input_sources: list[dict[str, Any]],
    openapi_spec: dict[str, Any],
    run_orchestrator_generate: RunOrchestratorGenerate,
    extract_quality_gate: ExtractQualityGate,
    safe_case_id: SafeCaseId,
    infer_targets: InferTargets,
    write_case_yaml: WriteCaseYaml,
    save_case_state: SaveCaseState,
    save_test_point_plan: Callable[..., Any] | None,
    append_history: AppendHistory,
    now_iso: NowIso,
    is_quality_gate_blocked: IsQualityGateBlocked,
    ai_cases_root: Any,
    utc: Any,
    datetime_module: Any,
    http_exception_cls: Any,
    bad_gateway_status: int,
    unprocessable_entity_status: int,
    existing_case_ids: list[str] | None = None,
    selected_candidate: dict[str, Any] | None = None,
    allocate_case_id: AllocateCaseId,
    trace_id: str = "",
    mode: str = "generate",
) -> dict[str, Any]:
    _ = safe_case_id, infer_targets, utc, datetime_module
    log_debug_event(
        logger=_LOGGER,
        event="runtime.generate.input",
        trace_id=trace_id,
        payload={
            "project": str(getattr(payload, "project", "") or ""),
            "page": normalized_page,
            "requirement": effective_requirement,
            "multisource_enabled": multisource_enabled,
            "input_sources": input_sources,
            "openapi_spec": openapi_spec,
            "existing_case_ids": existing_case_ids or [],
            "selected_candidate": selected_candidate if isinstance(selected_candidate, dict) else {},
        },
        extra={"compare_with_event": "service.generate.input"},
    )
    orchestrator_result: dict[str, Any] = {}
    case_yaml: dict[str, Any] = {}
    resolved_page = normalized_page
    quality_gate: dict[str, Any] | None = None
    selected_intent_ids_list = _extract_selected_intent_ids(payload=payload, selected_candidate=selected_candidate)
    selected_intent_ids = set(selected_intent_ids_list)
    candidate_snapshots = _extract_candidate_snapshots(payload=payload, selected_candidate=selected_candidate)
    try:
        orchestrator_result = run_orchestrator_generate(
            requirement=effective_requirement,
            page=normalized_page,
            source=payload.source,
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            prd_text=payload.prd_text,
            prd_url=payload.prd_url,
            user_story=payload.user_story,
            git_diff=payload.git_diff,
            git_diff_path=payload.git_diff_path,
            openapi_url=payload.openapi_url,
            defect_ticket=payload.defect_ticket,
            runtime_logs=payload.runtime_logs,
        )
        quality_gate = extract_quality_gate(orchestrator_result.get("requirement_spec"))
        generated_case = orchestrator_result.get("case") or {}
        if not isinstance(generated_case, dict) or not generated_case:
            raise http_exception_cls(status_code=bad_gateway_status, detail="orchestrator returned invalid case payload")
        case_yaml = generated_case
        execution_payload = case_yaml.get("execution")
        if not isinstance(execution_payload, dict):
            execution_payload = {}
            case_yaml["execution"] = execution_payload
        resolved_page = (
            str(execution_payload.get("page", "")).strip()
            or str(orchestrator_result.get("requirement_spec", {}).get("page", "")).strip()
            or normalized_page
            or "product"
        )
        execution_payload["page"] = resolved_page
        case_yaml["module"] = str(case_yaml.get("module", "")).strip() or resolved_page
        case_yaml["description"] = (
            str(case_yaml.get("description", "")).strip()
            or f"AI generated from requirement: {effective_requirement or 'multi-source'}"
        )
        test_points_payload = orchestrator_result.get("test_points")
        if not isinstance(test_points_payload, dict):
            test_points_payload = {}
            orchestrator_result["test_points"] = test_points_payload
        test_points = test_points_payload.get("points")
        if not isinstance(test_points, list) or not test_points:
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail={
                    "code": "execution_compiler_missing_test_points",
                    "message": "orchestrator returned no test points",
                    "reason": "test_points.points is empty",
                    "stage": "run_generate_pipeline",
                },
            )
        try:
            plan_wrapper = {
                "version": "TestPointPlanV1",
                "project": str(getattr(payload, "project", "mall") or "mall"),
                "case_id": str(getattr(payload, "case_id", "") or ""),
                "page": resolved_page,
                "points": test_points,
            }
            normalized_plan, _contract_warnings = normalize_test_point_plan_v1(plan_wrapper)
            test_points = normalized_plan.get("points", test_points)
        except Exception:
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail={
                    "code": "execution_compiler_contract_normalization_failed",
                    "message": "test point normalization failed",
                    "reason": "normalize_test_point_plan_v1 raised an exception",
                    "stage": "run_generate_pipeline",
                },
            )

        requirement_spec: dict[str, Any] | None = (
            orchestrator_result.get("requirement_spec")
            if isinstance(orchestrator_result.get("requirement_spec"), dict)
            else None
        )
        if selected_intent_ids:
            scoped_points, resolved_selected_intent_ids, missing_selected_intent_ids = _scope_points_to_selected_intents(
                test_points if isinstance(test_points, list) else [],
                selected_intent_ids,
            )
            if missing_selected_intent_ids:
                raise http_exception_cls(
                    status_code=unprocessable_entity_status,
                    detail={
                        "code": "execution_compiler_intent_coverage_failed",
                        "message": "selected intents are missing in normalized test points",
                        "reason": "selected_intent_ids were not fully materialized into test_points.points",
                        "stage": "run_generate_pipeline",
                        "selected_intent_ids": sorted(selected_intent_ids),
                        "resolved_intent_ids": sorted(resolved_selected_intent_ids),
                        "missing_intent_ids": missing_selected_intent_ids,
                    },
                )
            test_points = scoped_points
            requirement_spec = _filter_requirement_spec_by_selected_intents(requirement_spec or {}, selected_intent_ids)
            orchestrator_result["requirement_spec"] = requirement_spec
            test_points_payload["points"] = test_points
        test_points = _enrich_test_points_with_candidate_snapshots(
            points=test_points if isinstance(test_points, list) else [],
            candidate_snapshots=candidate_snapshots,
        )
        test_points_payload["points"] = test_points

        try:
            page_object = resolve_page_object(str(payload.project or ""), resolved_page)
        except ExecutionCompilerError as page_object_exc:
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail=page_object_exc.to_detail(),
            ) from page_object_exc

        validator = ContractValidator()
        validation_result = validator.validate_full(
            requirement_spec if isinstance(requirement_spec, dict) else None,
            test_points if isinstance(test_points, list) else [],
            page_object,
            strict=True,
        )
        if not validation_result.valid:
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail={
                    "code": "test_point_contract_validation_failed",
                    "message": "test point contract validation failed",
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                    "stage": "run_generate_pipeline",
                },
            )

        compiled_steps = compile_execution_steps(test_points, page_object)
        if selected_intent_ids:
            compiled_intent_ids = {
                _normalized_text(step.get("intent_id"))
                for step in compiled_steps
                if isinstance(step, dict)
                and _normalized_text(step.get("intent_id"))
                and _normalized_text(step.get("action")).lower() != "login"
            }
            missing_intent_ids = sorted(selected_intent_ids - compiled_intent_ids)
            unexpected_intent_ids = sorted(compiled_intent_ids - selected_intent_ids)
            if missing_intent_ids or unexpected_intent_ids:
                raise http_exception_cls(
                    status_code=unprocessable_entity_status,
                    detail={
                        "code": "execution_compiler_intent_coverage_failed",
                        "message": "compiled steps do not strictly match selected intents",
                        "reason": "selected intent ids and compiled intent ids are inconsistent",
                        "stage": "run_generate_pipeline",
                        "selected_intent_ids": sorted(selected_intent_ids),
                        "compiled_intent_ids": sorted(compiled_intent_ids),
                        "missing_intent_ids": missing_intent_ids,
                        "unexpected_intent_ids": unexpected_intent_ids,
                    },
                )
        execution_payload["steps"] = compiled_steps
        if selected_intent_ids_list:
            execution_payload["selected_intent_ids"] = selected_intent_ids_list
        orchestrator_result["execution_requested"] = True
        review_summary = test_points_payload.get("review_summary")
        if isinstance(review_summary, dict):
            review_summary["intent_coverage_status"] = "covered"
            review_summary["status"] = "covered"
            review_summary["orphan_point_count"] = 0
            review_summary["orphan_step_count"] = 0
        log_debug_event(
            logger=_LOGGER,
            event="runtime.generate.orchestrator_output",
            trace_id=trace_id,
            payload=orchestrator_result,
        )
    except Exception as exc:
        if isinstance(exc, ExecutionCompilerError):
            _log_generation_failure(
                level=logging.WARNING,
                stage="execution_compiler",
                trace_id=trace_id,
                error=exc.to_detail(),
                payload={
                    "selected_intent_ids": selected_intent_ids_list,
                    "mode": mode,
                },
            )
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail=exc.to_detail(),
            ) from exc
        if isinstance(exc, http_exception_cls):
            is_gate_blocked, blocked_gate = is_quality_gate_blocked(getattr(exc, "detail", ""))
            if is_gate_blocked and isinstance(blocked_gate, dict):
                _log_generation_failure(
                    level=logging.WARNING,
                    stage="quality_gate",
                    trace_id=trace_id,
                    error=getattr(exc, "detail", ""),
                    payload={
                        "selected_intent_ids": selected_intent_ids_list,
                        "mode": mode,
                    },
                    extra={"blocked_gate": blocked_gate},
                )
                append_history(
                    {
                        "timestamp": now_iso(),
                        "action": "generate_case_blocked_by_quality_gate",
                        "case_id": payload.case_id.strip(),
                        "page": normalized_page,
                        "source": payload.source,
                        "multi_source_enabled": multisource_enabled,
                        "quality_gate": blocked_gate,
                        "orchestrator_error_reason": getattr(exc, "detail", ""),
                    }
                )
                raise http_exception_cls(
                    status_code=getattr(exc, "status_code", unprocessable_entity_status)
                    if isinstance(getattr(exc, "status_code", None), int)
                    else unprocessable_entity_status,
                    detail={
                        "code": "requirement_quality_gate_blocked",
                        "message": "requirement quality gate blocked orchestration",
                        "quality_gate": blocked_gate,
                        "upstream_error": getattr(exc, "detail", ""),
                    },
                ) from exc
            upstream_status_code = getattr(exc, "status_code", None)
            upstream_detail = getattr(exc, "detail", "")
            detail_payload = upstream_detail if isinstance(upstream_detail, dict) else {}
            detail_code = str(detail_payload.get("code", "")).strip().lower()
            detail_reason_code = str(detail_payload.get("reason_code", "")).strip().lower()
            if (
                isinstance(upstream_status_code, int)
                and upstream_status_code == unprocessable_entity_status
                and detail_code in _COMPILER_ERROR_CODES
            ):
                _log_generation_failure(
                    level=logging.WARNING,
                    stage="compiler_upstream",
                    trace_id=trace_id,
                    error=detail_payload or upstream_detail,
                    payload={
                        "selected_intent_ids": selected_intent_ids_list,
                        "mode": mode,
                        "upstream_status_code": upstream_status_code,
                    },
                )
                raise http_exception_cls(
                    status_code=unprocessable_entity_status,
                    detail=detail_payload or {
                        "code": "execution_compiler_failed",
                        "message": "execution compiler failed",
                        "reason": str(upstream_detail)[:500],
                        "stage": "run_generate_pipeline",
                    },
                ) from exc
            if (
                isinstance(upstream_status_code, int)
                and upstream_status_code == unprocessable_entity_status
                and (
                    detail_code == "validation_error"
                    or detail_reason_code == "test_design_invalid_output"
                )
            ):
                _log_generation_failure(
                    level=logging.WARNING,
                    stage="validation_upstream",
                    trace_id=trace_id,
                    error=detail_payload or upstream_detail,
                    payload={
                        "selected_intent_ids": selected_intent_ids_list,
                        "mode": mode,
                        "upstream_status_code": upstream_status_code,
                    },
                )
                raise http_exception_cls(
                    status_code=unprocessable_entity_status,
                    detail=detail_payload or {
                        "code": "validation_error",
                        "message": str(upstream_detail)[:500],
                    },
                ) from exc
            _log_generation_failure(
                level=logging.ERROR,
                stage="orchestrator_generate_failed",
                trace_id=trace_id,
                error=upstream_detail,
                payload={
                    "selected_intent_ids": selected_intent_ids_list,
                    "mode": mode,
                    "upstream_status_code": upstream_status_code,
                    "detail_code": detail_code,
                    "detail_reason_code": detail_reason_code,
                },
            )
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail={
                    "code": "orchestrator_generate_failed",
                    "message": "orchestrator generate failed",
                    "upstream_error": str(upstream_detail)[:500],
                },
            ) from exc
        else:
            upstream_error = str(exc)
            _log_generation_failure(
                level=logging.ERROR,
                stage="unexpected_exception",
                trace_id=trace_id,
                error=upstream_error[:500],
                payload={
                    "selected_intent_ids": selected_intent_ids_list,
                    "mode": mode,
                    "is_http_exception": False,
                },
            )
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail={
                    "code": "orchestrator_generate_failed",
                    "message": "orchestrator generate failed",
                    "upstream_error": upstream_error[:500],
                },
            ) from exc

    case_id = allocate_case_id(
        requested_case_id=payload.case_id or case_yaml.get("id", ""),
        project=payload.project,
        page=resolved_page or normalized_page or "product",
        module=str(case_yaml.get("module", "")).strip() or resolved_page or normalized_page or "product",
        ai_cases_root=ai_cases_root,
        existing_case_ids=existing_case_ids,
    )
    case_yaml["id"] = case_id
    if payload.title.strip():
        case_yaml["title"] = payload.title.strip()
    if payload.priority.strip():
        case_yaml["priority"] = payload.priority.strip()
    cleaned_tags = [item.strip() for item in payload.tags if item.strip()]
    case_yaml["tags"] = cleaned_tags or [item.strip() for item in case_yaml.get("tags", []) if str(item).strip()] or ["ai-generated"]
    execution_payload = case_yaml.get("execution")
    if not isinstance(execution_payload, dict):
        execution_payload = {}
        case_yaml["execution"] = execution_payload
    execution_payload["page"] = resolved_page or "product"
    case_yaml["module"] = str(case_yaml.get("module", "")).strip() or execution_payload["page"]

    case_path = ai_cases_root / f"{case_id}.yaml"
    final_text = write_case_yaml(case_path, case_yaml)
    state_entry = save_case_state(payload.project, case_yaml, case_path)
    test_point_path = None
    if callable(save_test_point_plan):
        test_point_path = save_test_point_plan(
            project=payload.project,
            case_id=case_id,
            page=resolved_page,
            page_url=str(getattr(payload, "page_url", "") or ""),
            requirement=effective_requirement,
            plan={
                "version": "TestPointPlanV1",
                "project": payload.project,
                "case_id": case_id,
                "page": resolved_page,
                "source_type": "generate_chain",
                "requirement": [effective_requirement],
                "generated_at": now_iso(),
                "points": test_points if isinstance(test_points, list) else [],
                "coverage": {},
                "review_summary": {},
                "metadata": {
                    "origin": "generate_chain",
                    "selected_intent_ids": sorted(selected_intent_ids),
                    "selected_candidates": candidate_snapshots,
                },
            },
        )
    append_history(
        {
            "timestamp": now_iso(),
            "action": "generate_case",
            "case_id": case_id,
            "title": str(case_yaml.get("title", case_id)),
            "path": str(case_path.resolve()),
            "test_points_path": str(test_point_path.resolve()) if isinstance(test_point_path, Path) else "",
            "source": payload.source,
            "multi_source_enabled": multisource_enabled,
            "orchestrator_error_reason": "",
            "quality_gate": quality_gate,
        }
    )
    if debug_enabled():
        append_history(
            {
                "timestamp": now_iso(),
                "action": "workbench_generation_debug_trace",
                "trace_id": trace_id,
                "stage": "runtime.generate",
                "case_id": case_id,
                "page": execution_payload["page"],
            }
        )
    result = {
        "message": "case generated",
        "item": {
            "case_id": case_id,
            "project": payload.project,
            "path": str(case_path.resolve()),
            "test_points_path": str(test_point_path.resolve()) if isinstance(test_point_path, Path) else "",
            "yaml_content": final_text,
            "state": state_entry,
            "page": execution_payload["page"],
            "orchestrator_result": orchestrator_result,
            "orchestrator_error_reason": "",
            "quality_gate": quality_gate,
        },
    }
    log_debug_event(
        logger=_LOGGER,
        event="runtime.generate.output",
        trace_id=trace_id,
        payload=result,
        extra={"compare_with_event": "runtime.generate.orchestrator_output"},
    )
    return result
