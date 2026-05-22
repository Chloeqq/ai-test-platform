# mypy: ignore-errors

import os
from contextlib import nullcontext
from copy import deepcopy

from playwright.sync_api import Page

from runner.action_registry import ACTION_DEFINITIONS
from runner.locator_resolver import resolve_locator
from runner.variable_resolver import resolve_variables

try:
    import allure
except ImportError:  # pragma: no cover - Allure is optional for local runner usage.
    allure = None


class YamlExecutor:
    def __init__(self, page: Page, username: str, password: str, base_url: str):
        self.page = page
        self.username = username
        self.password = password
        self.base_url = base_url

    def execute(self, test_case: dict) -> None:
        execution = test_case.get("execution")
        if not execution:
            raise ValueError(
                f"Missing execution section in test case: {test_case.get('id')}"
            )

        page_name = execution.get("page")
        steps = execution.get("steps", [])
        variables = execution.get("variables", {})
        data_context = test_case.get("_data", {})
        case_base_url = str(execution.get("page_url") or self.base_url or "").strip()

        resolved_context = self._build_context(variables, data_context)

        for index, step in enumerate(steps, start=1):
            self._pause_for_observation("before-step")
            self._execute_step(
                step,
                step_index=index,
                default_page_name=page_name,
                context=resolved_context,
                base_url=case_base_url,
            )
            self._pause_for_observation("after-step")
        self._hold_final_state_for_observation()

    def _build_context(self, variables: dict, data_context: dict) -> dict:
        """
        把 execution.variables 和 data_expander 传入的 _data 合并成最终上下文
        例如：
        variables:
          search_keyword: "{{keyword}}"

        _data:
          keyword: 手机

        最终得到：
          {
            "keyword": "手机",
            "search_keyword": "手机"
          }
        """
        context = dict(data_context)

        for key, value in variables.items():
            if isinstance(value, str):
                context[key] = resolve_variables(value, context)
            else:
                context[key] = value

        return context

    def _resolve_step_page_name(self, default_page_name: str, step: dict, step_index: int) -> str:
        page_name = str(step.get("page") or default_page_name or "").strip()
        if not page_name:
            raise ValueError(f"Step {step_index} cannot resolve page name")
        return page_name

    def _execute_step(
        self,
        step: dict,
        *,
        step_index: int,
        default_page_name: str,
        context: dict,
        base_url: str,
    ) -> None:
        action = step.get("action")
        action_definition = ACTION_DEFINITIONS.get(action)
        page_name = self._resolve_step_page_name(default_page_name, step, step_index)
        step_context = self._build_step_context(step, step_index=step_index, page_name=page_name)
        self._set_page_execution_context("_ai_current_step_context", step_context)
        step_title = self._render_allure_step_title(
            step,
            step_index=step_index,
            page_name=page_name,
            context=context,
        )

        if not action_definition:
            self._set_page_execution_context("_ai_failed_step_context", step_context)
            raise ValueError(f"Unsupported action at step {step_index}: {action}")

        target = step.get("target")
        locator = None

        try:
            with self._allure_step(step_title):
                self._attach_allure_expected_result(step)
                if action_definition["requires_target"]:
                    if not target:
                        raise ValueError(
                            f"Step {step_index} requires target for action '{action}' on page '{page_name}'"
                        )
                    selector = str(step.get("selector") or step.get("locator_value") or "").strip()
                    locator_type = str(step.get("locator_type") or "").strip()
                    role = self._resolve_role(step, action=str(action or "").strip(), locator_type=locator_type)
                    if not selector or not locator_type:
                        raise ValueError(
                            f"Step {step_index} requires compiled selector binding for action '{action}' on page '{page_name}'"
                        )
                    locator = resolve_locator(
                        self.page,
                        {
                            "locator_type": locator_type,
                            "locator_value": selector,
                            "role": role,
                        },
                    )
                elif target:
                    selector = str(step.get("selector") or step.get("locator_value") or "").strip()
                    locator_type = str(step.get("locator_type") or "").strip()
                    role = self._resolve_role(step, action=str(action or "").strip(), locator_type=locator_type)
                    if selector and locator_type:
                        locator = resolve_locator(
                            self.page,
                            {
                                "locator_type": locator_type,
                                "locator_value": selector,
                                "role": role,
                            },
                        )
                    else:
                        raise ValueError(
                            f"Step {step_index} references target '{target}' without compiled selector binding"
                        )

                action_definition["handler"](
                    page=self.page,
                    locator=locator,
                    step=step,
                    context=context,
                    username=self.username,
                    password=self.password,
                    base_url=base_url,
                )
        except Exception:
            self._set_page_execution_context("_ai_failed_step_context", step_context)
            raise

    def _build_step_context(self, step: dict, *, step_index: int, page_name: str) -> dict:
        traceability = step.get("traceability")
        action = str(step.get("action") or "").strip()
        locator_type = str(step.get("locator_type") or "").strip()
        return {
            "step_index": step_index,
            "page_code": page_name,
            "action": action,
            "element_code": str(step.get("target") or "").strip(),
            "target": str(step.get("target") or "").strip(),
            "selector": str(step.get("selector") or step.get("locator_value") or "").strip(),
            "locator_type": locator_type,
            "role": self._resolve_role(step, action=action, locator_type=locator_type),
            "intent_id": str(step.get("intent_id") or "").strip(),
            "traceability": deepcopy(traceability) if isinstance(traceability, dict) else {},
        }

    def _resolve_role(self, step: dict, *, action: str, locator_type: str) -> str:
        role = str(step.get("role") or "").strip()
        if role or locator_type != "role":
            return role
        if action == "click":
            return "button"
        if action in {"fill", "input", "type"}:
            return "textbox"
        return role

    def _render_allure_step_title(self, step: dict, *, step_index: int, page_name: str, context: dict) -> str:
        action = str(step.get("action") or "").strip().lower()
        target_name = str(step.get("target_name") or step.get("target") or "").replace("element:", "").strip()
        value = self._resolve_display_value(step.get("value"), context)
        safe_value = self._mask_sensitive_value(value, step=step)
        page_label = _friendly_page_name(page_name)
        if action in {"goto", "open"}:
            return f"{step_index}. 打开{page_label}"
        if action in {"fill", "input", "type"}:
            target_label = target_name or "目标输入框"
            return f"{step_index}. 在{target_label}输入 {safe_value}" if safe_value else f"{step_index}. 在{target_label}输入"
        if action == "click":
            target_label = target_name or "目标元素"
            return f"{step_index}. 点击{target_label}"
        if action.startswith("assert"):
            return f"{step_index}. 校验{target_name or page_label}"
        return f"{step_index}. 执行{action or '步骤'}"

    def _resolve_display_value(self, value, context: dict) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return resolve_variables(value, context)
        return str(value)

    def _mask_sensitive_value(self, value: str, *, step: dict) -> str:
        raw_text = " ".join(
            str(part or "").lower()
            for part in (
                step.get("target"),
                step.get("target_name"),
                step.get("locator_value"),
                step.get("selector"),
            )
        )
        if any(token in raw_text for token in ("password", "passwd", "pwd", "密码", "token", "secret")):
            return "******" if value else ""
        return value

    def _allure_step(self, title: str):
        if allure is None:
            return nullcontext()
        try:
            return allure.step(title)
        except Exception:
            return nullcontext()

    def _attach_allure_expected_result(self, step: dict) -> None:
        expected_result = str(step.get("expected_result") or "").strip()
        if not expected_result or allure is None:
            return
        try:
            allure.attach(
                expected_result,
                name="预期结果",
                attachment_type=allure.attachment_type.TEXT,
            )
        except Exception:
            pass

    def _set_page_execution_context(self, key: str, value: dict) -> None:
        try:
            setattr(self.page, key, value)
        except Exception:
            # Failure traceback is best-effort and must never change test behavior.
            pass

    def _pause_for_observation(self, _phase: str) -> None:
        delay_ms = _positive_int_from_env("WORKBENCH_VISIBLE_STEP_DELAY_MS", default=0, max_value=10_000)
        if delay_ms <= 0:
            return
        try:
            self.page.wait_for_timeout(delay_ms)
        except Exception:
            pass

    def _hold_final_state_for_observation(self) -> None:
        hold_ms = _positive_int_from_env("WORKBENCH_VISIBLE_HOLD_MS", default=0, max_value=60_000)
        if hold_ms <= 0:
            return
        try:
            self.page.wait_for_timeout(hold_ms)
        except Exception:
            pass


def _positive_int_from_env(name: str, *, default: int, max_value: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(float(raw_value))
    except ValueError:
        return default
    return max(0, min(value, max_value))


def _friendly_page_name(page_name: str) -> str:
    normalized = str(page_name or "").strip().lower()
    names = {
        "login": "登录页面",
        "auth": "认证页面",
    }
    return names.get(normalized, f"{page_name}页面" if page_name else "页面")
