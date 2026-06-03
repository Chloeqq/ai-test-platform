# mypy: ignore-errors
"""编排流程支撑：需求解析、用例生成、执行编译与报告落盘的顺序编排。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from shared_backend.execution_compiler import ExecutionCompilerError, compile_execution_steps
from shared_backend.schemas.validator import ContractValidator


class OrchestrationFlowSupport:
    """实现 orchestrate 主流程，通过注入的回调与 OrchestratorService 解耦。"""

    _TIMEOUT_CIRCUIT_BREAKER_MAX = 3
    _TIMEOUT_CIRCUIT_RESET_SECONDS = 300  # 5 分钟后重置

    def __init__(
        self,
        *,
        orchestration_result_cls,
        validation_error_cls,
        runner_execution_error_cls,
        allowed_sources: set[str],
        now: Callable[[], str],
        resolve_runner_profile: Callable[[str], dict[str, Any]],
        parse_requirement_spec: Callable[..., dict[str, Any]],
        enforce_requirement_quality_gate: Callable[..., None],
        record_requirement_parse_telemetry: Callable[..., None],
        generate_case: Callable[..., dict[str, Any]],
        build_design_generation: Callable[[dict[str, Any]], dict[str, Any]],
        merge_case_requirements: Callable[[str, dict[str, Any]], list[str]],
        build_test_points_preview: Callable[..., dict[str, Any]],
        resolve_page_object: Callable[[str, str], dict[str, Any]],
        prepare_generated_case_for_assets: Callable[[dict[str, Any]], dict[str, Any]],
        save_case: Callable[[dict[str, Any]], Path],
        agent_pipeline_order: Callable[[], list[str]],
        build_execution_record: Callable[..., dict[str, Any]],
        empty_evidence_manifest: Callable[[], dict[str, Any]],
        build_execution_record_metadata: Callable[..., dict[str, Any]],
        snapshot_evidence_files: Callable[[], set[str]],
        run_case: Callable[[str, Path], Any],
        build_evidence_manifest: Callable[[set[str], set[str]], dict[str, Any]],
        build_and_save_report: Callable[..., tuple[dict[str, Any], Path, Path]],
        build_report_summary_path: Callable[[], str],
    ) -> None:
        self._orchestration_result_cls = orchestration_result_cls
        self._validation_error_cls = validation_error_cls
        self._runner_execution_error_cls = runner_execution_error_cls
        self._allowed_sources = allowed_sources
        self._now = now
        self._resolve_runner_profile = resolve_runner_profile
        self._parse_requirement_spec = parse_requirement_spec
        self._enforce_requirement_quality_gate = enforce_requirement_quality_gate
        self._record_requirement_parse_telemetry = record_requirement_parse_telemetry
        self._generate_case = generate_case
        self._build_design_generation = build_design_generation
        self._merge_case_requirements = merge_case_requirements
        self._build_test_points_preview = build_test_points_preview
        self._resolve_page_object = resolve_page_object
        self._prepare_generated_case_for_assets = prepare_generated_case_for_assets
        self._save_case = save_case
        self._agent_pipeline_order = agent_pipeline_order
        self._build_execution_record = build_execution_record
        self._empty_evidence_manifest = empty_evidence_manifest
        self._build_execution_record_metadata = build_execution_record_metadata
        self._snapshot_evidence_files = snapshot_evidence_files
        self._run_case = run_case
        self._build_evidence_manifest = build_evidence_manifest
        self._build_and_save_report = build_and_save_report
        self._build_report_summary_path = build_report_summary_path
        # 熔断状态
        self._circuit_open = False
        self._consecutive_timeouts = 0
        self._last_timeout_at = None

    def _record_timeout(self) -> None:
        import time
        self._consecutive_timeouts += 1
        self._last_timeout_at = time.time()
        if self._consecutive_timeouts >= self._TIMEOUT_CIRCUIT_BREAKER_MAX:
            self._circuit_open = True

    def _record_success(self) -> None:
        self._consecutive_timeouts = 0
        self._circuit_open = False

    def _check_circuit(self) -> None:
        import time
        if self._circuit_open and self._last_timeout_at:
            elapsed = time.time() - self._last_timeout_at
            if elapsed >= self._TIMEOUT_CIRCUIT_RESET_SECONDS:
                self._circuit_open = False
                self._consecutive_timeouts = 0
        if self._circuit_open:
            raise self._validation_error_cls(
                "orchestrator circuit breaker open: too many consecutive timeouts",
                details={"reason_code": "circuit_breaker_open", "retry_after_seconds": self._TIMEOUT_CIRCUIT_RESET_SECONDS},
            )

    @staticmethod
    def _build_generated_script_shell(*, case: dict[str, Any], runner_profile: dict[str, Any]) -> dict[str, Any]:
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        return {
            "version": "GeneratedScriptV1",
            "framework": str(runner_profile.get("framework", "playwright")).strip() or "playwright",
            "language": str(runner_profile.get("language", "python")).strip() or "python",
            "case_id": str(case.get("id", "")).strip(),
            "page": str(execution.get("page", "")).strip(),
            "filename": "",
            "entrypoint": "",
            "script_code": "",
            "script_path": "",
            "metadata": {
                "runner": str(runner_profile.get("runner", "playwright")).strip() or "playwright",
            },
        }

    @staticmethod
    def _build_execution_plan_shell(
        *,
        case: dict[str, Any],
        execute: bool,
        source: str,
        runner_profile: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "ExecutionPlanV1",
            "run_mode": "generate_and_run" if execute else "generate_only",
            "source": source,
            "priority": str(case.get("priority", "P1")).strip() or "P1",
            "environment": "test",
            "parallelism": 1,
            "retry_policy": {
                "enabled": bool(execute),
                "max_retries": 0,
                "backoff_seconds": 0,
            },
            "stages": [],
            "scheduling_hints": {
                "queue": str(runner_profile.get("environment_pool", "normal")).strip() or "normal",
                "expected_total_seconds": 60,
                "resource_profile": str(runner_profile.get("channel", "default")).strip() or "default",
            },
            "metadata": {
                "runner": str(runner_profile.get("runner", "playwright")).strip() or "playwright",
            },
        }

    @staticmethod
    def _materialize_compiled_steps(*, case: dict[str, Any], compiled_steps: list[dict[str, Any]]) -> dict[str, Any]:
        normalized_case = dict(case) if isinstance(case, dict) else {}
        execution = normalized_case.get("execution") if isinstance(normalized_case.get("execution"), dict) else {}
        execution = dict(execution)
        materialized_steps: list[dict[str, Any]] = []
        for index, raw_step in enumerate(compiled_steps):
            step = raw_step if isinstance(raw_step, dict) else {}
            action = str(step.get("action", "")).strip()
            if not action:
                continue
            traceability = step.get("traceability") if isinstance(step.get("traceability"), dict) else {}
            source_point_key = str(step.get("source_point_key", "")).strip()
            if not source_point_key:
                intent_id = str(step.get("intent_id", "")).strip()
                if intent_id:
                    source_point_key = intent_id
                else:
                    source_index = traceability.get("source_point_index")
                    if isinstance(source_index, int) and source_index >= 0:
                        source_point_key = f"point-{source_index + 1:02d}"
            materialized_step: dict[str, Any] = {
                "action": action,
                "target": str(step.get("target", "")).strip() or None,
                "selector": str(step.get("selector", "")).strip() or None,
                "locator_type": str(step.get("locator_type", "")).strip() or None,
                "intent_id": str(step.get("intent_id", "")).strip() or None,
                "traceability": traceability,
            }
            if source_point_key:
                materialized_step["source_point_key"] = source_point_key
            if step.get("value") is not None:
                materialized_step["value"] = step.get("value")
            if action == "assert_count" and step.get("count") is not None:
                materialized_step["count"] = step.get("count")
            materialized_steps.append(materialized_step)

        if materialized_steps:
            execution["steps"] = materialized_steps
            normalized_case["execution"] = execution
        return normalized_case

    def _validate_compile_and_persist_case(
        self, *, case: dict[str, Any], points: list[dict[str, Any]],
        project: str, resolved_page: str, requirement_spec: dict[str, Any],
    ) -> dict[str, Any]:
        """验证测试点合约、编译执行步骤、持久化生成产物。返回更新后的 case。"""
        try:
            page_object = self._resolve_page_object(project, resolved_page)
        except Exception as exc:
            if isinstance(exc, self._validation_error_cls):
                raise
            raise self._validation_error_cls(
                "page object resolution failed",
                details={"reason_code": "page_object_not_found", "project": project,
                         "page": resolved_page, "upstream_error": str(exc)[:500]}) from exc
        try:
            from shared_backend.schemas.contracts import normalize_test_point_plan_v1
            plan_wrapper = {"version": "TestPointPlanV1", "project": project,
                            "page": resolved_page, "points": points}
            normalized_plan, _warnings = normalize_test_point_plan_v1(plan_wrapper)
            points = normalized_plan.get("points", points)
        except Exception:
            pass
        validation_result = ContractValidator().validate_full(
            requirement_spec if isinstance(requirement_spec, dict) else None,
            points, page_object, strict=True)
        if not validation_result.valid:
            raise self._validation_error_cls(
                "test point contract validation failed",
                details={"reason_code": "test_point_contract_validation_failed",
                         "errors": validation_result.errors, "warnings": validation_result.warnings})
        try:
            compiled_steps = compile_execution_steps(points, page_object)
        except ExecutionCompilerError as exc:
            raise self._validation_error_cls(
                "execution compiler failed", details=exc.to_detail()) from exc
        case = self._materialize_compiled_steps(case=case, compiled_steps=compiled_steps)
        try:
            case = self._prepare_generated_case_for_assets(case)
        except Exception as exc:
            raise self._validation_error_cls(
                "generated case failed asset validation",
                details={"reason_code": "asset_validation_failed", "upstream_error": str(exc)[:500]}) from exc
        try:
            case_path = self._save_case(case)
        except Exception as exc:
            raise self._validation_error_cls(
                "generated case asset persist failed",
                details={"reason_code": "asset_persist_failed", "upstream_error": str(exc)[:500]}) from exc
        case["id"] = str(case_path.stem).strip()
        return case

    def orchestrate(
        self,
        *,
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
    ):
        """执行完整编排流水线并返回 OrchestrationResult。"""
        self._check_circuit()
        normalized_requirement = requirement.strip()
        normalized_page = page.strip()
        if not normalized_page:
            raise self._validation_error_cls("page must not be empty")
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
                raise self._validation_error_cls("requirement must not be empty")

        normalized_source = source.strip().lower()
        if normalized_source not in self._allowed_sources:
            raise self._validation_error_cls("source must be one of: manual, ai, regression")
        normalized_mode = mode.strip().lower() if isinstance(mode, str) and mode.strip() else None
        if normalized_mode is None:
            normalized_mode = "generate_and_run" if execute else "generate_only"
        runner_profile = self._resolve_runner_profile(runner)
        if execute and not bool(runner_profile.get("execution_supported", False)):
            raise self._validation_error_cls(f"runner {runner_profile.get('runner')} does not support execute=true yet")

        requirement_spec = self._parse_requirement_spec(
            requirement=requirement,
            page=normalized_page,
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
        resolved_page = str(requirement_spec.get("page", "")).strip() or normalized_page
        requirement_spec["page"] = resolved_page

        try:
            self._enforce_requirement_quality_gate(requirement_spec, stage="orchestrate")
            self._record_requirement_parse_telemetry(
                requirement_spec=requirement_spec,
                stage="orchestrate",
                source=normalized_source,
                outcome="allow",
            )
        except self._validation_error_cls:
            self._record_requirement_parse_telemetry(
                requirement_spec=requirement_spec,
                stage="orchestrate",
                source=normalized_source,
                outcome="block",
            )
            raise

        design_requirement = str(requirement_spec.get("design_input", "")).strip() or normalized_requirement
        if not design_requirement:
            design_requirement = str(requirement_spec.get("normalized_requirement", "")).strip()
        if not design_requirement:
            raise self._validation_error_cls(
                "design requirement is empty",
                details={"reason_code": "test_design_request_invalid"},
            )

        case = self._generate_case(requirement=design_requirement, page=resolved_page)
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        execution["runner"] = str(runner_profile.get("runner", "playwright")).strip() or "playwright"
        execution["page"] = str(execution.get("page", "")).strip() or resolved_page
        case["execution"] = execution
        design_generation = self._build_design_generation(case)
        case["requirement"] = self._merge_case_requirements(
            raw_requirement=requirement or design_requirement,
            requirement_spec=requirement_spec,
        )
        generated_script = self._build_generated_script_shell(case=case, runner_profile=runner_profile)
        execution_plan = self._build_execution_plan_shell(
            case=case,
            execute=execute,
            source=normalized_source,
            runner_profile=runner_profile,
        )
        test_points = self._build_test_points_preview(
            case=case,
            requirement_spec=requirement_spec,
        )
        points = test_points.get("points") if isinstance(test_points.get("points"), list) else []
        if not points:
            raise self._validation_error_cls(
                "test points are empty",
                details={"reason_code": "execution_compiler_missing_test_points"},
            )
        project = str(case.get("project", "")).strip() or str(requirement_spec.get("project", "")).strip() or "mall"
        case = self._validate_compile_and_persist_case(
            case=case, points=points, project=project,
            resolved_page=resolved_page, requirement_spec=requirement_spec)
        started_at = self._now()

        result = self._orchestration_result_cls(
            requirement_spec=requirement_spec,
            case=case,
            generated_script=generated_script,
            execution_plan=execution_plan,
            design_generation=design_generation,
            risk_report={},
            failure_triage={},
            agent_pipeline=self._agent_pipeline_order(),
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
                metadata=self._build_execution_record_metadata(
                    requirement_spec=requirement_spec,
                    test_points=test_points,
                    runner_profile=runner_profile,
                ),
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
                metadata=self._build_execution_record_metadata(
                    requirement_spec=requirement_spec,
                    test_points=test_points,
                    runner_profile=runner_profile,
                ),
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
                runner_profile=runner_profile,
            )
                raise self._runner_execution_error_cls(
                    "Runner execution failed",
                    details={
                        "runner_exit_code": completed.returncode,
                        "runner_stdout": completed.stdout,
                        "runner_stderr": completed.stderr,
                        "report": report_payload,
                        "report_json_path": str(report_json_path),
                        "report_markdown_path": str(report_markdown_path),
                        "report_summary_path": self._build_report_summary_path() if execute else "",
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
            runner_profile=runner_profile,
        )
        result.report = report_payload
        result.report_json_path = str(report_json_path)
        result.report_markdown_path = str(report_markdown_path)
        result.report_summary_path = self._build_report_summary_path() if execute else ""
        result.risk_report = report_payload.get("risk_report", {})
        result.failure_triage = report_payload.get("failure_triage", {})
        if not execute:
            result.execution_record = report_payload["execution_record"]

        self._record_success()
        return result
