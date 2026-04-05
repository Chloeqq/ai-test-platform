# mypy: ignore-errors

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from datetime_compat import UTC
from shared_backend.observability import build_ai_trace_context


class RequirementParseSupport:
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
            pythonpath_entries = [str(self._repo_root), str(self._requirement_parser_root)]
            existing_pythonpath = str(os.environ.get("PYTHONPATH", "")).strip()
            if existing_pythonpath:
                pythonpath_entries.append(existing_pythonpath)
            env = dict(os.environ)
            env["PYTHONPATH"] = os.pathsep.join(entry for entry in pythonpath_entries if entry)
            completed = subprocess.run(
                [sys.executable, "-m", "src.index", "--input", str(temp_path)],
                cwd=str(self._requirement_parser_root),
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "requirement parser failed")
            parsed = json.loads(completed.stdout.strip() or "{}")
            if not isinstance(parsed, dict):
                raise RuntimeError("requirement parser returned non-object payload")
            if not isinstance(parsed.get("parser_runtime"), dict):
                parsed["parser_runtime"] = self.build_requirement_parser_runtime_fallback(
                    source="subprocess",
                    detail="missing parser_runtime in parser output",
                )
            supplemental_context = self._build_fallback_multisource_context(
                input_sources=input_sources,
                openapi_spec=openapi_spec,
                openapi_url=openapi_url,
                git_diff=git_diff,
                git_diff_path=git_diff_path,
                defect_ticket=defect_ticket,
            )
            return self._harmonize_requirement_spec(
                requirement_spec=parsed,
                source=source,
                requirement=requirement,
                fallback_context=supplemental_context,
            )
        except Exception:
            normalized = requirement.strip()
            fallback_context = self._build_fallback_multisource_context(
                input_sources=input_sources,
                openapi_spec=openapi_spec,
                openapi_url=openapi_url,
                git_diff=git_diff,
                git_diff_path=git_diff_path,
                defect_ticket=defect_ticket,
            )
            resolved_page = page or self._infer_page_from_text(
                requirement=requirement,
                prd_text=prd_text,
                user_story=user_story,
                git_diff=git_diff,
                defect_ticket=defect_ticket,
                runtime_logs=runtime_logs,
                openapi_spec=openapi_spec,
                input_sources=input_sources,
            )
            ranked_candidates = self._rank_page_candidates(
                fallback_context=fallback_context,
                source_inputs=input_sources or [],
                current_page=page or resolved_page,
            )
            if not page and ranked_candidates:
                resolved_page = str(ranked_candidates[0].get("page", "")).strip() or resolved_page
            design_input_rows = [
                str(item).strip()
                for item in [
                    requirement,
                    normalized,
                    prd_text,
                    user_story,
                    *fallback_context["design_input_fragments"],
                ]
                if str(item).strip()
            ]
            source_inputs = fallback_context["source_inputs"]
            test_intents: list[dict[str, Any]] = [
                {
                    "intent_id": "intent-01",
                    "title": normalized[:80] or "基础流程验证",
                    "intent_type": "functional",
                    "priority": "P1",
                    "steps_hint": ["smoke", "assert"],
                    "dependencies": [],
                    "source_ids": [str(item.get("source_type", "")).strip() for item in source_inputs if isinstance(item, dict)],
                }
            ]
            if isinstance(openapi_spec, dict) and openapi_spec:
                test_intents.append(
                    {
                        "intent_id": "intent-api-01",
                        "title": "关键 API 契约与页面交互保持一致",
                        "intent_type": "api",
                        "priority": "P1",
                        "steps_hint": ["api", "assert"],
                        "dependencies": [],
                        "source_ids": ["openapi"],
                    }
                )
            if fallback_context["changed_files"] or defect_ticket.strip():
                test_intents.append(
                    {
                        "intent_id": "intent-regression-01",
                        "title": "变更影响范围需要纳入回归验证",
                        "intent_type": "regression",
                        "priority": "P1",
                        "steps_hint": ["regression", "assert"],
                        "dependencies": [],
                        "source_ids": ["git_diff" if fallback_context["changed_files"] else "defect_ticket"],
                    }
                )
            ambiguities: list[dict[str, Any]] = []
            if runtime_logs.strip():
                ambiguities.append(
                    {
                        "field": "runtime_logs",
                        "reason": runtime_logs[:160],
                        "severity": "medium",
                    }
                )
            fallback_spec = {
                "version": "RequirementSpecV1",
                "source_type": source,
                "page": resolved_page,
                "raw_requirement": requirement,
                "normalized_requirement": normalized,
                "source_inputs": source_inputs,
                "entities": [],
                "test_intents": test_intents,
                "coverage_matrix": [
                    {
                        "requirement_id": "REQ-001",
                        "requirement_text": (normalized or " / ".join(design_input_rows))[:200],
                        "intent_ids": [str(item.get("intent_id", "")).strip() for item in test_intents if isinstance(item, dict)],
                        "coverage_ratio": 1.0,
                        "traceability_status": "covered",
                    }
                ],
                "dependency_graph": [
                    {"intent_id": str(item.get("intent_id", "")).strip(), "depends_on": []}
                    for item in test_intents
                    if isinstance(item, dict)
                ],
                "business_rules": fallback_context["business_rules"],
                "ambiguities": ambiguities,
                "change_impact": {
                    "changed_modules": fallback_context["changed_modules"],
                    "changed_files": fallback_context["changed_files"],
                    "affected_intent_ids": [str(item.get("intent_id", "")).strip() for item in test_intents if isinstance(item, dict)],
                    "suggested_regression_scope": [resolved_page],
                    "risk_hint": "fallback",
                    "changed_areas": fallback_context["changed_modules"],
                    "impact_score": min(100, 20 + len(fallback_context["changed_files"]) * 10 + len(test_intents) * 5),
                },
                "historical_patterns": [],
                "priority": "P1",
                "design_input": " / ".join(design_input_rows[:8]) or "基础流程验证",
                "field_definitions": [],
                "parameter_constraints": fallback_context["parameter_constraints"],
                "parse_confidence": 0.78 if source_inputs else (0.72 if normalized else 0.5),
                "parser_runtime": self.build_requirement_parser_runtime_fallback(
                    source="orchestrator_fallback",
                    detail="requirement parser subprocess failed; fallback spec used",
                ),
            }
            return self._harmonize_requirement_spec(
                requirement_spec=fallback_spec,
                source=source,
                requirement=requirement,
                fallback_context=fallback_context,
            )

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
        return "product"

    @staticmethod
    def build_requirement_parser_runtime_fallback(*, source: str, detail: str) -> dict[str, Any]:
        runtime = {
            "agent": "requirement-parser-agent",
            "pipeline": "requirement->test_points",
            "generated_at": datetime.now(UTC).isoformat(),
            "mode": "rule_based",
            "llm_enabled": False,
            "model": "rule-engine",
            "prompt_name": "requirement-parser-system",
            "prompt_version": "requirement-parser.prompt.unknown",
            "prompt_fingerprint": "",
            "instructions_version": "requirement-parser.instructions.unknown",
            "source": source,
            "detail": detail,
            "llm_trace": {
                "attempted": False,
                "succeeded": False,
                "fallback_used": True,
                "reason_code": "fallback_rule_based",
                "latency_ms": 0,
                "overlay_key_count": 0,
                "total_tokens": 0,
            },
        }
        runtime["ai_trace"] = build_ai_trace_context(
            page="common",
            prompt_version=str(runtime.get("prompt_version", "")).strip(),
            model=str(runtime.get("model", "")).strip(),
            source=source,
            fallback_used=True,
            fallback_reason="fallback_rule_based",
            instructions_version=str(runtime.get("instructions_version", "")).strip(),
        )
        runtime["trace_id"] = runtime["ai_trace"]["trace_id"]
        return runtime
