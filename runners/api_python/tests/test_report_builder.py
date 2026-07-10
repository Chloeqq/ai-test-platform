"""Unit tests for Report Builder — Sprint 2 Day 9."""
from __future__ import annotations

from app.models.api_test_models import (
    AssertionResult,
    ExecutionResult,
    TestReport,
)
from runners.api_python.layer_comparator import LayerComparison, LayerDivergence
from runners.api_python.report_builder import (
    build_report,
    quick_report,
    render_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api_passed(name="test") -> ExecutionResult:
    return ExecutionResult(
        intent_name=name, status="passed", failure_layer=None, platform_error=False,
        assertions=[AssertionResult(type="status", expected=200, actual=200, passed=True)],
        evidence={"response": {"body": {"code": 200}}},
    )


def _api_failed(name="test") -> ExecutionResult:
    return ExecutionResult(
        intent_name=name, status="failed", failure_layer="business_rule", platform_error=False,
        assertions=[AssertionResult(type="status", expected=200, actual=500, passed=False)],
        evidence={"response": {"body": {"code": 500}}},
    )


def _api_network_error() -> ExecutionResult:
    return ExecutionResult(
        intent_name="conn_test", status="failed", failure_layer="network", platform_error=False,
        evidence={"error": "connection_refused"},
    )


def _api_platform_error() -> ExecutionResult:
    return ExecutionResult(
        intent_name="plat_test", status="failed", platform_error=True,
        platform_error_details="selftest FAIL",
    )


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------

def test_build_report_all_passed():
    results = [_api_passed("a"), _api_passed("b")]
    report = build_report(results, title="Test")
    assert isinstance(report, TestReport)
    assert "2 scenarios" in report.summary
    assert "2 passed" in report.summary
    assert report.confidence_level == "Level_A"


def test_build_report_mixed():
    results = [_api_passed("a"), _api_failed("b")]
    report = build_report(results)
    assert "2 scenarios" in report.summary
    assert "1 passed" in report.summary
    assert "1 failed" in report.summary


def test_build_report_with_network_error():
    results = [_api_network_error()]
    report = build_report(results)
    assert report.confidence_level == "Level_B"


def test_build_report_with_platform_error():
    results = [_api_platform_error()]
    report = build_report(results)
    assert report.confidence_level == "Level_C"


def test_build_report_with_layer_comparisons():
    results = [_api_passed("a"), _api_failed("b")]
    comps = [
        LayerComparison(intent_name="a"),
        LayerComparison(intent_name="b", divergences=[
            LayerDivergence(direction="intent_api", description="API mismatch"),
        ]),
    ]
    report = build_report(results, layer_comparisons=comps)
    assert len(report.findings) == 1
    assert "API mismatch" in report.findings[0]


# ---------------------------------------------------------------------------
# render_report
# ---------------------------------------------------------------------------

def test_render_report_output():
    results = [_api_passed("login_success"), _api_failed("login_failed")]
    comps = [
        LayerComparison(intent_name="login_success"),
        LayerComparison(intent_name="login_failed", divergences=[
            LayerDivergence(direction="intent_api", description="assertion failed: code=500"),
        ]),
    ]
    report = build_report(results, layer_comparisons=comps, title="mall login")
    output = render_report(report)
    assert "ATP Test Report" in output
    assert "login_success" in output
    assert "login_failed" in output
    assert "Level_A" in output


def test_render_report_no_comparisons():
    results = [_api_passed("test")]
    report = build_report(results)
    output = render_report(report)
    assert "ATP Test Report" in output


# ---------------------------------------------------------------------------
# quick_report
# ---------------------------------------------------------------------------

def test_quick_report():
    results = [_api_passed("a"), _api_passed("b")]
    output = quick_report(results)
    assert "ATP Test Report" in output
    assert "a" in output
    assert "b" in output
