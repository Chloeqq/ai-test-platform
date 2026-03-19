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
    assert "/orchestrate" in paths
    assert "/requirements/parse" in paths
    assert "/healing/preview" in paths
    assert "/reports/latest" in paths
    assert "/reports/{case_id}" in paths
    assert "/assets/page-objects" in paths
    assert "/assets/page-objects/{page}/elements" in paths
    assert "/assets/test-cases/sync" in paths
    assert "/assets/scaffold" in paths
    assert "/assets/scaffold/templates" in paths
    assert "/assets/scaffold/templates/{template}" in paths
    assert "get" in paths["/health"]
    assert "post" in paths["/orchestrate"]
    assert "post" in paths["/requirements/parse"]


def test_openapi_spec_matches_current_orchestrate_response_codes():
    spec = _load_openapi_spec()
    responses = spec["paths"]["/orchestrate"]["post"]["responses"]

    assert set(responses.keys()) == {"201", "400", "404", "415", "422", "502", "500"}


def test_openapi_spec_matches_requirement_parse_response_codes():
    spec = _load_openapi_spec()
    responses = spec["paths"]["/requirements/parse"]["post"]["responses"]

    assert set(responses.keys()) == {"201", "400", "404", "415", "422", "500"}


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
    blocker_schema = schemas["RequirementQualityGateBlockerV1"]
    assert blocker_schema["properties"]["alert_code"]["type"] == "string"
    assert blocker_schema["properties"]["category"]["type"] == "string"
    assert blocker_schema["properties"]["severity"]["enum"] == ["low", "medium", "high", "critical"]


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

    assert "report" in result_schema["properties"]
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
    assert report_schema["properties"]["self_healing_advice"]["$ref"] == "#/components/schemas/SelfHealingAdvice"
    assert report_schema["properties"]["self_healing_suggestion_preview"]["$ref"] == "#/components/schemas/SelfHealingSuggestionPreview"
    assert report_schema["properties"]["self_healing_execution_preview"]["$ref"] == "#/components/schemas/SelfHealingExecutionPreview"
    assert report_schema["properties"]["execution_record"]["$ref"] == "#/components/schemas/ExecutionRecordV1"
    assert report_schema["properties"]["execution_record_meta"]["$ref"] == "#/components/schemas/ExecutionRecordResolutionMetaV1"
    assert report_schema["properties"]["request_context"]["$ref"] == "#/components/schemas/ExecutionRequestContext"
    assert report_schema["properties"]["failure_reason"]["type"] == "string"
    assert report_schema["properties"]["source"]["enum"] == ["manual", "ai", "regression"]
    assert report_schema["properties"]["evidence"]["$ref"] == "#/components/schemas/EvidenceManifestV1"
    evidence_schema = spec["components"]["schemas"]["EvidenceManifestV1"]
    assert "analysis_files" in evidence_schema["properties"]
    assert "suggestion_files" in evidence_schema["properties"]
    assert "execution_record_files" in evidence_schema["properties"]
    assert "self_healing_result_files" in evidence_schema["properties"]
    assert evidence_schema["properties"]["version"]["const"] == "EvidenceManifestV1"


def _load_openapi_spec() -> dict:
    with open(OPENAPI_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
