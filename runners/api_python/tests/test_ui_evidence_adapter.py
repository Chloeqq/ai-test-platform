"""Unit tests for UIEvidence Adapter — Sprint 2 Day 7."""
from __future__ import annotations

from app.models.api_test_models import UIEvidence
from runners.api_python.ui_evidence_adapter import (
    import_ui_results,
    match_to_intents,
    parse_generic_result,
    parse_playwright_result,
)


# ---------------------------------------------------------------------------
# parse_playwright_result
# ---------------------------------------------------------------------------

PLAYWRIGHT_INPUT = {
    "case_id": "login_failed_001",
    "title": "密码可见性切换",
    "status": "passed",
    "assertions": [
        {
            "type": "assert_text",
            "target": "login-submit-btn",
            "expected": "请输入账号",
            "actual": "登录",
        },
    ],
}


def test_parse_playwright_basic():
    result = parse_playwright_result(PLAYWRIGHT_INPUT)
    assert result is not None
    assert result.case_id == "login_failed_001"
    assert result.status == "passed"
    assert len(result.assertions) == 1
    assert result.assertions[0].type == "assert_text"
    assert result.assertions[0].target == "login-submit-btn"
    assert result.assertions[0].expected == "请输入账号"
    assert result.assertions[0].actual == "登录"


def test_parse_playwright_no_assertions():
    result = parse_playwright_result({
        "case_id": "test001",
        "status": "passed",
    })
    assert result is not None
    assert len(result.assertions) == 0


def test_parse_playwright_empty_input():
    result = parse_playwright_result({})
    assert result is None


def test_parse_playwright_intent_name_fallback():
    """If no intent_name, fall back to case_id."""
    result = parse_playwright_result({
        "case_id": "login_001",
        "status": "failed",
    })
    assert result is not None
    assert result.intent_name == "login_001"


# ---------------------------------------------------------------------------
# parse_generic_result
# ---------------------------------------------------------------------------

def test_parse_generic_basic():
    result = parse_generic_result({
        "case_id": "login_failed",
        "status": "failed",
        "assertion_type": "assert_text",
        "assertion_target": "error-toast",
        "expected_value": "密码不正确",
    })
    assert result is not None
    assert result.status == "failed"
    assert len(result.assertions) == 1
    assert result.assertions[0].expected == "密码不正确"


def test_parse_generic_no_assertion():
    result = parse_generic_result({
        "case_id": "test001",
        "status": "passed",
    })
    assert result is not None
    assert len(result.assertions) == 0


def test_parse_generic_empty():
    assert parse_generic_result({}) is None


# ---------------------------------------------------------------------------
# import_ui_results
# ---------------------------------------------------------------------------

def test_import_playwright_format():
    raw = [
        {"case_id": "a", "status": "passed"},
        {"case_id": "b", "status": "failed", "assertions": [
            {"type": "assert_url", "target": "", "expected": "/home", "actual": "/login"},
        ]},
        {},  # invalid → filtered
        "not_a_dict",  # invalid → filtered
    ]
    results = import_ui_results(raw, format="playwright")
    assert len(results) == 2
    assert results[0].case_id == "a"
    assert results[1].case_id == "b"
    assert len(results[1].assertions) == 1


def test_import_generic_format():
    raw = [
        {"case_id": "test1", "status": "passed", "assertion_type": "assert_visible", "assertion_target": "dashboard"},
    ]
    results = import_ui_results(raw, format="generic")
    assert len(results) == 1
    assert results[0].case_id == "test1"


# ---------------------------------------------------------------------------
# match_to_intents
# ---------------------------------------------------------------------------

def test_match_exact():
    evidence = [
        UIEvidence(case_id="c1", intent_name="login_success", status="passed"),
        UIEvidence(case_id="c2", intent_name="login_failed", status="failed"),
    ]
    matched = match_to_intents(evidence, ["login_success", "login_failed", "missing_intent"])
    assert matched["login_success"] is not None
    assert matched["login_failed"] is not None
    assert matched["missing_intent"] is None


def test_match_partial():
    evidence = [UIEvidence(case_id="c1", intent_name="login_success", status="passed")]
    matched = match_to_intents(evidence, ["login_success", "login_failed"])
    assert matched["login_success"] is not None
    assert matched["login_failed"] is None


def test_match_empty():
    matched = match_to_intents([], ["test"])
    assert matched["test"] is None
