"""ATP Bridge Service — Phase 3 Integration.

Translates between the web API layer and the runners/api_python/ core.
Keeps runners pure; this is the only place that knows about both worlds.
"""
from __future__ import annotations

import os
from typing import Any

from app.models.api_test_models import (
    ApiRequest,
    Assertion,
    ExecutionResult,
    TestIntent,
)
from app.schemas.atp_api import (
    AnalyzeReport,
    AnalyzeRequest,
    AnalyzeResponse,
    ApiExecutionSummary,
    CapabilitiesResponse,
    HealthCheck,
    HealthResponse,
    LayerComparisonOutput,
    LayerDivergenceOutput,
    SutConnectionCheck,
)
from runners.api_python.executor.api_step_runner import execute_api_test
from runners.api_python.layer_comparator import compare_layers
from runners.api_python.requirement_parser import parse_requirement
from runners.api_python.ui_evidence_adapter import import_ui_results


# ---------------------------------------------------------------------------
# POST /api/atp/analyze
# ---------------------------------------------------------------------------

def run_analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Execute the full ATP analysis pipeline."""
    # 1. Parse requirement → TestIntents
    intents = _parse_to_test_intents(req)

    # 2. Execute API tests
    api_results = _execute_api_tests(intents, req.sut.base_url)

    # 3. Import UI evidence
    ui_evidence_map = _import_ui_evidence(req)

    # 4. Layer comparison
    comparisons = _run_layer_comparisons(intents, api_results, ui_evidence_map)

    # 5. Build response
    return _build_analyze_response(intents, api_results, comparisons, len(req.ui_evidences))


def _parse_to_test_intents(req: AnalyzeRequest) -> list[TestIntent]:
    """Parse requirement text into TestIntent list."""
    # Try parsing from requirement text
    parsed = parse_requirement(req.requirement.text, use_llm=req.use_llm)

    intents: list[TestIntent] = []
    for idx, item in enumerate(parsed):
        scenario = item.get("scenario", "positive")
        # Build API request from sut config
        login_path = req.sut.api.login_path or "/admin/login"
        base_path = req.sut.api.base_path or ""

        if scenario == "positive":
            body = {"username": os.getenv("ATP_SUT_USERNAME", "admin"),
                    "password": os.getenv("ATP_SUT_PASSWORD", "macro123")}
            assertions = [
                {"type": "status", "expected": 200},
                {"type": "json", "path": "code", "expected": 200},
                {"type": "json", "path": "data.token", "operator": "not_empty"},
            ]
        else:
            body = {"username": os.getenv("ATP_SUT_USERNAME", "admin"),
                    "password": "wrong_password"}
            assertions = [
                {"type": "status", "expected": 200},
                {"type": "json", "path": "code", "expected": 500},
                {"type": "json", "path": "message", "operator": "contains", "expected": "密码"},
            ]

        intents.append(TestIntent(
            name=item.get("name", f"intent_{idx}"),
            scenario=scenario,
            api_request=ApiRequest(
                method="POST",
                path=f"{base_path}{login_path}",
                body=body,
            ),
            assertions=[Assertion(**a) for a in assertions],
        ))

    return intents


def _execute_api_tests(intents: list[TestIntent], base_url: str) -> list[ExecutionResult]:
    """Run all API tests."""
    return [execute_api_test(i, base_url=base_url, skip_selftest=True) for i in intents]


def _import_ui_evidence(req: AnalyzeRequest) -> dict[str, Any]:
    """Import UI evidence from request.

    Returns a dict keyed by intent_name for direct lookup.
    """
    raw = [
        {
            "case_id": e.case_id,
            "intent_name": e.intent_name,
            "status": e.status,
            "assertions": e.assertions,
        }
        for e in req.ui_evidences
    ]
    imported = import_ui_results(raw, format="playwright")
    return {e.intent_name: e for e in imported}


def _infer_scenario_from_ui_status(evidence: Any) -> str:
    """Infer scenario type from UI evidence status and assertions.

    If status=failed or has assertions targeting error elements → negative.
    Otherwise → positive.
    """
    if hasattr(evidence, "status") and evidence.status == "failed":
        return "negative"
    if hasattr(evidence, "assertions"):
        for a in evidence.assertions:
            target = getattr(a, "target", "")
            expected = getattr(a, "expected", "")
            # Error checking assertions → likely negative scenario
            if any(kw in str(target) + str(expected) for kw in ("error", "toast", "错误", "不能", "拒绝")):
                return "negative"
    return "positive"


def _match_ui_evidence(
    intent_name: str,
    intent_scenario: str,
    ui_evidence_map: dict[str, Any],
    used: set[str],
) -> Any | None:
    """Match UI evidence to an intent.

    1. First try exact name match.
    2. Then try scenario-based match (same scenario, not yet used).
    """
    # Exact match
    if intent_name in ui_evidence_map and intent_name not in used:
        used.add(intent_name)
        return ui_evidence_map[intent_name]

    # Scenario-based fallback match
    for name, evidence in ui_evidence_map.items():
        if name in used:
            continue
        inferred = _infer_scenario_from_ui_status(evidence)
        if inferred == intent_scenario:
            used.add(name)
            return evidence

    return None


def _run_layer_comparisons(
    intents: list[TestIntent],
    api_results: list[ExecutionResult],
    ui_evidence_map: dict[str, Any],
) -> list[LayerComparisonOutput]:
    """Run layer comparisons for all intents.

    Matches UI evidence to API intents by name first, then by scenario type.
    Each UI evidence is used at most once.
    """
    api_map = {r.intent_name: r for r in api_results}
    outputs: list[LayerComparisonOutput] = []
    used_evidence: set[str] = set()

    for intent in intents:
        matched_ui = _match_ui_evidence(
            intent.name, intent.scenario, ui_evidence_map, used_evidence,
        )
        comp = compare_layers(
            intent_name=intent.name,
            intent_scenario=intent.scenario,
            api_result=api_map.get(intent.name),
            ui_evidence=matched_ui,
        )
        outputs.append(LayerComparisonOutput(
            intent_name=comp.intent_name,
            has_divergences=comp.has_divergences,
            divergences=[
                LayerDivergenceOutput(
                    direction=d.direction,
                    description=d.description,
                    possible_causes=d.possible_causes,
                )
                for d in comp.divergences
            ],
        ))

    return outputs


def _build_analyze_response(
    intents: list[TestIntent],
    api_results: list[ExecutionResult],
    comparisons: list[LayerComparisonOutput],
    ui_evidence_count: int,
) -> AnalyzeResponse:
    """Build final analyze response."""
    summaries = [
        ApiExecutionSummary(
            intent_name=r.intent_name,
            scenario=intents[i].scenario if i < len(intents) else "positive",
            status=r.status,
            assertions_passed=sum(1 for a in r.assertions if a.passed),
            assertions_total=len(r.assertions),
            failure_layer=r.failure_layer,
            platform_error=r.platform_error,
        )
        for i, r in enumerate(api_results)
    ]

    passed = sum(1 for r in api_results if r.status == "passed")
    total = len(api_results)
    platform_errors = sum(1 for r in api_results if r.platform_error)
    divergences = sum(1 for c in comparisons if c.has_divergences)

    if platform_errors:
        confidence = "Level_C"
    elif divergences > 0:
        confidence = "Level_B"
    else:
        confidence = "Level_A"

    findings: list[str] = []
    for c in comparisons:
        for d in c.divergences:
            findings.append(f"[{d.direction}] {c.intent_name}: {d.description}")

    report = AnalyzeReport(
        summary=f"{total} intents, {passed} passed, {divergences} with divergences",
        confidence_level=confidence,
        findings=findings,
        total_intents=total,
        total_ui_evidences=ui_evidence_count,
    )

    return AnalyzeResponse(
        execution_results=summaries,
        layer_comparisons=comparisons,
        report=report,
    )


# ---------------------------------------------------------------------------
# GET /api/atp/capabilities
# ---------------------------------------------------------------------------

def get_capabilities() -> CapabilitiesResponse:
    """Return ATP platform capabilities."""
    return CapabilitiesResponse()


# ---------------------------------------------------------------------------
# GET /api/atp/health
# ---------------------------------------------------------------------------

def get_health(sut_url: str = "") -> HealthResponse:
    """Run health checks and return status."""
    checks: dict[str, HealthCheck] = {}

    # API Runner check
    try:
        from runners.api_python.executor.api_step_runner import selftest
        ok, msg = selftest(timeout=10)
        checks["api_runner"] = HealthCheck(
            status="ready" if ok else "unavailable", message=msg,
        )
    except Exception as exc:
        checks["api_runner"] = HealthCheck(status="error", message=str(exc))

    # DB Runner check
    db_url = os.getenv("ATP_SUT_DB_URL", "").strip()
    if db_url:
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(db_url, future=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            checks["db_runner"] = HealthCheck(status="ready", message=f"connected to {db_url[:40]}...")
        except Exception as exc:
            checks["db_runner"] = HealthCheck(status="unavailable", message=str(exc))
    else:
        checks["db_runner"] = HealthCheck(status="unavailable", message="ATP_SUT_DB_URL not configured")

    # LLM Parser check
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        checks["llm_parser"] = HealthCheck(status="ready", message="LLM configured")
    else:
        checks["llm_parser"] = HealthCheck(status="unavailable", message="OPENAI_API_KEY not set (mock mode available)")

    # SUT connection
    sut_check = SutConnectionCheck(url=sut_url, status="not_configured")
    if sut_url:
        try:
            import requests
            resp = requests.get(sut_url, timeout=5)
            sut_check.status = "reachable"
            sut_check.url = sut_url
        except Exception as exc:
            sut_check.status = "unreachable"
            sut_check.url = f"{sut_url} ({exc})"
    checks["sut_connection"] = HealthCheck(status=sut_check.status, message=sut_check.url)

    # Overall status
    all_ready = all(c.status == "ready" or c.status == "unavailable" for c in checks.values())
    any_error = any(c.status == "error" for c in checks.values())

    if any_error:
        overall = "unhealthy"
    elif all_ready:
        overall = "healthy"
    else:
        overall = "degraded"

    return HealthResponse(status=overall, checks=checks, sut_connection=sut_check)
