"""UIEvidence Adapter — Sprint 2 Day 7.

Accepts external UI test results (Playwright JSON / generic format),
normalizes them into UIEvidence models, and matches to TestIntent
by intent_name for the Layer Comparator.

ATP does NOT execute UI tests — it only judges their trustworthiness.
"""
from __future__ import annotations

from typing import Any

from app.models.api_test_models import UIEvidence, UIAssertion


# ---------------------------------------------------------------------------
# Playwright JSON format parser
# ---------------------------------------------------------------------------

def parse_playwright_result(raw: dict[str, Any]) -> UIEvidence | None:
    """Parse a single Playwright test result into UIEvidence.

    Expected input format (Playwright JSON reporter output):
    {
      "case_id": "login_failed_001",
      "title": "password visibility toggle",
      "status": "passed",       // or "failed"
      "assertions": [
        {
          "type": "assert_text",
          "target": "login-submit-btn",
          "expected": "password",
          "actual": "password"
        }
      ]
    }

    Returns None if the input cannot be parsed.
    """
    case_id = str(raw.get("case_id") or raw.get("title") or "")
    if not case_id:
        return None

    intent_name = str(raw.get("intent_name") or raw.get("case_id") or "")
    status = str(raw.get("status", "unknown")).lower()

    raw_assertions = raw.get("assertions")
    if isinstance(raw_assertions, list):
        assertions = [
            UIAssertion(
                type=str(a.get("type", "")),
                target=str(a.get("target", "")),
                expected=str(a.get("expected", "")),
                actual=str(a.get("actual", "")),
            )
            for a in raw_assertions
            if isinstance(a, dict)
        ]
    else:
        assertions = []

    return UIEvidence(
        case_id=case_id,
        intent_name=intent_name,
        status=status,
        assertions=assertions,
    )


# ---------------------------------------------------------------------------
# Generic format parser
# ---------------------------------------------------------------------------

def parse_generic_result(raw: dict[str, Any]) -> UIEvidence | None:
    """Parse a generic/minimal UI test result.

    Minimal format:
    {
      "case_id": "login_failed",
      "status": "passed",
      "assertion_type": "assert_text",
      "assertion_target": "error-toast",
      "expected_value": "密码不正确"
    }
    """
    case_id = str(raw.get("case_id", ""))
    if not case_id:
        return None

    intent_name = str(raw.get("intent_name") or raw.get("case_id", ""))
    status = str(raw.get("status", "unknown")).lower()

    assertion_type = str(raw.get("assertion_type", ""))
    if assertion_type:
        assertions = [
            UIAssertion(
                type=assertion_type,
                target=str(raw.get("assertion_target", "")),
                expected=str(raw.get("expected_value", "")),
                actual=str(raw.get("actual_value", "")),
            )
        ]
    else:
        assertions = []

    return UIEvidence(
        case_id=case_id,
        intent_name=intent_name,
        status=status,
        assertions=assertions,
    )


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------

def import_ui_results(
    raw_results: list[dict[str, Any]],
    *,
    format: str = "playwright",
) -> list[UIEvidence]:
    """Import a list of UI test results and return normalized UIEvidence.

    Args:
        raw_results: List of raw result dicts.
        format: "playwright" | "generic"

    Returns:
        List of UIEvidence objects (invalid entries filtered out).
    """
    parser = parse_playwright_result if format == "playwright" else parse_generic_result
    results: list[UIEvidence] = []
    for raw in raw_results:
        if not isinstance(raw, dict):
            continue
        evidence = parser(raw)
        if evidence is not None:
            results.append(evidence)
    return results


# ---------------------------------------------------------------------------
# Match to TestIntent
# ---------------------------------------------------------------------------

def match_to_intents(
    ui_evidence: list[UIEvidence],
    intent_names: list[str],
) -> dict[str, UIEvidence | None]:
    """Match UIEvidence to TestIntent names.

    Returns a dict mapping intent_name → UIEvidence (or None if no match).
    """
    evidence_by_name: dict[str, UIEvidence] = {
        e.intent_name: e for e in ui_evidence if e.intent_name
    }
    return {name: evidence_by_name.get(name) for name in intent_names}
