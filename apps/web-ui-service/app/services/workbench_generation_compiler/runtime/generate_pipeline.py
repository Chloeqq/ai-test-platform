from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from app.models.page_object import PageElement
from shared_backend.db import get_db_session as SessionLocal
from shared_backend.observability import summarize_http_context
from shared_backend.step_fields import STEP_FIELD_NAMES
from shared_backend.type_utils import str_value as _normalized_text

_YAML_PAGE_OBJECT_ROOT = Path(__file__).resolve().parents[6] / "assets" / "page-objects" / "web"


class RunOrchestratorGenerate(Protocol):
    def __call__(self, requirement: str, *, page: str, **kwargs: Any) -> dict[str, Any]: ...


class ExtractQualityGate(Protocol):
    def __call__(self, result: dict[str, Any] | None) -> dict[str, Any] | None: ...


class WriteCaseYaml(Protocol):
    def __call__(self, case_id: str, data: dict[str, Any], **kwargs: Any) -> str: ...


class AllocateCaseId(Protocol):
    def __call__(self, prefix: str, **kwargs: Any) -> str: ...


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
    "dsl_v1_1_missing_source_identity",
    "dsl_v1_1_invalid_data_source",
    "dsl_v1_1_missing_input_data_source",
    "dsl_v1_1_missing_executable_assertion",
    "dsl_v1_1_page_url_mismatch",
    "dsl_v1_1_selected_intent_count_invalid",
    "page_object_not_found",
    "page_object_empty_elements",
    "target_binding_failed",
    "execution_render_failed",
}

_SUPPORTED_TOP_LEVEL_ASSERTIONS = {"assert_visible", "assert_count", "assert_metric", "assert_text", "assert_url", "assert_attribute"}
# 字段集合来自 shared_backend/step_fields.py（唯一事实源）。
_TOP_LEVEL_ASSERTION_KEYS = STEP_FIELD_NAMES
_VARIABLE_TEMPLATE_RE = re.compile(r"^\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}$")
_DSL_DATA_SOURCE_TYPES = {"inline", "pool", "env"}


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


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fa5]+", "", _normalized_text(value).lower())


def _is_sensitive_key(value: Any) -> bool:
    normalized = _normalized_text(value).lower()
    return any(token in normalized for token in ("password", "passwd", "pwd", "secret", "token", "credential"))


def _redact_generation_payload(value: Any) -> Any:
    """
    生成负载脱敏函数，用于在记录日志、存储快照、返回调试信息之前，自动把敏感数据隐藏掉
    :param value:
    :return:
    """
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = _normalized_text(key)
            if _is_sensitive_key(key_text):
                redacted[key] = "***"
            elif key_text in {"value", "data", "content"}:
                redacted[key] = "***" if item not in (None, "", [], {}) else item
            elif key_text in {"steps", "steps_hint"} and isinstance(item, list):
                redacted[key] = [f"<{len(item)} item(s)>"]
            else:
                redacted[key] = _redact_generation_payload(item)
        return redacted
    if isinstance(value, list):
        return [_redact_generation_payload(item) for item in value]
    return value


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
    semantic_blob = " ".join([element_code, element_name, locator_value, role, business_type]).lower()
    if business_type == "input" and any(token in semantic_blob for token in ["username", "user_name", "account", "账号", "用户名"]):
        for raw in ["账号输入框", "用户名输入框", "用户输入框"]:
            key = _normalized_key(raw)
            if key and key not in seen:
                seen.add(key)
                deduped.append(raw)
    if _is_password_input_element(
        element_code=element_code,
        element_name=element_name,
        locator_value=locator_value,
        role=role,
        business_type=business_type,
    ):
        for raw in ["密码输入框"]:
            key = _normalized_key(raw)
            if key and key not in seen:
                seen.add(key)
                deduped.append(raw)
    if ("login" in semantic_blob or "登录" in semantic_blob) and "logout" not in semantic_blob and "退出" not in semantic_blob:
        if business_type == "button":
            for raw in ["登录按钮"]:
                key = _normalized_key(raw)
                if key and key not in seen:
                    seen.add(key)
                    deduped.append(raw)
    return deduped


def _is_password_input_element(
    *,
    element_code: str,
    element_name: str,
    locator_value: str,
    role: str,
    business_type: str
) -> bool:
    business = _normalized_text(business_type).lower()
    # 第一步：只允许输入框类型，其它（checkbox/radio/button等）直接排除
    if business not in {"input", "text_input", "password", "password_input"}:
        return False

    role_text = _normalized_text(role).lower()
    semantic_parts = [
        _normalized_text(element_code).lower(),
        _normalized_text(element_name).lower(),
        _normalized_text(locator_value).lower(),
        role_text,
        business
    ]
    semantic_blob = " ".join(semantic_parts)

    # 排除“记住密码”这类复选框语义（冗余但作为安全兜底保留）
    if any(token in semantic_blob for token in ["记住密码", "rememberpassword", "rememberme", "checkbox", "复选框"]):
        return False

    has_password_keyword = "password" in semantic_blob or "密码" in semantic_blob
    # 角色检查：标准输入框角色，或 role 为空时只看密码关键词
    is_valid_role = role_text in {"textbox", "password"} or not role_text
    return has_password_keyword and is_valid_role


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
        "involved_element_codes": _list_text(candidate.get("involved_element_codes")),
        "source_asset_id": _normalized_text(candidate.get("source_asset_id") or candidate.get("asset_id")),
        "source_asset_title": _normalized_text(candidate.get("source_asset_title") or candidate.get("asset_title")),
    }
    if not normalized["intent_id"]:
        normalized["intent_id"] = _normalized_text(candidate.get("key"))
    return normalized


def _point_type_from_intent_type(value: Any) -> str:
    normalized = _normalized_text(value).lower()
    if normalized in {"negative", "security", "compatibility", "performance"}:
        return "assertion"
    if normalized == "api":
        return "api"
    return normalized or "action"


def _candidate_identity(candidate: dict[str, Any]) -> tuple[str, str]:
    intent_id = _normalized_text(candidate.get("intent_id") or candidate.get("key")) or "manual-intent"
    title = (
        _normalized_text(candidate.get("title"))
        or _normalized_text(candidate.get("summary"))
        or intent_id
    )
    return intent_id, title


def _direct_candidate_requirement_lines(candidate: dict[str, Any], *, intent_id: str, title: str) -> list[str]:
    lines: list[str] = []
    intent_type = _normalized_text(candidate.get("intent_type")) or "functional"
    precondition = _normalized_text(candidate.get("precondition"))
    expected = _normalized_text(candidate.get("expected") or candidate.get("expected_result"))
    involved_elements = _list_text(candidate.get("involved_elements"))
    if intent_id:
        lines.append(f"测试点ID：{intent_id}")
    if title:
        lines.append(f"测试点标题：{title}")
    if intent_type:
        lines.append(f"测试类型：{intent_type}")
    if precondition:
        lines.append(f"前置条件：{precondition}")
    if expected:
        lines.append(f"预期结果：{expected}")
    if involved_elements:
        lines.append(f"涉及元素：{'、'.join(involved_elements)}")
    return lines or [title or intent_id or "AI生成用例"]


def _find_candidate_snapshot_by_intent(
    *,
    intent_id: str,
    candidate_snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_intent_id = _normalized_text(intent_id)
    if not normalized_intent_id:
        return {}
    for candidate in candidate_snapshots:
        if isinstance(candidate, dict) and _normalized_text(candidate.get("intent_id")) == normalized_intent_id:
            return candidate
    return {}


def _find_requirement_intent_by_id(requirement_spec: dict[str, Any] | None, intent_id: str) -> dict[str, Any]:
    if not isinstance(requirement_spec, dict):
        return {}
    normalized_intent_id = _normalized_text(intent_id)
    intents = requirement_spec.get("test_intents")
    if not isinstance(intents, list) or not normalized_intent_id:
        return {}
    for item in intents:
        if isinstance(item, dict) and _normalized_text(item.get("intent_id")) == normalized_intent_id:
            return item
    return {}


def _find_test_point_by_intent(test_points: list[dict[str, Any]], intent_id: str) -> dict[str, Any]:
    normalized_intent_id = _normalized_text(intent_id)
    if not normalized_intent_id:
        return {}
    for point in test_points:
        if isinstance(point, dict) and _normalized_text(point.get("intent_id") or point.get("key")) == normalized_intent_id:
            return point
    return {}


def _execution_intent_ids(
    *,
    selected_intent_ids: list[str],
    execution_payload: dict[str, Any],
    compiled_steps: list[dict[str, Any]],
    test_points: list[dict[str, Any]],
) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        intent_id = _normalized_text(value)
        if not intent_id or intent_id == "__page_entry__" or intent_id in seen:
            return
        seen.add(intent_id)
        deduped.append(intent_id)

    for value in selected_intent_ids:
        add(value)
    raw_selected = execution_payload.get("selected_intent_ids")
    if isinstance(raw_selected, list):
        for value in raw_selected:
            add(value)
    for step in compiled_steps:
        if isinstance(step, dict):
            add(step.get("intent_id"))
    for point in test_points:
        if isinstance(point, dict) and not _is_precondition_point(point):
            add(point.get("intent_id") or point.get("key"))
    return deduped


def _intent_product_metadata(
    *,
    intent_id: str,
    case_yaml: dict[str, Any],
    candidate_snapshots: list[dict[str, Any]],
    requirement_spec: dict[str, Any] | None,
    test_points: list[dict[str, Any]],
    effective_requirement: str,
) -> dict[str, str]:
    candidate = _find_candidate_snapshot_by_intent(
        intent_id=intent_id,
        candidate_snapshots=candidate_snapshots,
    )
    requirement_intent = _find_requirement_intent_by_id(requirement_spec, intent_id)
    point = _find_test_point_by_intent(test_points, intent_id)
    point_snapshot = {}
    metadata = point.get("metadata") if isinstance(point.get("metadata"), dict) else {}
    if isinstance(metadata.get("candidate_snapshot"), dict):
        point_snapshot = metadata["candidate_snapshot"]
    title = (
        _normalized_text(candidate.get("title") or candidate.get("summary"))
        or _normalized_text(point_snapshot.get("title") or point_snapshot.get("summary"))
        or _normalized_text(requirement_intent.get("title") or requirement_intent.get("summary"))
        or _normalized_text(point.get("description") or point.get("title"))
        or _normalized_text(case_yaml.get("title"))
        or intent_id
    )
    intent_type = (
        _normalized_text(candidate.get("intent_type"))
        or _normalized_text(point_snapshot.get("intent_type"))
        or _normalized_text(requirement_intent.get("intent_type"))
        or _normalized_text(point.get("point_type"))
        or "functional"
    )
    precondition = (
        _normalized_text(candidate.get("precondition"))
        or _normalized_text(point_snapshot.get("precondition"))
        or _normalized_text(requirement_intent.get("precondition"))
        or _normalized_text(point.get("precondition"))
    )
    expected = (
        _normalized_text(candidate.get("expected") or candidate.get("expected_result"))
        or _normalized_text(point_snapshot.get("expected") or point_snapshot.get("expected_result"))
        or _normalized_text(requirement_intent.get("expected") or requirement_intent.get("expected_result"))
        or _normalized_text(point.get("expected_result") or point.get("expected"))
        or _normalized_text(case_yaml.get("expected_result"))
    )
    source_asset_id = (
        _normalized_text(candidate.get("source_asset_id") or candidate.get("asset_id"))
        or _normalized_text(point_snapshot.get("source_asset_id") or point_snapshot.get("asset_id"))
        or _normalized_text(case_yaml.get("source_asset_id"))
    )
    source_asset_title = (
        _normalized_text(candidate.get("source_asset_title") or candidate.get("asset_title"))
        or _normalized_text(point_snapshot.get("source_asset_title") or point_snapshot.get("asset_title"))
        or _normalized_text(case_yaml.get("source_asset_title"))
        or _normalized_text(effective_requirement)
    )
    return {
        "intent_id": intent_id,
        "title": title,
        "type": intent_type,
        "precondition": precondition,
        "expected": expected,
        "source_asset_id": source_asset_id,
        "source_asset_title": source_asset_title,
    }



# ---- 函数体已移至子模块（单向依赖: format → orchestrate → steps）----
# 导入放在文件末尾：子模块 import 本文件时，所有 leaf 函数定义已加载完毕
# re-exports for _svc() lazy-lookup (restored after accidental deletion in f3adab3)
from .generate_pipeline_format import _enrich_product_case_yaml_v1_1  # noqa: E402
from .generate_pipeline_orchestrate import (  # noqa: E402
    _build_direct_candidate_orchestrator_result,
    _enrich_test_points_with_candidate_snapshots,
    _extract_candidate_snapshots,
    _format_product_case_yaml,
    _load_page_object_from_db,
    _resolve_page_object_from_assets,
    _resolve_page_object_from_db,
    resolve_page_object,
)
