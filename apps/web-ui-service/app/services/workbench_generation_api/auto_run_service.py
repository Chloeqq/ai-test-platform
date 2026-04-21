from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services import test_case_service

from .context import WorkbenchContext
from .orchestrator_client import OrchestratorClient
from .repository import WorkbenchGenerationRepository


class AutoRunService:
    def __init__(
        self,
        *,
        context: WorkbenchContext,
    ) -> None:
        self._context = context
        self._orchestrator_client = context.orchestrator_client
        self._generation_service = context.generation
        self._runtime = context.runtime
        self._db = context.db
        self._repository = context.repository

    def execute(self, payload: Any) -> dict[str, Any]:
        self._runtime.ensure_dirs()
        requirement_text = payload.requirement.strip()
        input_sources = [item for item in payload.input_sources if isinstance(item, dict)]
        openapi_spec = payload.openapi_spec if isinstance(payload.openapi_spec, dict) else {}
        has_multisource_inputs = self._generation_service.has_multisource_inputs(
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            prd_text=payload.prd_text,
            prd_url=payload.prd_url,
            user_story=payload.user_story,
            git_diff=payload.git_diff,
            git_diff_path=payload.git_diff_path,
            openapi_url=payload.openapi_url,
            defect_ticket=payload.defect_ticket,
            runtime_logs=payload.runtime_logs,
        )
        raw_urls = [str(item).strip() for item in payload.page_urls if str(item).strip()]
        if not raw_urls:
            raise self._runtime.HTTPException(
                status_code=self._runtime.status.HTTP_400_BAD_REQUEST,
                detail="page_urls must not be empty",
            )

        items: list[dict[str, Any]] = []
        for raw_url in raw_urls:
            page_context = self._generation_service.prepare_auto_run_page_context(
                raw_url=raw_url,
                requirement_text=requirement_text,
                multisource_enabled=has_multisource_inputs,
                build_system_requirement=self._runtime.build_system_requirement,
                extract_page_from_url=self._runtime.extract_page_from_url,
                resolve_page_url=self._runtime.resolve_page_url,
                validate_page_surface_url=self._runtime.validate_page_surface_url,
                extract_page_surface=self._runtime.extract_page_surface,
                normalize_page_surface=self._runtime.normalize_page_surface,
                build_surface_element_candidates=self._runtime.build_surface_element_candidates,
                surface_confidence_summary=self._runtime.surface_confidence_summary,
                enhance_page_object_from_surface=self._runtime.enhance_page_object_from_surface,
                build_requirement_steps=self._runtime.build_requirement_steps,
                build_page_object_quality=self._runtime.build_page_object_quality,
                normalize_page_object_draft=self._runtime.normalize_page_object_draft,
            )
            page_url = str(page_context["page_url"])
            page = str(page_context["page"])
            resolved_page_url = str(page_context["resolved_page_url"])
            effective_requirement = str(page_context["effective_requirement"])
            surface = page_context["surface"] if isinstance(page_context["surface"], dict) else {}
            page_object_path = page_context["page_object_path"]
            steps = page_context["steps"] if isinstance(page_context["steps"], list) else []
            coverage = page_context["coverage"] if isinstance(page_context["coverage"], dict) else {}
            page_object_quality = (
                page_context["page_object_quality"] if isinstance(page_context["page_object_quality"], dict) else {}
            )
            page_object_summary = (
                page_context["page_object_summary"] if isinstance(page_context["page_object_summary"], dict) else {}
            )
            enriched_requirement = f"{effective_requirement}\n目标页面 {page}"
            case_id = ""
            case_path = self._runtime.Path()
            test_points: dict[str, Any] = {}
            test_point_path = self._runtime.Path()
            requirement_spec: dict[str, Any] = self._runtime.build_requirement_spec_for_risk(
                page=page,
                requirement=effective_requirement,
                quality_gate={},
            )
            quality_gate: dict[str, Any] = {}

            try:
                orchestrator_result = self._orchestrator_client.generate(
                    requirement=enriched_requirement,
                    page=page,
                    source=payload.source,
                    input_sources=input_sources,
                    openapi_spec=openapi_spec or None,
                    prd_text=payload.prd_text,
                    prd_url=payload.prd_url,
                    user_story=payload.user_story,
                    git_diff=payload.git_diff,
                    git_diff_path=payload.git_diff_path,
                    openapi_url=payload.openapi_url,
                    defect_ticket=payload.defect_ticket,
                    runtime_logs=payload.runtime_logs,
                )
                orchestrator_requirement_spec = orchestrator_result.get("requirement_spec")
                if isinstance(orchestrator_requirement_spec, dict):
                    requirement_spec = orchestrator_requirement_spec
                quality_gate = self._orchestrator_client.extract_quality_gate(requirement_spec) or {}
                generated_result = self._generation_service.persist_auto_run_generated_case(
                    orchestrator_result=orchestrator_result,
                    project=payload.project,
                    page=page,
                    resolved_page_url=resolved_page_url,
                    effective_requirement=effective_requirement,
                    steps=steps,
                    coverage=coverage,
                    surface=surface,
                    page_object_path=page_object_path,
                    repo_root=self._runtime.REPO_ROOT,
                    ai_cases_root=self._runtime.AI_CASES_ROOT,
                    path_cls=self._runtime.Path,
                    safe_case_id=self._runtime.safe_case_id,
                    datetime_module=self._runtime.datetime,
                    utc=self._runtime.UTC,
                    http_exception_cls=self._runtime.HTTPException,
                    bad_gateway_status=self._runtime.status.HTTP_502_BAD_GATEWAY,
                    write_case_yaml=self._runtime.write_case_yaml,
                    read_case_yaml=self._runtime.read_case_yaml,
                    save_case_state=self._runtime.save_case_state,
                    normalize_test_point_plan_payload=self._runtime.normalize_test_point_plan,
                    steps_to_points=self._runtime.steps_to_points,
                    inherit_test_point_confidence_from_surface=self._runtime.inherit_test_point_confidence_from_surface,
                    annotate_test_point_plan_review=self._runtime.annotate_test_point_plan_review,
                    save_test_point_plan=self._runtime.save_test_point_plan,
                    append_history=self._runtime.append_history,
                    now_iso=self._runtime.now_iso,
                    allocate_case_id=self._repository.allocate_case_id,
                )
                case_id = str(generated_result["case_id"])
                case_path = generated_result["case_path"]
                case_yaml = generated_result["case_yaml"] if isinstance(generated_result.get("case_yaml"), dict) else {}
                if case_yaml:
                    test_case_service.upsert_test_case_from_workbench(
                        self._db,
                        project_code=payload.project,
                        case_yaml=case_yaml,
                        source_path=str(case_path),
                    )
                test_points = generated_result["test_points"] if isinstance(generated_result["test_points"], dict) else {}
                test_point_path = generated_result["test_point_path"]
            except self._runtime.HTTPException as exc:
                blocked_by_quality_gate, blocked_gate = self._orchestrator_client.is_quality_gate_blocked(exc.detail)
                if blocked_by_quality_gate and isinstance(blocked_gate, dict):
                    self._runtime.append_history(
                        {
                            "timestamp": self._runtime.now_iso(),
                            "action": "auto_generate_case_blocked_by_quality_gate",
                            "case_id": case_id,
                            "page": page,
                            "page_url": resolved_page_url,
                            "quality_gate": blocked_gate,
                        }
                    )
                    items.append(
                        self._generation_service.build_auto_run_generate_failed_item(
                            page_url=page_url,
                            resolved_page_url=resolved_page_url,
                            page=page,
                            surface=surface,
                            page_object_path=page_object_path,
                            page_object_quality=page_object_quality,
                            page_object_summary=page_object_summary,
                            coverage=coverage,
                            quality_gate=blocked_gate,
                            runner_script=str((self._runtime.RUNNER_ROOT / "tests" / "test_yaml_ai_generated.py").resolve()),
                        )
                    )
                    continue
                items.append(
                    self._generation_service.build_auto_run_generate_failed_item(
                        page_url=page_url,
                        resolved_page_url=resolved_page_url,
                        page=page,
                        surface=surface,
                        page_object_path=page_object_path,
                        page_object_quality=page_object_quality,
                        page_object_summary=page_object_summary,
                        coverage=coverage,
                        quality_gate={},
                        runner_script=str((self._runtime.RUNNER_ROOT / "tests" / "test_yaml_ai_generated.py").resolve()),
                    )
                )
                continue
            except Exception:  # pragma: no cover
                items.append(
                    self._generation_service.build_auto_run_generate_failed_item(
                        page_url=page_url,
                        resolved_page_url=resolved_page_url,
                        page=page,
                        surface=surface,
                        page_object_path=page_object_path,
                        page_object_quality=page_object_quality,
                        page_object_summary=page_object_summary,
                        coverage=coverage,
                        quality_gate={},
                        runner_script=str((self._runtime.RUNNER_ROOT / "tests" / "test_yaml_ai_generated.py").resolve()),
                    )
                )
                continue

            run_job = self._runtime.start_run(
                project=payload.project,
                case_id=case_id,
                case_path=case_path,
                source="auto-run",
            )
            run_id = str(run_job.get("run_id", "")).strip()
            final_item, timed_out = self._runtime.wait_run_terminal(run_id, timeout_seconds=payload.wait_seconds)
            final_status = str((final_item or run_job).get("status", "running")).strip() or "running"
            has_step_coverage_gap = str(coverage.get("status", "full")).lower() != "full"
            has_page_object_gap = str(page_object_summary.get("status", "full")).lower() != "full"
            if (has_step_coverage_gap or has_page_object_gap) and final_status.lower() == "passed":
                final_status = "coverage_gap"
                self._runtime.update_job(
                    run_id,
                    {"status": final_status, "coverage": coverage, "page_object_summary": page_object_summary},
                )
                self._runtime.update_runtime_run(
                    run_id,
                    {"status": final_status, "coverage": coverage, "page_object_summary": page_object_summary},
                )
            else:
                self._runtime.update_job(run_id, {"coverage": coverage, "page_object_summary": page_object_summary})
                self._runtime.update_runtime_run(run_id, {"coverage": coverage, "page_object_summary": page_object_summary})

            governance_context = self._generation_service.build_auto_run_governance_context(
                project=payload.project,
                run_id=run_id,
                case_id=case_id,
                page=page,
                page_url=resolved_page_url,
                effective_requirement=effective_requirement,
                quality_gate=quality_gate,
                steps=steps,
                final_status=final_status,
                surface=surface,
                page_object_quality=page_object_quality,
                page_object_summary=page_object_summary,
                test_points=test_points,
                coverage=coverage,
                requirement_spec=requirement_spec,
                build_page_analysis_context=self._runtime.build_page_analysis_context,
                build_item_review_state=self._runtime.build_item_review_state,
                evaluate_risk_report=self._runtime.evaluate_risk_report,
                build_execution_gate=self._runtime.build_execution_gate,
            )
            analysis_context = governance_context["analysis_context"] if isinstance(governance_context["analysis_context"], dict) else {}
            risk_report = governance_context["risk_report"] if isinstance(governance_context["risk_report"], dict) else {}
            review_state = governance_context["review_state"] if isinstance(governance_context["review_state"], dict) else {}
            execution_gate = governance_context["execution_gate"] if isinstance(governance_context["execution_gate"], dict) else {}
            sync_payload = governance_context["sync_payload"] if isinstance(governance_context["sync_payload"], dict) else {}
            self._runtime.update_job(run_id, sync_payload)
            self._runtime.update_runtime_run(run_id, sync_payload)
            items.append(
                self._generation_service.build_auto_run_item(
                    page_url=page_url,
                    resolved_page_url=resolved_page_url,
                    page=page,
                    surface=surface,
                    analysis_context=analysis_context,
                    case_id=case_id,
                    case_path=case_path,
                    page_object_path=page_object_path,
                    page_object_quality=page_object_quality,
                    page_object_summary=page_object_summary,
                    test_point_path=test_point_path,
                    test_points=test_points,
                    run_id=run_id,
                    final_status=final_status,
                    coverage=coverage,
                    timed_out=timed_out,
                    risk_report=risk_report,
                    execution_gate=execution_gate,
                    review_state=review_state,
                    runner_script=str((self._runtime.RUNNER_ROOT / "tests" / "test_yaml_ai_generated.py").resolve()),
                )
            )

        allure_payload: dict[str, Any] = {}
        allure_error: Any = ""
        try:
            allure_payload = self._runtime.report_allure_refresh()
        except self._runtime.HTTPException as exc:
            allure_error = exc.detail

        return {
            "summary": self._generation_service.build_auto_run_summary(
                project=payload.project,
                raw_urls=raw_urls,
                items=items,
            ),
            "items": items,
            "allure": {
                "refresh": allure_payload,
                "error": allure_error,
            },
        }
