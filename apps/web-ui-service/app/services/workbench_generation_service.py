"""High-level generation orchestration — coordinates requirement parsing, test-point
extraction, and case compilation.

Boundary note:
- This module is the *entry-point facade* called by ``workbench_generation_router``.
- ``workbench_generation_api/`` contains the runtime pipeline (``generate_pipeline.py``,
  ``context.py``) that this service delegates to for actual execution.
- ``workbench_generation_compiler/`` houses the compilation layer (IR, normalization,
  mapping) consumed by the pipeline.
"""
from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any, Callable

from shared_backend.case_ids import build_case_id, match_case_id, next_case_sequence, normalize_case_id
from app.services.workbench_generation_compiler.debug import (
    build_trace_id,
    debug_enabled,
    log_debug_event,
)
from app.services.workbench_generation_compiler.runtime.generate_pipeline import (
    run_generate_pipeline,
)
from app.services.workbench_generation_compiler.runtime.preview_pipeline import (
    run_preview_pipeline,
)
from app.services.workbench_generation_api import preview_store


BuildSystemRequirement = Callable[..., str]
RunOrchestratorParse = Callable[..., dict[str, Any]]
RunOrchestratorGenerate = Callable[..., dict[str, Any]]
RenderRequirementSpecMarkdown = Callable[[dict[str, Any]], str]
ExtractQualityGate = Callable[[dict[str, Any] | None], dict[str, Any] | None]
SafeCaseId = Callable[[str], str]
WriteCaseYaml = Callable[..., str]
SaveCaseState = Callable[[str, dict[str, Any], Any], dict[str, Any]]
AppendHistory = Callable[[dict[str, Any]], None]
InferTargets = Callable[[str], tuple[str, str]]
NowIso = Callable[[], str]
IsQualityGateBlocked = Callable[[Any], tuple[bool, dict[str, Any] | None]]
ExtractPageFromUrl = Callable[[str], tuple[str, str]]
ResolvePageUrl = Callable[[str, str], str]
ValidatePageSurfaceUrl = Callable[[str], Any]
ExtractPageSurface = Callable[[str], dict[str, Any] | Any]
NormalizePageSurface = Callable[..., dict[str, Any]]
BuildSurfaceElementCandidates = Callable[[str, dict[str, Any]], list[dict[str, Any]]]
SurfaceConfidenceSummary = Callable[[dict[str, Any]], dict[str, Any]]
EnhancePageObjectFromSurface = Callable[[str, dict[str, Any]], Any]
BuildRequirementSteps = Callable[[str, str, str, dict[str, Any]], tuple[list[dict[str, Any]], dict[str, Any]]]
BuildPageObjectQuality = Callable[[str, str, dict[str, Any], Any], dict[str, Any]]
NormalizePageObjectDraft = Callable[..., dict[str, Any]]
BuildFallbackCase = Callable[..., dict[str, Any]]
ReadCaseYaml = Callable[..., tuple[dict[str, Any], str]]
StepsToPoints = Callable[[str, str, list[dict[str, Any]]], dict[str, Any]]
InheritTestPointConfidenceFromSurface = Callable[..., dict[str, Any]]
AnnotateTestPointPlanReview = Callable[[dict[str, Any]], dict[str, Any]]
SaveTestPointPlan = Callable[..., Any]
BuildPageAnalysisContext = Callable[..., dict[str, Any]]
BuildItemReviewState = Callable[..., dict[str, Any]]
EvaluateRiskReport = Callable[..., dict[str, Any]]
BuildExecutionGate = Callable[..., dict[str, Any]]
NormalizeTestPointPlanPayload = Callable[[dict[str, Any]], dict[str, Any]]
AllocateCaseId = Callable[..., str]


_LOGGER = logging.getLogger(__name__)


def _allocate_case_id(
    *,
    requested_case_id: str,
    project: str,
    page: str,
    module: str,
    ai_cases_root: Path,
    existing_case_ids: list[str] | None = None,
) -> str:
    requested = normalize_case_id(requested_case_id, fallback="").strip() if str(requested_case_id).strip() else ""
    assets_root = ai_cases_root.resolve().parent
    all_existing_case_ids: list[str] = []
    seen_case_ids: set[str] = set()
    if assets_root.exists():
        for path in assets_root.rglob("*.yaml"):
            normalized_path_case_id = normalize_case_id(path.stem, fallback="").strip()
            if normalized_path_case_id and match_case_id(normalized_path_case_id) and normalized_path_case_id not in seen_case_ids:
                seen_case_ids.add(normalized_path_case_id)
                all_existing_case_ids.append(normalized_path_case_id)
    for item in existing_case_ids or []:
        value = normalize_case_id(str(item or "").strip(), fallback="").strip()
        if value and match_case_id(value) and value not in seen_case_ids:
            seen_case_ids.add(value)
            all_existing_case_ids.append(value)
    if requested and match_case_id(requested) and requested not in seen_case_ids:
        return requested
    sequence = next_case_sequence(
        existing_case_ids=all_existing_case_ids,
        page=page,
        module=module,
        project=project,
        case_type="FN",
        source="AI",
    )
    return build_case_id(
        project=project,
        page=page,
        module=module,
        case_type="FN",
        source="AI",
        sequence=sequence,
    )


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strip_list_prefix(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^\s*(?:[-*•·]+\s*|\d+\s*[.)、]\s*)", "", cleaned)
    return cleaned.strip()


def _normalize_generated_case_title(value: str) -> str:
    text = _strip_list_prefix(str(value or ""))
    if not text:
        return ""
    text = text.strip("`'\" ")
    text = re.sub(r"\s+", " ", text).strip()
    for prefix in ["测试意图：", "测试意图:", "需求：", "需求:", "功能描述：", "功能描述:"]:
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
            break
    if re.match(r"^【[^】]{1,24}】$", text):
        return ""
    if re.match(r"^(模块|页面|功能|功能描述|测试点|场景|需求)\s*[:：]?$", text):
        return ""
    if text.endswith(("：", ":")) and len(text) <= 18:
        return ""
    if len(text) < 4:
        return ""
    return text[:120]


def _ensure_execution_steps(
    *,
    case_yaml: dict[str, Any],
    page: str,
    title: str,
    infer_targets: InferTargets,
) -> None:
    _ = page, title, infer_targets
    execution_payload = case_yaml.get("execution")
    if not isinstance(execution_payload, dict):
        execution_payload = {}
        case_yaml["execution"] = execution_payload
    raw_steps = execution_payload.get("steps")
    normalized_steps: list[dict[str, Any]] = []
    if isinstance(raw_steps, list) and raw_steps:
        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                continue
            normalized_steps.append(raw_step)
    if not normalized_steps:
        raise ValueError("orchestrator returned empty execution.steps in pure-ai mode")
    execution_payload["steps"] = normalized_steps

def extract_quality_gate(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    direct = payload.get("quality_gate")
    if isinstance(direct, dict):
        return direct
    details = payload.get("details")
    if isinstance(details, dict):
        nested = details.get("quality_gate")
        if isinstance(nested, dict):
            return nested
    error = payload.get("error")
    if isinstance(error, dict):
        nested = extract_quality_gate(error)
        if isinstance(nested, dict):
            return nested
    return None


def is_quality_gate_blocked(payload: Any) -> tuple[bool, dict[str, Any] | None]:
    gate = extract_quality_gate(payload)
    if not isinstance(gate, dict):
        return False, None
    decision = str(gate.get("decision", "")).strip().lower()
    if decision == "block":
        return True, gate
    blockers = gate.get("blockers")
    if isinstance(blockers, list) and len(blockers) > 0:
        return True, gate
    return False, gate


def build_requirement_spec_for_risk(
    *,
    page: str,
    requirement: str,
    quality_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "page": page,
        "priority": "P1",
        "requirement": [requirement] if requirement else [],
        "quality_gate": quality_gate if isinstance(quality_gate, dict) else {},
    }


def build_system_requirement(
    *,
    page: str,
    page_url: str = "",
    has_multisource_inputs: bool = False,
    normalize_page_slug_fn: Any = None,
    page_friendly_name: dict[str, str] | None = None,
) -> str:
    normalize_page_slug = normalize_page_slug_fn if callable(normalize_page_slug_fn) else (lambda value: str(value or "").strip())
    normalized_page = normalize_page_slug(page) if str(page).strip() else ""
    if has_multisource_inputs:
        return "多输入源需求驱动的页面核心流程验证"
    friendly_names = page_friendly_name if isinstance(page_friendly_name, dict) else {}
    page_label = friendly_names.get(normalized_page, normalized_page or "目标页面")
    route_label = str(page_url or "").strip()
    if route_label:
        return f"自动生成的页面测试目标：验证 {page_label} 页面可访问、关键区域可见、核心基础交互可执行。目标 URL：{route_label}"
    return f"自动生成的页面测试目标：验证 {page_label} 页面可访问、关键区域可见、核心基础交互可执行。"


def render_requirement_spec_markdown(requirement_spec: dict[str, Any]) -> str:
    spec = requirement_spec if isinstance(requirement_spec, dict) else {}
    page = str(spec.get("page", "")).strip() or "-"
    priority = str(spec.get("priority", "")).strip() or "P1"
    parse_confidence = spec.get("parse_confidence", 0)
    test_intents: list[Any] = _list_value(spec.get("test_intents"))
    ambiguities: list[Any] = _list_value(spec.get("ambiguities"))
    business_rules: list[Any] = _list_value(spec.get("business_rules"))
    quality_gate = _dict_value(spec.get("quality_gate"))
    lines = [
        "# 需求测试点分析",
        "",
        f"- 页面: `{page}`",
        f"- 优先级: `{priority}`",
        f"- 解析置信度: `{parse_confidence}`",
        f"- 测试点数量: `{len(test_intents)}`",
        f"- 规则数量: `{len(business_rules)}`",
        f"- 消歧数量: `{len(ambiguities)}`",
    ]
    if quality_gate:
        blockers = _list_value(quality_gate.get("blockers"))
        lines.extend(
            [
                "",
                "## 质量门禁",
                f"- 决策: `{str(quality_gate.get('decision', '')).strip() or '-'}`",
                f"- 阶段: `{str(quality_gate.get('stage', '')).strip() or '-'}`",
                f"- 阻断项数量: `{len(blockers)}`",
            ]
        )
    if test_intents:
        lines.extend(["", "## 测试点"])
        for index, intent in enumerate(test_intents[:20], start=1):
            if not isinstance(intent, dict):
                continue
            lines.append(
                f"{index}. [{str(intent.get('priority', 'P1')).strip() or 'P1'}/{str(intent.get('intent_type', 'functional')).strip() or 'functional'}] {str(intent.get('title', '')).strip() or f'intent-{index:02d}'}"
            )
    return "\n".join(lines).strip() + "\n"


def build_execution_plan_for_risk(
    *,
    page: str,
    steps: list[dict[str, Any]],
    test_points: dict[str, Any],
    coverage: dict[str, Any],
    page_surface_summary: dict[str, Any],
    page_semantic_summary: dict[str, Any],
    page_object_summary: dict[str, Any],
    review_state: dict[str, Any],
    final_status: str,
    build_execution_gate_fn: BuildExecutionGate,
) -> dict[str, Any]:
    point_summary = (test_points or {}).get("review_summary", {}) if isinstance(test_points, dict) else {}
    gate_check = build_execution_gate_fn(
        page=page,
        final_status=final_status,
        coverage=coverage if isinstance(coverage, dict) else {},
        page_surface_summary=page_surface_summary if isinstance(page_surface_summary, dict) else {},
        page_semantic_summary=page_semantic_summary if isinstance(page_semantic_summary, dict) else {},
        page_object_summary=page_object_summary if isinstance(page_object_summary, dict) else {},
        test_points=test_points if isinstance(test_points, dict) else {},
        review_state=review_state if isinstance(review_state, dict) else {},
    )
    return {
        "version": "ExecutionPlanV1",
        "page": page,
        "retry_policy": {"max_retries": 0},
        "gate_check": gate_check,
        "metadata": {
            "step_count": len(steps),
            "pending_test_point_reviews": int(point_summary.get("pending_review_count", 0) or 0),
            "skip_suggestions": int(point_summary.get("skip_suggestion_count", 0) or 0),
            "dependency_review_points": int(point_summary.get("dependency_review_count", 0) or 0),
            "missing_dependency_points": int(point_summary.get("missing_dependency_point_count", 0) or 0),
            "gate_decision": str(gate_check.get("decision", "")).strip() or "allow",
        },
    }


def has_multisource_inputs(
    *,
    input_sources: list[dict[str, Any]],
    openapi_spec: dict[str, Any],
    prd_text: str,
    prd_url: str,
    user_story: str,
    git_diff: str,
    git_diff_path: str,
    openapi_url: str,
    defect_ticket: str,
    runtime_logs: str,
) -> bool:
    return any(
        [
            bool(input_sources),
            bool(openapi_spec),
            bool(str(prd_text).strip()),
            bool(str(prd_url).strip()),
            bool(str(user_story).strip()),
            bool(str(git_diff).strip()),
            bool(str(git_diff_path).strip()),
            bool(str(openapi_url).strip()),
            bool(str(defect_ticket).strip()),
            bool(str(runtime_logs).strip()),
        ]
    )


def resolve_effective_requirement(
    *,
    requirement_text: str,
    normalized_page: str,
    multisource_enabled: bool,
    build_system_requirement: BuildSystemRequirement,
) -> str:
    return str(requirement_text).strip() or build_system_requirement(
        page=normalized_page,
        has_multisource_inputs=multisource_enabled,
    )


def build_preview_response(
    *,
    effective_requirement: str,
    normalized_page: str,
    source: str,
    input_sources: list[dict[str, Any]],
    openapi_spec: dict[str, Any],
    prd_text: str,
    prd_url: str,
    user_story: str,
    git_diff: str,
    git_diff_path: str,
    openapi_url: str,
    defect_ticket: str,
    runtime_logs: str,
    run_orchestrator_parse: RunOrchestratorParse,
    render_requirement_spec_markdown: RenderRequirementSpecMarkdown,
    extract_quality_gate: ExtractQualityGate,
    project: str = "mall",
) -> dict[str, Any]:
    trace_id = build_trace_id(
        stage="service.preview",
        payload={
            "page": normalized_page,
            "source": source,
            "requirement": effective_requirement,
            "input_sources_count": len(input_sources),
        },
    )
    log_debug_event(
        logger=_LOGGER,
        event="service.preview.input",
        trace_id=trace_id,
        payload={
            "effective_requirement": effective_requirement,
            "normalized_page": normalized_page,
            "source": source,
            "input_sources": input_sources,
            "openapi_spec": openapi_spec,
            "prd_text": prd_text,
            "prd_url": prd_url,
            "user_story": user_story,
            "git_diff": git_diff,
            "git_diff_path": git_diff_path,
            "openapi_url": openapi_url,
            "defect_ticket": defect_ticket,
            "runtime_logs": runtime_logs,
        },
    )
    full_result = run_preview_pipeline(
        effective_requirement=effective_requirement,
        normalized_page=normalized_page,
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
        run_orchestrator_parse=run_orchestrator_parse,
        render_requirement_spec_markdown=render_requirement_spec_markdown,
        extract_quality_gate=extract_quality_gate,
        list_value=_list_value,
        dict_value=_dict_value,
        trace_id=trace_id,
    )
    snapshot = preview_store.save_preview_snapshot(
        project=project,
        page=normalized_page,
        source=source,
        effective_requirement=effective_requirement,
        preview_payload=full_result,
        trace_id=trace_id,
    )
    result = preview_store.build_public_preview_response(snapshot)
    log_debug_event(
        logger=_LOGGER,
        event="service.preview.output",
        trace_id=trace_id,
        payload=result,
        extra={"compare_with_event": "runtime.preview.output"},
    )
    return result


def build_generated_case_payload(
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
    save_test_point_plan: SaveTestPointPlan | None = None,
    append_history: AppendHistory,
    now_iso: NowIso,
    is_quality_gate_blocked: IsQualityGateBlocked,
    ai_cases_root: Any,
    utc: Any,
    datetime_module: Any,
    http_exception_cls: Any,
    bad_gateway_status: int,
    unprocessable_entity_status: int,
    allocate_case_id: AllocateCaseId,
    existing_case_ids: list[str] | None = None,
    selected_candidate: dict[str, Any] | None = None,
    mode: str = "generate",
) -> dict[str, Any]:
    trace_id = build_trace_id(
        stage="service.generate",
        payload={
            "project": str(getattr(payload, "project", "") or ""),
            "page": normalized_page,
            "requirement": effective_requirement,
            "input_sources_count": len(input_sources),
            "selected_candidate": selected_candidate if isinstance(selected_candidate, dict) else {},
        },
    )
    log_debug_event(
        logger=_LOGGER,
        event="service.generate.input",
        trace_id=trace_id,
        payload={
            "payload": payload,
            "normalized_page": normalized_page,
            "effective_requirement": effective_requirement,
            "multisource_enabled": multisource_enabled,
            "input_sources": input_sources,
            "openapi_spec": openapi_spec,
            "existing_case_ids": existing_case_ids or [],
            "selected_candidate": selected_candidate if isinstance(selected_candidate, dict) else {},
        },
    )
    result = run_generate_pipeline(
        payload=payload,
        normalized_page=normalized_page,
        effective_requirement=effective_requirement,
        multisource_enabled=multisource_enabled,
        input_sources=input_sources,
        openapi_spec=openapi_spec,
        run_orchestrator_generate=run_orchestrator_generate,
        extract_quality_gate=extract_quality_gate,
        write_case_yaml=write_case_yaml,
        save_case_state=save_case_state,
        save_test_point_plan=save_test_point_plan,
        append_history=append_history,
        now_iso=now_iso,
        is_quality_gate_blocked=is_quality_gate_blocked,
        ai_cases_root=ai_cases_root,
        utc=utc,
        datetime_module=datetime_module,
        http_exception_cls=http_exception_cls,
        bad_gateway_status=bad_gateway_status,
        unprocessable_entity_status=unprocessable_entity_status,
        existing_case_ids=existing_case_ids,
        selected_candidate=selected_candidate,
        allocate_case_id=allocate_case_id,
        safe_case_id=safe_case_id,
        infer_targets=infer_targets,
        trace_id=trace_id,
        mode=mode,
    )
    log_debug_event(
        logger=_LOGGER,
        event="service.generate.output",
        trace_id=trace_id,
        payload=result,
        extra={
            "compare_with_event": "runtime.generate.output",
            "debug_history_enabled": debug_enabled(),
        },
    )
    return result


def build_auto_run_summary(*, project: str, raw_urls: list[str], items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items)
    passed = sum(1 for item in items if str(item.get("status", "")).lower() == "passed")
    failed = sum(1 for item in items if str(item.get("status", "")).lower() == "failed")
    coverage_gap = sum(1 for item in items if str(item.get("status", "")).lower() == "coverage_gap")
    generate_failed = sum(1 for item in items if str(item.get("status", "")).lower() == "generate_failed")
    pending_reviews = sum(
        int((item.get("review_state") or {}).get("pending_sections", 0) or 0)
        for item in items
        if isinstance(item.get("review_state"), dict)
    )
    confirmed_reviews = sum(
        int((item.get("review_state") or {}).get("confirmed_sections", 0) or 0)
        for item in items
        if isinstance(item.get("review_state"), dict)
    )
    gate_blocked = sum(
        1
        for item in items
        if str((item.get("execution_gate") or {}).get("decision", "")).strip().lower() == "block"
    )
    gate_manual_review = sum(
        1
        for item in items
        if str((item.get("execution_gate") or {}).get("decision", "")).strip().lower() == "manual_review"
    )
    gate_allow = sum(
        1
        for item in items
        if str((item.get("execution_gate") or {}).get("decision", "")).strip().lower() == "allow"
    )
    return {
        "project": project,
        "total": total,
        "passed": passed,
        "failed": failed,
        "coverage_gap": coverage_gap,
        "generate_failed": generate_failed,
        "pending_reviews": pending_reviews,
        "confirmed_reviews": confirmed_reviews,
        "gate_blocked": gate_blocked,
        "gate_manual_review": gate_manual_review,
        "gate_allow": gate_allow,
        "requested_urls": raw_urls,
    }


def prepare_auto_run_page_context(
    *,
    raw_url: str,
    requirement_text: str,
    multisource_enabled: bool,
    build_system_requirement: BuildSystemRequirement,
    extract_page_from_url: ExtractPageFromUrl,
    resolve_page_url: ResolvePageUrl,
    validate_page_surface_url: ValidatePageSurfaceUrl,
    extract_page_surface: ExtractPageSurface,
    normalize_page_surface: NormalizePageSurface,
    build_surface_element_candidates: BuildSurfaceElementCandidates,
    surface_confidence_summary: SurfaceConfidenceSummary,
    enhance_page_object_from_surface: EnhancePageObjectFromSurface,
    build_requirement_steps: BuildRequirementSteps,
    build_page_object_quality: BuildPageObjectQuality,
    normalize_page_object_draft: NormalizePageObjectDraft,
) -> dict[str, Any]:
    page_url, page = extract_page_from_url(raw_url)
    resolved_page_url = resolve_page_url(page_url, page)
    effective_requirement = str(requirement_text).strip() or build_system_requirement(
        page=page,
        page_url=resolved_page_url,
        has_multisource_inputs=multisource_enabled,
    )
    validate_page_surface_url(resolved_page_url)
    surface = extract_page_surface(resolved_page_url)
    if not isinstance(surface, dict):
        surface = {}
    surface = normalize_page_surface(surface, page=page, requested_url=resolved_page_url)
    if not isinstance(surface.get("element_candidates"), list):
        surface["element_candidates"] = build_surface_element_candidates(page, surface)
    if not isinstance(surface.get("confidence_summary"), dict):
        surface["confidence_summary"] = surface_confidence_summary(surface)
    if "confidence" not in surface:
        surface["confidence"] = surface["confidence_summary"].get("confidence", 0.0)
    if "requires_review" not in surface:
        surface["requires_review"] = surface["confidence_summary"].get("requires_review", False)
    page_object_path = enhance_page_object_from_surface(page, surface)
    steps, coverage = build_requirement_steps(effective_requirement, page, resolved_page_url, surface)
    page_object_quality = build_page_object_quality(page, effective_requirement, surface, page_object_path)
    page_object_quality = normalize_page_object_draft(
        page_object_quality,
        page=page,
        path=str(page_object_path.resolve()),
    )
    page_object_summary = page_object_quality.get("summary", {}) if isinstance(page_object_quality, dict) else {}
    page_object_coverage = page_object_quality.get("coverage", {}) if isinstance(page_object_quality, dict) else {}
    if isinstance(page_object_coverage, dict) and page_object_coverage:
        coverage = {**coverage, "page_object": page_object_coverage}
    return {
        "page_url": page_url,
        "page": page,
        "resolved_page_url": resolved_page_url,
        "effective_requirement": effective_requirement,
        "surface": surface,
        "page_object_path": page_object_path,
        "steps": steps,
        "coverage": coverage,
        "page_object_quality": page_object_quality,
        "page_object_summary": page_object_summary,
    }


def build_auto_run_generate_failed_item(
    *,
    page_url: str,
    resolved_page_url: str,
    page: str,
    surface: dict[str, Any],
    page_object_path: Any,
    page_object_quality: dict[str, Any],
    page_object_summary: dict[str, Any],
    coverage: dict[str, Any],
    quality_gate: dict[str, Any],
    runner_script: str,
) -> dict[str, Any]:
    return {
        "page_url": page_url,
        "resolved_page_url": resolved_page_url,
        "page": page,
        "page_surface": surface,
        "page_surface_summary": surface.get("confidence_summary", {}),
        "case_id": "",
        "case_path": "",
        "page_object_path": str(page_object_path.resolve()),
        "page_object": page_object_quality,
        "page_object_summary": page_object_summary,
        "test_points_path": "",
        "test_points": {},
        "run_id": "",
        "status": "generate_failed",
        "coverage": coverage,
        "timed_out": False,
        "quality_gate": quality_gate,
        "error": {
            "code": "requirement_quality_gate_blocked",
            "message": "requirement quality gate blocked orchestration",
        },
        "runner": {
            "script": runner_script,
            "mode": "yaml-driven",
        },
    }


def persist_auto_run_fallback_case(
    *,
    page: str,
    effective_requirement: str,
    resolved_page_url: str,
    steps: list[dict[str, Any]],
    project: str,
    page_object_path: Any,
    surface: dict[str, Any],
    coverage: dict[str, Any],
    fallback_reason: Any,
    build_fallback_case: BuildFallbackCase,
    safe_case_id: SafeCaseId,
    write_case_yaml: WriteCaseYaml,
    read_case_yaml: ReadCaseYaml,
    save_case_state: SaveCaseState,
    steps_to_points: StepsToPoints,
    inherit_test_point_confidence_from_surface: InheritTestPointConfidenceFromSurface,
    annotate_test_point_plan_review: AnnotateTestPointPlanReview,
    save_test_point_plan: SaveTestPointPlan,
    append_history: AppendHistory,
    now_iso: NowIso,
    ai_cases_root: Any,
    allocate_case_id: AllocateCaseId,
) -> dict[str, Any]:
    fallback_case = build_fallback_case(
        page=page,
        requirement=effective_requirement,
        resolved_page_url=resolved_page_url,
        steps=steps,
    )
    case_id = allocate_case_id(
        requested_case_id=str(fallback_case.get("id", "")).strip(),
        project=project,
        page=page,
        module=str(fallback_case.get("module", "")).strip() or page,
        ai_cases_root=ai_cases_root,
    )
    fallback_case["id"] = case_id
    case_path = (ai_cases_root / f"{case_id}.yaml").resolve()
    write_case_yaml(case_path, fallback_case)
    case_yaml, _ = read_case_yaml(case_path)
    save_case_state(project, case_yaml, case_path)
    test_points = steps_to_points(page, effective_requirement, steps)
    test_points["source_type"] = "fallback"
    test_points["coverage"] = coverage
    test_points["fallback_reason"] = fallback_reason
    test_points = inherit_test_point_confidence_from_surface(plan=test_points, surface=surface)
    test_points = annotate_test_point_plan_review(test_points)
    test_point_path = save_test_point_plan(
        project=project,
        case_id=case_id,
        page=page,
        page_url=resolved_page_url,
        requirement=effective_requirement,
        plan=test_points,
        case_path=case_path,
        page_object_path=page_object_path,
    )
    append_history(
        {
            "timestamp": now_iso(),
            "action": "auto_generate_case_fallback",
            "case_id": case_id,
            "page": page,
            "page_url": resolved_page_url,
            "path": str(case_path),
            "fallback_reason": fallback_reason,
        }
    )
    return {
        "case_id": case_id,
        "case_path": case_path,
        "case_yaml": case_yaml,
        "test_points": test_points,
        "test_point_path": test_point_path,
    }


def build_auto_run_governance_context(
    *,
    project: str,
    run_id: str,
    case_id: str,
    page: str,
    page_url: str,
    effective_requirement: str,
    quality_gate: dict[str, Any],
    steps: list[dict[str, Any]],
    final_status: str,
    surface: dict[str, Any],
    page_object_quality: dict[str, Any],
    page_object_summary: dict[str, Any],
    test_points: dict[str, Any],
    coverage: dict[str, Any],
    requirement_spec: dict[str, Any],
    build_page_analysis_context: BuildPageAnalysisContext,
    build_item_review_state: BuildItemReviewState,
    evaluate_risk_report: EvaluateRiskReport,
    build_execution_gate: BuildExecutionGate,
) -> dict[str, Any]:
    analysis_context = build_page_analysis_context(
        page=page,
        project=project,
        case_id=case_id,
        page_url=page_url,
        page_surface=surface,
        page_object=page_object_quality,
        test_points=test_points,
    )
    page_surface_summary = surface.get("confidence_summary", {}) if isinstance(surface.get("confidence_summary"), dict) else {}
    pre_review_state = build_item_review_state(
        project=project,
        run_id=run_id,
        page=page,
        page_surface_summary=page_surface_summary,
        test_points=test_points,
        page_surface=surface,
        page_object=page_object_quality,
    )
    risk_report = evaluate_risk_report(
        page=page,
        requirement=effective_requirement,
        quality_gate=quality_gate,
        steps=steps,
        final_status=final_status,
        run_id=run_id,
        project=project,
        page_surface_summary=page_surface_summary,
        page_object_summary=page_object_summary,
        test_points=test_points,
        review_state=pre_review_state,
        page_surface=surface,
        page_object=page_object_quality,
        requirement_spec=requirement_spec,
    )
    review_state = build_item_review_state(
        project=project,
        run_id=run_id,
        page=page,
        page_surface_summary=page_surface_summary,
        test_points=test_points,
        page_surface=surface,
        page_object=page_object_quality,
        risk_report=risk_report,
    )
    execution_gate = build_execution_gate(
        page=page,
        final_status=final_status,
        coverage=coverage if isinstance(coverage, dict) else {},
        page_surface_summary=page_surface_summary,
        page_semantic_summary=analysis_context.get("page_semantic_summary", {})
        if isinstance(analysis_context.get("page_semantic_summary"), dict)
        else {},
        page_object_summary=page_object_summary if isinstance(page_object_summary, dict) else {},
        test_points=test_points if isinstance(test_points, dict) else {},
        review_state=review_state if isinstance(review_state, dict) else {},
        risk_report=risk_report if isinstance(risk_report, dict) else {},
    )
    sync_payload = {
        "page": page,
        "review_state": review_state,
        "risk_report": risk_report,
        "execution_gate": execution_gate,
        "page_semantic": analysis_context.get("page_semantic", {}) if isinstance(analysis_context.get("page_semantic"), dict) else {},
        "page_semantic_summary": analysis_context.get("page_semantic_summary", {})
        if isinstance(analysis_context.get("page_semantic_summary"), dict)
        else {},
        "page_object_summary": page_object_summary,
        "coverage": coverage,
    }
    return {
        "analysis_context": analysis_context,
        "risk_report": risk_report,
        "review_state": review_state,
        "execution_gate": execution_gate,
        "sync_payload": sync_payload,
    }


def persist_auto_run_generated_case(
    *,
    orchestrator_result: dict[str, Any],
    project: str,
    page: str,
    resolved_page_url: str,
    effective_requirement: str,
    steps: list[dict[str, Any]],
    coverage: dict[str, Any],
    surface: dict[str, Any],
    page_object_path: Any,
    repo_root: Any,
    ai_cases_root: Any,
    path_cls: Any,
    safe_case_id: SafeCaseId,
    datetime_module: Any,
    utc: Any,
    http_exception_cls: Any,
    bad_gateway_status: int,
    write_case_yaml: WriteCaseYaml,
    read_case_yaml: ReadCaseYaml,
    save_case_state: SaveCaseState,
    normalize_test_point_plan_payload: NormalizeTestPointPlanPayload,
    steps_to_points: StepsToPoints,
    inherit_test_point_confidence_from_surface: InheritTestPointConfidenceFromSurface,
    annotate_test_point_plan_review: AnnotateTestPointPlanReview,
    save_test_point_plan: SaveTestPointPlan,
    append_history: AppendHistory,
    now_iso: NowIso,
    allocate_case_id: AllocateCaseId,
) -> dict[str, Any]:
    generated_case = orchestrator_result.get("case") or {}
    if not isinstance(generated_case, dict):
        raise http_exception_cls(
            status_code=bad_gateway_status,
            detail="orchestrator returned invalid case payload",
        )
    case_id = allocate_case_id(
        requested_case_id=str(generated_case.get("id", "")).strip(),
        project=project,
        page=page,
        module=str(generated_case.get("module", "")).strip() or page,
        ai_cases_root=ai_cases_root,
    )
    generated_case["id"] = case_id
    execution_payload = generated_case.get("execution")
    if not isinstance(execution_payload, dict):
        execution_payload = {}
    execution_payload["runner"] = "playwright"
    execution_payload["page"] = page
    execution_payload.setdefault("variables", {})
    execution_payload["steps"] = steps
    generated_case["execution"] = execution_payload
    generated_case["requirement"] = [effective_requirement, f"url: {resolved_page_url}"]

    case_path_raw = str(orchestrator_result.get("case_path", "")).strip()
    if case_path_raw:
        candidate = path_cls(case_path_raw).expanduser()
        case_path = candidate if candidate.is_absolute() else (repo_root / candidate)
    else:
        case_path = ai_cases_root / f"{case_id}.yaml"
    case_path = case_path.resolve()

    write_case_yaml(case_path, generated_case)
    case_yaml, _ = read_case_yaml(case_path)
    state_entry = save_case_state(project, case_yaml, case_path)

    plan_payload = orchestrator_result.get("test_points") or {}
    if not isinstance(plan_payload, dict):
        plan_payload = {}
    if isinstance(plan_payload.get("points"), list) and plan_payload.get("points"):
        test_points = normalize_test_point_plan_payload(
            {
                **plan_payload,
                "project": project,
                "case_id": case_id,
                "page": page,
                "page_url": resolved_page_url,
                "source_type": str(plan_payload.get("source_type", "requirement_intents")).strip()
                or "requirement_intents",
                "coverage": coverage,
                "metadata": {
                    **(plan_payload.get("metadata", {}) if isinstance(plan_payload.get("metadata"), dict) else {}),
                    "upstream": "orchestrator",
                },
            }
        )
    else:
        test_points = steps_to_points(page, effective_requirement, steps)
        test_points["coverage"] = coverage
        if plan_payload:
            test_points["upstream_plan"] = plan_payload
    test_points = inherit_test_point_confidence_from_surface(plan=test_points, surface=surface)
    test_points = annotate_test_point_plan_review(test_points)
    test_point_path = save_test_point_plan(
        project=project,
        case_id=case_id,
        page=page,
        page_url=resolved_page_url,
        requirement=effective_requirement,
        plan=test_points,
        case_path=case_path,
        page_object_path=page_object_path,
    )
    append_history(
        {
            "timestamp": now_iso(),
            "action": "auto_generate_case",
            "case_id": case_id,
            "page": page,
            "page_url": resolved_page_url,
            "path": str(case_path),
            "test_points_path": str(test_point_path),
            "state_version": state_entry.get("version", 1),
        }
    )
    return {
        "case_id": case_id,
        "case_path": case_path,
        "case_yaml": case_yaml,
        "state_entry": state_entry,
        "test_points": test_points,
        "test_point_path": test_point_path,
    }


def build_auto_run_item(
    *,
    page_url: str,
    resolved_page_url: str,
    page: str,
    surface: dict[str, Any],
    analysis_context: dict[str, Any],
    case_id: str,
    case_path: Any,
    page_object_path: Any,
    page_object_quality: dict[str, Any],
    page_object_summary: dict[str, Any],
    test_point_path: Any,
    test_points: dict[str, Any],
    run_id: str,
    final_status: str,
    coverage: dict[str, Any],
    timed_out: bool,
    risk_report: dict[str, Any],
    execution_gate: dict[str, Any],
    review_state: dict[str, Any],
    runner_script: str,
) -> dict[str, Any]:
    return {
        "page_url": page_url,
        "resolved_page_url": resolved_page_url,
        "page": page,
        "page_surface": surface,
        "page_surface_summary": surface.get("confidence_summary", {}),
        "page_semantic": analysis_context.get("page_semantic", {})
        if isinstance(analysis_context.get("page_semantic"), dict)
        else {},
        "page_semantic_summary": analysis_context.get("page_semantic_summary", {})
        if isinstance(analysis_context.get("page_semantic_summary"), dict)
        else {},
        "case_id": case_id,
        "case_path": str(case_path),
        "page_object_path": str(page_object_path.resolve()),
        "page_object": page_object_quality,
        "page_object_summary": page_object_summary,
        "test_points_path": str(test_point_path.resolve()) if test_point_path else "",
        "test_points": test_points,
        "run_id": run_id,
        "status": final_status,
        "coverage": coverage,
        "timed_out": timed_out,
        "risk_report": risk_report,
        "execution_gate": execution_gate,
        "review_state": review_state,
        "runner": {
            "script": runner_script,
            "mode": "yaml-driven",
        },
    }
