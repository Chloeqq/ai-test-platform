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
from shared_backend.type_utils import dict_value as _dict_value, list_value as _list_value


BuildSystemRequirement = Callable[..., str]
RunOrchestratorParse = Callable[..., dict[str, Any]]
RunOrchestratorGenerate = Callable[..., dict[str, Any]]
RenderRequirementSpecMarkdown = Callable[[dict[str, Any]], str]
ExtractQualityGate = Callable[[dict[str, Any] | None], dict[str, Any] | None]
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
    write_case_yaml: WriteCaseYaml,
    save_case_state: SaveCaseState,
    save_test_point_plan: SaveTestPointPlan | None = None,
    append_history: AppendHistory,
    now_iso: NowIso,
    is_quality_gate_blocked: IsQualityGateBlocked,
    ai_cases_root: Any,
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
        http_exception_cls=http_exception_cls,
        bad_gateway_status=bad_gateway_status,
        unprocessable_entity_status=unprocessable_entity_status,
        existing_case_ids=existing_case_ids,
        selected_candidate=selected_candidate,
        allocate_case_id=allocate_case_id,
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


