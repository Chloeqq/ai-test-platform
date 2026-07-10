from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ..debug import log_debug_event

RunOrchestratorParse = Callable[..., dict[str, Any]]
RenderRequirementSpecMarkdown = Callable[[dict[str, Any]], str]
ExtractQualityGate = Callable[[dict[str, Any] | None], dict[str, Any] | None]
ListValue = Callable[[Any], list[Any]]
DictValue = Callable[[Any], dict[str, Any]]


_LOGGER = logging.getLogger(__name__)


def run_preview_pipeline(
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
    list_value: ListValue,
    dict_value: DictValue,
    trace_id: str = "",
) -> dict[str, Any]:
    log_debug_event(
        logger=_LOGGER,
        event="runtime.preview.input",
        trace_id=trace_id,
        payload={
            "effective_requirement": effective_requirement,
            "normalized_page": normalized_page,
            "source": source,
            "input_sources": input_sources,
            "openapi_spec": openapi_spec,
        },
        extra={"compare_with_event": "service.preview.input"},
    )
    parse_result = run_orchestrator_parse(
        requirement=effective_requirement,
        page=normalized_page,
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
    )
    requirement_spec = parse_result.get("requirement_spec")
    if not isinstance(requirement_spec, dict):
        requirement_spec = parse_result if isinstance(parse_result, dict) else {}
    requirement_analysis_markdown = str(parse_result.get("requirement_analysis_markdown", "")).strip()
    if not requirement_analysis_markdown:
        requirement_analysis_markdown = render_requirement_spec_markdown(requirement_spec)
    quality_gate = extract_quality_gate(requirement_spec)
    test_intents = list_value(requirement_spec.get("test_intents"))
    ambiguities = list_value(requirement_spec.get("ambiguities"))
    business_rules = list_value(requirement_spec.get("business_rules"))
    parser_runtime = dict_value(requirement_spec.get("parser_runtime"))
    source_summary = dict_value(parser_runtime.get("source_summary"))
    source_inputs = list_value(requirement_spec.get("source_inputs"))
    source_count = int(
        source_summary.get(
            "source_count",
            parser_runtime.get("source_count", len(source_inputs)),
        )
        or 0
    )
    source_types = list_value(source_summary.get("source_types"))
    if not source_types:
        source_types = [
            str(item.get("source_type", "")).strip()
            for item in source_inputs
            if isinstance(item, dict) and str(item.get("source_type", "")).strip()
        ]
    deduped_source_types: list[str] = []
    for item in source_types:
        value = str(item).strip()
        if value and value not in deduped_source_types:
            deduped_source_types.append(value)
    change_impact = dict_value(requirement_spec.get("change_impact"))

    intent_type_distribution: dict[str, int] = {}
    for item in test_intents:
        if not isinstance(item, dict):
            continue
        intent_type = str(item.get("intent_type", "unknown")).strip() or "unknown"
        intent_type_distribution[intent_type] = intent_type_distribution.get(intent_type, 0) + 1

    result = {
        "item": {
            "page": str(requirement_spec.get("page", "")).strip(),
            "priority": str(requirement_spec.get("priority", "")).strip() or "P1",
            "parse_confidence": requirement_spec.get("parse_confidence", 0),
            "intent_count": len(test_intents),
            "intent_type_distribution": intent_type_distribution,
            "ambiguity_count": len(ambiguities),
            "rule_count": len(business_rules),
            "source_count": source_count,
            "source_types": deduped_source_types,
            "change_impact": {
                "impact_score": change_impact.get("impact_score", 0),
                "changed_areas": list_value(change_impact.get("changed_areas")),
                "risk_signal_count": len(list_value(change_impact.get("risk_signals"))),
                "top_factor": dict_value(change_impact.get("top_factor")),
                "recommended_regression_scope": list_value(change_impact.get("recommended_regression_scope")),
            },
            "quality_gate": quality_gate,
            "requirement_spec": requirement_spec,
            "requirement_analysis_markdown": requirement_analysis_markdown,
            "output_contract": {
                "machine_schema": "RequirementSpecV1",
                "human_render": "RequirementAnalysisMarkdownV1",
                "rendered_by": "web-ui-service",
            },
        }
    }
    log_debug_event(
        logger=_LOGGER,
        event="runtime.preview.output",
        trace_id=trace_id,
        payload=result,
    )
    return result
