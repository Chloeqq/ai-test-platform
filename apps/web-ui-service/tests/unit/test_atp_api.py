"""Smoke tests for ATP API integration — Phase 3."""
from __future__ import annotations

import pytest

from app.schemas.atp_api import (
    AnalyzeRequest,
    AnalyzeResponse,
    CapabilitiesResponse,
    HealthResponse,
    RequirementInput,
    SutConfig,
    SutApiConfig,
    HealthCheck,
)
from app.services.atp_bridge import get_capabilities, get_health


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

def test_analyze_request_defaults():
    req = AnalyzeRequest(requirement=RequirementInput(text="test"))
    assert req.requirement.text == "test"
    assert req.sut.base_url == ""
    assert req.ui_evidences == []
    assert req.use_llm is False


def test_analyze_request_full():
    req = AnalyzeRequest(
        requirement=RequirementInput(text="验证登录"),
        sut=SutConfig(base_url="http://localhost:8090", api=SutApiConfig(login_path="/admin/login")),
        ui_evidences=[{
            "case_id": "c1", "intent_name": "test", "status": "failed",
            "format": "playwright", "assertions": [{"type": "assert_text", "target": "btn", "expected": "x", "actual": "y"}],
        }],
    )
    assert req.sut.base_url == "http://localhost:8090"
    assert req.sut.api.login_path == "/admin/login"
    assert len(req.ui_evidences) == 1
    assert req.ui_evidences[0].case_id == "c1"


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

def test_capabilities_response():
    caps = get_capabilities()
    assert isinstance(caps, CapabilitiesResponse)
    assert caps.version == "v3.2"
    assert "api_oracle" in caps.features
    assert "layer_comparison" in caps.features
    assert "playwright-json" in caps.supported_ui_formats


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_without_sut():
    health = get_health(sut_url="")
    assert isinstance(health, HealthResponse)
    assert health.status in {"healthy", "degraded", "unhealthy"}
    assert "api_runner" in health.checks
    assert "db_runner" in health.checks


def test_health_with_unreachable_sut():
    health = get_health(sut_url="http://192.0.2.1:9999")
    assert health.sut_connection.status == "unreachable"


# ---------------------------------------------------------------------------
# HealthCheck model
# ---------------------------------------------------------------------------

def test_health_check_defaults():
    hc = HealthCheck()
    assert hc.status == "unknown"
    assert hc.message == ""


def test_health_check_ready():
    hc = HealthCheck(status="ready", message="all good")
    assert hc.status == "ready"
