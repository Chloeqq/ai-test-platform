# mypy: ignore-errors

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from datetime_compat import UTC
from shared_backend.observability import build_ai_trace_context

from .instructions import INSTRUCTIONS_VERSION
from .prompt import PROMPT_NAME, PROMPT_VERSION, SYSTEM_PROMPT
from .schema import (
    AmbiguityItem,
    BusinessRule,
    RequirementEntity,
    RequirementSourceInput,
    RequirementSpec,
    TestIntent,
)
from .tools.document_fetcher import DocumentFetchError, fetch_document
from .tools.local_file_reader import LocalFileReadError, read_local_file
from .tools.user_story_parser import parse_user_story

_LOGGER = logging.getLogger(__name__)

SOURCE_TYPE_ALIASES = {
    "swagger": "openapi",
    "open_api": "openapi",
    "postman_collection": "postman",
    "userstory": "user_story",
    "gitdiff": "git_diff",
    "bug": "defect_ticket",
    "ticket": "defect_ticket",
    "log": "runtime_logs",
}


class RequirementParserAgent:
    def __init__(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[3]

    @staticmethod
    def _truncate(value: Any, *, limit: int = 1200) -> str:
        text = str(value or "")
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    def parse(
        self,
        requirement: str,
        *,
        page: str = "",
        source_type: str = "text",
        openapi_spec: dict[str, Any] | None = None,
        input_sources: list[dict[str, Any]] | None = None,
        prd_text: str = "",
        prd_url: str = "",
        user_story: str = "",
        git_diff: str = "",
        git_diff_path: str = "",
        openapi_url: str = "",
        defect_ticket: str = "",
        runtime_logs: str = "",
        prompt_system: str | None = None,
        prompt_user: str | None = None,
    ) -> dict[str, Any]:
        parse_started_at = datetime.now(UTC)

        mode = str(os.getenv("REQUIREMENT_PARSER_MODE", "")).strip().lower()
        if mode != "llm":
            raise RuntimeError("pure llm mode required: REQUIREMENT_PARSER_MODE must be llm")

        normalized_requirement = str(requirement or "").strip()
        normalized_prd = str(prd_text or "").strip()
        normalized_prd_url = str(prd_url or "").strip()
        normalized_user_story = str(user_story or "").strip()
        normalized_git_diff = str(git_diff or "").strip()
        normalized_git_diff_path = str(git_diff_path or "").strip()
        normalized_openapi_url = str(openapi_url or "").strip()
        normalized_defect = str(defect_ticket or "").strip()
        normalized_logs = str(runtime_logs or "").strip()

        effective_openapi_spec = openapi_spec if isinstance(openapi_spec, dict) else None

        if normalized_openapi_url:
            fetched_openapi = self._safe_fetch_document(normalized_openapi_url)
            if fetched_openapi:
                fetched_openapi_content = str(fetched_openapi.get("text", "")).strip()
                fetched_openapi_payload = fetched_openapi.get("parsed")
                if isinstance(fetched_openapi_payload, dict):
                    effective_openapi_spec = fetched_openapi_payload
                elif fetched_openapi_content:
                    guessed_payload = self._parse_openapi_text(fetched_openapi_content)
                    if isinstance(guessed_payload, dict):
                        effective_openapi_spec = guessed_payload

        if normalized_prd_url and not normalized_prd:
            fetched_prd = self._safe_fetch_document(normalized_prd_url)
            if fetched_prd:
                normalized_prd = str(fetched_prd.get("text", "")).strip()

        if normalized_git_diff_path and not normalized_git_diff:
            loaded_diff = self._safe_read_local_file(normalized_git_diff_path)
            if loaded_diff:
                normalized_git_diff = loaded_diff

        structured_user_story = parse_user_story(normalized_user_story) if normalized_user_story else {}
        if structured_user_story:
            story_lines: list[str] = []
            role = str(structured_user_story.get("role", "")).strip()
            goal = str(structured_user_story.get("goal", "")).strip()
            benefit = str(structured_user_story.get("benefit", "")).strip()
            acceptance = structured_user_story.get("acceptance_criteria")
            if role:
                story_lines.append(f"角色: {role}")
            if goal:
                story_lines.append(f"需求: {goal}")
            if benefit:
                story_lines.append(f"目的: {benefit}")
            if isinstance(acceptance, list):
                for item in acceptance[:10]:
                    line = str(item).strip()
                    if line:
                        story_lines.append(f"验收标准: {line}")
            if story_lines:
                normalized_user_story = "\n".join(story_lines)

        normalized_sources = self._normalize_sources(
            source_type=source_type,
            requirement=normalized_requirement,
            input_sources=input_sources,
            openapi_spec=effective_openapi_spec,
            prd_text=normalized_prd,
            prd_url=normalized_prd_url,
            user_story=normalized_user_story,
            git_diff=normalized_git_diff,
            git_diff_path=normalized_git_diff_path,
            openapi_url=normalized_openapi_url,
            defect_ticket=normalized_defect,
            runtime_logs=normalized_logs,
        )
        if not normalized_sources:
            raise ValueError("requirement or input_sources must not be empty")

        normalized_page = str(page or "").strip()
        if not normalized_page:
            raise ValueError("page must not be empty in pure llm mode")

        merged_text = self._merge_source_text(normalized_sources)
        inferred_page = normalized_page

        llm_overlay, llm_meta = self._run_llm_overlay(
            merged_text=merged_text,
            inferred_page=inferred_page,
            source_type=source_type,
            source_inputs=normalized_sources,
            prompt_system=prompt_system,
            prompt_user=prompt_user,
        )
        if not bool(llm_meta.get("succeeded", False)):
            reason = str(llm_meta.get("reason", "")).strip() or "llm execution failed"
            raise RuntimeError(f"forced llm mode requires successful llm overlay: {reason[:240]}")

        intents = self._overlay_to_test_intents(llm_overlay=llm_overlay, page=inferred_page)
        if not intents:
            raise RuntimeError("llm output did not provide valid test_intents")

        entities = self._overlay_to_entities(llm_overlay=llm_overlay, intents=intents)
        business_rules = self._overlay_to_business_rules(llm_overlay=llm_overlay)
        ambiguities = self._overlay_to_ambiguities(llm_overlay=llm_overlay)
        coverage_matrix = self._build_coverage_matrix(sources=normalized_sources, intents=intents)
        dependency_graph = self._build_dependency_graph(intents)
        priority = self._normalize_priority_value(str(llm_overlay.get("priority", "")).strip()) or "P1"
        parse_confidence = self._resolve_parse_confidence(llm_overlay.get("parse_confidence"), default=0.88)

        parser_runtime = self._build_parser_runtime_metadata(
            llm_meta=llm_meta,
            parse_started_at=parse_started_at,
            source_count=len(normalized_sources),
            intent_count=len(intents),
            ambiguity_count=len(ambiguities),
            parse_confidence=parse_confidence,
        )

        spec = RequirementSpec(
            version="RequirementSpecV1",
            source_type=source_type,
            page=inferred_page,
            raw_requirement=normalized_requirement or merged_text,
            normalized_requirement=self._normalize_text(merged_text),
            source_inputs=normalized_sources,
            entities=entities,
            test_intents=intents,
            coverage_matrix=coverage_matrix,
            dependency_graph=dependency_graph,
            business_rules=business_rules,
            ambiguities=ambiguities,
            change_impact={},
            historical_patterns=[],
            priority=priority,
            design_input=(normalized_requirement or merged_text)[:8000],
            parse_confidence=parse_confidence,
            parser_runtime=parser_runtime,
        )
        return spec.to_dict()

    @staticmethod
    def _normalize_confidence(value: Any, *, default: float) -> float:
        try:
            numeric = float(value)
        except Exception:
            numeric = default
        if numeric < 0.0:
            return 0.0
        if numeric > 1.0:
            return 1.0
        return round(numeric, 2)

    @staticmethod
    def _resolve_parse_confidence(value: Any, *, default: float) -> float:
        """
        Some providers return schema placeholder value 0.0 for parse_confidence.
        Treat non-positive values as missing and fallback to default confidence.
        """
        try:
            numeric = float(value)
        except Exception:
            numeric = default
        if numeric <= 0.0:
            numeric = default
        if numeric > 1.0:
            numeric = 1.0
        return round(numeric, 2)

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(str(value or "").replace("\r", "\n").split())

    @staticmethod
    def _canonical_source_type(source_type: str) -> str:
        normalized = str(source_type or "").strip().lower() or "text"
        return SOURCE_TYPE_ALIASES.get(normalized, normalized)

    def _safe_fetch_document(self, url: str) -> dict[str, Any]:
        try:
            return fetch_document(url=url)
        except DocumentFetchError as exc:
            _LOGGER.warning("fetch_document failed for url=%s: %s", url, exc)
            return {}
        except Exception:
            _LOGGER.exception("unexpected error fetching document url=%s", url)
            return {}

    def _safe_read_local_file(self, path: str) -> str:
        try:
            result = read_local_file(path=path, repo_root=self.repo_root)
            return str(result.get("text", "")) if isinstance(result, dict) else ""
        except LocalFileReadError as exc:
            _LOGGER.warning("read_local_file failed for path=%s: %s", path, exc)
            return ""
        except Exception:
            _LOGGER.exception("unexpected error reading local file path=%s", path)
            return ""

    @staticmethod
    def _parse_openapi_text(content: str) -> dict[str, Any]:
        text = str(content or "").strip()
        if not text:
            return {}
        try:
            payload = json.loads(text)
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _normalize_sources(
        self,
        *,
        source_type: str,
        requirement: str,
        input_sources: list[dict[str, Any]] | None,
        openapi_spec: dict[str, Any] | None,
        prd_text: str,
        prd_url: str,
        user_story: str,
        git_diff: str,
        git_diff_path: str,
        openapi_url: str,
        defect_ticket: str,
        runtime_logs: str,
    ) -> list[RequirementSourceInput]:
        sources: list[RequirementSourceInput] = []

        if isinstance(input_sources, list):
            for index, item in enumerate(input_sources, start=1):
                if not isinstance(item, dict):
                    continue
                content = str(item.get("content", "")).strip()
                if not content:
                    continue
                item_type = self._canonical_source_type(str(item.get("source_type", "text")))
                metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                payload = dict(metadata)
                payload["content"] = content[:12000]
                sources.append(
                    RequirementSourceInput(
                        source_id=f"source-{index:02d}",
                        source_type=item_type,
                        content_preview=content[:200],
                        metadata=payload,
                    )
                )

        if requirement:
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type=self._canonical_source_type(source_type),
                    content_preview=requirement[:200],
                    metadata={"content": requirement[:12000]},
                )
            )
        if prd_text:
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type="prd",
                    content_preview=prd_text[:200],
                    metadata={"content": prd_text[:12000], "source_ref": prd_url},
                )
            )
        if user_story:
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type="user_story",
                    content_preview=user_story[:200],
                    metadata={"content": user_story[:12000]},
                )
            )
        if git_diff:
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type="git_diff",
                    content_preview=git_diff[:200],
                    metadata={"content": git_diff[:12000], "source_ref": git_diff_path},
                )
            )
        if defect_ticket:
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type="defect_ticket",
                    content_preview=defect_ticket[:200],
                    metadata={"content": defect_ticket[:12000]},
                )
            )
        if runtime_logs:
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type="runtime_logs",
                    content_preview=runtime_logs[:200],
                    metadata={"content": runtime_logs[:12000]},
                )
            )
        if isinstance(openapi_spec, dict) and openapi_spec:
            openapi_text = json.dumps(openapi_spec, ensure_ascii=False)
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type="openapi",
                    content_preview=openapi_text[:200],
                    metadata={"content": openapi_text[:12000], "source_ref": openapi_url},
                )
            )
        return sources

    @staticmethod
    def _merge_source_text(sources: list[RequirementSourceInput]) -> str:
        rows: list[str] = []
        for source in sources:
            content = str(source.metadata.get("content", "")).strip()
            if content:
                rows.append(content)
                continue
            preview = str(source.content_preview).strip()
            if preview:
                rows.append(preview)
        return "\n".join(rows)

    def _run_llm_overlay(
        self,
        *,
        merged_text: str,
        inferred_page: str,
        source_type: str,
        source_inputs: list[RequirementSourceInput],
        prompt_system: str | None = None,
        prompt_user: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        openai_api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
        configured_model = (
            str(os.getenv("OPENAI_MODEL", "")).strip()
            or str(os.getenv("REQUIREMENT_PARSER_MODEL", "")).strip()
            or "gpt-5.4"
        )
        llm_meta: dict[str, Any] = {
            "attempted": False,
            "succeeded": False,
            "mode": "llm",
            "model": configured_model,
            "reason_code": "",
            "reason": "",
            "source_count": len(source_inputs),
            "input_chars": len(merged_text),
            "prompt_chars": 0,
            "overlay_key_count": 0,
        }
        started_at = datetime.now(UTC)

        if not openai_api_key:
            llm_meta["reason_code"] = "missing_api_key"
            llm_meta["reason"] = "OPENAI_API_KEY is empty"
            return {}, self._finalize_llm_meta(llm_meta=llm_meta, started_at=started_at, overlay={})

        llm_meta["attempted"] = True
        try:
            from openai import OpenAI

            timeout_seconds = int(str(os.getenv("REQUIREMENT_PARSER_LLM_TIMEOUT_SECONDS", "90")).strip() or 90)
            if timeout_seconds < 10:
                timeout_seconds = 10
            if timeout_seconds > 180:
                timeout_seconds = 180
            max_retries_raw = str(os.getenv("REQUIREMENT_PARSER_LLM_MAX_RETRIES", "2")).strip()
            try:
                max_retries = int(max_retries_raw)
            except Exception:
                max_retries = 2
            if max_retries < 0:
                max_retries = 0
            if max_retries > 5:
                max_retries = 5
            llm_meta["max_retries"] = max_retries
            llm_overlay_attempts_raw = str(os.getenv("REQUIREMENT_PARSER_OVERLAY_ATTEMPTS", "3")).strip()
            try:
                llm_overlay_attempts = int(llm_overlay_attempts_raw)
            except Exception:
                llm_overlay_attempts = 3
            if llm_overlay_attempts < 1:
                llm_overlay_attempts = 1
            if llm_overlay_attempts > 5:
                llm_overlay_attempts = 5
            llm_meta["overlay_attempts"] = llm_overlay_attempts
            client = OpenAI(
                api_key=openai_api_key,
                base_url=str(os.getenv("OPENAI_BASE_URL", "")).strip() or None,
                timeout=timeout_seconds,
                max_retries=max_retries,
            )
            prompt_payload = {
                "source_type": source_type,
                "page": inferred_page,
                "source_count": len(source_inputs),
                "text": merged_text[:12000],
                "output_schema": {
                    "page": "string",
                    "priority": "P0|P1|P2",
                    "parse_confidence": 0.0,
                    "test_intents": [
                        {
                            "title": "string",
                            "intent_type": "functional|negative|security|boundary|format|interaction_exception",
                            "scene_type": "positive|non_empty|boundary|format|business_exception|interaction_exception|security",
                            "priority": "P0|P1|P2",
                            "test_data_type": "correct|empty|boundary|invalid|wrong|lock|timeout|forbidden",
                            "precondition": "string",
                            "steps": ["string"],
                            "steps_hint": ["string"],
                            "target": "string",
                            "value": "string|number|boolean|null",
                            "expected_result": "string",
                            "involved_elements": ["string"],
                        }
                    ],
                    "business_rules": ["string"],
                    "ambiguities": ["string"],
                },
            }
            llm_meta["prompt_chars"] = len(json.dumps(prompt_payload, ensure_ascii=False))
            max_tokens = int(str(os.getenv("REQUIREMENT_PARSER_MAX_TOKENS", "8192")).strip() or 8192)
            if max_tokens < 400:
                max_tokens = 400
            if max_tokens > 8192:
                max_tokens = 8192
            llm_meta["max_tokens"] = max_tokens

            last_error = ""
            last_output = ""
            for attempt in range(1, llm_overlay_attempts + 1):
                request_max_tokens = max_tokens
                if attempt > 1 and llm_meta.get("max_tokens"):
                    request_max_tokens = int(llm_meta["max_tokens"])
                user_prompt = self._build_overlay_user_prompt(
                    prompt_payload=prompt_payload,
                    attempt=attempt,
                    previous_output=last_output,
                    previous_error=last_error,
                )
                llm_meta["attempt"] = attempt
                llm_meta["user_prompt_chars"] = len(user_prompt)
                llm_meta["request_max_tokens"] = request_max_tokens
                completion = client.chat.completions.create(
                    model=configured_model,
                    temperature=0.1,
                    max_tokens=request_max_tokens,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": prompt_system or SYSTEM_PROMPT},
                        {"role": "user", "content": prompt_user or user_prompt},
                    ],
                )
                usage = getattr(completion, "usage", None)
                if usage is not None:
                    llm_meta["prompt_tokens"] = getattr(usage, "prompt_tokens", None)
                    llm_meta["completion_tokens"] = getattr(usage, "completion_tokens", None)
                    llm_meta["total_tokens"] = getattr(usage, "total_tokens", None)
                first_choice = completion.choices[0] if completion.choices else None
                llm_meta["finish_reason"] = str(getattr(first_choice, "finish_reason", "") or "").strip()
                content_raw = getattr(getattr(first_choice, "message", None), "content", "")
                content = self._normalize_completion_content(content_raw).strip()
                last_output = content
                overlay = self._extract_json_object(content_raw)
                if not isinstance(overlay, dict) or not overlay:
                    if llm_meta["finish_reason"] == "length":
                        last_error = "llm output truncated by max_tokens"
                        if attempt < llm_overlay_attempts:
                            max_tokens = min(8192, max(max_tokens + 2048, int(max_tokens * 1.5)))
                            llm_meta["max_tokens"] = max_tokens
                    else:
                        last_error = "llm output is not valid JSON object"
                    llm_meta["reason_code"] = "invalid_overlay"
                    if attempt >= llm_overlay_attempts:
                        raise ValueError(last_error)
                    continue
                overlay = self._coerce_llm_overlay(overlay=overlay, page=inferred_page)
                llm_meta["succeeded"] = True
                llm_meta["reason_code"] = "ok"
                llm_meta["reason"] = "ok"
                llm_meta["attempts_used"] = attempt
                return overlay, self._finalize_llm_meta(llm_meta=llm_meta, started_at=started_at, overlay=overlay)
            llm_meta["reason_code"] = "invalid_overlay"
            raise ValueError(last_error or "llm output is not valid JSON object")
        except Exception as exc:
            llm_meta["reason_code"] = llm_meta.get("reason_code") or "llm_exception"
            llm_meta["reason"] = f"llm overlay failed: {str(exc)[:200]}"
            return {}, self._finalize_llm_meta(llm_meta=llm_meta, started_at=started_at, overlay={})

    def _build_overlay_user_prompt(
        self,
        *,
        prompt_payload: dict[str, Any],
        attempt: int,
        previous_output: str,
        previous_error: str,
    ) -> str:
        base_payload = json.dumps(prompt_payload, ensure_ascii=False)
        if attempt <= 1:
            return base_payload
        if "truncated by max_tokens" in str(previous_error).lower():
            return "\n".join(
                [
                    "上一次输出被 max_tokens 截断，请重新输出完整 JSON 对象。",
                    "硬性要求：只输出一个 JSON 对象，禁止 Markdown、解释文字、代码块。",
                    "请尽量保持字段简洁，不要加入额外说明。",
                    "请基于以下输入重新输出完整 JSON 对象：",
                    base_payload,
                ]
            )
        return "\n".join(
            [
                "上一次输出未通过 JSON 对象校验，请严格修复。",
                "硬性要求：只输出一个 JSON 对象，禁止 Markdown、解释文字、代码块。",
                f"上次错误：{self._truncate(previous_error, limit=400)}",
                "上次输出（截断）：",
                self._truncate(previous_output, limit=1500),
                "请基于以下输入重新输出完整 JSON 对象：",
                base_payload,
            ]
        )

    @staticmethod
    def _finalize_llm_meta(
        *,
        llm_meta: dict[str, Any],
        started_at: datetime,
        overlay: dict[str, Any],
    ) -> dict[str, Any]:
        finished_at = datetime.now(UTC)
        llm_meta["started_at"] = started_at.isoformat()
        llm_meta["finished_at"] = finished_at.isoformat()
        llm_meta["latency_ms"] = max(0, int((finished_at - started_at).total_seconds() * 1000))
        llm_meta["overlay_key_count"] = len(overlay)
        llm_meta["overlay_keys"] = sorted([str(key) for key in overlay.keys()])[:20]
        return llm_meta

    @staticmethod
    def _extract_json_object(raw: str) -> dict[str, Any]:
        text = RequirementParserAgent._normalize_completion_content(raw).strip()
        if not text:
            return {}
        if text.startswith("```json"):
            text = text[len("```json") :].strip()
        elif text.startswith("```"):
            text = text[len("```") :].strip()
        if text.endswith("```"):
            text = text[:-3].strip()
        try:
            payload = json.loads(text)
            if isinstance(payload, str):
                payload = json.loads(payload)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            pass

        start = text.find("{")
        if start < 0:
            return {}

        in_string = False
        escaped = False
        depth = 0
        end = -1
        for idx in range(start, len(text)):
            ch = text[idx]
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
                continue
            if ch == "{":
                depth += 1
                continue
            if ch == "}":
                depth -= 1
                if depth == 0:
                    end = idx
                    break
        if end <= start:
            return {}
        try:
            payload = json.loads(text[start : end + 1])
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _normalize_completion_content(content: Any) -> str:
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
        if isinstance(content, dict):
            text = content.get("text")
            if isinstance(text, str):
                return text
            try:
                return json.dumps(content, ensure_ascii=False)
            except Exception:
                return str(content)
        return str(content or "")

    @staticmethod
    def _normalize_priority_value(value: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized in {"P0", "P1", "P2"}:
            return normalized
        if normalized == "P3":
            return "P2"
        return "P1"

    def _coerce_llm_overlay(self, *, overlay: dict[str, Any], page: str) -> dict[str, Any]:
        normalized = dict(overlay)
        normalized["page"] = str(overlay.get("page", "")).strip() or str(page or "").strip() or "common"
        normalized["priority"] = self._normalize_priority_value(str(overlay.get("priority", "")).strip())
        normalized["parse_confidence"] = self._resolve_parse_confidence(overlay.get("parse_confidence"), default=0.88)
        intents = overlay.get("test_intents")
        normalized_intents: list[dict[str, Any]] = []
        if isinstance(intents, list):
            for row in intents[:40]:
                if not isinstance(row, dict):
                    continue
                title = str(row.get("title", "")).strip()
                if not title:
                    continue
                precondition = str(row.get("precondition", "")).strip()
                raw_steps = row.get("steps") if isinstance(row.get("steps"), list) else []
                steps = [str(step).strip()[:200] for step in raw_steps if str(step).strip()]
                expected_result = str(row.get("expected_result", "")).strip()
                normalized_intents.append(
                    {
                        "title": title[:160],
                        "intent_type": str(row.get("intent_type", "functional")).strip().lower() or "functional",
                        "scene_type": str(row.get("scene_type", "")).strip().lower(),
                        "priority": self._normalize_priority_value(str(row.get("priority", "")).strip()),
                        "test_data_type": str(row.get("test_data_type", "")).strip().lower(),
                        "precondition": precondition[:240],
                        "steps": steps,
                        "steps_hint": [
                            str(item).strip()[:200]
                            for item in (row.get("steps_hint") if isinstance(row.get("steps_hint"), list) else [])
                            if str(item).strip()
                        ],
                        "target": str(row.get("target", "")).strip()[:120],
                        "value": row.get("value"),
                        "expected_result": expected_result[:240],
                        "involved_elements": [
                            str(item).strip()[:100]
                            for item in (row.get("involved_elements") if isinstance(row.get("involved_elements"), list) else [])
                            if str(item).strip()
                        ],
                        "dependencies": [
                            str(item).strip()
                            for item in (row.get("dependencies") if isinstance(row.get("dependencies"), list) else [])
                            if str(item).strip()
                        ],
                        "source_ids": [
                            str(item).strip()
                            for item in (row.get("source_ids") if isinstance(row.get("source_ids"), list) else [])
                            if str(item).strip()
                        ],
                    }
                )
        normalized["test_intents"] = normalized_intents
        normalized["business_rules"] = [
            str(item).strip()[:240]
            for item in (overlay.get("business_rules") if isinstance(overlay.get("business_rules"), list) else [])
            if str(item).strip()
        ][:40]
        normalized["ambiguities"] = [
            str(item).strip()[:240]
            for item in (overlay.get("ambiguities") if isinstance(overlay.get("ambiguities"), list) else [])
            if str(item).strip()
        ][:40]
        return normalized

    @staticmethod
    def _overlay_to_test_intents(*, llm_overlay: dict[str, Any], page: str) -> list[TestIntent]:
        items = llm_overlay.get("test_intents")
        if not isinstance(items, list):
            return []
        intents: list[TestIntent] = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            steps = [str(step).strip()[:200] for step in (item.get("steps") if isinstance(item.get("steps"), list) else []) if str(step).strip()]
            intent = TestIntent(
                intent_id=str(item.get("intent_id", "")).strip() or f"intent-{index:02d}",
                title=title[:160],
                intent_type=str(item.get("intent_type", "functional")).strip().lower() or "functional",
                priority=RequirementParserAgent._normalize_priority_value(str(item.get("priority", "")).strip()),
                precondition=str(item.get("precondition", "")).strip()[:240],
                steps=steps,
                target=str(item.get("target", "")).strip()[:120],
                value=item.get("value"),
                expected_result=str(item.get("expected_result", "")).strip()[:240],
                scene_type=str(item.get("scene_type", "")).strip().lower(),
                test_data_type=str(item.get("test_data_type", "")).strip().lower(),
                involved_elements=[
                    str(value).strip()[:100]
                    for value in (item.get("involved_elements") if isinstance(item.get("involved_elements"), list) else [])
                    if str(value).strip()
                ],
                dependencies=[
                    str(value).strip()
                    for value in (item.get("dependencies") if isinstance(item.get("dependencies"), list) else [])
                    if str(value).strip()
                ],
                source_ids=[
                    str(value).strip()
                    for value in (item.get("source_ids") if isinstance(item.get("source_ids"), list) else [])
                    if str(value).strip()
                ],
                steps_hint=[
                    str(value).strip()[:200]
                    for value in (item.get("steps_hint") if isinstance(item.get("steps_hint"), list) else [])
                    if str(value).strip()
                ],
            )
            if not intent.steps and intent.precondition:
                continue
            intents.append(intent)
        return intents

    @staticmethod
    def _overlay_to_entities(*, llm_overlay: dict[str, Any], intents: list[TestIntent]) -> list[RequirementEntity]:
        entities: list[RequirementEntity] = []
        seen: set[str] = set()
        raw_entities = llm_overlay.get("entities")
        if isinstance(raw_entities, list):
            for item in raw_entities[:40]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                entity_type = str(item.get("entity_type", "")).strip() or "component"
                if not name:
                    continue
                key = f"{entity_type}:{name}".lower()
                if key in seen:
                    continue
                seen.add(key)
                entities.append(
                    RequirementEntity(
                        name=name[:100],
                        entity_type=entity_type[:40],
                        confidence=RequirementParserAgent._normalize_confidence(item.get("confidence"), default=0.7),
                    )
                )
        for intent in intents:
            for element in intent.involved_elements:
                key = f"element:{element}".lower()
                if key in seen:
                    continue
                seen.add(key)
                entities.append(
                    RequirementEntity(
                        name=element[:100],
                        entity_type="element",
                        confidence=0.72,
                    )
                )
        return entities[:60]

    @staticmethod
    def _overlay_to_business_rules(*, llm_overlay: dict[str, Any]) -> list[BusinessRule]:
        rules = llm_overlay.get("business_rules")
        if not isinstance(rules, list):
            return []
        result: list[BusinessRule] = []
        for index, text in enumerate(rules[:40], start=1):
            value = str(text).strip()
            if not value:
                continue
            result.append(
                BusinessRule(
                    rule_id=f"rule-{index:02d}",
                    rule_text=value[:240],
                    rule_type="llm",
                    confidence=0.75,
                )
            )
        return result

    @staticmethod
    def _overlay_to_ambiguities(*, llm_overlay: dict[str, Any]) -> list[AmbiguityItem]:
        items = llm_overlay.get("ambiguities")
        if not isinstance(items, list):
            return []
        result: list[AmbiguityItem] = []
        for index, text in enumerate(items[:40], start=1):
            value = str(text).strip()
            if not value:
                continue
            result.append(
                AmbiguityItem(
                    item_id=f"amb-{index:02d}",
                    text=value[:160],
                    reason="LLM 检测到潜在歧义。",
                    suggestion="请补充可验证输入、操作和预期结果。",
                    severity="medium",
                )
            )
        return result

    @staticmethod
    def _build_coverage_matrix(
        *,
        sources: list[RequirementSourceInput],
        intents: list[TestIntent],
    ) -> list[dict[str, Any]]:
        if not intents:
            return []
        source_ids = [source.source_id for source in sources]
        requirement_text = " / ".join(
            str(source.content_preview or "").strip()
            for source in sources[:6]
            if str(source.content_preview or "").strip()
        )[:200]
        return [
            {
                "requirement_id": "REQ-001",
                "requirement_text": requirement_text or "llm generated requirement coverage",
                "intent_ids": [intent.intent_id for intent in intents],
                "coverage_ratio": 1.0,
                "traceability_status": "covered",
                "source_ids": source_ids,
            }
        ]

    @staticmethod
    def _build_dependency_graph(intents: list[TestIntent]) -> list[dict[str, Any]]:
        graph: list[dict[str, Any]] = []
        for intent in intents:
            graph.append(
                {
                    "intent_id": intent.intent_id,
                    "depends_on": list(intent.dependencies or []),
                }
            )
        return graph

    def _build_parser_runtime_metadata(
        self,
        *,
        llm_meta: dict[str, Any],
        parse_started_at: datetime,
        source_count: int,
        intent_count: int,
        ambiguity_count: int,
        parse_confidence: float,
    ) -> dict[str, Any]:
        parse_finished_at = datetime.now(UTC)
        parse_duration_ms = max(0, int((parse_finished_at - parse_started_at).total_seconds() * 1000))
        configured_model = str(llm_meta.get("model", "")).strip() or "unknown"
        prompt_fingerprint = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:16]
        llm_trace = dict(llm_meta)
        llm_trace["mode"] = "llm"

        runtime = {
            "agent": "requirement-parser-agent",
            "pipeline": "requirement->test_points",
            "generated_at": parse_finished_at.isoformat(),
            "mode": "llm",
            "llm_enabled": True,
            "model": configured_model,
            "prompt_name": PROMPT_NAME,
            "prompt_version": PROMPT_VERSION,
            "prompt_fingerprint": prompt_fingerprint,
            "instructions_version": INSTRUCTIONS_VERSION,
            "parse_started_at": parse_started_at.isoformat(),
            "parse_finished_at": parse_finished_at.isoformat(),
            "parse_duration_ms": parse_duration_ms,
            "source_count": max(0, int(source_count)),
            "intent_count": max(0, int(intent_count)),
            "ambiguity_count": max(0, int(ambiguity_count)),
            "parse_confidence": round(float(parse_confidence), 2),
            "llm_trace": llm_trace,
        }
        runtime["ai_trace"] = build_ai_trace_context(
            page="common",
            prompt_version=str(runtime.get("prompt_version", "")).strip(),
            model=str(runtime.get("model", "")).strip(),
            source="llm_parse",
            instructions_version=str(runtime.get("instructions_version", "")).strip(),
        )
        runtime["trace_id"] = runtime["ai_trace"]["trace_id"]
        return runtime
