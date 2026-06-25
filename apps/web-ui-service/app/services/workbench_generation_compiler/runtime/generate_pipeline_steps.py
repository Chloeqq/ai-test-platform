"""generate_pipeline 管线步骤与入口 —— 提取自 generate_pipeline.py。"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable, Protocol
import yaml
from sqlalchemy.exc import OperationalError

# SessionLocal imported from .generate_pipeline
from app.models.page_object import PageElement, PageObject
from app.repositories.page_object_repository import PageObjectRepository

from ..debug import debug_enabled, log_debug_event
from shared_backend.observability import summarize_http_context
from shared_backend.execution_compiler import ExecutionCompilerError, compile_execution_steps
from shared_backend.element_binding import build_element_alias_map
from shared_backend.intent_mapping import resolve_explicit_step
from shared_backend.schemas.contracts import normalize_test_point_plan_v1
from shared_backend.schemas.validator import ContractValidator
from shared_backend.type_utils import str_value as _normalized_text


# 从上游模块导入（无循环：File 1→File 2→File 3→File 4 单向依赖）
from .generate_pipeline import (
    SessionLocal,  # noqa: E402
    _normalized_text, _LOGGER, _YAML_PAGE_OBJECT_ROOT,
    _COMPILER_ERROR_CODES, _DSL_DATA_SOURCE_TYPES,
    _log_generation_failure, _redact_generation_payload,
    _normalized_key, _normalize_json_list, _is_qualified_formal_element,
    _element_display_name, _infer_element_aliases, _list_text,
    _extract_selected_intent_ids, _execution_intent_ids,
    _find_candidate_snapshot_by_intent, _candidate_steps,
    _normalize_candidate_snapshot, _point_type_from_intent_type,
    _candidate_identity, _direct_candidate_requirement_lines,
    _scope_points_to_selected_intents, _filter_requirement_spec_by_selected_intents,
    _is_precondition_point, _looks_like_password_toggle_element,
    _looks_like_generic_recorded_name,
)
from .generate_pipeline_format import (  # noqa: E402
    _product_description, _product_page_load_expected, _product_element_name,
    _product_locator, _product_element_meta, _trusted_page_url,
    _product_step_expected, _format_product_execution_steps,
    _append_login_success_assertion, _step_element_code,
    _normalize_dsl_data_sources, _enrich_dsl_v1_1_data_bindings,
    _normalize_top_level_assertion, _assertion_signature,
    _normalize_dsl_v1_1_assertions, _is_ai_automated_case,
    _validate_dsl_v1_1_minimum_contract, _enrich_product_case_yaml_v1_1,
)

def _svc():
    """惰性查找主模块。"""
    from . import generate_pipeline as _svc_mod
    return _svc_mod

from .generate_pipeline_orchestrate import (  # noqa: E402
    _format_product_case_yaml, _attach_point_expected_results,
    _build_direct_candidate_orchestrator_result,
    _extract_candidate_snapshots,
    _enrich_test_points_with_candidate_snapshots,
    _resolve_page_object_from_db,
    _load_cross_page_data_testid_element,
    _load_page_object_from_db,
    _resolve_page_object_from_assets,
)


def _handle_generation_exception(
    *,
    exc: Exception,
    trace_id: str,
    selected_intent_ids_list: list[str],
    mode: str,
    http_exception_cls: Any,
    unprocessable_entity_status: int,
    is_quality_gate_blocked: Any,
    payload: Any,
    normalized_page: str,
    multisource_enabled: bool,
    append_history: Any,
    now_iso: Any,
) -> None:
    """处理生成管线异常：分类记录日志并重新抛出对应的 HTTPException。"""
    if isinstance(exc, ExecutionCompilerError):
        _log_generation_failure(
            level=logging.WARNING, stage="execution_compiler", trace_id=trace_id,
            error=exc.to_detail(),
            payload={"selected_intent_ids": selected_intent_ids_list, "mode": mode},
        )
        raise http_exception_cls(status_code=unprocessable_entity_status, detail=exc.to_detail()) from exc
    if isinstance(exc, http_exception_cls):
        is_gate_blocked, blocked_gate = is_quality_gate_blocked(getattr(exc, "detail", ""))
        if is_gate_blocked and isinstance(blocked_gate, dict):
            _log_generation_failure(
                level=logging.WARNING, stage="quality_gate", trace_id=trace_id,
                error=getattr(exc, "detail", ""),
                payload={"selected_intent_ids": selected_intent_ids_list, "mode": mode},
                extra={"blocked_gate": blocked_gate},
            )
            append_history({
                "timestamp": now_iso(),
                "action": "generate_case_blocked_by_quality_gate",
                "case_id": payload.case_id.strip(), "page": normalized_page,
                "source": payload.source, "multi_source_enabled": multisource_enabled,
                "quality_gate": blocked_gate, "orchestrator_error_reason": getattr(exc, "detail", ""),
            })
            raise http_exception_cls(
                status_code=getattr(exc, "status_code", unprocessable_entity_status)
                if isinstance(getattr(exc, "status_code", None), int) else unprocessable_entity_status,
                detail={"code": "requirement_quality_gate_blocked",
                         "message": "requirement quality gate blocked orchestration",
                         "quality_gate": blocked_gate, "upstream_error": getattr(exc, "detail", "")},
            ) from exc
        upstream_status_code = getattr(exc, "status_code", None)
        upstream_detail = getattr(exc, "detail", "")
        detail_payload = upstream_detail if isinstance(upstream_detail, dict) else {}
        detail_code = str(detail_payload.get("code", "")).strip().lower()
        detail_reason_code = str(detail_payload.get("reason_code", "")).strip().lower()
        if (isinstance(upstream_status_code, int) and upstream_status_code == unprocessable_entity_status
                and detail_code in _COMPILER_ERROR_CODES):
            _log_generation_failure(
                level=logging.WARNING, stage="compiler_upstream", trace_id=trace_id,
                error=detail_payload or upstream_detail,
                payload={"selected_intent_ids": selected_intent_ids_list, "mode": mode,
                         "upstream_status_code": upstream_status_code},
            )
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail=detail_payload or {"code": "execution_compiler_failed",
                                            "message": "execution compiler failed",
                                            "reason": str(upstream_detail)[:500],
                                            "stage": "run_generate_pipeline"},
            ) from exc
        if (isinstance(upstream_status_code, int) and upstream_status_code == unprocessable_entity_status
                and (detail_code == "validation_error" or detail_reason_code == "test_design_invalid_output")):
            _log_generation_failure(
                level=logging.WARNING, stage="validation_upstream", trace_id=trace_id,
                error=detail_payload or upstream_detail,
                payload={"selected_intent_ids": selected_intent_ids_list, "mode": mode,
                         "upstream_status_code": upstream_status_code},
            )
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail=detail_payload or {"code": "validation_error", "message": str(upstream_detail)[:500]},
            ) from exc
        _log_generation_failure(
            level=logging.ERROR, stage="orchestrator_generate_failed", trace_id=trace_id,
            error=upstream_detail,
            payload={"selected_intent_ids": selected_intent_ids_list, "mode": mode,
                     "upstream_status_code": upstream_status_code, "detail_code": detail_code,
                     "detail_reason_code": detail_reason_code},
        )
        raise http_exception_cls(
            status_code=unprocessable_entity_status,
            detail={"code": "orchestrator_generate_failed", "message": "orchestrator generate failed",
                    "upstream_error": str(upstream_detail)[:500]},
        ) from exc
    upstream_error = str(exc)
    _log_generation_failure(
        level=logging.ERROR, stage="unexpected_exception", trace_id=trace_id,
        error=upstream_error[:500],
        payload={"selected_intent_ids": selected_intent_ids_list, "mode": mode, "is_http_exception": False},
    )
    raise http_exception_cls(
        status_code=unprocessable_entity_status,
        detail={"code": "orchestrator_generate_failed", "message": "orchestrator generate failed",
                "upstream_error": upstream_error[:500]},
    ) from exc


def _call_orchestrator_and_parse(
    *,
    payload: Any,
    normalized_page: str,
    effective_requirement: str,
    candidate_snapshots: list[dict[str, Any]],
    selected_candidate: dict[str, Any] | None,
    run_orchestrator_generate: RunOrchestratorGenerate,
    extract_quality_gate: ExtractQualityGate,
    http_exception_cls: Any,
    bad_gateway_status: int,
    unprocessable_entity_status: int,
    input_sources: list[dict[str, Any]],
    openapi_spec: dict[str, Any],
) -> dict[str, Any]:
    """Step 1: call orchestrator and parse response."""
    direct_orchestrator_result = _build_direct_candidate_orchestrator_result(
        payload=payload,
        normalized_page=normalized_page,
        effective_requirement=effective_requirement,
        candidate_snapshots=candidate_snapshots,
        selected_candidate=selected_candidate,
    )
    if direct_orchestrator_result is not None:
        orchestrator_result = direct_orchestrator_result
        _LOGGER.info(
            "pipeline using direct candidate path (no LLM call): page=%s candidates=%d",
            normalized_page, len(candidate_snapshots),
        )
    else:
        _LOGGER.info(
            "pipeline calling orchestrator LLM: page=%s requirement_chars=%d",
            normalized_page, len(effective_requirement),
        )
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
    return {
        "orchestrator_result": orchestrator_result,
        "case_yaml": case_yaml,
        "execution_payload": execution_payload,
        "resolved_page": resolved_page,
        "quality_gate": quality_gate,
        "test_points": test_points,
        "test_points_payload": test_points_payload,
    }


def _normalize_and_scope_test_points(
    *,
    payload: Any,
    resolved_page: str,
    test_points: list[dict[str, Any]],
    test_points_payload: dict[str, Any],
    orchestrator_result: dict[str, Any],
    selected_intent_ids: set[str],
    candidate_snapshots: list[dict[str, Any]],
    requirement_spec: dict[str, Any] | None,
    http_exception_cls: Any,
    unprocessable_entity_status: int,
) -> dict[str, Any]:
    """Step 2: normalize, scope test points to selected intents, and enrich with candidate snapshots."""
    try:
        plan_wrapper = {
            "version": "TestPointPlanV1",
            "project": str(getattr(payload, "project", "mall") or "mall"),
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

    requirement_spec = (
        orchestrator_result.get("requirement_spec")
        if isinstance(orchestrator_result.get("requirement_spec"), dict)
        else None
    )
    if selected_intent_ids:
        scoped_points, resolved_selected_intent_ids, missing_selected_intent_ids = _scope_points_to_selected_intents(
            test_points if isinstance(test_points, list) else [],
            selected_intent_ids,
        )
        if missing_selected_intent_ids:
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail={
                    "code": "execution_compiler_intent_coverage_failed",
                    "message": "selected intents are missing in normalized test points",
                    "reason": "selected_intent_ids were not fully materialized into test_points.points",
                    "stage": "run_generate_pipeline",
                    "selected_intent_ids": sorted(selected_intent_ids),
                    "resolved_intent_ids": sorted(resolved_selected_intent_ids),
                    "missing_intent_ids": missing_selected_intent_ids,
                },
            )
        test_points = scoped_points
        requirement_spec = _filter_requirement_spec_by_selected_intents(requirement_spec or {}, selected_intent_ids)
        orchestrator_result["requirement_spec"] = requirement_spec
        test_points_payload["points"] = test_points
    test_points = _enrich_test_points_with_candidate_snapshots(
        points=test_points if isinstance(test_points, list) else [],
        candidate_snapshots=candidate_snapshots,
    )
    test_points_payload["points"] = test_points
    return {
        "test_points": test_points,
        "test_points_payload": test_points_payload,
        "requirement_spec": requirement_spec,
        "orchestrator_result": orchestrator_result,
    }


def _validate_and_compile_steps(
    *,
    payload: Any,
    resolved_page: str,
    requirement_spec: dict[str, Any] | None,
    test_points: list[dict[str, Any]],
    page_object: dict[str, Any],
    http_exception_cls: Any,
    unprocessable_entity_status: int,
    selected_intent_ids: set[str],
    selected_intent_ids_list: list[str],
    execution_payload: dict[str, Any],
    test_points_payload: dict[str, Any],
    orchestrator_result: dict[str, Any],
) -> dict[str, Any]:
    """Step 3: resolve page object, validate contracts, and compile execution steps."""
    try:
        page_object = _svc().resolve_page_object(str(payload.project or ""), resolved_page)
    except ExecutionCompilerError as page_object_exc:
        raise http_exception_cls(
            status_code=unprocessable_entity_status,
            detail=page_object_exc.to_detail(),
        ) from page_object_exc
    try:
        trusted_page_url = _trusted_page_url(
            payload_page_url=getattr(payload, "page_url", ""),
            page_object=page_object,
        )
    except ExecutionCompilerError as page_url_exc:
        raise http_exception_cls(
            status_code=unprocessable_entity_status,
            detail=page_url_exc.to_detail(),
        ) from page_url_exc

    validator = ContractValidator()
    validation_result = validator.validate_full(
        requirement_spec if isinstance(requirement_spec, dict) else None,
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

    compiled_steps = _attach_point_expected_results(
        compile_execution_steps(test_points, page_object),
        test_points if isinstance(test_points, list) else [],
    )
    page_entry_url = trusted_page_url
    if page_entry_url:
        first_step = compiled_steps[0] if compiled_steps and isinstance(compiled_steps[0], dict) else {}
        first_action = _normalized_text(first_step.get("action")).lower()
        first_value = _normalized_text(first_step.get("value") or first_step.get("target"))
        if first_action != "goto" or first_value != page_entry_url:
            compiled_steps = [
                {
                    "action": "goto",
                    "target": "",
                    "selector": "",
                    "locator_type": "",
                    "role": "",
                    "intent_id": "__page_entry__",
                    "confidence": 1.0,
                    "value": page_entry_url,
                    "traceability": {
                        "source": "page_object.page_url",
                        "page": resolved_page,
                    },
                },
                *compiled_steps,
            ]
    if selected_intent_ids:
        compiled_intent_ids = {
            _normalized_text(step.get("intent_id"))
            for step in compiled_steps
            if isinstance(step, dict)
            and _normalized_text(step.get("intent_id"))
            and _normalized_text(step.get("intent_id")) != "__page_entry__"
            and _normalized_text(step.get("action")).lower() != "login"
            and _normalized_text(step.get("action")).lower() != "goto"
        }
        missing_intent_ids = sorted(selected_intent_ids - compiled_intent_ids)
        unexpected_intent_ids = sorted(compiled_intent_ids - selected_intent_ids)
        if missing_intent_ids or unexpected_intent_ids:
            raise http_exception_cls(
                status_code=unprocessable_entity_status,
                detail={
                    "code": "execution_compiler_intent_coverage_failed",
                    "message": "compiled steps do not strictly match selected intents",
                    "reason": "selected intent ids and compiled intent ids are inconsistent",
                    "stage": "run_generate_pipeline",
                    "selected_intent_ids": sorted(selected_intent_ids),
                    "compiled_intent_ids": sorted(compiled_intent_ids),
                    "missing_intent_ids": missing_intent_ids,
                    "unexpected_intent_ids": unexpected_intent_ids,
                },
            )
    execution_payload["steps"] = compiled_steps
    if selected_intent_ids_list:
        execution_payload["selected_intent_ids"] = selected_intent_ids_list
    orchestrator_result["execution_requested"] = True
    return {
        "page_object": page_object,
        "trusted_page_url": trusted_page_url,
        "compiled_steps": compiled_steps,
        "execution_payload": execution_payload,
        "orchestrator_result": orchestrator_result,
        "test_points_payload": test_points_payload,
    }


def _allocate_and_format_case_id(
    *,
    payload: Any,
    case_yaml: dict[str, Any],
    resolved_page: str,
    normalized_page: str,
    allocate_case_id: AllocateCaseId,
    ai_cases_root: Any,
    existing_case_ids: list[str] | None,
    page_object: dict[str, Any],
    execution_payload: dict[str, Any],
) -> dict[str, Any]:
    """Step 4: allocate case ID and set title/priority/tags/module/pages."""
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
    final_page_url = _normalized_text(page_object.get("page_url") or execution_payload.get("page_url"))
    if final_page_url:
        execution_payload["page_url"] = final_page_url
    return {
        "case_id": case_id,
        "case_yaml": case_yaml,
        "execution_payload": execution_payload,
        "final_page_url": final_page_url,
    }


def _evaluate_case_quality_gate(
    *,
    case_yaml: dict[str, Any],
    page_object: dict[str, Any],
    requirement_spec: dict[str, Any] | None,
    test_points: list[dict[str, Any]],
    project: str,
) -> tuple["ValidationReport", bool]:
    """调用 CaseQualityGate 对生成的用例执行质量门禁评估。

    返回 (ValidationReport, seed_data_available)。
    """
    from app.services.quality_gate.pipeline_gate import evaluate_case_quality

    return evaluate_case_quality(
        case_yaml=case_yaml,
        page_object=page_object,
        requirement_spec=requirement_spec,
        test_points=test_points,
        project=project,
    )


def _append_quality_gate_attribution(
    *,
    append_history: Any,
    now_iso: Any,
    case_id: str,
    quality_gate: dict[str, Any],
) -> None:
    """V3.0b: 将质量门结果映射为归因记录，写入 history。

    复用 failure-analysis-agent 的 category/source 分类体系，
    通过 rule_attribution_map 将触发规则映射到 failure_category/source。
    """
    rule_results = quality_gate.get("rule_results")
    if not isinstance(rule_results, list) or not rule_results:
        return

    from app.services.quality_gate.rule_attribution_map import resolve_attribution

    attribution = resolve_attribution(rule_results)
    triggered = attribution.get("triggered_rules", [])
    if not triggered:
        return  # 无规则触发 → 无需归因

    append_history({
        "timestamp": now_iso(),
        "action": "quality_gate_attribution",
        "case_id": case_id,
        "failure_category": attribution["failure_category"],
        "failure_source": attribution["failure_source"],
        "confidence": attribution["confidence"],
        "triggered_rules": triggered,
        "gate_decision": quality_gate.get("decision", ""),
        "gate_score": quality_gate.get("score", 0),
    })


def _persist_and_build_response(
    *,
    payload: Any,
    case_yaml: dict[str, Any],
    resolved_page: str,
    final_page_url: str,
    case_id: str,
    page_object: dict[str, Any],
    test_points: list[dict[str, Any]],
    candidate_snapshots: list[dict[str, Any]],
    requirement_spec: dict[str, Any] | None,
    selected_intent_ids_list: list[str],
    selected_intent_ids: set[str],
    effective_requirement: str,
    write_case_yaml: WriteCaseYaml,
    save_case_state: SaveCaseState,
    save_test_point_plan: Callable[..., Any] | None,
    now_iso: NowIso,
    append_history: AppendHistory,
    multisource_enabled: bool,
    quality_gate: dict[str, Any] | None,
    orchestrator_result: dict[str, Any],
    trace_id: str,
    http_exception_cls: Any,
    unprocessable_entity_status: int,
    mode: str,
    ai_cases_root: Any,
) -> dict[str, Any]:
    """Step 5: format product YAML, write files, save state, append history, build result."""
    _execution_payload = case_yaml.get("execution")
    if not isinstance(_execution_payload, dict):
        _execution_payload = {}
        case_yaml["execution"] = _execution_payload
    try:
        case_yaml = _format_product_case_yaml(
            case_yaml=case_yaml,
            payload=payload,
            page=_execution_payload["page"],
            page_url=final_page_url,
            page_object=page_object,
            test_points=test_points if isinstance(test_points, list) else [],
            candidate_snapshots=candidate_snapshots,
            requirement_spec=requirement_spec,
            selected_intent_ids=selected_intent_ids_list,
            effective_requirement=effective_requirement,
        )
    except ExecutionCompilerError as exc:
        _log_generation_failure(
            level=logging.WARNING,
            stage="dsl_v1_1_enrichment",
            trace_id=trace_id,
            error=exc.to_detail(),
            payload={
                "selected_intent_ids": selected_intent_ids_list,
                "mode": mode,
            },
        )
        raise http_exception_cls(
            status_code=unprocessable_entity_status,
            detail=exc.to_detail(),
        ) from exc
    execution_payload = case_yaml.get("execution") if isinstance(case_yaml.get("execution"), dict) else {}

    # ── Case Quality Gate ──────────────────────────────────────────────
    gate_report, seed_data_available = _evaluate_case_quality_gate(
        case_yaml=case_yaml,
        page_object=page_object,
        requirement_spec=requirement_spec,
        test_points=test_points,
        project=str(getattr(payload, "project", "") or ""),
    )
    quality_gate = {
        "decision": gate_report.decision.value,
        "score": gate_report.score.total_score,
        "grade": gate_report.score.grade,
        "summary": gate_report.summary,
        "seed_data_available": seed_data_available,
        "rule_results": [
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "passed": r.passed,
                "severity": r.severity.value if r.severity else "",
                "message": r.message,
            }
            for r in gate_report.results
        ],
    }
    _LOGGER.info(
        "quality_gate: case_id=%s decision=%s score=%s grade=%s seed_data=%s",
        case_id, gate_report.decision.value, gate_report.score.total_score, gate_report.score.grade,
        seed_data_available,
    )
    if gate_report.is_rejected:
        raise http_exception_cls(
            status_code=unprocessable_entity_status,
            detail={
                "code": "quality_gate_rejected",
                "message": f"用例质量门禁不通过: {gate_report.summary}",
                "quality_gate": quality_gate,
            },
        )
    # ───────────────────────────────────────────────────────────────────

    case_path = ai_cases_root / f"{case_id}.yaml"
    final_text = write_case_yaml(case_path, case_yaml)
    state_entry = save_case_state(payload.project, case_yaml, case_path)
    test_point_path = None
    if callable(save_test_point_plan):
        test_point_path = save_test_point_plan(
            project=payload.project,
            case_id=case_id,
            page=resolved_page,
            page_url=str(getattr(payload, "page_url", "") or ""),
            requirement=effective_requirement,
            plan={
                "version": "TestPointPlanV1",
                "project": payload.project,
                "case_id": case_id,
                "page": resolved_page,
                "source_type": "generate_chain",
                "requirement": [effective_requirement],
                "generated_at": now_iso(),
                "points": test_points if isinstance(test_points, list) else [],
                "coverage": {},
                "review_summary": {},
                "metadata": {
                    "origin": "generate_chain",
                    "selected_intent_ids": sorted(selected_intent_ids),
                    "selected_candidates": _redact_generation_payload(candidate_snapshots),
                },
            },
        )
    append_history(
        {
            "timestamp": now_iso(),
            "action": "generate_case",
            "case_id": case_id,
            "title": str(case_yaml.get("title", case_id)),
            "path": str(case_path.resolve()),
            "test_points_path": str(test_point_path.resolve()) if isinstance(test_point_path, Path) else "",
            "source": payload.source,
            "multi_source_enabled": multisource_enabled,
            "orchestrator_error_reason": "",
            "quality_gate": quality_gate,
        }
    )
    # V3.0b: 质量门归因记录 — 将规则结果映射到 failure analysis 分类体系
    _append_quality_gate_attribution(
        append_history=append_history,
        now_iso=now_iso,
        case_id=case_id,
        quality_gate=quality_gate,
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
            "test_points_path": str(test_point_path.resolve()) if isinstance(test_point_path, Path) else "",
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
        payload=_redact_generation_payload(result),
        extra={"compare_with_event": "runtime.generate.orchestrator_output"},
    )
    return result


def run_generate_pipeline(
    *, payload: Any, normalized_page: str, effective_requirement: str,
    multisource_enabled: bool, input_sources: list[dict[str, Any]], openapi_spec: dict[str, Any],
    run_orchestrator_generate: RunOrchestratorGenerate, extract_quality_gate: ExtractQualityGate,
    write_case_yaml: WriteCaseYaml, save_case_state: SaveCaseState,
    save_test_point_plan: Callable[..., Any] | None,
    append_history: AppendHistory, now_iso: NowIso, is_quality_gate_blocked: IsQualityGateBlocked,
    ai_cases_root: Any, http_exception_cls: Any, bad_gateway_status: int,
    unprocessable_entity_status: int, existing_case_ids: list[str] | None = None,
    selected_candidate: dict[str, Any] | None = None,
    allocate_case_id: AllocateCaseId, trace_id: str = "", mode: str = "generate",
) -> dict[str, Any]:
    log_debug_event(logger=_LOGGER, event="runtime.generate.input", trace_id=trace_id, payload={
        "project": str(getattr(payload, "project", "") or ""), "page": normalized_page,
        "requirement": effective_requirement, "multisource_enabled": multisource_enabled,
        "input_sources": _redact_generation_payload(input_sources), "openapi_spec": openapi_spec,
        "existing_case_ids": existing_case_ids or [],
        "selected_candidate": _redact_generation_payload(selected_candidate) if isinstance(selected_candidate, dict) else {},
    }, extra={"compare_with_event": "service.generate.input"})
    orchestrator_result: dict[str, Any] = {}
    case_yaml: dict[str, Any] = {}
    resolved_page = normalized_page
    quality_gate: dict[str, Any] | None = None
    requirement_spec: dict[str, Any] | None = None
    test_points: list[dict[str, Any]] = []
    page_object: dict[str, Any] = {}
    selected_intent_ids_list = _extract_selected_intent_ids(payload=payload, selected_candidate=selected_candidate)
    selected_intent_ids = set(selected_intent_ids_list)
    candidate_snapshots = _extract_candidate_snapshots(payload=payload, selected_candidate=selected_candidate)
    if candidate_snapshots and len(selected_intent_ids_list) != 1:
        raise http_exception_cls(status_code=unprocessable_entity_status, detail={
            "code": "dsl_v1_1_selected_intent_count_invalid",
            "message": "DSL V1.1 formal generation requires exactly one selected intent",
            "selected_intent_ids": selected_intent_ids_list,
            "stage": "run_generate_pipeline",
        })
    try:
        step1 = _call_orchestrator_and_parse(
            payload=payload, normalized_page=normalized_page,
            effective_requirement=effective_requirement,
            candidate_snapshots=candidate_snapshots, selected_candidate=selected_candidate,
            run_orchestrator_generate=run_orchestrator_generate,
            extract_quality_gate=extract_quality_gate,
            http_exception_cls=http_exception_cls, bad_gateway_status=bad_gateway_status,
            unprocessable_entity_status=unprocessable_entity_status,
            input_sources=input_sources, openapi_spec=openapi_spec,
        )
        step2 = _normalize_and_scope_test_points(
            payload=payload, resolved_page=step1["resolved_page"],
            test_points=step1["test_points"], test_points_payload=step1["test_points_payload"],
            orchestrator_result=step1["orchestrator_result"],
            selected_intent_ids=selected_intent_ids, candidate_snapshots=candidate_snapshots,
            requirement_spec=requirement_spec,
            http_exception_cls=http_exception_cls,
            unprocessable_entity_status=unprocessable_entity_status,
        )
        step3 = _validate_and_compile_steps(
            payload=payload, resolved_page=step1["resolved_page"],
            requirement_spec=step2["requirement_spec"], test_points=step2["test_points"],
            page_object=page_object, http_exception_cls=http_exception_cls,
            unprocessable_entity_status=unprocessable_entity_status,
            selected_intent_ids=selected_intent_ids,
            selected_intent_ids_list=selected_intent_ids_list,
            execution_payload=step1["execution_payload"],
            test_points_payload=step2["test_points_payload"],
            orchestrator_result=step2["orchestrator_result"],
        )
        review_summary = step3["test_points_payload"].get("review_summary")
        if isinstance(review_summary, dict):
            review_summary["intent_coverage_status"] = "covered"
            review_summary["status"] = "covered"
            review_summary["orphan_point_count"] = 0
            review_summary["orphan_step_count"] = 0
        log_debug_event(logger=_LOGGER, event="runtime.generate.orchestrator_output",
                        trace_id=trace_id,
                        payload=_redact_generation_payload(step3["orchestrator_result"]))
        orchestrator_result = step3["orchestrator_result"]
        case_yaml = step1["case_yaml"]
        resolved_page = step1["resolved_page"]
        page_object = step3["page_object"]
        test_points = step2["test_points"]
        quality_gate = step1["quality_gate"]
        requirement_spec = step2["requirement_spec"]
    except Exception as exc:
        _handle_generation_exception(
            exc=exc, trace_id=trace_id, selected_intent_ids_list=selected_intent_ids_list,
            mode=mode, http_exception_cls=http_exception_cls,
            unprocessable_entity_status=unprocessable_entity_status,
            is_quality_gate_blocked=is_quality_gate_blocked, payload=payload,
            normalized_page=normalized_page, multisource_enabled=multisource_enabled,
            append_history=append_history, now_iso=now_iso)

    step4 = _allocate_and_format_case_id(
        payload=payload, case_yaml=case_yaml, resolved_page=resolved_page,
        normalized_page=normalized_page, allocate_case_id=allocate_case_id,
        ai_cases_root=ai_cases_root, existing_case_ids=existing_case_ids,
        page_object=page_object, execution_payload=case_yaml.get("execution", {}),
    )
    return _persist_and_build_response(
        payload=payload, case_yaml=step4["case_yaml"],
        resolved_page=resolved_page, final_page_url=step4["final_page_url"],
        case_id=step4["case_id"], page_object=page_object, test_points=test_points,
        candidate_snapshots=candidate_snapshots, requirement_spec=requirement_spec,
        selected_intent_ids_list=selected_intent_ids_list,
        selected_intent_ids=selected_intent_ids, effective_requirement=effective_requirement,
        write_case_yaml=write_case_yaml, save_case_state=save_case_state,
        save_test_point_plan=save_test_point_plan, now_iso=now_iso,
        append_history=append_history, multisource_enabled=multisource_enabled,
        quality_gate=quality_gate, orchestrator_result=orchestrator_result,
        trace_id=trace_id, http_exception_cls=http_exception_cls,
        unprocessable_entity_status=unprocessable_entity_status,
        mode=mode, ai_cases_root=ai_cases_root,
    )
