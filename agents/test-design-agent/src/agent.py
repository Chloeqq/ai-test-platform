# mypy: ignore-errors

from copy import deepcopy
from pathlib import Path
import os
import re
import yaml
from dotenv import load_dotenv
from openai import OpenAI
from typing import Any

from .prompt import SYSTEM_PROMPT, USER_TEMPLATE
from .schema import TestCase
from .test_points import build_test_point_plan, render_steps_from_test_point_plan
from .tools.page_object_loader import list_page_elements
from .tools.target_validator import validate_targets


ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV)


class TestDesignAgent:
    SUPPORTED_ACTIONS = {"login", "click", "fill", "wait_for", "assert_visible", "assert_url", "goto"}
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
        fallback_raw = os.getenv("OPENAI_MODEL_FALLBACKS", "gpt-5.2,gpt-5.4")

        if not api_key:
            raise ValueError(f"OPENAI_API_KEY not found. Please set it in {ROOT_ENV}")

        if not base_url:
            raise ValueError(f"OPENAI_BASE_URL not found. Please set it in {ROOT_ENV}")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = final_model
        self.fallback_models = [
            item.strip()
            for item in fallback_raw.split(",")
            if item.strip() and item.strip() != self.model
        ]

    @staticmethod
    def _is_model_not_found_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return "model_not_found" in text or "no available channel for model" in text

    def _create_completion_with_fallback(self, messages: list[dict], temperature: float):
        candidate_models = [self.model] + self.fallback_models
        last_error: Exception | None = None
        for candidate in candidate_models:
            try:
                return self.client.chat.completions.create(
                    model=candidate,
                    messages=messages,
                    temperature=temperature,
                )
            except Exception as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        raise RuntimeError("No model candidate available for completion")

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
        elif isinstance(requirement, dict):
            requirement = [f"{key}: {value}" for key, value in requirement.items()]
        elif not isinstance(requirement, list):
            requirement = [str(requirement)]

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

            if action == "goto" and step.get("value") in (None, ""):
                raise ValueError(f"Step {index} action 'goto' requires a non-empty value")

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

        response = self._create_completion_with_fallback(
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

    def design_bundle(
        self,
        *,
        requirement: str = "",
        page: str = "",
        requirement_spec: dict[str, Any] | None = None,
        case: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_spec = requirement_spec if isinstance(requirement_spec, dict) else {}
        normalized_page = str(page or normalized_spec.get("page", "") or "").strip() or "product"
        normalized_requirement = str(requirement or normalized_spec.get("design_input", "") or normalized_spec.get("raw_requirement", "") or "").strip()
        requirement_rows = self._normalize_requirement_rows(
            requirement=normalized_requirement,
            requirement_spec=normalized_spec,
        )

        if case is None:
            if normalized_spec:
                case = self._build_case_from_requirement_spec(
                    requirement_spec=normalized_spec,
                    page=normalized_page,
                    requirement_rows=requirement_rows,
                )
            else:
                generated_requirement = normalized_requirement or f"{normalized_page} 功能验证"
                case = self.generate(requirement=generated_requirement, page=normalized_page)
        else:
            case = deepcopy(case)

        if normalized_spec:
            test_points = self._build_points_from_requirement_spec(
                requirement_spec=normalized_spec,
                page=normalized_page,
                intents=normalized_spec.get("test_intents") if isinstance(normalized_spec.get("test_intents"), list) else [],
            )
        else:
            test_points = self._build_test_points_from_case(case)

        designed_case = self._render_case_from_test_points(case, test_points)
        designed_case = self._enforce_stable_page_baseline(designed_case, normalized_page)
        designed_case = self._drop_empty_step_fields(designed_case)
        designed_case = self._enrich_case_for_enterprise(designed_case, test_points, normalized_spec)

        traceability = self._build_traceability(designed_case, test_points, normalized_spec)
        review_summary = self._build_enterprise_review_summary(designed_case, test_points, traceability)
        bundle_confidence = self._calculate_bundle_confidence(designed_case, test_points, review_summary)
        bundle_requires_review = bool(
            review_summary["pending_review_count"]
            or review_summary["low_confidence_point_count"]
            or bundle_confidence < 0.75
        )

        return {
            "version": "TestDesignBundleV1",
            "page": normalized_page,
            "requirement": requirement_rows,
            "requirement_spec": normalized_spec,
            "case": designed_case,
            "test_points": test_points,
            "traceability": traceability,
            "review_summary": review_summary,
            "confidence": bundle_confidence,
            "warnings": self._merge_unique_strings(
                test_points.get("warnings", []) if isinstance(test_points, dict) else [],
                traceability.get("warnings", []) if isinstance(traceability, dict) else [],
                review_summary.get("warnings", []) if isinstance(review_summary, dict) else [],
            ),
            "requires_review": bundle_requires_review,
            "metadata": {
                "generator": "test-design-agent",
                "mode": "enterprise_bundle",
                "requirement_spec_present": bool(normalized_spec),
                "case_confidence": designed_case.get("confidence", 0.0),
            },
        }

    def _normalize_requirement_rows(self, *, requirement: str, requirement_spec: dict[str, Any]) -> list[str]:
        rows: list[str] = []
        if requirement:
            rows.append(requirement)
        spec_rows = requirement_spec.get("requirement")
        if isinstance(spec_rows, str):
            spec_rows = [spec_rows]
        if isinstance(spec_rows, list):
            for item in spec_rows:
                text = str(item).strip()
                if text and text not in rows:
                    rows.append(text)
        raw_requirement = str(requirement_spec.get("raw_requirement", "")).strip()
        if raw_requirement and raw_requirement not in rows:
            rows.append(raw_requirement)
        design_input = str(requirement_spec.get("design_input", "")).strip()
        if design_input and design_input not in rows:
            rows.append(design_input)
        return rows or ["基础流程验证"]

    def _build_case_from_requirement_spec(
        self,
        *,
        requirement_spec: dict[str, Any],
        page: str,
        requirement_rows: list[str],
    ) -> dict[str, Any]:
        intents = requirement_spec.get("test_intents") if isinstance(requirement_spec.get("test_intents"), list) else []
        points = self._build_points_from_requirement_spec(page=page, requirement_spec=requirement_spec, intents=intents)
        case_id = str(requirement_spec.get("case_id", "")).strip() or f"TC-{page.upper()}-001"
        title = (
            str(requirement_spec.get("title", "")).strip()
            or str(requirement_spec.get("design_input", "")).strip()
            or f"{page} 企业回归验证"
        )
        case = {
            "version": "v4",
            "id": case_id.replace("_", "-").upper(),
            "title": title[:120],
            "module": page,
            "priority": str(requirement_spec.get("priority", "P1")).strip() or "P1",
            "tags": self._merge_tags(page=page, requirement_spec=requirement_spec),
            "owner": "qa-team",
            "status": "automated",
            "description": str(requirement_spec.get("design_input", "")).strip() or str(requirement_spec.get("raw_requirement", "")).strip(),
            "requirement": requirement_rows,
            "data": {
                "source": "requirement_spec",
                "intent_count": len(intents),
            },
            "execution": {
                "runner": "playwright",
                "page": page,
                "variables": {},
                "steps": render_steps_from_test_point_plan(points),
            },
        }
        case = self._enforce_stable_page_baseline(case, page)
        case = self._drop_empty_step_fields(case)
        return case

    def _build_points_from_requirement_spec(
        self,
        *,
        page: str,
        requirement_spec: dict[str, Any],
        intents: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        normalized_intents = intents if isinstance(intents, list) else []
        field_definitions = self._normalize_field_definitions(requirement_spec)
        requirement_rows = self._normalize_requirement_rows(
            requirement=str(requirement_spec.get("design_input", "")).strip() or str(requirement_spec.get("raw_requirement", "")).strip(),
            requirement_spec=requirement_spec,
        )

        needs_login_precondition = not any(
            self._map_intent_to_step(
                page=page,
                intent_type=str(intent.get("intent_type", "functional")).strip().lower() or "functional",
                title=str(intent.get("title", "")).strip() or "",
                steps_hint=intent.get("steps_hint"),
            )[0] == "login"
            for intent in normalized_intents
            if isinstance(intent, dict)
        )

        points: list[dict[str, Any]] = []
        if needs_login_precondition:
            points.append(
                {
                    "key": f"{page}-00",
                    "point_type": "precondition",
                    "action": "login",
                    "description": "Use shared login precondition.",
                    "priority": "P0",
                    "dependencies": [],
                    "source_ids": [],
                    "dependent_elements": [],
                    "confidence": 0.96,
                    "warnings": [],
                    "requires_review": False,
                    "suggestion": "execute",
                    "review_reason": "共享登录预条件稳定，可直接执行。",
                }
            )

        for index, intent in enumerate(normalized_intents[:80], start=1):
            if not isinstance(intent, dict):
                continue
            title = str(intent.get("title", "")).strip() or f"intent-{index:02d}"
            intent_type = str(intent.get("intent_type", "functional")).strip().lower() or "functional"
            priority = str(intent.get("priority", "P1")).strip() or "P1"
            dependencies = intent.get("dependencies") if isinstance(intent.get("dependencies"), list) else []
            source_ids = intent.get("source_ids") if isinstance(intent.get("source_ids"), list) else []
            action, target, value = self._map_intent_to_step(
                page=page,
                intent_type=intent_type,
                title=title,
                steps_hint=intent.get("steps_hint"),
            )
            point_fields = self._point_fields_for_intent(
                action=action,
                target=target,
                value=value,
                intent_type=intent_type,
            )
            point = {
                "key": str(intent.get("intent_id", f"intent-{index:02d}")).strip() or f"intent-{index:02d}",
                "point_type": self._map_intent_type_to_point_type(intent_type),
                "action": action,
                "description": title[:200],
                "priority": priority,
                "dependencies": [str(item).strip() for item in dependencies if str(item).strip()],
                "source_ids": [str(item).strip() for item in source_ids if str(item).strip()],
                "dependent_elements": point_fields["dependent_elements"],
                "confidence": point_fields["confidence"],
                "warnings": point_fields["warnings"],
                "requires_review": point_fields["requires_review"],
                "suggestion": point_fields["suggestion"],
                "review_reason": point_fields["review_reason"],
            }
            if target:
                point["target"] = target
            if value is not None:
                point["value"] = value
            points.append(point)

        points.extend(self._build_points_from_field_definitions(page=page, field_definitions=field_definitions))

        plan = {
            "version": "TestPointPlanV1",
            "project": "default",
            "case_id": str(requirement_spec.get("case_id", "")).strip() or f"TC-{page.upper()}-001",
            "page": page,
            "source_type": "requirement_intents",
            "requirement": requirement_rows,
            "generated_at": requirement_spec.get("generated_at") or "enterprise_bundle",
            "points": points,
            "metadata": {
                "build_source": "requirement_spec.test_intents+field_definitions" if field_definitions else "requirement_spec.test_intents",
                "intent_count": len(normalized_intents),
                "field_definition_count": len(field_definitions),
                "point_count": len(points),
                "technique_distribution": self._build_technique_distribution(points),
            },
        }
        plan = self._annotate_plan_summary(plan)
        return plan

    def _normalize_field_definitions(self, requirement_spec: dict[str, Any]) -> list[dict[str, Any]]:
        raw_items: list[Any] = []
        for key in ("field_definitions", "parameter_constraints"):
            value = requirement_spec.get(key)
            if isinstance(value, list):
                raw_items.extend(value)

        normalized: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for index, item in enumerate(raw_items[:40], start=1):
            if not isinstance(item, dict):
                continue
            field_key = str(item.get("field_key", "")).strip() or str(item.get("name", "")).strip() or f"field_{index:02d}"
            field_type = str(item.get("field_type", "")).strip().lower() or str(item.get("type", "")).strip().lower() or "string"
            target = str(item.get("target", "")).strip() or str(item.get("page_target", "")).strip()
            constraints = self._normalize_field_constraints(item)
            format_hint = str(constraints.get("format", "")).strip().lower()
            if field_type == "string" and format_hint in {"date", "date-time", "datetime", "timestamp"}:
                field_type = "datetime" if format_hint in {"date-time", "datetime", "timestamp"} else "date"
            enum_values = item.get("enum") if isinstance(item.get("enum"), list) else constraints.get("enum") if isinstance(constraints.get("enum"), list) else []
            source_ids = [str(source_id).strip() for source_id in item.get("source_ids", []) if str(source_id).strip()] if isinstance(item.get("source_ids"), list) else []
            marker = (field_key, target, field_type)
            if marker in seen:
                continue
            seen.add(marker)
            parameter_location = str(item.get("location", "")).strip().lower() or str(item.get("in", "")).strip().lower()
            api_method = str(item.get("method", "")).strip().upper()
            api_path = str(item.get("path", "")).strip()
            normalized.append(
                {
                    "field_key": field_key,
                    "title": str(item.get("title", "")).strip() or str(item.get("label", "")).strip() or field_key,
                    "field_type": field_type,
                    "target": target or None,
                    "required": bool(item.get("required", False)),
                    "constraints": constraints,
                    "enum_values": [str(enum_value) for enum_value in enum_values if str(enum_value).strip()],
                    "source_ids": source_ids,
                    "parameter_location": parameter_location or None,
                    "api_method": api_method or None,
                    "api_path": api_path or None,
                }
            )
        return normalized

    def _build_points_from_field_definitions(
        self,
        *,
        page: str,
        field_definitions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        points: list[dict[str, Any]] = []
        for field in field_definitions[:20]:
            if not isinstance(field, dict):
                continue
            field_key = str(field.get("field_key", "")).strip() or "field"
            title = str(field.get("title", "")).strip() or field_key
            field_type = str(field.get("field_type", "")).strip().lower() or "string"
            target = str(field.get("target", "")).strip() or None
            constraints = field.get("constraints") if isinstance(field.get("constraints"), dict) else {}
            enum_values = [str(item).strip() for item in field.get("enum_values", []) if str(item).strip()] if isinstance(field.get("enum_values"), list) else []
            source_ids = [str(item).strip() for item in field.get("source_ids", []) if str(item).strip()] if isinstance(field.get("source_ids"), list) else []
            parameter_location = str(field.get("parameter_location", "")).strip().lower()
            api_method = str(field.get("api_method", "")).strip().upper()
            api_path = str(field.get("api_path", "")).strip()
            is_api_parameter = parameter_location in {"query", "path", "header", "body", "cookie"}

            scenarios: list[dict[str, Any]] = []
            if bool(field.get("required", False)):
                scenarios.append(
                    {
                        "technique_type": "equivalence",
                        "technique_source": "required_empty",
                        "description": f"{title} 必填为空值校验",
                        "value": "",
                    }
                )
            if enum_values:
                scenarios.append(
                    {
                        "technique_type": "equivalence",
                        "technique_source": "enum_valid",
                        "description": f"{title} 枚举有效值校验",
                        "value": enum_values[0],
                    }
                )
                scenarios.append(
                    {
                        "technique_type": "equivalence",
                        "technique_source": "enum_invalid",
                        "description": f"{title} 枚举非法值校验",
                        "value": "__invalid_enum__",
                    }
                )
            elif field_type in {"string", "text", "keyword", "search"}:
                min_length = self._safe_int(constraints.get("min_length"))
                max_length = self._safe_int(constraints.get("max_length"))
                if min_length and min_length > 0:
                    scenarios.append(
                        {
                            "technique_type": "boundary",
                            "technique_source": "min_length",
                            "description": f"{title} 最小长度边界校验",
                            "value": self._repeat_value("a", min_length),
                        }
                    )
                if max_length and max_length > 0:
                    scenarios.append(
                        {
                            "technique_type": "boundary",
                            "technique_source": "over_max_length",
                            "description": f"{title} 超最大长度边界校验",
                            "value": self._repeat_value("a", min(max_length + 1, max_length + 8, 80)),
                        }
                    )
            elif field_type in {"integer", "number", "decimal", "float", "amount", "price", "currency_amount"}:
                min_value = self._safe_float(constraints.get("min"))
                max_value = self._safe_float(constraints.get("max"))
                if min_value is not None:
                    scenarios.append(
                        {
                            "technique_type": "boundary",
                            "technique_source": "min_value",
                            "description": f"{title} 最小值边界校验",
                            "value": self._stringify_numeric(min_value),
                        }
                    )
                if max_value is not None:
                    scenarios.append(
                        {
                            "technique_type": "boundary",
                            "technique_source": "over_max_value",
                            "description": f"{title} 超最大值边界校验",
                            "value": self._stringify_numeric(max_value + (1 if float(max_value).is_integer() else 0.01)),
                        }
                    )
                if field_type in {"amount", "price", "currency_amount", "decimal", "float"}:
                    scenarios.append(
                        {
                            "technique_type": "equivalence",
                            "technique_source": "negative_value",
                            "description": f"{title} 负金额/负数值校验",
                            "value": "-0.01",
                        }
                    )
            elif field_type in {"date", "datetime", "timestamp"}:
                min_date = str(constraints.get("min_date", "")).strip() or "2026-01-01"
                max_date = str(constraints.get("max_date", "")).strip() or "2026-12-31"
                scenarios.append(
                    {
                        "technique_type": "boundary",
                        "technique_source": "min_date",
                        "description": f"{title} 最小日期边界校验",
                        "value": min_date,
                    }
                )
                scenarios.append(
                    {
                        "technique_type": "boundary",
                        "technique_source": "max_date",
                        "description": f"{title} 最大日期边界校验",
                        "value": max_date,
                    }
                )
                scenarios.append(
                    {
                        "technique_type": "equivalence",
                        "technique_source": "invalid_date_format",
                        "description": f"{title} 非法日期格式校验",
                        "value": "2026/13/40",
                    }
                )

            unique_scenarios: list[dict[str, Any]] = []
            seen_scenarios: set[tuple[str, str, str]] = set()
            for scenario in scenarios[:3]:
                marker = (
                    str(scenario.get("technique_type", "")).strip(),
                    str(scenario.get("technique_source", "")).strip(),
                    str(scenario.get("value", "")).strip(),
                )
                if marker in seen_scenarios:
                    continue
                seen_scenarios.add(marker)
                unique_scenarios.append(scenario)

            for index, scenario in enumerate(unique_scenarios, start=1):
                point_fields = self._point_fields_for_constraint(
                    target=target,
                    technique_type=str(scenario.get("technique_type", "")).strip() or "normal",
                    technique_source=str(scenario.get("technique_source", "")).strip() or "field_definition",
                )
                safe_field_key = re.sub(r"[^a-zA-Z0-9]+", "-", field_key).strip("-").lower() or "field"
                safe_technique = re.sub(r"[^a-zA-Z0-9]+", "-", str(scenario.get("technique_source", "")).strip()).strip("-").lower() or f"scenario-{index:02d}"
                point: dict[str, Any] = {
                    "key": f"{page}-{safe_field_key}-{safe_technique}",
                    "point_type": "api" if is_api_parameter else "input",
                    "action": "api_request" if is_api_parameter else "fill",
                    "field_key": field_key,
                    "description": str(scenario.get("description", "")).strip() or f"{title} 约束校验",
                    "priority": "P1",
                    "dependencies": [],
                    "source_ids": source_ids,
                    "dependent_elements": point_fields["dependent_elements"],
                    "confidence": point_fields["confidence"],
                    "warnings": point_fields["warnings"],
                    "requires_review": point_fields["requires_review"],
                    "suggestion": point_fields["suggestion"],
                    "review_reason": point_fields["review_reason"],
                    "technique_type": point_fields["technique_type"],
                    "technique_source": point_fields["technique_source"],
                    "technique_confidence": point_fields["technique_confidence"],
                    "execution_scope": point_fields["execution_scope"],
                }
                if target:
                    point["target"] = target
                point["value"] = scenario.get("value")
                if parameter_location:
                    point["parameter_location"] = parameter_location
                if api_method:
                    point["api_method"] = api_method
                if api_path:
                    point["api_path"] = api_path
                points.append(point)
        return points

    def _build_traceability(
        self,
        case: dict[str, Any],
        test_points: dict[str, Any],
        requirement_spec: dict[str, Any],
    ) -> dict[str, Any]:
        execution = case.get("execution", {}) if isinstance(case.get("execution"), dict) else {}
        steps = execution.get("steps", []) if isinstance(execution.get("steps"), list) else []
        points = test_points.get("points", []) if isinstance(test_points.get("points"), list) else []
        point_keys = [str(point.get("key", "")).strip() for point in points if isinstance(point, dict)]
        mainline_point_keys = [
            str(point.get("key", "")).strip()
            for point in points
            if isinstance(point, dict) and str(point.get("execution_scope", "mainline")).strip().lower() != "design_only"
        ]
        target_map: dict[str, list[int]] = {}
        for index, step in enumerate(steps, start=1):
            target = str((step or {}).get("target", "")).strip()
            if not target:
                continue
            target_map.setdefault(target, []).append(index)

        point_links: list[dict[str, Any]] = []
        missing_targets: list[str] = []
        for point in points:
            if not isinstance(point, dict):
                continue
            target = str(point.get("target", "")).strip()
            linked_steps = target_map.get(target, []) if target else []
            execution_scope = str(point.get("execution_scope", "mainline")).strip().lower() or "mainline"
            if execution_scope != "design_only" and target and not linked_steps:
                missing_targets.append(target)
            point_links.append(
                {
                    "point_key": str(point.get("key", "")).strip(),
                    "action": str(point.get("action", "")).strip(),
                    "target": target,
                    "execution_scope": execution_scope,
                    "linked_step_indexes": linked_steps,
                    "dependent_elements": [str(item).strip() for item in point.get("dependent_elements", []) if str(item).strip()] if isinstance(point.get("dependent_elements"), list) else [],
                }
            )

        coverage_ratio = round(len(mainline_point_keys) / max(1, len(steps)), 2) if steps else 0.0
        warnings = []
        if missing_targets:
            warnings.append(f"存在 {len(missing_targets)} 个测试点无法映射到执行步骤")

        return {
            "point_links": point_links,
            "step_target_map": target_map,
            "coverage_ratio": coverage_ratio,
            "missing_targets": missing_targets,
            "mainline_point_count": len(mainline_point_keys),
            "design_only_point_count": max(0, len(point_keys) - len(mainline_point_keys)),
            "warnings": warnings,
            "requirement_source": "requirement_spec" if requirement_spec else "generated_case",
        }

    def _build_enterprise_review_summary(
        self,
        case: dict[str, Any],
        test_points: dict[str, Any],
        traceability: dict[str, Any],
    ) -> dict[str, Any]:
        points = test_points.get("points", []) if isinstance(test_points.get("points"), list) else []
        low_confidence_point_count = sum(1 for point in points if isinstance(point, dict) and float(point.get("confidence", 0.0) or 0.0) < 0.75)
        pending_review_count = sum(
            1
            for point in points
            if isinstance(point, dict)
            and bool(point.get("requires_review"))
            and str(point.get("suggestion", "")).strip().lower() != "skip"
        )
        warnings = list(dict.fromkeys(
            [str(item).strip() for item in (test_points.get("warnings") or []) if str(item).strip()]
            + [str(item).strip() for item in (traceability.get("warnings") or []) if str(item).strip()]
        ))
        return {
            "low_confidence_point_count": low_confidence_point_count,
            "pending_review_count": pending_review_count,
            "execute_suggestion_count": int((test_points.get("review_summary") or {}).get("execute_suggestion_count", 0) or 0),
            "review_suggestion_count": int((test_points.get("review_summary") or {}).get("review_suggestion_count", 0) or 0),
            "skip_suggestion_count": int((test_points.get("review_summary") or {}).get("skip_suggestion_count", 0) or 0),
            "total_points": len(points),
            "technique_distribution": self._build_technique_distribution(points),
            "case_confidence": self._calculate_case_confidence(case, points, traceability),
            "warnings": warnings,
            "requires_review": bool(low_confidence_point_count or pending_review_count or warnings),
        }

    def _calculate_bundle_confidence(
        self,
        case: dict[str, Any],
        test_points: dict[str, Any],
        review_summary: dict[str, Any],
    ) -> float:
        case_confidence = float(case.get("confidence", 0.0) or 0.0)
        point_confidence = float(test_points.get("confidence", 0.0) or 0.0)
        summary_confidence = float(review_summary.get("case_confidence", 0.0) or 0.0)
        return round(max(0.0, min(1.0, (case_confidence + point_confidence + summary_confidence) / 3.0)), 2)

    def _calculate_case_confidence(
        self,
        case: dict[str, Any],
        points: list[dict[str, Any]],
        traceability: dict[str, Any],
    ) -> float:
        step_confidences = [float(point.get("confidence", 0.0) or 0.0) for point in points if isinstance(point, dict)]
        base = sum(step_confidences) / len(step_confidences) if step_confidences else 0.0
        penalty = min(0.2, len(traceability.get("missing_targets", [])) * 0.05)
        if not case.get("execution", {}).get("steps"):
            penalty += 0.1
        return round(max(0.0, min(1.0, base - penalty)), 2)

    def _annotate_plan_summary(self, plan: dict[str, Any]) -> dict[str, Any]:
        points = plan.get("points", []) if isinstance(plan.get("points"), list) else []
        confidences = [float(point.get("confidence", 0.0) or 0.0) for point in points if isinstance(point, dict)]
        low_confidence_point_count = sum(1 for point in points if isinstance(point, dict) and float(point.get("confidence", 0.0) or 0.0) < 0.75)
        pending_review_count = sum(1 for point in points if isinstance(point, dict) and bool(point.get("requires_review")) and str(point.get("suggestion", "")).strip().lower() != "skip")
        dependent_elements = self._merge_unique_strings(*[
            [str(item).strip() for item in point.get("dependent_elements", []) if str(item).strip()]
            for point in points
            if isinstance(point, dict)
        ])
        summary = {
            "confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
            "warnings": [str(item).strip() for item in plan.get("warnings", []) if str(item).strip()] if isinstance(plan.get("warnings"), list) else [],
            "requires_review": bool(low_confidence_point_count or pending_review_count),
            "review_summary": {
                "pending_review_count": pending_review_count,
                "skip_suggestion_count": sum(1 for point in points if isinstance(point, dict) and str(point.get("suggestion", "")).strip().lower() == "skip"),
                "review_suggestion_count": sum(1 for point in points if isinstance(point, dict) and str(point.get("suggestion", "")).strip().lower() == "review"),
                "execute_suggestion_count": sum(1 for point in points if isinstance(point, dict) and str(point.get("suggestion", "")).strip().lower() == "execute"),
                "low_confidence_point_count": low_confidence_point_count,
                "total_points": len(points),
                "dependent_element_count": len(dependent_elements),
                "technique_distribution": self._build_technique_distribution(points),
            },
        }
        plan["confidence"] = summary["confidence"]
        plan["warnings"] = self._merge_unique_strings(plan.get("warnings", []), summary["warnings"])
        plan["requires_review"] = summary["requires_review"]
        plan["review_summary"] = summary["review_summary"]
        return plan

    @staticmethod
    def _merge_unique_strings(*groups: list[str]) -> list[str]:
        seen: set[str] = set()
        merged: list[str] = []
        for group in groups:
            for item in group or []:
                text = str(item).strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                merged.append(text)
        return merged

    def _enrich_case_for_enterprise(
        self,
        case: dict[str, Any],
        test_points: dict[str, Any],
        requirement_spec: dict[str, Any],
    ) -> dict[str, Any]:
        points = test_points.get("points", []) if isinstance(test_points.get("points"), list) else []
        point_confidences = [float(point.get("confidence", 0.0) or 0.0) for point in points if isinstance(point, dict)]
        traceability_penalty = 0.05 if not case.get("execution", {}).get("steps") else 0.0
        case_confidence = round(max(0.0, min(1.0, (sum(point_confidences) / len(point_confidences) if point_confidences else 0.0) - traceability_penalty)), 2)
        case["confidence"] = case_confidence
        case["warnings"] = self._merge_unique_strings(
            case.get("warnings", []),
            test_points.get("warnings", []) if isinstance(test_points.get("warnings"), list) else [],
        )
        case["requires_review"] = bool(
            case_confidence < 0.75
            or bool((test_points.get("review_summary") or {}).get("pending_review_count", 0))
            or bool(case.get("warnings"))
        )
        metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
        metadata = deepcopy(metadata)
        metadata.update(
            {
                "design_mode": "enterprise_bundle",
                "requirement_spec_present": bool(requirement_spec),
                "point_count": len(points),
                "case_confidence": case_confidence,
                "technique_distribution": self._build_technique_distribution(points),
            }
        )
        case["metadata"] = metadata
        return case

    def _point_fields_for_constraint(
        self,
        *,
        target: str | None,
        technique_type: str,
        technique_source: str,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        normalized_target = str(target or "").strip()
        confidence = 0.89 if normalized_target else 0.62
        if not normalized_target:
            warnings.append("结构化字段约束缺少稳定 target。")
        suggestion = "execute" if confidence >= 0.85 and not warnings else "review"
        review_reason = (
            "结构化字段约束已命中，可作为补充回归测试点。"
            if suggestion == "execute"
            else "字段约束已识别，但 target 不稳定，建议人工补齐后执行。"
        )
        return {
            "confidence": round(max(0.0, min(1.0, confidence)), 2),
            "warnings": warnings,
            "requires_review": confidence < 0.75 or bool(warnings),
            "suggestion": suggestion,
            "review_reason": review_reason,
            "dependent_elements": [normalized_target] if normalized_target else [],
            "technique_type": technique_type,
            "technique_source": technique_source,
            "technique_confidence": round(max(0.0, min(1.0, confidence)), 2),
            "execution_scope": "design_only",
        }

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            if value in (None, ""):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            if value in (None, ""):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _repeat_value(seed: str, size: int) -> str:
        if size <= 0:
            return ""
        return (seed or "x") * min(size, 80)

    @staticmethod
    def _stringify_numeric(value: float) -> str:
        return str(int(value)) if float(value).is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _build_technique_distribution(points: list[dict[str, Any]]) -> dict[str, int]:
        distribution: dict[str, int] = {}
        for point in points:
            if not isinstance(point, dict):
                continue
            technique_type = str(point.get("technique_type", "normal")).strip().lower() or "normal"
            distribution[technique_type] = distribution.get(technique_type, 0) + 1
        return dict(sorted(distribution.items()))

    @staticmethod
    def _normalize_field_constraints(item: dict[str, Any]) -> dict[str, Any]:
        raw_constraints = item.get("constraints") if isinstance(item.get("constraints"), dict) else {}
        normalized = dict(raw_constraints)
        alias_pairs = {
            "minimum": "min",
            "maximum": "max",
            "exclusiveMinimum": "exclusive_min",
            "exclusiveMaximum": "exclusive_max",
            "minLength": "min_length",
            "maxLength": "max_length",
            "minItems": "min_items",
            "maxItems": "max_items",
            "format": "format",
        }
        for source_key, target_key in alias_pairs.items():
            if source_key in item and target_key not in normalized:
                normalized[target_key] = item.get(source_key)
            if source_key in raw_constraints and target_key not in normalized:
                normalized[target_key] = raw_constraints.get(source_key)
        if "min" not in normalized and item.get("min") not in (None, ""):
            normalized["min"] = item.get("min")
        if "max" not in normalized and item.get("max") not in (None, ""):
            normalized["max"] = item.get("max")
        if "min_length" not in normalized and item.get("min_length") not in (None, ""):
            normalized["min_length"] = item.get("min_length")
        if "max_length" not in normalized and item.get("max_length") not in (None, ""):
            normalized["max_length"] = item.get("max_length")
        format_hint = str(normalized.get("format", "")).strip().lower()
        if format_hint in {"date", "date-time", "datetime", "timestamp"}:
            normalized.setdefault("min_date", str(item.get("min_date", "")).strip() or str(raw_constraints.get("min_date", "")).strip())
            normalized.setdefault("max_date", str(item.get("max_date", "")).strip() or str(raw_constraints.get("max_date", "")).strip())
        return normalized

    def _point_fields_for_intent(
        self,
        *,
        action: str,
        target: str | None,
        value: Any,
        intent_type: str,
    ) -> dict[str, Any]:
        confidence = 0.82
        warnings: list[str] = []
        normalized_action = str(action).strip()
        normalized_target = str(target or "").strip()

        if normalized_action == "login":
            confidence = 0.96
        elif normalized_action == "fill":
            confidence = 0.88 if normalized_target and value not in (None, "") else 0.62
        elif normalized_action in {"click", "wait_for", "assert_visible"}:
            confidence = 0.9 if normalized_target else 0.6
        elif normalized_action == "assert_url":
            confidence = 0.93 if value not in (None, "") else 0.58
        elif normalized_action == "goto":
            confidence = 0.84 if value not in (None, "") else 0.55
        elif normalized_action == "api_request":
            confidence = 0.86 if normalized_target else 0.66
        else:
            confidence = 0.68
            warnings.append(f"未识别的 action: {normalized_action}")

        if normalized_action in {"click", "wait_for", "assert_visible", "fill", "api_request"} and not normalized_target:
            warnings.append(f"{normalized_action} 依赖 target，但当前未能稳定识别。")
        if normalized_action == "fill" and value in (None, ""):
            warnings.append("fill 步骤缺少 value")
        if normalized_action == "goto" and value in (None, ""):
            warnings.append("goto 步骤缺少 value")
        if intent_type in {"negative", "security", "performance", "compatibility"}:
            warnings.append(f"{intent_type} 场景建议人工抽样复核。")

        suggestion = "execute" if confidence >= 0.85 and not warnings else "review"
        if confidence < 0.6:
            suggestion = "skip"
        review_reason = "高置信度测试点，可直接执行。" if suggestion == "execute" else "当前测试点存在不确定性，需要复核。"
        dependent_elements = [normalized_target] if normalized_target else []
        return {
            "confidence": round(max(0.0, min(1.0, confidence)), 2),
            "warnings": warnings,
            "requires_review": confidence < 0.75 or bool(warnings) or suggestion != "execute",
            "suggestion": suggestion,
            "review_reason": review_reason,
            "dependent_elements": dependent_elements,
        }

    @staticmethod
    def _map_intent_type_to_point_type(intent_type: str) -> str:
        mapping = {
            "functional": "action",
            "negative": "assertion",
            "security": "assertion",
            "compatibility": "assertion",
            "performance": "assertion",
            "regression": "action",
            "api": "api",
        }
        return mapping.get(intent_type, "action")

    def _map_intent_to_step(
        self,
        *,
        page: str,
        intent_type: str,
        title: str,
        steps_hint: Any,
    ) -> tuple[str, str | None, Any]:
        hints = [str(item).strip().lower() for item in (steps_hint if isinstance(steps_hint, list) else []) if str(item).strip()]
        lowered_title = title.lower()
        if any(item == "login" or item == "auth_check" for item in hints) or any(token in lowered_title for token in ["登录", "鉴权", "auth"]):
            return "login", None, None
        if any(item.startswith("open:") for item in hints):
            return "click", f"{page}_menu", None
        if any(item.startswith("api:") or item == "api" for item in hints) or intent_type == "api":
            return "api_request", f"{page}_api", f"{page} api"
        if any(item in {"search", "query"} for item in hints) or any(token in lowered_title for token in ["搜索", "查询", "筛选"]):
            return "fill", "search_input", "3"
        if any(item in {"create", "update", "delete", "submit", "approve"} for item in hints):
            return "click", f"{page}_menu", None
        if any(item in {"assert", "negative", "regression", "smoke"} for item in hints):
            return "assert_visible", f"{page}_list_title", None
        return "wait_for", f"{page}_list_title", None

    @staticmethod
    def _merge_tags(*, page: str, requirement_spec: dict[str, Any]) -> list[str]:
        tags: list[str] = ["regression", "enterprise", page]
        spec_tags = requirement_spec.get("tags")
        if isinstance(spec_tags, list):
            for item in spec_tags:
                text = str(item).strip()
                if text and text not in tags:
                    tags.append(text)
        intent_types = requirement_spec.get("test_intents")
        if isinstance(intent_types, list):
            has_security = any(isinstance(item, dict) and str(item.get("intent_type", "")).strip().lower() == "security" for item in intent_types)
            has_performance = any(isinstance(item, dict) and str(item.get("intent_type", "")).strip().lower() == "performance" for item in intent_types)
            if has_security and "security" not in tags:
                tags.append("security")
            if has_performance and "performance" not in tags:
                tags.append("performance")
        return tags
