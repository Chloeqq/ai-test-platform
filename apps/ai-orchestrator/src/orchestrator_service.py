import os
import re
import subprocess
import sys
import json
from datetime import UTC, datetime
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
    case: dict[str, Any]
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

    def __init__(self, repo_root: Path | None = None):
        self.repo_root = repo_root or Path(__file__).resolve().parents[3]
        self.agent_root = self.repo_root / "agents" / "test-design-agent"
        self.failure_agent_root = self.repo_root / "agents" / "failure-analysis-agent"
        self.self_healing_agent_root = self.repo_root / "agents" / "self-healing-advisor-agent" / "src"
        self.runner_root = self.repo_root / "runners" / "web-playwright-python"
        self.generated_cases_root = self.repo_root / "assets" / "test-cases" / "ai-generated"
        self.report_root = self.repo_root / "reports" / "executions"

    def orchestrate(
        self,
        requirement: str,
        page: str,
        execute: bool = False,
        source: str = "manual",
        mode: str | None = None,
    ) -> OrchestrationResult:
        if not requirement.strip():
            raise OrchestratorValidationError("requirement must not be empty")

        if not page.strip():
            raise OrchestratorValidationError("page must not be empty")

        normalized_source = source.strip().lower()
        if normalized_source not in self.ALLOWED_SOURCES:
            raise OrchestratorValidationError("source must be one of: manual, ai, regression")
        normalized_mode = mode.strip().lower() if isinstance(mode, str) and mode.strip() else None
        if normalized_mode is None:
            normalized_mode = "generate_and_run" if execute else "generate_only"

        case = self._generate_case(requirement=requirement, page=page)
        test_points = self._build_test_points_preview(case)
        case = self._prepare_generated_case_for_assets(case)
        case_path = self._save_case(case)
        started_at = self._now()

        result = OrchestrationResult(
            case=case,
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
                    case=case,
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
            case=case,
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
        if not execute:
            result.execution_record = report_payload["execution_record"]

        return result

    def _generate_case(self, requirement: str, page: str) -> dict[str, Any]:
        if str(self.agent_root) not in sys.path:
            sys.path.insert(0, str(self.agent_root))

        from src.agent import TestDesignAgent
        from src.tools.yaml_writer import save_yaml  # noqa: F401

        agent = TestDesignAgent()
        return agent.generate(requirement=requirement, page=page)

    def _build_test_points_preview(self, case: dict[str, Any]) -> dict[str, Any]:
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
        return plan.model_dump(exclude_none=True)

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

    @staticmethod
    def serialize_result(result: OrchestrationResult) -> dict[str, Any]:
        return asdict(result)

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
        return manifest

    def _build_and_save_report(
        self,
        case: dict[str, Any],
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
            case=case,
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
        case: dict[str, Any],
        case_path: Path,
        execution_requested: bool,
        completed: subprocess.CompletedProcess[str] | None,
        evidence_manifest: dict[str, Any],
        started_at: str,
        finished_at: str,
        source: str,
        mode: str,
    ) -> dict[str, Any]:
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
            },
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
        report_payload["execution_record"] = self._load_execution_record_from_manifest(evidence_manifest) or self._build_execution_record(
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
        report_payload["failure_analysis"] = self._analyze_failure(
            report_payload=report_payload,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
        )
        report_payload["self_healing_advice"] = self._build_self_healing_advice(
            case=case,
            report_payload=report_payload,
        )
        report_payload["self_healing_suggestion_preview"] = self._load_self_healing_suggestion_preview(report_payload)
        report_payload["self_healing_execution_preview"] = self._load_self_healing_execution_preview(report_payload)
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
        return payload if isinstance(payload, dict) else {}

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
        return {
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
                "likely_cause": "",
                "risk_level": "low",
                "recommended_action": "No immediate failure action is required.",
                "confidence": 1.0,
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
                "likely_cause": report_payload["failure_reason"] or "Unknown execution failure.",
                "risk_level": "medium",
                "recommended_action": "Review the pytest output and captured evidence manually.",
                "confidence": 0.35,
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
        self_healing_advice = report_payload["self_healing_advice"]
        self_healing_suggestion_preview = report_payload.get("self_healing_suggestion_preview", {})
        self_healing_execution_preview = report_payload.get("self_healing_execution_preview", {})
        request_context = report_payload["request_context"]
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
            f"- Likely Cause: {failure_analysis['likely_cause'] or '-'}",
            f"- Risk Level: {failure_analysis['risk_level']}",
            f"- Recommended Action: {failure_analysis['recommended_action']}",
            f"- Confidence: {failure_analysis['confidence']}",
            f"- Evidence Used: {', '.join(failure_analysis['evidence_used']) if failure_analysis['evidence_used'] else '-'}",
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
