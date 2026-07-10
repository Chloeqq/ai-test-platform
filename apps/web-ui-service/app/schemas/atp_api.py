"""ATP API Schemas — Phase 3 Platform Integration.

Pydantic models for ATP analyze/capabilities/health endpoints.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# POST /api/atp/analyze
# ---------------------------------------------------------------------------

class RequirementInput(BaseModel):
    """Natural language requirement text."""
    text: str = ""


class SutApiConfig(BaseModel):
    """System Under Test API configuration."""
    login_path: str = ""
    base_path: str = ""


class SutConfig(BaseModel):
    """System Under Test configuration."""
    base_url: str = ""
    api: SutApiConfig = Field(default_factory=SutApiConfig)


class UIEvidenceInput(BaseModel):
    """Single UI test result evidence."""
    case_id: str = ""
    intent_name: str = ""
    status: str = "passed"
    format: str = "playwright"  # "playwright" | "generic"
    assertions: list[dict[str, Any]] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    """POST /api/atp/analyze request body."""
    requirement: RequirementInput = Field(default_factory=RequirementInput)
    sut: SutConfig = Field(default_factory=SutConfig)
    ui_evidences: list[UIEvidenceInput] = Field(default_factory=list)
    use_llm: bool = False


# ---------------------------------------------------------------------------
# POST /api/atp/analyze response
# ---------------------------------------------------------------------------

class ApiExecutionSummary(BaseModel):
    """Summary of API test execution."""
    intent_name: str = ""
    scenario: str = ""
    status: str = ""
    assertions_passed: int = 0
    assertions_total: int = 0
    failure_layer: str | None = None
    platform_error: bool = False


class LayerDivergenceOutput(BaseModel):
    """Single layer divergence in response."""
    direction: str = ""
    description: str = ""
    possible_causes: list[str] = Field(default_factory=list)


class LayerComparisonOutput(BaseModel):
    """Layer comparison result in response."""
    intent_name: str = ""
    has_divergences: bool = False
    divergences: list[LayerDivergenceOutput] = Field(default_factory=list)


class AnalyzeReport(BaseModel):
    """Report section of analyze response."""
    summary: str = ""
    confidence_level: str = ""
    findings: list[str] = Field(default_factory=list)
    total_intents: int = 0
    total_ui_evidences: int = 0


class AnalyzeResponse(BaseModel):
    """POST /api/atp/analyze response body."""
    execution_results: list[ApiExecutionSummary] = Field(default_factory=list)
    layer_comparisons: list[LayerComparisonOutput] = Field(default_factory=list)
    report: AnalyzeReport = Field(default_factory=AnalyzeReport)


# ---------------------------------------------------------------------------
# GET /api/atp/capabilities
# ---------------------------------------------------------------------------

class CapabilitiesResponse(BaseModel):
    """GET /api/atp/capabilities response."""
    version: str = "v3.2"
    features: list[str] = Field(default_factory=lambda: [
        "api_oracle",
        "sql_assertion",
        "ui_evidence_analysis",
        "layer_comparison",
        "fault_attribution",
        "test_reliability_gate",
        "requirement_parser",
    ])
    supported_ui_formats: list[str] = Field(default_factory=lambda: [
        "playwright-json",
        "generic",
    ])


# ---------------------------------------------------------------------------
# GET /api/atp/health
# ---------------------------------------------------------------------------

class HealthCheck(BaseModel):
    """Individual health check result."""
    status: str = "unknown"  # "ready" | "unavailable" | "error"
    message: str = ""


class SutConnectionCheck(BaseModel):
    """SUT connectivity check."""
    url: str = ""
    status: str = "unknown"  # "reachable" | "unreachable" | "not_configured"


class HealthResponse(BaseModel):
    """GET /api/atp/health response."""
    status: str = "unknown"  # "healthy" | "degraded" | "unhealthy"
    checks: dict[str, HealthCheck] = Field(default_factory=dict)
    sut_connection: SutConnectionCheck = Field(default_factory=SutConnectionCheck)
