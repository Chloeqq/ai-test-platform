# mypy: ignore-errors

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime_compat import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

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


ACTION_KEYWORDS: dict[str, list[str]] = {
    "search": ["搜索", "查询", "筛选", "检索"],
    "create": ["新建", "创建", "新增", "添加"],
    "update": ["编辑", "修改", "更新"],
    "delete": ["删除", "移除", "作废"],
    "submit": ["提交", "保存", "确认"],
    "approve": ["审批", "审核", "通过", "驳回"],
    "login": ["登录", "登出", "鉴权"],
    "export": ["导出", "下载"],
    "import": ["导入", "上传"],
}

HIGH_RISK_KEYWORDS = ["支付", "退款", "下单", "结算", "权限", "登录", "删除", "审批", "发布", "风控"]
PERFORMANCE_KEYWORDS = ["性能", "并发", "吞吐", "响应时间", "延迟", "qps", "稳定性"]
SECURITY_KEYWORDS = ["安全", "越权", "鉴权", "注入", "xss", "csrf", "token", "权限控制"]
COMPATIBILITY_KEYWORDS = ["兼容", "浏览器", "设备", "系统版本", "ios", "android", "edge", "safari", "firefox"]
AMBIGUOUS_KEYWORDS = ["等等", "等", "相关", "尽量", "尽快", "适当", "必要时", "可能", "优化一下"]
RULE_PATTERNS: list[tuple[str, str]] = [
    ("must", r"(必须|务必|只能|不得|禁止)[^。；;]{1,80}"),
    ("range", r"(至少|最多|不超过|大于|小于|介于)[^。；;]{1,80}"),
    ("permission", r"(管理员|普通用户|访客|角色|权限)[^。；;]{1,80}"),
]
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
LOW_SIGNAL_SENTENCE_PATTERNS = [
    r"^diff --git",
    r"^index [0-9a-f]+\.\.[0-9a-f]+",
    r"^\+\+\+ ",
    r"^--- ",
    r"^@@ ",
    r"^new file mode",
    r"^deleted file mode",
]
NEGATIVE_KEYWORDS = ["异常", "错误", "失败", "空", "边界", "非法", "无效", "超时", "timeout"]
CRITICAL_CHANGE_FILE_HINTS = [
    "auth",
    "permission",
    "risk",
    "payment",
    "order",
    "security",
    "refund",
]

_STRUCTURED_REQUIREMENT_LABEL_KEY = {
    "用例名称": "title",
    "用例标题": "title",
    "标题": "title",
    "case title": "title",
    "title": "title",
    "前置条件": "precondition",
    "前提条件": "precondition",
    "precondition": "precondition",
    "测试步骤": "steps",
    "操作步骤": "steps",
    "步骤": "steps",
    "steps": "steps",
    "step": "steps",
    "预期结果": "expected_results",
    "期望结果": "expected_results",
    "断言": "expected_results",
    "expected": "expected_results",
    "expected result": "expected_results",
    "priority": "priority",
    "优先级": "priority",
}
_STRUCTURED_REQUIREMENT_LABEL_PATTERN = re.compile(
    r"(用例名称|用例标题|标题|前置条件|前提条件|测试步骤|操作步骤|步骤|预期结果|期望结果|断言|优先级|case title|title|precondition|steps?|expected(?: result)?|priority)\s*[:：\-]\s*",
    re.IGNORECASE,
)
_STRUCTURED_TITLE_NOISE_PREFIX = re.compile(r"^(?:前置条件|前提条件|测试步骤|操作步骤|步骤|预期结果|期望结果|断言)\s*[:：\-]?\s*")


class RequirementParserAgent:
    def __init__(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[3]
        self.report_root = self.repo_root / "reports" / "executions"
        self.telemetry_root = self.repo_root / "reports" / "telemetry"
        self.requirement_parse_eval_log = self.telemetry_root / "requirement-parser-eval.jsonl"

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
    ) -> dict[str, Any]:
        parse_started_at = datetime.now(UTC)
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

        merged_text = self._merge_source_text(normalized_sources)
        inferred_page = page or self._infer_page(merged_text)
        llm_overlay, llm_meta = self._run_llm_overlay(
            merged_text=merged_text,
            inferred_page=inferred_page,
            source_type=source_type,
            source_inputs=normalized_sources,
        )
        llm_mode = str(llm_meta.get("mode", "")).strip().lower()
        llm_succeeded = bool(llm_meta.get("succeeded", False))
        if llm_mode == "llm" and not llm_succeeded:
            reason = str(llm_meta.get("reason", "")).strip() or "llm execution failed"
            raise RuntimeError(f"forced llm mode requires successful llm overlay: {reason[:240]}")
        entities = self._extract_entities(merged_text, page=inferred_page, openapi_spec=effective_openapi_spec, git_diff=normalized_git_diff)
        intents = self._extract_test_intents(
            sources=normalized_sources,
            page=inferred_page,
            openapi_spec=effective_openapi_spec,
            git_diff=normalized_git_diff,
            defect_ticket=normalized_defect,
            runtime_logs=normalized_logs,
        )
        intents = self._deduplicate_intents(intents)
        intents = self._ensure_minimum_intent_baseline(
            intents=intents,
            page=inferred_page,
            sources=normalized_sources,
            git_diff=normalized_git_diff,
            defect_ticket=normalized_defect,
            runtime_logs=normalized_logs,
        )
        intents = self._merge_llm_intents(intents=intents, llm_overlay=llm_overlay, page=inferred_page)
        intents = self._ensure_minimum_intent_baseline(
            intents=intents,
            page=inferred_page,
            sources=normalized_sources,
            git_diff=normalized_git_diff,
            defect_ticket=normalized_defect,
            runtime_logs=normalized_logs,
        )
        intents = self._apply_dependency_analysis(intents)
        priority = self._infer_priority(
            merged_text,
            intents=intents,
            defect_ticket=normalized_defect,
            git_diff=normalized_git_diff,
            source_inputs=normalized_sources,
        )
        priority = self._merge_llm_priority(priority=priority, llm_overlay=llm_overlay)
        coverage_matrix = self._build_coverage_matrix(normalized_sources, intents)
        dependency_graph = self._build_dependency_graph(intents)
        business_rules = self._extract_business_rules(merged_text)
        business_rules = self._merge_llm_business_rules(business_rules=business_rules, llm_overlay=llm_overlay)
        ambiguities = self._detect_ambiguities(merged_text)
        ambiguities = self._merge_llm_ambiguities(ambiguities=ambiguities, llm_overlay=llm_overlay)
        change_impact = self._analyze_change_impact(
            git_diff=normalized_git_diff,
            intents=intents,
            inferred_page=inferred_page,
        )
        historical_patterns = self._extract_historical_patterns(intents=intents, page=inferred_page)
        design_input = self._build_design_input(
            raw_requirement=normalized_requirement or merged_text,
            intents=intents,
            priority=priority,
            business_rules=business_rules,
            ambiguities=ambiguities,
        )
        parse_confidence = self._estimate_parse_confidence(
            source_count=len(normalized_sources),
            entities=entities,
            intents=intents,
            ambiguities=ambiguities,
        )
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
            change_impact=change_impact,
            historical_patterns=historical_patterns,
            priority=priority,
            design_input=design_input,
            parse_confidence=parse_confidence,
            parser_runtime=parser_runtime,
        )
        parsed_result = spec.to_dict()
        self._append_parse_evaluation_log(parsed_result)
        return parsed_result

    def _build_parser_runtime_metadata(
        self,
        *,
        llm_meta: dict[str, Any] | None = None,
        parse_started_at: datetime | None = None,
        source_count: int = 0,
        intent_count: int = 0,
        ambiguity_count: int = 0,
        parse_confidence: float = 0.0,
    ) -> dict[str, Any]:
        openai_model = str(os.getenv("OPENAI_MODEL", "")).strip()
        openai_api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
        legacy_mode = str(os.getenv("REQUIREMENT_PARSER_MODE", "")).strip().lower()
        configured_model = (
            openai_model
            or str(os.getenv("REQUIREMENT_PARSER_MODEL", "")).strip()
            or "rule-engine"
        )
        if legacy_mode in {"rule_based", "llm", "hybrid"}:
            configured_mode = legacy_mode
        else:
            configured_mode = "llm" if openai_api_key else "rule_based"
        llm_enabled = configured_mode in {"llm", "hybrid"} and bool(openai_api_key)
        prompt_fingerprint = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:16]
        parse_finished_at = datetime.now(UTC)
        parse_started = parse_started_at or parse_finished_at
        parse_duration_ms = max(0, int((parse_finished_at - parse_started).total_seconds() * 1000))
        return {
            "agent": "requirement-parser-agent",
            "pipeline": "requirement->test_points",
            "generated_at": parse_finished_at.isoformat(),
            "mode": configured_mode,
            "llm_enabled": llm_enabled,
            "model": configured_model if llm_enabled else "rule-engine",
            "prompt_name": PROMPT_NAME,
            "prompt_version": PROMPT_VERSION,
            "prompt_fingerprint": prompt_fingerprint,
            "instructions_version": INSTRUCTIONS_VERSION,
            "parse_started_at": parse_started.isoformat(),
            "parse_finished_at": parse_finished_at.isoformat(),
            "parse_duration_ms": parse_duration_ms,
            "source_count": max(0, int(source_count)),
            "intent_count": max(0, int(intent_count)),
            "ambiguity_count": max(0, int(ambiguity_count)),
            "parse_confidence": round(float(parse_confidence), 2),
            "llm_trace": llm_meta or {},
        }

    def _run_llm_overlay(
        self,
        *,
        merged_text: str,
        inferred_page: str,
        source_type: str,
        source_inputs: list[RequirementSourceInput],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        openai_model = str(os.getenv("OPENAI_MODEL", "")).strip()
        openai_api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
        legacy_mode = str(os.getenv("REQUIREMENT_PARSER_MODE", "")).strip().lower()
        if legacy_mode in {"rule_based", "llm", "hybrid"}:
            configured_mode = legacy_mode
        else:
            configured_mode = "llm" if openai_api_key else "rule_based"
        configured_model = (
            openai_model
            or str(os.getenv("REQUIREMENT_PARSER_MODEL", "")).strip()
            or "rule-engine"
        )
        llm_meta: dict[str, Any] = {
            "attempted": False,
            "succeeded": False,
            "fallback_used": False,
            "mode": configured_mode,
            "model": configured_model,
            "reason_code": "",
            "reason": "",
            "source_count": len(source_inputs),
            "input_chars": len(merged_text),
            "prompt_chars": 0,
            "overlay_key_count": 0,
        }
        started_at = datetime.now(UTC)
        if configured_mode not in {"llm", "hybrid"}:
            llm_meta["reason_code"] = "mode_disabled"
            llm_meta["reason"] = "llm mode disabled"
            return {}, self._finalize_llm_meta(llm_meta=llm_meta, started_at=started_at, overlay={})

        api_key = openai_api_key
        if not api_key:
            llm_meta["fallback_used"] = True
            llm_meta["reason_code"] = "missing_api_key"
            llm_meta["reason"] = "OPENAI_API_KEY is empty"
            return {}, self._finalize_llm_meta(llm_meta=llm_meta, started_at=started_at, overlay={})

        llm_meta["attempted"] = True
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key,
                base_url=str(os.getenv("OPENAI_BASE_URL", "")).strip() or None,
                timeout=30,
                max_retries=0,
            )
            prompt_payload = {
                "source_type": source_type,
                "page": inferred_page,
                "source_count": len(source_inputs),
                "text": merged_text[:12000],
                "output_format": {
                    "page": "string",
                    "priority": "P0|P1|P2",
                    "test_intents": [
                        {
                            "title": "string",
                            "intent_type": "functional|negative|performance|security|compatibility|regression|api",
                            "priority": "P0|P1|P2",
                            "steps_hint": ["string"],
                        }
                    ],
                    "business_rules": ["string"],
                    "ambiguities": ["string"],
                },
            }
            llm_meta["prompt_chars"] = len(json.dumps(prompt_payload, ensure_ascii=False))
            completion = client.chat.completions.create(
                model=configured_model,
                temperature=0.1,
                max_tokens=400,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
                ],
            )
            usage = getattr(completion, "usage", None)
            if usage is not None:
                llm_meta["prompt_tokens"] = getattr(usage, "prompt_tokens", None)
                llm_meta["completion_tokens"] = getattr(usage, "completion_tokens", None)
                llm_meta["total_tokens"] = getattr(usage, "total_tokens", None)
            content = str((completion.choices[0].message.content if completion.choices else "") or "").strip()
            overlay = self._extract_json_object(content)
            if not isinstance(overlay, dict) or not overlay:
                overlay = self._salvage_overlay_from_text(raw_text=content, page=inferred_page)
                if overlay:
                    llm_meta["succeeded"] = True
                    llm_meta["reason_code"] = "ok_salvaged"
                    llm_meta["reason"] = "ok_salvaged"
                    return overlay, self._finalize_llm_meta(llm_meta=llm_meta, started_at=started_at, overlay=overlay)
                llm_meta["reason_code"] = "invalid_overlay"
                raise ValueError("llm output is not valid JSON object")
            llm_meta["succeeded"] = True
            llm_meta["reason_code"] = "ok"
            llm_meta["reason"] = "ok"
            return overlay, self._finalize_llm_meta(llm_meta=llm_meta, started_at=started_at, overlay=overlay)
        except Exception as exc:
            llm_meta["fallback_used"] = True
            llm_meta["reason_code"] = llm_meta.get("reason_code") or "llm_exception"
            llm_meta["reason"] = f"llm overlay failed: {str(exc)[:200]}"
            return {}, self._finalize_llm_meta(llm_meta=llm_meta, started_at=started_at, overlay={})

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
        text = str(raw or "").strip()
        if not text:
            return {}
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            payload = json.loads(text[start : end + 1])
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _salvage_overlay_from_text(self, *, raw_text: str, page: str) -> dict[str, Any]:
        text = str(raw_text or "").strip()
        if not text:
            return {}
        lines = [self._sanitize_sentence(line) for line in text.splitlines()]
        candidates: list[str] = []
        for line in lines:
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith(("```", "json", "输出", "说明", "结果")):
                continue
            if len(line) < 6:
                continue
            candidates.append(line)
            if len(candidates) >= 12:
                break
        if not candidates:
            return {}

        test_intents: list[dict[str, Any]] = []
        for line in candidates[:6]:
            intent_type = self._classify_intent_type(line)
            steps_hint = self._infer_steps_hint(line, intent_type, page)
            test_intents.append(
                {
                    "title": line[:120],
                    "intent_type": intent_type,
                    "priority": "P1",
                    "steps_hint": steps_hint or [f"open:{page or 'target_page'}", "assert"],
                }
            )
        return {"test_intents": test_intents} if test_intents else {}

    def _merge_llm_intents(
        self,
        *,
        intents: list[TestIntent],
        llm_overlay: dict[str, Any],
        page: str,
    ) -> list[TestIntent]:
        raw_items = llm_overlay.get("test_intents")
        if not isinstance(raw_items, list):
            return intents
        merged = list(intents)
        for item in raw_items[:30]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            intent_type = str(item.get("intent_type", "functional")).strip().lower() or "functional"
            priority = str(item.get("priority", "P1")).strip().upper() or "P1"
            raw_steps_hint = item.get("steps_hint") if isinstance(item.get("steps_hint"), list) else []
            steps_hint = [str(step).strip() for step in raw_steps_hint if str(step).strip()]
            if not steps_hint:
                steps_hint = self._infer_steps_hint(title, intent_type, page)
            merged.append(
                TestIntent(
                    intent_id=f"intent-{len(merged)+1:02d}",
                    title=title[:120],
                    intent_type=intent_type,
                    priority=priority if priority in {"P0", "P1", "P2"} else "P1",
                    steps_hint=steps_hint,
                    dependencies=[],
                    source_ids=[],
                )
            )
        return self._deduplicate_intents(merged)

    @staticmethod
    def _merge_llm_priority(*, priority: str, llm_overlay: dict[str, Any]) -> str:
        llm_priority = str(llm_overlay.get("priority", "")).strip().upper()
        if llm_priority not in {"P0", "P1", "P2"}:
            return priority
        ranking = {"P0": 3, "P1": 2, "P2": 1}
        current = str(priority or "P1").strip().upper()
        return llm_priority if ranking.get(llm_priority, 0) >= ranking.get(current, 0) else current

    def _merge_llm_business_rules(
        self,
        *,
        business_rules: list[BusinessRule],
        llm_overlay: dict[str, Any],
    ) -> list[BusinessRule]:
        raw_rules = llm_overlay.get("business_rules")
        if not isinstance(raw_rules, list):
            return business_rules
        merged = list(business_rules)
        for text in raw_rules[:20]:
            rule_text = str(text).strip()
            if not rule_text:
                continue
            merged.append(
                BusinessRule(
                    rule_id=f"rule-{len(merged)+1:02d}",
                    rule_text=rule_text[:200],
                    rule_type="llm",
                    confidence=0.72,
                )
            )
        dedup: dict[tuple[str, str], BusinessRule] = {}
        for rule in merged:
            key = (rule.rule_type, rule.rule_text)
            if key not in dedup:
                dedup[key] = rule
        rows = list(dedup.values())
        for index, row in enumerate(rows, start=1):
            row.rule_id = f"rule-{index:02d}"
        return rows[:40]

    def _merge_llm_ambiguities(
        self,
        *,
        ambiguities: list[AmbiguityItem],
        llm_overlay: dict[str, Any],
    ) -> list[AmbiguityItem]:
        raw_ambiguities = llm_overlay.get("ambiguities")
        if not isinstance(raw_ambiguities, list):
            return ambiguities
        merged = list(ambiguities)
        for text in raw_ambiguities[:20]:
            line = str(text).strip()
            if not line:
                continue
            merged.append(
                AmbiguityItem(
                    item_id=f"amb-{len(merged)+1:02d}",
                    text=line[:120],
                    reason="LLM 识别到潜在需求歧义。",
                    suggestion="请补充可验证阈值与前置条件。",
                    severity="medium",
                )
            )
        dedup: dict[str, AmbiguityItem] = {}
        for row in merged:
            key = row.text.strip()
            if key and key not in dedup:
                dedup[key] = row
        rows = list(dedup.values())
        for index, row in enumerate(rows, start=1):
            row.item_id = f"amb-{index:02d}"
        return rows[:40]

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
                item_type = self._canonical_source_type(str(item.get("source_type", "text")).strip().lower() or "text")
                content = str(item.get("content", "")).strip()
                metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
                metadata = dict(metadata)
                if not content:
                    continue
                metadata.setdefault("content", content[:8000])
                sources.append(
                    RequirementSourceInput(
                        source_id=f"source-{index:02d}",
                        source_type=item_type,
                        content_preview=content[:200],
                        metadata=metadata,
                    )
                )
        if requirement:
            requirement_metadata: dict[str, Any] = {"field": "requirement", "content": requirement[:8000]}
            structured_case = self._extract_structured_requirement_fields(requirement)
            if structured_case:
                requirement_metadata["structured_case"] = structured_case
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type=self._canonical_source_type(source_type or "text"),
                    content_preview=requirement[:200],
                    metadata=requirement_metadata,
                )
            )
        if prd_text:
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type="prd",
                    content_preview=prd_text[:200],
                    metadata={"field": "prd_text", "content": prd_text[:8000], "source_ref": prd_url},
                )
            )
        if user_story:
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type="user_story",
                    content_preview=user_story[:200],
                    metadata={"field": "user_story", "content": user_story[:8000]},
                )
            )
        if git_diff:
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type="git_diff",
                    content_preview=git_diff[:200],
                    metadata={"field": "git_diff", "content": git_diff[:12000], "source_ref": git_diff_path},
                )
            )
        if defect_ticket:
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type="defect_ticket",
                    content_preview=defect_ticket[:200],
                    metadata={"field": "defect_ticket", "content": defect_ticket[:8000]},
                )
            )
        if runtime_logs:
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type="runtime_logs",
                    content_preview=runtime_logs[:200],
                    metadata={"field": "runtime_logs", "content": runtime_logs[:8000]},
                )
            )
        if isinstance(openapi_spec, dict) and openapi_spec:
            title = str(((openapi_spec.get("info") or {}).get("title", "OpenAPI"))).strip() or "OpenAPI"
            openapi_summary = self._summarize_openapi_spec(openapi_spec)
            sources.append(
                RequirementSourceInput(
                    source_id=f"source-{len(sources)+1:02d}",
                    source_type="openapi",
                    content_preview=f"{title} ({len((openapi_spec.get('paths') or {}))} paths)",
                    metadata={"field": "openapi_spec", "content": openapi_summary, "source_ref": openapi_url},
                )
            )
        return sources

    def _safe_fetch_document(self, url: str) -> dict[str, Any]:
        try:
            return fetch_document(url=url)
        except DocumentFetchError:
            return {}
        except Exception:
            return {}

    def _safe_read_local_file(self, file_path: str) -> str:
        try:
            payload = read_local_file(path=file_path, repo_root=self.repo_root)
            return str(payload.get("text", "")).strip()
        except LocalFileReadError:
            return ""
        except Exception:
            return ""

    @staticmethod
    def _split_structured_text_items(value: str) -> list[str]:
        text = str(value or "").replace("\r", "\n").strip()
        if not text:
            return []
        text = re.sub(r"[；;]+", "\n", text)
        text = re.sub(r"\s*([0-9]+)\s*[\.\)、]\s*", r"\n\1. ", text)
        text = re.sub(r"\s*[•·]\s*", "\n", text)
        rows: list[str] = []
        for raw_line in text.split("\n"):
            line = str(raw_line).strip(" \t-，,。")
            if not line:
                continue
            line = re.sub(r"^(?:\d+\.\s*|[-*]\s*)", "", line).strip()
            if not line:
                continue
            if line.lower() in _STRUCTURED_REQUIREMENT_LABEL_KEY:
                continue
            rows.append(line[:240])
        dedup: list[str] = []
        for row in rows:
            if row not in dedup:
                dedup.append(row)
        return dedup

    def _extract_structured_requirement_fields(self, text: str) -> dict[str, Any]:
        raw_text = str(text or "").strip()
        if not raw_text:
            return {}
        matches = list(_STRUCTURED_REQUIREMENT_LABEL_PATTERN.finditer(raw_text))
        if not matches:
            return {}
        structured: dict[str, Any] = {
            "title": "",
            "precondition": "",
            "steps": [],
            "expected_results": [],
            "priority": "",
        }
        for index, match in enumerate(matches):
            raw_label = str(match.group(1) or "").strip().lower()
            canonical_key = _STRUCTURED_REQUIREMENT_LABEL_KEY.get(raw_label)
            if not canonical_key:
                continue
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_text)
            value = str(raw_text[start:end]).strip(" \n\r\t-：:，,。")
            if not value:
                continue
            if canonical_key in {"steps", "expected_results"}:
                items = self._split_structured_text_items(value)
                if items:
                    merged_items = structured.get(canonical_key)
                    if not isinstance(merged_items, list):
                        merged_items = []
                    for item in items:
                        if item not in merged_items:
                            merged_items.append(item)
                    structured[canonical_key] = merged_items
                continue
            if canonical_key == "priority":
                priority_match = re.search(r"\bP[0-3]\b", value.upper())
                structured["priority"] = priority_match.group(0) if priority_match else ""
                continue
            current_text = str(structured.get(canonical_key, "")).strip()
            if not current_text:
                structured[canonical_key] = value[:240]
        has_signal = any(
            [
                str(structured.get("title", "")).strip(),
                str(structured.get("precondition", "")).strip(),
                bool(structured.get("steps")),
                bool(structured.get("expected_results")),
            ]
        )
        return structured if has_signal else {}

    @staticmethod
    def _normalize_structured_priority(value: str) -> str:
        candidate = str(value or "").strip().upper()
        return candidate if candidate in {"P0", "P1", "P2"} else ""

    @staticmethod
    def _infer_structured_title(
        *,
        title: str,
        page: str,
        steps: list[str],
        expected_results: list[str],
    ) -> str:
        normalized_title = _STRUCTURED_TITLE_NOISE_PREFIX.sub("", str(title or "").strip())
        if normalized_title:
            return normalized_title[:120]
        for item in steps:
            quoted = re.findall(r"[「“\"'《](.*?)[」”\"'》]", str(item))
            if quoted:
                candidate = str(quoted[-1]).strip()
                if candidate:
                    return f"{candidate}页面主流程校验"[:120]
        for item in expected_results:
            candidate = str(item).strip()
            if candidate:
                short = candidate[:40]
                return f"{short}校验"[:120]
        fallback_page = str(page or "目标页面").strip() or "目标页面"
        return f"{fallback_page}页面主流程校验"[:120]

    def _extract_structured_case_intents(
        self,
        *,
        source: RequirementSourceInput,
        page: str,
        defect_ticket: str,
        git_diff: str,
        start_index: int,
    ) -> list[TestIntent]:
        metadata = source.metadata if isinstance(source.metadata, dict) else {}
        structured = metadata.get("structured_case")
        if not isinstance(structured, dict):
            return []
        title = str(structured.get("title", "")).strip()
        precondition = str(structured.get("precondition", "")).strip()
        steps = [
            str(item).strip()
            for item in (structured.get("steps") if isinstance(structured.get("steps"), list) else [])
            if str(item).strip()
        ]
        expected_results = [
            str(item).strip()
            for item in (
                structured.get("expected_results") if isinstance(structured.get("expected_results"), list) else []
            )
            if str(item).strip()
        ]
        merged_text = " ".join([title, precondition, *steps[:8], *expected_results[:8]]).strip()
        if not merged_text:
            return []
        priority = self._normalize_structured_priority(str(structured.get("priority", "")).strip()) or self._infer_priority(
            merged_text,
            intents=[],
            defect_ticket=defect_ticket,
            git_diff=git_diff,
            source_inputs=[],
        )
        normalized_title = self._infer_structured_title(
            title=title,
            page=page,
            steps=steps,
            expected_results=expected_results,
        )
        intent_type = self._classify_intent_type(merged_text)
        steps_hint = self._extract_steps_hint(merged_text, page=page, source_type="text")
        if not steps_hint:
            steps_hint = [f"open:{page or 'target_page'}", "smoke", "assert"]
        lowered_hints = [str(item).strip().lower() for item in steps_hint]
        if expected_results and "assert" not in lowered_hints:
            steps_hint.append("assert")
        return [
            TestIntent(
                intent_id=f"intent-{start_index:02d}",
                title=normalized_title[:90],
                intent_type=intent_type,
                priority=priority,
                steps_hint=steps_hint,
                dependencies=[],
                source_ids=[source.source_id],
            )
        ]

    @staticmethod
    def _parse_openapi_text(raw_text: str) -> dict[str, Any] | None:
        if not raw_text.strip():
            return None
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        try:
            import yaml

            parsed_yaml = yaml.safe_load(raw_text)
            if isinstance(parsed_yaml, dict):
                return parsed_yaml
        except Exception:
            return None
        return None

    @staticmethod
    def _merge_source_text(sources: list[RequirementSourceInput]) -> str:
        parts = []
        for source in sources:
            prefix = f"[{source.source_type}]"
            source_text = source.content_preview
            if isinstance(source.metadata, dict):
                source_text = str(source.metadata.get("content", source_text)).strip()[:300]
            parts.append(f"{prefix} {source_text}")
        return "\n".join(parts).strip()

    @staticmethod
    def _canonical_source_type(source_type: str) -> str:
        normalized = (source_type or "text").strip().lower()
        return SOURCE_TYPE_ALIASES.get(normalized, normalized or "text")

    @staticmethod
    def _summarize_openapi_spec(openapi_spec: dict[str, Any]) -> str:
        if not isinstance(openapi_spec, dict):
            return ""
        lines: list[str] = []
        title = str(((openapi_spec.get("info") or {}).get("title", "OpenAPI"))).strip()
        if title:
            lines.append(title)
        for path_name, methods in list((openapi_spec.get("paths") or {}).items())[:100]:
            if not isinstance(methods, dict):
                continue
            for method, operation in methods.items():
                method_name = str(method).strip().upper()
                if method_name not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                    continue
                op = operation if isinstance(operation, dict) else {}
                summary = str(op.get("summary") or op.get("operationId") or "").strip()
                line = f"{method_name} {path_name}"
                if summary:
                    line = f"{line} - {summary}"
                lines.append(line)
        return "\n".join(lines)[:10000]

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _infer_page(self, text: str) -> str:
        match = re.search(r"(商品|订单|退货|权限|用户|登录|首页|结算|支付|目录|分类)", text)
        if not match:
            return "product"
        mapping = {
            "商品": "product",
            "订单": "order",
            "退货": "returnapply",
            "权限": "permission",
            "用户": "user",
            "登录": "login",
            "首页": "home",
            "结算": "checkout",
            "支付": "payment",
            "目录": "catalog",
            "分类": "category",
        }
        return mapping.get(match.group(1), "product")

    def _extract_entities(
        self,
        text: str,
        *,
        page: str,
        openapi_spec: dict[str, Any] | None,
        git_diff: str,
    ) -> list[RequirementEntity]:
        entities: list[RequirementEntity] = [RequirementEntity(name=page, entity_type="page", confidence=0.96)]
        for token in ["服务单号", "订单号", "商品名称", "用户名", "密码", "状态", "时间范围", "SKU", "金额", "手机号"]:
            if token in text:
                entities.append(RequirementEntity(name=token, entity_type="field", confidence=0.88))
        for action, keywords in ACTION_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                entities.append(RequirementEntity(name=action, entity_type="action", confidence=0.86))
        for endpoint in re.findall(r"\b(?:GET|POST|PUT|PATCH|DELETE)\s+([/\w\-\{\}]+)", text, re.IGNORECASE):
            entities.append(RequirementEntity(name=endpoint, entity_type="api_path", confidence=0.86))
        for url in re.findall(r"https?://[^\s\"']+", text):
            entities.append(RequirementEntity(name=url[:120], entity_type="url", confidence=0.82))

        element_tokens = re.findall(r"(按钮|输入框|下拉|表格|弹窗|菜单|分页|筛选器|卡片)", text)
        for token in element_tokens:
            entities.append(RequirementEntity(name=token, entity_type="ui_element", confidence=0.83))

        if isinstance(openapi_spec, dict):
            for path_name in list((openapi_spec.get("paths") or {}).keys())[:20]:
                entities.append(RequirementEntity(name=str(path_name), entity_type="api_path", confidence=0.87))

        for changed in re.findall(r"\+\+\+\s+b/([^\s]+)", git_diff):
            entities.append(RequirementEntity(name=changed, entity_type="changed_file", confidence=0.8))

        return self._deduplicate_entities(entities)

    @staticmethod
    def _deduplicate_entities(items: list[RequirementEntity]) -> list[RequirementEntity]:
        dedup: dict[tuple[str, str], RequirementEntity] = {}
        for item in items:
            key = (item.name.strip(), item.entity_type.strip())
            if not key[0] or not key[1]:
                continue
            current = dedup.get(key)
            if current is None or item.confidence > current.confidence:
                dedup[key] = item
        return list(dedup.values())

    def _extract_test_intents(
        self,
        *,
        sources: list[RequirementSourceInput],
        page: str,
        openapi_spec: dict[str, Any] | None,
        git_diff: str,
        defect_ticket: str,
        runtime_logs: str,
    ) -> list[TestIntent]:
        intents: list[TestIntent] = []
        for source in sources:
            source_type = self._canonical_source_type(source.source_type)
            structured_intents = self._extract_structured_case_intents(
                source=source,
                page=page,
                defect_ticket=defect_ticket,
                git_diff=git_diff,
                start_index=len(intents) + 1,
            )
            if structured_intents:
                intents.extend(structured_intents)
                continue
            source_text = self._read_source_content(source)
            if not source_text:
                continue
            if source_type == "openapi":
                intents.extend(
                    self._extract_api_source_intents(
                        text=source_text,
                        page=page,
                        source_id=source.source_id,
                        start_index=len(intents) + 1,
                    )
                )
                continue
            if source_type == "git_diff":
                intents.extend(
                    self._extract_git_diff_intents(
                        source_text,
                        page=page,
                        source_id=source.source_id,
                        start_index=len(intents) + 1,
                    )
                )
                continue
            intents.extend(
                self._extract_sentence_intents(
                    text=source_text,
                    source_type=source_type,
                    source_id=source.source_id,
                    page=page,
                    git_diff=git_diff,
                    defect_ticket=defect_ticket,
                    start_index=len(intents) + 1,
                )
            )

        intents.extend(self._extract_openapi_intents(openapi_spec, start_index=len(intents) + 1))
        intents.extend(
            self._extract_defect_intents(
                defect_ticket,
                runtime_logs,
                page=page,
                start_index=len(intents) + 1,
            )
        )
        if not intents:
            intents.append(
                TestIntent(
                    intent_id="intent-01",
                    title="基础流程验证",
                    intent_type="functional",
                    priority="P1",
                    steps_hint=[f"open:{page}", "assert"],
                    dependencies=[],
                    source_ids=[],
                )
            )
        return intents

    def _ensure_minimum_intent_baseline(
        self,
        *,
        intents: list[TestIntent],
        page: str,
        sources: list[RequirementSourceInput],
        git_diff: str,
        defect_ticket: str,
        runtime_logs: str,
    ) -> list[TestIntent]:
        if not intents:
            return intents

        normalized_page = str(page or "target_page").strip() or "target_page"
        source_types = {
            self._canonical_source_type(str(source.source_type).strip().lower())
            for source in sources
            if isinstance(source, RequirementSourceInput)
        }
        intent_rows = list(intents)
        existing_titles = {str(intent.title).strip().lower() for intent in intent_rows if str(intent.title).strip()}
        has_primary_flow = any(intent.intent_type in {"functional", "api"} for intent in intent_rows)
        negative_like_count = sum(
            1 for intent in intent_rows if intent.intent_type in {"negative", "security", "compatibility"}
        )

        enforce_baseline = bool(
            source_types.intersection({"text", "manual", "requirement", "prd", "user_story", "ai"})
            or len(intent_rows) <= 2
        )
        if not enforce_baseline:
            return self._deduplicate_intents(intent_rows)

        baseline_templates: list[tuple[str, str, list[str], str]] = [
            ("functional", f"{normalized_page}主流程功能校验", [f"open:{normalized_page}", "smoke", "assert"], "P1"),
            (
                "negative",
                f"{normalized_page}异常输入与错误处理校验",
                [f"open:{normalized_page}", "negative", "assert"],
                "P1",
            ),
            (
                "negative",
                f"{normalized_page}边界值与必填约束校验",
                [f"open:{normalized_page}", "boundary", "assert"],
                "P1",
            ),
        ]

        for intent_type, title, steps_hint, priority in baseline_templates:
            if intent_type == "functional" and has_primary_flow:
                continue
            if intent_type == "negative" and negative_like_count >= 2:
                continue
            title_key = title.strip().lower()
            if title_key in existing_titles:
                continue
            intent_rows.append(
                TestIntent(
                    intent_id=f"intent-{len(intent_rows)+1:02d}",
                    title=title[:90],
                    intent_type=intent_type,
                    priority=priority,
                    steps_hint=steps_hint,
                    dependencies=[],
                    source_ids=[],
                )
            )
            existing_titles.add(title_key)
            if intent_type == "functional":
                has_primary_flow = True
            if intent_type == "negative":
                negative_like_count += 1

        has_regression = any(intent.intent_type == "regression" for intent in intent_rows)
        if (git_diff.strip() or defect_ticket.strip() or runtime_logs.strip()) and not has_regression:
            regression_title = f"{normalized_page}变更影响回归校验"
            if regression_title.strip().lower() not in existing_titles:
                intent_rows.append(
                    TestIntent(
                        intent_id=f"intent-{len(intent_rows)+1:02d}",
                        title=regression_title[:90],
                        intent_type="regression",
                        priority="P1",
                        steps_hint=[f"open:{normalized_page}", "regression", "assert"],
                        dependencies=[],
                        source_ids=[],
                    )
                )

        return self._deduplicate_intents(intent_rows)

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        if not text.strip():
            return []
        raw_fragments = re.split(r"[。；;!?\n]+", text)
        fragments: list[str] = []
        for item in raw_fragments:
            normalized = item.strip(" ，,")
            if not normalized:
                continue
            if any(re.match(pattern, normalized, re.IGNORECASE) for pattern in LOW_SIGNAL_SENTENCE_PATTERNS):
                continue
            if len(normalized) <= 2:
                continue
            fragments.append(normalized)
        return fragments

    def _extract_sentence_intents(
        self,
        *,
        text: str,
        source_type: str,
        source_id: str,
        page: str,
        git_diff: str,
        defect_ticket: str,
        start_index: int,
    ) -> list[TestIntent]:
        intents: list[TestIntent] = []
        index = start_index
        fragments = self._split_sentences(text)
        for sentence in fragments[:60]:
            sentence = self._sanitize_sentence(sentence)
            if not sentence or self._is_low_signal_sentence(sentence):
                continue
            intent_type = self._classify_intent_type(sentence)
            priority = self._infer_priority(
                sentence,
                intents=[],
                defect_ticket=defect_ticket,
                git_diff=git_diff,
                source_inputs=[],
            )
            title = sentence if source_type in {"text", "manual", "requirement"} else f"[{source_type}] {sentence}"
            intents.append(
                TestIntent(
                    intent_id=f"intent-{index:02d}",
                    title=title[:90],
                    intent_type=intent_type,
                    priority=priority,
                    steps_hint=self._extract_steps_hint(sentence, page=page, source_type=source_type),
                    dependencies=[],
                    source_ids=[source_id],
                )
            )
            index += 1
        return intents

    @staticmethod
    def _sanitize_sentence(sentence: str) -> str:
        cleaned = re.sub(r"\s+", " ", sentence).strip()
        cleaned = cleaned.strip("`'\"")
        cleaned = cleaned[:240]
        return cleaned

    @staticmethod
    def _is_low_signal_sentence(sentence: str) -> bool:
        lowered = sentence.lower()
        if any(re.match(pattern, lowered) for pattern in LOW_SIGNAL_SENTENCE_PATTERNS):
            return True
        if re.fullmatch(r"[+\-@#*/\s0-9a-fA-F:.]{3,}", sentence):
            return True
        if sentence.count("/") > 4 and " " not in sentence:
            return True
        return False

    @staticmethod
    def _read_source_content(source: RequirementSourceInput) -> str:
        if isinstance(source.metadata, dict):
            value = source.metadata.get("content")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return str(source.content_preview or "").strip()

    def _extract_api_source_intents(
        self,
        *,
        text: str,
        page: str,
        source_id: str,
        start_index: int,
    ) -> list[TestIntent]:
        intents: list[TestIntent] = []
        index = start_index
        endpoint_matches = re.findall(r"\b(GET|POST|PUT|PATCH|DELETE)\s+([/\w\-\{\}]+)", text, re.IGNORECASE)
        for method, path_name in endpoint_matches[:40]:
            normalized_method = str(method).upper()
            title = f"API: {normalized_method} {path_name}"
            intents.append(
                TestIntent(
                    intent_id=f"intent-{index:02d}",
                    title=title[:90],
                    intent_type="api",
                    priority="P1",
                    steps_hint=[f"api:{normalized_method.lower()}:{path_name}", "assert"],
                    dependencies=[],
                    source_ids=[source_id],
                )
            )
            index += 1
        if intents:
            return intents
        fallback_fragments = self._split_sentences(text)
        for sentence in fallback_fragments[:20]:
            title = f"[openapi] {sentence}"
            intents.append(
                TestIntent(
                    intent_id=f"intent-{index:02d}",
                    title=title[:90],
                    intent_type="api",
                    priority="P1",
                    steps_hint=[f"open:{page}", "api", "assert"],
                    dependencies=[],
                    source_ids=[source_id],
                )
            )
            index += 1
        return intents

    def _extract_openapi_intents(self, openapi_spec: dict[str, Any] | None, *, start_index: int) -> list[TestIntent]:
        if not isinstance(openapi_spec, dict):
            return []
        intents: list[TestIntent] = []
        index = start_index
        for path_name, methods in list((openapi_spec.get("paths") or {}).items())[:50]:
            if not isinstance(methods, dict):
                continue
            for method, operation in methods.items():
                normalized_method = str(method).strip().lower()
                if normalized_method not in {"get", "post", "put", "patch", "delete"}:
                    continue
                op = operation if isinstance(operation, dict) else {}
                title = str(op.get("summary") or op.get("operationId") or f"{normalized_method.upper()} {path_name}").strip()
                title = f"API: {title}"
                intents.append(
                    TestIntent(
                        intent_id=f"intent-{index:02d}",
                        title=title[:80],
                        intent_type="api",
                        priority="P1",
                        steps_hint=[f"api:{normalized_method}:{path_name}", "assert"],
                        dependencies=[],
                        source_ids=[],
                    )
                )
                index += 1
        return intents

    def _extract_git_diff_intents(
        self,
        git_diff: str,
        *,
        page: str,
        source_id: str,
        start_index: int,
    ) -> list[TestIntent]:
        if not git_diff.strip():
            return []
        intents: list[TestIntent] = []
        index = start_index
        changed_files = re.findall(r"\+\+\+\s+b/([^\s]+)", git_diff)
        changed_functions = re.findall(r"^\+\s*def\s+([a-zA-Z_]\w*)", git_diff, re.MULTILINE)
        for file_path in changed_files[:20]:
            module = file_path.split("/")[-1]
            intents.append(
                TestIntent(
                    intent_id=f"intent-{index:02d}",
                    title=f"变更影响回归: {module}",
                    intent_type="regression",
                    priority=self._priority_from_changed_file(file_path),
                    steps_hint=[f"open:{page}", "regression", "assert"],
                    dependencies=[],
                    source_ids=[source_id],
                )
            )
            index += 1
        for function_name in changed_functions[:20]:
            intents.append(
                TestIntent(
                    intent_id=f"intent-{index:02d}",
                    title=f"变更函数回归: {function_name}",
                    intent_type="regression",
                    priority="P1",
                    steps_hint=[f"open:{page}", "regression", "assert"],
                    dependencies=[],
                    source_ids=[source_id],
                )
            )
            index += 1
        return intents

    def _extract_defect_intents(
        self,
        defect_ticket: str,
        runtime_logs: str,
        *,
        page: str,
        start_index: int,
    ) -> list[TestIntent]:
        text = f"{defect_ticket}\n{runtime_logs}".strip()
        if not text:
            return []
        intents: list[TestIntent] = []
        index = start_index
        for token, intent_type in [
            ("timeout", "negative"),
            ("assert", "negative"),
            ("error", "negative"),
            ("unauthorized", "security"),
            ("500", "negative"),
        ]:
            if token in text.lower():
                intents.append(
                    TestIntent(
                        intent_id=f"intent-{index:02d}",
                        title=f"缺陷回归: 处理 {token} 场景",
                        intent_type=intent_type,
                        priority="P0" if token in {"unauthorized", "500"} else "P1",
                        steps_hint=[f"open:{page}", "negative", "assert"],
                        dependencies=[],
                        source_ids=[],
                    )
                )
                index += 1
        if "critical" in text.lower() or "sev1" in text.lower():
            intents.append(
                TestIntent(
                    intent_id=f"intent-{index:02d}",
                    title="缺陷回归: 高严重级别主流程校验",
                    intent_type="regression",
                    priority="P0",
                    steps_hint=[f"open:{page}", "regression", "assert"],
                    dependencies=[],
                    source_ids=[],
                )
            )
        return intents

    @staticmethod
    def _deduplicate_intents(intents: list[TestIntent]) -> list[TestIntent]:
        dedup: list[TestIntent] = []
        seen_titles: dict[str, TestIntent] = {}
        for intent in intents:
            key = intent.title.strip().lower()
            if not key:
                continue
            existing = seen_titles.get(key)
            if existing is None:
                seen_titles[key] = intent
                dedup.append(intent)
                continue
            if existing.priority == "P0":
                existing.source_ids = sorted(set(existing.source_ids + intent.source_ids))
                continue
            if intent.priority == "P0":
                existing.priority = intent.priority
            existing.source_ids = sorted(set(existing.source_ids + intent.source_ids))
        for index, intent in enumerate(dedup, start=1):
            intent.intent_id = f"intent-{index:02d}"
        return dedup

    def _apply_dependency_analysis(self, intents: list[TestIntent]) -> list[TestIntent]:
        first_by_type: dict[str, str] = {}
        base_flow_intent = ""
        for intent in intents:
            if intent.intent_type in {"functional", "api"} and not base_flow_intent:
                base_flow_intent = intent.intent_id
            first_by_type.setdefault(intent.intent_type, intent.intent_id)
        for intent in intents:
            dependencies: list[str] = []
            title = intent.title.lower()
            if (
                intent.intent_type in {"negative", "performance", "security", "regression", "compatibility"}
                and base_flow_intent
                and base_flow_intent != intent.intent_id
            ):
                dependencies.append(base_flow_intent)
            if any(token in title for token in ["删除", "修改", "提交", "审批", "回归", "缺陷回归"]):
                for dep_type in ["functional", "api"]:
                    dep_intent = first_by_type.get(dep_type)
                    if dep_intent and dep_intent != intent.intent_id:
                        dependencies.append(dep_intent)
            if any("login" in step or "鉴权" in title for step in intent.steps_hint):
                dependencies = []
            intent.dependencies = sorted(set(dependencies))
        return intents

    @staticmethod
    def _priority_from_changed_file(file_path: str) -> str:
        lowered = file_path.lower()
        if any(token in lowered for token in CRITICAL_CHANGE_FILE_HINTS):
            return "P0"
        if any(token in lowered for token in ["router", "service", "controller", "api"]):
            return "P1"
        return "P2"

    @staticmethod
    def _build_dependency_graph(intents: list[TestIntent]) -> list[dict[str, Any]]:
        graph = []
        for intent in intents:
            graph.append(
                {
                    "intent_id": intent.intent_id,
                    "depends_on": intent.dependencies,
                }
            )
        return graph

    def _classify_intent_type(self, sentence: str) -> str:
        lowered = sentence.lower()
        if any(token in lowered for token in PERFORMANCE_KEYWORDS):
            return "performance"
        if any(token in lowered for token in SECURITY_KEYWORDS):
            return "security"
        if any(token in lowered for token in COMPATIBILITY_KEYWORDS):
            return "compatibility"
        if any(token in sentence.lower() for token in NEGATIVE_KEYWORDS):
            return "negative"
        if any(token in lowered for token in ["api:", "openapi", "/api/", "http"]):
            return "api"
        return "functional"

    def _extract_steps_hint(self, sentence: str, *, page: str, source_type: str = "text") -> list[str]:
        source_type = self._canonical_source_type(source_type)
        if source_type in {"openapi", "postman"}:
            hints = ["api", "assert"]
        else:
            hints = [f"open:{page or 'target_page'}"]
        for action, keywords in ACTION_KEYWORDS.items():
            if any(keyword in sentence for keyword in keywords):
                hints.append(action)
        if "验证" in sentence or "断言" in sentence:
            hints.append("assert")
        if "性能" in sentence and "performance_probe" not in hints:
            hints.append("performance_probe")
        if any(token in sentence.lower() for token in ["兼容", "浏览器", "设备"]):
            hints.append("cross_browser")
        if any(token in sentence.lower() for token in ["权限", "鉴权", "unauthorized"]):
            hints.append("auth_check")
        if len(hints) == 1:
            hints.extend(["smoke", "assert"])
        return list(dict.fromkeys(hints))

    def _infer_steps_hint(self, title: str, intent_type: str, page: str) -> list[str]:
        source_type = "openapi" if intent_type == "api" else "text"
        return self._extract_steps_hint(title, page=page, source_type=source_type)

    def _infer_priority(
        self,
        text: str,
        *,
        intents: list[TestIntent],
        defect_ticket: str,
        git_diff: str,
        source_inputs: list[RequirementSourceInput],
    ) -> str:
        lowered = text.lower()
        source_types = {self._canonical_source_type(source.source_type) for source in source_inputs}
        changed_files = re.findall(r"\+\+\+\s+b/([^\s]+)", git_diff)
        if any(token in text for token in HIGH_RISK_KEYWORDS):
            return "P0"
        if any(token in lowered for token in ["critical", "sev1", "blocker"]):
            return "P0"
        if defect_ticket and any(token in defect_ticket.lower() for token in ["p0", "sev1", "critical"]):
            return "P0"
        if git_diff and re.search(r"(auth|payment|order|permission|risk)", git_diff, re.IGNORECASE):
            return "P0"
        if changed_files and len(changed_files) >= 10:
            return "P0"
        if {"defect_ticket", "runtime_logs"} & source_types:
            return "P1"
        if any(token in text for token in ["关键", "核心", "主流程", "必须"]):
            return "P1"
        if any(intent.intent_type in {"security", "performance"} for intent in intents):
            return "P1"
        return "P2"

    def _build_coverage_matrix(self, sources: list[RequirementSourceInput], intents: list[TestIntent]) -> list[dict[str, Any]]:
        matrix: list[dict[str, Any]] = []
        for idx, source in enumerate(sources, start=1):
            text = self._read_source_content(source)[:500]
            matched = []
            for intent in intents:
                if source.source_id in intent.source_ids:
                    matched.append(intent.intent_id)
                    continue
                overlap = self._keyword_overlap_score(text, intent.title)
                if overlap >= 0.15:
                    matched.append(intent.intent_id)
            if not matched and intents:
                matched = [intents[min(idx - 1, len(intents) - 1)].intent_id]
            matrix.append(
                {
                    "requirement_id": f"REQ-{idx:03d}",
                    "source_id": source.source_id,
                    "source_type": source.source_type,
                    "requirement_text": text[:200],
                    "intent_ids": matched,
                    "coverage_ratio": round(len(matched) / max(1, len(intents)), 2),
                    "traceability_status": "covered" if matched else "gap",
                }
            )
        return matrix

    @staticmethod
    def _keyword_overlap_score(left: str, right: str) -> float:
        left_tokens = {token for token in re.split(r"[^a-zA-Z0-9\u4e00-\u9fff]+", left.lower()) if token}
        right_tokens = {token for token in re.split(r"[^a-zA-Z0-9\u4e00-\u9fff]+", right.lower()) if token}
        if not left_tokens or not right_tokens:
            return 0.0
        overlap = len(left_tokens & right_tokens)
        return overlap / max(1, len(right_tokens))

    def _extract_business_rules(self, text: str) -> list[BusinessRule]:
        rules: list[BusinessRule] = []
        for rule_type, pattern in RULE_PATTERNS:
            for matched in re.findall(pattern, text):
                value = matched.strip(" ，,。；;")
                if not value:
                    continue
                rules.append(
                    BusinessRule(
                        rule_id=f"rule-{len(rules)+1:02d}",
                        rule_text=value[:120],
                        rule_type=rule_type,
                        confidence=0.86,
                    )
                )
        for matched in re.findall(r"(?:\bP\d{1,2}\b|sev\d|critical|high|medium|low)", text, re.IGNORECASE):
            rules.append(
                BusinessRule(
                    rule_id=f"rule-{len(rules)+1:02d}",
                    rule_text=f"风险等级约束: {matched}",
                    rule_type="risk",
                    confidence=0.75,
                )
            )
        dedup: dict[tuple[str, str], BusinessRule] = {}
        for rule in rules:
            key = (rule.rule_type, rule.rule_text)
            if key not in dedup:
                dedup[key] = rule
        result = list(dedup.values())
        for index, rule in enumerate(result, start=1):
            rule.rule_id = f"rule-{index:02d}"
        return result

    def _detect_ambiguities(self, text: str) -> list[AmbiguityItem]:
        results: list[AmbiguityItem] = []
        fragments = self._split_sentences(text)
        for fragment in fragments:
            if any(token in fragment for token in AMBIGUOUS_KEYWORDS):
                results.append(
                    AmbiguityItem(
                        item_id=f"amb-{len(results)+1:02d}",
                        text=fragment[:120],
                        reason="需求描述存在模糊词，可能导致测试点不稳定。",
                        suggestion="请补充明确的输入条件、阈值和可验证结果。",
                        severity="medium",
                    )
                )
        if "性能" in text and not re.search(r"\d+\s*(ms|秒|s|qps|并发)", text, re.IGNORECASE):
            results.append(
                AmbiguityItem(
                    item_id=f"amb-{len(results)+1:02d}",
                    text="性能目标缺少量化指标",
                    reason="性能测试要求未给出可执行阈值。",
                    suggestion="补充响应时间、吞吐或并发目标，例如 P95 < 500ms。",
                    severity="high",
                )
            )
        if "必须" in text and "可选" in text:
            results.append(
                AmbiguityItem(
                    item_id=f"amb-{len(results)+1:02d}",
                    text="同一需求同时出现“必须/可选”表达",
                    reason="强制约束与可选约束冲突，无法稳定判定优先级。",
                    suggestion="请明确哪些场景是强制，哪些是增量优化。",
                    severity="high",
                )
            )
        if not any(token in text for token in ["验证", "断言", "期望", "结果", "应当"]):
            results.append(
                AmbiguityItem(
                    item_id=f"amb-{len(results)+1:02d}",
                    text="需求缺少可验证结果描述",
                    reason="无法提取明确断言条件，可能导致生成用例可执行但不可判定。",
                    suggestion="补充“输入-动作-预期结果”三段式描述。",
                    severity="medium",
                )
            )
        return results

    def _analyze_change_impact(self, *, git_diff: str, intents: list[TestIntent], inferred_page: str) -> dict[str, Any]:
        if not git_diff.strip():
            return {
                "changed_modules": [],
                "affected_intent_ids": [],
                "suggested_regression_scope": [inferred_page],
                "risk_hint": "no_git_diff",
                "impact_score": 0,
                "changed_areas": [],
            }
        changed_files = re.findall(r"\+\+\+\s+b/([^\s]+)", git_diff)
        changed_modules = sorted({file_path.split("/")[0] for file_path in changed_files if file_path})
        changed_areas = sorted(
            {
                self._classify_change_area(file_path)
                for file_path in changed_files
                if file_path
            }
        )
        affected_ids = []
        lowered_diff = git_diff.lower()
        for intent in intents:
            title = intent.title.lower()
            if any(token in lowered_diff for token in re.split(r"[^a-z0-9\u4e00-\u9fff]+", title) if token):
                affected_ids.append(intent.intent_id)
                continue
            if intent.intent_type == "regression" and any(file_path.lower().endswith(".py") for file_path in changed_files):
                affected_ids.append(intent.intent_id)
        if not affected_ids:
            affected_ids = [intent.intent_id for intent in intents[: min(3, len(intents))]]
        high_risk_change = len(changed_files) >= 8 or any("security" in item for item in changed_modules)
        risk_hint = "high_change_risk" if high_risk_change else "normal_change_risk"
        impact_score = min(100, len(changed_files) * 8 + (20 if high_risk_change else 0) + (10 if "backend" in changed_areas else 0))
        return {
            "changed_modules": changed_modules,
            "changed_files": changed_files[:50],
            "affected_intent_ids": affected_ids,
            "suggested_regression_scope": sorted(set(changed_modules + [inferred_page])),
            "risk_hint": risk_hint,
            "impact_score": impact_score,
            "changed_areas": changed_areas,
        }

    @staticmethod
    def _classify_change_area(file_path: str) -> str:
        lowered = file_path.lower()
        if "/tests/" in lowered or lowered.startswith("tests/"):
            return "test"
        if "/ui/" in lowered or "/frontend/" in lowered or lowered.endswith((".tsx", ".ts", ".jsx", ".js", ".css", ".html")):
            return "frontend"
        if lowered.endswith((".yaml", ".yml", ".json", ".toml")):
            return "config"
        return "backend"

    def _extract_historical_patterns(self, *, intents: list[TestIntent], page: str) -> list[dict[str, Any]]:
        if not self.report_root.exists():
            return []
        patterns: dict[str, dict[str, Any]] = {}
        intent_type_counter: dict[str, int] = {}
        report_files = sorted(self.report_root.glob("*.report.json"), key=lambda path: path.stat().st_mtime, reverse=True)[:200]
        for path in report_files:
            try:
                payload = path.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                report = json.loads(payload)
            except Exception:
                continue
            if not isinstance(report, dict):
                continue
            report_page = str(report.get("page", "")).strip()
            if page and report_page and report_page != page:
                continue
            category = str((report.get("failure_analysis") or {}).get("failure_category", "unknown")).strip().lower() or "unknown"
            entry = patterns.setdefault(
                category,
                {"pattern": category, "count": 0, "sample_case_ids": []},
            )
            entry["count"] = int(entry["count"]) + 1
            intent_type = str((report.get("execution_record") or {}).get("mode", "")).strip().lower()
            if intent_type:
                intent_type_counter[intent_type] = intent_type_counter.get(intent_type, 0) + 1
            case_id = str(report.get("case_id", "")).strip()
            if case_id and len(entry["sample_case_ids"]) < 5:
                entry["sample_case_ids"].append(case_id)
        rows = sorted(patterns.values(), key=lambda item: int(item.get("count", 0)), reverse=True)
        if intents:
            rows.append(
                {
                    "pattern": "intent_mix",
                    "count": len(intents),
                    "sample_case_ids": [],
                    "intent_types": sorted({intent.intent_type for intent in intents}),
                }
            )
        if intent_type_counter:
            rows.append(
                {
                    "pattern": "historical_execution_mode",
                    "count": sum(intent_type_counter.values()),
                    "distribution": intent_type_counter,
                    "sample_case_ids": [],
                }
            )
        return rows[:10]

    @staticmethod
    def _build_design_input(
        *,
        raw_requirement: str,
        intents: list[TestIntent],
        priority: str,
        business_rules: list[BusinessRule],
        ambiguities: list[AmbiguityItem],
    ) -> str:
        lines = [
            f"原始需求: {raw_requirement}",
            f"整体优先级: {priority}",
            "结构化测试点:",
        ]
        for intent in intents:
            source_ref = ",".join(intent.source_ids) if intent.source_ids else "-"
            lines.append(
                f"- [{intent.intent_id}]({intent.intent_type}/{intent.priority}) {intent.title}; steps={','.join(intent.steps_hint)}; deps={','.join(intent.dependencies) or '-'}; sources={source_ref}"
            )
        if business_rules:
            lines.append("业务规则:")
            for rule in business_rules[:8]:
                lines.append(f"- [{rule.rule_type}] {rule.rule_text}")
        if ambiguities:
            lines.append("需求消歧提示:")
            for item in ambiguities[:6]:
                lines.append(f"- [{item.severity}] {item.text} -> {item.suggestion}")
        lines.append("请基于以上测试点生成稳定可执行 YAML。")
        return "\n".join(lines)

    @staticmethod
    def _estimate_parse_confidence(
        *,
        source_count: int,
        entities: list[RequirementEntity],
        intents: list[TestIntent],
        ambiguities: list[AmbiguityItem],
    ) -> float:
        base = 0.55
        base += min(0.2, source_count * 0.05)
        base += min(0.15, len(entities) * 0.01)
        base += min(0.15, len(intents) * 0.015)
        base -= min(0.2, len(ambiguities) * 0.04)
        return round(max(0.2, min(0.95, base)), 2)

    def _append_parse_evaluation_log(self, parsed_result: dict[str, Any]) -> None:
        if not isinstance(parsed_result, dict):
            return
        parser_runtime = parsed_result.get("parser_runtime")
        runtime = parser_runtime if isinstance(parser_runtime, dict) else {}
        llm_trace = runtime.get("llm_trace")
        llm = llm_trace if isinstance(llm_trace, dict) else {}
        intents = parsed_result.get("test_intents")
        ambiguities = parsed_result.get("ambiguities")
        source_inputs = parsed_result.get("source_inputs")
        coverage_matrix = parsed_result.get("coverage_matrix")

        intent_count = len(intents) if isinstance(intents, list) else 0
        ambiguity_count = len(ambiguities) if isinstance(ambiguities, list) else 0
        source_count = len(source_inputs) if isinstance(source_inputs, list) else 0
        coverage_count = len(coverage_matrix) if isinstance(coverage_matrix, list) else 0
        try:
            parse_confidence = float(parsed_result.get("parse_confidence") or 0.0)
        except Exception:
            parse_confidence = 0.0
        quality_decision = "allow"
        quality_reasons: list[str] = []
        if intent_count < 1:
            quality_decision = "needs_review"
            quality_reasons.append("insufficient_test_intents")
        if parse_confidence < 0.6:
            quality_decision = "needs_review"
            quality_reasons.append("low_parse_confidence")
        if ambiguity_count > 3:
            quality_decision = "needs_review"
            quality_reasons.append("high_ambiguity_count")

        event = {
            "event_type": "requirement_parse_evaluation",
            "timestamp": datetime.now(UTC).isoformat(),
            "page": str(parsed_result.get("page", "")).strip(),
            "source_type": str(parsed_result.get("source_type", "")).strip() or "text",
            "priority": str(parsed_result.get("priority", "")).strip() or "P1",
            "source_count": source_count,
            "intent_count": intent_count,
            "ambiguity_count": ambiguity_count,
            "coverage_count": coverage_count,
            "parse_confidence": round(parse_confidence, 2),
            "quality_decision": quality_decision,
            "quality_reasons": quality_reasons,
            "parser_runtime": {
                "mode": str(runtime.get("mode", "")).strip() or "rule_based",
                "model": str(runtime.get("model", "")).strip() or "rule-engine",
                "prompt_version": str(runtime.get("prompt_version", "")).strip() or "unknown",
                "instructions_version": str(runtime.get("instructions_version", "")).strip() or "unknown",
                "parse_duration_ms": int(runtime.get("parse_duration_ms", 0) or 0),
            },
            "llm_trace": {
                "attempted": bool(llm.get("attempted", False)),
                "succeeded": bool(llm.get("succeeded", False)),
                "fallback_used": bool(llm.get("fallback_used", False)),
                "reason_code": str(llm.get("reason_code", "")).strip(),
                "latency_ms": int(llm.get("latency_ms", 0) or 0),
                "prompt_tokens": llm.get("prompt_tokens"),
                "completion_tokens": llm.get("completion_tokens"),
                "total_tokens": llm.get("total_tokens"),
                "overlay_key_count": int(llm.get("overlay_key_count", 0) or 0),
            },
        }
        try:
            self.telemetry_root.mkdir(parents=True, exist_ok=True)
            with self.requirement_parse_eval_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            return
