# mypy: ignore-errors

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from shared_backend.observability import build_ai_trace_context
from shared_backend.state_machines import get_run_status_name, normalize_run_status


class ExecutionReportSupport:
    def __init__(
        self,
        *,
        ensure_runner_import_path: Callable[[], None],
        normalize_execution_record: Callable[..., dict[str, Any]],
        normalize_evidence_manifest: Callable[..., dict[str, Any]],
        ensure_change_impact_explainability: Callable[[dict[str, Any]], dict[str, Any]],
        build_summary_text: Callable[..., str],
        extract_runner_metrics: Callable[[str], dict[str, int]],
        build_pytest_results: Callable[..., dict[str, Any]],
        extract_failure_reason: Callable[..., str],
        analyze_failure: Callable[..., dict[str, Any]],
        triage_failure: Callable[..., dict[str, Any]],
        enrich_failure_triage_with_history: Callable[..., dict[str, Any]],
        build_self_healing_advice: Callable[..., dict[str, Any]],
        load_self_healing_suggestion_preview: Callable[[dict[str, Any]], dict[str, Any]],
        load_self_healing_execution_preview: Callable[[dict[str, Any]], dict[str, Any]],
        evaluate_risk_report: Callable[..., dict[str, Any]],
        agent_pipeline_order: Callable[[], list[str]],
        logger: Any,
        runner_root: Path,
    ) -> None:
        self._ensure_runner_import_path = ensure_runner_import_path
        self._normalize_execution_record = normalize_execution_record
        self._normalize_evidence_manifest = normalize_evidence_manifest
        self._ensure_change_impact_explainability = ensure_change_impact_explainability
        self._build_summary_text = build_summary_text
        self._extract_runner_metrics = extract_runner_metrics
        self._build_pytest_results = build_pytest_results
        self._extract_failure_reason = extract_failure_reason
        self._analyze_failure = analyze_failure
        self._triage_failure = triage_failure
        self._enrich_failure_triage_with_history = enrich_failure_triage_with_history
        self._build_self_healing_advice = build_self_healing_advice
        self._load_self_healing_suggestion_preview = load_self_healing_suggestion_preview
        self._load_self_healing_execution_preview = load_self_healing_execution_preview
        self._evaluate_risk_report = evaluate_risk_report
        self._agent_pipeline_order = agent_pipeline_order
        self._logger = logger
        self._runner_root = runner_root

    def build_report_summary_path(self) -> str:
        self._ensure_runner_import_path()
        from tools.report_summary import build_report_summary  # type: ignore[import-not-found]

        summary_path = build_report_summary(
            self._runner_root / "artifacts",
            self._runner_root / "artifacts" / "report_summary.txt",
        )
        return str(summary_path)

    def load_report_summary_preview(self, summary_path: Path) -> dict[str, Any]:
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
                        self.append_report_summary_case_preview(preview, current_case)
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
                self.append_report_summary_case_preview(preview, current_case)
        except OSError:
            return preview
        return preview

    @staticmethod
    def append_report_summary_case_preview(preview: dict[str, Any], current_case: dict[str, str]) -> None:
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

    def build_report_payload(
        self,
        *,
        requirement_spec: dict[str, Any],
        case: dict[str, Any],
        test_points: dict[str, Any],
        generated_script: dict[str, Any],
        execution_plan: dict[str, Any],
        design_generation: dict[str, Any],
        case_path: Path,
        execution_requested: bool,
        completed: Any,
        evidence_manifest: dict[str, Any],
        started_at: str,
        finished_at: str,
        source: str,
        mode: str,
        runner_profile: dict[str, Any] | None = None,
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
        traceability_summary = test_point_metadata.get("traceability_summary") if isinstance(test_point_metadata.get("traceability_summary"), dict) else {}
        parser_runtime = requirement_spec.get("parser_runtime", {}) if isinstance(requirement_spec.get("parser_runtime"), dict) else {}
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
                "runner": str((runner_profile or {}).get("runner", "playwright")).strip() or "playwright",
                "runner_profile": deepcopy(runner_profile or {}),
                "execution_requested": execution_requested,
                "requirement_parser": parser_runtime,
                "technique_summary": technique_summary,
                "source_summary": parser_runtime.get("source_summary", {}) if isinstance(parser_runtime.get("source_summary"), dict) else {},
                "page_resolution": parser_runtime.get("page_resolution", {}) if isinstance(parser_runtime.get("page_resolution"), dict) else {},
                "change_impact": requirement_spec.get("change_impact", {}) if isinstance(requirement_spec.get("change_impact"), dict) else {},
            },
            "requirement_spec": requirement_spec,
            "test_points_summary": {
                "page": str(test_points.get("page", "")).strip(),
                "point_count": len(test_points.get("points", [])) if isinstance(test_points.get("points"), list) else 0,
                "review_summary": test_points.get("review_summary", {}) if isinstance(test_points.get("review_summary"), dict) else {},
                "technique_summary": technique_summary,
                "traceability_summary": traceability_summary,
            },
            "generated_script": generated_script,
            "execution_plan": execution_plan,
            "design_generation": design_generation,
            "agent_pipeline": self._agent_pipeline_order(),
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
        execution_record, execution_record_meta = self.resolve_execution_record_for_report(
            case=case,
            execution_requested=execution_requested,
            source=source,
            mode=mode,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            runner_exit_code=completed.returncode if completed else None,
            evidence_manifest=evidence_manifest,
            execution_metadata=self.build_execution_record_metadata(
                requirement_spec=requirement_spec,
                test_points=test_points,
                runner_profile=runner_profile,
            ),
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
    def inspect_execution_record_manifest(evidence_manifest: dict[str, Any]) -> dict[str, Any]:
        record_files = evidence_manifest.get("execution_record_files") or []
        if not isinstance(record_files, list) or not record_files:
            return {
                "status": "no_entry",
                "path": "",
                "record": {},
            }
        path = Path(str(record_files[0]))
        if not path.exists():
            return {
                "status": "file_missing",
                "path": str(path),
                "record": {},
            }
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {
                "status": "invalid_json",
                "path": str(path),
                "record": {},
            }
        if not isinstance(payload, dict):
            return {
                "status": "invalid_payload",
                "path": str(path),
                "record": {},
            }
        return {
            "status": "loaded",
            "path": str(path),
            "record": payload,
        }

    @staticmethod
    def load_execution_record_from_manifest(evidence_manifest: dict[str, Any]) -> dict[str, Any]:
        inspected = ExecutionReportSupport.inspect_execution_record_manifest(evidence_manifest)
        record = inspected.get("record")
        return record if isinstance(record, dict) else {}

    def resolve_execution_record_for_report(
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
        record_files = evidence_manifest.get("execution_record_files")
        manifest_record_count = len(record_files) if isinstance(record_files, list) else 0
        meta = {
            "version": "ExecutionRecordResolutionMetaV1",
            "source": "generated",
            "manifest_record_count": manifest_record_count,
            "manifest_record_path": "",
            "manifest_status": "not_checked",
            "resolution_reason": "generated_without_artifacts",
        }

        manifest_inspection = self.inspect_execution_record_manifest(evidence_manifest)
        meta["manifest_record_path"] = str(manifest_inspection.get("path", "")).strip()
        meta["manifest_status"] = str(manifest_inspection.get("status", "not_checked")).strip() or "not_checked"
        manifest_execution_record = manifest_inspection.get("record")
        if manifest_execution_record:
            meta["source"] = "manifest"
            meta["resolution_reason"] = "execution_record_loaded_from_manifest"
            return self.merge_execution_record_metadata(
                self._normalize_execution_record(manifest_execution_record),
                execution_metadata,
            ), meta

        execution_record = self.build_execution_record(
            case=case,
            execution_requested=execution_requested,
            source=source,
            mode=mode,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            runner_exit_code=runner_exit_code,
            evidence_manifest=evidence_manifest,
            metadata=execution_metadata,
        )
        if meta["source"] == "generated":
            meta["resolution_reason"] = "generated_without_execution_artifacts"
        return execution_record, meta

    @staticmethod
    def merge_execution_record_metadata(
        execution_record: dict[str, Any],
        supplemental_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(execution_record, dict):
            return execution_record
        if not isinstance(supplemental_metadata, dict) or not supplemental_metadata:
            return execution_record
        metadata = execution_record.get("metadata") if isinstance(execution_record.get("metadata"), dict) else {}
        merged = dict(metadata)
        for key, value in supplemental_metadata.items():
            if key not in merged:
                merged[key] = deepcopy(value)
                continue
            if isinstance(merged.get(key), dict) and isinstance(value, dict):
                merged[key] = {
                    **deepcopy(value),
                    **merged[key],
                }
        execution_record["metadata"] = merged
        return execution_record

    def build_execution_record_metadata(
        self,
        *,
        requirement_spec: dict[str, Any],
        test_points: dict[str, Any],
        runner_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parser_runtime = requirement_spec.get("parser_runtime") if isinstance(requirement_spec.get("parser_runtime"), dict) else {}
        source_summary = parser_runtime.get("source_summary") if isinstance(parser_runtime.get("source_summary"), dict) else {}
        if not source_summary:
            source_inputs = requirement_spec.get("source_inputs") if isinstance(requirement_spec.get("source_inputs"), list) else []
            source_summary = {
                "source_count": len([item for item in source_inputs if isinstance(item, dict)]),
                "source_types": list(
                    dict.fromkeys(
                        str(item.get("source_type", "")).strip()
                        for item in source_inputs
                        if isinstance(item, dict) and str(item.get("source_type", "")).strip()
                    )
                ),
            }
        page_resolution = parser_runtime.get("page_resolution") if isinstance(parser_runtime.get("page_resolution"), dict) else {}
        if not page_resolution:
            page_resolution = {
                "page": str(requirement_spec.get("page", "")).strip(),
                "resolution_reason": "requirement_spec.page",
            }
        test_point_metadata = test_points.get("metadata") if isinstance(test_points.get("metadata"), dict) else {}
        traceability_summary = (
            test_point_metadata.get("traceability_summary")
            if isinstance(test_point_metadata.get("traceability_summary"), dict)
            else {}
        )
        change_impact = self._ensure_change_impact_explainability(
            requirement_spec.get("change_impact") if isinstance(requirement_spec.get("change_impact"), dict) else {}
        )
        active_runner_profile = runner_profile if isinstance(runner_profile, dict) else {}
        ai_trace = parser_runtime.get("ai_trace") if isinstance(parser_runtime.get("ai_trace"), dict) else {}
        if not ai_trace:
            ai_trace = build_ai_trace_context(
                page=str(requirement_spec.get("page", "")).strip(),
                prompt_version=str(parser_runtime.get("prompt_version", "")).strip(),
                model=str(parser_runtime.get("model", "")).strip(),
                source=str(requirement_spec.get("source_type", "")).strip() or "manual",
                instructions_version=str(parser_runtime.get("instructions_version", "")).strip(),
            )
        return {
            "runner": str(active_runner_profile.get("runner", "playwright")).strip() or "playwright",
            "runner_profile": deepcopy(active_runner_profile),
            "ai_observability": {
                "trace_id": str(ai_trace.get("trace_id", "")).strip(),
                "prompt_version": str(ai_trace.get("prompt_version", "")).strip(),
                "model": str(ai_trace.get("model", "")).strip(),
                "instructions_version": str(ai_trace.get("instructions_version", "")).strip(),
            },
            "multisource": {
                "source_summary": deepcopy(source_summary),
                "page_resolution": deepcopy(page_resolution),
                "traceability_summary": deepcopy(traceability_summary),
                "change_impact": deepcopy(change_impact),
            }
        }

    def build_execution_record(
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
        steps = case.get("execution", {}).get("steps", [])
        requirement = case.get("requirement") or []
        if isinstance(requirement, str):
            requirement = [requirement]
        normalized_status = normalize_run_status(status)
        raw = {
            "version": "ExecutionRecordV1",
            "schema_version": "execution-record.v1",
            "run_id": f"{case.get('id', '')}:{started_at}",
            "case_id": case.get("id", ""),
            "project": "default",
            "source": source,
            "mode": mode,
            "status": normalized_status,
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
                    "execution_record_files": len(evidence_manifest.get("execution_record_files", [])),
                    "self_healing_result_files": len(evidence_manifest.get("self_healing_result_files", [])),
                    "videos": len(evidence_manifest.get("videos", [])),
                    "other_files": len(evidence_manifest.get("other_files", [])),
                },
                "runner_exit_code": runner_exit_code,
                "execution_requested": execution_requested,
            },
            "metadata": deepcopy(metadata) if isinstance(metadata, dict) else {},
        }
        raw["metadata"]["run_state"] = {
            "status": normalized_status,
            "status_name": get_run_status_name(normalized_status),
        }
        return self._normalize_execution_record(raw)

    @staticmethod
    def render_report_json(report_payload: dict[str, Any]) -> str:
        return json.dumps(report_payload, ensure_ascii=False, indent=2)

    @staticmethod
    def render_report_markdown(report_payload: dict[str, Any]) -> str:
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
            f"- Manifest Record Path: {execution_record_meta.get('manifest_record_path', '-') or '-'}",
            f"- Manifest Status: {execution_record_meta.get('manifest_status', '-')}",
            f"- Resolution Reason: {execution_record_meta.get('resolution_reason', '-')}",
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

    @staticmethod
    def _truncate_text(text: str, max_length: int = 4000) -> str:
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."
