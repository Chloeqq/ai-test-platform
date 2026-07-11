# mypy: ignore-errors
"""编排核心服务：协调多 Agent、质量门、执行、报告与失败自愈。"""

import os
import re
import subprocess
import sys
import json
import logging

_logger = logging.getLogger(__name__)
import importlib.util
from datetime_compat import UTC
from datetime import datetime
from dataclasses import asdict, dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any
import yaml

from services.execution_report_support import ExecutionReportSupport
from services.multisource_support import MultisourceSupport
from services.analytics_query_support import AnalyticsQuerySupport
from services.agent_execution_support import AgentExecutionSupport
from services.failure_healing_support import FailureHealingSupport
from services.orchestration_flow_support import OrchestrationFlowSupport
from services.requirement_parse_support import RequirementParseSupport
from services.requirement_testpoint_support import RequirementTestPointSupport
from services.runner_registry_support import RunnerRegistrySupport
from shared_backend.observability import build_ai_trace_context


class OrchestratorError(Exception):
    """编排层可预期错误，携带 HTTP 状态码与结构化 error 载荷。"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = int(status_code)
        self.details = details or {}

    def to_response(self) -> dict[str, Any]:
        payload = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.details:
            payload["error"]["details"] = self.details
        return payload


class OrchestratorValidationError(OrchestratorError):
    """请求参数或业务校验失败（422）。"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code="validation_error",
            message=message,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            details=details,
        )


class RunnerExecutionError(OrchestratorError):
    """测试 Runner 执行失败（502）。"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code="runner_failed",
            message=message,
            status_code=HTTPStatus.BAD_GATEWAY,
            details=details,
        )


@dataclass
class OrchestrationResult:
    """单次 orchestrate 调用的完整产物（规格、用例、执行与报告路径）。"""

    requirement_spec: dict[str, Any]
    case: dict[str, Any]
    generated_script: dict[str, Any]
    execution_plan: dict[str, Any]
    design_generation: dict[str, Any]
    risk_report: dict[str, Any]
    failure_triage: dict[str, Any]
    agent_pipeline: list[str]
    test_points: dict[str, Any]
    execution_record: dict[str, Any]
    case_path: str
    execution_requested: bool
    runner_exit_code: int | None = None
    runner_stdout: str = ""
    runner_stderr: str = ""
    report: dict[str, Any] | None = None
    report_json_path: str = ""
    report_markdown_path: str = ""
    report_summary_path: str = ""


class OrchestratorService:
    """AI 测试编排门面：组合各领域 Support 类完成端到端流程。"""

    ALLOWED_SOURCES = {"manual", "ai", "regression"}
    # 需求质量门阻断项与告警码映射
    REQUIREMENT_QUALITY_BLOCKER_CATALOG: dict[str, dict[str, str]] = {
        "insufficient_test_intents": {
            "category": "coverage",
            "severity": "high",
            "alert_code": "REQQG_INTENTS_LOW",
            "metric_key": "intent_count",
        },
        "low_parse_confidence": {
            "category": "quality",
            "severity": "high",
            "alert_code": "REQQG_CONFIDENCE_LOW",
            "metric_key": "parse_confidence",
        },
        "high_ambiguity_present": {
            "category": "ambiguity",
            "severity": "high",
            "alert_code": "REQQG_AMBIGUITY_HIGH",
            "metric_key": "high_ambiguity_count",
        },
        "coverage_gap_ratio_high": {
            "category": "coverage",
            "severity": "medium",
            "alert_code": "REQQG_COVERAGE_GAP_HIGH",
            "metric_key": "coverage_gap_ratio",
        },
        "missing_design_input": {
            "category": "input",
            "severity": "critical",
            "alert_code": "REQQG_DESIGN_INPUT_MISSING",
            "metric_key": "has_design_input",
        },
        "missing_page_resolution": {
            "category": "input",
            "severity": "critical",
            "alert_code": "REQQG_PAGE_MISSING",
            "metric_key": "has_page",
        },
    }

    def __init__(self, repo_root: Path | None = None):
        """初始化仓库路径、Agent 根目录与各领域 Support 依赖注入。"""
        self.repo_root = repo_root or Path(__file__).resolve().parents[3]
        self.apps_root = self.repo_root / "apps"
        # Dev convenience: in Docker the PYTHONPATH is set; this fallback
        # ensures the service is runnable from the repo checkout directly.
        if str(self.apps_root) not in sys.path:
            sys.path.insert(0, str(self.apps_root))
        self.requirement_parser_root = self.repo_root / "agents" / "requirement-parser-agent"
        self.agent_root = self.repo_root / "agents" / "test-design-agent"
        self.script_generation_root = self.repo_root / "agents" / "script-generation-agent"
        self.execution_planner_root = self.repo_root / "agents" / "execution-planner-agent"
        self.risk_evaluation_root = self.repo_root / "agents" / "risk-evaluation-agent"
        self.failure_triage_root = self.repo_root / "agents" / "failure-triage-agent"
        self.failure_agent_root = self.repo_root / "agents" / "failure-analysis-agent"
        self.self_healing_agent_root = self.repo_root / "agents" / "self-healing-advisor-agent" / "src"
        self.runner_root = self.repo_root / "runners" / "web-playwright-python"
        self.generated_cases_root = self.repo_root / "assets" / "test-cases" / "ai-generated"
        self.report_root = self.repo_root / "reports" / "executions"
        self.telemetry_root = self.repo_root / "reports" / "telemetry"
        self.requirement_parse_telemetry_log = self.telemetry_root / "requirement-parse-events.jsonl"
        self.generated_scripts_root = self.report_root / "generated-scripts"
        self.schemas_root = self.repo_root / "apps" / "ai-orchestrator" / "src" / "schemas"
        self.tools_root = self.repo_root / "apps" / "ai-orchestrator" / "src" / "tools"
        self._runtime_module_cache: dict[str, Any] = {}
        self.requirement_quality_gate_enabled = self._env_bool(
            "REQUIREMENT_QUALITY_GATE_ENABLED",
            default=True,
        )
        self.requirement_min_parse_confidence = self._env_float(
            "REQUIREMENT_MIN_PARSE_CONFIDENCE",
            default=0.6,
        )
        self.requirement_min_test_intents = self._env_int(
            "REQUIREMENT_MIN_TEST_INTENTS",
            default=3,
        )
        self.requirement_block_high_ambiguity = self._env_bool(
            "REQUIREMENT_BLOCK_HIGH_AMBIGUITY",
            default=True,
        )
        self.requirement_max_coverage_gap_ratio = self._env_float(
            "REQUIREMENT_MAX_COVERAGE_GAP_RATIO",
            default=0.5,
        )
        self.logger = logging.getLogger(__name__)
        self._runner_registry_support = RunnerRegistrySupport(repo_root=self.repo_root)
        self._multisource_support = MultisourceSupport(
            load_runtime_module=self._load_runtime_module,
            infer_page_from_text=self._infer_page_from_text,
            build_source_id=self._build_source_id,
            slug_token=self._slug_token,
            dedup_strings=self._dedup_strings,
            logger=self.logger,
            tools_root=self.tools_root,
        )
        self._execution_report_support = ExecutionReportSupport(
            ensure_runner_import_path=self._ensure_runner_import_path,
            normalize_execution_record=self._normalize_execution_record,
            normalize_evidence_manifest=self._normalize_evidence_manifest,
            ensure_change_impact_explainability=self._ensure_change_impact_explainability,
            build_summary_text=self._build_summary_text,
            extract_runner_metrics=self._extract_runner_metrics,
            build_pytest_results=self._build_pytest_results,
            extract_failure_reason=self._extract_failure_reason,
            analyze_failure=self._analyze_failure,
            triage_failure=self._triage_failure,
            enrich_failure_triage_with_history=self._enrich_failure_triage_with_history,
            build_self_healing_advice=self._build_self_healing_advice,
            load_self_healing_suggestion_preview=self._load_self_healing_suggestion_preview,
            load_self_healing_execution_preview=self._load_self_healing_execution_preview,
            evaluate_risk_report=self._evaluate_risk_report,
            agent_pipeline_order=self.agent_pipeline_order,
            logger=self.logger,
            runner_root=self.runner_root,
        )
        self._analytics_query_support = AnalyticsQuerySupport(
            now=self._now,
            iter_recent_reports=self._iter_recent_reports,
            load_self_healing_suggestion_preview=self._load_self_healing_suggestion_preview,
            load_report_summary_preview=self._load_report_summary_preview,
            get_report_root=lambda: self.report_root,
            get_runner_root=lambda: self.runner_root,
            get_requirement_parse_telemetry_log=lambda: self.requirement_parse_telemetry_log,
        )
        self._failure_healing_support = FailureHealingSupport(
            now=self._now,
            iter_recent_reports=self._iter_recent_reports,
            run_failure_analysis_agent=lambda payload: self._run_failure_analysis_agent(payload),
            run_self_healing_advisor_agent=lambda payload: self._run_self_healing_advisor_agent(payload),
            load_available_targets=lambda page_name: self._load_available_targets(page_name),
            risk_evaluation_root=self.risk_evaluation_root,
            failure_triage_root=self.failure_triage_root,
        )
        self._requirement_parse_support = RequirementParseSupport(
            repo_root=self.repo_root,
            requirement_parser_root=self.requirement_parser_root,
            build_fallback_multisource_context=self._build_fallback_multisource_context,
            harmonize_requirement_spec=self._harmonize_requirement_spec,
            infer_page_from_text=self._infer_page_from_text,
            rank_page_candidates=self._rank_page_candidates,
        )
        self._requirement_testpoint_support = RequirementTestPointSupport(
            now=self._now,
            normalize_test_point_plan=self._normalize_test_point_plan,
            build_test_point_traceability_summary=self._build_test_point_traceability_summary,
            agent_root=self.agent_root,
            requirement_quality_gate_enabled=self.requirement_quality_gate_enabled,
            requirement_min_parse_confidence=self.requirement_min_parse_confidence,
            requirement_min_test_intents=self.requirement_min_test_intents,
            requirement_block_high_ambiguity=self.requirement_block_high_ambiguity,
            requirement_max_coverage_gap_ratio=self.requirement_max_coverage_gap_ratio,
            blocker_catalog=self.REQUIREMENT_QUALITY_BLOCKER_CATALOG,
        )
        self._agent_execution_support = AgentExecutionSupport(
            agent_root=self.agent_root,
            script_generation_root=self.script_generation_root,
            execution_planner_root=self.execution_planner_root,
            generated_scripts_root=self.generated_scripts_root,
            repo_root=self.repo_root,
        )
        self._orchestration_flow_support = OrchestrationFlowSupport(
            orchestration_result_cls=OrchestrationResult,
            validation_error_cls=OrchestratorValidationError,
            runner_execution_error_cls=RunnerExecutionError,
            allowed_sources=self.ALLOWED_SOURCES,
            now=self._now,
            resolve_runner_profile=self._resolve_runner_profile,
            parse_requirement_spec=lambda **kwargs: self._parse_requirement_spec(**kwargs),
            enforce_requirement_quality_gate=lambda requirement_spec, stage: self._enforce_requirement_quality_gate(
                requirement_spec,
                stage=stage,
            ),
            record_requirement_parse_telemetry=lambda **kwargs: self._record_requirement_parse_telemetry(**kwargs),
            generate_case=lambda **kwargs: self._generate_case(**kwargs),
            build_design_generation=lambda case: self._build_design_generation(case),
            merge_case_requirements=lambda raw_requirement, requirement_spec: self._merge_case_requirements(
                raw_requirement,
                requirement_spec,
            ),
            build_test_points_preview=lambda **kwargs: self._build_test_points_preview(**kwargs),
            resolve_page_object=lambda project, page: self._resolve_page_object(project=project, page=page),
            prepare_generated_case_for_assets=lambda case: self._prepare_generated_case_for_assets(case),
            save_case=lambda case: self._save_case(case),
            agent_pipeline_order=self.agent_pipeline_order,
            build_execution_record=lambda **kwargs: self._build_execution_record(**kwargs),
            empty_evidence_manifest=self._empty_evidence_manifest,
            build_execution_record_metadata=lambda **kwargs: self._build_execution_record_metadata(**kwargs),
            snapshot_evidence_files=self._snapshot_evidence_files,
            run_case=lambda case_id, case_path: self._run_case(case_id, case_path),
            build_evidence_manifest=lambda before, after: self._build_evidence_manifest(before, after),
            build_and_save_report=lambda **kwargs: self._build_and_save_report(**kwargs),
            build_report_summary_path=self._build_report_summary_path,
        )

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        """
        从环境变量读取一个开关,判断它开还是关
        :param name:
        :param default:
        :return:
        """
        raw = os.getenv(name)
        # 如果根本没有这个变量，就用默认值
        if raw is None:
            return default
        # 如果有，看它的值是不是"开"的意思
        # "1", "true", "yes", "on" 都算开（True）
        # 其他所有值都算关（False）
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        # 去环境变量里找这个名字的值
        raw = os.getenv(name)
        # 找不到，用默认值
        if raw is None:
            return default
        try:
            # 找到了，尝试把它转成小数
            return float(str(raw).strip())
        except (TypeError, ValueError):
            # 转失败了（比如值是"abc"），也用默认值
            return default

    def _load_runtime_module(self, *, cache_key: str, module_path: Path) -> Any:
        cached = self._runtime_module_cache.get(cache_key)
        if cached is not None:
            return cached
        resolved = module_path.resolve()
        repo_root = Path(__file__).resolve().parents[3]
        if not str(resolved).startswith(str(repo_root)):
            raise ImportError(f"module path escapes repository root: {resolved}")
        if not resolved.exists():
            raise FileNotFoundError(f"module file not found: {resolved}")
        self.logger.debug("dynamic-loading module %s from %s", cache_key, resolved)
        spec = importlib.util.spec_from_file_location(cache_key, str(resolved))
        if spec is None or spec.loader is None:
            raise ImportError(f"unable to load module spec: {resolved}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._runtime_module_cache[cache_key] = module
        return module

    def _build_fallback_multisource_context(
        self,
        *,
        input_sources: list[dict[str, Any]] | None = None,
        openapi_spec: dict[str, Any] | None = None,
        openapi_url: str = "",
        git_diff: str = "",
        git_diff_path: str = "",
        defect_ticket: str = "",
    ) -> dict[str, Any]:
        return self._multisource_support.build_fallback_multisource_context(
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            openapi_url=openapi_url,
            git_diff=git_diff,
            git_diff_path=git_diff_path,
            defect_ticket=defect_ticket,
        )

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return int(str(raw).strip())
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _slug_token(value: Any, *, default: str = "item") -> str:
        text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
        return text or default

    def _build_source_id(self, *, source_type: str, hint: str, index: int) -> str:
        normalized_type = self._slug_token(source_type, default="source")
        normalized_hint = self._slug_token(hint, default=f"{normalized_type}-{index:02d}")
        return f"{normalized_type}.{normalized_hint}"

    def _normalize_multisource_source_inputs(
        self,
        source_inputs: list[dict[str, Any]] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
        return self._multisource_support.normalize_multisource_source_inputs(source_inputs)

    @staticmethod
    def _dedup_strings(values: list[Any]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for item in values:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    def _rank_page_candidates(
        self,
        *,
        fallback_context: dict[str, Any],
        source_inputs: list[dict[str, Any]],
        current_page: str = "",
    ) -> list[dict[str, Any]]:
        return self._multisource_support.rank_page_candidates(
            fallback_context=fallback_context,
            source_inputs=source_inputs,
            current_page=current_page,
        )

    def _resolve_source_ids(
        self,
        *,
        raw_source_ids: list[Any] | None,
        source_ids_by_type: dict[str, list[str]],
        fallback_types: list[str] | None = None,
        fallback_to_all: bool = False,
    ) -> list[str]:
        return self._multisource_support.resolve_source_ids(
            raw_source_ids=raw_source_ids,
            source_ids_by_type=source_ids_by_type,
            fallback_types=fallback_types,
            fallback_to_all=fallback_to_all,
        )

    def _normalize_business_rules(
        self,
        *,
        business_rules: list[dict[str, Any]] | None,
        source_ids_by_type: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        return self._multisource_support.normalize_business_rules(
            business_rules=business_rules,
            source_ids_by_type=source_ids_by_type,
        )

    def _normalize_test_intents_for_multisource(
        self,
        *,
        intents: list[dict[str, Any]] | None,
        source_ids_by_type: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        return self._multisource_support.normalize_test_intents_for_multisource(
            intents=intents,
            source_ids_by_type=source_ids_by_type,
        )

    def _normalize_coverage_matrix_for_multisource(
        self,
        *,
        coverage_matrix: list[dict[str, Any]] | None,
        test_intents: list[dict[str, Any]],
        source_ids_by_type: dict[str, list[str]],
        requirement_text: str,
    ) -> list[dict[str, Any]]:
        return self._multisource_support.normalize_coverage_matrix_for_multisource(
            coverage_matrix=coverage_matrix,
            test_intents=test_intents,
            source_ids_by_type=source_ids_by_type,
            requirement_text=requirement_text,
        )

    def _normalize_change_impact_for_multisource(
        self,
        *,
        change_impact: dict[str, Any] | None,
        fallback_context: dict[str, Any],
        test_intents: list[dict[str, Any]],
        source_ids_by_type: dict[str, list[str]],
    ) -> dict[str, Any]:
        return self._multisource_support.normalize_change_impact_for_multisource(
            change_impact=change_impact,
            fallback_context=fallback_context,
            test_intents=test_intents,
            source_ids_by_type=source_ids_by_type,
        )

    def _ensure_change_impact_explainability(self, change_impact: dict[str, Any] | None) -> dict[str, Any]:
        return self._multisource_support.ensure_change_impact_explainability(change_impact)

    def _build_page_resolution_summary(
        self,
        *,
        page: str,
        fallback_context: dict[str, Any],
        source_inputs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._multisource_support.build_page_resolution_summary(
            page=page,
            fallback_context=fallback_context,
            source_inputs=source_inputs,
        )

    def _harmonize_requirement_spec(
        self,
        *,
        requirement_spec: dict[str, Any],
        source: str,
        requirement: str,
        fallback_context: dict[str, Any],
    ) -> dict[str, Any]:
        spec = dict(requirement_spec) if isinstance(requirement_spec, dict) else {}
        normalized_source_inputs, source_ids_by_type = self._normalize_multisource_source_inputs(
            spec.get("source_inputs") if isinstance(spec.get("source_inputs"), list) else fallback_context.get("source_inputs")
        )
        spec["source_inputs"] = normalized_source_inputs
        spec["test_intents"] = self._normalize_test_intents_for_multisource(
            intents=spec.get("test_intents") if isinstance(spec.get("test_intents"), list) else [],
            source_ids_by_type=source_ids_by_type,
        )
        spec["business_rules"] = self._normalize_business_rules(
            business_rules=spec.get("business_rules") if isinstance(spec.get("business_rules"), list) else fallback_context.get("business_rules"),
            source_ids_by_type=source_ids_by_type,
        )
        spec["coverage_matrix"] = self._normalize_coverage_matrix_for_multisource(
            coverage_matrix=spec.get("coverage_matrix") if isinstance(spec.get("coverage_matrix"), list) else [],
            test_intents=spec["test_intents"],
            source_ids_by_type=source_ids_by_type,
            requirement_text=str(spec.get("raw_requirement", "")).strip() or str(requirement).strip() or str(spec.get("design_input", "")).strip(),
        )
        spec["change_impact"] = self._normalize_change_impact_for_multisource(
            change_impact=spec.get("change_impact") if isinstance(spec.get("change_impact"), dict) else {},
            fallback_context=fallback_context,
            test_intents=spec["test_intents"],
            source_ids_by_type=source_ids_by_type,
        )
        spec["parameter_constraints"] = [
            {
                **item,
                "source_id": str(item.get("source_id", "")).strip() or self._resolve_source_ids(
                    raw_source_ids=[item.get("source_id")] if item.get("source_id") else ["openapi"],
                    source_ids_by_type=source_ids_by_type,
                    fallback_types=["openapi"],
                    fallback_to_all=False,
                )[0] if self._resolve_source_ids(
                    raw_source_ids=[item.get("source_id")] if item.get("source_id") else ["openapi"],
                    source_ids_by_type=source_ids_by_type,
                    fallback_types=["openapi"],
                    fallback_to_all=False,
                ) else "",
            }
            for item in (spec.get("parameter_constraints") if isinstance(spec.get("parameter_constraints"), list) else fallback_context.get("parameter_constraints", []))
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        ][:40]
        parser_runtime = spec.get("parser_runtime") if isinstance(spec.get("parser_runtime"), dict) else {}
        llm_trace = parser_runtime.get("llm_trace") if isinstance(parser_runtime.get("llm_trace"), dict) else {}
        parser_runtime["llm_trace"] = {
            "attempted": bool(llm_trace.get("attempted", False)),
            "succeeded": bool(llm_trace.get("succeeded", False)),
            "reason_code": str(llm_trace.get("reason_code", "")).strip() or "llm_parse",
            "latency_ms": int(llm_trace.get("latency_ms", 0) or 0),
            "overlay_key_count": len(normalized_source_inputs),
            "total_tokens": llm_trace.get("total_tokens"),
        }
        parser_runtime["source_summary"] = {
            "source_count": len(normalized_source_inputs),
            "source_types": sorted(source_ids_by_type.keys()),
            "has_multisource_inputs": len(normalized_source_inputs) > 1,
        }
        if not isinstance(parser_runtime.get("ai_trace"), dict):
            parser_runtime["ai_trace"] = build_ai_trace_context(
                page=str(spec.get("page", "")).strip(),
                prompt_version=str(parser_runtime.get("prompt_version", "")).strip(),
                model=str(parser_runtime.get("model", "")).strip(),
                source=str(source).strip(),
                instructions_version=str(parser_runtime.get("instructions_version", "")).strip(),
            )
        parser_runtime["trace_id"] = str(parser_runtime.get("trace_id", "")).strip() or str(
            parser_runtime["ai_trace"].get("trace_id", "")
        ).strip()
        parser_runtime["page_resolution"] = self._build_page_resolution_summary(
            page=str(spec.get("page", "")).strip(),
            fallback_context=fallback_context,
            source_inputs=normalized_source_inputs,
        )
        spec["parser_runtime"] = parser_runtime
        spec["source_type"] = str(spec.get("source_type", "")).strip() or source
        return spec

    def _build_test_point_traceability_summary(
        self,
        *,
        requirement_spec: dict[str, Any],
        test_points: dict[str, Any],
    ) -> dict[str, Any]:
        return self._multisource_support.build_test_point_traceability_summary(
            requirement_spec=requirement_spec,
            test_points=test_points,
        )

    def orchestrate(
        self,
        requirement: str,
        page: str = "",
        execute: bool = False,
        source: str = "manual",
        mode: str | None = None,
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
        runner: str = "playwright",
    ) -> OrchestrationResult:
        """端到端编排：解析需求 → 生成用例 → 可选执行 → 产出报告。"""
        return self._orchestration_flow_support.orchestrate(
            requirement=requirement,
            page=page,
            execute=execute,
            source=source,
            mode=mode,
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
            runner=runner,
        )

    def _parse_requirement_spec(
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
            return self._requirement_parse_support.parse_requirement_spec(
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
        except RuntimeError as exc:
            raise OrchestratorError(
                code="requirement_parser_failed",
                message=str(exc) or "requirement parser failed",
                status_code=HTTPStatus.BAD_GATEWAY,
            ) from exc

    @staticmethod
    def _infer_page_from_text(
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
        return RequirementParseSupport.infer_page_from_text(
            requirement=requirement,
            prd_text=prd_text,
            user_story=user_story,
            git_diff=git_diff,
            defect_ticket=defect_ticket,
            runtime_logs=runtime_logs,
            openapi_spec=openapi_spec,
            input_sources=input_sources,
        )

    def _build_requirement_quality_gate(self, requirement_spec: dict[str, Any], *, stage: str) -> dict[str, Any]:
        return self._requirement_testpoint_support.build_requirement_quality_gate(requirement_spec, stage=stage)

    def _attach_requirement_quality_gate(self, requirement_spec: dict[str, Any], *, stage: str) -> dict[str, Any]:
        return self._requirement_testpoint_support.attach_requirement_quality_gate(requirement_spec, stage=stage)

    def _build_requirement_quality_blocker(
        self,
        *,
        code: str,
        message: str,
        value: Any = None,
        threshold: Any = None,
    ) -> dict[str, Any]:
        return self._requirement_testpoint_support.build_requirement_quality_blocker(
            code=code,
            message=message,
            value=value,
            threshold=threshold,
        )

    def _enforce_requirement_quality_gate(self, requirement_spec: dict[str, Any], *, stage: str) -> None:
        gate = self._requirement_testpoint_support.enforce_requirement_quality_gate(requirement_spec, stage=stage)
        requirement_spec["quality_gate"] = gate
        if not gate.get("gate_enabled", False):
            return
        if str(gate.get("decision", "")).strip().lower() != "block":
            return
        raise OrchestratorValidationError(
            "requirement quality gate blocked orchestration",
            details={"quality_gate": gate},
        )

    @staticmethod
    def _merge_case_requirements(raw_requirement: str, requirement_spec: dict[str, Any]) -> list[str]:
        return RequirementTestPointSupport.merge_case_requirements(raw_requirement, requirement_spec)

    def _evaluate_risk_report(
        self,
        *,
        requirement_spec: dict[str, Any],
        execution_plan: dict[str, Any],
        execution_record: dict[str, Any],
        failure_analysis: dict[str, Any],
        failure_triage: dict[str, Any],
    ) -> dict[str, Any]:
        return self._failure_healing_support.evaluate_risk_report(
            requirement_spec=requirement_spec,
            execution_plan=execution_plan,
            execution_record=execution_record,
            failure_analysis=failure_analysis,
            failure_triage=failure_triage,
        )

    def _triage_failure(
        self,
        *,
        failure_analysis: dict[str, Any],
        execution_record: dict[str, Any],
        evidence_manifest: dict[str, Any],
        report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._failure_healing_support.triage_failure(
            failure_analysis=failure_analysis,
            execution_record=execution_record,
            evidence_manifest=evidence_manifest,
            report=report,
        )

    def _enrich_failure_triage_with_history(
        self,
        *,
        triage: dict[str, Any],
        case_id: str,
        page: str,
        started_at: str,
    ) -> dict[str, Any]:
        return self._failure_healing_support.enrich_failure_triage_with_history(
            triage=triage,
            case_id=case_id,
            page=page,
            started_at=started_at,
        )

    def _iter_recent_reports(self, *, limit: int = 200) -> list[dict[str, Any]]:
        report_files = sorted(
            self.report_root.glob("*.report.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        records: list[dict[str, Any]] = []
        for report_path in report_files[: max(1, limit)]:
            try:
                payload = json.loads(report_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                _logger.debug("skipping unreadable report file: %s", report_path, exc_info=True)
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return records

    def _normalize_test_point_plan(self, payload: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
        from shared_backend.schemas import normalize_test_point_plan_v1

        normalized, warnings = normalize_test_point_plan_v1(payload, strict=strict)
        for warning in warnings:
            self.logger.warning("test_point_plan normalization warning: %s", warning)
        return normalized

    def _normalize_execution_record(self, payload: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
        try:
            from shared_backend.schemas import normalize_execution_record_v1

            normalized, warnings = normalize_execution_record_v1(payload, strict=strict)
            for warning in warnings:
                self.logger.warning("execution_record normalization warning: %s", warning)
            return normalized
        except Exception as exc:
            self.logger.warning("execution_record normalization unavailable, keep raw payload: %s", exc)
            return payload if isinstance(payload, dict) else {}

    def _normalize_evidence_manifest(self, payload: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
        try:
            from shared_backend.schemas import normalize_evidence_manifest_v1

            normalized, warnings = normalize_evidence_manifest_v1(payload, strict=strict)
            for warning in warnings:
                self.logger.warning("evidence_manifest normalization warning: %s", warning)
            return normalized
        except Exception as exc:
            self.logger.warning("evidence_manifest normalization unavailable, keep raw payload: %s", exc)
            return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _parse_test_design_error(raw_error: str) -> dict[str, Any]:
        text = str(raw_error or "").strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _generate_case(self, requirement: str, page: str) -> dict[str, Any]:
        try:
            return self._agent_execution_support.generate_case(requirement, page)
        except RuntimeError as exc:
            parsed = self._parse_test_design_error(str(exc))
            if parsed:
                code = str(parsed.get("code", "")).strip() or "test_design_failed"
                message = str(parsed.get("message", "")).strip() or "test-design-agent failed"
                details = parsed.get("details") if isinstance(parsed.get("details"), dict) else {}
                reason_code = str(details.get("reason_code", "")).strip() or code
                normalized_details = {
                    "reason_code": reason_code,
                    "test_design_error": {
                        "code": code,
                        "message": message,
                        "details": details,
                    },
                }
                if code in {"test_design_invalid_output", "test_design_bundle_invalid_output", "test_design_request_invalid"}:
                    raise OrchestratorValidationError(message, details=normalized_details) from exc
                if code == "test_design_llm_unavailable":
                    raise OrchestratorError(
                        code=code,
                        message=message,
                        status_code=HTTPStatus.BAD_GATEWAY,
                        details=normalized_details,
                    ) from exc
                raise OrchestratorError(
                    code=code,
                    message=message,
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    details=normalized_details,
                ) from exc
            raise OrchestratorError(
                code="test_design_failed",
                message="test-design-agent failed",
                status_code=HTTPStatus.BAD_GATEWAY,
                details={
                    "reason_code": "test_design_failed",
                    "upstream_error": str(exc)[:500],
                },
            ) from exc

    def _build_design_generation(self, case: dict[str, Any]) -> dict[str, Any]:
        return AgentExecutionSupport.build_design_generation(case)

    def _build_test_points_preview(
        self,
        *,
        case: dict[str, Any],
        requirement_spec: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            return self._requirement_testpoint_support.build_test_points_preview(
                case=case,
                requirement_spec=requirement_spec,
            )
        except ValueError as exc:
            raise OrchestratorValidationError(
                str(exc) or "test point preview failed",
                details={
                    "reason_code": "test_point_preview_failed",
                    "upstream_error": str(exc)[:500],
                },
            ) from exc

    def _build_test_points_from_requirement_spec(
        self,
        *,
        case: dict[str, Any],
        requirement_spec: dict[str, Any],
    ) -> dict[str, Any]:
        return self._requirement_testpoint_support.build_test_points_from_requirement_spec(
            case=case,
            requirement_spec=requirement_spec,
        )

    def _apply_constraint_summary_to_test_points(
        self,
        test_points: dict[str, Any],
        *,
        requirement_spec: dict[str, Any],
    ) -> dict[str, Any]:
        return self._requirement_testpoint_support.apply_constraint_summary_to_test_points(
            test_points,
            requirement_spec=requirement_spec,
        )

    def _build_constraint_technique_summary(
        self,
        *,
        requirement_spec: dict[str, Any],
        current_points: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self._requirement_testpoint_support.build_constraint_technique_summary(
            requirement_spec=requirement_spec,
            current_points=current_points,
        )

    @staticmethod
    def _map_intent_type_to_point_type(intent_type: str) -> str:
        return RequirementTestPointSupport.map_intent_type_to_point_type(intent_type)

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        return RequirementTestPointSupport.safe_int(value)

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        return RequirementTestPointSupport.safe_float(value)

    def _map_intent_to_step(
        self,
        *,
        page: str,
        intent_type: str,
        title: str,
        steps_hint: Any,
        target: Any = None,
        value: Any = None,
        page_element_alias_map: dict[str, str] | None = None,
    ) -> tuple[str, str | None, Any]:
        return RequirementTestPointSupport.map_intent_to_step(
            page=page,
            intent_type=intent_type,
            title=title,
            steps_hint=steps_hint,
            target=target,
            value=value,
            page_element_alias_map=page_element_alias_map,
        )

    def _save_case(self, case: dict[str, Any]) -> Path:
        self._ensure_runner_import_path()
        from runner.asset_toolkit import save_test_case

        return save_test_case(
            case,
            kind="ai-generated",
            output_dir=self.generated_cases_root,
        )

    def _prepare_generated_case_for_assets(self, case: dict[str, Any]) -> dict[str, Any]:
        self._ensure_runner_import_path()
        from runner.asset_toolkit import prepare_generated_test_case

        return prepare_generated_test_case(case)

    def _ensure_runner_import_path(self) -> None:
        # Prefer PYTHONPATH in Docker; this fallback keeps the service runnable in dev.
        if str(self.runner_root) not in sys.path:
            sys.path.insert(0, str(self.runner_root))

    def _resolve_page_object(self, *, project: str, page: str) -> dict[str, Any]:
        """Orchestrator 的页面对象解析（Path A）。

        先查 YAML asset，再回退到 DB。返回 {page, elements}。
        对应的 pipeline 入口是 generate_pipeline.resolve_page_object()，
        对应的 facade 入口是 facade._page_object_generation_context()。
        三者功能等价，返回格式略有不同。
        """
        normalized_project = str(project).strip() or "mall"
        normalized_page = str(page).strip().lower()
        if not normalized_page:
            raise OrchestratorValidationError(
                "page object identity must not be empty",
                details={"reason_code": "page_object_not_found", "project": normalized_project, "page": normalized_page},
            )
        asset_path = self.repo_root / "assets" / "page-objects" / "web" / f"{normalized_page}.page-object.yaml"
        if asset_path.exists():
            try:
                raw = yaml.safe_load(asset_path.read_text(encoding="utf-8")) or {}
            except (yaml.YAMLError, OSError, ValueError) as exc:
                raise OrchestratorValidationError(
                    "failed to resolve page object from assets",
                    details={
                        "reason_code": "page_object_not_found",
                        "project": normalized_project,
                        "page": normalized_page,
                        "upstream_error": str(exc)[:500],
                    },
                ) from exc
            if isinstance(raw, dict):
                elements_raw = raw.get("elements")
                if isinstance(elements_raw, dict):
                    elements: dict[str, dict[str, str]] = {}
                    for code, item in elements_raw.items():
                        element_code = str(code or "").strip()
                        selector = ""
                        locator_type = "css"
                        role = ""
                        if isinstance(item, dict):
                            selector = str(item.get("locator_value") or item.get("selector") or "").strip()
                            locator_type = str(item.get("locator_type") or "").strip() or "css"
                            role = str(item.get("role") or "").strip()
                        elif isinstance(item, str):
                            selector = str(item or "").strip()
                        if not element_code or not selector:
                            continue
                        elements[element_code] = {
                            "selector": selector,
                            "type": locator_type,
                            "role": role,
                        }
                    if elements:
                        return {"page": normalized_page, "elements": elements}
        try:
            from shared_backend.db import get_db_session
            from shared_backend.page_object_queries import (
                fetch_page_object_id,
                fetch_page_elements,
            )

            with get_db_session() as db:
                po_id = fetch_page_object_id(
                    db, project=normalized_project, client="web", page=normalized_page,
                )
                if po_id is None:
                    raise OrchestratorValidationError(
                        "page object not found",
                        details={
                            "reason_code": "page_object_not_found",
                            "project": normalized_project,
                            "page": normalized_page,
                        },
                    )
                element_rows = fetch_page_elements(db, page_object_id=po_id)
            if not element_rows:
                raise OrchestratorValidationError(
                    "page object has no elements",
                    details={
                        "reason_code": "page_object_empty_elements",
                        "project": normalized_project,
                        "page": normalized_page,
                    },
                )
            elements: dict[str, dict[str, str]] = {}
            for el in element_rows:
                code = el["element_code"]
                selector = el["locator_value"]
                if not code or not selector:
                    continue
                elements[code] = {
                    "selector": selector,
                    "type": el["locator_type"] or "css",
                    "role": el["role"],
                }
            if not elements:
                raise OrchestratorValidationError(
                    "page object has no bindable elements",
                    details={
                        "reason_code": "page_object_empty_elements",
                        "project": normalized_project,
                        "page": normalized_page,
                    },
                )
            return {"page": normalized_page, "elements": elements}
        except OrchestratorValidationError:
            raise
        except Exception as exc:
            raise OrchestratorValidationError(
                "failed to resolve page object",
                details={
                    "reason_code": "page_object_not_found",
                    "project": normalized_project,
                    "page": normalized_page,
                    "upstream_error": str(exc)[:500],
                },
            ) from exc

    def _build_report_summary_path(self) -> str:
        return self._execution_report_support.build_report_summary_path()

    def _run_case(self, case_id: str, case_path: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["RUN_MODE"] = "ai"
        env["TEST_CASE_ID"] = case_id
        env["TEST_CASE_PATH"] = str(case_path)

        return subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_yaml_ai_generated.py", "-rs"],
            cwd=self.runner_root,
            env=env,
            text=True,
            capture_output=True,
        )

    def parse_requirement(
        self,
        *,
        requirement: str,
        page: str = "",
        source: str = "manual",
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
        """仅解析需求为 RequirementSpec，并附加质量门与遥测。"""
        if not page.strip():
            raise OrchestratorValidationError("page must not be empty")
        if not requirement.strip():
            if not any(
                [
                    isinstance(input_sources, list) and bool(input_sources),
                    isinstance(openapi_spec, dict) and bool(openapi_spec),
                    bool(prd_text.strip()),
                    bool(prd_url.strip()),
                    bool(user_story.strip()),
                    bool(git_diff.strip()),
                    bool(git_diff_path.strip()),
                    bool(openapi_url.strip()),
                    bool(defect_ticket.strip()),
                    bool(runtime_logs.strip()),
                ]
            ):
                raise OrchestratorValidationError("requirement must not be empty")
        parsed = self._parse_requirement_spec(
            requirement=requirement,
            page=page.strip(),
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
        self._attach_requirement_quality_gate(parsed, stage="parse")
        scope_text = self._requirement_parse_support.build_scope_text(
            requirement=requirement,
            prd_text=prd_text,
            user_story=user_story,
            git_diff=git_diff,
            defect_ticket=defect_ticket,
            runtime_logs=runtime_logs,
            input_sources=input_sources,
        )
        parsed["scope_estimate"] = self._requirement_parse_support.estimate_input_scope(scope_text)
        self._record_requirement_parse_telemetry(
            requirement_spec=parsed,
            stage="parse",
            source=source,
            outcome=str((parsed.get("quality_gate") or {}).get("decision", "allow")).strip() or "allow",
        )
        return parsed

    def get_requirement_parse_telemetry_summary(
        self,
        *,
        limit: int = 500,
        prompt_version: str = "",
        model: str = "",
        mode: str = "",
        stage: str = "",
    ) -> dict[str, Any]:
        return self._analytics_query_support.get_requirement_parse_telemetry_summary(
            limit=limit,
            prompt_version=prompt_version,
            model=model,
            mode=mode,
            stage=stage,
        )

    def get_llm_health(self, *, probe: bool = True) -> dict[str, Any]:
        """检查 LLM 配置完整性，可选发起轻量连通性探活。"""
        api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
        base_url = str(os.getenv("OPENAI_BASE_URL", "")).strip()
        model = str(os.getenv("OPENAI_MODEL", "")).strip()
        force_llm = RequirementParseSupport.is_llm_force_mode_enabled()

        masked_key = ""
        if api_key:
            masked_key = f"{api_key[:6]}***{api_key[-4:]}" if len(api_key) > 12 else "***"

        result: dict[str, Any] = {
            "status": "ok",
            "force_llm_mode": bool(force_llm),
            "config": {
                "has_api_key": bool(api_key),
                "api_key_masked": masked_key,
                "base_url": base_url,
                "model": model,
                "provider": "openai_compatible",
            },
            "checks": {
                "api_key_present": bool(api_key),
                "base_url_present": bool(base_url),
                "model_present": bool(model),
            },
            "probe": {
                "enabled": bool(probe),
                "attempted": False,
                "ok": False,
                "latency_ms": 0,
                "error_code": "",
                "error_message": "",
            },
            "actionable": [],
        }

        if not api_key:
            result["status"] = "warning"
            result["actionable"].append("请在 .env 中设置 OPENAI_API_KEY。")
        if not base_url:
            result["status"] = "warning"
            result["actionable"].append("请在 .env 中设置 OPENAI_BASE_URL。")
        if not model:
            result["status"] = "warning"
            result["actionable"].append("请在 .env 中设置 OPENAI_MODEL。")

        if not probe or result["status"] != "ok":
            if not result["actionable"]:
                result["actionable"].append("配置已通过基础校验，可执行 probe=true 进行连通性检测。")
            return result

        started_at = datetime.now(UTC)
        probe_block = result["probe"]
        probe_block["attempted"] = True
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key,
                base_url=base_url or None,
                timeout=8,
                max_retries=0,
            )
            completion = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[
                    {"role": "system", "content": "healthcheck"},
                    {"role": "user", "content": "ping"},
                ],
                max_tokens=1,
            )
            probe_block["ok"] = True
            usage = getattr(completion, "usage", None)
            if usage is not None:
                probe_block["usage"] = {
                    "prompt_tokens": getattr(usage, "prompt_tokens", None),
                    "completion_tokens": getattr(usage, "completion_tokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None),
                }
            result["actionable"].append("LLM 连通性通过。")
        except Exception as exc:
            result["status"] = "warning"
            probe_block["ok"] = False
            probe_block["error_code"] = "llm_probe_failed"
            probe_block["error_message"] = str(exc)[:240]
            result["actionable"].append("LLM 探活失败，请核对 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL。")
        finally:
            ended_at = datetime.now(UTC)
            probe_block["latency_ms"] = max(0, int((ended_at - started_at).total_seconds() * 1000))
        return result

    def _iter_requirement_parse_telemetry_events(self, *, limit: int) -> list[dict[str, Any]]:
        return self._analytics_query_support.iter_requirement_parse_telemetry_events(limit=limit)

    def _record_requirement_parse_telemetry(
        self,
        *,
        requirement_spec: dict[str, Any],
        stage: str,
        source: str,
        outcome: str,
    ) -> None:
        self._analytics_query_support.record_requirement_parse_telemetry(
            requirement_spec=requirement_spec,
            stage=stage,
            source=source,
            outcome=outcome,
        )

    def list_runners(self) -> dict[str, Any]:
        """返回已注册的 Runner 目录（Playwright / API / Mobile 等）。"""
        return self._runner_registry_support.list_runners()

    def _resolve_runner_profile(self, runner: str) -> dict[str, Any]:
        try:
            return self._runner_registry_support.resolve_runner_profile(runner)
        except ValueError as exc:
            raise OrchestratorValidationError(str(exc)) from exc

    def evaluate_risk(
        self,
        *,
        requirement_spec: dict[str, Any],
        execution_plan: dict[str, Any],
        execution_record: dict[str, Any],
        failure_analysis: dict[str, Any],
        failure_triage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """调用风险评估 Agent，输出 RiskReportV1。"""
        return self._evaluate_risk_report(
            requirement_spec=requirement_spec,
            execution_plan=execution_plan,
            execution_record=self._normalize_execution_record(execution_record),
            failure_analysis=failure_analysis,
            failure_triage=failure_triage or {},
        )

    def triage_failure(
        self,
        *,
        failure_analysis: dict[str, Any],
        execution_record: dict[str, Any],
        evidence_manifest: dict[str, Any],
        report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """对失败进行分诊并融合历史报告上下文。"""
        raw_triage = self._triage_failure(
            failure_analysis=failure_analysis,
            execution_record=self._normalize_execution_record(execution_record),
            evidence_manifest=self._normalize_evidence_manifest(evidence_manifest),
            report=report or {},
        )
        active_report = report if isinstance(report, dict) else {}
        case_id = str(active_report.get("case_id") or execution_record.get("case_id") or "").strip()
        page = str(active_report.get("page") or (execution_record.get("step_summary") or {}).get("page") or "").strip()
        started_at = str(active_report.get("started_at") or execution_record.get("started_at") or self._now()).strip()
        return self._enrich_failure_triage_with_history(
            triage=raw_triage,
            case_id=case_id,
            page=page,
            started_at=started_at,
        )

    @staticmethod
    def agent_pipeline_order() -> list[str]:
        return [
            "requirement-parser-agent",
            "test-design-agent",
            "script-generation-agent",
            "execution-planner-agent",
            "risk-evaluation-agent",
            "failure-analysis-agent",
            "failure-triage-agent",
            "self-healing-advisor-agent",
        ]

    @staticmethod
    def serialize_result(result: OrchestrationResult) -> dict[str, Any]:
        return asdict(result)

    @staticmethod
    def render_requirement_spec_markdown(requirement_spec: dict[str, Any]) -> str:
        return RequirementTestPointSupport.render_requirement_spec_markdown(requirement_spec)

    def get_latest_report(self) -> dict[str, Any]:
        """读取最近一次执行报告 JSON。"""
        try:
            return self._analytics_query_support.get_latest_report()
        except ValueError as exc:
            raise OrchestratorValidationError(str(exc)) from exc

    def get_report(self, case_id: str) -> dict[str, Any]:
        try:
            return self._analytics_query_support.get_report(case_id)
        except ValueError as exc:
            raise OrchestratorValidationError(str(exc)) from exc

    def get_failure_clusters(
        self,
        *,
        limit: int = 200,
        max_clusters: int = 20,
        queue: str = "",
        failure_class: str = "",
        severity: str = "",
    ) -> dict[str, Any]:
        return self._analytics_query_support.get_failure_clusters(
            limit=limit,
            max_clusters=max_clusters,
            queue=queue,
            failure_class=failure_class,
            severity=severity,
        )

    def get_failure_cluster(self, *, cluster_id: str, limit: int = 200) -> dict[str, Any]:
        try:
            return self._analytics_query_support.get_failure_cluster(cluster_id=cluster_id, limit=limit)
        except ValueError as exc:
            raise OrchestratorValidationError(str(exc)) from exc

    def _load_report_summary_preview(self, summary_path: Path) -> dict[str, Any]:
        return self._execution_report_support.load_report_summary_preview(summary_path)

    @staticmethod
    def _append_report_summary_case_preview(preview: dict[str, Any], current_case: dict[str, str]) -> None:
        ExecutionReportSupport.append_report_summary_case_preview(preview, current_case)

    def preview_self_healing_advice(
        self,
        page: str,
        case: dict[str, Any] | None = None,
        failure_reason: str = "",
        failure_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """预览自愈建议（不写入执行产物）。"""
        try:
            return self._failure_healing_support.preview_self_healing_advice(
                page=page,
                case=case,
                failure_reason=failure_reason,
                failure_analysis=failure_analysis,
            )
        except ValueError as exc:
            raise OrchestratorValidationError(str(exc)) from exc

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _snapshot_evidence_files(self) -> set[str]:
        roots = [
            self.runner_root / "artifacts",
            self.runner_root / "test-results" / "videos",
        ]
        paths: set[str] = set()
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.is_file():
                    paths.add(str(path.resolve()))
        return paths

    @staticmethod
    def _empty_evidence_manifest() -> dict[str, Any]:
        return {
            "version": "EvidenceManifestV1",
            "schema_version": "evidence-manifest.v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "artifact_root": "",
            "screenshots": [],
            "html_pages": [],
            "meta_files": [],
            "analysis_files": [],
            "suggestion_files": [],
            "execution_record_files": [],
            "self_healing_result_files": [],
            "videos": [],
            "other_files": [],
            "total_files": 0,
            "metadata": {},
        }

    def _build_evidence_manifest(self, before: set[str], after: set[str]) -> dict[str, Any]:
        manifest = self._empty_evidence_manifest()
        for raw_path in sorted(after - before):
            path = Path(raw_path)
            if path.suffix.lower() == ".png":
                manifest["screenshots"].append(raw_path)
            elif path.suffix.lower() == ".html":
                manifest["html_pages"].append(raw_path)
            elif path.suffix.lower() == ".txt":
                if path.name == "analysis.txt":
                    manifest["analysis_files"].append(raw_path)
                else:
                    manifest["meta_files"].append(raw_path)
            elif path.suffix.lower() == ".json" and path.name == "suggestion.json":
                manifest["suggestion_files"].append(raw_path)
            elif path.suffix.lower() == ".json" and path.name == "execution_record.json":
                manifest["execution_record_files"].append(raw_path)
            elif path.suffix.lower() == ".json" and path.name == "self_healing_result.json":
                manifest["self_healing_result_files"].append(raw_path)
            elif path.suffix.lower() == ".webm":
                manifest["videos"].append(raw_path)
            else:
                manifest["other_files"].append(raw_path)
        manifest["total_files"] = sum(
            len(manifest[key])
            for key in (
                "screenshots",
                "html_pages",
                "meta_files",
                "analysis_files",
                "suggestion_files",
                "execution_record_files",
                "self_healing_result_files",
                "videos",
                "other_files",
            )
        )
        candidate_roots = sorted({str(Path(item).resolve().parent) for item in (after - before)})
        if candidate_roots:
            manifest["artifact_root"] = candidate_roots[0]
        return self._normalize_evidence_manifest(manifest)

    def _build_and_save_report(
        self,
        requirement_spec: dict[str, Any],
        case: dict[str, Any],
        test_points: dict[str, Any],
        generated_script: dict[str, Any],
        execution_plan: dict[str, Any],
        design_generation: dict[str, Any],
        case_path: Path,
        execution_requested: bool,
        completed: subprocess.CompletedProcess[str] | None,
        evidence_manifest: dict[str, Any],
        started_at: str,
        finished_at: str,
        source: str,
        mode: str,
        runner_profile: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], Path, Path]:
        report_payload = self._build_report_payload(
            requirement_spec=requirement_spec,
            case=case,
            test_points=test_points,
            generated_script=generated_script,
            execution_plan=execution_plan,
            design_generation=design_generation,
            case_path=case_path,
            execution_requested=execution_requested,
            completed=completed,
            evidence_manifest=evidence_manifest,
            started_at=started_at,
            finished_at=finished_at,
            source=source,
            mode=mode,
            runner_profile=runner_profile,
        )
        return self._write_report_files(case["id"], report_payload)

    def _build_report_payload(
        self,
        requirement_spec: dict[str, Any],
        case: dict[str, Any],
        test_points: dict[str, Any],
        generated_script: dict[str, Any],
        execution_plan: dict[str, Any],
        design_generation: dict[str, Any],
        case_path: Path,
        execution_requested: bool,
        completed: subprocess.CompletedProcess[str] | None,
        evidence_manifest: dict[str, Any],
        started_at: str,
        finished_at: str,
        source: str,
        mode: str,
        runner_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return self._execution_report_support.build_report_payload(
                requirement_spec=requirement_spec,
                case=case,
                test_points=test_points,
                generated_script=generated_script,
                execution_plan=execution_plan,
                design_generation=design_generation,
                case_path=case_path,
                execution_requested=execution_requested,
                completed=completed,
                evidence_manifest=evidence_manifest,
                started_at=started_at,
                finished_at=finished_at,
                source=source,
                mode=mode,
                runner_profile=runner_profile,
            )
        except ValueError as exc:
            raise OrchestratorValidationError(str(exc)) from exc

    @staticmethod
    def _load_execution_record_from_manifest(evidence_manifest: dict[str, Any]) -> dict[str, Any]:
        return ExecutionReportSupport.load_execution_record_from_manifest(evidence_manifest)

    def _resolve_execution_record_for_report(
        self,
        *,
        case: dict[str, Any],
        execution_requested: bool,
        source: str,
        mode: str,
        started_at: str,
        finished_at: str,
        status: str,
        runner_exit_code: int | None,
        evidence_manifest: dict[str, Any],
        execution_metadata: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            return self._execution_report_support.resolve_execution_record_for_report(
                case=case,
                execution_requested=execution_requested,
                source=source,
                mode=mode,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                runner_exit_code=runner_exit_code,
                evidence_manifest=evidence_manifest,
                execution_metadata=execution_metadata,
            )
        except ValueError as exc:
            raise OrchestratorValidationError(str(exc)) from exc

    @staticmethod
    def _merge_execution_record_metadata(
        execution_record: dict[str, Any],
        supplemental_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return ExecutionReportSupport.merge_execution_record_metadata(execution_record, supplemental_metadata)

    def _build_execution_record_metadata(
        self,
        *,
        requirement_spec: dict[str, Any],
        test_points: dict[str, Any],
        runner_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._execution_report_support.build_execution_record_metadata(
            requirement_spec=requirement_spec,
            test_points=test_points,
            runner_profile=runner_profile,
        )

    def _build_execution_record(
        self,
        *,
        case: dict[str, Any],
        execution_requested: bool,
        source: str,
        mode: str,
        started_at: str,
        finished_at: str,
        status: str,
        runner_exit_code: int | None,
        evidence_manifest: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._execution_report_support.build_execution_record(
            case=case,
            execution_requested=execution_requested,
            source=source,
            mode=mode,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            runner_exit_code=runner_exit_code,
            evidence_manifest=evidence_manifest,
            metadata=metadata,
        )

    @staticmethod
    def _extract_runner_metrics(output: str) -> dict[str, int]:
        metrics = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
        }
        for key in metrics:
            match = re.search(rf"(\d+)\s+{key}", output)
            if match:
                metrics[key] = int(match.group(1))
        return metrics

    @staticmethod
    def _build_pytest_results(
        output: str,
        error_output: str,
        runner_exit_code: int | None,
        metrics: dict[str, int],
    ) -> dict[str, Any]:
        collected = None
        collected_match = re.search(r"collected\s+(\d+)\s+items?", output)
        if collected_match:
            collected = int(collected_match.group(1))

        duration_seconds = None
        duration_match = re.search(r"in\s+([0-9]+(?:\.[0-9]+)?)s", output)
        if duration_match:
            duration_seconds = float(duration_match.group(1))

        return {
            "collected": collected,
            "passed": metrics["passed"],
            "failed": metrics["failed"],
            "skipped": metrics["skipped"],
            "errors": metrics["errors"],
            "runner_exit_code": runner_exit_code,
            "duration_seconds": duration_seconds,
            "has_stderr": bool(error_output.strip()),
        }

    @staticmethod
    def _extract_failure_reason(output: str, error_output: str, status: str) -> str:
        if status != "failed":
            return ""

        combined = "\n".join(part for part in (output, error_output) if part)
        patterns = [
            r"AssertionError:\s+(.+)",
            r"TimeoutError:\s+(.+)",
            r"E\s+(.+)",
            r"FAILED\s+.+\s+-\s+(.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, combined)
            if match:
                return match.group(1).strip()

        lines = [line.strip() for line in combined.splitlines() if line.strip()]
        if lines:
            return lines[-1]
        return "Runner execution failed without a parsed failure reason."

    def _analyze_failure(self, report_payload: dict[str, Any], stdout_text: str, stderr_text: str) -> dict[str, Any]:
        return self._failure_healing_support.analyze_failure(report_payload, stdout_text, stderr_text)

    def _run_failure_analysis_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Dev fallback; Docker sets PYTHONPATH for agent roots.
        if str(self.failure_agent_root) not in sys.path:
            sys.path.insert(0, str(self.failure_agent_root))
        from analyze import FailureAnalysisAgent

        agent = FailureAnalysisAgent()
        return agent.analyze(payload)

    def _build_self_healing_advice(self, case: dict[str, Any], report_payload: dict[str, Any]) -> dict[str, Any]:
        return self._failure_healing_support.build_self_healing_advice(case, report_payload)

    @staticmethod
    def _load_self_healing_suggestion_preview(report_payload: dict[str, Any]) -> dict[str, Any]:
        return FailureHealingSupport.load_self_healing_suggestion_preview(report_payload)

    @staticmethod
    def _load_self_healing_execution_preview(report_payload: dict[str, Any]) -> dict[str, Any]:
        return FailureHealingSupport.load_self_healing_execution_preview(report_payload)

    def _run_self_healing_advisor_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Dev fallback; Docker sets PYTHONPATH for agent roots.
        if str(self.self_healing_agent_root) not in sys.path:
            sys.path.insert(0, str(self.self_healing_agent_root))
        from agent import SelfHealingAdvisorAgent

        agent = SelfHealingAdvisorAgent()
        return agent.advise(payload)

    def _load_available_targets(self, page_name: str) -> list[str]:
        if not page_name:
            return []
        try:
            from shared_backend.db import get_db_session
            with get_db_session() as session:
                from shared_backend.db.models import PageElement
                rows = session.query(PageElement.code).filter(
                    PageElement.page_name == page_name
                ).all()
                if rows:
                    return sorted(r.code for r in rows if r.code)
        except (ImportError, AttributeError) as exc:
            self.logger.debug("unable to load available targets for page %s: %s", page_name, exc)
        except Exception as exc:
            self.logger.warning("unexpected error loading available targets for page %s: %s", page_name, exc)
        return []

    @staticmethod
    def _build_summary_text(status: str, case: dict[str, Any], execution_requested: bool, metrics: dict[str, int]) -> str:
        if not execution_requested:
            return f"Generated test case {case['id']} for page {case.get('execution', {}).get('page', '-')}. Execution was not requested."
        return (
            f"Executed test case {case['id']} with status {status}. "
            f"passed={metrics['passed']} failed={metrics['failed']} skipped={metrics['skipped']} errors={metrics['errors']}."
        )

    @staticmethod
    def _truncate_text(text: str, max_length: int = 4000) -> str:
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def _write_report_files(self, case_id: str, report_payload: dict[str, Any]) -> tuple[dict[str, Any], Path, Path]:
        self.report_root.mkdir(parents=True, exist_ok=True)
        json_path = self.report_root / f"{case_id}.report.json"
        markdown_path = self.report_root / f"{case_id}.report.md"
        json_path.write_text(self._render_report_json(report_payload), encoding="utf-8")
        markdown_path.write_text(self._render_report_markdown(report_payload), encoding="utf-8")
        return report_payload, json_path, markdown_path

    @staticmethod
    def _render_report_json(report_payload: dict[str, Any]) -> str:
        return ExecutionReportSupport.render_report_json(report_payload)

    @staticmethod
    def _render_report_markdown(report_payload: dict[str, Any]) -> str:
        return ExecutionReportSupport.render_report_markdown(report_payload)
