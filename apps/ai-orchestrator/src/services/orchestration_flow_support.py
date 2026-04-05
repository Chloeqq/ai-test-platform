# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class OrchestrationFlowSupport:
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
        generate_script_bundle: Callable[..., dict[str, Any]],
        build_execution_plan: Callable[..., dict[str, Any]],
        build_test_points_preview: Callable[..., dict[str, Any]],
        render_case_steps_from_test_points: Callable[..., dict[str, Any]],
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
        self._generate_script_bundle = generate_script_bundle
        self._build_execution_plan = build_execution_plan
        self._build_test_points_preview = build_test_points_preview
        self._render_case_steps_from_test_points = render_case_steps_from_test_points
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
            design_requirement = str(requirement_spec.get("normalized_requirement", "")).strip() or "基础流程验证"

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
        generated_script = self._generate_script_bundle(
            case=case,
            framework=str(runner_profile.get("framework", "playwright")).strip() or "playwright",
            language=str(runner_profile.get("language", "python")).strip() or "python",
        )
        execution_plan = self._build_execution_plan(
            case=case,
            execution_requested=execute,
            source=normalized_source,
            execution_config={"runner_profile": runner_profile},
        )
        test_points = self._build_test_points_preview(
            case=case,
            requirement_spec=requirement_spec,
        )
        case = self._render_case_steps_from_test_points(case=case, test_points=test_points)
        case = self._prepare_generated_case_for_assets(case)
        case_path = self._save_case(case)
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

        return result
