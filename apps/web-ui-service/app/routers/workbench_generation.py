from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.services import workbench_generation_service
from . import legacy_workbench


router = APIRouter(tags=["workbench-generation"])


@router.post("/api/workbench/generate", status_code=status.HTTP_201_CREATED)
def generate_case(payload: legacy_workbench.GenerateCasePayload) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    normalized_page = legacy_workbench._normalize_page_slug(payload.page) if payload.page.strip() else ""
    requirement_text = payload.requirement.strip()
    input_sources = [item for item in payload.input_sources if isinstance(item, dict)]
    openapi_spec = payload.openapi_spec if isinstance(payload.openapi_spec, dict) else {}
    has_multisource_inputs = workbench_generation_service.has_multisource_inputs(
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
    effective_requirement = workbench_generation_service.resolve_effective_requirement(
        requirement_text=requirement_text,
        normalized_page=normalized_page,
        multisource_enabled=has_multisource_inputs,
        build_system_requirement=legacy_workbench._build_system_requirement,
    )
    if not effective_requirement and not has_multisource_inputs and not normalized_page:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_400_BAD_REQUEST,
            detail="requirement must not be empty when no page or additional input sources are provided",
        )
    return workbench_generation_service.build_generated_case_payload(
        payload=payload,
        normalized_page=normalized_page,
        effective_requirement=effective_requirement,
        multisource_enabled=has_multisource_inputs,
        input_sources=input_sources,
        openapi_spec=openapi_spec,
        run_orchestrator_generate=legacy_workbench._run_orchestrator_generate,
        extract_quality_gate=legacy_workbench._extract_quality_gate,
        safe_case_id=legacy_workbench._safe_case_id,
        infer_targets=legacy_workbench._infer_targets,
        write_case_yaml=legacy_workbench._write_case_yaml,
        save_case_state=legacy_workbench._save_case_state,
        append_history=legacy_workbench._append_history,
        now_iso=legacy_workbench._now_iso,
        is_quality_gate_blocked=legacy_workbench._is_quality_gate_blocked,
        ai_cases_root=legacy_workbench.AI_CASES_ROOT,
        utc=legacy_workbench.UTC,
        datetime_module=legacy_workbench.datetime,
        http_exception_cls=legacy_workbench.HTTPException,
        bad_gateway_status=legacy_workbench.status.HTTP_502_BAD_GATEWAY,
        unprocessable_entity_status=422,
    )


@router.post("/api/workbench/preview-test-points")
def preview_test_points(payload: legacy_workbench.GenerateCasePayload) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    requirement_text = payload.requirement.strip()
    normalized_page = legacy_workbench._normalize_page_slug(payload.page) if payload.page.strip() else ""
    input_sources = [item for item in payload.input_sources if isinstance(item, dict)]
    openapi_spec = payload.openapi_spec if isinstance(payload.openapi_spec, dict) else {}
    has_multisource_inputs = workbench_generation_service.has_multisource_inputs(
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
    effective_requirement = workbench_generation_service.resolve_effective_requirement(
        requirement_text=requirement_text,
        normalized_page=normalized_page,
        multisource_enabled=has_multisource_inputs,
        build_system_requirement=legacy_workbench._build_system_requirement,
    )
    if not effective_requirement and not has_multisource_inputs and not normalized_page:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_400_BAD_REQUEST,
            detail="requirement must not be empty when no page or additional input sources are provided",
        )
    return workbench_generation_service.build_preview_test_points_payload(
        effective_requirement=effective_requirement,
        normalized_page=normalized_page,
        source=payload.source,
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
        run_orchestrator_parse=legacy_workbench._run_orchestrator_parse,
        render_requirement_spec_markdown=legacy_workbench._render_requirement_spec_markdown,
        extract_quality_gate=legacy_workbench._extract_quality_gate,
    )


@router.post("/api/workbench/auto-run")
def auto_run(payload: legacy_workbench.AutoRunPayload) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    requirement_text = payload.requirement.strip()
    input_sources = [item for item in payload.input_sources if isinstance(item, dict)]
    openapi_spec = payload.openapi_spec if isinstance(payload.openapi_spec, dict) else {}
    has_multisource_inputs = workbench_generation_service.has_multisource_inputs(
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
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_400_BAD_REQUEST,
            detail="page_urls must not be empty",
        )

    items: list[dict[str, Any]] = []
    for raw_url in raw_urls:
        page_context = workbench_generation_service.prepare_auto_run_page_context(
            raw_url=raw_url,
            requirement_text=requirement_text,
            multisource_enabled=has_multisource_inputs,
            build_system_requirement=legacy_workbench._build_system_requirement,
            extract_page_from_url=legacy_workbench._extract_page_from_url,
            resolve_page_url=legacy_workbench._resolve_page_url,
            validate_page_surface_url=legacy_workbench._validate_page_surface_url,
            extract_page_surface=legacy_workbench._extract_page_surface,
            normalize_page_surface=legacy_workbench._normalize_page_surface,
            build_surface_element_candidates=legacy_workbench._build_surface_element_candidates,
            surface_confidence_summary=legacy_workbench._surface_confidence_summary,
            enhance_page_object_from_surface=legacy_workbench._enhance_page_object_from_surface,
            build_requirement_steps=legacy_workbench._build_requirement_steps,
            build_page_object_quality=legacy_workbench._build_page_object_quality,
            normalize_page_object_draft=legacy_workbench._normalize_page_object_draft,
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
        orchestrator_result: dict[str, Any]
        case_id = ""
        case_path = legacy_workbench.Path()
        test_points: dict[str, Any] = {}
        test_point_path = legacy_workbench.Path()
        requirement_spec: dict[str, Any] = legacy_workbench._build_requirement_spec_for_risk(
            page=page,
            requirement=effective_requirement,
            quality_gate={},
        )
        quality_gate: dict[str, Any] = {}

        try:
            orchestrator_result = legacy_workbench._run_orchestrator_generate(
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
            quality_gate = legacy_workbench._extract_quality_gate(requirement_spec) or {}
            generated_result = workbench_generation_service.persist_auto_run_generated_case(
                orchestrator_result=orchestrator_result,
                project=payload.project,
                page=page,
                resolved_page_url=resolved_page_url,
                effective_requirement=effective_requirement,
                steps=steps,
                coverage=coverage,
                surface=surface,
                page_object_path=page_object_path,
                repo_root=legacy_workbench.REPO_ROOT,
                ai_cases_root=legacy_workbench.AI_CASES_ROOT,
                path_cls=legacy_workbench.Path,
                safe_case_id=legacy_workbench._safe_case_id,
                datetime_module=legacy_workbench.datetime,
                utc=legacy_workbench.UTC,
                http_exception_cls=legacy_workbench.HTTPException,
                bad_gateway_status=legacy_workbench.status.HTTP_502_BAD_GATEWAY,
                write_case_yaml=legacy_workbench._write_case_yaml,
                read_case_yaml=legacy_workbench._read_case_yaml,
                save_case_state=legacy_workbench._save_case_state,
                normalize_test_point_plan_payload=legacy_workbench._normalize_test_point_plan_payload,
                steps_to_points=legacy_workbench._steps_to_points,
                inherit_test_point_confidence_from_surface=legacy_workbench._inherit_test_point_confidence_from_surface,
                annotate_test_point_plan_review=legacy_workbench._annotate_test_point_plan_review,
                save_test_point_plan=legacy_workbench._save_test_point_plan,
                append_history=legacy_workbench._append_history,
                now_iso=legacy_workbench._now_iso,
            )
            case_id = str(generated_result["case_id"])
            case_path = generated_result["case_path"]
            test_points = generated_result["test_points"] if isinstance(generated_result["test_points"], dict) else {}
            test_point_path = generated_result["test_point_path"]
        except legacy_workbench.HTTPException as exc:
            blocked_by_quality_gate, blocked_gate = legacy_workbench._is_quality_gate_blocked(exc.detail)
            if blocked_by_quality_gate and isinstance(blocked_gate, dict):
                legacy_workbench._append_history(
                    {
                        "timestamp": legacy_workbench._now_iso(),
                        "action": "auto_generate_case_blocked_by_quality_gate",
                        "case_id": case_id,
                        "page": page,
                        "page_url": resolved_page_url,
                        "quality_gate": blocked_gate,
                        "fallback_reason": exc.detail,
                    }
                )
                items.append(
                    workbench_generation_service.build_auto_run_generate_failed_item(
                        page_url=page_url,
                        resolved_page_url=resolved_page_url,
                        page=page,
                        surface=surface,
                        page_object_path=page_object_path,
                        page_object_quality=page_object_quality,
                        page_object_summary=page_object_summary,
                        coverage=coverage,
                        quality_gate=blocked_gate,
                        runner_script=str(
                            (legacy_workbench.RUNNER_ROOT / "tests" / "test_yaml_ai_generated.py").resolve()
                        ),
                    )
                )
                continue
            fallback_result = workbench_generation_service.persist_auto_run_fallback_case(
                page=page,
                effective_requirement=effective_requirement,
                resolved_page_url=resolved_page_url,
                steps=steps,
                project=payload.project,
                page_object_path=page_object_path,
                surface=surface,
                coverage=coverage,
                fallback_reason=exc.detail,
                build_fallback_case=legacy_workbench._build_fallback_case,
                safe_case_id=legacy_workbench._safe_case_id,
                write_case_yaml=legacy_workbench._write_case_yaml,
                read_case_yaml=legacy_workbench._read_case_yaml,
                save_case_state=legacy_workbench._save_case_state,
                steps_to_points=legacy_workbench._steps_to_points,
                inherit_test_point_confidence_from_surface=legacy_workbench._inherit_test_point_confidence_from_surface,
                annotate_test_point_plan_review=legacy_workbench._annotate_test_point_plan_review,
                save_test_point_plan=legacy_workbench._save_test_point_plan,
                append_history=legacy_workbench._append_history,
                now_iso=legacy_workbench._now_iso,
                ai_cases_root=legacy_workbench.AI_CASES_ROOT,
            )
            case_id = str(fallback_result["case_id"])
            case_path = fallback_result["case_path"]
            test_points = fallback_result["test_points"] if isinstance(fallback_result["test_points"], dict) else {}
            test_point_path = fallback_result["test_point_path"]
        except Exception as exc:  # pragma: no cover
            fallback_result = workbench_generation_service.persist_auto_run_fallback_case(
                page=page,
                effective_requirement=effective_requirement,
                resolved_page_url=resolved_page_url,
                steps=steps,
                project=payload.project,
                page_object_path=page_object_path,
                surface=surface,
                coverage=coverage,
                fallback_reason=str(exc),
                build_fallback_case=legacy_workbench._build_fallback_case,
                safe_case_id=legacy_workbench._safe_case_id,
                write_case_yaml=legacy_workbench._write_case_yaml,
                read_case_yaml=legacy_workbench._read_case_yaml,
                save_case_state=legacy_workbench._save_case_state,
                steps_to_points=legacy_workbench._steps_to_points,
                inherit_test_point_confidence_from_surface=legacy_workbench._inherit_test_point_confidence_from_surface,
                annotate_test_point_plan_review=legacy_workbench._annotate_test_point_plan_review,
                save_test_point_plan=legacy_workbench._save_test_point_plan,
                append_history=legacy_workbench._append_history,
                now_iso=legacy_workbench._now_iso,
                ai_cases_root=legacy_workbench.AI_CASES_ROOT,
            )
            case_id = str(fallback_result["case_id"])
            case_path = fallback_result["case_path"]
            test_points = fallback_result["test_points"] if isinstance(fallback_result["test_points"], dict) else {}
            test_point_path = fallback_result["test_point_path"]

        run_job = legacy_workbench._start_run(
            project=payload.project,
            case_id=case_id,
            case_path=case_path,
            source="auto-run",
        )
        run_id = str(run_job.get("run_id", "")).strip()
        final_item, timed_out = legacy_workbench._wait_run_terminal(run_id, timeout_seconds=payload.wait_seconds)
        final_status = str((final_item or run_job).get("status", "running")).strip() or "running"
        has_step_coverage_gap = str(coverage.get("status", "full")).lower() != "full"
        has_page_object_gap = str(page_object_summary.get("status", "full")).lower() != "full"
        if (has_step_coverage_gap or has_page_object_gap) and final_status.lower() == "passed":
            final_status = "coverage_gap"
            legacy_workbench._update_job(
                run_id,
                {"status": final_status, "coverage": coverage, "page_object_summary": page_object_summary},
            )
            legacy_workbench._update_runtime_run(
                run_id,
                {"status": final_status, "coverage": coverage, "page_object_summary": page_object_summary},
            )
        else:
            legacy_workbench._update_job(run_id, {"coverage": coverage, "page_object_summary": page_object_summary})
            legacy_workbench._update_runtime_run(run_id, {"coverage": coverage, "page_object_summary": page_object_summary})

        governance_context = workbench_generation_service.build_auto_run_governance_context(
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
            build_page_analysis_context=legacy_workbench._build_page_analysis_context,
            build_item_review_state=legacy_workbench._build_item_review_state,
            evaluate_risk_report=legacy_workbench._evaluate_risk_report,
            build_execution_gate=legacy_workbench._build_execution_gate,
        )
        analysis_context = (
            governance_context["analysis_context"] if isinstance(governance_context["analysis_context"], dict) else {}
        )
        risk_report = governance_context["risk_report"] if isinstance(governance_context["risk_report"], dict) else {}
        review_state = governance_context["review_state"] if isinstance(governance_context["review_state"], dict) else {}
        execution_gate = (
            governance_context["execution_gate"] if isinstance(governance_context["execution_gate"], dict) else {}
        )
        sync_payload = governance_context["sync_payload"] if isinstance(governance_context["sync_payload"], dict) else {}
        legacy_workbench._update_job(run_id, sync_payload)
        legacy_workbench._update_runtime_run(run_id, sync_payload)
        items.append(
            workbench_generation_service.build_auto_run_item(
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
                runner_script=str((legacy_workbench.RUNNER_ROOT / "tests" / "test_yaml_ai_generated.py").resolve()),
            )
        )

    allure_payload: dict[str, Any] = {}
    allure_error: Any = ""
    try:
        allure_payload = legacy_workbench.report_allure_refresh()
    except legacy_workbench.HTTPException as exc:
        allure_error = exc.detail

    return {
        "summary": workbench_generation_service.build_auto_run_summary(
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
