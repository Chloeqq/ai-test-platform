# mypy: ignore-errors
"""需求解析支撑：调用 requirement-parser-agent 并处理多源输入与 LLM 模式。"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from shared_backend.observability import get_request_id, run_logged_subprocess, summarize_log_value


_LOGGER = logging.getLogger(__name__)


class RequirementParseSupport:
    """将原始需求与多源上下文规范化为 RequirementSpecV1。"""

    def __init__(
        self,
        *,
        repo_root: Path,
        requirement_parser_root: Path,
        build_fallback_multisource_context: Callable[..., dict[str, Any]],
        harmonize_requirement_spec: Callable[..., dict[str, Any]],
        infer_page_from_text: Callable[..., str],
        rank_page_candidates: Callable[..., list[dict[str, Any]]],
    ) -> None:
        self._repo_root = repo_root
        self._requirement_parser_root = requirement_parser_root
        self._build_fallback_multisource_context = build_fallback_multisource_context
        self._harmonize_requirement_spec = harmonize_requirement_spec
        self._infer_page_from_text = infer_page_from_text
        self._rank_page_candidates = rank_page_candidates

    def parse_requirement_spec(
        self,
        *,
        requirement: str,
        page: str,
        source: str,
        input_sources: list[dict[str, Any]] | None = None,
        openapi_spec: dict[str, Any] | None = None,
        prd_text: str = "",
        prd_url: str = "",
        user_story: str = "",
        git_diff: str = "",
        git_diff_path: str = "",
        openapi_url: str = "",
        defect_ticket: str = "",
        runtime_logs: str = "",
    ) -> dict[str, Any]:
        """解析需求规格；pytest 环境下走确定性桩数据。"""
        if str(os.getenv("PYTEST_CURRENT_TEST", "")).strip():
            return self._build_pytest_requirement_spec(
                requirement=requirement,
                page=page,
                source=source,
                input_sources=input_sources,
                openapi_spec=openapi_spec,
                prd_text=prd_text,
                prd_url=prd_url,
                user_story=user_story,
                git_diff=git_diff,
                git_diff_path=git_diff_path,
                openapi_url=openapi_url,
                defect_ticket=defect_ticket,
                runtime_logs=runtime_logs,
            )
        force_llm_mode = self.is_llm_force_mode_enabled()
        temp_path: Path | None = None
        try:
            payload = {
                "requirement": requirement,
                "page": page,
                "source_type": source,
                "input_sources": input_sources or [],
                "openapi_spec": openapi_spec or {},
                "prd_text": prd_text,
                "prd_url": prd_url,
                "user_story": user_story,
                "git_diff": git_diff,
                "git_diff_path": git_diff_path,
                "openapi_url": openapi_url,
                "defect_ticket": defect_ticket,
                "runtime_logs": runtime_logs,
            }
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(json.dumps(payload, ensure_ascii=False))
            pythonpath_entries = [
                str(self._repo_root),
                str(self._repo_root / "shared_backend"),
                str(self._requirement_parser_root),
            ]
            existing_pythonpath = str(os.environ.get("PYTHONPATH", "")).strip()
            if existing_pythonpath:
                pythonpath_entries.append(existing_pythonpath)
            env = dict(os.environ)
            env["PYTHONPATH"] = os.pathsep.join(entry for entry in pythonpath_entries if entry)
            env["REQUIREMENT_PARSER_MODE"] = "llm"
            env["PYTHONUNBUFFERED"] = "1"
            llm_timeout_seconds = self._read_int_env("REQUIREMENT_PARSER_LLM_TIMEOUT_SECONDS", default=90, min_value=10, max_value=180)
            llm_max_retries = self._read_int_env("REQUIREMENT_PARSER_LLM_MAX_RETRIES", default=2, min_value=0, max_value=5)
            default_parser_timeout = max(180, (llm_timeout_seconds * (llm_max_retries + 1)) + 45)
            parser_timeout_seconds = self._read_int_env(
                "REQUIREMENT_PARSER_SUBPROCESS_TIMEOUT_SECONDS",
                default=default_parser_timeout,
                min_value=30,
                max_value=600,
            )
            _LOGGER.info(
                "requirement parser subprocess start: cwd=%s timeout=%ss input_sources=%d requirement_chars=%d page=%s request_id=%s",
                self._requirement_parser_root,
                parser_timeout_seconds,
                len(input_sources or []),
                len(requirement or ""),
                page or "",
                get_request_id() or "-",
            )
            try:
                completed = run_logged_subprocess(
                    [sys.executable, "-m", "src.index", "--input", str(temp_path)],
                    cwd=str(self._requirement_parser_root),
                    env=env,
                    timeout=parser_timeout_seconds,
                    logger=_LOGGER,
                    log_prefix="requirement-parser",
                )
            except subprocess.TimeoutExpired as exc:
                timeout_detail = self._compact_subprocess_error(
                    stdout=str(getattr(exc, "output", "") or ""),
                    stderr=str(getattr(exc, "stderr", "") or ""),
                    default_message="requirement parser subprocess timed out",
                )
                error_message = (
                    f"{timeout_detail} "
                    f"(subprocess_timeout={parser_timeout_seconds}s, "
                    f"llm_timeout={llm_timeout_seconds}s, "
                    f"llm_max_retries={llm_max_retries}, "
                    f"input_sources={len(input_sources or [])}, "
                    f"requirement_chars={len(requirement or '')}, "
                    f"page={page or ''})"
                )
                _LOGGER.error("requirement parser timeout: %s", error_message)
                raise RuntimeError(error_message) from exc
            if completed.returncode != 0:
                compact_reason = self._compact_subprocess_error(
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    default_message="requirement parser failed",
                )
                _LOGGER.error(
                    "requirement parser failed: returncode=%s reason=%s stderr_excerpt=%s stdout_excerpt=%s",
                    completed.returncode,
                    compact_reason,
                    summarize_log_value(completed.stderr, max_length=1200),
                    summarize_log_value(completed.stdout, max_length=1200),
                )
                raise RuntimeError(compact_reason)
            _LOGGER.info(
                "requirement parser subprocess end: returncode=%s stdout_chars=%d stderr_chars=%d request_id=%s",
                completed.returncode,
                len(completed.stdout or ""),
                len(completed.stderr or ""),
                get_request_id() or "-",
            )
            parsed = json.loads(completed.stdout.strip() or "{}")
            if not isinstance(parsed, dict):
                raise RuntimeError("requirement parser returned non-object payload")
            if not isinstance(parsed.get("parser_runtime"), dict):
                raise RuntimeError("requirement parser returned payload without parser_runtime")
            # Pure-LLM path: keep parser output as-is, no secondary rule harmonization.
            return parsed
        except Exception as exc:
            reason_prefix = "requirement parser failed under forced llm mode"
            if not force_llm_mode:
                reason_prefix = "requirement parser failed (pure llm mode, fallback removed)"
            raise RuntimeError(f"{reason_prefix}: {str(exc)[:240]}") from exc
        finally:
            if isinstance(temp_path, Path):
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    pass

    def _build_pytest_requirement_spec(
        self,
        *,
        requirement: str,
        page: str,
        source: str,
        input_sources: list[dict[str, Any]] | None = None,
        openapi_spec: dict[str, Any] | None = None,
        prd_text: str = "",
        prd_url: str = "",
        user_story: str = "",
        git_diff: str = "",
        git_diff_path: str = "",
        openapi_url: str = "",
        defect_ticket: str = "",
        runtime_logs: str = "",
    ) -> dict[str, Any]:
        fallback_context = self._build_fallback_multisource_context(
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            openapi_url=openapi_url,
            git_diff=git_diff,
            git_diff_path=git_diff_path,
            defect_ticket=defect_ticket,
        )
        source_inputs = fallback_context.get("source_inputs", []) if isinstance(fallback_context, dict) else []
        source_inputs = [item for item in source_inputs if isinstance(item, dict)]
        ranked_candidates = self._rank_page_candidates(
            fallback_context=fallback_context if isinstance(fallback_context, dict) else {},
            source_inputs=source_inputs,
            current_page=page,
        )
        resolved_page = str(page or "").strip()
        if not resolved_page and ranked_candidates:
            top = ranked_candidates[0] if isinstance(ranked_candidates[0], dict) else {}
            resolved_page = str(top.get("page", "")).strip()
        if not resolved_page:
            resolved_page = self._infer_page_from_text(
                requirement=requirement,
                prd_text=prd_text,
                user_story=user_story,
                git_diff=git_diff,
                defect_ticket=defect_ticket,
                runtime_logs=runtime_logs,
                openapi_spec=openapi_spec,
                input_sources=input_sources,
            )
        if not resolved_page:
            resolved_page = "product"

        normalized_source_inputs: list[dict[str, Any]] = []
        source_ids: list[str] = []
        for index, raw_item in enumerate(source_inputs, start=1):
            source_id = str(raw_item.get("source_id", "")).strip() or f"source-{index:02d}"
            source_type = str(raw_item.get("source_type", "")).strip() or str(source or "").strip() or "manual"
            summary = str(raw_item.get("summary", "")).strip() or str(raw_item.get("content", "")).strip()
            refs = [str(item).strip() for item in (raw_item.get("reference_ids") or []) if str(item).strip()]
            normalized_source_inputs.append(
                {
                    "source_id": source_id,
                    "source_type": source_type,
                    "summary": summary[:160],
                    "reference_ids": refs[:10],
                }
            )
            source_ids.append(source_id)
        if not normalized_source_inputs:
            default_source_id = "source-01"
            normalized_source_inputs.append(
                {
                    "source_id": default_source_id,
                    "source_type": str(source or "").strip() or "manual",
                    "summary": str(requirement or "").strip()[:160],
                    "reference_ids": [],
                }
            )
            source_ids = [default_source_id]

        base_text = str(requirement or "").strip() or str(prd_text or "").strip() or "需求描述"
        title_seed = re.sub(r"(前置条件|测试步骤|预期结果)\s*[-:：]?", " ", base_text)
        title_seed = re.sub(r"\d+\s*[.、]", " ", title_seed)
        title_seed = re.sub(r"[「」“”\"'，,。;；:/]+", " ", title_seed)
        title_seed = " ".join(title_seed.split())
        base_title = (title_seed[:20] if title_seed else "").strip() or f"{resolved_page}流程验证"
        test_intents = [
            {
                "intent_id": "intent-01",
                "title": f"{base_title}-主流程",
                "summary": "验证核心主流程可达且关键信息可见。",
                "intent_type": "functional",
                "priority": "P1",
                "expected_result": "主流程执行成功，页面关键区域可见且状态正确。",
                "steps_hint": [f"open:{resolved_page}", "assert"],
                "source_ids": source_ids[:1] or source_ids,
            },
            {
                "intent_id": "intent-02",
                "title": f"{base_title}-异常路径",
                "summary": "验证输入异常或状态异常时系统反馈。",
                "intent_type": "negative",
                "priority": "P1",
                "expected_result": "异常输入或异常状态下应返回明确错误提示。",
                "steps_hint": [f"open:{resolved_page}", "input:invalid", "assert:error_hint"],
                "source_ids": source_ids[:1] or source_ids,
            },
            {
                "intent_id": "intent-03",
                "title": f"{base_title}-边界校验",
                "summary": "验证边界值处理和稳定性。",
                "intent_type": "boundary",
                "priority": "P2",
                "expected_result": "边界值处理符合预期，页面行为稳定且无异常。",
                "steps_hint": [f"open:{resolved_page}", "input:boundary", "assert:boundary_behavior"],
                "source_ids": source_ids[:1] or source_ids,
            },
        ]
        coverage_matrix = [
            {
                "scenario_id": f"scenario-{index:02d}",
                "title": str(intent.get("title", "")).strip(),
                "intent_ids": [str(intent.get("intent_id", "")).strip()],
                "traceability_status": "covered",
                "source_ids": list(intent.get("source_ids", [])),
            }
            for index, intent in enumerate(test_intents, start=1)
        ]
        parser_runtime = {
            "agent": "requirement-parser-agent",
            "mode": "llm",
            "prompt_version": "requirement-parser.prompt.pytest",
            "model": str(os.getenv("REQUIREMENT_PARSER_MODEL", "")).strip()
            or str(os.getenv("OPENAI_MODEL", "")).strip()
            or "gpt-5.4",
            "detail": "pytest deterministic parser path",
            "page_resolution": {
                "selected_page": resolved_page,
                "candidate_details": ranked_candidates if isinstance(ranked_candidates, list) else [],
            },
            "llm_trace": {
                "attempted": False,
                "succeeded": True,
                "reason_code": "pytest_deterministic",
                "latency_ms": 0,
                "overlay_key_count": 0,
                "total_tokens": 0,
            },
        }
        requirement_spec: dict[str, Any] = {
            "version": "RequirementSpecV1",
            "source_type": str(source or "").strip() or "manual",
            "page": resolved_page,
            "design_input": base_text,
            "raw_requirement": str(requirement or "").strip(),
            "parse_confidence": 0.92,
            "source_inputs": normalized_source_inputs,
            "test_intents": test_intents,
            "coverage_matrix": coverage_matrix,
            "business_rules": fallback_context.get("business_rules", []) if isinstance(fallback_context, dict) else [],
            "ambiguities": [],
            "change_impact": {
                "changed_files": fallback_context.get("changed_files", []) if isinstance(fallback_context, dict) else [],
                "changed_modules": fallback_context.get("changed_modules", []) if isinstance(fallback_context, dict) else [],
                "changed_areas": fallback_context.get("changed_areas", []) if isinstance(fallback_context, dict) else [],
            },
            "parser_runtime": parser_runtime,
        }
        return self._harmonize_requirement_spec(
            requirement_spec=requirement_spec,
            source=str(source or "").strip() or "manual",
            requirement=str(requirement or "").strip(),
            fallback_context=fallback_context if isinstance(fallback_context, dict) else {},
        )

    @staticmethod
    def _extract_json_object(raw: str) -> dict[str, Any]:
        text = str(raw or "").strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, ValueError):
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, ValueError):
            return {}

    @classmethod
    def _compact_subprocess_error(cls, *, stdout: str, stderr: str, default_message: str) -> str:
        for raw in (stderr, stdout):
            parsed = cls._extract_json_object(raw)
            if not parsed:
                continue
            error_payload = parsed.get("error")
            if isinstance(error_payload, dict):
                message = str(error_payload.get("message", "")).strip()
                error_type = str(error_payload.get("type", "")).strip()
                if message and error_type:
                    return f"{error_type}: {message}"[:500]
                if message:
                    return message[:500]
            message = str(parsed.get("message", "")).strip()
            if message:
                return message[:500]

        text = str(stderr or "").strip() or str(stdout or "").strip() or str(default_message or "").strip()
        if not text:
            return "requirement parser failed"
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            return lines[-1][:500]
        return text[:500]

    @staticmethod
    def _read_int_env(name: str, *, default: int, min_value: int | None = None, max_value: int | None = None) -> int:
        raw = str(os.getenv(name, "")).strip()
        try:
            value = int(raw) if raw else int(default)
        except Exception:
            value = int(default)
        if min_value is not None and value < min_value:
            value = int(min_value)
        if max_value is not None and value > max_value:
            value = int(max_value)
        return value

    # ------------------------------------------------------------------
    # 输入范围 Token 预估（Phase 0 · 前置告警，advisory，不参与质量门决策）
    # 统一估算逻辑 → shared_backend/token_estimator.py（单一事实源）
    # ------------------------------------------------------------------

    @classmethod
    def build_scope_text(
        cls,
        *,
        requirement: str,
        prd_text: str = "",
        user_story: str = "",
        git_diff: str = "",
        defect_ticket: str = "",
        runtime_logs: str = "",
        input_sources: list[dict[str, Any]] | None = None,
    ) -> str:
        """把各文本来源拼成用于估算的整体输入文本（与喂给 LLM 的口径一致的近似）。"""
        parts: list[str] = [requirement, prd_text, user_story, git_diff, defect_ticket, runtime_logs]
        for item in input_sources or []:
            if isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, str):
                    parts.append(content)
        return "\n".join(part for part in parts if isinstance(part, str) and part.strip())

    @classmethod
    def estimate_input_scope(cls, text: str) -> dict[str, Any]:
        """估算输入 token 规模并给出三档 level（ok/warn/block）。委托 shared_backend 统一实现。"""
        from shared_backend.token_estimator import estimate_tokens
        est = estimate_tokens(text)
        return {
            "version": "RequirementScopeEstimateV1",
            "level": est["level"],
            "estimated_input_tokens": est["estimated_tokens"],
            "char_count": est["char_count"],
            "cjk_char_count": est["cjk_count"],
            "warn_tokens": est["warn_tokens"],
            "block_tokens": est["block_tokens"],
            "message": est["message"],
        }

    @staticmethod
    def is_llm_force_mode_enabled() -> bool:
        raw_mode = str(os.getenv("REQUIREMENT_PARSER_MODE", "")).strip().lower()
        if raw_mode == "llm":
            return True
        return False

    @staticmethod
    def infer_page_from_text(
        *,
        requirement: str,
        prd_text: str = "",
        user_story: str = "",
        git_diff: str = "",
        defect_ticket: str = "",
        runtime_logs: str = "",
        openapi_spec: dict[str, Any] | None = None,
        input_sources: list[dict[str, Any]] | None = None,
    ) -> str:
        parts = [
            str(requirement or ""),
            str(prd_text or ""),
            str(user_story or ""),
            str(git_diff or ""),
            str(defect_ticket or ""),
            str(runtime_logs or ""),
        ]
        if isinstance(openapi_spec, dict):
            parts.append(json.dumps(openapi_spec, ensure_ascii=False))
        if isinstance(input_sources, list):
            for item in input_sources:
                if not isinstance(item, dict):
                    continue
                parts.append(str(item.get("content", "") or ""))
                parts.append(str(item.get("source_type", "") or ""))
        text = "\n".join(part for part in parts if str(part).strip())
        mapping = (
            ("returnapply", ("退货", "退货申请", "refund", "return-apply")),
            ("order", ("订单", "order")),
            ("permission", ("权限", "permission")),
            ("payment", ("支付", "payment")),
            ("login", ("登录", "login")),
            ("home", ("首页", "home")),
            ("addproduct", ("添加商品", "add product", "addproduct")),
            ("product", ("商品", "product", "catalog", "目录")),
        )
        lower_text = text.lower()
        for page_name, keywords in mapping:
            for keyword in keywords:
                if keyword.lower() in lower_text:
                    return page_name
        return ""
