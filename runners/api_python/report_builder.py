"""Report Builder — Sprint 2 Day 9.

Builds the final TestReport by combining:
  - ExecutionResults (API + DB assertions)
  - LayerComparisons (intent vs API vs UI)
  - Test Reliability Gate findings

Outputs structured TestReport model + CLI-formatted text.
"""
from __future__ import annotations

from typing import Any

from app.models.api_test_models import ExecutionResult, TestReport
from runners.api_python.layer_comparator import LayerComparison


# ---------------------------------------------------------------------------
# Build report
# ---------------------------------------------------------------------------

def build_report(
    api_results: list[ExecutionResult],
    layer_comparisons: list[LayerComparison] | None = None,
    title: str = "ATP Test Report",
) -> TestReport:
    """Build a TestReport from execution results and layer comparisons.

    Args:
        api_results: List of API execution results.
        layer_comparisons: Optional layer comparison results.
        title: Report title.

    Returns:
        TestReport model.
    """
    comparisons = layer_comparisons or []

    # Summary
    total = len(api_results)
    passed = sum(1 for r in api_results if r.status == "passed")
    failed = total - passed
    platform_errors = sum(1 for r in api_results if r.platform_error)

    summary_parts = [f"{title}: {total} scenarios"]
    if passed:
        summary_parts.append(f"{passed} passed")
    if failed:
        summary_parts.append(f"{failed} failed")
    if platform_errors:
        summary_parts.append(f"{platform_errors} platform errors")

    # Findings
    findings: list[str] = []

    # Network/platform issues
    for r in api_results:
        if r.failure_layer == "network":
            findings.append(f"网络不可达: {r.intent_name} — {r.evidence.get('error', 'unknown')}")
        if r.platform_error:
            findings.append(f"平台异常: {r.intent_name} — {r.platform_error_details}")

    # Divergences
    for comp in comparisons:
        for d in comp.divergences:
            findings.append(
                f"[{d.direction}] {comp.intent_name}: {d.description}"
            )

    # Confidence level
    if platform_errors:
        confidence = "Level_C"  # Platform issues → results untrustworthy
    elif any(r.failure_layer == "network" for r in api_results):
        confidence = "Level_B"  # Network issues → results questionable
    else:
        confidence = "Level_A"  # Platform healthy, network ok → results trustworthy

    return TestReport(
        summary=", ".join(summary_parts),
        results=api_results,
        calibrations=[_comparison_to_dict(c) for c in comparisons],
        findings=findings,
        confidence_level=confidence,
    )


def _comparison_to_dict(comp: LayerComparison) -> dict[str, Any]:
    return {
        "intent_name": comp.intent_name,
        "has_divergences": comp.has_divergences,
        "intent_api_divergences": len(comp.intent_api_divergences),
        "intent_ui_divergences": len(comp.intent_ui_divergences),
        "divergences": [
            {
                "direction": d.direction,
                "description": d.description,
                "possible_causes": d.possible_causes,
            }
            for d in comp.divergences
        ],
    }


# ---------------------------------------------------------------------------
# CLI renderer
# ---------------------------------------------------------------------------

_SEPARATOR = "─" * 60


def render_report(report: TestReport) -> str:
    """Render a TestReport as formatted CLI text."""
    lines: list[str] = []

    lines.append("")
    lines.append("╔" + "═" * 58 + "╗")
    lines.append("║  ATP Test Report" + " " * 42 + "║")
    lines.append("╚" + "═" * 58 + "╝")
    lines.append("")

    # Summary
    lines.append(f"  Summary: {report.summary}")
    lines.append(f"  Confidence: {report.confidence_level}")
    lines.append("")

    # Results table
    if report.results:
        lines.append(_SEPARATOR)
        lines.append("  API Execution Results")
        lines.append(_SEPARATOR)
        for r in report.results:
            icon = "✅" if r.status == "passed" else "❌"
            platform = " ⚠️PLATFORM" if r.platform_error else ""
            network = " 🌐NETWORK" if r.failure_layer == "network" else ""
            lines.append(f"  {icon} {r.intent_name}: {r.status}{platform}{network}")
            if r.platform_error:
                lines.append(f"     └─ {r.platform_error_details}")
            if r.failure_layer and r.failure_layer not in ("business_rule",):
                lines.append(f"     └─ failure_layer={r.failure_layer}, evidence={r.evidence.get('error', '')}")
            for a in r.assertions:
                icon_a = "  ✓" if a.passed else "  ✗"
                lines.append(f"    {icon_a} {a.type} {a.path or ''}: expected={a.expected}, actual={a.actual}")
        lines.append("")

    # Layer comparisons
    if report.calibrations:
        lines.append(_SEPARATOR)
        lines.append("  Layer Comparisons (intent vs API vs UI)")
        lines.append(_SEPARATOR)
        for cal in report.calibrations:
            if not isinstance(cal, dict):
                continue
            if not cal.get("has_divergences"):
                lines.append(f"  ✅ {cal['intent_name']}: aligned")
                continue
            lines.append(f"  ⚠️  {cal['intent_name']}: {cal['intent_api_divergences']} API + {cal['intent_ui_divergences']} UI divergences")
            for d in cal.get("divergences", []):
                if not isinstance(d, dict):
                    continue
                lines.append(f"     [{d.get('direction', '')}] {d.get('description', '')}")
                causes = d.get("possible_causes", [])
                for c in causes[:2]:  # Show first 2 causes
                    lines.append(f"       {c}")
        lines.append("")

    # Findings
    if report.findings:
        lines.append(_SEPARATOR)
        lines.append("  Findings")
        lines.append(_SEPARATOR)
        for f in report.findings:
            lines.append(f"  • {f}")
        lines.append("")

    lines.append(_SEPARATOR)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Quick report from just API results (no layer comparisons yet)
# ---------------------------------------------------------------------------

def quick_report(
    api_results: list[ExecutionResult],
    title: str = "ATP Test Report",
) -> str:
    """Quick CLI report from API results only (no layer comparisons).

    Useful for Sprint 1 / early development.
    """
    report = build_report(api_results, title=title)
    return render_report(report)
