# mypy: ignore-errors

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any, Callable

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from .prompt import (
    SYSTEM_PROMPT,
    build_bundle_prompt,
    build_bundle_repair_prompt,
    build_generate_prompt,
    build_generate_repair_prompt,
)
from .schema import DesignBundle, TestCase
from .tools.page_object_loader import list_page_elements


ROOT_ENV = REPO_ROOT / ".env"
load_dotenv(ROOT_ENV)


class TestDesignAgentError(RuntimeError):
    def __init__(self, *, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = str(code).strip() or "test_design_failed"
        self.message = str(message).strip() or "test design failed"
        self.details = details if isinstance(details, dict) else {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class TestDesignAgent:
    def __init__(self, model: str | None = None):
        self.mode = self._resolve_mode()
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        self.model = str(model or os.getenv("OPENAI_MODEL", "gpt-5.4")).strip()
        self.max_retries = self._env_int("TEST_DESIGN_LLM_MAX_RETRIES", default=3, min_value=1, max_value=10)
        self.timeout_seconds = self._env_int("TEST_DESIGN_LLM_TIMEOUT_SECONDS", default=90, min_value=10, max_value=600)
        self.client = None

        if self.mode == "deterministic":
            return

        if not api_key:
            raise ValueError(f"OPENAI_API_KEY not found. Please set it in {ROOT_ENV}")
        if not base_url:
            raise ValueError(f"OPENAI_BASE_URL not found. Please set it in {ROOT_ENV}")
        if not self.model:
            raise ValueError(f"OPENAI_MODEL not found. Please set it in {ROOT_ENV}")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    @staticmethod
    def _resolve_mode() -> str:
        raw = str(os.getenv("TEST_DESIGN_MODE", "llm")).strip().lower()
        if raw == "deterministic":
            return "deterministic"
        return "llm"

    @staticmethod
    def _env_int(name: str, *, default: int, min_value: int, max_value: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = int(str(raw).strip())
        except Exception:
            return default
        return max(min_value, min(max_value, value))

    @staticmethod
    def _truncate(value: Any, *, limit: int = 1200) -> str:
        text = str(value or "")
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    @staticmethod
    def _extract_json_object(content: str) -> dict[str, Any]:
        cleaned = str(content or "").strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[len("```json"):].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[len("```"):].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        start = cleaned.find("{")
        if start < 0:
            raise ValueError("LLM output is not a JSON object")

        in_string = False
        escaped = False
        depth = 0
        end = -1

        for idx in range(start, len(cleaned)):
            ch = cleaned[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == "\"":
                    in_string = False
                continue

            if ch == "\"":
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = idx
                    break

        if end <= start:
            raise ValueError("unable to locate complete JSON object in LLM output")

        snippet = cleaned[start : end + 1]
        parsed = json.loads(snippet)
        if not isinstance(parsed, dict):
            raise ValueError("LLM output JSON must be an object")
        return parsed

    @staticmethod
    def _ensure_non_empty(value: str, *, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise TestDesignAgentError(
                code="test_design_request_invalid",
                message=f"{field_name} must not be empty",
                details={"reason_code": "test_design_request_invalid", "field": field_name},
            )
        return normalized

    @staticmethod
    def _safe_list_page_elements(page: str) -> list[str]:
        try:
            items = list_page_elements(page)
        except Exception:
            return []
        return [str(item).strip() for item in items if str(item).strip()]

    @staticmethod
    def _normalize_content_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        chunks.append(text)
                elif isinstance(item, str) and item.strip():
                    chunks.append(item)
            return "\n".join(chunks)
        return str(content or "")

    def _request_llm(self, *, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            timeout=self.timeout_seconds,
        )
        choices = response.choices if isinstance(getattr(response, "choices", None), list) else []
        if not choices:
            raise ValueError("LLM returned empty choices")
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", "")
        text = self._normalize_content_text(content).strip()
        if not text:
            raise ValueError("LLM returned empty content")
        return text

    def _run_structured_generation(
        self,
        *,
        validator: type[BaseModel],
        initial_prompt: str,
        repair_prompt_builder: Callable[[str, str], str],
        exhausted_code: str,
        exhausted_message: str,
    ) -> dict[str, Any]:
        last_output = ""
        last_error = ""

        for attempt in range(1, self.max_retries + 1):
            prompt = initial_prompt if attempt == 1 else repair_prompt_builder(last_output, last_error)
            try:
                content = self._request_llm(user_prompt=prompt)
            except Exception as exc:
                last_error = f"llm_request_failed: {self._truncate(exc, limit=400)}"
                if attempt >= self.max_retries:
                    raise TestDesignAgentError(
                        code="test_design_llm_unavailable",
                        message="LLM request failed in test-design-agent",
                        details={
                            "reason_code": "test_design_llm_unavailable",
                            "attempts": attempt,
                            "last_error": last_error,
                        },
                    ) from exc
                continue

            last_output = content
            try:
                payload = self._extract_json_object(content)
                validated = validator.model_validate(payload)
                return validated.model_dump(exclude_none=True)
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                last_error = self._truncate(exc, limit=600)
                if attempt >= self.max_retries:
                    raise TestDesignAgentError(
                        code=exhausted_code,
                        message=exhausted_message,
                        details={
                            "reason_code": exhausted_code,
                            "attempts": attempt,
                            "last_error": last_error,
                            "last_output": self._truncate(last_output, limit=1500),
                        },
                    ) from exc
                continue

        raise TestDesignAgentError(
            code=exhausted_code,
            message=exhausted_message,
            details={"reason_code": exhausted_code, "attempts": self.max_retries},
        )

    def _build_deterministic_case(
        self,
        *,
        requirement: str,
        page: str,
        page_elements: list[str],
    ) -> dict[str, Any]:
        page_token = str(page or "product").strip().lower() or "product"
        page_label = {
            "login": "登录",
            "home": "首页",
            "product": "商品",
            "order": "订单",
            "permission": "权限",
            "payment": "支付",
        }.get(page_token, "页面")
        explicit_case_id = str(os.getenv("TEST_DESIGN_DETERMINISTIC_CASE_ID", "")).strip()
        case_id = explicit_case_id or f"ATP-WEB-{page_token.upper()}-CORE-FN-AI-900001"
        title = f"{page_label}主流程验证"
        description = "用于主链路冒烟验证的稳定生成用例。"
        steps: list[dict[str, Any]]
        lowered_requirement = str(requirement or "").lower()
        if page_token == "login" or "登录" in str(requirement or "") or "login" in lowered_requirement or "auth" in lowered_requirement:
            steps = [{"action": "login"}]
        elif page_elements:
            steps = [{"action": "assert_visible", "target": page_elements[0]}]
        else:
            steps = [{"action": "login"}]

        return {
            "version": "v4",
            "id": case_id,
            "title": title,
            "module": page_token,
            "priority": "P1",
            "tags": ["ai-generated", page_token, "deterministic"],
            "owner": "qa-team",
            "status": "automated",
            "description": description,
            "requirement": [str(requirement or "").strip()] if str(requirement or "").strip() else [],
            "data": {},
            "execution": {
                "runner": "playwright",
                "page": page_token,
                "variables": {},
                "steps": steps,
            },
        }

    def _build_deterministic_bundle(
        self,
        *,
        requirement: str,
        page: str,
        requirement_spec: dict[str, Any],
        case: dict[str, Any] | None,
        page_elements: list[str],
    ) -> dict[str, Any]:
        deterministic_case = case if isinstance(case, dict) and case else self._build_deterministic_case(
            requirement=requirement,
            page=page,
            page_elements=page_elements,
        )
        point_action = "login" if str(page).strip().lower() == "login" else "assert_visible"
        point_target = "" if point_action == "login" else (page_elements[0] if page_elements else "")
        raw_step: dict[str, Any] = {"action": point_action, "raw_text": "deterministic smoke step"}
        if point_target:
            raw_step["target"] = point_target
        test_point = {
            "key": "intent-01",
            "intent_id": "intent-01",
            "point_type": "action",
            "description": "deterministic smoke point",
            "action": point_action,
            "target": point_target or None,
            "involved_elements": [point_target] if point_target else [],
            "steps": [raw_step],
            "source_ids": ["source-01"],
        }
        return {
            "version": "DesignBundleV1",
            "page": str(page).strip(),
            "requirement": [str(requirement).strip()] if str(requirement).strip() else [],
            "requirement_spec": requirement_spec if isinstance(requirement_spec, dict) else {},
            "case": deterministic_case,
            "test_points": {
                "page": str(page).strip(),
                "requirement": [str(requirement).strip()] if str(requirement).strip() else [],
                "points": [test_point],
                "review_summary": {
                    "pending_review_count": 0,
                    "skip_suggestion_count": 0,
                    "review_suggestion_count": 0,
                    "execute_suggestion_count": 1,
                    "total_points": 1,
                },
                "warnings": [],
                "requires_review": False,
            },
            "traceability": {"intent_count": 1, "mapped_points": 1},
            "review_summary": {"pending_review_count": 0, "total_points": 1},
            "confidence": 1.0,
            "warnings": [],
            "requires_review": False,
            "metadata": {"mode": "deterministic"},
        }

    def generate(self, requirement: str, page: str) -> dict[str, Any]:
        normalized_page = self._ensure_non_empty(page, field_name="page")
        normalized_requirement = self._ensure_non_empty(requirement, field_name="requirement")
        page_elements = self._safe_list_page_elements(normalized_page)
        current_mode = str(getattr(self, "mode", "llm")).strip().lower()
        if current_mode == "deterministic":
            return TestCase.model_validate(
                self._build_deterministic_case(
                    requirement=normalized_requirement,
                    page=normalized_page,
                    page_elements=page_elements,
                )
            ).model_dump(exclude_none=True)

        initial_prompt = build_generate_prompt(
            requirement=normalized_requirement,
            page=normalized_page,
            page_elements=page_elements,
        )

        def _repair_prompt(previous_output: str, validation_error: str) -> str:
            return build_generate_repair_prompt(
                requirement=normalized_requirement,
                page=normalized_page,
                page_elements=page_elements,
                previous_output=self._truncate(previous_output, limit=3500),
                validation_error=self._truncate(validation_error, limit=1500),
            )

        return self._run_structured_generation(
            validator=TestCase,
            initial_prompt=initial_prompt,
            repair_prompt_builder=_repair_prompt,
            exhausted_code="test_design_invalid_output",
            exhausted_message="test-design-agent returned invalid structured output",
        )

    def generate_test_points(self, requirement: str, page: str) -> dict[str, Any]:
        bundle = self.design_bundle(requirement=requirement, page=page)
        points = bundle.get("test_points")
        return points if isinstance(points, dict) else {}

    def design_bundle(
        self,
        *,
        requirement: str = "",
        page: str = "",
        requirement_spec: dict[str, Any] | None = None,
        case: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_spec = requirement_spec if isinstance(requirement_spec, dict) else {}
        normalized_page = str(page or normalized_spec.get("page", "")).strip()
        normalized_page = self._ensure_non_empty(normalized_page, field_name="page")
        normalized_requirement = (
            str(requirement or "").strip()
            or str(normalized_spec.get("design_input", "")).strip()
            or str(normalized_spec.get("raw_requirement", "")).strip()
        )
        normalized_requirement = self._ensure_non_empty(normalized_requirement, field_name="requirement")
        page_elements = self._safe_list_page_elements(normalized_page)
        current_mode = str(getattr(self, "mode", "llm")).strip().lower()
        if current_mode == "deterministic":
            return DesignBundle.model_validate(
                self._build_deterministic_bundle(
                    requirement=normalized_requirement,
                    page=normalized_page,
                    requirement_spec=normalized_spec,
                    case=case if isinstance(case, dict) else None,
                    page_elements=page_elements,
                )
            ).model_dump(exclude_none=True)

        initial_prompt = build_bundle_prompt(
            requirement=normalized_requirement,
            page=normalized_page,
            requirement_spec=normalized_spec,
            case=case,
            page_elements=page_elements,
        )

        def _repair_prompt(previous_output: str, validation_error: str) -> str:
            return build_bundle_repair_prompt(
                requirement=normalized_requirement,
                page=normalized_page,
                requirement_spec=normalized_spec,
                case=case,
                page_elements=page_elements,
                previous_output=self._truncate(previous_output, limit=3500),
                validation_error=self._truncate(validation_error, limit=1500),
            )

        return self._run_structured_generation(
            validator=DesignBundle,
            initial_prompt=initial_prompt,
            repair_prompt_builder=_repair_prompt,
            exhausted_code="test_design_bundle_invalid_output",
            exhausted_message="test-design-agent returned invalid design_bundle output",
        )
