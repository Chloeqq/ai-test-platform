from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence, TypeAlias

from datetime_compat import UTC
from fastapi import HTTPException, status
from shared_backend.case_ids import (
    build_case_id,
    build_case_metadata,
    infer_client_code,
    match_case_id,
    next_case_sequence,
    normalize_case_id,
    normalize_case_type as normalize_business_case_type,
    normalize_client_code,
    normalize_source_code,
)
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session
import yaml

from app.models.page_object import PageObjectRef
from app.models.page_object import PageElement, PageObject
from app.models.test_case import (
    TestCase,
    TestCaseDefect,
    TestCaseExecution,
    TestCaseStep,
    TestCaseTreeNode,
    TestCaseVersion,
)
from app.models.test_project import TestProject
from app.schemas.test_case import (
    BatchStatusUpdatePayload,
    BatchTagsUpdatePayload,
    TestCaseCreate,
    TestCaseDataConfig,
    TestCaseScriptUpdate,
    TestCaseUpdate,
)
from app.services.test_case_bootstrap_service import (
    ensure_seed_data,
    get_module_tree_items as get_module_tree_items,
)
from app.services.test_case_data_service import (
    DataConfigPayload,
    compose_data_driven_script,
    generate_ai_script,
    normalize_case_ids,
    normalize_data_config,
    normalize_markers,
    normalize_optional_text,
    normalize_report_url as normalize_report_url,
    normalize_status,
    normalize_tags,
    normalize_test_case_type,
    normalize_test_steps,
    normalize_text_list,
    positive_ids,
    render_test_steps_text,
    refresh_existing_data_driven_script,
)
from app.services.test_case_search_service import (
    build_test_case_search_context,
    parse_test_case_search_query,
)
from app.services import test_project_service

PaginationPayload: TypeAlias = dict[str, int | bool | None]
FilterOptionsPayload: TypeAlias = dict[str, list[str]]
StatsPayload: TypeAlias = dict[str, int | float]

REPO_ROOT = Path(__file__).resolve().parents[4]
ASSETS_CASES_ROOT = REPO_ROOT / "assets" / "test-cases"
EXECUTION_REPORTS_ROOT = REPO_ROOT / "reports" / "executions"
DEFAULT_PROJECT_CODE = "mall"


@dataclass(frozen=True)
class TestCaseListResult:
    cases: list[TestCase]
    pagination: PaginationPayload
    filters: FilterOptionsPayload
    latest_versions: dict[int, int]
    search_context: dict[str, str]
    stats: StatsPayload
    project_statuses: dict[str, str]


@dataclass(frozen=True)
class TestCaseDetailResult:
    case: TestCase
    defects: list[TestCaseDefect]
    executions: list[TestCaseExecution]
    versions: list[TestCaseVersion]
    data_config: DataConfigPayload
    project_status: str


@dataclass(frozen=True)
class TestCaseMutationResult:
    case: TestCase
    data_config: DataConfigPayload
    script_code: str
    latest_version_no: int | None


@dataclass(frozen=True)
class TestCaseVersionComparison:
    from_version: int
    to_version: int
    added_lines: int
    removed_lines: int
    diff_lines: list[str]


def _normalize_project_code(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized or DEFAULT_PROJECT_CODE


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_step_text(value: Any) -> str:
    return str(value or "").strip()


def _resolve_step_locator(step: dict[str, Any]) -> tuple[str, str]:
    locator_type = _normalize_step_text(step.get("locator_type"))
    locator_value = _normalize_step_text(step.get("locator_value"))
    if locator_type and locator_value:
        return locator_type, locator_value
    target = _normalize_step_text(step.get("target"))
    if target.startswith("element:"):
        return "element", target.removeprefix("element:").strip()
    if ":" in target:
        prefix, suffix = target.split(":", 1)
        prefix = prefix.strip().lower()
        suffix = suffix.strip()
        if prefix and suffix and prefix in {"css", "xpath", "text", "role", "id", "name", "url", "element"}:
            return prefix, suffix
    return "", ""


def _sync_test_case_steps(db: Session, case: TestCase) -> None:
    steps = case.test_steps if isinstance(case.test_steps, list) else []
    db.execute(delete(TestCaseStep).where(TestCaseStep.case_id == int(case.id)))
    for index, raw_step in enumerate(steps, start=1):
        step = raw_step if isinstance(raw_step, dict) else {}
        action = _normalize_step_text(step.get("action"))
        target = _normalize_step_text(step.get("target"))
        locator_type, locator_value = _resolve_step_locator(step)
        step_data = _normalize_step_text(step.get("value"))
        expected_result = _normalize_step_text(step.get("expected_result")) or _normalize_step_text(step.get("description"))
        db.add(
            TestCaseStep(
                case_id=int(case.id),
                case_business_id=_normalize_step_text(case.case_id),
                project_code=_normalize_step_text(case.project_code) or DEFAULT_PROJECT_CODE,
                page_code=_normalize_step_text(case.page_code),
                step_index=index,
                action=action,
                target=target,
                locator_type=locator_type,
                locator_value=locator_value,
                step_data=step_data,
                expected_result=expected_result,
                raw_payload=step,
            )
        )


def _normalize_business_case_id(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = normalize_case_id(raw, fallback="").strip().lower()
    if not normalized or not match_case_id(normalized):
        return ""
    return normalized


def _ensure_project_exists(db: Session, project_code: str) -> None:
    normalized_project_code = _normalize_project_code(project_code)
    existing = db.execute(
        select(TestProject).where(TestProject.project_code == normalized_project_code)
    ).scalar_one_or_none()
    if existing:
        return
    db.add(
        TestProject(
            project_code=normalized_project_code,
            project_name=normalized_project_code.upper(),
            description="Auto-created from synchronized workbench generation",
            status="active",
            created_by="system",
        )
    )
    db.commit()


def _ensure_project_writable(db: Session, project_code: str) -> str:
    normalized_project_code = _normalize_project_code(project_code)
    # Keep backward compatibility for legacy paths that may write before explicit
    # project setup, while still enforcing inactive-project write protection.
    _ensure_project_exists(db, normalized_project_code)
    test_project_service.ensure_project_active_for_write(db, normalized_project_code)
    return normalized_project_code


def _workbench_steps(case_yaml: dict[str, Any]) -> list[dict[str, Any]]:
    execution = case_yaml.get("execution") if isinstance(case_yaml, dict) else {}
    if not isinstance(execution, dict):
        return []
    return normalize_test_steps(execution.get("steps") if isinstance(execution.get("steps"), list) else [])


def _normalize_match_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def _infer_step_action_for_repair(step: dict[str, Any]) -> str:
    raw_action = _normalize_step_text(step.get("action")).lower()
    action_aliases = {
        "fill": "input",
        "type": "input",
        "enter": "input",
        "input_text": "input",
        "tap": "click",
        "press": "click",
        "submit": "click",
        "login": "click",
        "assert": "assert_visible",
        "verify": "assert_visible",
        "check": "assert_visible",
        "validation": "assert_visible",
        "open": "goto",
        "navigate": "goto",
        "visit": "goto",
    }
    action = action_aliases.get(raw_action, raw_action)
    weak_actions = {
        "",
        "custom_step",
        "step",
        "flow",
        "action",
        "smoke",
        "negative",
        "positive",
        "scenario",
    }
    if action and action not in weak_actions:
        return action
    merged = " ".join(
        [
            _normalize_step_text(step.get("description")),
            _normalize_step_text(step.get("target")),
            _normalize_step_text(step.get("value")),
            _normalize_step_text(step.get("expected_result")),
        ]
    ).lower()
    if any(token in merged for token in ["输入", "填写", "fill", "type", "input"]):
        return "input"
    if any(token in merged for token in ["点击", "click", "submit", "提交"]):
        return "click"
    if any(token in merged for token in ["断言", "验证", "校验", "assert"]):
        return "assert_visible"
    if any(token in merged for token in ["打开", "访问", "open", "goto", "navigate"]):
        return "goto"
    if action:
        return action
    return "custom_step"


def _load_page_elements_for_step_repair(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
) -> list[PageElement]:
    normalized_project = _normalize_project_code(project_code)
    normalized_client = normalize_client_code(client or "web")
    normalized_page = str(page_code or "").strip().lower()
    if not normalized_page:
        return []
    page_object = db.execute(
        select(PageObject).where(
            PageObject.project_code == normalized_project,
            PageObject.client == normalized_client,
            PageObject.page_code == normalized_page,
        )
    ).scalar_one_or_none()
    if page_object is None:
        page_object = db.execute(
            select(PageObject)
            .where(PageObject.page_code == normalized_page)
            .order_by(PageObject.updated_at.desc())
        ).scalars().first()
    if page_object is None:
        return []
    return db.execute(
        select(PageElement)
        .where(PageElement.page_object_id == int(page_object.id))
        .order_by(PageElement.id.asc())
    ).scalars().all()


def _classify_login_element_role(element: PageElement) -> str:
    blob = _normalize_match_text(
        " ".join(
            [
                str(element.element_code or ""),
                str(element.element_name or ""),
                str(element.locator_value or ""),
                str(element.role or ""),
                str(element.business_type or ""),
            ]
        )
    )
    if any(token in blob for token in ["记住密码", "rememberpassword", "rememberme", "checkbox", "复选框"]):
        return "other"
    if any(
        token in blob
        for token in [
            "密码显隐",
            "显示密码",
            "隐藏密码",
            "明文",
            "密文",
            "passwordvisibility",
            "showpassword",
            "hidepassword",
            "togglepassword",
            "visibilitytoggle",
            "eyetoggle",
            "ipath3",
        ]
    ):
        return "password_toggle"
    if any(token in blob for token in ["用户名", "username", "account", "账号"]):
        return "username"
    if any(token in blob for token in ["密码", "password", "passwd"]):
        return "password"
    if any(token in blob for token in ["登录", "login", "submit", "btn", "button"]):
        return "login_button"
    if any(token in blob for token in ["错误", "提示", "error", "toast"]):
        return "error"
    if any(token in blob for token in ["首页", "home"]):
        return "home"
    return "other"


def _build_login_element_map(elements: list[PageElement]) -> dict[str, list[PageElement]]:
    result: dict[str, list[PageElement]] = {
        "username": [],
        "password": [],
        "password_toggle": [],
        "login_button": [],
        "error": [],
        "home": [],
        "other": [],
    }
    for element in elements:
        role = _classify_login_element_role(element)
        result.setdefault(role, []).append(element)
    return result


def _looks_like_login_step_payload(*, page_code: str, steps: Sequence[dict[str, Any]]) -> bool:
    normalized_page = str(page_code or "").strip().lower()
    if normalized_page == "login":
        return True
    merged = _normalize_match_text(
        " ".join(
            " ".join(
                [
                    _normalize_step_text(step.get("description")),
                    _normalize_step_text(step.get("target")),
                    _normalize_step_text(step.get("value")),
                    _normalize_step_text(step.get("expected_result")),
                    _normalize_step_text(step.get("locator_value")),
                ]
            )
            for step in steps
            if isinstance(step, dict)
        )
    )
    login_tokens = ["登录", "username", "password", "账号", "用户名", "密码", "login"]
    if any(token in merged for token in login_tokens):
        return True
    return False


def _has_login_key_elements(role_map: dict[str, list[PageElement]]) -> bool:
    return bool(role_map.get("username") and role_map.get("password") and role_map.get("login_button"))


def _score_login_role_element(element: PageElement, role: str) -> int:
    locator_type = str(element.locator_type or "").strip().lower()
    locator_value = _normalize_match_text(element.locator_value)
    element_name = _normalize_match_text(element.element_name)
    element_code = _normalize_match_text(element.element_code)
    role_text = _normalize_match_text(element.role)

    blob = " ".join([locator_value, element_name, element_code, role_text])
    score = 0

    if role == "username":
        if any(token in blob for token in ["用户名", "username", "account", "账号"]):
            score += 40
        if locator_type in {"role", "id", "name"}:
            score += 15
    elif role == "password":
        if any(token in blob for token in ["密码", "password", "passwd"]):
            score += 40
        if locator_type in {"role", "id", "name"}:
            score += 15
    elif role == "password_toggle":
        if any(
            token in blob
            for token in [
                "密码显隐",
                "显示密码",
                "隐藏密码",
                "明文",
                "密文",
                "passwordvisibility",
                "showpassword",
                "hidepassword",
                "toggle",
                "eye",
                "icon",
                "ipath3",
            ]
        ):
            score += 45
        if locator_type in {"css", "role", "id", "name"}:
            score += 15
    elif role == "login_button":
        if any(token in blob for token in ["登录", "login", "submit", "提交"]):
            score += 45
        if any(token in blob for token in ["按钮", "button", "btn"]):
            score += 20
        if locator_type in {"role", "text", "id", "name"}:
            score += 20
        elif locator_type == "css":
            score += 5
        if any(token in blob for token in ["ipath", "svg", "icon"]):
            score -= 35
    else:
        if locator_type in {"role", "text", "id", "name"}:
            score += 5

    if locator_value:
        score += max(0, 12 - min(12, len(locator_value) // 8))
    return score


def _best_role_element(role_map: dict[str, list[PageElement]], role: str) -> PageElement | None:
    candidates = role_map.get(role) or []
    if not candidates:
        return None
    return max(candidates, key=lambda item: _score_login_role_element(item, role))


def _pick_login_element_for_step(
    *,
    step: dict[str, Any],
    role_map: dict[str, list[PageElement]],
    input_index: int,
) -> tuple[PageElement | None, str]:
    action = _infer_step_action_for_repair(step)
    all_elements = [item for items in role_map.values() for item in items]
    matched_by_target: tuple[PageElement, str] | None = None
    matched_by_locator: tuple[PageElement, str] | None = None
    raw_target = _normalize_step_text(step.get("target"))
    if raw_target.startswith("element:"):
        expected_code = raw_target.removeprefix("element:").strip().lower()
        for candidate in all_elements:
            code = str(candidate.element_code or "").strip().lower()
            if code and code == expected_code:
                matched_by_target = (candidate, _classify_login_element_role(candidate))
                break
    raw_locator_value = _normalize_step_text(step.get("locator_value"))
    if raw_locator_value and action in {"input", "fill", "type", "custom_step"}:
        locator_key = _normalize_match_text(raw_locator_value)
        for candidate in all_elements:
            if _normalize_match_text(candidate.locator_value) == locator_key:
                matched_by_locator = (candidate, _classify_login_element_role(candidate))
                break
    merged = _normalize_match_text(
        " ".join(
            [
                _normalize_step_text(step.get("description")),
                _normalize_step_text(step.get("target")),
                _normalize_step_text(step.get("value")),
                _normalize_step_text(step.get("expected_result")),
            ]
        )
    )
    desired_role = ""
    if action in {"input", "fill", "type"}:
        if any(token in merged for token in ["密码", "password", "passwd"]):
            desired_role = "password"
        elif any(token in merged for token in ["用户名", "username", "account", "账号"]):
            desired_role = "username"
        else:
            desired_role = "username" if input_index == 0 else "password"
    elif action == "click":
        if any(
            token in merged
            for token in [
                "密码显隐",
                "显示密码",
                "隐藏密码",
                "明文",
                "密文",
                "passwordvisibility",
                "showpassword",
                "hidepassword",
                "togglepassword",
                "eyetoggle",
                "visibilitytoggle",
            ]
        ):
            desired_role = "password_toggle"
        elif any(token in merged for token in ["登录", "login", "submit", "提交"]) or not _normalize_step_text(step.get("target")):
            desired_role = "login_button"
    elif action in {"assert_visible", "wait_for", "assert_text"}:
        if any(token in merged for token in ["错误", "提示", "error", "toast"]):
            desired_role = "error"
        elif any(token in merged for token in ["首页", "home"]):
            desired_role = "home"

    if matched_by_target is not None and matched_by_target[1] not in {"other", "password_toggle"}:
        if not desired_role or desired_role == matched_by_target[1]:
            return matched_by_target

    if desired_role and role_map.get(desired_role):
        best = _best_role_element(role_map, desired_role)
        if best is not None:
            return best, desired_role
    if action in {"input", "fill", "type"} and role_map.get("username"):
        if input_index == 0:
            best = _best_role_element(role_map, "username")
            if best is not None:
                return best, "username"
        if role_map.get("password"):
            best = _best_role_element(role_map, "password")
            if best is not None:
                return best, "password"
        best = _best_role_element(role_map, "username")
        if best is not None:
            return best, "username"
    if action == "click" and role_map.get("login_button"):
        best = _best_role_element(role_map, "login_button")
        if best is not None:
            return best, "login_button"
    if matched_by_target is not None:
        return matched_by_target
    if matched_by_locator is not None:
        return matched_by_locator
    return None, ""


def _build_login_scenario_context(text: str) -> dict[str, bool]:
    merged = _normalize_match_text(text)
    positive = any(
        token in merged
        for token in [
            "首次登录成功",
            "登录成功",
            "正确账号密码",
            "正确的账号密码",
            "跳转至平台工作台首页",
            "跳转到平台工作台首页",
            "跳转至工作台首页",
            "跳转到工作台首页",
        ]
    )
    negative = any(
        token in merged
        for token in [
            "失败",
            "错误",
            "异常",
            "为空",
            "空值",
            "非法",
            "锁定",
            "禁止",
            "未成功",
            "超时",
            "negative",
            "invalid",
            "wrong",
            "lock",
            "forbidden",
            "timeout",
            "提示",
        ]
    ) and not positive
    return {
        "negative": negative,
        "lock": not positive and any(token in merged for token in ["锁定", "lock"]),
        "empty_username": not positive and (("用户名" in merged and "为空" in merged) or "usernameempty" in merged),
        "empty_password": not positive and (("密码" in merged and "为空" in merged) or "passwordempty" in merged),
        "wrong_username": not positive and (("用户名" in merged and "错误" in merged) or "wrongusername" in merged),
        "wrong_password": not positive and (("密码" in merged and "错误" in merged) or "wrongpassword" in merged),
        "over_limit_username": not positive and (("用户名" in merged and any(token in merged for token in ["超长", "超限", "超过", "长度"])) or "usernametoolong" in merged),
        "over_limit_password": not positive and (("密码" in merged and any(token in merged for token in ["超长", "超限", "超过", "长度"])) or "passwordtoolong" in merged),
    }


def _default_expected_for_login_step(role: str, action: str, scenario_context: dict[str, bool]) -> str:
    if role == "username" and action in {"input", "fill", "type"}:
        return "用户名输入框内容正确显示"
    if role == "password" and action in {"input", "fill", "type"}:
        return "密码输入框内容正确显示（掩码）"
    if role == "password_toggle" and action == "click":
        return "密码输入框在明文与掩码之间切换成功"
    if role == "login_button" and action == "click":
        if scenario_context.get("lock"):
            return "登录失败，页面提示“账号已锁定，请稍后重试”"
        if scenario_context.get("empty_username"):
            return "登录失败，页面提示“用户名不能为空”"
        if scenario_context.get("empty_password"):
            return "登录失败，页面提示“密码不能为空”"
        if scenario_context.get("wrong_username") or scenario_context.get("wrong_password"):
            return "登录失败，页面提示“账号或密码错误”"
        if scenario_context.get("over_limit_username"):
            return "登录失败，页面提示“用户名长度超出限制”"
        if scenario_context.get("over_limit_password"):
            return "登录失败，页面提示“密码长度超出限制”"
        if scenario_context.get("negative"):
            return "登录失败，页面展示与当前场景匹配的错误提示"
        return "页面跳转到首页，显示已登录状态"
    if role == "error" and action in {"assert_visible", "wait_for"}:
        if scenario_context.get("negative"):
            return "显示与场景匹配的错误提示信息"
        return "关键提示信息可见"
    return ""


def _is_positive_login_expected(value: str) -> bool:
    normalized = _normalize_match_text(value)
    return any(token in normalized for token in ["跳转", "首页", "已登录", "token", "会话状态正常", "登录成功"])


def _is_negative_login_expected(value: str) -> bool:
    normalized = _normalize_match_text(value)
    return any(token in normalized for token in ["登录失败", "错误提示", "账号或密码错误", "未成功", "锁定", "超时"])


def _is_weak_login_locator(locator_type: str, locator_value: str) -> bool:
    normalized_type = str(locator_type or "").strip().lower()
    normalized_value = _normalize_match_text(locator_value)
    if not normalized_type or not normalized_value:
        return True
    if normalized_type in {"role", "text", "placeholder"} and any(
        token in normalized_value
        for token in ["请输入", "placeholder", "用户名输入框", "密码输入框", "输入用户名", "输入密码"]
    ):
        return True
    return False


def _stable_locator_for_login_role(*, role: str, locator_type: str, locator_value: str) -> tuple[str, str]:
    if not _is_weak_login_locator(locator_type, locator_value):
        return locator_type, locator_value
    if role == "username":
        return (
            "css",
            "input[name='username'], #username, #username-input, "
            "input[placeholder*='请输入用户名'], input[placeholder*='用户名']",
        )
    if role == "password":
        return (
            "css",
            "input[type='password'], input[name='password'], #password, #password-input, "
            "input[placeholder*='请输入密码'], input[placeholder*='密码']",
        )
    if role == "login_button":
        return "css", "button[type='submit'], #login-btn, .login-button, .el-button--primary"
    return locator_type, locator_value


def _friendly_target_name_for_login(role: str, element: PageElement) -> str:
    if role == "username":
        return "用户名输入框"
    if role == "password":
        return "密码输入框"
    if role == "password_toggle":
        return "密码显隐开关"
    if role == "login_button":
        return "登录按钮"
    if role == "error":
        return "错误提示"
    if role == "home":
        return "首页关键元素"
    return str(element.element_name or "").strip() or str(element.element_code or "").strip()


def _dedupe_exact_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in steps:
        signature = "||".join(
            [
                _normalize_step_text(item.get("action")).lower(),
                _normalize_step_text(item.get("target")),
                _normalize_step_text(item.get("locator_type")).lower(),
                _normalize_step_text(item.get("locator_value")),
                _normalize_step_text(item.get("value")),
                _normalize_step_text(item.get("expected_result")),
            ]
        )
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(item)
    return deduped


def _repair_execution_steps_for_storage(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
    steps: list[dict[str, Any]],
    scenario_context_text: str = "",
) -> list[dict[str, Any]]:
    if not steps:
        return []
    repaired_steps = [dict(item) for item in steps if isinstance(item, dict)]
    if not _env_flag("AUTO_RETRY_FIX_ENABLED", True):
        return repaired_steps
    auto_fill_locator_enabled = _env_flag("AUTO_FILL_LOCATOR_ENABLED", True)
    auto_fix_expected_enabled = _env_flag("AUTO_FIX_EXPECTED_ENABLED", True)
    normalized_page = str(page_code or "").strip().lower()
    if not _looks_like_login_step_payload(page_code=normalized_page, steps=repaired_steps):
        return _dedupe_exact_steps(repaired_steps)
    candidate_pages: list[str] = []
    if normalized_page:
        candidate_pages.append(normalized_page)
    if "login" not in candidate_pages:
        candidate_pages.append("login")

    role_map: dict[str, list[PageElement]] | None = None
    for candidate_page in candidate_pages:
        elements = _load_page_elements_for_step_repair(
            db,
            project_code=project_code,
            client=client,
            page_code=candidate_page,
        )
        if not elements:
            continue
        candidate_role_map = _build_login_element_map(elements)
        if _has_login_key_elements(candidate_role_map):
            role_map = candidate_role_map
            break
        if role_map is None and any(candidate_role_map.values()):
            role_map = candidate_role_map
    if role_map is None:
        return _dedupe_exact_steps(repaired_steps)

    login_input_index = 0
    scenario_context = _build_login_scenario_context(scenario_context_text)
    normalized: list[dict[str, Any]] = []
    for step in repaired_steps:
        action = _infer_step_action_for_repair(step)
        if action:
            step["action"] = action
        element, role = _pick_login_element_for_step(
            step=step,
            role_map=role_map,
            input_index=login_input_index,
        )
        if action in {"input", "fill", "type"}:
            login_input_index += 1
        if element is not None:
            if auto_fill_locator_enabled:
                step["target"] = f"element:{str(element.element_code or '').strip()}"
                raw_locator_type = str(element.locator_type or "").strip()
                raw_locator_value = str(element.locator_value or "").strip()
                fixed_locator_type, fixed_locator_value = _stable_locator_for_login_role(
                    role=role,
                    locator_type=raw_locator_type,
                    locator_value=raw_locator_value,
                )
                step["locator_type"] = fixed_locator_type
                step["locator_value"] = fixed_locator_value
                step["target_name"] = _friendly_target_name_for_login(role, element)
            if auto_fill_locator_enabled and action in {"input", "fill", "type"} and _normalize_step_text(step.get("value")) == "":
                # 账号密码必须来自测试资产或用例脚本；自动修复只补定位器，不生成测试数据。
                step.pop("value", None)
            if auto_fix_expected_enabled:
                current_expected = _normalize_step_text(step.get("expected_result"))
                if (
                    not current_expected
                    or (scenario_context.get("negative") and _is_positive_login_expected(current_expected))
                    or (not scenario_context.get("negative") and role == "login_button" and action == "click" and _is_negative_login_expected(current_expected))
                ):
                    expected = _default_expected_for_login_step(role, action, scenario_context)
                    if expected:
                        step["expected_result"] = expected
        normalized.append(step)
    return _dedupe_exact_steps(normalized)


def _repair_expected_result_for_storage(
    *,
    expected_result: str,
    steps: Sequence[dict[str, Any]],
    scenario_context_text: str = "",
) -> str:
    normalized_expected = normalize_optional_text(expected_result)
    if not _env_flag("AUTO_RETRY_FIX_ENABLED", True):
        return normalized_expected
    if not _env_flag("AUTO_FIX_EXPECTED_ENABLED", True):
        return normalized_expected
    scenario_context = _build_login_scenario_context(scenario_context_text)
    generic_tokens = [
        "系统应给出符合业务规则的反馈",
        "符合业务规则的反馈",
        "系统应提示",
    ]
    if normalized_expected and not any(token in normalized_expected for token in generic_tokens):
        return normalized_expected

    candidates: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        value = normalize_optional_text(step.get("expected_result")) or normalize_optional_text(step.get("expected"))
        if value and value not in candidates:
            candidates.append(value)
    if candidates:
        if scenario_context.get("negative"):
            for candidate in candidates:
                if any(token in candidate for token in ["失败", "错误", "不能为空", "锁定", "非法", "超出", "拦截", "提示"]):
                    return candidate[:260]
            if scenario_context.get("lock"):
                return "登录失败，页面提示“账号已锁定，请稍后重试”"
        for candidate in candidates:
            if any(token in candidate for token in ["跳转", "登录", "已登录", "token", "Token"]):
                if scenario_context.get("negative"):
                    continue
                return candidate[:260]
        if len(candidates) == 1:
            return candidates[0][:260]
        return "；".join(candidates[:2])[:260]
    return normalized_expected


def _sanitize_workbench_script_code_for_storage(
    script_code: str,
    *,
    steps: Sequence[dict[str, Any]] | None = None,
    expected_result: str = "",
) -> str:
    raw_script = str(script_code or "")
    if "requirement:" not in raw_script:
        return raw_script
    try:
        parsed = yaml.safe_load(raw_script)
    except yaml.YAMLError:
        return raw_script
    if not isinstance(parsed, dict):
        return raw_script
    if not any(key in parsed for key in ("id", "title", "execution", "module")):
        return raw_script
    if steps is not None:
        execution = parsed.get("execution") if isinstance(parsed.get("execution"), dict) else {}
        execution["steps"] = [dict(step) for step in steps if isinstance(step, dict)]
        parsed["execution"] = execution
    normalized_expected = normalize_optional_text(expected_result)
    if normalized_expected:
        parsed["expected_result"] = normalized_expected
    return _workbench_yaml_script(parsed)


def _repair_case_detail_payload_in_storage(db: Session, *, case: TestCase) -> None:
    if not _env_flag("AUTO_RETRY_FIX_ENABLED", True):
        return
    raw_steps = case.test_steps if isinstance(case.test_steps, list) else []
    scenario_context_text = " ".join(
        [
            normalize_optional_text(case.name),
            normalize_optional_text(case.expected_result),
            normalize_optional_text(case.notes),
            normalize_optional_text(case.test_steps_text),
        ]
    ).strip()
    repaired_steps = _repair_execution_steps_for_storage(
        db,
        project_code=case.project_code,
        client=case.client,
        page_code=case.page_code or case.product_line,
        steps=raw_steps,
        scenario_context_text=scenario_context_text,
    )
    repaired_expected_result = _repair_expected_result_for_storage(
        expected_result=case.expected_result,
        steps=repaired_steps,
        scenario_context_text=scenario_context_text,
    )
    repaired_script_code = _sanitize_workbench_script_code_for_storage(
        case.script_code or "",
        steps=repaired_steps,
        expected_result=repaired_expected_result,
    )

    changed = False
    if repaired_steps != raw_steps:
        case.test_steps = repaired_steps
        case.test_steps_text = render_test_steps_text(repaired_steps)
        changed = True
    if repaired_expected_result and repaired_expected_result != normalize_optional_text(case.expected_result):
        case.expected_result = repaired_expected_result
        changed = True
    if repaired_script_code and repaired_script_code != str(case.script_code or ""):
        case.script_code = repaired_script_code
        sync_generated_case_yaml_file(case.source_ref, repaired_script_code)
        changed = True

    if not changed:
        return

    case.updated_at = datetime.now(UTC)
    db.add(case)
    _sync_test_case_steps(db, case)
    db.commit()
    db.refresh(case)


def _compact_workbench_requirement_line(value: str) -> str:
    text = str(value or "").replace("\r", "\n").strip()
    text = text.replace("\u3000", " ")
    text = re.sub(r"^\s*(?:[-*•·]+\s*|\d+\s*[.)、]\s*)", "", text)
    text = re.sub(r"^\[(?:p\d|P\d)(?:/[a-z_]+)?\]\s*", "", text)
    text = text.replace('"', "").replace("'", "").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) <= 220:
        return text
    segments = [item.strip() for item in re.split(r"[。；;]", text) if item.strip()]
    return (segments[0] if segments else text[:220]).strip()[:220]


def _looks_like_workbench_requirement_noise(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    normalized = text.lower()
    noise_tokens = [
        "原始需求",
        "结构化测试点",
        "请基于以上测试点生成稳定可执行",
        "业务规则",
        "需求消歧",
        "requirement_overview",
        "analysis_time",
        "page_elements",
        "business_objects",
        "operations",
        "source-",
        "intent-",
    ]
    if any(token in normalized for token in noise_tokens):
        return True
    if re.match(r"^【(模块|页面|功能描述|涉及元素|优先级|前置条件)】", text):
        return True
    if re.search(r'"(name|type|attribute|related_entity|page_elements|business_objects|operations)"\s*:', normalized):
        return True
    if re.match(r'^[a-z_][\w-]*"\s*:\s*', normalized):
        return True
    if text.startswith("{") or text.endswith("}") or text.endswith("},") or text.endswith(":") or text.endswith("："):
        return True
    return False


def _sanitize_workbench_requirement_lines(
    values: Sequence[Any] | None,
    *,
    fallback_text: str = "",
    max_items: int = 8,
) -> list[str]:
    normalized: list[str] = []
    dedupe: set[str] = set()

    def _append(raw: Any) -> None:
        for line in str(raw or "").replace("\r", "\n").split("\n"):
            compact = _compact_workbench_requirement_line(line)
            if not compact or _looks_like_workbench_requirement_noise(compact):
                continue
            dedupe_key = compact.lower()
            if dedupe_key in dedupe:
                continue
            dedupe.add(dedupe_key)
            normalized.append(compact)
            if len(normalized) >= max_items:
                return

    for item in values or []:
        _append(item)
        if len(normalized) >= max_items:
            break

    if not normalized and str(fallback_text).strip():
        _append(fallback_text)
    return normalized[:max_items]


def _sanitize_workbench_requirement_object(value: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = ("intent_id", "title", "type", "precondition", "source_asset_id")
    sanitized: dict[str, Any] = {}
    for key in allowed_keys:
        text = normalize_optional_text(value.get(key))
        if text:
            sanitized[key] = text
    return sanitized


def _workbench_requirement_lines_from_object(value: dict[str, Any]) -> list[str]:
    requirement = _sanitize_workbench_requirement_object(value)
    rows: list[str] = []
    label_pairs = [
        ("intent_id", "测试点ID"),
        ("title", "测试点标题"),
        ("type", "测试类型"),
        ("precondition", "前置条件"),
        ("source_asset_id", "来源资产"),
    ]
    for key, label in label_pairs:
        text = normalize_optional_text(requirement.get(key))
        if text:
            rows.append(f"{label}：{text}")
    return rows


def _extract_requirement_value_from_lines(lines: Sequence[Any], *prefixes: str) -> str:
    normalized_prefixes = tuple(str(prefix or "").strip() for prefix in prefixes if str(prefix or "").strip())
    if not normalized_prefixes:
        return ""
    for raw in lines:
        for line in str(raw or "").replace("\r", "\n").split("\n"):
            text = line.strip().lstrip("-*•·").strip()
            for prefix in normalized_prefixes:
                if text.startswith(prefix):
                    return text[len(prefix):].strip()
    return ""


def _append_unique_identity_value(target: list[str], value: Any) -> None:
    text = normalize_optional_text(value)
    if text and text not in target:
        target.append(text)


def _normalize_source_asset_identity(value: Any) -> str:
    text = normalize_optional_text(value).lower()
    return _normalize_business_case_id(text) or text


def _workbench_source_identity(case_yaml: dict[str, Any]) -> tuple[str, list[str]]:
    if not isinstance(case_yaml, dict):
        return "", []
    source_asset_id = normalize_optional_text(case_yaml.get("source_asset_id"))
    intent_ids: list[str] = []
    raw_requirement = case_yaml.get("requirement")
    if isinstance(raw_requirement, dict):
        source_asset_id = source_asset_id or normalize_optional_text(raw_requirement.get("source_asset_id"))
        _append_unique_identity_value(intent_ids, raw_requirement.get("intent_id"))
    else:
        lines = raw_requirement if isinstance(raw_requirement, list) else ([raw_requirement] if raw_requirement is not None else [])
        source_asset_id = source_asset_id or _extract_requirement_value_from_lines(
            lines,
            "来源资产：",
            "来源资产:",
            "source_asset_id：",
            "source_asset_id:",
        )
        _append_unique_identity_value(
            intent_ids,
            _extract_requirement_value_from_lines(
                lines,
                "测试点ID：",
                "测试点ID:",
                "intent_id：",
                "intent_id:",
            ),
        )
    execution = case_yaml.get("execution") if isinstance(case_yaml.get("execution"), dict) else {}
    selected_ids = execution.get("selected_intent_ids") if isinstance(execution.get("selected_intent_ids"), list) else []
    for intent_id in selected_ids:
        _append_unique_identity_value(intent_ids, intent_id)
    return source_asset_id, intent_ids


def _load_case_yaml_from_script(script_code: Any) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(str(script_code or "")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _derive_case_projection_from_script(script_code: Any) -> dict[str, Any]:
    """Derive display-only case fields from the canonical YAML script."""
    case_yaml = _load_case_yaml_from_script(script_code)
    if not case_yaml:
        return {}
    steps = _workbench_steps(case_yaml)
    requirement_lines = _workbench_requirement(case_yaml)
    expected_result = (
        normalize_optional_text(case_yaml.get("expected_result"))
        or "\n".join(requirement_lines)
        or normalize_optional_text(case_yaml.get("description"))
    )
    return {
        "precondition_state": normalize_optional_text(case_yaml.get("precondition_state")),
        "test_steps": steps,
        "test_steps_text": render_test_steps_text(steps),
        "expected_result": expected_result,
    }


def _find_existing_workbench_case_by_source_identity(
    db: Session,
    *,
    project_code: str,
    source_asset_id: str,
    intent_id: str,
) -> TestCase | None:
    normalized_project = _normalize_project_code(project_code)
    normalized_asset = _normalize_source_asset_identity(source_asset_id)
    normalized_intent = normalize_optional_text(intent_id)
    if not normalized_project or not normalized_asset or not normalized_intent:
        return None
    candidates = db.execute(
        select(TestCase)
        .where(TestCase.project_code == normalized_project)
        .order_by(TestCase.updated_at.desc(), TestCase.id.desc())
    ).scalars().all()
    for candidate in candidates:
        candidate_asset, candidate_intents = _workbench_source_identity(
            _load_case_yaml_from_script(candidate.script_code)
        )
        if _normalize_source_asset_identity(candidate_asset) == normalized_asset and normalized_intent in candidate_intents:
            return candidate
    return None


def _legacy_requirement_object(case_yaml: dict[str, Any]) -> dict[str, Any]:
    raw_requirement = case_yaml.get("requirement")
    lines = raw_requirement if isinstance(raw_requirement, list) else ([raw_requirement] if raw_requirement is not None else [])
    sanitized_lines = _sanitize_workbench_requirement_lines(lines, fallback_text="")
    legacy_title = ""
    for line in sanitized_lines:
        if line in {"登录功能", "登录功能："}:
            continue
        legacy_title = line
        break
    execution = case_yaml.get("execution") if isinstance(case_yaml.get("execution"), dict) else {}
    selected_ids = execution.get("selected_intent_ids") if isinstance(execution.get("selected_intent_ids"), list) else []
    intent_id = (
        _extract_requirement_value_from_lines(lines, "测试点ID：", "测试点ID:")
        or (normalize_optional_text(selected_ids[0]) if selected_ids else "")
    )
    title = (
        _extract_requirement_value_from_lines(lines, "测试点标题：", "测试点标题:", "测试意图：", "测试意图:")
        or legacy_title
        or normalize_optional_text(case_yaml.get("title"))
    )
    intent_type = _extract_requirement_value_from_lines(lines, "测试类型：", "测试类型:") or "functional"
    precondition = _extract_requirement_value_from_lines(lines, "前置条件：", "前置条件:")
    source_asset_id = normalize_optional_text(case_yaml.get("source_asset_id"))
    return _sanitize_workbench_requirement_object(
        {
            "intent_id": intent_id,
            "title": title,
            "type": intent_type,
            "precondition": precondition,
            "source_asset_id": source_asset_id,
        }
    )


def _target_code_from_step(step: dict[str, Any]) -> str:
    target = normalize_optional_text(step.get("target"))
    if target.startswith("element:"):
        return target.removeprefix("element:").strip()
    return target


def _friendly_step_target_name(step: dict[str, Any]) -> str:
    target_name = normalize_optional_text(step.get("target_name"))
    if target_name:
        return target_name
    target_code = _target_code_from_step(step)
    if target_code == "username_input":
        return "用户名输入框"
    if target_code == "password_input":
        return "密码输入框"
    if target_code == "login_button":
        return "登录按钮"
    return target_code


def _workbench_step_locator(step: dict[str, Any]) -> tuple[str, str]:
    locator_type = normalize_optional_text(step.get("locator_type"))
    locator_value = normalize_optional_text(step.get("locator_value")) or normalize_optional_text(step.get("selector"))
    return locator_type, locator_value


def _productize_workbench_steps_for_script(case_yaml: dict[str, Any]) -> list[dict[str, Any]]:
    execution = case_yaml.get("execution") if isinstance(case_yaml.get("execution"), dict) else {}
    steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
    expected_result = normalize_optional_text(case_yaml.get("expected_result"))
    product_steps: list[dict[str, Any]] = []
    non_navigation_indexes = [
        index
        for index, raw in enumerate(steps)
        if isinstance(raw, dict) and normalize_optional_text(raw.get("action")).lower() not in {"goto", "login"}
    ]
    final_step_index = non_navigation_indexes[-1] if non_navigation_indexes else -1
    for index, raw in enumerate(steps):
        if not isinstance(raw, dict):
            continue
        raw_action = normalize_optional_text(raw.get("action")).lower()
        action = "input" if raw_action in {"fill", "type"} else (raw_action or "custom_step")
        if action == "goto":
            value = normalize_optional_text(raw.get("value") or raw.get("target"))
            product_steps.append(
                {
                    "action": "goto",
                    "value": value,
                    "expected_result": normalize_optional_text(raw.get("expected_result")) or "页面加载完成",
                }
            )
            continue
        target_code = _target_code_from_step(raw)
        locator_type, locator_value = _workbench_step_locator(raw)
        target_name = _friendly_step_target_name(raw)
        step: dict[str, Any] = {
            "action": action,
            "target": f"element:{target_code}" if target_code else "",
            "locator_type": locator_type,
            "locator_value": locator_value,
            "target_name": target_name,
        }
        if raw.get("value") is not None:
            step["value"] = raw.get("value")
        step_expected = normalize_optional_text(raw.get("expected_result") or raw.get("expected"))
        if index == final_step_index and expected_result:
            step_expected = expected_result
        if step_expected:
            step["expected_result"] = step_expected
        product_steps.append(step)
    return product_steps


def _coerce_workbench_case_yaml_for_script(case_yaml: dict[str, Any]) -> dict[str, Any]:
    payload = _sanitize_workbench_case_yaml_for_storage(case_yaml)
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
    page_url = normalize_optional_text(execution.get("page_url"))
    if not page_url:
        for step in steps:
            if isinstance(step, dict) and normalize_optional_text(step.get("action")).lower() == "goto":
                page_url = normalize_optional_text(step.get("value") or step.get("target"))
                if page_url:
                    break
    product_execution = {
        "runner": normalize_optional_text(execution.get("runner")) or "playwright",
        "page": normalize_optional_text(execution.get("page") or payload.get("module")) or "common",
        "page_url": page_url,
        "variables": execution.get("variables") if isinstance(execution.get("variables"), dict) else {},
        "steps": _productize_workbench_steps_for_script(payload),
        "selected_intent_ids": execution.get("selected_intent_ids") if isinstance(execution.get("selected_intent_ids"), list) else [],
    }
    payload["version"] = "v1"
    payload["execution"] = product_execution
    if not isinstance(payload.get("requirement"), dict):
        legacy_requirement = _legacy_requirement_object(payload)
        if legacy_requirement:
            payload["requirement"] = legacy_requirement
    ordered: dict[str, Any] = {}
    for key in (
        "version",
        "id",
        "project",
        "module",
        "title",
        "priority",
        "tags",
        "owner",
        "status",
        "description",
        "requirement",
        "data",
        "execution",
        "expected_result",
    ):
        if key in payload:
            ordered[key] = payload[key]
    for key, value in payload.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def _sanitize_workbench_case_yaml_for_storage(case_yaml: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(case_yaml, dict):
        return {}
    if not _env_flag("POST_PROCESSING_ENABLED", True):
        return dict(case_yaml)
    sanitized = dict(case_yaml)
    raw_requirement = sanitized.get("requirement")
    if isinstance(raw_requirement, dict):
        structured_requirement = _sanitize_workbench_requirement_object(raw_requirement)
        if structured_requirement:
            sanitized["requirement"] = structured_requirement
        return sanitized
    if isinstance(raw_requirement, list):
        requirement_values = raw_requirement
    elif raw_requirement is None:
        requirement_values = []
    else:
        requirement_values = [raw_requirement]
    fallback_text = normalize_optional_text(sanitized.get("description")) or normalize_optional_text(sanitized.get("title"))
    sanitized_requirement = _sanitize_workbench_requirement_lines(requirement_values, fallback_text=fallback_text)
    if sanitized_requirement:
        sanitized["requirement"] = sanitized_requirement
        description = normalize_optional_text(sanitized.get("description"))
        if (
            not description
            or _looks_like_workbench_requirement_noise(description)
            or len(description) > 260
        ):
            fallback_description = normalize_optional_text(sanitized.get("title"))
            if fallback_description and not _looks_like_workbench_requirement_noise(fallback_description):
                sanitized["description"] = fallback_description[:260]
            else:
                sanitized["description"] = sanitized_requirement[0][:260]
    return sanitized


def _workbench_requirement(case_yaml: dict[str, Any]) -> list[str]:
    if not isinstance(case_yaml, dict):
        return []
    if not _env_flag("POST_PROCESSING_ENABLED", True):
        raw_requirement = case_yaml.get("requirement")
        if isinstance(raw_requirement, list):
            return [str(item).strip() for item in raw_requirement if str(item).strip()]
        if raw_requirement is None:
            return []
        text = str(raw_requirement).strip()
        return [text] if text else []
    raw_requirement = case_yaml.get("requirement")
    if isinstance(raw_requirement, dict):
        return _workbench_requirement_lines_from_object(raw_requirement)
    if isinstance(raw_requirement, list):
        requirement_values = raw_requirement
    elif raw_requirement is None:
        requirement_values = []
    else:
        requirement_values = [raw_requirement]
    fallback_text = normalize_optional_text(case_yaml.get("description")) or normalize_optional_text(case_yaml.get("title"))
    return _sanitize_workbench_requirement_lines(requirement_values, fallback_text=fallback_text)


def _workbench_yaml_script(case_yaml: dict[str, Any]) -> str:
    if not isinstance(case_yaml, dict):
        return ""
    payload = _coerce_workbench_case_yaml_for_script(case_yaml)
    if not _env_flag("POST_PROCESSING_ENABLED", True):
        payload = dict(case_yaml)
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False).strip() + "\n"


def sync_generated_case_yaml_file(source_ref: str, script_code: str) -> bool:
    """Keep the runner YAML aligned with the case-center post-processed script."""
    raw_source_ref = normalize_optional_text(source_ref)
    normalized_script_code = str(script_code or "").strip()
    if not raw_source_ref or not normalized_script_code:
        return False

    candidate_path = Path(raw_source_ref).expanduser()
    if not candidate_path.is_absolute():
        candidate_path = REPO_ROOT / candidate_path
    try:
        resolved_path = candidate_path.resolve()
        resolved_root = ASSETS_CASES_ROOT.resolve()
        resolved_path.relative_to(resolved_root)
    except Exception:
        return False

    if resolved_path.suffix.lower() not in {".yaml", ".yml"}:
        return False

    next_content = normalized_script_code + "\n"
    try:
        if resolved_path.exists() and resolved_path.read_text(encoding="utf-8") == next_content:
            return True
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path.write_text(next_content, encoding="utf-8")
        return True
    except OSError:
        return False


def _existing_asset_case_ids() -> list[str]:
    if not ASSETS_CASES_ROOT.exists():
        return []
    return [path.stem for path in ASSETS_CASES_ROOT.rglob("*.yaml")]


def _delete_case_asset_files(case_ids: Sequence[str]) -> list[str]:
    if not ASSETS_CASES_ROOT.exists():
        return []
    target_case_ids = {
        _normalize_business_case_id(item)
        for item in case_ids
        if _normalize_business_case_id(item)
    }
    if not target_case_ids:
        return []
    removed_paths: list[str] = []
    for yaml_path in ASSETS_CASES_ROOT.rglob("*.yaml"):
        normalized_stem = _normalize_business_case_id(yaml_path.stem)
        if normalized_stem not in target_case_ids:
            continue
        yaml_path.unlink(missing_ok=True)
        removed_paths.append(str(yaml_path))
    return removed_paths


def _delete_execution_report_files(case_ids: Sequence[str]) -> list[str]:
    if not EXECUTION_REPORTS_ROOT.exists():
        return []
    target_case_ids = {
        _normalize_business_case_id(item)
        for item in case_ids
        if _normalize_business_case_id(item)
    }
    if not target_case_ids:
        return []
    removed_paths: list[str] = []
    for case_id in sorted(target_case_ids):
        report_json = EXECUTION_REPORTS_ROOT / f"{case_id}.report.json"
        report_md = EXECUTION_REPORTS_ROOT / f"{case_id}.report.md"
        for report_path in (report_json, report_md):
            if not report_path.exists():
                continue
            report_path.unlink(missing_ok=True)
            removed_paths.append(str(report_path))
    return removed_paths


def _is_ddt_case(case: TestCase) -> bool:
    case_id_value = str(case.case_id or "").strip().lower()
    name_value = str(case.name or "").strip().lower()
    if "ddt" in case_id_value or "ddt" in name_value:
        return True
    tags = [str(item or "").strip().lower() for item in (case.tags or [])]
    if any("ddt" in item for item in tags):
        return True
    markers = [str(item or "").strip().lower() for item in (case.markers or [])]
    if any("ddt" in item for item in markers):
        return True
    data_config = case.data_config if isinstance(case.data_config, dict) else {}
    if bool(data_config.get("ddt_enabled")):
        return True
    parameter_line = str(data_config.get("parameter_line", "")).strip().lower()
    if "ddt" in parameter_line:
        return True
    return False


def _dedupe_text_items(values: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _existing_case_ids(db: Session, *, exclude_case_id: int | None = None) -> list[str]:
    stmt = select(TestCase.case_id)
    if exclude_case_id:
        stmt = stmt.where(TestCase.id != exclude_case_id)
    database_case_ids = [
        _normalize_business_case_id(item)
        for item in db.execute(stmt).scalars().all()
    ]
    asset_case_ids = [_normalize_business_case_id(item) for item in _existing_asset_case_ids()]
    return _dedupe_text_items([*asset_case_ids, *database_case_ids])


def _source_code_for_mode(mode: str, source: str) -> str:
    requested = str(source or "").strip()
    if requested:
        return normalize_source_code(requested)
    if str(mode or "").strip().lower() == "ai":
        return "ai"
    return "mn"


def _created_source_from_code(source_code: str) -> str:
    normalized = str(source_code or "").strip().lower()
    if normalized == "ai":
        return "ai"
    if normalized == "fb":
        return "workbench"
    if normalized == "imp":
        return "import"
    return "manual"


def _resolve_case_identity(
    db: Session,
    *,
    requested_case_id: str,
    project_code: str,
    client: str,
    product_line: str,
    module: str,
    page_code: str,
    module_code: str,
    title: str,
    description: str,
    tags: list[str],
    case_type: str,
    source: str,
    test_type: str,
    pytest_path: str,
    exclude_case_id: int | None = None,
    allow_existing_requested_case_id: bool = False,
) -> dict[str, str]:
    normalized_project_code = _normalize_project_code(project_code)
    resolved_client = normalize_client_code(
        client or infer_client_code(test_type, runner=pytest_path)
    )
    metadata = build_case_metadata(
        page=page_code or module or product_line or "common",
        module=module_code or module or product_line or "core",
        title=title,
        description=description,
        tags=tags,
        project=normalized_project_code,
        client=resolved_client,
        source_hint=source,
        legacy=normalize_source_code(source or "mn") == "imp",
    )
    resolved_case_type = normalize_business_case_type(case_type or metadata["case_type"])
    resolved_source = normalize_source_code(source or metadata["source"])
    resolved_page_code = metadata["page_code"]
    resolved_module_code = metadata["module_code"]
    existing_case_ids = _existing_case_ids(db, exclude_case_id=exclude_case_id)

    requested = str(requested_case_id or "").strip()
    normalized_requested = _normalize_business_case_id(requested)
    if requested:
        if not normalized_requested:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="case_id must follow shared_backend naming rules",
            )
        if normalized_requested in existing_case_ids and not allow_existing_requested_case_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"case_id already exists: {normalized_requested}",
            )
        resolved_case_id = normalized_requested
    else:
        sequence = next_case_sequence(
            existing_case_ids=existing_case_ids,
            page=module or product_line or resolved_page_code,
            module=module or product_line or resolved_module_code,
            project=normalized_project_code,
            client=resolved_client,
            page_code=resolved_page_code,
            module_code=resolved_module_code,
            case_type=resolved_case_type,
            source=resolved_source,
        )
        resolved_case_id = build_case_id(
            page=module or product_line or resolved_page_code,
            module=module or product_line or resolved_module_code,
            sequence=sequence,
            project=normalized_project_code,
            client=resolved_client,
            page_code=resolved_page_code,
            module_code=resolved_module_code,
            case_type=resolved_case_type,
            source=resolved_source,
        )

    return {
        "case_id": resolved_case_id,
        "project_code": normalized_project_code,
        "client": resolved_client,
        "page_code": resolved_page_code,
        "page_name": metadata["page_name"],
        "module_code": resolved_module_code,
        "module_name": metadata["module_name"],
        "case_type": resolved_case_type,
        "source": resolved_source,
    }


def case_or_404(db: Session, case_id: int | str) -> TestCase:
    ensure_seed_data(db)
    raw_case_id = str(case_id or "").strip()
    case: TestCase | None
    if raw_case_id.isdigit():
        case = db.execute(select(TestCase).where(TestCase.id == int(raw_case_id))).scalar_one_or_none()
    else:
        normalized_case_id = _normalize_business_case_id(raw_case_id)
        if not normalized_case_id:
            case = None
        else:
            case = db.execute(
                select(TestCase).where(TestCase.case_id == normalized_case_id)
            ).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test case not found")
    return case


def resolve_target_case_ids(
    db: Session,
    *,
    ids: Sequence[object] | None = None,
    case_ids: Sequence[object] | None = None,
) -> list[int]:
    ensure_seed_data(db)
    target_ids = positive_ids(ids or [])
    normalized_case_ids: list[str] = []
    for raw in normalize_case_ids(case_ids or []):
        normalized = _normalize_business_case_id(raw)
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"invalid case_id: {raw}",
            )
        if normalized not in normalized_case_ids:
            normalized_case_ids.append(normalized)

    if normalized_case_ids:
        rows = db.execute(
            select(TestCase.case_id, TestCase.id).where(TestCase.case_id.in_(normalized_case_ids))
        ).all()
        matched_map = {str(case_id): int(item_id) for case_id, item_id in rows}
        missing_case_ids = [item for item in normalized_case_ids if item not in matched_map]
        if missing_case_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"test case not found: {missing_case_ids[0]}",
            )
        for case_id_value in normalized_case_ids:
            item_id = matched_map[case_id_value]
            if item_id not in target_ids:
                target_ids.append(item_id)
    return target_ids


def _ensure_case_writable(db: Session, case: TestCase) -> None:
    _ensure_project_writable(db, case.project_code)


def _ensure_cases_writable(db: Session, cases: Sequence[TestCase]) -> None:
    project_codes = sorted(
        {
            _normalize_project_code(item.project_code)
            for item in cases
            if str(item.project_code or "").strip()
        }
    )
    for project_code in project_codes:
        _ensure_project_writable(db, project_code)


def list_test_cases(
    db: Session,
    *,
    q: str,
    project_code: str,
    source: str,
    tag: str,
    priority: str,
    status: str,
    creator: str,
    last_result: str,
    product_line: str,
    module: str,
    test_type: str,
    sort_field: str,
    sort_order: str,
    page: int,
    page_size: int,
) -> TestCaseListResult:
    ensure_seed_data(db)
    parsed_search = parse_test_case_search_query(q)
    keyword = parsed_search.keyword
    creator_filter = creator.strip()
    parsed_creator_filter = parsed_search.creator.strip()
    creator_context = creator_filter or parsed_creator_filter
    last_result_filter = last_result.strip() or parsed_search.last_result
    status_filter = status.strip() or parsed_search.status
    test_type_filter = test_type.strip() or parsed_search.test_type
    source_filter = source.strip().lower() or parsed_search.source
    stmt = select(TestCase)
    if project_code.strip():
        stmt = stmt.where(TestCase.project_code == _normalize_project_code(project_code))
    if keyword:
        raw_term = keyword
        term = f"%{raw_term}%"
        normalized_case_id = _normalize_business_case_id(raw_term)
        conditions: list[Any] = [
            TestCase.case_id.like(term),
            TestCase.name.like(term),
            TestCase.module.like(term),
            TestCase.product_line.like(term),
            TestCase.creator.like(term),
        ]
        if normalized_case_id:
            conditions.append(TestCase.case_id == normalized_case_id)
        if raw_term.isdigit():
            conditions.append(TestCase.id == int(raw_term))
        stmt = stmt.where(or_(*conditions))
    if priority.strip():
        priority_values = [item.strip().upper() for item in str(priority or "").split(",") if item.strip()]
        if priority_values:
            if len(priority_values) == 1:
                stmt = stmt.where(TestCase.priority == priority_values[0])
            else:
                stmt = stmt.where(TestCase.priority.in_(priority_values))
    if status_filter:
        stmt = stmt.where(TestCase.status == normalize_status(status_filter))
    if creator_filter:
        stmt = stmt.where(TestCase.creator == creator_filter)
    elif parsed_creator_filter:
        stmt = stmt.where(TestCase.creator.like(f"%{parsed_creator_filter}%"))
    if last_result_filter:
        stmt = stmt.where(TestCase.last_execution_result == last_result_filter)
    if product_line.strip():
        stmt = stmt.where(TestCase.product_line == product_line.strip())
    if module.strip():
        stmt = stmt.where(TestCase.module == module.strip())
    if test_type_filter:
        stmt = stmt.where(TestCase.test_type == normalize_test_case_type(test_type_filter))
    if source_filter in {"ai", "mn", "cv", "imp", "fb"}:
        stmt = stmt.where(TestCase.source == source_filter)

    cases = db.execute(stmt).scalars().all()
    tag_filter = tag.strip()
    if tag_filter:
        cases = [item for item in cases if tag_filter in (item.tags or [])]

    sort_field_value = str(sort_field or "").strip().lower() or "updated_at"
    sort_order_value = str(sort_order or "").strip().lower() or "desc"
    reverse = sort_order_value != "asc"

    def sort_key(item: TestCase) -> Any:
        if sort_field_value in {"id", "case_id"}:
            return str(item.case_id or "").strip() or f"{item.id:08d}"
        if sort_field_value == "name":
            return str(item.name or "").strip().lower()
        if sort_field_value == "module":
            return (
                str(item.product_line or "").strip().lower(),
                str(item.module or "").strip().lower(),
                str(item.case_id or "").strip().lower(),
            )
        if sort_field_value == "created_at":
            return item.created_at or datetime.min.replace(tzinfo=UTC)
        if sort_field_value == "priority":
            mapping = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
            return mapping.get(str(item.priority or "").strip().upper(), 99)
        if sort_field_value == "status":
            mapping = {"active": 0, "inactive": 1, "deprecated": 2}
            return mapping.get(str(item.status or "").strip().lower(), 99)
        if sort_field_value in {"last_result", "last_execution_result"}:
            mapping = {"failed": 0, "unknown": 1, "skipped": 2, "passed": 3}
            return mapping.get(str(item.last_execution_result or "").strip().lower(), 99)
        return item.updated_at or item.created_at or datetime.min.replace(tzinfo=UTC)

    cases = sorted(cases, key=sort_key, reverse=reverse)

    total_items = len(cases)
    passed_count = sum(1 for item in cases if str(item.last_execution_result or "").strip().lower() == "passed")
    failed_count = sum(1 for item in cases if str(item.last_execution_result or "").strip().lower() == "failed")
    skipped_count = sum(1 for item in cases if str(item.last_execution_result or "").strip().lower() == "skipped")
    automated_count = sum(1 for item in cases if str(item.automation_status or "").strip().lower() == "automated")
    pass_rate = round((passed_count / total_items) * 100, 1) if total_items else 0.0
    automation_rate = round((automated_count / total_items) * 100, 1) if total_items else 0.0
    total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1
    selected_page = max(1, min(page, total_pages))
    start = (selected_page - 1) * page_size
    page_cases = cases[start:start + page_size]
    latest_versions: dict[int, int] = {}
    if page_cases:
        version_rows = db.execute(
            select(TestCaseVersion.case_id, func.max(TestCaseVersion.version_no))
            .where(TestCaseVersion.case_id.in_([case.id for case in page_cases]))
            .group_by(TestCaseVersion.case_id)
        ).all()
        latest_versions = {int(case_id): int(version_no or 0) for case_id, version_no in version_rows}

    tags = sorted(
        {
            tag_item
            for case in db.execute(select(TestCase.tags)).all()
            for tag_item in (case[0] or [])
            if str(tag_item).strip()
        }
    )
    creators = sorted({item[0] for item in db.execute(select(TestCase.creator)).all() if item[0]})
    product_lines = sorted({item[0] for item in db.execute(select(TestCase.product_line)).all() if item[0]})
    modules = sorted({item[0] for item in db.execute(select(TestCase.module)).all() if item[0]})
    project_codes = sorted({item[0] for item in db.execute(select(TestCase.project_code)).all() if item[0]})
    priorities = sorted(
        {item[0] for item in db.execute(select(TestCase.priority)).all() if item[0]}
    )
    last_results = sorted(
        {
            item[0]
            for item in db.execute(select(TestCase.last_execution_result)).all()
            if item[0]
        }
    )
    sources = sorted({item[0] for item in db.execute(select(TestCase.source)).all() if item[0]})
    test_types = sorted({item[0] for item in db.execute(select(TestCase.test_type)).all() if item[0]})

    page_project_codes = sorted(
        {
            _normalize_project_code(case.project_code)
            for case in page_cases
            if str(case.project_code or "").strip()
        }
    )
    project_status_rows = (
        db.execute(
            select(TestProject.project_code, TestProject.status).where(TestProject.project_code.in_(page_project_codes))
        ).all()
        if page_project_codes
        else []
    )
    project_statuses = {
        str(project_code or "").strip().lower(): str(status_value or "").strip().lower() or "active"
        for project_code, status_value in project_status_rows
    }

    return TestCaseListResult(
        cases=page_cases,
        pagination={
            "page": selected_page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_prev": selected_page > 1,
            "has_next": selected_page < total_pages,
            "prev_page": selected_page - 1 if selected_page > 1 else None,
            "next_page": selected_page + 1 if selected_page < total_pages else None,
        },
        filters={
            "product_lines": product_lines,
            "modules": modules,
            "project_codes": project_codes,
            "test_types": test_types,
            "tags": tags,
            "priorities": priorities,
            "statuses": sorted({item[0] for item in db.execute(select(TestCase.status)).all() if item[0]}),
            "sources": sources,
            "creators": creators,
            "last_results": last_results,
        },
        latest_versions=latest_versions,
        search_context=build_test_case_search_context(
            keyword=keyword,
            project_code=project_code.strip(),
            product_line=product_line.strip(),
            module=module.strip(),
            priority=priority.strip(),
            test_type=test_type_filter,
            status=status_filter,
            creator=creator_context,
            last_result=last_result_filter,
            source=source_filter,
        ),
        stats={
            "total": total_items,
            "passed": passed_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "automated": automated_count,
            "automation_rate": automation_rate,
            "pass_rate": pass_rate,
        },
        project_statuses=project_statuses,
    )


def create_test_case(db: Session, payload: TestCaseCreate) -> TestCase:
    ensure_seed_data(db)
    tags = normalize_tags(payload.tags)
    related_services = normalize_text_list(payload.related_services)
    scenario_types = normalize_text_list(payload.scenario_types)
    artifact_links = normalize_text_list(payload.artifact_links)
    test_steps = normalize_test_steps(payload.test_steps)
    data_config = normalize_data_config(payload.data_config)
    script_code = payload.script_code.strip()
    name = payload.name.strip()
    if payload.mode == "ai":
        script_code = generate_ai_script(payload.requirement, payload.module)
        if not name:
            short_req = (
                payload.requirement.strip()[:14]
                if payload.requirement.strip()
                else "AI生成用例"
            )
            name = f"{payload.module}-{short_req}"

    script_code = compose_data_driven_script(script_code, data_config)

    if not script_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="script_code must not be empty")
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name must not be empty")

    normalized_test_type = normalize_test_case_type(payload.test_type)
    resolved_identity = _resolve_case_identity(
        db,
        requested_case_id=payload.case_id,
        project_code=payload.project_code,
        client=payload.client,
        product_line=payload.product_line.strip(),
        module=payload.module.strip(),
        page_code=payload.page_code.strip(),
        module_code=payload.module_code.strip(),
        title=name,
        description=payload.expected_result or payload.notes or payload.requirement,
        tags=tags,
        case_type=payload.case_type,
        source=_source_code_for_mode(payload.mode, payload.source),
        test_type=normalized_test_type,
        pytest_path=payload.pytest_path,
    )
    _ensure_project_writable(db, resolved_identity["project_code"])
    created_source = _created_source_from_code(resolved_identity["source"])
    normalized_test_steps_text = payload.test_steps_text.strip() or render_test_steps_text(test_steps)
    normalized_trigger_entry = normalize_optional_text(payload.trigger_entry) or (
        "API" if normalized_test_type == "api" else "UI"
    )
    normalized_automation_status = normalize_optional_text(payload.automation_status) or (
        "automated" if (payload.pytest_path.strip() or script_code.strip()) else "manual"
    )
    now_ts = datetime.now(UTC)

    case = TestCase(
        case_id=resolved_identity["case_id"],
        project_code=resolved_identity["project_code"],
        client=resolved_identity["client"],
        page_code=resolved_identity["page_code"],
        page_name=resolved_identity["page_name"],
        module_code=resolved_identity["module_code"],
        module_name=resolved_identity["module_name"],
        case_type=resolved_identity["case_type"],
        source=resolved_identity["source"],
        name=name,
        product_line=payload.product_line.strip(),
        module=payload.module.strip(),
        chain_stage=normalize_optional_text(payload.chain_stage),
        sut_service=normalize_optional_text(payload.sut_service),
        related_services=related_services,
        priority=payload.priority.strip() or "P2",
        test_type=normalized_test_type,
        scenario_types=scenario_types,
        trigger_entry=normalized_trigger_entry,
        fault_injection_type=normalize_optional_text(payload.fault_injection_type),
        fault_injection_target=normalize_optional_text(payload.fault_injection_target),
        fault_injection_params=normalize_optional_text(payload.fault_injection_params),
        setup_sql=normalize_optional_text(payload.setup_sql),
        precondition_state=normalize_optional_text(payload.precondition_state),
        test_steps=test_steps,
        test_steps_text=normalized_test_steps_text,
        concurrency_model=normalize_optional_text(payload.concurrency_model),
        retry_policy=normalize_optional_text(payload.retry_policy),
        expected_result=normalize_optional_text(payload.expected_result),
        assert_sql=normalize_optional_text(payload.assert_sql),
        event_assertion=normalize_optional_text(payload.event_assertion),
        metric_assertion=normalize_optional_text(payload.metric_assertion),
        cleanup_script=normalize_optional_text(payload.cleanup_script),
        artifact_links=artifact_links,
        notes=normalize_optional_text(payload.notes),
        tags=tags,
        markers=normalize_markers(payload.markers),
        creator=payload.creator.strip() or "admin",
        assignee=payload.assignee.strip(),
        pytest_path=payload.pytest_path.strip(),
        status=normalize_status(payload.status),
        automation_status=normalized_automation_status,
        created_source=created_source,
        source_ref=payload.source_ref.strip(),
        script_code=script_code,
        data_config=data_config,
        last_execution_result="unknown",
        last_report_url="",
        last_synced_at=datetime.now(UTC) if created_source in {"ai", "workbench"} else None,
        created_at=now_ts,
        updated_at=now_ts,
    )
    db.add(case)
    db.flush()
    _sync_test_case_steps(db, case)
    db.commit()
    db.refresh(case)

    db.add(
        TestCaseVersion(
            case_id=case.id,
            version_no=1,
            script_code=case.script_code,
            changed_by=case.creator,
            change_summary=f"case created by {payload.mode}",
        )
    )
    db.commit()
    return case


def upsert_test_case_from_workbench(
    db: Session,
    *,
    project_code: str,
    case_yaml: dict[str, Any],
    source_path: str,
    source_name: str = "ai-workbench",
) -> TestCase:
    ensure_seed_data(db)
    case_yaml = _sanitize_workbench_case_yaml_for_storage(case_yaml)
    normalized_case_id = _normalize_business_case_id((case_yaml or {}).get("id"))
    if not normalized_case_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="generated case is missing a valid case_id",
        )

    normalized_project_code = _normalize_project_code(project_code)
    _ensure_project_writable(db, normalized_project_code)
    source_asset_id, source_intent_ids = _workbench_source_identity(case_yaml)
    source_intent_id = source_intent_ids[0] if len(source_intent_ids) == 1 else ""

    title = normalize_optional_text(case_yaml.get("title")) or normalized_case_id
    tags = normalize_tags(normalize_text_list(case_yaml.get("tags")))
    requirement_lines = _workbench_requirement(case_yaml)
    description = normalize_optional_text(case_yaml.get("description")) or "\n".join(requirement_lines)
    execution = case_yaml.get("execution") if isinstance(case_yaml, dict) else {}
    execution = execution if isinstance(execution, dict) else {}
    page_slug = normalize_optional_text(execution.get("page") or case_yaml.get("module") or "common") or "common"
    module_slug = normalize_optional_text(case_yaml.get("module") or page_slug) or page_slug
    steps = _workbench_steps(case_yaml)
    scenario_context_text = " ".join(
        [
            normalize_optional_text(case_yaml.get("title")),
            normalize_optional_text(case_yaml.get("description")),
            "\n".join(requirement_lines),
        ]
    ).strip()
    if _env_flag("AUTO_RETRY_FIX_ENABLED", True):
        steps = _repair_execution_steps_for_storage(
            db,
            project_code=normalized_project_code,
            client="web",
            page_code=page_slug,
            steps=steps,
            scenario_context_text=scenario_context_text,
        )
    execution["steps"] = steps
    case_yaml["execution"] = execution
    metadata = build_case_metadata(
        page=page_slug,
        module=module_slug,
        title=title,
        description=description,
        tags=tags,
        project=normalized_project_code,
        client="web",
        source_hint="ai",
    )
    existing = db.execute(
        select(TestCase).where(TestCase.case_id == normalized_case_id)
    ).scalar_one_or_none()
    if existing is None and source_asset_id and source_intent_id:
        existing = _find_existing_workbench_case_by_source_identity(
            db,
            project_code=normalized_project_code,
            source_asset_id=source_asset_id,
            intent_id=source_intent_id,
        )
        if existing is not None:
            normalized_case_id = _normalize_business_case_id(existing.case_id)
            case_yaml["id"] = normalized_case_id
    resolved_identity = _resolve_case_identity(
        db,
        requested_case_id=normalized_case_id,
        project_code=normalized_project_code,
        client="web",
        product_line=page_slug,
        module=module_slug,
        page_code=metadata["page_code"],
        module_code=metadata["module_code"],
        title=title,
        description=description,
        tags=tags,
        case_type=metadata["case_type"],
        source="ai",
        test_type="ui",
        pytest_path="",
        exclude_case_id=existing.id if existing else None,
        allow_existing_requested_case_id=True,
    )
    script_code = _workbench_yaml_script(case_yaml)
    raw_expected_result = (
        normalize_optional_text(case_yaml.get("expected_result"))
        or "\n".join(requirement_lines)
        or description
    )
    expected_result = _repair_expected_result_for_storage(
        expected_result=raw_expected_result,
        steps=steps,
        scenario_context_text=scenario_context_text,
    ) if _env_flag("AUTO_RETRY_FIX_ENABLED", True) else raw_expected_result
    owner = normalize_optional_text(case_yaml.get("owner")) or source_name
    source_ref = normalize_optional_text(source_path)
    chain_stage = normalize_optional_text(case_yaml.get("chain_stage")) or metadata["page_name"]
    notes = normalize_optional_text(case_yaml.get("notes")) or "Synchronized from AI workbench generated asset."
    test_steps_text = render_test_steps_text(steps)
    sync_generated_case_yaml_file(source_ref, script_code)

    if existing is None:
        now_ts = datetime.now(UTC)
        case = TestCase(
            case_id=resolved_identity["case_id"],
            project_code=resolved_identity["project_code"],
            client=resolved_identity["client"],
            page_code=resolved_identity["page_code"],
            page_name=resolved_identity["page_name"],
            module_code=resolved_identity["module_code"],
            module_name=resolved_identity["module_name"],
            case_type=resolved_identity["case_type"],
            source=resolved_identity["source"],
            name=title,
            product_line=resolved_identity["page_name"],
            module=resolved_identity["module_name"],
            chain_stage=chain_stage,
            sut_service=normalize_optional_text(case_yaml.get("sut_service")),
            related_services=normalize_text_list(case_yaml.get("related_services")),
            priority=normalize_optional_text(case_yaml.get("priority")) or "P1",
            test_type="ui",
            scenario_types=normalize_text_list(case_yaml.get("scenario_types")),
            trigger_entry=normalize_optional_text(case_yaml.get("trigger_entry")) or "UI",
            fault_injection_type=normalize_optional_text(case_yaml.get("fault_injection_type")),
            fault_injection_target=normalize_optional_text(case_yaml.get("fault_injection_target")),
            fault_injection_params=normalize_optional_text(case_yaml.get("fault_injection_params")),
            setup_sql=normalize_optional_text(case_yaml.get("setup_sql")),
            precondition_state=normalize_optional_text(case_yaml.get("precondition_state")),
            test_steps=steps,
            test_steps_text=test_steps_text,
            concurrency_model=normalize_optional_text(case_yaml.get("concurrency_model")),
            retry_policy=normalize_optional_text(case_yaml.get("retry_policy")),
            expected_result=expected_result,
            assert_sql=normalize_optional_text(case_yaml.get("assert_sql")),
            event_assertion=normalize_optional_text(case_yaml.get("event_assertion")),
            metric_assertion=normalize_optional_text(case_yaml.get("metric_assertion")),
            cleanup_script=normalize_optional_text(case_yaml.get("cleanup_script")),
            artifact_links=normalize_text_list(case_yaml.get("artifact_links")),
            notes=notes,
            tags=tags,
            markers=normalize_markers([]),
            creator=owner,
            assignee=owner,
            pytest_path="",
            status="inactive",
            automation_status="automated" if steps else "manual",
            created_source="ai",
            source_ref=source_ref,
            script_code=script_code,
            data_config=normalize_data_config(TestCaseDataConfig()),
            last_execution_result="unknown",
            last_report_url="",
            last_synced_at=now_ts,
            created_at=now_ts,
            updated_at=now_ts,
        )
        db.add(case)
        db.flush()
        _sync_test_case_steps(db, case)
        db.commit()
        db.refresh(case)
        db.add(
            TestCaseVersion(
                case_id=case.id,
                version_no=1,
                script_code=case.script_code,
                changed_by=owner,
                change_summary="case synchronized from ai workbench",
            )
        )
        db.commit()
        db.refresh(case)
        return case

    existing.project_code = resolved_identity["project_code"]
    existing.client = resolved_identity["client"]
    existing.page_code = resolved_identity["page_code"]
    existing.page_name = resolved_identity["page_name"]
    existing.module_code = resolved_identity["module_code"]
    existing.module_name = resolved_identity["module_name"]
    existing.case_type = resolved_identity["case_type"]
    existing.source = resolved_identity["source"]
    existing.name = title
    existing.product_line = resolved_identity["page_name"]
    existing.module = resolved_identity["module_name"]
    existing.chain_stage = chain_stage
    existing.sut_service = normalize_optional_text(case_yaml.get("sut_service"))
    existing.related_services = normalize_text_list(case_yaml.get("related_services"))
    existing.priority = normalize_optional_text(case_yaml.get("priority")) or existing.priority or "P1"
    existing.test_type = "ui"
    existing.scenario_types = normalize_text_list(case_yaml.get("scenario_types"))
    existing.trigger_entry = normalize_optional_text(case_yaml.get("trigger_entry")) or "UI"
    existing.fault_injection_type = normalize_optional_text(case_yaml.get("fault_injection_type"))
    existing.fault_injection_target = normalize_optional_text(case_yaml.get("fault_injection_target"))
    existing.fault_injection_params = normalize_optional_text(case_yaml.get("fault_injection_params"))
    existing.setup_sql = normalize_optional_text(case_yaml.get("setup_sql"))
    existing.precondition_state = normalize_optional_text(case_yaml.get("precondition_state"))
    existing.test_steps = steps
    existing.test_steps_text = test_steps_text
    existing.concurrency_model = normalize_optional_text(case_yaml.get("concurrency_model"))
    existing.retry_policy = normalize_optional_text(case_yaml.get("retry_policy"))
    existing.expected_result = expected_result
    existing.assert_sql = normalize_optional_text(case_yaml.get("assert_sql"))
    existing.event_assertion = normalize_optional_text(case_yaml.get("event_assertion"))
    existing.metric_assertion = normalize_optional_text(case_yaml.get("metric_assertion"))
    existing.cleanup_script = normalize_optional_text(case_yaml.get("cleanup_script"))
    existing.artifact_links = normalize_text_list(case_yaml.get("artifact_links"))
    existing.notes = notes
    existing.tags = tags
    existing.creator = existing.creator or owner
    existing.assignee = owner
    existing.status = "inactive"
    existing.automation_status = "automated" if steps else "manual"
    existing.created_source = "ai"
    existing.source_ref = source_ref
    existing.script_code = script_code
    existing.last_synced_at = datetime.now(UTC)
    existing.updated_at = datetime.now(UTC)
    db.add(existing)
    _sync_test_case_steps(db, existing)
    db.commit()

    db.add(
        TestCaseVersion(
            case_id=existing.id,
            version_no=_next_version_no(db, existing.id),
            script_code=existing.script_code,
            changed_by=owner,
            change_summary="case re-synchronized from ai workbench",
        )
    )
    db.commit()
    db.refresh(existing)
    return existing


def get_test_case_detail(db: Session, case_id: int | str) -> TestCaseDetailResult:
    ensure_seed_data(db)
    case = case_or_404(db, case_id)
    defects = db.execute(
        select(TestCaseDefect)
        .where(TestCaseDefect.case_id == case.id)
        .order_by(TestCaseDefect.created_at.desc())
    ).scalars().all()
    executions = db.execute(
        select(TestCaseExecution)
        .where(TestCaseExecution.case_id == case.id)
        .order_by(TestCaseExecution.executed_at.desc(), TestCaseExecution.id.desc())
        .limit(10)
    ).scalars().all()
    versions = db.execute(
        select(TestCaseVersion)
        .where(TestCaseVersion.case_id == case.id)
        .order_by(TestCaseVersion.version_no.desc(), TestCaseVersion.id.desc())
    ).scalars().all()
    normalized_data_config = normalize_data_config(
        TestCaseDataConfig.model_validate(case.data_config or {})
    )
    project_status = test_project_service.get_project_status(db, case.project_code)
    return TestCaseDetailResult(
        case=case,
        defects=list(defects),
        executions=list(executions),
        versions=list(versions),
        data_config=normalized_data_config,
        project_status=project_status,
    )


def _next_version_no(db: Session, case_id: int) -> int:
    latest_version = db.execute(
        select(TestCaseVersion.version_no)
        .where(TestCaseVersion.case_id == case_id)
        .order_by(TestCaseVersion.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()
    return int(latest_version or 0) + 1


def update_test_case(db: Session, case_id: int | str, payload: TestCaseUpdate) -> TestCaseMutationResult:
    case = case_or_404(db, case_id)
    target_project_code = (
        _normalize_project_code(payload.project_code)
        if payload.project_code is not None
        else _normalize_project_code(case.project_code)
    )
    _ensure_project_writable(db, target_project_code)
    changed = False
    latest_version_no: int | None = None

    if payload.project_code is not None:
        next_value = _normalize_project_code(payload.project_code)
        if case.project_code != next_value:
            case.project_code = next_value
            changed = True
    if payload.client is not None:
        next_value = normalize_client_code(
            payload.client or infer_client_code(case.test_type, runner=case.pytest_path)
        )
        if case.client != next_value:
            case.client = next_value
            changed = True
    if payload.page_code is not None:
        next_value = normalize_optional_text(payload.page_code)
        if next_value and case.page_code != next_value:
            case.page_code = next_value
            changed = True
    if payload.module_code is not None:
        next_value = normalize_optional_text(payload.module_code)
        if next_value and case.module_code != next_value:
            case.module_code = next_value
            changed = True
    if payload.case_type is not None:
        next_value = normalize_business_case_type(payload.case_type or case.case_type)
        if case.case_type != next_value:
            case.case_type = next_value
            changed = True
    if payload.source is not None:
        next_value = normalize_source_code(payload.source or case.source)
        if case.source != next_value:
            case.source = next_value
            changed = True
    if payload.name is not None:
        name = payload.name.strip()
        if name:
            case.name = name
            changed = True
    if payload.product_line is not None:
        case.product_line = payload.product_line.strip() or case.product_line
        changed = True
    if payload.module is not None:
        case.module = payload.module.strip() or case.module
        changed = True
    if payload.chain_stage is not None:
        case.chain_stage = normalize_optional_text(payload.chain_stage)
        changed = True
    if payload.sut_service is not None:
        case.sut_service = normalize_optional_text(payload.sut_service)
        changed = True
    if payload.related_services is not None:
        case.related_services = normalize_text_list(payload.related_services)
        changed = True
    if payload.priority is not None:
        case.priority = payload.priority.strip() or case.priority
        changed = True
    if payload.test_type is not None:
        case.test_type = normalize_test_case_type(payload.test_type)
        changed = True
    if payload.scenario_types is not None:
        case.scenario_types = normalize_text_list(payload.scenario_types)
        changed = True
    if payload.trigger_entry is not None:
        case.trigger_entry = normalize_optional_text(payload.trigger_entry)
        changed = True
    if payload.fault_injection_type is not None:
        case.fault_injection_type = normalize_optional_text(payload.fault_injection_type)
        changed = True
    if payload.fault_injection_target is not None:
        case.fault_injection_target = normalize_optional_text(payload.fault_injection_target)
        changed = True
    if payload.fault_injection_params is not None:
        case.fault_injection_params = normalize_optional_text(payload.fault_injection_params)
        changed = True
    if payload.setup_sql is not None:
        case.setup_sql = normalize_optional_text(payload.setup_sql)
        changed = True
    if payload.precondition_state is not None:
        case.precondition_state = normalize_optional_text(payload.precondition_state)
        changed = True
    if payload.test_steps is not None:
        case.test_steps = normalize_test_steps(payload.test_steps)
        changed = True
    if payload.test_steps_text is not None:
        case.test_steps_text = normalize_optional_text(payload.test_steps_text)
        changed = True
    if payload.concurrency_model is not None:
        case.concurrency_model = normalize_optional_text(payload.concurrency_model)
        changed = True
    if payload.retry_policy is not None:
        case.retry_policy = normalize_optional_text(payload.retry_policy)
        changed = True
    if payload.expected_result is not None:
        case.expected_result = normalize_optional_text(payload.expected_result)
        changed = True
    if payload.assert_sql is not None:
        case.assert_sql = normalize_optional_text(payload.assert_sql)
        changed = True
    if payload.event_assertion is not None:
        case.event_assertion = normalize_optional_text(payload.event_assertion)
        changed = True
    if payload.metric_assertion is not None:
        case.metric_assertion = normalize_optional_text(payload.metric_assertion)
        changed = True
    if payload.cleanup_script is not None:
        case.cleanup_script = normalize_optional_text(payload.cleanup_script)
        changed = True
    if payload.artifact_links is not None:
        case.artifact_links = normalize_text_list(payload.artifact_links)
        changed = True
    if payload.notes is not None:
        case.notes = normalize_optional_text(payload.notes)
        changed = True
    if payload.tags is not None:
        case.tags = normalize_tags(payload.tags)
        changed = True
    if payload.markers is not None:
        case.markers = normalize_markers(payload.markers)
        changed = True
    if payload.creator is not None:
        case.creator = payload.creator.strip() or case.creator
        changed = True
    if payload.assignee is not None:
        case.assignee = payload.assignee.strip()
        changed = True
    if payload.pytest_path is not None:
        case.pytest_path = payload.pytest_path.strip()
        changed = True
    if payload.status is not None:
        case.status = normalize_status(payload.status)
        changed = True
    if payload.automation_status is not None:
        case.automation_status = normalize_optional_text(payload.automation_status) or case.automation_status
        changed = True
    if payload.source_ref is not None:
        case.source_ref = normalize_optional_text(payload.source_ref)
        changed = True

    data_config_updated = False
    normalized_data_config = normalize_data_config(
        TestCaseDataConfig.model_validate(case.data_config or {})
    )
    if payload.data_config is not None:
        normalized_data_config = normalize_data_config(payload.data_config)
        case.data_config = normalized_data_config
        case.script_code = refresh_existing_data_driven_script(
            case.script_code or "",
            normalized_data_config,
        )
        data_config_updated = True
        changed = True

    if payload.script_code is not None:
        case.script_code = payload.script_code
        projection = _derive_case_projection_from_script(payload.script_code)
        if projection:
            case.precondition_state = projection["precondition_state"]
            case.test_steps = projection["test_steps"]
            case.test_steps_text = projection["test_steps_text"]
            case.expected_result = projection["expected_result"]
        changed = True

    if payload.automation_status is None and (
        payload.pytest_path is not None or payload.script_code is not None
    ):
        case.automation_status = "automated" if (case.pytest_path or case.script_code) else "manual"

    if payload.test_steps_text is None and payload.test_steps is not None:
        case.test_steps_text = render_test_steps_text(case.test_steps if isinstance(case.test_steps, list) else [])

    if (payload.case_id is not None and str(payload.case_id).strip()) or not _normalize_business_case_id(case.case_id):
        resolved_identity = _resolve_case_identity(
            db,
            requested_case_id=payload.case_id or "",
            project_code=case.project_code,
            client=case.client,
            product_line=case.product_line,
            module=case.module,
            page_code=case.page_code,
            module_code=case.module_code,
            title=case.name,
            description=case.expected_result or case.notes,
            tags=normalize_tags(list(case.tags or [])),
            case_type=case.case_type,
            source=case.source,
            test_type=case.test_type,
            pytest_path=case.pytest_path,
            exclude_case_id=case.id,
        )
        if case.case_id != resolved_identity["case_id"]:
            case.case_id = resolved_identity["case_id"]
            changed = True
        case.project_code = resolved_identity["project_code"]
        case.client = resolved_identity["client"]
        case.page_code = resolved_identity["page_code"]
        case.page_name = resolved_identity["page_name"]
        case.module_code = resolved_identity["module_code"]
        case.module_name = resolved_identity["module_name"]
        case.case_type = resolved_identity["case_type"]
        case.source = resolved_identity["source"]
    else:
        refreshed_metadata = build_case_metadata(
            page=case.page_code or case.module or case.product_line or "common",
            module=case.module_code or case.module or case.product_line or "core",
            title=case.name,
            description=case.expected_result or case.notes,
            tags=list(case.tags or []),
            project=case.project_code,
            client=case.client,
            source_hint=case.source,
            legacy=case.source == "imp",
        )
        case.page_name = refreshed_metadata["page_name"]
        case.module_name = refreshed_metadata["module_name"]

    if changed:
        case.updated_at = datetime.now(UTC)
        db.add(case)
        if payload.script_code is not None:
            latest_version_no = _next_version_no(db, case.id)
            db.add(
                TestCaseVersion(
                    case_id=case.id,
                    version_no=latest_version_no,
                    script_code=case.script_code,
                    changed_by=(
                        payload.creator.strip()
                        if payload.creator and payload.creator.strip()
                        else case.creator
                    ),
                    change_summary="case updated",
                )
            )
        elif data_config_updated:
            latest_version_no = _next_version_no(db, case.id)
            db.add(
                TestCaseVersion(
                    case_id=case.id,
                    version_no=latest_version_no,
                    script_code=case.script_code,
                    changed_by=case.creator,
                    change_summary="data config updated",
                )
            )
        _sync_test_case_steps(db, case)
        db.commit()

    return TestCaseMutationResult(
        case=case,
        data_config=normalized_data_config,
        script_code=case.script_code,
        latest_version_no=latest_version_no,
    )


def compare_case_versions(
    db: Session,
    case_id: int | str,
    from_version: int,
    to_version: int,
) -> TestCaseVersionComparison:
    ensure_seed_data(db)
    case = case_or_404(db, case_id)
    from_item = db.execute(
        select(TestCaseVersion).where(
            TestCaseVersion.case_id == case.id,
            TestCaseVersion.version_no == from_version,
        )
    ).scalar_one_or_none()
    to_item = db.execute(
        select(TestCaseVersion).where(
            TestCaseVersion.case_id == case.id,
            TestCaseVersion.version_no == to_version,
        )
    ).scalar_one_or_none()
    if not from_item or not to_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="version not found")

    diff_lines = list(
        difflib.unified_diff(
            (from_item.script_code or "").splitlines(),
            (to_item.script_code or "").splitlines(),
            fromfile=f"v{from_version}",
            tofile=f"v{to_version}",
            lineterm="",
        )
    )
    added_lines = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    removed_lines = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    return TestCaseVersionComparison(
        from_version=from_version,
        to_version=to_version,
        added_lines=added_lines,
        removed_lines=removed_lines,
        diff_lines=diff_lines,
    )


def update_script(db: Session, case_id: int | str, payload: TestCaseScriptUpdate) -> int:
    case = case_or_404(db, case_id)
    _ensure_case_writable(db, case)
    old_lines = len((case.script_code or "").splitlines())
    new_lines = len(payload.script_code.splitlines())
    delta = new_lines - old_lines
    case.script_code = payload.script_code
    projection = _derive_case_projection_from_script(payload.script_code)
    if projection:
        case.precondition_state = projection["precondition_state"]
        case.test_steps = projection["test_steps"]
        case.test_steps_text = projection["test_steps_text"]
        case.expected_result = projection["expected_result"]
    case.updated_at = datetime.now(UTC)
    db.add(case)
    _sync_test_case_steps(db, case)
    next_version = _next_version_no(db, case.id)
    db.add(
        TestCaseVersion(
            case_id=case.id,
            version_no=next_version,
            script_code=payload.script_code,
            changed_by=payload.changed_by.strip() or "admin",
            change_summary=f"script updated, line delta {delta:+d}",
        )
    )
    db.commit()
    return next_version


def batch_delete_test_cases(
    db: Session,
    ids: Sequence[object] | None = None,
    case_ids: Sequence[object] | None = None,
) -> int:
    target_ids = resolve_target_case_ids(db, ids=ids, case_ids=case_ids)
    if not target_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids or case_ids must not be empty")
    deleting_rows = db.execute(
        select(TestCase.id, TestCase.case_id).where(TestCase.id.in_(target_ids))
    ).all()
    deleting_case_ids = [
        _normalize_business_case_id(item_case_id)
        for _item_id, item_case_id in deleting_rows
        if _normalize_business_case_id(item_case_id)
    ]
    db.query(TestCaseDefect).filter(TestCaseDefect.case_id.in_(target_ids)).delete(
        synchronize_session=False
    )
    db.query(TestCaseExecution).filter(TestCaseExecution.case_id.in_(target_ids)).delete(
        synchronize_session=False
    )
    db.query(TestCaseVersion).filter(TestCaseVersion.case_id.in_(target_ids)).delete(
        synchronize_session=False
    )
    db.query(TestCaseStep).filter(TestCaseStep.case_id.in_(target_ids)).delete(
        synchronize_session=False
    )
    if deleting_case_ids:
        db.query(PageObjectRef).filter(
            PageObjectRef.reference_type == "test_case",
            PageObjectRef.reference_key.in_(deleting_case_ids),
        ).delete(
            synchronize_session=False
        )
    deleted_count = db.query(TestCase).filter(TestCase.id.in_(target_ids)).delete(
        synchronize_session=False
    )
    db.commit()
    _delete_case_asset_files(deleting_case_ids)
    _delete_execution_report_files(deleting_case_ids)
    return int(deleted_count)


def purge_ddt_test_cases(db: Session) -> dict[str, Any]:
    ensure_seed_data(db)
    cases = list(db.execute(select(TestCase).order_by(TestCase.id.asc())).scalars().all())
    target_cases = [item for item in cases if _is_ddt_case(item)]
    if not target_cases:
        return {
            "deleted_count": 0,
            "deleted_case_ids": [],
        }
    target_ids = [int(item.id) for item in target_cases]
    target_case_ids = [
        _normalize_business_case_id(item.case_id)
        for item in target_cases
        if _normalize_business_case_id(item.case_id)
    ]
    deleted_count = batch_delete_test_cases(db, ids=target_ids)
    return {
        "deleted_count": deleted_count,
        "deleted_case_ids": target_case_ids,
    }


def batch_update_test_case_tags(db: Session, payload: BatchTagsUpdatePayload) -> int:
    target_ids = resolve_target_case_ids(db, ids=payload.ids, case_ids=payload.case_ids)
    if not target_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids or case_ids must not be empty")
    target_tags = normalize_tags(payload.tags)
    if not target_tags:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tags must not be empty")

    updated = 0
    cases = db.execute(select(TestCase).where(TestCase.id.in_(target_ids))).scalars().all()
    _ensure_cases_writable(db, cases)
    for case in cases:
        if payload.mode == "append":
            case.tags = normalize_tags(list(case.tags or []) + target_tags)
        else:
            case.tags = target_tags
        case.updated_at = datetime.now(UTC)
        db.add(case)
        updated += 1
    db.commit()
    return updated


def batch_update_test_case_status(db: Session, payload: BatchStatusUpdatePayload) -> int:
    target_ids = resolve_target_case_ids(db, ids=payload.ids, case_ids=payload.case_ids)
    if not target_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids or case_ids must not be empty")
    target_status = normalize_status(payload.status)

    updated = 0
    cases = db.execute(select(TestCase).where(TestCase.id.in_(target_ids))).scalars().all()
    _ensure_cases_writable(db, cases)
    for case in cases:
        if case.status == target_status:
            continue
        case.status = target_status
        case.updated_at = datetime.now(UTC)
        db.add(case)
        db.add(
            TestCaseVersion(
                case_id=case.id,
                version_no=_next_version_no(db, case.id),
                script_code=case.script_code,
                changed_by=case.creator,
                change_summary=f"status updated to {target_status}",
            )
        )
        updated += 1
    db.commit()
    return updated


def list_test_cases_for_export(
    db: Session,
    ids: Sequence[object] | None = None,
    case_ids: Sequence[object] | None = None,
) -> list[TestCase]:
    ensure_seed_data(db)
    target_ids = resolve_target_case_ids(db, ids=ids, case_ids=case_ids)
    if not target_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids or case_ids must not be empty")
    return list(
        db.execute(
            select(TestCase).where(TestCase.id.in_(target_ids)).order_by(TestCase.id.asc())
        ).scalars().all()
    )


def add_test_case_defect(
    db: Session,
    case_id: int | str,
    defect_key: str,
    defect_url: str = "",
) -> TestCaseDefect:
    case = case_or_404(db, case_id)
    _ensure_case_writable(db, case)
    key = defect_key.strip()
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="defect_key must not be empty")
    defect = TestCaseDefect(case_id=case.id, defect_key=key, defect_url=defect_url.strip())
    db.add(defect)
    db.commit()
    db.refresh(defect)
    return defect


def create_module_tree_node(
    db: Session,
    *,
    project_code: str,
    product_line: str,
    module: str = "",
) -> dict[str, Any]:
    ensure_seed_data(db)
    normalized_project_code = _normalize_project_code(project_code)
    _ensure_project_writable(db, normalized_project_code)
    normalized_product_line = str(product_line or "").strip()
    normalized_module = str(module or "").strip()
    if not normalized_product_line:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="product_line must not be empty")
    exists = db.execute(
        select(TestCaseTreeNode).where(
            TestCaseTreeNode.project_code == normalized_project_code,
            TestCaseTreeNode.product_line == normalized_product_line,
            TestCaseTreeNode.module == normalized_module,
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="tree node already exists")
    node = TestCaseTreeNode(
        project_code=normalized_project_code,
        product_line=normalized_product_line,
        module=normalized_module,
    )
    db.add(node)
    db.commit()
    return {
        "project_code": normalized_project_code,
        "product_line": normalized_product_line,
        "module": normalized_module,
    }


def update_module_tree_node(
    db: Session,
    *,
    project_code: str,
    product_line: str,
    module: str,
    new_product_line: str,
    new_module: str = "",
) -> dict[str, Any]:
    ensure_seed_data(db)
    normalized_project_code = _normalize_project_code(project_code)
    _ensure_project_writable(db, normalized_project_code)
    old_product_line = str(product_line or "").strip()
    old_module = str(module or "").strip()
    target_product_line = str(new_product_line or "").strip()
    target_module = str(new_module or "").strip()
    if not old_product_line or not target_product_line:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="product_line must not be empty")

    case_stmt = select(TestCase).where(
        TestCase.project_code == normalized_project_code,
        TestCase.product_line == old_product_line,
    )
    if old_module:
        case_stmt = case_stmt.where(TestCase.module == old_module)
    matching_cases = list(db.execute(case_stmt).scalars().all())

    existing_node = db.execute(
        select(TestCaseTreeNode).where(
            TestCaseTreeNode.project_code == normalized_project_code,
            TestCaseTreeNode.product_line == old_product_line,
            TestCaseTreeNode.module == old_module,
        )
    ).scalar_one_or_none()
    if not matching_cases and existing_node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tree node not found")

    for case in matching_cases:
        case.product_line = target_product_line
        if old_module:
            case.module = target_module
        case.updated_at = datetime.now(UTC)
        db.add(case)

    duplicate = db.execute(
        select(TestCaseTreeNode).where(
            TestCaseTreeNode.project_code == normalized_project_code,
            TestCaseTreeNode.product_line == target_product_line,
            TestCaseTreeNode.module == target_module,
        )
    ).scalar_one_or_none()
    if duplicate is None:
        db.add(
            TestCaseTreeNode(
                project_code=normalized_project_code,
                product_line=target_product_line,
                module=target_module,
            )
        )
    if existing_node is not None:
        db.delete(existing_node)
    db.commit()
    return {
        "project_code": normalized_project_code,
        "product_line": target_product_line,
        "module": target_module,
        "updated_cases": len(matching_cases),
    }


def delete_module_tree_node(
    db: Session,
    *,
    project_code: str,
    product_line: str,
    module: str = "",
    cascade_cases: bool = False,
) -> dict[str, Any]:
    ensure_seed_data(db)
    normalized_project_code = _normalize_project_code(project_code)
    normalized_product_line = str(product_line or "").strip()
    normalized_module = str(module or "").strip()
    if not normalized_product_line:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="product_line must not be empty")

    case_stmt = select(TestCase.id, TestCase.case_id).where(
        TestCase.project_code == normalized_project_code,
        TestCase.product_line == normalized_product_line,
    )
    if normalized_module:
        case_stmt = case_stmt.where(TestCase.module == normalized_module)
    case_rows = list(db.execute(case_stmt).all())
    target_case_ids = [str(item_case_id or "").strip() for _item_id, item_case_id in case_rows if str(item_case_id or "").strip()]

    if case_rows and not cascade_cases:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"tree node still has {len(case_rows)} cases; set cascade_cases=true to delete them together",
        )

    deleted_cases = 0
    if case_rows and cascade_cases:
        deleted_cases = batch_delete_test_cases(db, case_ids=target_case_ids)

    node_stmt = select(TestCaseTreeNode).where(
        TestCaseTreeNode.project_code == normalized_project_code,
        TestCaseTreeNode.product_line == normalized_product_line,
    )
    if normalized_module:
        node_stmt = node_stmt.where(TestCaseTreeNode.module == normalized_module)
    else:
        node_stmt = node_stmt.where(TestCaseTreeNode.module == "")
    node = db.execute(node_stmt).scalar_one_or_none()
    if node is not None:
        db.delete(node)
        db.commit()
    return {
        "project_code": normalized_project_code,
        "product_line": normalized_product_line,
        "module": normalized_module,
        "deleted_cases": int(deleted_cases),
    }
