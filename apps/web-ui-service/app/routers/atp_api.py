"""ATP API Router — Phase 3 Platform Integration.

Three endpoints:
  POST /api/atp/analyze     — Requirement → API Oracle → Layer Compare → Report
  GET  /api/atp/capabilities — List platform features
  GET  /api/atp/health       — Health check with per-component diagnostics

This router is independent of the existing workbench UI test infrastructure.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.schemas.atp_api import (
    AnalyzeRequest,
    AnalyzeResponse,
    CapabilitiesResponse,
    HealthResponse,
)
from app.services.atp_bridge import (
    get_capabilities,
    get_health,
    run_analyze,
)

router = APIRouter(tags=["atp-api"], prefix="/api/atp")


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a requirement against a system under test.

    Steps:
      1. Parse requirement → TestIntents
      2. Execute API tests against SUT
      3. Import UI evidence (if provided)
      4. Layer comparison (intent vs API vs UI)
      5. Return full analysis report

    Example request body:
        {
          "requirement": {"text": "验证登录：正确密码成功，错误密码拒绝"},
          "sut": {"base_url": "http://localhost:8090", "api": {"login_path": "/admin/login"}},
          "ui_evidences": [{"case_id": "c1", "status": "failed", "assertions": [...]}]
        }
    """
    return run_analyze(payload)


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities() -> CapabilitiesResponse:
    """Return ATP platform capabilities and supported features."""
    return get_capabilities()


@router.get("/health", response_model=HealthResponse)
def health(sut_url: str = Query(default="", description="Optional SUT base URL to check connectivity")) -> HealthResponse:
    """Platform health check with per-component diagnostics.

    Query params:
        sut_url: Optional SUT URL to test connectivity.
    """
    return get_health(sut_url=sut_url)
