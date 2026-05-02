from __future__ import annotations

import re
from typing import Any

from .feature_flags import FeatureFlags


class CandidateNormalizer:
    def __init__(self, flags: FeatureFlags) -> None:
        self._flags = flags

    def _normalize_candidate_text(self, value: str) -> str:
        text = str(value or "").strip()
        text = re.sub(r"^\s*(?:[-*•·]+\s*|\d+\s*[.)、]\s*)", "", text)
        text = re.sub(r"\s+", " ", text).strip("`'\" ")
        return text[:200]

    def _looks_like_heading_only_text(self, value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return True
        if re.match(r"^【[^】]{1,24}】$", text):
            return True
        if re.match(r"^【(模块|页面|功能|功能描述|涉及元素|输入元素|优先级|前置条件|异常场景|测试点)】", text):
            return True
        if re.match(r"^(模块|页面|功能|功能描述|测试点|场景|需求|优先级)\s*[:：]?$", text):
            return True
        if text.endswith(("：", ":")) and len(text) <= 18:
            return True
        if re.match(r'^"?[a-z_][\w-]*"?\s*:\s*"?$', text.lower()):
            return True
        return False

    def _looks_like_metadata_noise_text(self, value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return True
        lowered = text.lower()
        compact = re.sub(r"\s+", "", lowered)
        noisy_tokens = [
            "[page_url]",
            "[domain_rule]",
            "[priority_policy]",
            "[acceptance_rule]",
            "[user_story]",
            "requirement_overview",
            "analysis_time",
            "entities",
            "page_elements",
            "business_objects",
            "operations",
            "change_impact",
            "regression_scope",
            'source":"',
        ]
        if any(token in compact for token in noisy_tokens):
            return True
        if re.match(r"^\[page_url\]\s*https?://", lowered):
            return True
        if lowered.startswith("http://") or lowered.startswith("https://"):
            return True
        if re.match(r"^\[user_story\]\s*(角色|目的|需求)\s*:", text):
            return True
        if re.match(r'^[a-z_][\w-]*"\s*:\s*\{?$', lowered):
            return True
        if re.match(r'^[a-z_][\w-]*"\s*:\s*(?:"[^"]*"|\[|\{|\d+|true|false|null).*,?$', lowered):
            return True
        if text.endswith(("{", "},", ":")):
            return True
        return False

    def _normalize_candidate_steps(self, value: Any, *, filter_enabled: bool) -> list[str]:
        if not isinstance(value, list):
            return []
        steps: list[str] = []
        for item in value:
            if isinstance(item, str):
                text = self._normalize_candidate_text(item)
            elif isinstance(item, dict):
                text = self._normalize_candidate_text(
                    str(item.get("summary") or item.get("description") or item.get("title") or item.get("action") or "")
                )
            else:
                text = self._normalize_candidate_text(str(item or ""))
            if filter_enabled and self._looks_like_metadata_noise_text(text):
                continue
            if text and text not in steps:
                steps.append(text)
        return steps

    def normalize_candidates(self, raw_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filter_enabled = self._flags.testpoint_filter_enabled()
        normalized: list[dict[str, Any]] = []
        for raw_candidate in raw_candidates:
            if not isinstance(raw_candidate, dict):
                continue
            intent_id = self._normalize_candidate_text(str(raw_candidate.get("intent_id", "")).strip())
            title = self._normalize_candidate_text(str(raw_candidate.get("title", "")).strip())
            summary = self._normalize_candidate_text(str(raw_candidate.get("summary", "")).strip())
            if filter_enabled and (self._looks_like_heading_only_text(title) or self._looks_like_metadata_noise_text(title)):
                title = ""
            if filter_enabled and (self._looks_like_heading_only_text(summary) or self._looks_like_metadata_noise_text(summary)):
                summary = ""
            intent_type = str(raw_candidate.get("intent_type", "")).strip().lower()
            priority = str(raw_candidate.get("priority", "")).strip().upper()
            precondition = self._normalize_candidate_text(str(raw_candidate.get("precondition", "")).strip())
            if filter_enabled and self._looks_like_metadata_noise_text(precondition):
                precondition = ""
            expected = self._normalize_candidate_text(
                str(
                    raw_candidate.get("expected")
                    or raw_candidate.get("expect_result")
                    or raw_candidate.get("expected_result")
                    or ""
                ).strip()
            )
            if filter_enabled and self._looks_like_metadata_noise_text(expected):
                expected = ""
            steps = self._normalize_candidate_steps(raw_candidate.get("steps"), filter_enabled=filter_enabled)
            raw_steps_hint = raw_candidate.get("steps_hint")
            steps_hint: list[str] = []
            if isinstance(raw_steps_hint, list):
                for item in raw_steps_hint:
                    hint = self._normalize_candidate_text(str(item or ""))
                    if hint and hint not in steps_hint:
                        steps_hint.append(hint)
            scene_type = self._normalize_candidate_text(str(raw_candidate.get("scene_type", "")).strip())
            test_data_type = self._normalize_candidate_text(str(raw_candidate.get("test_data_type", "")).strip())
            raw_elements = raw_candidate.get("involved_elements")
            involved_elements: list[str] = []
            if isinstance(raw_elements, list):
                for item in raw_elements:
                    element = self._normalize_candidate_text(str(item or ""))
                    if element and (not filter_enabled or not self._looks_like_metadata_noise_text(element)) and element not in involved_elements:
                        involved_elements.append(element)
            raw_element_codes = raw_candidate.get("involved_element_codes")
            involved_element_codes: list[str] = []
            if isinstance(raw_element_codes, list):
                for item in raw_element_codes:
                    code = self._normalize_candidate_text(str(item or ""))
                    if code and code not in involved_element_codes:
                        involved_element_codes.append(code)
            raw_tags = raw_candidate.get("tags")
            tags: list[str] = []
            if isinstance(raw_tags, list):
                for item in raw_tags:
                    tag = str(item or "").strip()
                    if tag and (not filter_enabled or not self._looks_like_metadata_noise_text(tag)) and tag not in tags:
                        tags.append(tag)
            if not title:
                title = summary or (steps[0] if steps else "") or expected or precondition
            if not summary:
                summary = title or expected or precondition
            requirement_hint = summary or title
            if filter_enabled and self._looks_like_metadata_noise_text(requirement_hint):
                requirement_hint = ""
            has_meaningful_content = bool(
                requirement_hint or title or summary or precondition or expected or steps or steps_hint or involved_elements
            )
            if not has_meaningful_content:
                continue
            normalized.append(
                {
                    "intent_id": intent_id,
                    "title": title,
                    "summary": summary,
                    "intent_type": intent_type,
                    "priority": priority,
                    "tags": tags,
                    "requirement_hint": requirement_hint,
                    "precondition": precondition,
                    "steps": steps,
                    "steps_hint": steps_hint,
                    "expected": expected,
                    "scene_type": scene_type,
                    "test_data_type": test_data_type,
                    "involved_elements": involved_elements,
                    "involved_element_codes": involved_element_codes,
                }
            )
        return normalized

    def build_candidate_requirement(self, base_requirement: str, candidate: dict[str, Any]) -> str:
        requirement = str(base_requirement or "").strip()
        hint = str(candidate.get("requirement_hint", "")).strip()
        intent_type = str(candidate.get("intent_type", "")).strip()
        title = str(candidate.get("title", "")).strip()
        summary = str(candidate.get("summary", "")).strip()
        precondition = str(candidate.get("precondition", "")).strip()
        steps = candidate.get("steps")
        steps_hint = candidate.get("steps_hint")
        expected = str(candidate.get("expected", "")).strip()
        involved_elements = candidate.get("involved_elements")
        involved_element_codes = candidate.get("involved_element_codes")
        intent_id = str(candidate.get("intent_id", "")).strip()
        if not any([intent_id, title, summary, hint, intent_type, precondition, expected, steps, steps_hint, involved_elements, involved_element_codes]):
            return requirement
        lines: list[str] = []
        if intent_id:
            lines.append(f"测试点ID：{intent_id}")
        if title:
            lines.append(f"测试点标题：{title}")
        if hint:
            lines.append(f"测试意图：{hint}")
        if intent_type:
            lines.append(f"测试类型：{intent_type}")
        if precondition:
            lines.append(f"前置条件：{precondition}")
        if isinstance(steps_hint, list):
            hint_rows = [str(item).strip() for item in steps_hint if str(item).strip()]
            if hint_rows:
                lines.append("steps_hint:")
                for index, hint_row in enumerate(hint_rows[:10], start=1):
                    lines.append(f"{index}. {hint_row}")
        if isinstance(steps, list):
            step_rows = [str(item).strip() for item in steps if str(item).strip()]
            if step_rows:
                lines.append("操作步骤：")
                for index, step in enumerate(step_rows[:10], start=1):
                    lines.append(f"{index}. {step}")
        if expected:
            lines.append(f"预期结果：{expected}")
        if isinstance(involved_elements, list):
            elements = [str(item).strip() for item in involved_elements if str(item).strip()]
            if elements:
                lines.append(f"涉及元素：{'、'.join(elements)}")
        if isinstance(involved_element_codes, list):
            codes = [str(item).strip() for item in involved_element_codes if str(item).strip()]
            if codes:
                lines.append(f"涉及元素Code：{'、'.join(codes)}")
        lines.append("约束：仅围绕上述单个测试意图生成，不要扩展到其他测试意图。")
        return "\n".join(line for line in lines if line).strip()

    def extract_case_candidates_from_preview(
        self,
        preview_payload: dict[str, Any],
        *,
        max_cases: int,
    ) -> list[dict[str, Any]]:
        item = preview_payload.get("item") if isinstance(preview_payload, dict) else {}
        item = item if isinstance(item, dict) else {}
        requirement_spec = item.get("requirement_spec") if isinstance(item.get("requirement_spec"), dict) else {}
        test_intents = requirement_spec.get("test_intents") if isinstance(requirement_spec.get("test_intents"), list) else []
        candidates: list[dict[str, Any]] = []
        for intent in test_intents:
            if not isinstance(intent, dict):
                continue
            title = str(intent.get("title") or "").strip() or str(intent.get("summary") or "").strip()
            summary = str(intent.get("summary") or "").strip() or title
            intent_type = str(intent.get("intent_type") or "").strip().lower() or "functional"
            priority = str(intent.get("priority") or "").strip().upper() or "P1"
            tags: list[str] = []
            if isinstance(intent.get("tags"), list):
                for raw in intent.get("tags"):
                    value = str(raw or "").strip()
                    if value and value not in tags:
                        tags.append(value)
            if not title and not summary:
                continue
            candidates.append(
                {
                    "intent_id": str(intent.get("intent_id") or "").strip(),
                    "title": title or summary,
                    "summary": summary or title,
                    "intent_type": intent_type,
                    "priority": priority,
                    "tags": tags,
                    "precondition": str(intent.get("precondition") or "").strip(),
                    "steps": intent.get("steps") if isinstance(intent.get("steps"), list) else [],
                    "steps_hint": intent.get("steps_hint") if isinstance(intent.get("steps_hint"), list) else [],
                    "expected": str(
                        intent.get("expected") or intent.get("expected_result") or intent.get("expect_result") or ""
                    ).strip(),
                    "scene_type": str(intent.get("scene_type") or "").strip(),
                    "test_data_type": str(intent.get("test_data_type") or "").strip(),
                    "involved_elements": intent.get("involved_elements")
                    if isinstance(intent.get("involved_elements"), list)
                    else [],
                }
            )
            if len(candidates) >= max_cases:
                break
        return self.normalize_candidates(candidates)[:max_cases]
