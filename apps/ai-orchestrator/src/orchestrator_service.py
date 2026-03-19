import os
import re
import subprocess
import sys
import json
import hashlib
import tempfile
import logging
from datetime_compat import UTC
from datetime import datetime
from dataclasses import asdict, dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any


class OrchestratorError(Exception):
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
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code="validation_error",
            message=message,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            details=details,
        )


class RunnerExecutionError(OrchestratorError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code="runner_failed",
            message=message,
            status_code=HTTPStatus.BAD_GATEWAY,
            details=details,
        )


@dataclass
class OrchestrationResult:
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
    ALLOWED_SOURCES = {"manual", "ai", "regression"}
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
        self.repo_root = repo_root or Path(__file__).resolve().parents[3]
        self.apps_root = self.repo_root / "apps"
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
        self.execution_record_compat_builder_enabled = self._env_bool(
            "EXECUTION_RECORD_COMPAT_BUILDER_ENABLED",
            default=True,
        )
        self.test_point_steps_authoritative = self._env_bool(
            "TEST_POINT_STEPS_AUTHORITATIVE",
            default=True,
        )
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
            default=1,
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

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return float(str(raw).strip())
        except Exception:
            return default

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return int(str(raw).strip())
        except Exception:
            return default

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
    ) -> OrchestrationResult:
        normalized_requirement = requirement.strip()
        if not normalized_requirement:
            has_multisource_inputs = any(
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
            )
            if not has_multisource_inputs:
                raise OrchestratorValidationError("requirement must not be empty")

        normalized_source = source.strip().lower()
        if normalized_source not in self.ALLOWED_SOURCES:
            raise OrchestratorValidationError("source must be one of: manual, ai, regression")
        normalized_mode = mode.strip().lower() if isinstance(mode, str) and mode.strip() else None
        if normalized_mode is None:
            normalized_mode = "generate_and_run" if execute else "generate_only"

        requirement_spec = self._parse_requirement_spec(
            requirement=requirement,
            page=page.strip(),
            source=normalized_source,
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
        resolved_page = str(requirement_spec.get("page", "")).strip() or page.strip()
        if not resolved_page:
            resolved_page = "product"
            requirement_spec["page"] = resolved_page
        else:
            requirement_spec["page"] = resolved_page

        try:
            self._enforce_requirement_quality_gate(requirement_spec, stage="orchestrate")
            self._record_requirement_parse_telemetry(
                requirement_spec=requirement_spec,
                stage="orchestrate",
                source=normalized_source,
                outcome="allow",
            )
        except OrchestratorValidationError:
            self._record_requirement_parse_telemetry(
                requirement_spec=requirement_spec,
                stage="orchestrate",
                source=normalized_source,
                outcome="block",
            )
            raise

        design_requirement = str(requirement_spec.get("design_input", "")).strip() or normalized_requirement
        if not design_requirement:
            design_requirement = str(requirement_spec.get("normalized_requirement", "")).strip() or "基础流程验证"

        case = self._generate_case(requirement=design_requirement, page=resolved_page)
        design_generation = self._build_design_generation(case)
        case["requirement"] = self._merge_case_requirements(
            raw_requirement=requirement or design_requirement,
            requirement_spec=requirement_spec,
        )
        generated_script = self._generate_script_bundle(case=case, framework="playwright", language="python")
        execution_plan = self._build_execution_plan(
            case=case,
            execution_requested=execute,
            source=normalized_source,
            execution_config={},
        )
        test_points = self._build_test_points_preview(
            case=case,
            requirement_spec=requirement_spec,
        )
        case = self._render_case_steps_from_test_points(case=case, test_points=test_points)
        case = self._prepare_generated_case_for_assets(case)
        case_path = self._save_case(case)
        started_at = self._now()

        result = OrchestrationResult(
            requirement_spec=requirement_spec,
            case=case,
            generated_script=generated_script,
            execution_plan=execution_plan,
            design_generation=design_generation,
            risk_report={},
            failure_triage={},
            agent_pipeline=self.agent_pipeline_order(),
            test_points=test_points,
            execution_record=self._build_execution_record(
                case=case,
                execution_requested=execute,
                source=normalized_source,
                mode=normalized_mode,
                started_at=started_at,
                finished_at="",
                status="running" if execute else "generated",
                runner_exit_code=None,
                evidence_manifest=self._empty_evidence_manifest(),
            ),
            case_path=str(case_path),
            execution_requested=execute,
        )

        completed = None
        evidence_manifest = self._empty_evidence_manifest()
        if execute:
            evidence_before = self._snapshot_evidence_files()
            completed = self._run_case(case_id=case["id"], case_path=case_path)
            evidence_manifest = self._build_evidence_manifest(evidence_before, self._snapshot_evidence_files())
            result.runner_exit_code = completed.returncode
            result.runner_stdout = completed.stdout
            result.runner_stderr = completed.stderr
            result.execution_record = self._build_execution_record(
                case=case,
                execution_requested=execute,
                source=normalized_source,
                mode=normalized_mode,
                started_at=started_at,
                finished_at=self._now(),
                status="passed" if completed.returncode == 0 else "failed",
                runner_exit_code=completed.returncode,
                evidence_manifest=evidence_manifest,
            )
            if completed.returncode != 0:
                report_payload, report_json_path, report_markdown_path = self._build_and_save_report(
                    requirement_spec=requirement_spec,
                    case=case,
                    test_points=test_points,
                    generated_script=generated_script,
                    execution_plan=execution_plan,
                    design_generation=design_generation,
                    case_path=case_path,
                    execution_requested=execute,
                    completed=completed,
                    evidence_manifest=evidence_manifest,
                    started_at=started_at,
                    finished_at=self._now(),
                    source=normalized_source,
                    mode=normalized_mode,
                )
                report_summary_path = self._build_report_summary_path() if execute else ""
                raise RunnerExecutionError(
                    "Runner execution failed",
                    details={
                        "runner_exit_code": completed.returncode,
                        "runner_stdout": completed.stdout,
                        "runner_stderr": completed.stderr,
                        "report": report_payload,
                        "report_json_path": str(report_json_path),
                        "report_markdown_path": str(report_markdown_path),
                        "report_summary_path": report_summary_path,
                    },
                )

        report_payload, report_json_path, report_markdown_path = self._build_and_save_report(
            requirement_spec=requirement_spec,
            case=case,
            test_points=test_points,
            generated_script=generated_script,
            execution_plan=execution_plan,
            design_generation=design_generation,
            case_path=case_path,
            execution_requested=execute,
            completed=completed,
            evidence_manifest=evidence_manifest,
            started_at=started_at,
            finished_at=self._now(),
            source=normalized_source,
            mode=normalized_mode,
        )
        result.report = report_payload
        result.report_json_path = str(report_json_path)
        result.report_markdown_path = str(report_markdown_path)
        result.report_summary_path = self._build_report_summary_path() if execute else ""
        result.risk_report = report_payload.get("risk_report", {})
        result.failure_triage = report_payload.get("failure_triage", {})
        if not execute:
            result.execution_record = report_payload["execution_record"]

        return result

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
            pythonpath_entries = [str(self.repo_root), str(self.requirement_parser_root)]
            existing_pythonpath = str(os.environ.get("PYTHONPATH", "")).strip()
            if existing_pythonpath:
                pythonpath_entries.append(existing_pythonpath)
            env = dict(os.environ)
            env["PYTHONPATH"] = os.pathsep.join(entry for entry in pythonpath_entries if entry)
            completed = subprocess.run(
                [sys.executable, "-m", "src.index", "--input", str(temp_path)],
                cwd=str(self.requirement_parser_root),
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
                parsed["parser_runtime"] = self._build_requirement_parser_runtime_fallback(
                    source="subprocess",
                    detail="missing parser_runtime in parser output",
                )
            return parsed
        except Exception:
            normalized = requirement.strip()
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
            return {
                "version": "RequirementSpecV1",
                "source_type": source,
                "page": resolved_page,
                "raw_requirement": requirement,
                "normalized_requirement": normalized,
                "source_inputs": [],
                "entities": [],
                "test_intents": [
                    {
                        "intent_id": "intent-01",
                        "title": normalized[:80] or "基础流程验证",
                        "intent_type": "functional",
                        "priority": "P1",
                        "steps_hint": ["smoke", "assert"],
                        "dependencies": [],
                    }
                ],
                "coverage_matrix": [
                    {
                        "requirement_id": "REQ-001",
                        "requirement_text": normalized[:200],
                        "intent_ids": ["intent-01"],
                        "coverage_ratio": 1.0,
                    }
                ],
                "dependency_graph": [{"intent_id": "intent-01", "depends_on": []}],
                "business_rules": [],
                "ambiguities": [],
                "change_impact": {
                    "changed_modules": [],
                    "changed_files": [],
                    "affected_intent_ids": ["intent-01"],
                    "suggested_regression_scope": [resolved_page],
                    "risk_hint": "fallback",
                },
                "historical_patterns": [],
                "priority": "P1",
                "design_input": requirement or normalized or "基础流程验证",
                "parse_confidence": 0.72 if normalized else 0.5,
                "parser_runtime": self._build_requirement_parser_runtime_fallback(
                    source="orchestrator_fallback",
                    detail="requirement parser subprocess failed; fallback spec used",
                ),
            }

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
    def _build_requirement_parser_runtime_fallback(*, source: str, detail: str) -> dict[str, Any]:
        return {
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
        }

    def _build_requirement_quality_gate(self, requirement_spec: dict[str, Any], *, stage: str) -> dict[str, Any]:
        intents = requirement_spec.get("test_intents")
        intent_list = intents if isinstance(intents, list) else []
        ambiguities = requirement_spec.get("ambiguities")
        ambiguity_list = ambiguities if isinstance(ambiguities, list) else []
        coverage_matrix = requirement_spec.get("coverage_matrix")
        coverage_list = coverage_matrix if isinstance(coverage_matrix, list) else []

        high_ambiguity_count = 0
        medium_ambiguity_count = 0
        for item in ambiguity_list:
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity", "medium")).strip().lower()
            if severity in {"high", "critical"}:
                high_ambiguity_count += 1
            elif severity == "medium":
                medium_ambiguity_count += 1

        coverage_gap_count = 0
        for row in coverage_list:
            if not isinstance(row, dict):
                continue
            intent_ids = row.get("intent_ids")
            traceability = str(row.get("traceability_status", "")).strip().lower()
            has_links = isinstance(intent_ids, list) and bool(intent_ids)
            if traceability == "gap" or not has_links:
                coverage_gap_count += 1
        coverage_gap_ratio = (
            round(coverage_gap_count / max(1, len(coverage_list)), 2)
            if coverage_list
            else (1.0 if not intent_list else 0.0)
        )

        parse_confidence = requirement_spec.get("parse_confidence", 0.0)
        try:
            parse_confidence_value = float(parse_confidence)
        except Exception:
            parse_confidence_value = 0.0

        has_design_input = bool(str(requirement_spec.get("design_input", "")).strip())
        has_page = bool(str(requirement_spec.get("page", "")).strip())

        blockers: list[dict[str, Any]] = []
        if len(intent_list) < max(1, self.requirement_min_test_intents):
            blockers.append(
                self._build_requirement_quality_blocker(
                    code="insufficient_test_intents",
                    message=f"test_intents below threshold: {len(intent_list)} < {max(1, self.requirement_min_test_intents)}",
                    value=len(intent_list),
                    threshold=max(1, self.requirement_min_test_intents),
                )
            )
        if parse_confidence_value < self.requirement_min_parse_confidence:
            blockers.append(
                self._build_requirement_quality_blocker(
                    code="low_parse_confidence",
                    message=f"parse_confidence below threshold: {round(parse_confidence_value, 2)} < {self.requirement_min_parse_confidence}",
                    value=round(parse_confidence_value, 2),
                    threshold=self.requirement_min_parse_confidence,
                )
            )
        if self.requirement_block_high_ambiguity and high_ambiguity_count > 0:
            blockers.append(
                self._build_requirement_quality_blocker(
                    code="high_ambiguity_present",
                    message=f"high ambiguity present: {high_ambiguity_count}",
                    value=high_ambiguity_count,
                    threshold=0,
                )
            )
        if coverage_gap_ratio > self.requirement_max_coverage_gap_ratio:
            blockers.append(
                self._build_requirement_quality_blocker(
                    code="coverage_gap_ratio_high",
                    message=f"coverage_gap_ratio above threshold: {coverage_gap_ratio} > {self.requirement_max_coverage_gap_ratio}",
                    value=coverage_gap_ratio,
                    threshold=self.requirement_max_coverage_gap_ratio,
                )
            )
        if not has_design_input:
            blockers.append(
                self._build_requirement_quality_blocker(
                    code="missing_design_input",
                    message="design_input is empty",
                    value=has_design_input,
                    threshold=True,
                )
            )
        if not has_page:
            blockers.append(
                self._build_requirement_quality_blocker(
                    code="missing_page_resolution",
                    message="page is empty",
                    value=has_page,
                    threshold=True,
                )
            )

        return {
            "version": "RequirementQualityGateV1",
            "stage": stage,
            "gate_enabled": bool(self.requirement_quality_gate_enabled),
            "decision": "block" if blockers else "allow",
            "blockers": blockers,
            "metrics": {
                "parse_confidence": round(parse_confidence_value, 2),
                "intent_count": len(intent_list),
                "high_ambiguity_count": high_ambiguity_count,
                "medium_ambiguity_count": medium_ambiguity_count,
                "coverage_row_count": len(coverage_list),
                "coverage_gap_count": coverage_gap_count,
                "coverage_gap_ratio": coverage_gap_ratio,
                "has_design_input": has_design_input,
                "has_page": has_page,
                "blocker_codes": [str(item.get("code", "")).strip() for item in blockers if isinstance(item, dict)],
            },
            "thresholds": {
                "min_parse_confidence": self.requirement_min_parse_confidence,
                "min_test_intents": max(1, self.requirement_min_test_intents),
                "block_high_ambiguity": bool(self.requirement_block_high_ambiguity),
                "max_coverage_gap_ratio": self.requirement_max_coverage_gap_ratio,
            },
        }

    def _attach_requirement_quality_gate(self, requirement_spec: dict[str, Any], *, stage: str) -> dict[str, Any]:
        gate = self._build_requirement_quality_gate(requirement_spec, stage=stage)
        requirement_spec["quality_gate"] = gate
        return gate

    def _build_requirement_quality_blocker(
        self,
        *,
        code: str,
        message: str,
        value: Any = None,
        threshold: Any = None,
    ) -> dict[str, Any]:
        catalog = self.REQUIREMENT_QUALITY_BLOCKER_CATALOG.get(code, {})
        blocker: dict[str, Any] = {
            "code": code,
            "message": message,
            "category": str(catalog.get("category", "unknown")),
            "severity": str(catalog.get("severity", "medium")),
            "alert_code": str(catalog.get("alert_code", f"REQQG_{code.upper()}")),
            "metric_key": str(catalog.get("metric_key", "")),
        }
        if value is not None:
            blocker["value"] = value
        if threshold is not None:
            blocker["threshold"] = threshold
        return blocker

    def _enforce_requirement_quality_gate(self, requirement_spec: dict[str, Any], *, stage: str) -> None:
        gate = self._attach_requirement_quality_gate(requirement_spec, stage=stage)
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
        items: list[str] = []
        normalized_raw = str(raw_requirement).strip()
        if normalized_raw:
            items.append(normalized_raw)

        intents = requirement_spec.get("test_intents") or []
        if isinstance(intents, list):
            for intent in intents[:5]:
                if not isinstance(intent, dict):
                    continue
                title = str(intent.get("title", "")).strip()
                priority = str(intent.get("priority", "")).strip()
                if not title:
                    continue
                line = f"测试点({priority or 'P1'}): {title}"
                if line not in items:
                    items.append(line)
        return items or [normalized_raw or "基础流程验证"]

    def _generate_script_bundle(
        self,
        *,
        case: dict[str, Any],
        framework: str,
        language: str,
    ) -> dict[str, Any]:
        payload = {
            "framework": framework,
            "language": language,
            "case": case,
        }
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(json.dumps(payload, ensure_ascii=False))
            completed = subprocess.run(
                [sys.executable, "-m", "src.index", "--input", str(temp_path)],
                cwd=str(self.script_generation_root),
                text=True,
                capture_output=True,
                check=False,
            )
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "script generation failed")
            parsed = json.loads(completed.stdout.strip() or "{}")
            if not isinstance(parsed, dict):
                raise RuntimeError("script generation returned non-object payload")
            script_code = str(parsed.get("script_code", "")).strip()
            filename = str(parsed.get("filename", "")).strip()
            if script_code and filename:
                self.generated_scripts_root.mkdir(parents=True, exist_ok=True)
                output_path = self.generated_scripts_root / filename
                output_path.write_text(script_code + "\n", encoding="utf-8")
                parsed["script_path"] = str(output_path)
            return parsed
        except Exception as exc:
            return {
                "version": "GeneratedScriptV1",
                "framework": framework,
                "language": language,
                "case_id": str(case.get("id", "")).strip(),
                "page": str((case.get("execution") or {}).get("page", "")).strip(),
                "filename": "",
                "entrypoint": "",
                "script_code": "",
                "script_path": "",
                "metadata": {"error": str(exc)},
            }

    def _build_execution_plan(
        self,
        *,
        case: dict[str, Any],
        execution_requested: bool,
        source: str,
        execution_config: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "case": case,
            "execution_requested": execution_requested,
            "source": source,
            "execution_config": execution_config,
        }
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(json.dumps(payload, ensure_ascii=False))
            completed = subprocess.run(
                [sys.executable, "-m", "src.index", "--input", str(temp_path)],
                cwd=str(self.execution_planner_root),
                text=True,
                capture_output=True,
                check=False,
            )
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "execution planner failed")
            parsed = json.loads(completed.stdout.strip() or "{}")
            if not isinstance(parsed, dict):
                raise RuntimeError("execution planner returned non-object payload")
            return parsed
        except Exception as exc:
            return {
                "version": "ExecutionPlanV1",
                "run_mode": "generate_and_run" if execution_requested else "generate_only",
                "source": source,
                "priority": str(case.get("priority", "P1")).strip() or "P1",
                "environment": "test",
                "parallelism": 1,
                "retry_policy": {"enabled": bool(execution_requested), "max_retries": 1, "backoff_seconds": 5},
                "stages": [],
                "scheduling_hints": {"queue": "normal", "expected_total_seconds": 60, "resource_profile": "default"},
                "metadata": {"error": str(exc)},
            }

    def _evaluate_risk_report(
        self,
        *,
        requirement_spec: dict[str, Any],
        execution_plan: dict[str, Any],
        execution_record: dict[str, Any],
        failure_analysis: dict[str, Any],
        failure_triage: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "requirement_spec": requirement_spec,
            "execution_plan": execution_plan,
            "execution_record": execution_record,
            "failure_analysis": failure_analysis,
            "failure_triage": failure_triage,
        }
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(json.dumps(payload, ensure_ascii=False))
            completed = subprocess.run(
                [sys.executable, "-m", "src.index", "--input", str(temp_path)],
                cwd=str(self.risk_evaluation_root),
                text=True,
                capture_output=True,
                check=False,
            )
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "risk evaluation failed")
            parsed = json.loads(completed.stdout.strip() or "{}")
            if not isinstance(parsed, dict):
                raise RuntimeError("risk evaluation returned non-object payload")
            return parsed
        except Exception as exc:
            status = str(execution_record.get("status", "generated")).lower()
            fallback_decision = "allow" if status in {"passed", "generated"} else "manual_review"
            return {
                "version": "RiskReportV1",
                "risk_score": 55 if fallback_decision == "manual_review" else 30,
                "risk_level": "medium" if fallback_decision == "manual_review" else "low",
                "gate_decision": fallback_decision,
                "recommendation": "风险评估代理暂不可用，建议人工复核。",
                "factors": [{"factor": "agent_unavailable", "score": 20, "reason": str(exc)}],
                "metadata": {"fallback": True},
            }

    def _triage_failure(
        self,
        *,
        failure_analysis: dict[str, Any],
        execution_record: dict[str, Any],
        evidence_manifest: dict[str, Any],
        report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "failure_analysis": failure_analysis,
            "execution_record": execution_record,
            "evidence_manifest": evidence_manifest,
            "report": report or {},
        }
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(json.dumps(payload, ensure_ascii=False))
            completed = subprocess.run(
                [sys.executable, "-m", "src.index", "--input", str(temp_path)],
                cwd=str(self.failure_triage_root),
                text=True,
                capture_output=True,
                check=False,
            )
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "failure triage failed")
            parsed = json.loads(completed.stdout.strip() or "{}")
            if not isinstance(parsed, dict):
                raise RuntimeError("failure triage returned non-object payload")
            return parsed
        except Exception as exc:
            category = str(failure_analysis.get("failure_category", "unknown")).strip().lower() or "unknown"
            risk_level = str(failure_analysis.get("risk_level", "medium")).strip().lower() or "medium"
            status = str(execution_record.get("status", "generated")).strip().lower() or "generated"
            return {
                "version": "FailureTriageV1",
                "triage_label": f"{category}:{risk_level}:{status}",
                "failure_class": category,
                "severity": "S2" if status == "failed" else "S4",
                "owner_team": "qa-triage",
                "queue": "manual-triage",
                "bucket_key": f"{category}|fallback",
                "duplicate_of": "",
                "requires_manual_review": True,
                "confidence": 0.3,
                "signals": {
                    "status": status,
                    "risk_level": risk_level,
                    "evidence_total_files": int(evidence_manifest.get("total_files", 0) or 0),
                },
                "actions": [
                    {
                        "action": "create_ticket:manual-triage",
                        "owner": "qa-triage",
                        "reason": "分诊代理不可用，回退到人工分诊。",
                    }
                ],
                "metadata": {"fallback": True, "error": str(exc)},
            }

    def _enrich_failure_triage_with_history(
        self,
        *,
        triage: dict[str, Any],
        case_id: str,
        page: str,
        started_at: str,
    ) -> dict[str, Any]:
        if not isinstance(triage, dict):
            triage = {}
        current_case_id = str(case_id).strip()
        current_page = str(page).strip()
        current_bucket = str(triage.get("bucket_key", "")).strip().lower()
        current_class = str(triage.get("failure_class", "unknown")).strip().lower() or "unknown"
        current_started_at = str(started_at).strip() or self._now()

        similarity_candidates: list[dict[str, Any]] = []
        for report in self._iter_recent_reports(limit=200):
            candidate_case_id = str(report.get("case_id", "")).strip()
            if not candidate_case_id or candidate_case_id == current_case_id:
                continue
            candidate_status = str(report.get("status", "")).strip().lower()
            if candidate_status not in {"failed", "broken", "coverage_gap"}:
                continue

            candidate_triage = report.get("failure_triage", {})
            if not isinstance(candidate_triage, dict):
                continue
            candidate_bucket = str(candidate_triage.get("bucket_key", "")).strip().lower()
            candidate_class = str(candidate_triage.get("failure_class", "unknown")).strip().lower()
            candidate_page = str(report.get("page", "")).strip()
            same_bucket = bool(current_bucket and candidate_bucket and current_bucket == candidate_bucket)
            same_class_page = candidate_class == current_class and candidate_page == current_page and bool(current_page)
            if not same_bucket and not same_class_page:
                continue

            similarity_candidates.append(
                {
                    "case_id": candidate_case_id,
                    "status": candidate_status,
                    "started_at": str(report.get("started_at", "")).strip(),
                    "risk_level": str((report.get("risk_report", {}) or {}).get("risk_level", "")).strip(),
                    "bucket_key": candidate_bucket,
                }
            )

        similarity_candidates.sort(key=lambda item: item.get("started_at", ""))
        similar_cases = similarity_candidates[-10:]
        duplicate_of = str(triage.get("duplicate_of", "")).strip()
        if not duplicate_of and similar_cases:
            duplicate_of = similar_cases[-1]["case_id"]

        cluster_seed = current_bucket or f"{current_class}|{current_page or 'unknown-page'}"
        cluster_id = f"cluster-{hashlib.sha1(cluster_seed.encode('utf-8')).hexdigest()[:12]}"
        occurrence_count = len(similarity_candidates) + 1
        first_seen_at = similarity_candidates[0]["started_at"] if similarity_candidates and similarity_candidates[0].get("started_at") else current_started_at
        last_seen_at = current_started_at

        triage["cluster_id"] = cluster_id
        triage["occurrence_count"] = occurrence_count
        triage["first_seen_at"] = first_seen_at
        triage["last_seen_at"] = last_seen_at
        triage["similar_cases"] = similar_cases
        triage["duplicate_of"] = duplicate_of
        metadata = triage.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        metadata["history_enriched"] = True
        metadata["history_sample_size"] = len(similarity_candidates)
        triage["metadata"] = metadata
        return triage

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
            except Exception:
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return records

    def _normalize_test_point_plan(self, payload: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
        try:
            from shared_backend.schemas import normalize_test_point_plan_v1

            normalized, warnings = normalize_test_point_plan_v1(payload, strict=strict)
            for warning in warnings:
                self.logger.warning("test_point_plan normalization warning: %s", warning)
            return normalized
        except Exception as exc:
            self.logger.warning("test_point_plan normalization unavailable, keep raw payload: %s", exc)
            return payload if isinstance(payload, dict) else {}

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

    def _generate_case(self, requirement: str, page: str) -> dict[str, Any]:
        if str(self.agent_root) not in sys.path:
            sys.path.insert(0, str(self.agent_root))

        from src.agent import TestDesignAgent
        from src.tools.yaml_writer import save_yaml  # noqa: F401

        agent = TestDesignAgent()
        normalized_page = str(page).strip() or "product"
        try:
            generated = agent.generate(requirement=requirement, page=normalized_page)
            if isinstance(generated, dict) and generated:
                return generated
        except Exception as exc:
            return self._build_design_fallback_case(
                requirement=requirement,
                page=normalized_page,
                reason=str(exc),
            )
        return self._build_design_fallback_case(
            requirement=requirement,
            page=normalized_page,
            reason="test-design-agent returned empty payload",
        )

    def _build_design_fallback_case(self, *, requirement: str, page: str, reason: str) -> dict[str, Any]:
        normalized_page = str(page).strip() or "product"
        case_id = f"SMOKE-{normalized_page.upper()}-{datetime.now(UTC).strftime('%H%M%S')}"
        menu_target = f"{normalized_page}_menu"
        title_target = f"{normalized_page}_list_title"
        safe_requirement = str(requirement or "").strip() or f"{normalized_page} 页面核心流程验证"
        return {
            "version": "v4",
            "id": case_id,
            "title": f"SMOKE-{normalized_page.upper()}-FALLBACK",
            "module": normalized_page,
            "priority": "P1",
            "tags": ["ai-generated", "smoke", normalized_page, "fallback"],
            "owner": "qa-team",
            "status": "automated",
            "description": f"Fallback case generated because test-design-agent failed: {reason[:200]}",
            "requirement": [safe_requirement],
            "data": {},
            "execution": {
                "runner": "playwright",
                "page": normalized_page,
                "variables": {},
                "steps": [
                    {"action": "login"},
                    {"action": "click", "target": menu_target},
                    {"action": "wait_for", "target": title_target},
                    {"action": "assert_visible", "target": title_target},
                ],
            },
        }

    def _build_design_generation(self, case: dict[str, Any]) -> dict[str, Any]:
        tags = [str(item).strip().lower() for item in (case.get("tags") or []) if str(item).strip()]
        description = str(case.get("description", "")).strip()
        lowered_description = description.lower()
        fallback_used = ("fallback" in tags) or ("fallback case generated because test-design-agent failed" in lowered_description)
        fallback_reason = ""
        marker = "failed:"
        if fallback_used and marker in lowered_description:
            original_parts = description.split("failed:", 1)
            if len(original_parts) > 1:
                fallback_reason = original_parts[1].strip()
        if fallback_used and not fallback_reason:
            fallback_reason = "test-design-agent returned fallback case"
        return {
            "generator": "test-design-agent",
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
        }

    def _build_test_points_preview(
        self,
        *,
        case: dict[str, Any],
        requirement_spec: dict[str, Any],
    ) -> dict[str, Any]:
        intent_based = self._build_test_points_from_requirement_spec(
            case=case,
            requirement_spec=requirement_spec,
        )
        if intent_based.get("points"):
            return self._apply_constraint_summary_to_test_points(intent_based, requirement_spec=requirement_spec)
        return self._apply_constraint_summary_to_test_points(
            self._build_test_points_from_execution_steps(case),
            requirement_spec=requirement_spec,
        )

    def _build_test_points_from_execution_steps(self, case: dict[str, Any]) -> dict[str, Any]:
        if str(self.agent_root) not in sys.path:
            sys.path.insert(0, str(self.agent_root))

        from src.test_points import build_test_point_plan

        requirement = case.get("requirement") or []
        if isinstance(requirement, str):
            requirement = [requirement]

        execution = case.get("execution", {})
        plan = build_test_point_plan(
            page=execution.get("page", ""),
            requirement=requirement,
            steps=execution.get("steps", []),
        )
        raw_plan = plan.model_dump(exclude_none=True)
        payload = {
            "version": "TestPointPlanV1",
            "project": "default",
            "case_id": str(case.get("id", "")).strip(),
            "page": str(execution.get("page", "")).strip(),
            "source_type": "execution_steps",
            "requirement": requirement,
            "points": raw_plan.get("points", []),
            "generated_at": self._now(),
            "metadata": {
                "upstream_schema": str(raw_plan.get("version", "")).strip(),
                "point_count": len(raw_plan.get("points", [])) if isinstance(raw_plan.get("points"), list) else 0,
                "build_source": "execution_steps",
            },
        }
        return self._normalize_test_point_plan(payload)

    def _build_test_points_from_requirement_spec(
        self,
        *,
        case: dict[str, Any],
        requirement_spec: dict[str, Any],
    ) -> dict[str, Any]:
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        page = str(execution.get("page", "")).strip() or str(requirement_spec.get("page", "")).strip() or "product"
        case_id = str(case.get("id", "")).strip()
        requirement = case.get("requirement")
        if isinstance(requirement, str):
            requirement_rows = [requirement]
        elif isinstance(requirement, list):
            requirement_rows = [str(item).strip() for item in requirement if str(item).strip()]
        else:
            requirement_rows = []
        if not requirement_rows:
            requirement_rows = [str(requirement_spec.get("raw_requirement", "")).strip() or str(requirement_spec.get("design_input", "")).strip()]
            requirement_rows = [row for row in requirement_rows if row]

        intents = requirement_spec.get("test_intents") if isinstance(requirement_spec.get("test_intents"), list) else []
        points: list[dict[str, Any]] = [
            {
                "key": f"{page}-00",
                "point_type": "precondition",
                "action": "login",
                "description": "Use shared login precondition.",
                "priority": "P0",
                "dependencies": [],
                "source_ids": [],
            }
        ]
        for index, intent in enumerate(intents[:80], start=1):
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
            point = {
                "key": str(intent.get("intent_id", f"intent-{index:02d}")).strip() or f"intent-{index:02d}",
                "point_type": self._map_intent_type_to_point_type(intent_type),
                "action": action,
                "description": title[:200],
                "priority": priority,
                "dependencies": [str(item).strip() for item in dependencies if str(item).strip()],
                "source_ids": [str(item).strip() for item in source_ids if str(item).strip()],
            }
            if target:
                point["target"] = target
            if value is not None:
                point["value"] = value
            points.append(point)

        payload = {
            "version": "TestPointPlanV1",
            "project": "default",
            "case_id": case_id,
            "page": page,
            "source_type": "requirement_intents",
            "requirement": requirement_rows,
            "generated_at": self._now(),
            "points": points,
            "metadata": {
                "build_source": "requirement_spec.test_intents",
                "intent_count": len(intents),
                "point_count": len(points),
            },
        }
        return self._normalize_test_point_plan(payload)

    def _apply_constraint_summary_to_test_points(
        self,
        test_points: dict[str, Any],
        *,
        requirement_spec: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(test_points) if isinstance(test_points, dict) else {}
        metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
        metadata = dict(metadata)
        review_summary = normalized.get("review_summary") if isinstance(normalized.get("review_summary"), dict) else {}
        review_summary = dict(review_summary)
        points = normalized.get("points") if isinstance(normalized.get("points"), list) else []
        summary = self._build_constraint_technique_summary(requirement_spec=requirement_spec, current_points=points)
        metadata["technique_summary"] = summary
        metadata["field_definition_count"] = int(summary.get("field_definition_count", 0) or 0)
        metadata["parameter_constraint_count"] = int(summary.get("parameter_constraint_count", 0) or 0)
        review_summary.setdefault("mainline_point_count", len([point for point in points if isinstance(point, dict)]))
        normalized["metadata"] = metadata
        normalized["review_summary"] = review_summary
        return normalized

    def _build_constraint_technique_summary(
        self,
        *,
        requirement_spec: dict[str, Any],
        current_points: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        field_definitions = requirement_spec.get("field_definitions") if isinstance(requirement_spec.get("field_definitions"), list) else []
        parameter_constraints = requirement_spec.get("parameter_constraints") if isinstance(requirement_spec.get("parameter_constraints"), list) else []
        normalized_items = [item for item in [*field_definitions, *parameter_constraints] if isinstance(item, dict)]
        technique_distribution: dict[str, int] = {}
        api_parameter_count = 0
        field_definition_count = 0
        parameter_constraint_count = 0
        design_only_point_count = 0

        for item in normalized_items[:60]:
            field_type = str(item.get("field_type", "")).strip().lower() or str(item.get("type", "")).strip().lower() or "string"
            constraints = item.get("constraints") if isinstance(item.get("constraints"), dict) else {}
            format_hint = str(item.get("format", constraints.get("format", ""))).strip().lower()
            if field_type == "string" and format_hint in {"date", "date-time", "datetime", "timestamp"}:
                field_type = "datetime" if format_hint in {"date-time", "datetime", "timestamp"} else "date"
            is_parameter = bool(str(item.get("location", "")).strip() or str(item.get("in", "")).strip())
            if is_parameter:
                parameter_constraint_count += 1
                api_parameter_count += 1
            else:
                field_definition_count += 1

            equivalence_count = 0
            boundary_count = 0
            enum_values = item.get("enum") if isinstance(item.get("enum"), list) else constraints.get("enum") if isinstance(constraints.get("enum"), list) else []
            if bool(item.get("required", False)):
                equivalence_count += 1
            if enum_values:
                equivalence_count += 2
            if field_type in {"string", "text", "keyword", "search"}:
                if self._safe_int(item.get("min_length", constraints.get("min_length", constraints.get("minLength")))) not in (None, 0):
                    boundary_count += 1
                if self._safe_int(item.get("max_length", constraints.get("max_length", constraints.get("maxLength")))) not in (None, 0):
                    boundary_count += 1
            elif field_type in {"integer", "number", "decimal", "float", "amount", "price", "currency_amount"}:
                if self._safe_float(item.get("min", constraints.get("min", constraints.get("minimum")))) is not None:
                    boundary_count += 1
                if self._safe_float(item.get("max", constraints.get("max", constraints.get("maximum")))) is not None:
                    boundary_count += 1
                if field_type in {"decimal", "float", "amount", "price", "currency_amount"}:
                    equivalence_count += 1
            elif field_type in {"date", "datetime", "timestamp"}:
                boundary_count += 2
                equivalence_count += 1

            if boundary_count:
                technique_distribution["boundary"] = technique_distribution.get("boundary", 0) + boundary_count
                design_only_point_count += boundary_count
            if equivalence_count:
                technique_distribution["equivalence"] = technique_distribution.get("equivalence", 0) + equivalence_count
                design_only_point_count += equivalence_count

        current_mainline_point_count = len([point for point in (current_points or []) if isinstance(point, dict)])
        return {
            "field_definition_count": int(field_definition_count),
            "parameter_constraint_count": int(parameter_constraint_count),
            "api_parameter_count": int(api_parameter_count),
            "mainline_point_count": int(current_mainline_point_count),
            "design_only_point_count": int(design_only_point_count),
            "technique_distribution": dict(sorted(technique_distribution.items())),
            "has_structured_constraints": bool(field_definition_count or parameter_constraint_count),
            "source": "requirement_spec.constraints",
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
            return "assert_visible", f"{page}_list_title", None
        if any(item in {"search", "query"} for item in hints) or any(token in lowered_title for token in ["搜索", "查询", "筛选"]):
            return "fill", "search_input", "3"
        if any(item in {"create", "update", "delete", "submit", "approve"} for item in hints):
            return "click", f"{page}_menu", None
        if any(item in {"assert", "negative", "regression", "smoke"} for item in hints):
            return "assert_visible", f"{page}_list_title", None
        return "wait_for", f"{page}_list_title", None

    def _render_case_steps_from_test_points(self, *, case: dict[str, Any], test_points: dict[str, Any]) -> dict[str, Any]:
        rendered = dict(case)
        execution = rendered.get("execution") if isinstance(rendered.get("execution"), dict) else {}
        existing_steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
        if existing_steps and not self.test_point_steps_authoritative:
            return rendered

        points = test_points.get("points") if isinstance(test_points.get("points"), list) else []
        steps: list[dict[str, Any]] = []
        for point in points:
            if not isinstance(point, dict):
                continue
            action = str(point.get("action", "")).strip()
            if not action:
                continue
            step: dict[str, Any] = {"action": action}
            target = str(point.get("target", "")).strip()
            if target:
                step["target"] = target
            if "value" in point and point.get("value") is not None:
                step["value"] = point.get("value")
            if steps and steps[-1] == step:
                continue
            steps.append(step)
        if steps:
            execution = dict(execution)
            execution["steps"] = steps
            rendered["execution"] = execution
        return rendered

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
        if str(self.runner_root) not in sys.path:
            sys.path.insert(0, str(self.runner_root))

    def _build_report_summary_path(self) -> str:
        self._ensure_runner_import_path()
        from tools.report_summary import build_report_summary

        summary_path = build_report_summary(
            self.runner_root / "artifacts",
            self.runner_root / "artifacts" / "report_summary.txt",
        )
        return str(summary_path)

    def _run_case(self, case_id: str, case_path: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["RUN_MODE"] = "ai"
        env["TEST_CASE_ID"] = case_id
        env["TEST_CASE_PATH"] = str(case_path)

        return subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_yaml_ai_generated.py"],
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
        if not str(parsed.get("page", "")).strip():
            parsed["page"] = page.strip() or "product"
        self._attach_requirement_quality_gate(parsed, stage="parse")
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
        normalized_limit = max(1, min(int(limit), 5000))
        normalized_prompt_version = str(prompt_version).strip()
        normalized_model = str(model).strip()
        normalized_mode = str(mode).strip().lower()
        normalized_stage = str(stage).strip().lower()

        events = self._iter_requirement_parse_telemetry_events(limit=normalized_limit)
        filtered: list[dict[str, Any]] = []
        for event in events:
            parser_runtime = event.get("parser_runtime")
            runtime = parser_runtime if isinstance(parser_runtime, dict) else {}
            event_stage = str(event.get("stage", "")).strip().lower()
            event_prompt_version = str(runtime.get("prompt_version", "")).strip()
            event_model = str(runtime.get("model", "")).strip()
            event_mode = str(runtime.get("mode", "")).strip().lower()
            if normalized_stage and event_stage != normalized_stage:
                continue
            if normalized_prompt_version and event_prompt_version != normalized_prompt_version:
                continue
            if normalized_model and event_model != normalized_model:
                continue
            if normalized_mode and event_mode != normalized_mode:
                continue
            filtered.append(event)

        allow_count = 0
        blocked_count = 0
        llm_attempted_count = 0
        llm_succeeded_count = 0
        llm_fallback_count = 0
        groups: dict[str, dict[str, Any]] = {}

        for event in filtered:
            parser_runtime = event.get("parser_runtime")
            runtime = parser_runtime if isinstance(parser_runtime, dict) else {}
            llm_trace = event.get("llm_trace")
            llm = llm_trace if isinstance(llm_trace, dict) else {}
            decision = str(event.get("quality_gate_decision", "")).strip().lower() or "allow"
            blocked = decision == "block" or str(event.get("outcome", "")).strip().lower() == "block"

            if blocked:
                blocked_count += 1
            else:
                allow_count += 1
            if bool(llm.get("attempted", False)):
                llm_attempted_count += 1
            if bool(llm.get("succeeded", False)):
                llm_succeeded_count += 1
            if bool(llm.get("fallback_used", False)):
                llm_fallback_count += 1

            group_prompt = str(runtime.get("prompt_version", "")).strip() or "unknown"
            group_model = str(runtime.get("model", "")).strip() or "unknown"
            group_mode = str(runtime.get("mode", "")).strip().lower() or "rule_based"
            group_key = f"{group_prompt}|{group_model}|{group_mode}"
            group = groups.setdefault(
                group_key,
                {
                    "prompt_version": group_prompt,
                    "model": group_model,
                    "mode": group_mode,
                    "total": 0,
                    "allow_count": 0,
                    "blocked_count": 0,
                    "llm_attempted_count": 0,
                    "llm_succeeded_count": 0,
                    "llm_fallback_count": 0,
                },
            )
            group["total"] += 1
            if blocked:
                group["blocked_count"] += 1
            else:
                group["allow_count"] += 1
            if bool(llm.get("attempted", False)):
                group["llm_attempted_count"] += 1
            if bool(llm.get("succeeded", False)):
                group["llm_succeeded_count"] += 1
            if bool(llm.get("fallback_used", False)):
                group["llm_fallback_count"] += 1

        group_items = sorted(groups.values(), key=lambda item: int(item.get("total", 0)), reverse=True)
        for item in group_items:
            total = max(1, int(item.get("total", 0)))
            item["allow_rate"] = round(int(item.get("allow_count", 0)) / total, 3)
            item["llm_fallback_rate"] = round(int(item.get("llm_fallback_count", 0)) / total, 3)

        total_filtered = len(filtered)
        return {
            "version": "RequirementParseTelemetrySummaryV1",
            "generated_at": self._now(),
            "filters": {
                "limit": normalized_limit,
                "prompt_version": normalized_prompt_version,
                "model": normalized_model,
                "mode": normalized_mode,
                "stage": normalized_stage,
            },
            "total_events": total_filtered,
            "allow_count": allow_count,
            "blocked_count": blocked_count,
            "allow_rate": round(allow_count / max(1, total_filtered), 3),
            "llm_attempted_count": llm_attempted_count,
            "llm_succeeded_count": llm_succeeded_count,
            "llm_fallback_count": llm_fallback_count,
            "llm_fallback_rate": round(llm_fallback_count / max(1, total_filtered), 3),
            "groups": group_items[:100],
        }

    def _iter_requirement_parse_telemetry_events(self, *, limit: int) -> list[dict[str, Any]]:
        if not self.requirement_parse_telemetry_log.exists():
            return []
        events: list[dict[str, Any]] = []
        try:
            with self.requirement_parse_telemetry_log.open("r", encoding="utf-8") as handle:
                for line in handle:
                    text = str(line).strip()
                    if not text:
                        continue
                    try:
                        payload = json.loads(text)
                    except Exception:
                        continue
                    if isinstance(payload, dict):
                        events.append(payload)
        except Exception:
            return []
        if len(events) > limit:
            return events[-limit:]
        return events

    def _record_requirement_parse_telemetry(
        self,
        *,
        requirement_spec: dict[str, Any],
        stage: str,
        source: str,
        outcome: str,
    ) -> None:
        spec = requirement_spec if isinstance(requirement_spec, dict) else {}
        parser_runtime = spec.get("parser_runtime")
        runtime = parser_runtime if isinstance(parser_runtime, dict) else {}
        quality_gate = spec.get("quality_gate")
        gate = quality_gate if isinstance(quality_gate, dict) else {}
        blockers_raw = gate.get("blockers")
        blockers = blockers_raw if isinstance(blockers_raw, list) else []
        blocker_codes = [
            str(item.get("code", "")).strip()
            for item in blockers
            if isinstance(item, dict) and str(item.get("code", "")).strip()
        ][:20]
        llm_trace = runtime.get("llm_trace")
        llm = llm_trace if isinstance(llm_trace, dict) else {}
        try:
            parse_confidence = round(float(spec.get("parse_confidence", 0.0) or 0.0), 2)
        except Exception:
            parse_confidence = 0.0

        event = {
            "event_type": "requirement_parse_telemetry",
            "timestamp": self._now(),
            "stage": str(stage).strip().lower(),
            "source": str(source).strip().lower() or "manual",
            "outcome": str(outcome).strip().lower() or "allow",
            "page": str(spec.get("page", "")).strip(),
            "source_type": str(spec.get("source_type", "")).strip() or "text",
            "priority": str(spec.get("priority", "")).strip() or "P1",
            "parse_confidence": parse_confidence,
            "quality_gate_decision": str(gate.get("decision", "")).strip().lower() or "allow",
            "quality_gate_blocker_count": len(blocker_codes),
            "quality_gate_blocker_codes": blocker_codes,
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
                "total_tokens": llm.get("total_tokens"),
                "overlay_key_count": int(llm.get("overlay_key_count", 0) or 0),
            },
        }
        try:
            self.telemetry_root.mkdir(parents=True, exist_ok=True)
            with self.requirement_parse_telemetry_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            return

    def generate_script(
        self,
        *,
        case: dict[str, Any],
        framework: str = "playwright",
        language: str = "python",
    ) -> dict[str, Any]:
        if not isinstance(case, dict) or not case:
            raise OrchestratorValidationError("case must not be empty")
        return self._generate_script_bundle(case=case, framework=framework, language=language)

    def plan_execution(
        self,
        *,
        case: dict[str, Any],
        execution_requested: bool,
        source: str = "manual",
        execution_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(case, dict) or not case:
            raise OrchestratorValidationError("case must not be empty")
        return self._build_execution_plan(
            case=case,
            execution_requested=execution_requested,
            source=source,
            execution_config=execution_config or {},
        )

    def evaluate_risk(
        self,
        *,
        requirement_spec: dict[str, Any],
        execution_plan: dict[str, Any],
        execution_record: dict[str, Any],
        failure_analysis: dict[str, Any],
        failure_triage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
        spec = requirement_spec if isinstance(requirement_spec, dict) else {}
        page = str(spec.get("page", "")).strip() or "-"
        priority = str(spec.get("priority", "")).strip() or "P1"
        parse_confidence = spec.get("parse_confidence", 0)
        source_type = str(spec.get("source_type", "")).strip() or "manual"
        test_intents = spec.get("test_intents") if isinstance(spec.get("test_intents"), list) else []
        ambiguities = spec.get("ambiguities") if isinstance(spec.get("ambiguities"), list) else []
        business_rules = spec.get("business_rules") if isinstance(spec.get("business_rules"), list) else []
        quality_gate = spec.get("quality_gate") if isinstance(spec.get("quality_gate"), dict) else {}
        parser_runtime = spec.get("parser_runtime") if isinstance(spec.get("parser_runtime"), dict) else {}

        lines = [
            "# 需求测试点分析",
            "",
            "## 概览",
            f"- 来源: `{source_type}`",
            f"- 页面: `{page}`",
            f"- 优先级: `{priority}`",
            f"- 解析置信度: `{parse_confidence}`",
            f"- 测试点数量: `{len(test_intents)}`",
            f"- 规则数量: `{len(business_rules)}`",
            f"- 消歧数量: `{len(ambiguities)}`",
        ]

        if quality_gate:
            blockers = quality_gate.get("blockers") if isinstance(quality_gate.get("blockers"), list) else []
            lines.extend(
                [
                    "",
                    "## 质量门禁",
                    f"- 决策: `{str(quality_gate.get('decision', '')).strip() or '-'}`",
                    f"- 阶段: `{str(quality_gate.get('stage', '')).strip() or '-'}`",
                    f"- 阻断项数量: `{len(blockers)}`",
                ]
            )
            for index, blocker in enumerate(blockers[:10], start=1):
                if not isinstance(blocker, dict):
                    continue
                code = str(blocker.get("code", "")).strip() or "unknown"
                message = str(blocker.get("message", "")).strip() or "-"
                lines.append(f"- blocker-{index}: `{code}` {message}")

        if test_intents:
            lines.extend(["", "## 测试点"])
            for index, intent in enumerate(test_intents[:30], start=1):
                if not isinstance(intent, dict):
                    continue
                title = str(intent.get("title", "")).strip() or f"intent-{index:02d}"
                intent_type = str(intent.get("intent_type", "")).strip() or "functional"
                intent_priority = str(intent.get("priority", "")).strip() or "P1"
                lines.append(f"{index}. [{intent_priority}/{intent_type}] {title}")

        if business_rules:
            lines.extend(["", "## 业务规则"])
            for index, rule in enumerate(business_rules[:20], start=1):
                if isinstance(rule, dict):
                    text = str(rule.get("rule_text", "")).strip() or str(rule.get("text", "")).strip()
                else:
                    text = str(rule).strip()
                if text:
                    lines.append(f"{index}. {text}")

        if ambiguities:
            lines.extend(["", "## 待消歧"])
            for index, item in enumerate(ambiguities[:20], start=1):
                if not isinstance(item, dict):
                    text = str(item).strip()
                    if text:
                        lines.append(f"{index}. {text}")
                    continue
                text = str(item.get("text", "")).strip() or str(item.get("title", "")).strip() or "未命名歧义"
                suggestion = str(item.get("suggestion", "")).strip()
                if suggestion:
                    lines.append(f"{index}. {text} -> 建议: {suggestion}")
                else:
                    lines.append(f"{index}. {text}")

        if parser_runtime:
            lines.extend(
                [
                    "",
                    "## 解析运行信息",
                    f"- mode: `{str(parser_runtime.get('mode', '')).strip() or '-'}`",
                    f"- model: `{str(parser_runtime.get('model', '')).strip() or '-'}`",
                    f"- prompt_version: `{str(parser_runtime.get('prompt_version', '')).strip() or '-'}`",
                    f"- instructions_version: `{str(parser_runtime.get('instructions_version', '')).strip() or '-'}`",
                ]
            )
        return "\n".join(lines).strip() + "\n"

    def get_latest_report(self) -> dict[str, Any]:
        report_files = sorted(
            self.report_root.glob("*.report.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not report_files:
            raise OrchestratorValidationError("No execution reports found")
        return self.get_report(report_files[0].stem.removesuffix(".report"))

    def get_report(self, case_id: str) -> dict[str, Any]:
        normalized_case_id = case_id.strip()
        if not normalized_case_id:
            raise OrchestratorValidationError("case_id must not be empty")

        json_path = self.report_root / f"{normalized_case_id}.report.json"
        markdown_path = self.report_root / f"{normalized_case_id}.report.md"
        if not json_path.exists():
            raise OrchestratorValidationError(f"Execution report not found for case_id: {normalized_case_id}")

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        payload.setdefault("self_healing_suggestion_preview", self._load_self_healing_suggestion_preview(payload))
        report_summary_path = self.runner_root / "artifacts" / "report_summary.txt"
        return {
            "report": payload,
            "execution_record": payload.get("execution_record", {}),
            "report_json_path": str(json_path),
            "report_markdown_path": str(markdown_path),
            "report_summary_path": str(report_summary_path),
            "report_summary_preview": self._load_report_summary_preview(report_summary_path),
        }

    def get_failure_clusters(
        self,
        *,
        limit: int = 200,
        max_clusters: int = 20,
        queue: str = "",
        failure_class: str = "",
        severity: str = "",
    ) -> dict[str, Any]:
        normalized_limit = max(1, min(int(limit), 2000))
        normalized_max_clusters = max(1, min(int(max_clusters), 200))
        normalized_queue = str(queue).strip().lower()
        normalized_failure_class = str(failure_class).strip().lower()
        normalized_severity = str(severity).strip().upper()
        reports = self._iter_recent_reports(limit=normalized_limit)

        clusters: dict[str, dict[str, Any]] = {}
        total_failed_reports = 0
        queue_distribution: dict[str, int] = {}
        class_distribution: dict[str, int] = {}
        severity_distribution: dict[str, int] = {}

        for report in reports:
            status = str(report.get("status", "")).strip().lower()
            if status not in {"failed", "broken", "coverage_gap"}:
                continue
            total_failed_reports += 1

            triage = report.get("failure_triage", {})
            if not isinstance(triage, dict):
                triage = {}
            failure_analysis = report.get("failure_analysis", {})
            if not isinstance(failure_analysis, dict):
                failure_analysis = {}

            case_id = str(report.get("case_id", "")).strip()
            page = str(report.get("page", "")).strip()
            started_at = str(report.get("started_at", "")).strip()
            risk_level = str((report.get("risk_report", {}) or {}).get("risk_level", "")).strip().lower()
            queue = str(triage.get("queue", "")).strip() or "manual-triage"
            severity = str(triage.get("severity", "")).strip().upper() or "S4"
            failure_class = str(triage.get("failure_class", "")).strip().lower() or str(failure_analysis.get("failure_category", "unknown")).strip().lower() or "unknown"
            owner_team = str(triage.get("owner_team", "")).strip() or "qa-triage"
            bucket_key = str(triage.get("bucket_key", "")).strip().lower()
            cluster_id = str(triage.get("cluster_id", "")).strip()

            if not cluster_id:
                cluster_seed = bucket_key or f"{failure_class}|{page or 'unknown-page'}"
                cluster_id = f"cluster-{hashlib.sha1(cluster_seed.encode('utf-8')).hexdigest()[:12]}"

            row = clusters.setdefault(
                cluster_id,
                {
                    "cluster_id": cluster_id,
                    "failure_class": failure_class,
                    "page": page,
                    "queue": queue,
                    "owner_team": owner_team,
                    "severity": severity,
                    "bucket_key": bucket_key,
                    "occurrence_count": 0,
                    "first_seen_at": started_at,
                    "last_seen_at": started_at,
                    "latest_case_id": case_id,
                    "requires_manual_review_count": 0,
                    "risk_level_count": {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0},
                    "sample_cases": [],
                },
            )

            row["occurrence_count"] += 1
            if bool(triage.get("requires_manual_review", False)):
                row["requires_manual_review_count"] += 1

            current_first = str(row.get("first_seen_at", "")).strip()
            current_last = str(row.get("last_seen_at", "")).strip()
            if started_at:
                if not current_first or started_at < current_first:
                    row["first_seen_at"] = started_at
                if not current_last or started_at > current_last:
                    row["last_seen_at"] = started_at
                    row["latest_case_id"] = case_id or row.get("latest_case_id", "")

            if risk_level not in {"critical", "high", "medium", "low"}:
                risk_level = "unknown"
            row["risk_level_count"][risk_level] = int(row["risk_level_count"].get(risk_level, 0)) + 1

            row["sample_cases"].append(
                {
                    "case_id": case_id,
                    "status": status,
                    "page": page,
                    "started_at": started_at,
                    "risk_level": risk_level,
                    "severity": severity,
                    "queue": queue,
                }
            )

            queue_distribution[queue] = queue_distribution.get(queue, 0) + 1
            class_distribution[failure_class] = class_distribution.get(failure_class, 0) + 1
            severity_distribution[severity] = severity_distribution.get(severity, 0) + 1

        rows: list[dict[str, Any]] = []
        for row in clusters.values():
            sample_cases = sorted(
                row["sample_cases"],
                key=lambda item: str(item.get("started_at", "")),
                reverse=True,
            )[:5]
            risk_level_count = row["risk_level_count"]
            top_risk_level = max(
                ["critical", "high", "medium", "low", "unknown"],
                key=lambda level: int(risk_level_count.get(level, 0)),
            )
            occurrence_count = int(row["occurrence_count"])
            requires_manual_review_count = int(row["requires_manual_review_count"])
            manual_review_ratio = round(requires_manual_review_count / occurrence_count, 2) if occurrence_count > 0 else 0.0

            rows.append(
                {
                    "cluster_id": row["cluster_id"],
                    "failure_class": row["failure_class"],
                    "page": row["page"],
                    "queue": row["queue"],
                    "owner_team": row["owner_team"],
                    "severity": row["severity"],
                    "bucket_key": row["bucket_key"],
                    "occurrence_count": occurrence_count,
                    "first_seen_at": row["first_seen_at"],
                    "last_seen_at": row["last_seen_at"],
                    "latest_case_id": row["latest_case_id"],
                    "requires_manual_review_count": requires_manual_review_count,
                    "manual_review_ratio": manual_review_ratio,
                    "top_risk_level": top_risk_level,
                    "risk_level_count": risk_level_count,
                    "sample_cases": sample_cases,
                }
            )

        if normalized_queue:
            rows = [item for item in rows if str(item.get("queue", "")).strip().lower() == normalized_queue]
        if normalized_failure_class:
            rows = [
                item
                for item in rows
                if str(item.get("failure_class", "")).strip().lower() == normalized_failure_class
            ]
        if normalized_severity:
            rows = [item for item in rows if str(item.get("severity", "")).strip().upper() == normalized_severity]

        severity_rank = {"S0": 5, "S1": 4, "S2": 3, "S3": 2, "S4": 1}
        risk_rank = {"critical": 5, "high": 4, "medium": 3, "low": 2, "unknown": 1}
        rows.sort(
            key=lambda item: (
                severity_rank.get(str(item.get("severity", "S4")).upper(), 0),
                risk_rank.get(str(item.get("top_risk_level", "unknown")).lower(), 0),
                int(item.get("occurrence_count", 0)),
                str(item.get("last_seen_at", "")),
            ),
            reverse=True,
        )
        rows = rows[:normalized_max_clusters]

        return {
            "generated_at": self._now(),
            "total_failed_reports": total_failed_reports,
            "total_clusters": len(rows),
            "clusters": rows,
            "queue_distribution": [{"queue": key, "count": value} for key, value in sorted(queue_distribution.items(), key=lambda item: item[1], reverse=True)],
            "class_distribution": [{"failure_class": key, "count": value} for key, value in sorted(class_distribution.items(), key=lambda item: item[1], reverse=True)],
            "severity_distribution": [{"severity": key, "count": value} for key, value in sorted(severity_distribution.items(), key=lambda item: item[1], reverse=True)],
            "filters": {
                "queue": normalized_queue,
                "failure_class": normalized_failure_class,
                "severity": normalized_severity,
            },
        }

    def get_failure_cluster(self, *, cluster_id: str, limit: int = 200) -> dict[str, Any]:
        normalized_cluster_id = str(cluster_id).strip()
        if not normalized_cluster_id:
            raise OrchestratorValidationError("cluster_id must not be empty")
        cluster_payload = self.get_failure_clusters(limit=limit, max_clusters=200)
        for cluster in cluster_payload.get("clusters", []):
            if str(cluster.get("cluster_id", "")).strip() == normalized_cluster_id:
                return {
                    "generated_at": cluster_payload.get("generated_at", self._now()),
                    "cluster": cluster,
                }
        raise OrchestratorValidationError(f"Failure cluster not found: {normalized_cluster_id}")

    def _load_report_summary_preview(self, summary_path: Path) -> dict[str, Any]:
        preview = {
            "total_failed_cases": 0,
            "environment_failures": 0,
            "business_failures": 0,
            "high_risk_failures": 0,
            "actionable_self_healing_cases": 0,
            "environment_failure_cases": [],
            "actionable_self_healing_case_details": [],
        }
        if not summary_path.exists():
            return preview

        patterns = {
            "total_failed_cases": re.compile(r"^- Total Failed Cases: (\d+)$"),
            "environment_failures": re.compile(r"^- Environment Failures: (\d+)$"),
            "business_failures": re.compile(r"^- Business Failures: (\d+)$"),
            "high_risk_failures": re.compile(r"^- High Risk Failures: (\d+)$"),
            "actionable_self_healing_cases": re.compile(r"^- Cases With Actionable Self-Healing Advice: (\d+)$"),
        }
        try:
            current_case: dict[str, str] | None = None
            for raw_line in summary_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                for key, pattern in patterns.items():
                    match = pattern.match(line)
                    if match:
                        preview[key] = int(match.group(1))
                case_match = re.match(r"^\d+\.\s+Case:\s+(.+)$", line)
                if case_match:
                    if current_case:
                        self._append_report_summary_case_preview(preview, current_case)
                    current_case = {
                        "case_id": case_match.group(1).strip(),
                        "failure_category": "",
                        "actionable_suggestion": "no",
                        "suggestion_target": "",
                        "suggestion_advice_type": "",
                    }
                    continue
                if current_case is None:
                    continue
                if line.startswith("Failure Category: "):
                    current_case["failure_category"] = line.removeprefix("Failure Category: ").strip()
                elif line.startswith("Actionable Suggestion: "):
                    current_case["actionable_suggestion"] = line.removeprefix("Actionable Suggestion: ").strip().lower()
                elif line.startswith("Suggestion Target: "):
                    current_case["suggestion_target"] = line.removeprefix("Suggestion Target: ").strip()
                elif line.startswith("Suggestion Advice Type: "):
                    current_case["suggestion_advice_type"] = line.removeprefix("Suggestion Advice Type: ").strip()
            if current_case:
                self._append_report_summary_case_preview(preview, current_case)
        except OSError:
            return preview
        return preview

    @staticmethod
    def _append_report_summary_case_preview(preview: dict[str, Any], current_case: dict[str, str]) -> None:
        failure_category = current_case.get("failure_category", "").strip().lower()
        if failure_category in {"environment", "network", "authentication"}:
            preview["environment_failure_cases"].append(current_case["case_id"])
        if current_case.get("actionable_suggestion") == "yes":
            preview["actionable_self_healing_case_details"].append(
                {
                    "case_id": current_case["case_id"],
                    "target": current_case.get("suggestion_target", ""),
                    "advice_type": current_case.get("suggestion_advice_type", ""),
                }
            )

    def preview_self_healing_advice(
        self,
        page: str,
        case: dict[str, Any] | None = None,
        failure_reason: str = "",
        failure_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_page = page.strip()
        if not normalized_page:
            raise OrchestratorValidationError("page must not be empty")

        normalized_case = case if isinstance(case, dict) else {}
        normalized_failure_analysis = failure_analysis if isinstance(failure_analysis, dict) else {}
        if not normalized_case:
            normalized_case = {
                "execution": {
                    "page": normalized_page,
                    "steps": [],
                }
            }

        payload = {
            "page": normalized_page,
            "failure_reason": str(failure_reason).strip(),
            "failure_analysis": normalized_failure_analysis,
            "available_targets": self._load_available_targets(normalized_page),
            "case": normalized_case,
        }
        return self._run_self_healing_advisor_agent(payload)

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
    ) -> dict[str, Any]:
        evidence_manifest = self._normalize_evidence_manifest(evidence_manifest)
        stdout_text = completed.stdout if completed else ""
        stderr_text = completed.stderr if completed else ""
        metrics = self._extract_runner_metrics(stdout_text)
        pytest_results = self._build_pytest_results(
            output=stdout_text,
            error_output=stderr_text,
            runner_exit_code=completed.returncode if completed else None,
            metrics=metrics,
        )
        if not execution_requested:
            status = "generated"
        elif completed and completed.returncode == 0:
            status = "passed"
        else:
            status = "failed"

        test_point_metadata = test_points.get("metadata") if isinstance(test_points.get("metadata"), dict) else {}
        technique_summary = test_point_metadata.get("technique_summary") if isinstance(test_point_metadata.get("technique_summary"), dict) else {}
        report_payload = {
            "status": status,
            "summary": self._build_summary_text(status=status, case=case, execution_requested=execution_requested, metrics=metrics),
            "case_id": case["id"],
            "case_title": case.get("title", ""),
            "page": case.get("execution", {}).get("page", ""),
            "case_path": str(case_path),
            "execution_requested": execution_requested,
            "source": source,
            "request_context": {
                "page": case.get("execution", {}).get("page", ""),
                "mode": mode,
                "source": source,
                "execution_requested": execution_requested,
                "requirement_parser": requirement_spec.get("parser_runtime", {})
                if isinstance(requirement_spec.get("parser_runtime"), dict)
                else {},
                "technique_summary": technique_summary,
            },
            "requirement_spec": requirement_spec,
            "test_points_summary": {
                "page": str(test_points.get("page", "")).strip(),
                "point_count": len(test_points.get("points", [])) if isinstance(test_points.get("points"), list) else 0,
                "review_summary": test_points.get("review_summary", {}) if isinstance(test_points.get("review_summary"), dict) else {},
                "technique_summary": technique_summary,
            },
            "generated_script": generated_script,
            "execution_plan": execution_plan,
            "design_generation": design_generation,
            "agent_pipeline": self.agent_pipeline_order(),
            "started_at": started_at,
            "finished_at": finished_at,
            "runner_exit_code": completed.returncode if completed else None,
            "metrics": metrics,
            "pytest_results": pytest_results,
            "failure_reason": self._extract_failure_reason(output=stdout_text, error_output=stderr_text, status=status),
            "self_healing_enabled": os.getenv("SELF_HEALING_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"},
            "self_healing_attempted": bool(evidence_manifest.get("self_healing_result_files")),
            "evidence": evidence_manifest,
            "runner_stdout_excerpt": self._truncate_text(stdout_text),
            "runner_stderr_excerpt": self._truncate_text(stderr_text),
        }
        execution_record, execution_record_meta = self._resolve_execution_record_for_report(
            case=case,
            execution_requested=execution_requested,
            source=source,
            mode=mode,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            runner_exit_code=completed.returncode if completed else None,
            evidence_manifest=evidence_manifest,
        )
        report_payload["execution_record"] = execution_record
        report_payload["execution_record_meta"] = execution_record_meta
        report_payload["failure_analysis"] = self._analyze_failure(
            report_payload=report_payload,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
        )
        raw_triage = self._triage_failure(
            failure_analysis=report_payload["failure_analysis"],
            execution_record=report_payload["execution_record"],
            evidence_manifest=evidence_manifest,
            report=report_payload,
        )
        report_payload["failure_triage"] = self._enrich_failure_triage_with_history(
            triage=raw_triage,
            case_id=case.get("id", ""),
            page=report_payload.get("page", ""),
            started_at=started_at,
        )
        report_payload["self_healing_advice"] = self._build_self_healing_advice(
            case=case,
            report_payload=report_payload,
        )
        report_payload["self_healing_suggestion_preview"] = self._load_self_healing_suggestion_preview(report_payload)
        report_payload["self_healing_execution_preview"] = self._load_self_healing_execution_preview(report_payload)
        report_payload["risk_report"] = self._evaluate_risk_report(
            requirement_spec=requirement_spec,
            execution_plan=execution_plan,
            execution_record=report_payload["execution_record"],
            failure_analysis=report_payload["failure_analysis"],
            failure_triage=report_payload["failure_triage"],
        )
        return report_payload

    @staticmethod
    def _load_execution_record_from_manifest(evidence_manifest: dict[str, Any]) -> dict[str, Any]:
        record_files = evidence_manifest.get("execution_record_files") or []
        if not isinstance(record_files, list) or not record_files:
            return {}
        path = Path(str(record_files[0]))
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        return payload

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
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        record_files = evidence_manifest.get("execution_record_files")
        manifest_record_count = len(record_files) if isinstance(record_files, list) else 0
        meta = {
            "version": "ExecutionRecordResolutionMetaV1",
            "source": "generated",
            "manifest_record_count": manifest_record_count,
            "compat_builder_enabled": bool(self.execution_record_compat_builder_enabled),
            "compat_builder_used": False,
            "strict_violation": False,
        }

        manifest_execution_record = self._load_execution_record_from_manifest(evidence_manifest)
        if manifest_execution_record:
            meta["source"] = "manifest"
            return self._normalize_execution_record(manifest_execution_record), meta

        if execution_requested and int(evidence_manifest.get("total_files", 0) or 0) > 0:
            if not self.execution_record_compat_builder_enabled:
                meta["source"] = "strict_blocked"
                meta["strict_violation"] = True
                self.logger.error(
                    "execution_record manifest path missing/invalid for case %s; strict mode blocks compatibility builder",
                    case.get("id", ""),
                )
                raise OrchestratorValidationError(
                    "execution_record missing in evidence_manifest and compatibility builder is disabled"
                )
            meta["source"] = "compat_builder"
            meta["compat_builder_used"] = True
            self.logger.warning(
                "execution_record manifest path missing/invalid for case %s; using compatibility record builder",
                case.get("id", ""),
            )

        execution_record = self._build_execution_record(
            case=case,
            execution_requested=execution_requested,
            source=source,
            mode=mode,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            runner_exit_code=runner_exit_code,
            evidence_manifest=evidence_manifest,
        )
        return execution_record, meta

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
    ) -> dict[str, Any]:
        steps = case.get("execution", {}).get("steps", [])
        requirement = case.get("requirement") or []
        if isinstance(requirement, str):
            requirement = [requirement]
        raw = {
            "version": "ExecutionRecordV1",
            "schema_version": "execution-record.v1",
            "run_id": f"{case.get('id', '')}:{started_at}",
            "case_id": case.get("id", ""),
            "project": "default",
            "source": source,
            "mode": mode,
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "step_summary": {
                "page": case.get("execution", {}).get("page", ""),
                "requirement_count": len(requirement),
                "total_steps": len(steps),
                "action_types": sorted({step.get("action", "") for step in steps if step.get("action")}),
            },
            "evidence_index": {
                "total_files": evidence_manifest.get("total_files", 0),
                "artifact_categories": {
                    "screenshots": len(evidence_manifest.get("screenshots", [])),
                    "html_pages": len(evidence_manifest.get("html_pages", [])),
                    "meta_files": len(evidence_manifest.get("meta_files", [])),
                    "analysis_files": len(evidence_manifest.get("analysis_files", [])),
                    "suggestion_files": len(evidence_manifest.get("suggestion_files", [])),
                    "self_healing_result_files": len(evidence_manifest.get("self_healing_result_files", [])),
                    "videos": len(evidence_manifest.get("videos", [])),
                    "other_files": len(evidence_manifest.get("other_files", [])),
                },
                "runner_exit_code": runner_exit_code,
                "execution_requested": execution_requested,
            },
        }
        return self._normalize_execution_record(raw)

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
        if report_payload["status"] != "failed":
            return {
                "summary": "No failure analysis needed because the run did not fail.",
                "failure_category": "unknown",
                "failure_source": "unknown",
                "failure_source_reason": "No failure occurred, so no source classification is required.",
                "failure_source_confidence": 1.0,
                "source_evidence": [],
                "likely_cause": "",
                "risk_level": "low",
                "recommended_action": "No immediate failure action is required.",
                "confidence": 1.0,
                "requires_manual_review": False,
                "evidence_used": [],
            }

        try:
            return self._run_failure_analysis_agent(
                {
                    "report": report_payload,
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "error": report_payload["failure_reason"],
                }
            )
        except Exception:
            return {
                "summary": "Failure analysis agent was unavailable; returned heuristic fallback analysis.",
                "failure_category": "unknown",
                "failure_source": "unknown",
                "failure_source_reason": "Failure analysis agent was unavailable, so source classification fell back to unknown.",
                "failure_source_confidence": 0.35,
                "source_evidence": [
                    {
                        "signal": "fallback",
                        "value": "failure_analysis_agent_unavailable",
                        "origin": "report",
                        "supports": "unknown",
                    }
                ],
                "likely_cause": report_payload["failure_reason"] or "Unknown execution failure.",
                "risk_level": "medium",
                "recommended_action": "Review the pytest output and captured evidence manually.",
                "confidence": 0.35,
                "requires_manual_review": True,
                "evidence_used": ["stdout", "stderr"] if stdout_text or stderr_text else ["report"],
            }

    def _run_failure_analysis_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        if str(self.failure_agent_root) not in sys.path:
            sys.path.insert(0, str(self.failure_agent_root))
        from analyze import FailureAnalysisAgent

        agent = FailureAnalysisAgent()
        return agent.analyze(payload)

    def _build_self_healing_advice(self, case: dict[str, Any], report_payload: dict[str, Any]) -> dict[str, Any]:
        available_targets = self._load_available_targets(case.get("execution", {}).get("page", ""))
        payload = {
            "page": case.get("execution", {}).get("page", ""),
            "failure_reason": report_payload.get("failure_reason", ""),
            "failure_analysis": report_payload.get("failure_analysis", {}),
            "available_targets": available_targets,
            "case": case,
        }
        try:
            return self._run_self_healing_advisor_agent(payload)
        except Exception:
            return {
                "summary": "No self-healing advice generated.",
                "suggestion_type": "no_change",
                "suggested_changes": ["Do not modify files automatically. Review the report and failure analysis manually."],
                "rationale": "Self-healing advisor agent was unavailable.",
                "confidence": 0.0,
                "safe_to_apply_manually": True,
            }

    @staticmethod
    def _load_self_healing_suggestion_preview(report_payload: dict[str, Any]) -> dict[str, Any]:
        evidence = report_payload.get("evidence", {})
        if not isinstance(evidence, dict):
            return {}

        suggestion_files = evidence.get("suggestion_files") or []
        if not isinstance(suggestion_files, list) or not suggestion_files:
            return {}

        suggestion_path = Path(str(suggestion_files[0]))
        if not suggestion_path.exists():
            return {}

        try:
            payload = json.loads(suggestion_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        if not isinstance(payload, dict):
            return {}

        return {
            "summary": str(payload.get("summary", "No suggestion summary available.")).strip() or "No suggestion summary available.",
            "advice_type": str(payload.get("advice_type", "no_change")).strip() or "no_change",
            "target": str(payload.get("target", "")).strip(),
            "suggestion": str(payload.get("suggestion", "")).strip(),
            "confidence": payload.get("confidence", 0.0),
            "fix_candidates": payload.get("fix_candidates", []) if isinstance(payload.get("fix_candidates", []), list) else [],
        }

    @staticmethod
    def _load_self_healing_execution_preview(report_payload: dict[str, Any]) -> dict[str, Any]:
        evidence = report_payload.get("evidence", {})
        if not isinstance(evidence, dict):
            return {}

        result_files = evidence.get("self_healing_result_files") or []
        if not isinstance(result_files, list) or not result_files:
            return {}

        result_path = Path(str(result_files[0]))
        if not result_path.exists():
            return {}

        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        if not isinstance(payload, dict):
            return {}

        return {
            "status": str(payload.get("status", "unknown")).strip() or "unknown",
            "reason": str(payload.get("reason", "")).strip(),
            "attempts_used": int(payload.get("attempts_used", 0) or 0),
            "healed": bool(payload.get("healed", False)),
            "rolled_back": bool(payload.get("rolled_back", False)),
            "confidence": payload.get("confidence", 0.0),
            "plan_path": str(payload.get("plan_path", "")).strip(),
            "result_path": str(payload.get("result_path", "")).strip(),
        }

    def _run_self_healing_advisor_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        if str(self.self_healing_agent_root) not in sys.path:
            sys.path.insert(0, str(self.self_healing_agent_root))
        from agent import SelfHealingAdvisorAgent

        agent = SelfHealingAdvisorAgent()
        return agent.advise(payload)

    def _load_available_targets(self, page_name: str) -> list[str]:
        if not page_name:
            return []
        self._ensure_runner_import_path()
        from runner.paths import PAGE_OBJECTS_ROOT
        from runner.yaml_loader import load_yaml_file

        page_object_path = PAGE_OBJECTS_ROOT / f"{page_name}.page-object.yaml"
        if not page_object_path.exists():
            return []

        page_object = load_yaml_file(page_object_path)
        if not page_object:
            return []
        return sorted(page_object.get("elements", {}).keys())

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
        return json.dumps(report_payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _render_report_markdown(report_payload: dict[str, Any]) -> str:
        metrics = report_payload["metrics"]
        pytest_results = report_payload["pytest_results"]
        evidence = report_payload["evidence"]
        failure_analysis = report_payload["failure_analysis"]
        failure_triage = report_payload.get("failure_triage", {})
        self_healing_advice = report_payload["self_healing_advice"]
        self_healing_suggestion_preview = report_payload.get("self_healing_suggestion_preview", {})
        self_healing_execution_preview = report_payload.get("self_healing_execution_preview", {})
        request_context = report_payload["request_context"]
        execution_record_meta = report_payload.get("execution_record_meta", {})
        execution_plan = report_payload.get("execution_plan", {})
        risk_report = report_payload.get("risk_report", {})
        agent_pipeline = report_payload.get("agent_pipeline", [])
        test_points_summary = report_payload.get("test_points_summary", {})
        technique_summary = request_context.get("technique_summary", {}) if isinstance(request_context.get("technique_summary"), dict) else {}
        plan_stages = execution_plan.get("stages", []) if isinstance(execution_plan, dict) else []
        stage_lines: list[str] = []
        if isinstance(plan_stages, list):
            for stage in plan_stages:
                if not isinstance(stage, dict):
                    continue
                stage_lines.append(
                    "- {stage_id}: {stage_name} ({runner}, est={estimated}s, retry={retry})".format(
                        stage_id=stage.get("stage_id", "-"),
                        stage_name=stage.get("stage_name", "-"),
                        runner=stage.get("runner", "-"),
                        estimated=stage.get("estimated_seconds", "-"),
                        retry=stage.get("retry_limit", "-"),
                    )
                )
        lines = [
            f"# Execution Report: {report_payload['case_id']}",
            "",
            f"- Status: {report_payload['status']}",
            f"- Page: {report_payload['page'] or '-'}",
            f"- Case Path: {report_payload['case_path']}",
            f"- Execution Requested: {report_payload['execution_requested']}",
            f"- Source: {report_payload['source']}",
            f"- Runner Exit Code: {report_payload['runner_exit_code']}",
            f"- Started At: {report_payload['started_at']}",
            f"- Finished At: {report_payload['finished_at']}",
            "",
            "## Summary",
            "",
            report_payload["summary"],
            "",
            "## Request Context",
            "",
            f"- Page: {request_context['page']}",
            f"- Mode: {request_context['mode']}",
            f"- Source: {request_context['source']}",
            f"- Execution Requested: {request_context['execution_requested']}",
            f"- Structured Constraints: {bool(technique_summary.get('has_structured_constraints', False))}",
            f"- Technique Distribution: {json.dumps(technique_summary.get('technique_distribution', {}), ensure_ascii=False) if technique_summary else '{}'}",
            f"- Design-only Points: {technique_summary.get('design_only_point_count', 0) if technique_summary else 0}",
            "",
            "## Test Point Summary",
            "",
            f"- Page: {test_points_summary.get('page', '-') if isinstance(test_points_summary, dict) else '-'}",
            f"- Point Count: {test_points_summary.get('point_count', '-') if isinstance(test_points_summary, dict) else '-'}",
            f"- Review Summary: {json.dumps(test_points_summary.get('review_summary', {}), ensure_ascii=False) if isinstance(test_points_summary, dict) else '{}'}",
            f"- Technique Summary: {json.dumps(test_points_summary.get('technique_summary', {}), ensure_ascii=False) if isinstance(test_points_summary, dict) else '{}'}",
            "",
            "## Generated Script",
            "",
            f"- Framework: {report_payload.get('generated_script', {}).get('framework', '-')}",
            f"- Language: {report_payload.get('generated_script', {}).get('language', '-')}",
            f"- Entrypoint: {report_payload.get('generated_script', {}).get('entrypoint', '-')}",
            f"- Script Path: {report_payload.get('generated_script', {}).get('script_path', '-')}",
            "",
            "## Agent Pipeline",
            "",
            f"- Sequence: {' -> '.join(agent_pipeline) if isinstance(agent_pipeline, list) and agent_pipeline else '-'}",
            "",
            "## Execution Plan",
            "",
            f"- Version: {execution_plan.get('version', '-') if isinstance(execution_plan, dict) else '-'}",
            f"- Run Mode: {execution_plan.get('run_mode', '-') if isinstance(execution_plan, dict) else '-'}",
            f"- Priority: {execution_plan.get('priority', '-') if isinstance(execution_plan, dict) else '-'}",
            f"- Environment: {execution_plan.get('environment', '-') if isinstance(execution_plan, dict) else '-'}",
            f"- Parallelism: {execution_plan.get('parallelism', '-') if isinstance(execution_plan, dict) else '-'}",
            f"- Retry Policy: {json.dumps(execution_plan.get('retry_policy', {}), ensure_ascii=False) if isinstance(execution_plan, dict) else '-'}",
            f"- Scheduling Hints: {json.dumps(execution_plan.get('scheduling_hints', {}), ensure_ascii=False) if isinstance(execution_plan, dict) else '-'}",
            "- Stages:",
            *(stage_lines if stage_lines else ["- -"]),
            "",
            "## Risk Report",
            "",
            f"- Version: {risk_report.get('version', '-') if isinstance(risk_report, dict) else '-'}",
            f"- Risk Score: {risk_report.get('risk_score', '-') if isinstance(risk_report, dict) else '-'}",
            f"- Risk Level: {risk_report.get('risk_level', '-') if isinstance(risk_report, dict) else '-'}",
            f"- Gate Decision: {risk_report.get('gate_decision', '-') if isinstance(risk_report, dict) else '-'}",
            f"- Recommendation: {risk_report.get('recommendation', '-') if isinstance(risk_report, dict) else '-'}",
            f"- Factors: {json.dumps(risk_report.get('factors', []), ensure_ascii=False) if isinstance(risk_report, dict) else '-'}",
            "",
            "## Metrics",
            "",
            f"- Passed: {metrics['passed']}",
            f"- Failed: {metrics['failed']}",
            f"- Skipped: {metrics['skipped']}",
            f"- Errors: {metrics['errors']}",
            "",
            "## Pytest Results",
            "",
            f"- Collected: {pytest_results['collected']}",
            f"- Passed: {pytest_results['passed']}",
            f"- Failed: {pytest_results['failed']}",
            f"- Skipped: {pytest_results['skipped']}",
            f"- Errors: {pytest_results['errors']}",
            f"- Duration Seconds: {pytest_results['duration_seconds']}",
            f"- Runner Exit Code: {pytest_results['runner_exit_code']}",
            f"- Has Stderr: {pytest_results['has_stderr']}",
            "",
            "## Failure Reason",
            "",
            report_payload["failure_reason"] or "No failure reason because the run did not fail.",
            "",
            "## Self-Healing Status",
            "",
            f"- Enabled: {report_payload.get('self_healing_enabled', False)}",
            f"- Attempted: {report_payload.get('self_healing_attempted', False)}",
            "",
            "## Failure Analysis",
            "",
            f"- Summary: {failure_analysis['summary']}",
            f"- Category: {failure_analysis['failure_category']}",
            f"- Source: {failure_analysis.get('failure_source', '-')}",
            f"- Source Reason: {failure_analysis.get('failure_source_reason', '-') or '-'}",
            f"- Source Confidence: {failure_analysis.get('failure_source_confidence', '-')}",
            f"- Source Evidence: {json.dumps(failure_analysis.get('source_evidence', []), ensure_ascii=False) if failure_analysis.get('source_evidence') else '-'}",
            f"- Likely Cause: {failure_analysis['likely_cause'] or '-'}",
            f"- Risk Level: {failure_analysis['risk_level']}",
            f"- Recommended Action: {failure_analysis['recommended_action']}",
            f"- Confidence: {failure_analysis['confidence']}",
            f"- Requires Manual Review: {failure_analysis.get('requires_manual_review', '-')}",
            f"- Evidence Used: {', '.join(failure_analysis['evidence_used']) if failure_analysis['evidence_used'] else '-'}",
            "",
            "## Failure Triage",
            "",
            f"- Version: {failure_triage.get('version', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- Label: {failure_triage.get('triage_label', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- Class: {failure_triage.get('failure_class', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- Severity: {failure_triage.get('severity', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- Owner Team: {failure_triage.get('owner_team', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- Queue: {failure_triage.get('queue', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- Bucket Key: {failure_triage.get('bucket_key', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- Cluster ID: {failure_triage.get('cluster_id', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- Occurrence Count: {failure_triage.get('occurrence_count', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- First Seen At: {failure_triage.get('first_seen_at', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- Last Seen At: {failure_triage.get('last_seen_at', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- Duplicate Of: {failure_triage.get('duplicate_of', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- Requires Manual Review: {failure_triage.get('requires_manual_review', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- Confidence: {failure_triage.get('confidence', '-') if isinstance(failure_triage, dict) else '-'}",
            f"- Actions: {json.dumps(failure_triage.get('actions', []), ensure_ascii=False) if isinstance(failure_triage, dict) else '-'}",
            f"- Similar Cases: {json.dumps(failure_triage.get('similar_cases', []), ensure_ascii=False) if isinstance(failure_triage, dict) else '-'}",
            "",
            "## Self-Healing Advice",
            "",
            f"- Summary: {self_healing_advice['summary']}",
            f"- Suggestion Type: {self_healing_advice['suggestion_type']}",
            f"- Suggested Changes: {'; '.join(self_healing_advice['suggested_changes']) if self_healing_advice['suggested_changes'] else '-'}",
            f"- Rationale: {self_healing_advice['rationale']}",
            f"- Confidence: {self_healing_advice['confidence']}",
            f"- Safe To Apply Manually: {self_healing_advice['safe_to_apply_manually']}",
            "",
            "## Self-Healing Suggestion Preview",
            "",
            f"- Summary: {self_healing_suggestion_preview.get('summary', '-')}",
            f"- Advice Type: {self_healing_suggestion_preview.get('advice_type', '-')}",
            f"- Target: {self_healing_suggestion_preview.get('target', '-')}",
            f"- Suggestion: {self_healing_suggestion_preview.get('suggestion', '-')}",
            f"- Confidence: {self_healing_suggestion_preview.get('confidence', '-')}",
            f"- Fix Candidates: {', '.join(self_healing_suggestion_preview.get('fix_candidates', [])) if self_healing_suggestion_preview.get('fix_candidates') else '-'}",
            "",
            "## Self-Healing Execution Preview",
            "",
            f"- Status: {self_healing_execution_preview.get('status', '-')}",
            f"- Reason: {self_healing_execution_preview.get('reason', '-')}",
            f"- Attempts Used: {self_healing_execution_preview.get('attempts_used', '-')}",
            f"- Healed: {self_healing_execution_preview.get('healed', '-')}",
            f"- Rolled Back: {self_healing_execution_preview.get('rolled_back', '-')}",
            f"- Confidence: {self_healing_execution_preview.get('confidence', '-')}",
            f"- Plan Path: {self_healing_execution_preview.get('plan_path', '-')}",
            f"- Result Path: {self_healing_execution_preview.get('result_path', '-')}",
            "",
            "## Execution Record Resolution",
            "",
            f"- Source: {execution_record_meta.get('source', '-')}",
            f"- Manifest Record Count: {execution_record_meta.get('manifest_record_count', 0)}",
            f"- Compat Builder Enabled: {execution_record_meta.get('compat_builder_enabled', False)}",
            f"- Compat Builder Used: {execution_record_meta.get('compat_builder_used', False)}",
            f"- Strict Violation: {execution_record_meta.get('strict_violation', False)}",
            "",
            "## Evidence",
            "",
            f"- Total Files: {evidence['total_files']}",
            f"- Screenshots: {len(evidence['screenshots'])}",
            f"- HTML Pages: {len(evidence['html_pages'])}",
            f"- Meta Files: {len(evidence['meta_files'])}",
            f"- Analysis Files: {len(evidence['analysis_files'])}",
            f"- Suggestion Files: {len(evidence['suggestion_files'])}",
            f"- Execution Record Files: {len(evidence['execution_record_files'])}",
            f"- Self-Healing Result Files: {len(evidence['self_healing_result_files'])}",
            f"- Videos: {len(evidence['videos'])}",
            "",
            "## Runner Stdout Excerpt",
            "",
            "```text",
            report_payload["runner_stdout_excerpt"] or "(empty)",
            "```",
            "",
            "## Runner Stderr Excerpt",
            "",
            "```text",
            report_payload["runner_stderr_excerpt"] or "(empty)",
            "```",
        ]
        return "\n".join(lines) + "\n"
