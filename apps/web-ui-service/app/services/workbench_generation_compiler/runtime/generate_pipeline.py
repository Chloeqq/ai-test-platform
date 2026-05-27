from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable, Protocol
import yaml
from sqlalchemy.exc import OperationalError

from shared_backend.db import get_db_session as SessionLocal
from app.models.page_object import PageElement, PageObject
from app.repositories.page_object_repository import PageObjectRepository

from ..debug import debug_enabled, log_debug_event
from shared_backend.observability import summarize_http_context
from shared_backend.execution_compiler import ExecutionCompilerError, compile_execution_steps
from shared_backend.element_binding import build_element_alias_map
from shared_backend.intent_mapping import resolve_explicit_step
from shared_backend.schemas.contracts import normalize_test_point_plan_v1
from shared_backend.schemas.validator import ContractValidator
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

_SUPPORTED_TOP_LEVEL_ASSERTIONS = {"assert_visible", "assert_count", "assert_metric", "assert_text", "assert_url"}
_TOP_LEVEL_ASSERTION_KEYS = {
    "action",
    "target",
    "target_name",
    "selector",
    "locator_type",
    "locator_value",
    "role",
    "intent_id",
    "element_code",
    "count",
    "metric_rule",
    "rule",
    "extract_regex",
    "metric_label",
    "page",
    "value",
    "source_point_key",
    "traceability",
    "expected_result",
}
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
    if any(token in semantic_blob for token in ["username", "user_name", "account", "账号", "用户名"]):
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


def _product_description(title: str, expected: str) -> str:
    title = _normalized_text(title) or "AI生成用例"
    expected = _normalized_text(expected)
    title_key = _normalized_key(title)
    expected_key = _normalized_key(expected)
    if "首次登录成功" in title and any(token in expected for token in ["跳转", "工作台", "首页", "登录用户名"]):
        return f"{title} — 验证输入正确账号密码后可以成功登录并跳转至工作台首页"
    if title_key and expected_key and title_key == expected_key:
        return title
    if expected:
        return f"{title} — {expected[:180]}"
    return title


def _product_page_load_expected(page: str, page_object: dict[str, Any]) -> str:
    normalized_page = _normalized_text(page).lower()
    if normalized_page == "login":
        return "登录页面加载完成，显示账号输入框、密码输入框、登录按钮"
    element_names: list[str] = []
    elements = page_object.get("elements") if isinstance(page_object.get("elements"), dict) else {}
    for raw_meta in list(elements.values())[:3]:
        if not isinstance(raw_meta, dict):
            continue
        name = _normalized_text(raw_meta.get("name"))
        if name:
            element_names.append(name)
    if element_names:
        return f"{page or '目标'}页面加载完成，显示{'、'.join(element_names)}"
    return f"{page or '目标'}页面加载完成"


def _product_element_name(page: str, target_code: str, element_meta: dict[str, Any]) -> str:
    normalized_page = _normalized_text(page).lower()
    normalized_code = _normalized_text(target_code)
    if normalized_page == "login":
        if normalized_code == "username_input":
            return "用户名输入框"
        if normalized_code == "password_input":
            return "密码输入框"
        if normalized_code == "login_button":
            return "登录按钮"
        if normalized_code == "home_menu":
            return "首页菜单"
    return _normalized_text(element_meta.get("name") or element_meta.get("element_name")) or normalized_code


def _product_locator(
    *,
    page: str,
    target_code: str,
    locator_type: str,
    locator_value: str,
) -> tuple[str, str]:
    normalized_locator_type = _normalized_text(locator_type)
    normalized_locator_value = _normalized_text(locator_value)
    if normalized_locator_type and normalized_locator_value:
        return normalized_locator_type, normalized_locator_value
    normalized_page = _normalized_text(page).lower()
    normalized_code = _normalized_text(target_code)
    if normalized_page == "login":
        if normalized_code == "username_input":
            return (
                "css",
                "input[name='username'], #username, #username-input, "
                "input[placeholder*='请输入用户名'], input[placeholder*='用户名']",
            )
        if normalized_code == "password_input":
            return (
                "css",
                "input[type='password'], input[name='password'], #password, #password-input, "
                "input[placeholder*='请输入密码'], input[placeholder*='密码']",
            )
    return normalized_locator_type, normalized_locator_value


_LOGIN_DATA_TESTID_ELEMENT_CODES = {
    "username_input": "login-username-input",
    "password_input": "login-password-input",
    "login_button": "login-submit-btn",
    "home_menu": "home-page",
}


def _product_element_meta(
    *,
    page: str,
    target_code: str,
    elements: dict[str, Any],
) -> dict[str, Any]:
    """按语义 target 取页面对象元素；登录页优先桥接到真实 data-testid 元素。"""
    normalized_page = _normalized_text(page).lower()
    normalized_code = _normalized_text(target_code)
    if normalized_page == "login":
        testid_code = _LOGIN_DATA_TESTID_ELEMENT_CODES.get(normalized_code, "")
        testid_meta = elements.get(testid_code) if testid_code and isinstance(elements.get(testid_code), dict) else {}
        if _normalized_text(testid_meta.get("type") or testid_meta.get("locator_type")) == "data-testid":
            return testid_meta
    return elements.get(normalized_code) if isinstance(elements.get(normalized_code), dict) else {}


def _trusted_page_url(*, payload_page_url: Any, page_object: dict[str, Any]) -> str:
    governed_url = _normalized_text(page_object.get("page_url")) if isinstance(page_object, dict) else ""
    requested_url = _normalized_text(payload_page_url)
    if governed_url and requested_url and governed_url != requested_url:
        raise ExecutionCompilerError(
            code="dsl_v1_1_page_url_mismatch",
            message="DSL V1.1 page_url must match governed page object",
            reason=f"payload.page_url `{requested_url}` does not match page_object.page_url `{governed_url}`",
            stage="dsl_v1_1_enrichment",
        )
    return governed_url or requested_url


def _product_step_expected(
    *,
    action: str,
    target_name: str,
    target_code: str,
    value: Any,
    intent_expected: str,
    is_last_intent_step: bool,
    existing_expected: str,
) -> str:
    if existing_expected:
        return existing_expected
    if is_last_intent_step and intent_expected:
        return intent_expected
    normalized_action = _normalized_text(action).lower()
    value_text = _normalized_text(value)
    target_name = _normalized_text(target_name) or _normalized_text(target_code)
    if normalized_action == "input":
        if target_code == "password_input" or "密码" in target_name:
            return f"{target_name}内容以掩码形式显示"
        if value_text:
            return f"{target_name}内容显示为 {value_text}"
        return f"{target_name}内容已清空"
    if normalized_action == "click":
        return f"已点击{target_name}"
    return ""


def _format_product_execution_steps(
    *,
    compiled_steps: list[dict[str, Any]],
    page: str,
    page_url: str,
    page_object: dict[str, Any],
    expected_by_intent: dict[str, str],
) -> list[dict[str, Any]]:
    elements = page_object.get("elements") if isinstance(page_object.get("elements"), dict) else {}
    last_step_index_by_intent: dict[str, int] = {}
    for index, step in enumerate(compiled_steps):
        if not isinstance(step, dict):
            continue
        intent_id = _normalized_text(step.get("intent_id"))
        action = _normalized_text(step.get("action")).lower()
        if intent_id and intent_id != "__page_entry__" and action not in {"goto", "login"}:
            last_step_index_by_intent[intent_id] = index

    product_steps: list[dict[str, Any]] = []
    for index, raw_step in enumerate(compiled_steps):
        if not isinstance(raw_step, dict):
            continue
        raw_action = _normalized_text(raw_step.get("action")).lower()
        if raw_action in {"fill", "type"}:
            action = "input"
        else:
            action = raw_action or "custom_step"
        if action == "goto":
            value = _normalized_text(raw_step.get("value") or raw_step.get("target") or page_url)
            if not value and page_url:
                value = page_url
            step_payload = {
                "action": "goto",
                "value": value,
                "expected_result": _normalized_text(raw_step.get("expected_result"))
                or _product_page_load_expected(page, page_object),
            }
            product_steps.append(step_payload)
            continue

        target_code = _normalized_text(raw_step.get("target"))
        if target_code.startswith("element:"):
            target_code = target_code.removeprefix("element:").strip()
        element_meta = _product_element_meta(page=page, target_code=target_code, elements=elements)
        # 页面对象库是正式 locator 的事实源。旧编译步骤里可能携带 CSS/role 兜底，
        # 只能在页面对象缺少 locator 时使用，不能覆盖已治理的 data-testid/qa 定位。
        locator_type = _normalized_text(element_meta.get("type") or element_meta.get("locator_type") or raw_step.get("locator_type"))
        locator_value = _normalized_text(element_meta.get("selector") or element_meta.get("locator_value") or raw_step.get("locator_value") or raw_step.get("selector"))
        locator_type, locator_value = _product_locator(
            page=page,
            target_code=target_code,
            locator_type=locator_type,
            locator_value=locator_value,
        )
        target_name = _product_element_name(page, target_code, element_meta)
        intent_id = _normalized_text(raw_step.get("intent_id"))
        intent_expected = expected_by_intent.get(intent_id, "")
        step_payload: dict[str, Any] = {
            "action": action,
            "target": f"element:{target_code}" if target_code else "",
            "locator_type": locator_type,
            "locator_value": locator_value,
            "target_name": target_name,
        }
        role = _normalized_text(raw_step.get("role") or element_meta.get("role"))
        if locator_type == "role" and role:
            step_payload["role"] = role
        if raw_step.get("value") is not None:
            step_payload["value"] = raw_step.get("value")
        expected = _product_step_expected(
            action=action,
            target_name=target_name,
            target_code=target_code,
            value=raw_step.get("value"),
            intent_expected=intent_expected,
            is_last_intent_step=bool(intent_id and last_step_index_by_intent.get(intent_id) == index),
            existing_expected=_normalized_text(raw_step.get("expected_result") or raw_step.get("expected")),
        )
        if expected:
            step_payload["expected_result"] = expected
        product_steps.append(step_payload)
    _append_login_success_assertion(
        product_steps=product_steps,
        page=page,
        page_object=page_object,
        expected_by_intent=expected_by_intent,
    )
    return product_steps


def _append_login_success_assertion(
    *,
    product_steps: list[dict[str, Any]],
    page: str,
    page_object: dict[str, Any],
    expected_by_intent: dict[str, str],
) -> None:
    if _normalized_text(page).lower() != "login":
        return
    if any(_normalized_text(step.get("action")).lower().startswith("assert") for step in product_steps):
        return
    expected_text = " ".join(_normalized_text(value) for value in expected_by_intent.values()).lower()
    if not expected_text:
        return
    negative_tokens = ("失败", "错误", "请输入", "不跳转", "未跳转", "停留", "提示")
    success_tokens = ("登录成功", "跳转至平台工作台首页", "工作台首页", "权限导航菜单")
    if any(token in expected_text for token in negative_tokens):
        return
    if not any(token in expected_text for token in success_tokens):
        return

    elements = page_object.get("elements") if isinstance(page_object.get("elements"), dict) else {}
    home_meta = _product_element_meta(page="login", target_code="home_menu", elements=elements)
    locator_type = _normalized_text(home_meta.get("type") or home_meta.get("locator_type"))
    locator_value = _normalized_text(home_meta.get("selector") or home_meta.get("locator_value"))
    if not locator_type or not locator_value:
        return
    assertion_step: dict[str, Any] = {
        "action": "assert_visible",
        "target": "element:home_menu",
        "locator_type": locator_type,
        "locator_value": locator_value,
        "target_name": _product_element_name("login", "home_menu", home_meta),
        "expected_result": "登录后首页菜单可见，确认已离开登录页并进入工作台",
    }
    role = _normalized_text(home_meta.get("role"))
    if locator_type == "role" and role:
        assertion_step["role"] = role
    product_steps.append(assertion_step)


def _step_element_code(step: dict[str, Any]) -> str:
    target = _normalized_text(step.get("target") or step.get("element_code"))
    if target.startswith("element:"):
        target = target.removeprefix("element:").strip()
    return target


def _is_variable_template(value: Any) -> bool:
    return isinstance(value, str) and bool(_VARIABLE_TEMPLATE_RE.fullmatch(value.strip()))


def _variable_template_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    match = _VARIABLE_TEMPLATE_RE.fullmatch(value.strip())
    if not match:
        return ""
    return _normalized_text(match.group(1))


def _data_key_for_input(*, page: str, element_code: str) -> str:
    normalized_page = _normalized_text(page).lower()
    normalized_code = _normalized_text(element_code).lower()
    if normalized_page == "login" and normalized_code == "username_input":
        return "username"
    if normalized_page == "login" and normalized_code == "password_input":
        return "password"
    if normalized_code.endswith("_input"):
        normalized_code = normalized_code[: -len("_input")]
    data_key = re.sub(r"[^a-z0-9_]+", "_", normalized_code).strip("_")
    return data_key or "input_value"


def _variable_name_for_input(*, page: str, element_code: str, data_key: str) -> str:
    normalized_page = re.sub(r"[^a-z0-9_]+", "_", _normalized_text(page).lower()).strip("_")
    normalized_code = _normalized_text(element_code).lower()
    if normalized_page == "login" and normalized_code == "username_input":
        return "login_username"
    if normalized_page == "login" and normalized_code == "password_input":
        return "login_password"
    return f"{normalized_page}_{data_key}" if normalized_page else data_key


def _reserve_data_key(data: dict[str, Any], base_key: str, value: Any) -> str:
    def _existing_value_matches(raw_entry: Any) -> bool:
        if isinstance(raw_entry, dict):
            source_type = _normalized_data_source_type(raw_entry.get("source_type") or "inline")
            if source_type != "inline":
                return False
            return raw_entry.get("value") == value
        if isinstance(raw_entry, list):
            return raw_entry == [value]
        return raw_entry == value

    key = base_key
    suffix = 2
    while key in data and not _existing_value_matches(data.get(key)):
        key = f"{base_key}_{suffix}"
        suffix += 1
    return key


def _reserve_variable_name(variables: dict[str, Any], base_name: str, template: str) -> str:
    name = base_name
    suffix = 2
    while name in variables and variables.get(name) != template:
        name = f"{base_name}_{suffix}"
        suffix += 1
    return name


def _normalized_data_source_type(value: Any) -> str:
    return _normalized_text(value).lower()


def _normalize_data_source_entry(*, key: str, raw_value: Any) -> dict[str, Any]:
    if isinstance(raw_value, dict):
        source_type = _normalized_data_source_type(raw_value.get("source_type") or "inline")
        if source_type not in _DSL_DATA_SOURCE_TYPES:
            raise ExecutionCompilerError(
                code="dsl_v1_1_invalid_data_source",
                message=f"DSL V1.1 data source_type is invalid for key `{key}`",
                reason=f"unsupported source_type `{source_type}`",
                stage="dsl_v1_1_enrichment",
            )
        if source_type == "inline":
            if "value" not in raw_value:
                raise ExecutionCompilerError(
                    code="dsl_v1_1_invalid_data_source",
                    message=f"DSL V1.1 inline data requires value for key `{key}`",
                    reason="inline source missing value",
                    stage="dsl_v1_1_enrichment",
                )
            return {"source_type": "inline", "value": raw_value.get("value")}
        if source_type == "pool":
            pool_name = _normalized_text(raw_value.get("pool_name"))
            pool_key = _normalized_text(raw_value.get("key"))
            if not pool_name or not pool_key:
                raise ExecutionCompilerError(
                    code="dsl_v1_1_invalid_data_source",
                    message=f"DSL V1.1 pool data requires pool_name and key for `{key}`",
                    reason="pool source missing pool_name/key",
                    stage="dsl_v1_1_enrichment",
                )
            return {"source_type": "pool", "pool_name": pool_name, "key": pool_key}
        env_key = _normalized_text(raw_value.get("key"))
        if not env_key:
            raise ExecutionCompilerError(
                code="dsl_v1_1_invalid_data_source",
                message=f"DSL V1.1 env data requires key for `{key}`",
                reason="env source missing key",
                stage="dsl_v1_1_enrichment",
            )
        return {"source_type": "env", "key": env_key}
    if isinstance(raw_value, list):
        if not raw_value:
            raise ExecutionCompilerError(
                code="dsl_v1_1_invalid_data_source",
                message=f"DSL V1.1 inline data list for `{key}` must not be empty",
                reason="legacy list source is empty",
                stage="dsl_v1_1_enrichment",
            )
        return {"source_type": "inline", "value": raw_value}
    return {"source_type": "inline", "value": raw_value}


def _normalize_dsl_data_sources(product_yaml: dict[str, Any]) -> dict[str, Any]:
    raw_data = product_yaml.get("data")
    if raw_data is None:
        normalized: dict[str, Any] = {}
        product_yaml["data"] = normalized
        return normalized
    if not isinstance(raw_data, dict):
        raise ExecutionCompilerError(
            code="dsl_v1_1_invalid_data_source",
            message="DSL V1.1 data must be an object",
            reason="data section is not object",
            stage="dsl_v1_1_enrichment",
        )
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in raw_data.items():
        key = _normalized_text(raw_key)
        if not key:
            continue
        normalized[key] = _normalize_data_source_entry(key=key, raw_value=raw_value)
    product_yaml["data"] = normalized
    return normalized


def _enrich_dsl_v1_1_data_bindings(product_yaml: dict[str, Any], *, page: str) -> None:
    """把步骤里已有的输入值提升为 DSL V1.1 data/variables，不在代码层猜测默认值。"""
    execution_payload = product_yaml.get("execution") if isinstance(product_yaml.get("execution"), dict) else {}
    steps = execution_payload.get("steps") if isinstance(execution_payload.get("steps"), list) else []
    data = _normalize_dsl_data_sources(product_yaml)
    variables = execution_payload.get("variables") if isinstance(execution_payload.get("variables"), dict) else {}
    product_yaml["data"] = data
    execution_payload["variables"] = variables

    input_count = 0
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        action = _normalized_text(step.get("action")).lower()
        if action not in {"input", "fill"}:
            continue
        input_count += 1
        if "value" not in step:
            raise ExecutionCompilerError(
                code="dsl_v1_1_missing_input_data_source",
                message="DSL V1.1 input step requires declared data source",
                reason=f"input step {index} missing value or data reference",
                stage="dsl_v1_1_enrichment",
            )
        raw_value = step.get("value")
        if _is_variable_template(raw_value):
            referenced_key = _variable_template_key(raw_value)
            if not referenced_key:
                raise ExecutionCompilerError(
                    code="dsl_v1_1_missing_input_data_source",
                    message="DSL V1.1 input step variable reference is invalid",
                    reason=f"input step {index} has invalid variable template",
                    stage="dsl_v1_1_enrichment",
                )
            # 允许直接引用 data key，也允许先引用 execution.variables 再转到 data key。
            if referenced_key not in data:
                variable_mapping = variables.get(referenced_key)
                data_key = _variable_template_key(variable_mapping) if variable_mapping is not None else ""
                if not data_key or data_key not in data:
                    raise ExecutionCompilerError(
                        code="dsl_v1_1_missing_input_data_source",
                        message="DSL V1.1 input step requires declared data source",
                        reason=f"input step {index} references variable `{referenced_key}` without declared data source",
                        stage="dsl_v1_1_enrichment",
                    )
            continue

        element_code = _step_element_code(step)
        base_data_key = _data_key_for_input(page=page, element_code=element_code)
        data_key = _reserve_data_key(data, base_data_key, raw_value)
        data[data_key] = {"source_type": "inline", "value": raw_value}
        variable_template = f"{{{{{data_key}}}}}"
        base_variable_name = _variable_name_for_input(page=page, element_code=element_code, data_key=data_key)
        variable_name = _reserve_variable_name(variables, base_variable_name, variable_template)
        variables[variable_name] = variable_template
        step["value"] = f"{{{{{variable_name}}}}}"

    if input_count and not data:
        raise ExecutionCompilerError(
            code="dsl_v1_1_missing_input_data_source",
            message="DSL V1.1 input steps require declared data source",
            reason="input steps were found but no data bindings were generated",
            stage="dsl_v1_1_enrichment",
        )


def _normalize_top_level_assertion(step: dict[str, Any]) -> dict[str, Any]:
    assertion = {
        key: value
        for key, value in step.items()
        if key in _TOP_LEVEL_ASSERTION_KEYS and value is not None
    }
    if not _normalized_text(assertion.get("locator_value")) and _normalized_text(step.get("selector")):
        assertion["locator_value"] = _normalized_text(step.get("selector"))
    if not _normalized_text(assertion.get("target")) and _normalized_text(step.get("element_code")):
        assertion["target"] = f"element:{_normalized_text(step.get('element_code'))}"
    return assertion


def _assertion_signature(assertion: dict[str, Any]) -> tuple[str, ...]:
    return (
        _normalized_text(assertion.get("action")).lower(),
        _normalized_text(assertion.get("target") or assertion.get("element_code")),
        _normalized_text(assertion.get("locator_type")),
        _normalized_text(assertion.get("locator_value") or assertion.get("selector")),
        _normalized_text(assertion.get("value")),
        _normalized_text(assertion.get("count")),
        _normalized_text(assertion.get("metric_rule") or assertion.get("rule")),
        _normalized_text(assertion.get("extract_regex")),
    )


def _normalize_dsl_v1_1_assertions(product_yaml: dict[str, Any]) -> None:
    """标准化顶层断言：保留步骤内断言时序，只做顶层补充与去重。"""
    execution_payload = product_yaml.get("execution") if isinstance(product_yaml.get("execution"), dict) else {}
    steps = execution_payload.get("steps") if isinstance(execution_payload.get("steps"), list) else []
    assertions_raw = product_yaml.get("assertions") if isinstance(product_yaml.get("assertions"), list) else []
    assertions: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    step_assertion_signatures: set[tuple[str, ...]] = set()

    for step in steps:
        if not isinstance(step, dict):
            continue
        action = _normalized_text(step.get("action")).lower()
        if action not in _SUPPORTED_TOP_LEVEL_ASSERTIONS:
            continue
        normalized_step_assertion = _normalize_top_level_assertion({**step, "action": action})
        step_assertion_signatures.add(_assertion_signature(normalized_step_assertion))

    def add_assertion(raw: Any) -> None:
        if not isinstance(raw, dict):
            return
        action = _normalized_text(raw.get("action")).lower()
        if action not in _SUPPORTED_TOP_LEVEL_ASSERTIONS:
            return
        normalized = _normalize_top_level_assertion({**raw, "action": action})
        signature = _assertion_signature(normalized)
        if signature in step_assertion_signatures:
            return
        if signature in seen:
            return
        seen.add(signature)
        assertions.append(normalized)

    for raw in assertions_raw:
        add_assertion(raw)
    product_yaml["assertions"] = assertions


def _is_ai_automated_case(product_yaml: dict[str, Any]) -> bool:
    status = _normalized_text(product_yaml.get("status")).lower()
    tags = product_yaml.get("tags") if isinstance(product_yaml.get("tags"), list) else []
    normalized_tags = {_normalized_text(tag).lower() for tag in tags if _normalized_text(tag)}
    case_id = _normalized_text(product_yaml.get("id")).lower()
    return status == "automated" and ("ai-generated" in normalized_tags or "-ai-" in case_id)


def _validate_dsl_v1_1_minimum_contract(product_yaml: dict[str, Any]) -> None:
    """校验 V1.1 最小契约：来源身份完整，AI 自动化用例必须有真实断言。"""
    requirement = product_yaml.get("requirement") if isinstance(product_yaml.get("requirement"), dict) else {}
    execution_payload = product_yaml.get("execution") if isinstance(product_yaml.get("execution"), dict) else {}
    intent_id = _normalized_text(requirement.get("intent_id"))
    source_asset_id = _normalized_text(requirement.get("source_asset_id"))
    selected_ids = execution_payload.get("selected_intent_ids") if isinstance(execution_payload.get("selected_intent_ids"), list) else []
    normalized_selected_ids = {_normalized_text(item) for item in selected_ids if _normalized_text(item)}
    if not intent_id or not source_asset_id or normalized_selected_ids != {intent_id}:
        raise ExecutionCompilerError(
            code="dsl_v1_1_missing_source_identity",
            message="DSL V1.1 case requires source_asset_id and exactly one selected intent_id",
            reason="source identity is incomplete",
            stage="dsl_v1_1_enrichment",
        )
    if _is_ai_automated_case(product_yaml):
        steps = execution_payload.get("steps") if isinstance(execution_payload.get("steps"), list) else []
        step_assertion_count = 0
        for raw_step in steps:
            if not isinstance(raw_step, dict):
                continue
            action = _normalized_text(raw_step.get("action")).lower()
            if action in _SUPPORTED_TOP_LEVEL_ASSERTIONS:
                step_assertion_count += 1
        assertions = product_yaml.get("assertions") if isinstance(product_yaml.get("assertions"), list) else []
        if not assertions and step_assertion_count <= 0:
            raise ExecutionCompilerError(
                code="dsl_v1_1_missing_executable_assertion",
                message="DSL V1.1 AI automated case requires executable assertions",
                reason="expected_result is documentation only",
                stage="dsl_v1_1_enrichment",
            )


def _enrich_product_case_yaml_v1_1(product_yaml: dict[str, Any], *, page: str) -> dict[str, Any]:
    """生成器统一出口：写入 DB 的 script_code 必须先满足 DSL V1.1 契约。"""
    product_yaml["version"] = "v1.1"
    _enrich_dsl_v1_1_data_bindings(product_yaml, page=page)
    _normalize_dsl_v1_1_assertions(product_yaml)
    _validate_dsl_v1_1_minimum_contract(product_yaml)
    return product_yaml


def _format_product_case_yaml(
    *,
    case_yaml: dict[str, Any],
    payload: Any,
    page: str,
    page_url: str,
    page_object: dict[str, Any],
    test_points: list[dict[str, Any]],
    candidate_snapshots: list[dict[str, Any]],
    requirement_spec: dict[str, Any] | None,
    selected_intent_ids: list[str],
    effective_requirement: str,
) -> dict[str, Any]:
    execution_payload = case_yaml.get("execution") if isinstance(case_yaml.get("execution"), dict) else {}
    compiled_steps = execution_payload.get("steps") if isinstance(execution_payload.get("steps"), list) else []
    intent_ids = _execution_intent_ids(
        selected_intent_ids=selected_intent_ids,
        execution_payload=execution_payload,
        compiled_steps=compiled_steps,
        test_points=test_points,
    )
    primary_intent_id = intent_ids[0] if intent_ids else ""
    intent_meta = _intent_product_metadata(
        intent_id=primary_intent_id,
        case_yaml=case_yaml,
        candidate_snapshots=candidate_snapshots,
        requirement_spec=requirement_spec,
        test_points=test_points,
        effective_requirement=effective_requirement,
    ) if primary_intent_id else {
        "intent_id": "",
        "title": _normalized_text(case_yaml.get("title")),
        "type": "functional",
        "precondition": "",
        "expected": _normalized_text(case_yaml.get("expected_result")),
        "source_asset_id": "",
        "source_asset_title": _normalized_text(effective_requirement),
    }
    expected_by_intent = {
        intent_id: _intent_product_metadata(
            intent_id=intent_id,
            case_yaml=case_yaml,
            candidate_snapshots=candidate_snapshots,
            requirement_spec=requirement_spec,
            test_points=test_points,
            effective_requirement=effective_requirement,
        ).get("expected", "")
        for intent_id in intent_ids
    }
    expected = _normalized_text(intent_meta.get("expected")) or _normalized_text(case_yaml.get("expected_result"))
    title = _normalized_text(case_yaml.get("title")) or _normalized_text(intent_meta.get("title")) or _normalized_text(getattr(payload, "title", "")) or "AI生成用例"
    priority = _normalized_text(case_yaml.get("priority")) or _normalized_text(getattr(payload, "priority", "")) or "P1"
    tags = [item for item in case_yaml.get("tags", []) if _normalized_text(item)] if isinstance(case_yaml.get("tags"), list) else []
    product_yaml: dict[str, Any] = {
        "version": "v1",
        "id": _normalized_text(case_yaml.get("id")),
        "project": _normalized_text(case_yaml.get("project")) or _normalized_text(getattr(payload, "project", "")) or "mall",
        "module": page or _normalized_text(case_yaml.get("module")) or "product",
        "title": title,
        "priority": priority,
        "tags": tags or ["ai-generated"],
        "owner": _normalized_text(case_yaml.get("owner")) or "qa-team",
        "status": _normalized_text(case_yaml.get("status")) or "automated",
        "description": _product_description(title, expected),
        "requirement": {
            "intent_id": _normalized_text(intent_meta.get("intent_id")) or primary_intent_id,
            "title": _normalized_text(intent_meta.get("title")) or title,
            "type": _normalized_text(intent_meta.get("type")) or "functional",
            "precondition": _normalized_text(intent_meta.get("precondition")),
            "source_asset_id": _normalized_text(intent_meta.get("source_asset_id")),
        },
        "data": case_yaml.get("data") if isinstance(case_yaml.get("data"), dict) else {},
        "execution": {
            "runner": _normalized_text(execution_payload.get("runner")) or "playwright",
            "page": page or _normalized_text(execution_payload.get("page")) or "product",
            "page_url": page_url,
            "variables": execution_payload.get("variables") if isinstance(execution_payload.get("variables"), dict) else {},
            "steps": _format_product_execution_steps(
                compiled_steps=compiled_steps,
                page=page,
                page_url=page_url,
                page_object=page_object,
                expected_by_intent=expected_by_intent,
            ),
            "selected_intent_ids": intent_ids,
        },
        "expected_result": expected,
    }
    product_yaml = _enrich_product_case_yaml_v1_1(product_yaml, page=page)
    if not product_yaml["requirement"]["precondition"]:
        product_yaml["requirement"].pop("precondition", None)
    return product_yaml


def _attach_point_expected_results(compiled_steps: list[dict[str, Any]], test_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected_by_intent: dict[str, str] = {}
    for point in test_points:
        if not isinstance(point, dict):
            continue
        intent_id = _normalized_text(point.get("intent_id") or point.get("key"))
        expected = _normalized_text(point.get("expected_result") or point.get("expected"))
        if intent_id and expected:
            expected_by_intent[intent_id] = expected
    if not expected_by_intent:
        return compiled_steps

    last_step_index_by_intent: dict[str, int] = {}
    for index, step in enumerate(compiled_steps):
        if not isinstance(step, dict):
            continue
        intent_id = _normalized_text(step.get("intent_id"))
        action = _normalized_text(step.get("action")).lower()
        if not intent_id or intent_id == "__page_entry__" or action in {"goto", "login"}:
            continue
        if intent_id in expected_by_intent:
            last_step_index_by_intent[intent_id] = index

    for intent_id, index in last_step_index_by_intent.items():
        step = compiled_steps[index]
        if not _normalized_text(step.get("expected_result") or step.get("expected")):
            step["expected_result"] = expected_by_intent[intent_id]
    return compiled_steps


def _build_direct_candidate_orchestrator_result(
    *,
    payload: Any,
    normalized_page: str,
    effective_requirement: str,
    candidate_snapshots: list[dict[str, Any]],
    selected_candidate: dict[str, Any] | None,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    if isinstance(selected_candidate, dict) and selected_candidate:
        candidates.append(_normalize_candidate_snapshot(selected_candidate))
    candidates.extend(candidate_snapshots)
    candidate = next((item for item in candidates if _list_text(item.get("steps_hint"))), None)
    if not candidate:
        return None

    page = _normalized_text(normalized_page or getattr(payload, "page", "")) or "product"
    page_object = resolve_page_object(str(getattr(payload, "project", "") or ""), page)
    alias_map = build_element_alias_map(page_object)
    intent_id, title = _candidate_identity(candidate)
    steps: list[dict[str, Any]] = []
    involved_codes: list[str] = []
    for index, hint in enumerate(_list_text(candidate.get("steps_hint"))):
        action, target, value = resolve_explicit_step(
            steps_hint=[hint],
            page=page,
            page_element_alias_map=alias_map,
        )
        step: dict[str, Any] = {
            "action": action,
            "target": target or "",
            "raw_text": hint,
            "description": hint,
        }
        if value is not None:
            step["value"] = value
        if action == "assert_metric" and value is not None:
            step["metric_rule"] = value
            step["rule"] = value
        steps.append(step)
        if target and target not in involved_codes:
            involved_codes.append(target)

    if not steps:
        return None

    candidate_codes = _list_text(candidate.get("involved_element_codes")) or involved_codes
    if not candidate_codes:
        candidate_codes = involved_codes
    expected = _normalized_text(candidate.get("expected") or candidate.get("expected_result"))
    priority = _normalized_text(candidate.get("priority")) or _normalized_text(getattr(payload, "priority", "")) or "P1"
    intent_type = _normalized_text(candidate.get("intent_type")) or "functional"
    point = {
        "key": intent_id,
        "intent_id": intent_id,
        "point_type": _point_type_from_intent_type(intent_type),
        "action": _normalized_text(steps[0].get("action")) or "candidate",
        "description": title,
        "priority": priority,
        "expected_result": expected,
        "dependencies": [],
        "source_ids": [intent_id],
        "steps": steps,
        "involved_elements": candidate_codes,
        "metadata": {
            "candidate_snapshot": candidate,
            "traceability": {
                "intent_ids": [intent_id],
                "source_ids": [intent_id],
                "origin": "selected_candidate_direct_compile",
            },
        },
    }
    precondition = _normalized_text(candidate.get("precondition"))
    if precondition:
        point["precondition"] = precondition

    requirement_spec = {
        "project": _normalized_text(getattr(payload, "project", "")) or "mall",
        "page": page,
        "raw_requirement": effective_requirement,
        "design_input": effective_requirement,
        "source_type": "test_point_asset",
        "priority": priority,
        "parse_confidence": 1.0,
        "test_intents": [
            {
                "intent_id": intent_id,
                "title": title,
                "summary": _normalized_text(candidate.get("summary")) or title,
                "intent_type": intent_type,
                "priority": priority,
                "expected_result": expected,
                "steps_hint": _list_text(candidate.get("steps_hint")),
                "involved_elements": candidate_codes,
                "quality_gate": {"decision": "allow", "blockers": []},
            }
        ],
        "quality_gate": {"decision": "allow", "blockers": []},
    }
    case_yaml = {
        "version": "v4",
        "id": _normalized_text(getattr(payload, "case_id", "")),
        "project": _normalized_text(getattr(payload, "project", "")) or "mall",
        "module": page,
        "title": _normalized_text(getattr(payload, "title", "")) or title,
        "priority": priority,
        "tags": [item for item in getattr(payload, "tags", []) if _normalized_text(item)] or ["ai-generated"],
        "owner": "qa-team",
        "status": "automated",
        "description": _normalized_text(candidate.get("summary")) or title,
        "requirement": _direct_candidate_requirement_lines(candidate, intent_id=intent_id, title=title),
        "data": {},
        "execution": {
            "runner": "playwright",
            "page": page,
            "variables": {},
            "steps": [],
            "selected_intent_ids": [intent_id],
        },
        "expected_result": expected,
    }
    return {
        "requirement_spec": requirement_spec,
        "case": case_yaml,
        "test_points": {
            "version": "TestPointPlanV1",
            "project": _normalized_text(getattr(payload, "project", "")) or "mall",
            "case_id": _normalized_text(getattr(payload, "case_id", "")),
            "page": page,
            "source_type": "selected_candidate_direct_compile",
            "requirement": [effective_requirement or title],
            "points": [point],
            "metadata": {
                "build_source": "selected_candidate.steps_hint",
                "selected_intent_ids": [intent_id],
            },
        },
        "direct_compile": True,
    }


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
        candidate_element_codes = _list_text(candidate.get("involved_element_codes"))
        candidate_elements = _list_text(candidate.get("involved_elements"))
        if candidate_element_codes:
            point["involved_elements"] = candidate_element_codes
            point["involved_element_aliases"] = candidate_elements
        elif candidate_elements:
            point["involved_elements"] = candidate_elements
        existing_steps = point.get("steps") if isinstance(point.get("steps"), list) else []
        has_executable_steps = any(
            isinstance(step, dict)
            and _normalized_text(step.get("action"))
            and _normalized_text(step.get("action")).lower() != "candidate_step"
            for step in existing_steps
        )
        candidate_steps = _list_text(candidate.get("steps"))
        if candidate_steps and not has_executable_steps:
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
        page_object, elements = _load_page_object_from_db(project, page)
        if page_object is None:
            return None
    except OperationalError:
        _LOGGER.warning("DB page-object lookup connection failed for %s/%s; retrying once", project, page, exc_info=True)
        try:
            page_object, elements = _load_page_object_from_db(project, page)
            if page_object is None:
                return None
        except ExecutionCompilerError:
            raise
        except Exception as exc:
            _LOGGER.debug("DB page-object lookup retry failed for %s/%s", project, page, exc_info=True)
            raise ExecutionCompilerError(
                code="page_object_db_lookup_failed",
                message="page object DB lookup failed",
                reason=f"{project}/web/{page}: {type(exc).__name__}",
                stage="resolve_page_object",
            ) from exc
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
    if page == "login":
        success_element = _load_cross_page_data_testid_element(
            project=project,
            element_code="home-page",
            preferred_pages=("home", "layout"),
        )
        if success_element is not None and "home-page" not in mapping:
            mapping["home-page"] = success_element
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
    return {"page": page, "page_url": _normalized_text(getattr(page_object, "page_url", "")), "elements": mapping}


def _load_cross_page_data_testid_element(
    *,
    project: str,
    element_code: str,
    preferred_pages: tuple[str, ...],
) -> dict[str, Any] | None:
    """登录成功后会跳到首页，成功态断言允许引用首页的已治理 data-testid。"""
    normalized_code = _normalized_text(element_code)
    if not normalized_code:
        return None
    try:
        with SessionLocal() as db:
            repo = PageObjectRepository(db)
            row = repo.find_element_by_testid_across_pages(
                project, list(preferred_pages), normalized_code
            )
    except Exception:
        _LOGGER.debug("cross-page data-testid lookup failed for %s/%s", project, normalized_code, exc_info=True)
        return None
    if row is None or not _is_qualified_formal_element(row):
        return None
    selector = _normalized_text(getattr(row, "locator_value", ""))
    if not selector:
        return None
    return {
        "selector": selector,
        "type": "data-testid",
        "role": _normalized_text(getattr(row, "role", "")),
        "name": _element_display_name(
            page="home",
            element_code=normalized_code,
            element_name=_normalized_text(getattr(row, "element_name", "")),
            locator_value=selector,
            role=_normalized_text(getattr(row, "role", "")),
        ),
        "aliases": _infer_element_aliases(
            page="home",
            element_code=normalized_code,
            element_name=_normalized_text(getattr(row, "element_name", "")),
            locator_value=selector,
            role=_normalized_text(getattr(row, "role", "")),
            business_type=_normalized_text(getattr(row, "business_type", "")).lower(),
            aliases=_normalize_json_list(getattr(row, "aliases_json", [])),
        ),
        "business_type": _normalized_text(getattr(row, "business_type", "")).lower(),
        "business_domain": _normalized_text(getattr(row, "business_domain", "")).lower(),
        "semantic_tags": _normalize_json_list(getattr(row, "semantic_tags_json", [])),
        "review_status": _normalized_text(getattr(row, "review_status", "")).lower(),
        "stability_level": _normalized_text(getattr(row, "stability_level", "")).lower(),
        "status": _normalized_text(getattr(row, "status", "")).lower() or "active",
    }


def _load_page_object_from_db(project: str, page: str) -> tuple[PageObject | None, list[PageElement]]:
    with SessionLocal() as db:
        repo = PageObjectRepository(db)
        page_object = repo.get_by_identity(project, "web", page)
        if page_object is None:
            return None, []
        elements = repo.list_elements_by_page_object_id(int(page_object.id), order_by_id=True)
        return page_object, elements


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
    """Pipeline 的页面对象解析（Shared Path）。

    先查 DB（通过 _load_page_object_from_db），失败则回退到 YAML asset。
    返回 {page, page_url, elements}。
    对应的 orchestrator 入口是 OrchestratorService._resolve_page_object()，
    对应的 facade 入口是 facade._page_object_generation_context()。
    """
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


def _handle_generation_exception(
    *,
    exc: Exception,
    trace_id: str,
    selected_intent_ids_list: list[str],
    mode: str,
    http_exception_cls: Any,
    unprocessable_entity_status: int,
    is_quality_gate_blocked: Any,
    payload: Any,
    normalized_page: str,
    multisource_enabled: bool,
    append_history: Any,
    now_iso: Any,
) -> None:
    """处理生成管线异常：分类记录日志并重新抛出对应的 HTTPException。"""
    if isinstance(exc, ExecutionCompilerError):
        _log_generation_failure(
            level=logging.WARNING, stage="execution_compiler", trace_id=trace_id,
            error=exc.to_detail(),
            payload={"selected_intent_ids": selected_intent_ids_list, "mode": mode},
        )
        raise http_exception_cls(status_code=unprocessable_entity_status, detail=exc.to_detail()) from exc
    if isinstance(exc, http_exception_cls):
        is_gate_blocked, blocked_gate = is_quality_gate_blocked(getattr(exc, "detail", ""))
        if is_gate_blocked and isinstance(blocked_gate, dict):
            _log_generation_failure(
                level=logging.WARNING, stage="quality_gate", trace_id=trace_id,
                error=getattr(exc, "detail", ""),
                payload={"selected_intent_ids": selected_intent_ids_list, "mode": mode},
                extra={"blocked_gate": blocked_gate},
            )
            append_history({
                "timestamp": now_iso(),
                "action": "generate_case_blocked_by_quality_gate",
                "case_id": payload.case_id.strip(), "page": normalized_page,
                "source": payload.source, "multi_source_enabled": multisource_enabled,
                "quality_gate": blocked_gate, "orchestrator_error_reason": getattr(exc, "detail", ""),
            })
            raise http_exception_cls(
                status_code=getattr(exc, "status_code", unprocessable_entity_status)
                if isinstance(getattr(exc, "status_code", None), int) else unprocessable_entity_status,
                detail={"code": "requirement_quality_gate_blocked",
                         "message": "requirement quality gate blocked orchestration",
                         "quality_gate": blocked_gate, "upstream_error": getattr(exc, "detail", "")},
            ) from exc
        upstream_status_code = getattr(exc, "status_code", None)
        upstream_detail = getattr(exc, "detail", "")
        detail_payload = upstream_detail if isinstance(upstream_detail, dict) else {}
        detail_code = str(detail_payload.get("code", "")).strip().lower()
        detail_reason_code = str(detail_payload.get("reason_code", "")).strip().lower()
        if (isinstance(upstream_status_code, int) and upstream_status_code == unprocessable_entity_status
                and detail_code in _COMPILER_ERROR_CODES):
            _log_generation_failure(
                level=logging.WARNING, stage="compiler_upstream", trace_id=trace_id,
                error=detail_payload or upstream_detail,
                payload={"selected_intent_ids": selected_intent_ids_list, "mode": mode,
                         "upstream_status_code": upstream_status_code},
            )
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail=detail_payload or {"code": "execution_compiler_failed",
                                            "message": "execution compiler failed",
                                            "reason": str(upstream_detail)[:500],
                                            "stage": "run_generate_pipeline"},
            ) from exc
        if (isinstance(upstream_status_code, int) and upstream_status_code == unprocessable_entity_status
                and (detail_code == "validation_error" or detail_reason_code == "test_design_invalid_output")):
            _log_generation_failure(
                level=logging.WARNING, stage="validation_upstream", trace_id=trace_id,
                error=detail_payload or upstream_detail,
                payload={"selected_intent_ids": selected_intent_ids_list, "mode": mode,
                         "upstream_status_code": upstream_status_code},
            )
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail=detail_payload or {"code": "validation_error", "message": str(upstream_detail)[:500]},
            ) from exc
        _log_generation_failure(
            level=logging.ERROR, stage="orchestrator_generate_failed", trace_id=trace_id,
            error=upstream_detail,
            payload={"selected_intent_ids": selected_intent_ids_list, "mode": mode,
                     "upstream_status_code": upstream_status_code, "detail_code": detail_code,
                     "detail_reason_code": detail_reason_code},
        )
        raise http_exception_cls(
            status_code=unprocessable_entity_status,
            detail={"code": "orchestrator_generate_failed", "message": "orchestrator generate failed",
                    "upstream_error": str(upstream_detail)[:500]},
        ) from exc
    upstream_error = str(exc)
    _log_generation_failure(
        level=logging.ERROR, stage="unexpected_exception", trace_id=trace_id,
        error=upstream_error[:500],
        payload={"selected_intent_ids": selected_intent_ids_list, "mode": mode, "is_http_exception": False},
    )
    raise http_exception_cls(
        status_code=unprocessable_entity_status,
        detail={"code": "orchestrator_generate_failed", "message": "orchestrator generate failed",
                "upstream_error": upstream_error[:500]},
    ) from exc


def _call_orchestrator_and_parse(
    *,
    payload: Any,
    normalized_page: str,
    effective_requirement: str,
    candidate_snapshots: list[dict[str, Any]],
    selected_candidate: dict[str, Any] | None,
    run_orchestrator_generate: RunOrchestratorGenerate,
    extract_quality_gate: ExtractQualityGate,
    http_exception_cls: Any,
    bad_gateway_status: int,
    unprocessable_entity_status: int,
    input_sources: list[dict[str, Any]],
    openapi_spec: dict[str, Any],
) -> dict[str, Any]:
    """Step 1: call orchestrator and parse response."""
    direct_orchestrator_result = _build_direct_candidate_orchestrator_result(
        payload=payload,
        normalized_page=normalized_page,
        effective_requirement=effective_requirement,
        candidate_snapshots=candidate_snapshots,
        selected_candidate=selected_candidate,
    )
    if direct_orchestrator_result is not None:
        orchestrator_result = direct_orchestrator_result
        _LOGGER.info(
            "pipeline using direct candidate path (no LLM call): page=%s intent_ids=%s",
            normalized_page, selected_intent_ids_list,
        )
    else:
        _LOGGER.info(
            "pipeline calling orchestrator LLM: page=%s requirement_chars=%d",
            normalized_page, len(effective_requirement),
        )
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
    return {
        "orchestrator_result": orchestrator_result,
        "case_yaml": case_yaml,
        "execution_payload": execution_payload,
        "resolved_page": resolved_page,
        "quality_gate": quality_gate,
        "test_points": test_points,
        "test_points_payload": test_points_payload,
    }


def _normalize_and_scope_test_points(
    *,
    payload: Any,
    resolved_page: str,
    test_points: list[dict[str, Any]],
    test_points_payload: dict[str, Any],
    orchestrator_result: dict[str, Any],
    selected_intent_ids: set[str],
    candidate_snapshots: list[dict[str, Any]],
    requirement_spec: dict[str, Any] | None,
    http_exception_cls: Any,
    unprocessable_entity_status: int,
) -> dict[str, Any]:
    """Step 2: normalize, scope test points to selected intents, and enrich with candidate snapshots."""
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

    requirement_spec = (
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
    return {
        "test_points": test_points,
        "test_points_payload": test_points_payload,
        "requirement_spec": requirement_spec,
        "orchestrator_result": orchestrator_result,
    }


def _validate_and_compile_steps(
    *,
    payload: Any,
    resolved_page: str,
    requirement_spec: dict[str, Any] | None,
    test_points: list[dict[str, Any]],
    page_object: dict[str, Any],
    http_exception_cls: Any,
    unprocessable_entity_status: int,
    selected_intent_ids: set[str],
    selected_intent_ids_list: list[str],
    execution_payload: dict[str, Any],
    test_points_payload: dict[str, Any],
    orchestrator_result: dict[str, Any],
) -> dict[str, Any]:
    """Step 3: resolve page object, validate contracts, and compile execution steps."""
    try:
        page_object = resolve_page_object(str(payload.project or ""), resolved_page)
    except ExecutionCompilerError as page_object_exc:
        raise http_exception_cls(
            status_code=unprocessable_entity_status,
            detail=page_object_exc.to_detail(),
        ) from page_object_exc
    try:
        trusted_page_url = _trusted_page_url(
            payload_page_url=getattr(payload, "page_url", ""),
            page_object=page_object,
        )
    except ExecutionCompilerError as page_url_exc:
        raise http_exception_cls(
            status_code=unprocessable_entity_status,
            detail=page_url_exc.to_detail(),
        ) from page_url_exc

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

    compiled_steps = _attach_point_expected_results(
        compile_execution_steps(test_points, page_object),
        test_points if isinstance(test_points, list) else [],
    )
    page_entry_url = trusted_page_url
    if page_entry_url:
        first_step = compiled_steps[0] if compiled_steps and isinstance(compiled_steps[0], dict) else {}
        first_action = _normalized_text(first_step.get("action")).lower()
        first_value = _normalized_text(first_step.get("value") or first_step.get("target"))
        if first_action != "goto" or first_value != page_entry_url:
            compiled_steps = [
                {
                    "action": "goto",
                    "target": "",
                    "selector": "",
                    "locator_type": "",
                    "role": "",
                    "intent_id": "__page_entry__",
                    "confidence": 1.0,
                    "value": page_entry_url,
                    "traceability": {
                        "source": "page_object.page_url",
                        "page": resolved_page,
                    },
                },
                *compiled_steps,
            ]
    if selected_intent_ids:
        compiled_intent_ids = {
            _normalized_text(step.get("intent_id"))
            for step in compiled_steps
            if isinstance(step, dict)
            and _normalized_text(step.get("intent_id"))
            and _normalized_text(step.get("intent_id")) != "__page_entry__"
            and _normalized_text(step.get("action")).lower() != "login"
            and _normalized_text(step.get("action")).lower() != "goto"
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
    return {
        "page_object": page_object,
        "trusted_page_url": trusted_page_url,
        "compiled_steps": compiled_steps,
        "execution_payload": execution_payload,
        "orchestrator_result": orchestrator_result,
        "test_points_payload": test_points_payload,
    }


def _allocate_and_format_case_id(
    *,
    payload: Any,
    case_yaml: dict[str, Any],
    resolved_page: str,
    normalized_page: str,
    allocate_case_id: AllocateCaseId,
    ai_cases_root: Any,
    existing_case_ids: list[str] | None,
    page_object: dict[str, Any],
    execution_payload: dict[str, Any],
) -> dict[str, Any]:
    """Step 4: allocate case ID and set title/priority/tags/module/pages."""
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
    final_page_url = _normalized_text(page_object.get("page_url") or execution_payload.get("page_url"))
    if final_page_url:
        execution_payload["page_url"] = final_page_url
    return {
        "case_id": case_id,
        "case_yaml": case_yaml,
        "execution_payload": execution_payload,
        "final_page_url": final_page_url,
    }


def _persist_and_build_response(
    *,
    payload: Any,
    case_yaml: dict[str, Any],
    resolved_page: str,
    final_page_url: str,
    case_id: str,
    page_object: dict[str, Any],
    test_points: list[dict[str, Any]],
    candidate_snapshots: list[dict[str, Any]],
    requirement_spec: dict[str, Any] | None,
    selected_intent_ids_list: list[str],
    selected_intent_ids: set[str],
    effective_requirement: str,
    write_case_yaml: WriteCaseYaml,
    save_case_state: SaveCaseState,
    save_test_point_plan: Callable[..., Any] | None,
    now_iso: NowIso,
    append_history: AppendHistory,
    multisource_enabled: bool,
    quality_gate: dict[str, Any] | None,
    orchestrator_result: dict[str, Any],
    trace_id: str,
    http_exception_cls: Any,
    unprocessable_entity_status: int,
    mode: str,
    ai_cases_root: Any,
) -> dict[str, Any]:
    """Step 5: format product YAML, write files, save state, append history, build result."""
    _execution_payload = case_yaml.get("execution")
    if not isinstance(_execution_payload, dict):
        _execution_payload = {}
        case_yaml["execution"] = _execution_payload
    try:
        case_yaml = _format_product_case_yaml(
            case_yaml=case_yaml,
            payload=payload,
            page=_execution_payload["page"],
            page_url=final_page_url,
            page_object=page_object,
            test_points=test_points if isinstance(test_points, list) else [],
            candidate_snapshots=candidate_snapshots,
            requirement_spec=requirement_spec,
            selected_intent_ids=selected_intent_ids_list,
            effective_requirement=effective_requirement,
        )
    except ExecutionCompilerError as exc:
        _log_generation_failure(
            level=logging.WARNING,
            stage="dsl_v1_1_enrichment",
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
    execution_payload = case_yaml.get("execution") if isinstance(case_yaml.get("execution"), dict) else {}

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
                    "selected_candidates": _redact_generation_payload(candidate_snapshots),
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
        payload=_redact_generation_payload(result),
        extra={"compare_with_event": "runtime.generate.orchestrator_output"},
    )
    return result


def run_generate_pipeline(
    *, payload: Any, normalized_page: str, effective_requirement: str,
    multisource_enabled: bool, input_sources: list[dict[str, Any]], openapi_spec: dict[str, Any],
    run_orchestrator_generate: RunOrchestratorGenerate, extract_quality_gate: ExtractQualityGate,
    write_case_yaml: WriteCaseYaml, save_case_state: SaveCaseState,
    save_test_point_plan: Callable[..., Any] | None,
    append_history: AppendHistory, now_iso: NowIso, is_quality_gate_blocked: IsQualityGateBlocked,
    ai_cases_root: Any, http_exception_cls: Any, bad_gateway_status: int,
    unprocessable_entity_status: int, existing_case_ids: list[str] | None = None,
    selected_candidate: dict[str, Any] | None = None,
    allocate_case_id: AllocateCaseId, trace_id: str = "", mode: str = "generate",
) -> dict[str, Any]:
    log_debug_event(logger=_LOGGER, event="runtime.generate.input", trace_id=trace_id, payload={
        "project": str(getattr(payload, "project", "") or ""), "page": normalized_page,
        "requirement": effective_requirement, "multisource_enabled": multisource_enabled,
        "input_sources": _redact_generation_payload(input_sources), "openapi_spec": openapi_spec,
        "existing_case_ids": existing_case_ids or [],
        "selected_candidate": _redact_generation_payload(selected_candidate) if isinstance(selected_candidate, dict) else {},
    }, extra={"compare_with_event": "service.generate.input"})
    orchestrator_result: dict[str, Any] = {}
    case_yaml: dict[str, Any] = {}
    resolved_page = normalized_page
    quality_gate: dict[str, Any] | None = None
    requirement_spec: dict[str, Any] | None = None
    test_points: list[dict[str, Any]] = []
    page_object: dict[str, Any] = {}
    selected_intent_ids_list = _extract_selected_intent_ids(payload=payload, selected_candidate=selected_candidate)
    selected_intent_ids = set(selected_intent_ids_list)
    candidate_snapshots = _extract_candidate_snapshots(payload=payload, selected_candidate=selected_candidate)
    if candidate_snapshots and len(selected_intent_ids_list) != 1:
        raise http_exception_cls(status_code=unprocessable_entity_status, detail={
            "code": "dsl_v1_1_selected_intent_count_invalid",
            "message": "DSL V1.1 formal generation requires exactly one selected intent",
            "selected_intent_ids": selected_intent_ids_list,
            "stage": "run_generate_pipeline",
        })
    try:
        step1 = _call_orchestrator_and_parse(
            payload=payload, normalized_page=normalized_page,
            effective_requirement=effective_requirement,
            candidate_snapshots=candidate_snapshots, selected_candidate=selected_candidate,
            run_orchestrator_generate=run_orchestrator_generate,
            extract_quality_gate=extract_quality_gate,
            http_exception_cls=http_exception_cls, bad_gateway_status=bad_gateway_status,
            unprocessable_entity_status=unprocessable_entity_status,
            input_sources=input_sources, openapi_spec=openapi_spec,
        )
        step2 = _normalize_and_scope_test_points(
            payload=payload, resolved_page=step1["resolved_page"],
            test_points=step1["test_points"], test_points_payload=step1["test_points_payload"],
            orchestrator_result=step1["orchestrator_result"],
            selected_intent_ids=selected_intent_ids, candidate_snapshots=candidate_snapshots,
            requirement_spec=requirement_spec,
            http_exception_cls=http_exception_cls,
            unprocessable_entity_status=unprocessable_entity_status,
        )
        step3 = _validate_and_compile_steps(
            payload=payload, resolved_page=step1["resolved_page"],
            requirement_spec=step2["requirement_spec"], test_points=step2["test_points"],
            page_object=page_object, http_exception_cls=http_exception_cls,
            unprocessable_entity_status=unprocessable_entity_status,
            selected_intent_ids=selected_intent_ids,
            selected_intent_ids_list=selected_intent_ids_list,
            execution_payload=step1["execution_payload"],
            test_points_payload=step2["test_points_payload"],
            orchestrator_result=step2["orchestrator_result"],
        )
        review_summary = step3["test_points_payload"].get("review_summary")
        if isinstance(review_summary, dict):
            review_summary["intent_coverage_status"] = "covered"
            review_summary["status"] = "covered"
            review_summary["orphan_point_count"] = 0
            review_summary["orphan_step_count"] = 0
        log_debug_event(logger=_LOGGER, event="runtime.generate.orchestrator_output",
                        trace_id=trace_id,
                        payload=_redact_generation_payload(step3["orchestrator_result"]))
        orchestrator_result = step3["orchestrator_result"]
        case_yaml = step1["case_yaml"]
        resolved_page = step1["resolved_page"]
        page_object = step3["page_object"]
        test_points = step2["test_points"]
        quality_gate = step1["quality_gate"]
        requirement_spec = step2["requirement_spec"]
    except Exception as exc:
        _handle_generation_exception(
            exc=exc, trace_id=trace_id, selected_intent_ids_list=selected_intent_ids_list,
            mode=mode, http_exception_cls=http_exception_cls,
            unprocessable_entity_status=unprocessable_entity_status,
            is_quality_gate_blocked=is_quality_gate_blocked, payload=payload,
            normalized_page=normalized_page, multisource_enabled=multisource_enabled,
            append_history=append_history, now_iso=now_iso)

    step4 = _allocate_and_format_case_id(
        payload=payload, case_yaml=case_yaml, resolved_page=resolved_page,
        normalized_page=normalized_page, allocate_case_id=allocate_case_id,
        ai_cases_root=ai_cases_root, existing_case_ids=existing_case_ids,
        page_object=page_object, execution_payload=case_yaml.get("execution", {}),
    )
    return _persist_and_build_response(
        payload=payload, case_yaml=step4["case_yaml"],
        resolved_page=resolved_page, final_page_url=step4["final_page_url"],
        case_id=step4["case_id"], page_object=page_object, test_points=test_points,
        candidate_snapshots=candidate_snapshots, requirement_spec=requirement_spec,
        selected_intent_ids_list=selected_intent_ids_list,
        selected_intent_ids=selected_intent_ids, effective_requirement=effective_requirement,
        write_case_yaml=write_case_yaml, save_case_state=save_case_state,
        save_test_point_plan=save_test_point_plan, now_iso=now_iso,
        append_history=append_history, multisource_enabled=multisource_enabled,
        quality_gate=quality_gate, orchestrator_result=orchestrator_result,
        trace_id=trace_id, http_exception_cls=http_exception_cls,
        unprocessable_entity_status=unprocessable_entity_status,
        mode=mode, ai_cases_root=ai_cases_root,
    )
