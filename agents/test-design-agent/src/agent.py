from pathlib import Path
import os
import yaml
from dotenv import load_dotenv
from openai import OpenAI

from .prompt import SYSTEM_PROMPT, USER_TEMPLATE
from .schema import TestCase
from .test_points import build_test_point_plan, render_steps_from_test_point_plan
from .tools.page_object_loader import list_page_elements
from .tools.target_validator import validate_targets


ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV)


class TestDesignAgent:
    SUPPORTED_ACTIONS = {"login", "click", "fill", "wait_for", "assert_visible", "assert_url"}
    STABLE_PAGE_BASELINES = {
        "login": {
            "required_targets": {"home_menu"},
            "required_step_prefix": [
                {"action": "login"},
                {"action": "assert_visible", "target": "home_menu"},
            ],
        },
        "order": {
            "required_targets": {"order_menu", "order_list_title"},
            "required_step_prefix": [
                {"action": "login"},
                {"action": "click", "target": "order_menu"},
            ],
        },
        "permission": {
            "required_targets": {"permission_menu", "permission_table"},
            "required_step_prefix": [
                {"action": "login"},
                {"action": "click", "target": "permission_menu"},
            ],
        },
        "product": {
            "required_targets": {"product_menu", "product_list_title", "search_input", "search_button"},
            "required_step_prefix": [
                {"action": "login"},
                {"action": "click", "target": "product_menu"},
            ],
        },
    }

    def __init__(self, model: str | None = None):
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        final_model = model or os.getenv("OPENAI_MODEL", "qwen3.5-plus")

        if not api_key:
            raise ValueError(f"OPENAI_API_KEY not found. Please set it in {ROOT_ENV}")

        if not base_url:
            raise ValueError(f"OPENAI_BASE_URL not found. Please set it in {ROOT_ENV}")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = final_model

    def _clean_yaml_text(self, content: str) -> str:
        cleaned = content.strip()

        if cleaned.startswith("```yaml"):
            cleaned = cleaned[len("```yaml"):].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[len("```"):].strip()

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        return cleaned

    def _normalize_testcase(self, parsed: dict, page: str) -> dict:
        """
        把模型输出归一化成当前项目已跑通的固定结构。
        """
        if not isinstance(parsed, dict):
            raise ValueError("Model output is not a YAML object")

        meta = parsed.get("meta", {})
        execution = parsed.get("execution", {})

        requirement = parsed.get("requirement") or meta.get("requirement", [])
        if isinstance(requirement, str):
            requirement = [requirement]

        normalized_module = page
        normalized_owner = "qa-team"
        normalized_status = "automated"

        default_titles = {
            "login": "管理员登录验证",
            "product": "商品功能验证",
            "order": "订单功能验证",
            "permission": "权限功能验证",
        }

        normalized_title = (
            parsed.get("title")
            or meta.get("title")
            or default_titles.get(page, f"{page} 功能验证")
        )

        normalized_id = (
            parsed.get("id")
            or meta.get("id")
            or f"TC-{page.upper()}-001"
        )
        normalized_id = normalized_id.replace("_", "-").upper()

        normalized = {
            "version": "v4",
            "id": normalized_id,
            "title": normalized_title,
            "module": normalized_module,
            "priority": parsed.get("priority") or meta.get("priority", "P1"),
            "tags": parsed.get("tags") or meta.get("tags", [page]),
            "owner": normalized_owner,
            "status": normalized_status,
            "description": parsed.get("description") or meta.get("description", ""),
            "requirement": requirement,
            "data": parsed.get("data", {}),
            "execution": {
                "runner": "playwright",
                "page": execution.get("page") or parsed.get("page") or meta.get("page") or page,
                "variables": execution.get("variables", {}),
                "steps": execution.get("steps", []),
            },
        }

        return normalized

    def _rewrite_common_targets(self, test_case: dict, page: str) -> dict:
        """
        将模型常见的通用命名修正为你当前项目已跑通版本的 target 命名。
        """
        target_map = {
            "product": {
                "product_module": "product_menu",
                "nav_product": "product_menu",
                "menu_product": "product_menu",
                "search_field": "search_input",
                "keyword_input": "search_input",
                "btn_search": "search_button",
                "search_btn": "search_button",
                "product_list": "product_list_title",
                "list_title": "product_list_title",
            },
            "order": {
                "nav_order": "order_menu",
                "menu_order": "order_menu",
                "order_list": "order_list_title",
                "list_title": "order_list_title",
            },
            "permission": {
                "nav_permission": "permission_menu",
                "menu_permission": "permission_menu",
                "permission_list": "permission_table",
                "list_table": "permission_table",
            },
            "login": {
                "home_link": "home_menu",
                "index_link": "home_menu",
            },
        }

        page_map = target_map.get(page, {})
        steps = test_case.get("execution", {}).get("steps", [])

        for step in steps:
            target = step.get("target")
            if target in page_map:
                step["target"] = page_map[target]

        return test_case

    def _normalize_steps_for_stable_style(self, test_case: dict) -> dict:
        """
        让输出更贴近当前已跑通版本：
        - login 不带 target/value
        - click/wait_for/assert_visible 只保留必要字段
        """
        steps = test_case.get("execution", {}).get("steps", [])
        normalized_steps = []

        for step in steps:
            action = step.get("action")
            target = step.get("target")
            value = step.get("value")

            if action == "login":
                normalized_steps.append({"action": "login"})
                continue

            if action in {"click", "wait_for", "assert_visible"}:
                item = {"action": action}
                if target:
                    item["target"] = target
                normalized_steps.append(item)
                continue

            if action == "fill":
                item = {"action": "fill"}
                if target:
                    item["target"] = target
                if value is not None:
                    item["value"] = value
                normalized_steps.append(item)
                continue

            if action == "assert_url":
                item = {"action": "assert_url"}
                if value is not None:
                    item["value"] = value
                normalized_steps.append(item)
                continue

            normalized_steps.append(step)

        test_case["execution"]["steps"] = normalized_steps
        return test_case

    def _drop_empty_step_fields(self, test_case: dict) -> dict:
        """
        删除 step 中无意义的 null 字段。
        """
        steps = test_case.get("execution", {}).get("steps", [])
        cleaned_steps = []

        for step in steps:
            cleaned = dict(step)

            if cleaned.get("target") is None:
                cleaned.pop("target", None)

            if cleaned.get("value") is None:
                cleaned.pop("value", None)

            cleaned_steps.append(cleaned)

        test_case["execution"]["steps"] = cleaned_steps
        return test_case

    def _validate_project_rules(self, test_case: dict, page: str) -> None:
        execution = test_case.get("execution", {})
        execution_page = execution.get("page")
        steps = execution.get("steps", [])

        if execution_page != page:
            raise ValueError(
                f"Generated execution.page must be '{page}', got '{execution_page}'"
            )

        if not steps:
            raise ValueError("Generated test case must contain at least one execution step")

        for index, step in enumerate(steps, start=1):
            action = step.get("action")

            if action not in self.SUPPORTED_ACTIONS:
                raise ValueError(f"Unsupported action at step {index}: {action}")

            if action == "login":
                if "target" in step or "value" in step:
                    raise ValueError("login step must not include target or value")
                continue

            if action in {"click", "wait_for", "assert_visible", "fill"} and not step.get("target"):
                raise ValueError(f"Step {index} action '{action}' requires target")

            if action == "fill" and step.get("value") in (None, ""):
                raise ValueError(f"Step {index} action 'fill' requires a non-empty value")

            if action == "assert_url" and step.get("value") in (None, ""):
                raise ValueError(f"Step {index} action 'assert_url' requires a non-empty value")

    def _enforce_stable_page_baseline(self, test_case: dict, page: str) -> dict:
        baseline = self.STABLE_PAGE_BASELINES.get(page)
        if not baseline:
            return test_case

        steps = list(test_case.get("execution", {}).get("steps", []))
        if not steps:
            return test_case

        required_prefix = baseline["required_step_prefix"]
        prefix_length = len(required_prefix)
        remaining_steps = steps[prefix_length:]
        test_case["execution"]["steps"] = required_prefix + remaining_steps
        return test_case

    def _build_test_points_from_case(self, test_case: dict) -> dict:
        requirement = test_case.get("requirement") or []
        if isinstance(requirement, str):
            requirement = [requirement]

        execution = test_case.get("execution", {})
        page = execution.get("page", "")
        steps = execution.get("steps", [])

        plan = build_test_point_plan(page=page, requirement=requirement, steps=steps)
        return plan.model_dump(exclude_none=True)

    def _render_case_from_test_points(self, test_case: dict, plan: dict) -> dict:
        rendered = dict(test_case)
        execution = dict(rendered.get("execution", {}))
        execution["steps"] = render_steps_from_test_point_plan(plan)
        rendered["execution"] = execution
        return rendered

    def generate(self, requirement: str, page: str) -> dict:
        elements = list_page_elements(page)
        element_text = "\n".join(f"- {e}" for e in elements)

        prompt = f"""
{USER_TEMPLATE.format(requirement=requirement)}

当前页面名称:
{page}

当前页面可用元素（target 只能从这里选）:
{element_text}

强制要求:
1. execution.page 必须使用 {page}
2. target 只能使用以上元素名称
3. 不允许生成不存在的 target
4. 不要输出 Markdown 代码块
5. 只输出纯 YAML
6. login 步骤不能带 target 或 value
7. 必须严格复用当前稳定 smoke 命名风格
8. {page} 页面的前两步必须和当前稳定 smoke 基线保持一致
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        content = response.choices[0].message.content
        print("Raw model output:\n", content)

        cleaned = self._clean_yaml_text(content)
        parsed = yaml.safe_load(cleaned)

        normalized = self._normalize_testcase(parsed, page)
        normalized = self._rewrite_common_targets(normalized, page)
        normalized = self._normalize_steps_for_stable_style(normalized)
        normalized = self._enforce_stable_page_baseline(normalized, page)
        plan = self._build_test_points_from_case(normalized)
        normalized = self._render_case_from_test_points(normalized, plan)
        normalized = self._drop_empty_step_fields(normalized)

        validated = TestCase(**normalized)
        result = validated.model_dump(exclude_none=True)

        self._validate_project_rules(result, page)
        validate_targets(result)

        return result

    def generate_test_points(self, requirement: str, page: str) -> dict:
        test_case = self.generate(requirement=requirement, page=page)
        return self._build_test_points_from_case(test_case)
