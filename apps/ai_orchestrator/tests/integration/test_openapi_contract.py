from pathlib import Path

import pytest
import yaml


pytestmark = [pytest.mark.integration]


OPENAPI_PATH = (
    Path(__file__).resolve().parents[2] / "openapi" / "orchestrator-openapi.yaml"
)


def test_openapi_spec_declares_health_and_orchestrate_paths():
    spec = _load_openapi_spec()
    paths = spec["paths"]

    assert "/health" in paths
    assert "/health/llm" in paths
    assert "/orchestrate" in paths
    assert "/requirements/parse" in paths
    assert "/requirements/telemetry/summary" in paths
    assert "/risk/evaluate" in paths
    assert "/failures/triage" in paths
    assert "/healing/preview" in paths
    assert "/reports/latest" in paths
    assert "/reports/{case_id}" in paths
    assert "/runners/catalog" in paths
    assert "/assets/page-objects" in paths
    assert "/assets/page-objects/{page}/elements" in paths
    assert "/assets/test-cases/sync" in paths
    assert "/assets/scaffold" in paths
    assert "/assets/scaffold/templates" in paths
    assert "/assets/scaffold/templates/{template}" in paths
    assert "get" in paths["/health"]
    assert "get" in paths["/health/llm"]
    assert "post" in paths["/orchestrate"]
    assert "post" in paths["/requirements/parse"]
    assert "post" in paths["/risk/evaluate"]
    assert "post" in paths["/failures/triage"]


def test_openapi_spec_matches_current_orchestrate_response_codes():
    spec = _load_openapi_spec()
    responses = spec["paths"]["/orchestrate"]["post"]["responses"]

    assert set(responses.keys()) == {"201", "400", "404", "415", "422", "502", "500"}


def test_openapi_spec_matches_requirement_parse_response_codes():
    spec = _load_openapi_spec()
    responses = spec["paths"]["/requirements/parse"]["post"]["responses"]

    assert set(responses.keys()) == {"201", "400", "404", "415", "422", "500"}


def test_openapi_spec_matches_generation_and_planning_response_codes():
    spec = _load_openapi_spec()

    assert set(spec["paths"]["/health/llm"]["get"]["responses"].keys()) == {"200"}
    assert set(spec["paths"]["/requirements/telemetry/summary"]["get"]["responses"].keys()) == {"200"}
    assert set(spec["paths"]["/risk/evaluate"]["post"]["responses"].keys()) == {"201", "400", "415", "422", "500"}
    assert set(spec["paths"]["/failures/triage"]["post"]["responses"].keys()) == {"201", "400", "415", "422", "500"}


def test_openapi_spec_matches_healing_preview_response_codes():
    spec = _load_openapi_spec()
    responses = spec["paths"]["/healing/preview"]["post"]["responses"]

    assert set(responses.keys()) == {"200", "400", "404", "415", "422", "500"}


def test_openapi_spec_declares_scaffold_template_response_codes():
    spec = _load_openapi_spec()

    assert set(spec["paths"]["/assets/scaffold/templates"]["get"]["responses"].keys()) == {"200", "500"}
    assert set(spec["paths"]["/assets/scaffold/templates/{template}"]["get"]["responses"].keys()) == {"200", "422", "500"}


def test_openapi_spec_declares_report_query_response_codes():
    spec = _load_openapi_spec()

    assert set(spec["paths"]["/reports/latest"]["get"]["responses"].keys()) == {"200", "422", "500"}
    assert set(spec["paths"]["/reports/{case_id}"]["get"]["responses"].keys()) == {"200", "422", "500"}


def test_openapi_spec_requires_page_and_requirement_in_request_body():
    spec = _load_openapi_spec()
    request_schema = spec["components"]["schemas"]["OrchestrateRequest"]

    assert request_schema["required"] == ["requirement", "page"]
    assert request_schema["additionalProperties"] is False
    assert request_schema["properties"]["mode"]["enum"] == ["generate_only", "generate_and_run"]
    assert request_schema["properties"]["source"]["enum"] == ["manual", "ai", "regression"]
    assert request_schema["properties"]["runner"]["enum"] == ["playwright", "api", "mobile"]
    assert "git_diff_path" in request_schema["properties"]
    assert "prd_url" in request_schema["properties"]
    assert "openapi_url" in request_schema["properties"]


def test_openapi_spec_declares_requirement_parse_request_fields():
    spec = _load_openapi_spec()
    request_schema = spec["components"]["schemas"]["ParseRequirementRequest"]

    assert request_schema["required"] == ["requirement", "page"]
    assert request_schema["additionalProperties"] is False
    assert "prd_url" in request_schema["properties"]
    assert "git_diff_path" in request_schema["properties"]
    assert "openapi_url" in request_schema["properties"]


def test_openapi_spec_declares_asset_management_request_schemas():
    spec = _load_openapi_spec()
    schemas = spec["components"]["schemas"]

    assert "CreatePageObjectRequest" in schemas
    assert "AddPageElementRequest" in schemas
    assert "SyncTestCaseRequest" in schemas
    assert "ScaffoldAssetsRequest" in schemas
    assert "ScaffoldElementTemplate" in schemas
    assert "ScaffoldTemplate" in schemas
    assert "ScaffoldTemplateListResponse" in schemas
    assert "ScaffoldTemplateResponse" in schemas
    assert "ExecutionReport" in schemas
    assert "TestPointV1" in schemas
    assert "TestPointPlanV1" in schemas
    assert "ExecutionRecordV1" in schemas
    assert "ExecutionRecordResolutionMetaV1" in schemas
    assert "ParseRequirementRequest" in schemas
    assert "ParseRequirementResponse" in schemas
    assert "RequirementSpecV1" in schemas
    assert "RequirementInputSourceV1" in schemas
    assert "RequirementInputSource" in schemas
    assert "RequirementSourceInputV1" in schemas
    assert "RequirementEntityV1" in schemas
    assert "RequirementParserRuntimeV1" in schemas
    assert "RequirementChangeImpactV1" in schemas
    assert "RunnerProfile" in schemas
    assert "RunnerCatalogResponse" in schemas
    assert "RequirementTestIntentV1" in schemas
    assert "RequirementAmbiguityV1" in schemas
    assert "RequirementBusinessRuleV1" in schemas
    assert "RequirementCoverageEntryV1" in schemas
    assert "RequirementQualityGateV1" in schemas
    assert "RequirementQualityGateBlockerV1" in schemas
    assert "ExecutionStepSummaryV1" in schemas
    assert "ExecutionEvidenceIndexV1" in schemas
    assert "EvidenceManifestV1" in schemas
    assert "TestPoint" in schemas
    assert "TestPointPlan" in schemas
    assert "ExecutionRecord" in schemas
    assert "ExecutionRequestContext" in schemas
    assert "ExecutionReportMetrics" in schemas
    assert "ExecutionEvidenceSummary" in schemas
    assert "ExecutionReportResponse" in schemas
    assert "ReportSummaryPreview" in schemas
    assert "ReportSummaryActionableCase" in schemas
    assert "PytestResults" in schemas
    assert "FailureAnalysis" in schemas
    assert "SelfHealingAdvice" in schemas
    assert "SelfHealingSuggestionPreview" in schemas
    assert "SelfHealingExecutionPreview" in schemas
    assert "SelfHealingPreviewRequest" in schemas
    assert "SelfHealingPreviewResponse" in schemas
    assert "RiskReportResponse" in schemas
    assert "FailureTriageResponse" in schemas
    blocker_schema = schemas["RequirementQualityGateBlockerV1"]
    assert blocker_schema["properties"]["alert_code"]["type"] == "string"
    assert blocker_schema["properties"]["category"]["type"] == "string"
    assert blocker_schema["properties"]["severity"]["enum"] == ["low", "medium", "high", "critical"]


def test_openapi_spec_declares_requirement_parse_envelope():
    spec = _load_openapi_spec()
    schemas = spec["components"]["schemas"]
    response_schema = schemas["ParseRequirementResponse"]
    output_contract_schema = schemas["OutputContractV1"]

    assert response_schema["required"] == [
        "requirement_spec",
        "requirement_analysis_markdown",
        "output_contract",
    ]
    assert response_schema["additionalProperties"] is False
    assert response_schema["properties"]["requirement_analysis_markdown"]["type"] == "string"
    assert response_schema["properties"]["output_contract"]["$ref"] == "#/components/schemas/OutputContractV1"
    assert output_contract_schema["additionalProperties"] is False
    assert output_contract_schema["required"] == ["machine_schema", "human_render", "rendered_by"]
    assert output_contract_schema["properties"]["machine_schema"]["type"] == "string"
    assert output_contract_schema["properties"]["human_render"]["type"] == "string"
    assert output_contract_schema["properties"]["rendered_by"]["type"] == "string"


def test_openapi_spec_declares_requirement_spec_runtime_fields():
    spec = _load_openapi_spec()
    schema = spec["components"]["schemas"]["RequirementSpecV1"]

    assert schema["properties"]["source_type"]["type"] == "string"
    assert "raw_requirement" in schema["properties"]
    assert "normalized_requirement" in schema["properties"]
    assert "source_inputs" in schema["properties"]
    assert "entities" in schema["properties"]
    assert "dependency_graph" in schema["properties"]
    assert "historical_patterns" in schema["properties"]
    assert "change_impact" in schema["properties"]
    assert "parser_runtime" in schema["properties"]
    assert "design_input" in schema["properties"]
    assert schema["additionalProperties"] is False


def test_openapi_spec_allows_scaffold_element_templates():
    spec = _load_openapi_spec()
    schema = spec["components"]["schemas"]["ScaffoldAssetsRequest"]
    elements_schema = schema["properties"]["elements"]
    element_template = spec["components"]["schemas"]["ScaffoldElementTemplate"]

    assert elements_schema["type"] == "array"
    assert elements_schema["items"]["$ref"] == "#/components/schemas/ScaffoldElementTemplate"
    assert element_template["properties"]["smoke_role"]["enum"] == ["menu", "assert"]
    assert schema["properties"]["template"]["type"] == "string"


def test_openapi_spec_declares_report_fields_on_orchestration_result():
    spec = _load_openapi_spec()
    result_schema = spec["components"]["schemas"]["OrchestrationResult"]
    response_schema = spec["components"]["schemas"]["ExecutionReportResponse"]

    assert "requirement_spec" in result_schema["properties"]
    assert "report" in result_schema["properties"]
    assert "generated_script" in result_schema["properties"]
    assert "execution_plan" in result_schema["properties"]
    assert "design_generation" in result_schema["properties"]
    assert "risk_report" in result_schema["properties"]
    assert "failure_triage" in result_schema["properties"]
    assert "agent_pipeline" in result_schema["properties"]
    assert "test_points" in result_schema["properties"]
    assert "execution_record" in result_schema["properties"]
    assert "report_json_path" in result_schema["properties"]
    assert "report_markdown_path" in result_schema["properties"]
    assert "report_summary_path" in result_schema["properties"]
    assert result_schema["properties"]["report"]["$ref"] == "#/components/schemas/ExecutionReport"
    assert result_schema["properties"]["test_points"]["$ref"] == "#/components/schemas/TestPointPlanV1"
    assert result_schema["properties"]["execution_record"]["$ref"] == "#/components/schemas/ExecutionRecordV1"
    assert response_schema["properties"]["execution_record"]["$ref"] == "#/components/schemas/ExecutionRecordV1"
    assert "report_summary_path" in response_schema["properties"]
    assert response_schema["properties"]["report_summary_preview"]["$ref"] == "#/components/schemas/ReportSummaryPreview"


def test_openapi_spec_declares_pytest_and_failure_analysis_fields():
    spec = _load_openapi_spec()
    report_schema = spec["components"]["schemas"]["ExecutionReport"]

    assert report_schema["properties"]["pytest_results"]["$ref"] == "#/components/schemas/PytestResults"
    assert report_schema["properties"]["failure_analysis"]["$ref"] == "#/components/schemas/FailureAnalysis"
    assert report_schema["properties"]["self_healing_enabled"]["type"] == "boolean"
    assert report_schema["properties"]["self_healing_attempted"]["type"] == "boolean"
    assert report_schema["properties"]["requirement_spec"]["$ref"] == "#/components/schemas/RequirementSpecV1"
    assert report_schema["properties"]["test_points_summary"]["$ref"] == "#/components/schemas/ExecutionTestPointsSummaryV1"
    assert report_schema["properties"]["generated_script"]["type"] == "object"
    assert report_schema["properties"]["execution_plan"]["type"] == "object"
    assert report_schema["properties"]["design_generation"]["type"] == "object"
    assert report_schema["properties"]["agent_pipeline"]["type"] == "array"
    assert report_schema["properties"]["risk_report"]["type"] == "object"
    assert report_schema["properties"]["self_healing_advice"]["$ref"] == "#/components/schemas/SelfHealingAdvice"
    assert report_schema["properties"]["self_healing_suggestion_preview"]["$ref"] == "#/components/schemas/SelfHealingSuggestionPreview"
    assert report_schema["properties"]["self_healing_execution_preview"]["$ref"] == "#/components/schemas/SelfHealingExecutionPreview"
    assert report_schema["properties"]["execution_record"]["$ref"] == "#/components/schemas/ExecutionRecordV1"
    assert report_schema["properties"]["execution_record_meta"]["$ref"] == "#/components/schemas/ExecutionRecordResolutionMetaV1"
    assert report_schema["properties"]["request_context"]["$ref"] == "#/components/schemas/ExecutionRequestContext"
    assert report_schema["properties"]["failure_reason"]["type"] == "string"


def test_openapi_spec_declares_execution_request_context_and_test_points_summary():
    spec = _load_openapi_spec()
    request_context_schema = spec["components"]["schemas"]["ExecutionRequestContext"]
    test_points_summary_schema = spec["components"]["schemas"]["ExecutionTestPointsSummaryV1"]

    assert request_context_schema["additionalProperties"] is False
    assert request_context_schema["required"] == [
        "page",
        "mode",
        "source",
        "execution_requested",
        "runner",
        "runner_profile",
        "requirement_parser",
        "technique_summary",
        "source_summary",
        "page_resolution",
        "change_impact",
    ]
    assert request_context_schema["properties"]["runner_profile"]["$ref"] == "#/components/schemas/RunnerProfile"
    assert request_context_schema["properties"]["requirement_parser"]["type"] == "object"
    assert request_context_schema["properties"]["technique_summary"]["type"] == "object"
    assert request_context_schema["properties"]["source_summary"]["type"] == "object"
    assert request_context_schema["properties"]["page_resolution"]["type"] == "object"
    assert request_context_schema["properties"]["change_impact"]["type"] == "object"

    assert test_points_summary_schema["additionalProperties"] is False
    assert test_points_summary_schema["required"] == [
        "page",
        "point_count",
        "review_summary",
        "technique_summary",
        "traceability_summary",
    ]
    report_schema = spec["components"]["schemas"]["ExecutionReport"]
    assert report_schema["properties"]["source"]["enum"] == ["manual", "ai", "regression"]
    assert report_schema["properties"]["evidence"]["$ref"] == "#/components/schemas/EvidenceManifestV1"
    evidence_schema = spec["components"]["schemas"]["EvidenceManifestV1"]
    assert "analysis_files" in evidence_schema["properties"]
    assert "suggestion_files" in evidence_schema["properties"]
    assert "execution_record_files" in evidence_schema["properties"]
    assert "self_healing_result_files" in evidence_schema["properties"]
    assert evidence_schema["properties"]["version"]["const"] == "EvidenceManifestV1"
    meta_schema = spec["components"]["schemas"]["ExecutionRecordResolutionMetaV1"]
    assert "manifest_record_path" in meta_schema["properties"]
    assert "manifest_status" in meta_schema["properties"]
    assert "resolution_reason" in meta_schema["properties"]


def _load_openapi_spec() -> dict:
    with open(OPENAPI_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
