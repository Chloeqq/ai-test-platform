from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Protocol

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.page_object import PageElement, PageObject

from ..debug import debug_enabled, log_debug_event
from shared_backend.execution_compiler import ExecutionCompilerError, compile_execution_steps
from shared_backend.schemas.contracts import normalize_test_point_plan_v1
from shared_backend.schemas.validator import ContractValidator

_YAML_PAGE_OBJECT_ROOT = Path(__file__).resolve().parents[6] / "assets" / "page-objects" / "web"


class RunOrchestratorGenerate(Protocol):
    def __call__(self, requirement: str, *, page: str, **kwargs: Any) -> dict[str, Any]: ...


class ExtractQualityGate(Protocol):
    def __call__(self, result: dict[str, Any] | None) -> dict[str, Any] | None: ...


class WriteCaseYaml(Protocol):
    def __call__(self, case_id: str, data: dict[str, Any], **kwargs: Any) -> str: ...


class AllocateCaseId(Protocol):
    def __call__(self, prefix: str, **kwargs: Any) -> str: ...


SafeCaseId = Callable[[str], str]
InferTargets = Callable[[str], tuple[str, str]]
SaveCaseState = Callable[[str, dict[str, Any], Any], dict[str, Any]]
AppendHistory = Callable[[dict[str, Any]], None]
NowIso = Callable[[], str]
IsQualityGateBlocked = Callable[[Any], tuple[bool, dict[str, Any] | None]]


_LOGGER = logging.getLogger(__name__)
_COMPILER_ERROR_CODES = {
    "execution_compiler_missing_test_points",
    "execution_compiler_empty_test_points",
    "execution_compiler_invalid_point",
    "execution_compiler_missing_intent_id",
    "execution_compiler_unrecognized_step",
    "execution_compiler_invalid_dsl_action",
    "execution_compiler_intent_coverage_failed",
    "execution_ir_empty_steps",
    "page_object_not_found",
    "page_object_empty_elements",
    "target_binding_failed",
    "execution_render_failed",
}


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _resolve_page_object_from_db(project: str, page: str) -> dict[str, Any] | None:
    """Attempt to load page object elements from the database. Returns None on miss."""
    try:
        with SessionLocal() as db:
            page_object = db.execute(
                select(PageObject).where(
                    PageObject.project_code == project,
                    PageObject.client == "web",
                    PageObject.page_code == page,
                )
            ).scalar_one_or_none()
            if page_object is None:
                return None
            elements = (
                db.execute(
                    select(PageElement)
                    .where(PageElement.page_object_id == int(page_object.id))
                    .order_by(PageElement.id.asc())
                )
                .scalars()
                .all()
            )
    except Exception:
        _LOGGER.debug("DB page-object lookup failed for %s/%s", project, page, exc_info=True)
        return None
    if not elements:
        return None
    mapping: dict[str, dict[str, str]] = {}
    for element in elements:
        code = _normalized_text(getattr(element, "element_code", ""))
        selector = _normalized_text(getattr(element, "locator_value", ""))
        if not code or not selector:
            continue
        mapping[code] = {
            "selector": selector,
            "type": _normalized_text(getattr(element, "locator_type", "")) or "css",
            "role": _normalized_text(getattr(element, "role", "")),
        }
    return {"elements": mapping} if mapping else None


def resolve_page_object(project: str, page: str) -> dict[str, Any]:
    normalized_project = _normalized_text(project)
    normalized_page = _normalized_text(page).lower()
    if not normalized_project or not normalized_page:
        raise ExecutionCompilerError(
            code="page_object_not_found",
            message="page object identity is required",
            reason="project/page is empty",
            stage="resolve_page_object",
        )

    db_result = _resolve_page_object_from_db(normalized_project, normalized_page)
    if db_result is not None:
        return db_result

    raise ExecutionCompilerError(
        code="page_object_not_found",
        message="page object not found in DB",
        reason=f"{normalized_project}/web/{normalized_page}",
        stage="resolve_page_object",
    )


def run_generate_pipeline(
    *,
    payload: Any,
    normalized_page: str,
    effective_requirement: str,
    multisource_enabled: bool,
    input_sources: list[dict[str, Any]],
    openapi_spec: dict[str, Any],
    run_orchestrator_generate: RunOrchestratorGenerate,
    extract_quality_gate: ExtractQualityGate,
    safe_case_id: SafeCaseId,
    infer_targets: InferTargets,
    write_case_yaml: WriteCaseYaml,
    save_case_state: SaveCaseState,
    append_history: AppendHistory,
    now_iso: NowIso,
    is_quality_gate_blocked: IsQualityGateBlocked,
    ai_cases_root: Any,
    utc: Any,
    datetime_module: Any,
    http_exception_cls: Any,
    bad_gateway_status: int,
    unprocessable_entity_status: int,
    existing_case_ids: list[str] | None = None,
    selected_candidate: dict[str, Any] | None = None,
    allocate_case_id: AllocateCaseId,
    trace_id: str = "",
    mode: str = "generate",
) -> dict[str, Any]:
    _ = safe_case_id, infer_targets, utc, datetime_module
    log_debug_event(
        logger=_LOGGER,
        event="runtime.generate.input",
        trace_id=trace_id,
        payload={
            "project": str(getattr(payload, "project", "") or ""),
            "page": normalized_page,
            "requirement": effective_requirement,
            "multisource_enabled": multisource_enabled,
            "input_sources": input_sources,
            "openapi_spec": openapi_spec,
            "existing_case_ids": existing_case_ids or [],
            "selected_candidate": selected_candidate if isinstance(selected_candidate, dict) else {},
        },
        extra={"compare_with_event": "service.generate.input"},
    )
    orchestrator_result: dict[str, Any] = {}
    case_yaml: dict[str, Any] = {}
    resolved_page = normalized_page
    quality_gate: dict[str, Any] | None = None
    try:
        orchestrator_result = run_orchestrator_generate(
            requirement=effective_requirement,
            page=normalized_page,
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
        )
        quality_gate = extract_quality_gate(orchestrator_result.get("requirement_spec"))
        generated_case = orchestrator_result.get("case") or {}
        if not isinstance(generated_case, dict) or not generated_case:
            raise http_exception_cls(status_code=bad_gateway_status, detail="orchestrator returned invalid case payload")
        case_yaml = generated_case
        execution_payload = case_yaml.get("execution")
        if not isinstance(execution_payload, dict):
            execution_payload = {}
            case_yaml["execution"] = execution_payload
        resolved_page = (
            str(execution_payload.get("page", "")).strip()
            or str(orchestrator_result.get("requirement_spec", {}).get("page", "")).strip()
            or normalized_page
            or "product"
        )
        execution_payload["page"] = resolved_page
        case_yaml["module"] = str(case_yaml.get("module", "")).strip() or resolved_page
        case_yaml["description"] = (
            str(case_yaml.get("description", "")).strip()
            or f"AI generated from requirement: {effective_requirement or 'multi-source'}"
        )
        test_points_payload = orchestrator_result.get("test_points")
        if not isinstance(test_points_payload, dict):
            test_points_payload = {}
            orchestrator_result["test_points"] = test_points_payload
        test_points = test_points_payload.get("points")
        if not isinstance(test_points, list) or not test_points:
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail={
                    "code": "execution_compiler_missing_test_points",
                    "message": "orchestrator returned no test points",
                    "reason": "test_points.points is empty",
                    "stage": "run_generate_pipeline",
                },
            )
        try:
            plan_wrapper = {
                "version": "TestPointPlanV1",
                "project": str(getattr(payload, "project", "atp") or "atp"),
                "case_id": str(getattr(payload, "case_id", "") or ""),
                "page": resolved_page,
                "points": test_points,
            }
            normalized_plan, _contract_warnings = normalize_test_point_plan_v1(plan_wrapper)
            test_points = normalized_plan.get("points", test_points)
        except Exception:
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail={
                    "code": "execution_compiler_contract_normalization_failed",
                    "message": "test point normalization failed",
                    "reason": "normalize_test_point_plan_v1 raised an exception",
                    "stage": "run_generate_pipeline",
                },
            )

        try:
            page_object = resolve_page_object(str(payload.project or ""), resolved_page)
        except ExecutionCompilerError as page_object_exc:
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail=page_object_exc.to_detail(),
            ) from page_object_exc

        validator = ContractValidator()
        validation_result = validator.validate_full(
            orchestrator_result.get("requirement_spec") if isinstance(orchestrator_result.get("requirement_spec"), dict) else None,
            test_points if isinstance(test_points, list) else [],
            page_object,
            strict=True,
        )
        if not validation_result.valid:
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail={
                    "code": "test_point_contract_validation_failed",
                    "message": "test point contract validation failed",
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                    "stage": "run_generate_pipeline",
                },
            )

        compiled_steps = compile_execution_steps(test_points, page_object)
        execution_payload["steps"] = compiled_steps
        orchestrator_result["execution_requested"] = True
        review_summary = test_points_payload.get("review_summary")
        if isinstance(review_summary, dict):
            review_summary["intent_coverage_status"] = "covered"
            review_summary["status"] = "covered"
            review_summary["orphan_point_count"] = 0
            review_summary["orphan_step_count"] = 0
        log_debug_event(
            logger=_LOGGER,
            event="runtime.generate.orchestrator_output",
            trace_id=trace_id,
            payload=orchestrator_result,
        )
    except Exception as exc:
        if isinstance(exc, ExecutionCompilerError):
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail=exc.to_detail(),
            ) from exc
        if isinstance(exc, http_exception_cls):
            is_gate_blocked, blocked_gate = is_quality_gate_blocked(getattr(exc, "detail", ""))
            if is_gate_blocked and isinstance(blocked_gate, dict):
                append_history(
                    {
                        "timestamp": now_iso(),
                        "action": "generate_case_blocked_by_quality_gate",
                        "case_id": payload.case_id.strip(),
                        "page": normalized_page,
                        "source": payload.source,
                        "multi_source_enabled": multisource_enabled,
                        "quality_gate": blocked_gate,
                        "orchestrator_error_reason": getattr(exc, "detail", ""),
                    }
                )
                raise http_exception_cls(
                    status_code=getattr(exc, "status_code", unprocessable_entity_status)
                    if isinstance(getattr(exc, "status_code", None), int)
                    else unprocessable_entity_status,
                    detail={
                        "code": "requirement_quality_gate_blocked",
                        "message": "requirement quality gate blocked orchestration",
                        "quality_gate": blocked_gate,
                        "upstream_error": getattr(exc, "detail", ""),
                    },
                ) from exc
            upstream_status_code = getattr(exc, "status_code", None)
            upstream_detail = getattr(exc, "detail", "")
            detail_payload = upstream_detail if isinstance(upstream_detail, dict) else {}
            detail_code = str(detail_payload.get("code", "")).strip().lower()
            detail_reason_code = str(detail_payload.get("reason_code", "")).strip().lower()
            if (
                isinstance(upstream_status_code, int)
                and upstream_status_code == unprocessable_entity_status
                and detail_code in _COMPILER_ERROR_CODES
            ):
                raise http_exception_cls(
                    status_code=unprocessable_entity_status,
                    detail=detail_payload or {
                        "code": "execution_compiler_failed",
                        "message": "execution compiler failed",
                        "reason": str(upstream_detail)[:500],
                        "stage": "run_generate_pipeline",
                    },
                ) from exc
            if (
                isinstance(upstream_status_code, int)
                and upstream_status_code == unprocessable_entity_status
                and (
                    detail_code == "validation_error"
                    or detail_reason_code == "test_design_invalid_output"
                )
            ):
                raise http_exception_cls(
                    status_code=unprocessable_entity_status,
                    detail=detail_payload or {
                        "code": "validation_error",
                        "message": str(upstream_detail)[:500],
                    },
                ) from exc
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail={
                    "code": "orchestrator_generate_failed",
                    "message": "orchestrator generate failed",
                    "upstream_error": str(upstream_detail)[:500],
                },
            ) from exc
        else:
            upstream_error = str(exc)
            log_debug_event(
                logger=_LOGGER,
                event="runtime.generate.exception",
                trace_id=trace_id,
                payload={
                    "error": upstream_error[:500],
                    "is_http_exception": False,
                },
            )
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail={
                    "code": "orchestrator_generate_failed",
                    "message": "orchestrator generate failed",
                    "upstream_error": upstream_error[:500],
                },
            ) from exc

    case_id = allocate_case_id(
        requested_case_id=payload.case_id or case_yaml.get("id", ""),
        project=payload.project,
        page=resolved_page or normalized_page or "product",
        module=str(case_yaml.get("module", "")).strip() or resolved_page or normalized_page or "product",
        ai_cases_root=ai_cases_root,
        existing_case_ids=existing_case_ids,
    )
    case_yaml["id"] = case_id
    if payload.title.strip():
        case_yaml["title"] = payload.title.strip()
    if payload.priority.strip():
        case_yaml["priority"] = payload.priority.strip()
    cleaned_tags = [item.strip() for item in payload.tags if item.strip()]
    case_yaml["tags"] = cleaned_tags or [item.strip() for item in case_yaml.get("tags", []) if str(item).strip()] or ["ai-generated"]
    execution_payload = case_yaml.get("execution")
    if not isinstance(execution_payload, dict):
        execution_payload = {}
        case_yaml["execution"] = execution_payload
    execution_payload["page"] = resolved_page or "product"
    case_yaml["module"] = str(case_yaml.get("module", "")).strip() or execution_payload["page"]

    case_path = ai_cases_root / f"{case_id}.yaml"
    final_text = write_case_yaml(case_path, case_yaml)
    state_entry = save_case_state(payload.project, case_yaml, case_path)
    append_history(
        {
            "timestamp": now_iso(),
            "action": "generate_case",
            "case_id": case_id,
            "title": str(case_yaml.get("title", case_id)),
            "path": str(case_path.resolve()),
            "source": payload.source,
            "multi_source_enabled": multisource_enabled,
            "orchestrator_error_reason": "",
            "quality_gate": quality_gate,
        }
    )
    if debug_enabled():
        append_history(
            {
                "timestamp": now_iso(),
                "action": "workbench_generation_debug_trace",
                "trace_id": trace_id,
                "stage": "runtime.generate",
                "case_id": case_id,
                "page": execution_payload["page"],
            }
        )
    result = {
        "message": "case generated",
        "item": {
            "case_id": case_id,
            "project": payload.project,
            "path": str(case_path.resolve()),
            "yaml_content": final_text,
            "state": state_entry,
            "page": execution_payload["page"],
            "orchestrator_result": orchestrator_result,
            "orchestrator_error_reason": "",
            "quality_gate": quality_gate,
        },
    }
    log_debug_event(
        logger=_LOGGER,
        event="runtime.generate.output",
        trace_id=trace_id,
        payload=result,
        extra={"compare_with_event": "runtime.generate.orchestrator_output"},
    )
    return result
