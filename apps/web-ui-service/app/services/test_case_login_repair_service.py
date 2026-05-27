from __future__ import annotations

from typing import Any, Sequence

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.page_object import PageElement, PageObject
from app.services.test_case_data_service import normalize_optional_text
from app.services.test_case_service import (
    _env_flag,
    _infer_step_action_for_repair,
    _normalize_match_text,
    _normalize_project_code,
    _normalize_step_text,
)
from shared_backend.case_ids import normalize_client_code


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
    elements = db.execute(
        select(PageElement)
        .where(PageElement.page_object_id == int(page_object.id))
        .order_by(PageElement.id.asc())
    ).scalars().all()
    if normalized_page == "login":
        elements = list(elements) + _load_login_success_data_testid_elements(
            db,
            project_code=normalized_project,
            client=normalized_client,
        )
    return elements


def _load_login_success_data_testid_elements(
    db: Session,
    *,
    project_code: str,
    client: str,
) -> list[PageElement]:
    """登录成功态会进入首页，保存层修复时允许引用首页已治理 data-testid。"""
    return list(
        db.execute(
            select(PageElement)
            .join(PageObject, PageElement.page_object_id == PageObject.id)
            .where(
                PageObject.project_code == project_code,
                PageObject.client == client,
                PageObject.page_code.in_(["home", "layout"]),
                PageElement.element_code == "home-page",
                PageElement.locator_type == "data-testid",
            )
            .order_by(PageElement.id.asc())
        )
        .scalars()
        .all()
    )


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


_LOGIN_SEMANTIC_TARGET_TO_TESTID_CODE = {
    "username_input": "login-username-input",
    "password_input": "login-password-input",
    "login_button": "login-submit-btn",
    "home_menu": "home-page",
}

_LOGIN_TESTID_CODE_TO_SEMANTIC_TARGET = {
    testid_code: semantic_code
    for semantic_code, testid_code in _LOGIN_SEMANTIC_TARGET_TO_TESTID_CODE.items()
}


def _prefer_login_data_testid_counterpart(
    *,
    expected_code: str,
    all_elements: list[PageElement],
) -> PageElement | None:
    """保存层二次修复时，语义 target 要优先桥接到真实 data-testid 元素。"""
    counterpart_code = _LOGIN_SEMANTIC_TARGET_TO_TESTID_CODE.get(str(expected_code or "").strip().lower(), "")
    if not counterpart_code:
        return None
    for candidate in all_elements:
        code = str(candidate.element_code or "").strip().lower()
        locator_type = str(candidate.locator_type or "").strip().lower()
        if code == counterpart_code and locator_type == "data-testid":
            return candidate
    return None


def _should_preserve_login_semantic_target(*, step: dict[str, Any], element: PageElement) -> bool:
    """登录页旧语义 target 要保留，只把 locator 升级到真实 data-testid。"""
    raw_target = _normalize_step_text(step.get("target"))
    if not raw_target.startswith("element:"):
        return False
    semantic_code = raw_target.removeprefix("element:").strip().lower()
    element_code = str(element.element_code or "").strip().lower()
    return _LOGIN_TESTID_CODE_TO_SEMANTIC_TARGET.get(element_code) == semantic_code


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
        preferred = _prefer_login_data_testid_counterpart(expected_code=expected_code, all_elements=all_elements)
        if preferred is not None:
            matched_by_target = (preferred, _classify_login_element_role(preferred))
        else:
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
                if not _should_preserve_login_semantic_target(step=step, element=element):
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
    # Lazy import to avoid circular dependency: _workbench_yaml_script is
    # defined in test_case_service AFTER the login-repair section.
    from app.services.test_case_service import _workbench_yaml_script  # noqa: PLC0415

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
