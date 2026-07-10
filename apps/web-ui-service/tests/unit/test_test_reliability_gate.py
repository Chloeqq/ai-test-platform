"""Unit tests for Test Reliability Gate — Sprint 1 Day 4."""
from __future__ import annotations

from app.models.api_test_models import Assertion, TestIntent, ApiRequest
from app.services.test_reliability_gate import (
    GateResult,
    check_reliability,
    _rule_ai_hallucination,
    _rule_false_positive_risk,
    _rule_missing_assertions,
    _rule_weak_assertions,
)


# ---------------------------------------------------------------------------
# Unit: individual rules
# ---------------------------------------------------------------------------

def test_rule_missing_assertions_empty():
    reasons = _rule_missing_assertions([])
    assert len(reasons) == 1
    assert "断言缺失" in reasons[0]


def test_rule_missing_assertions_ok():
    reasons = _rule_missing_assertions([{"type": "status", "expected": 200}])
    assert len(reasons) == 0


def test_rule_weak_assertions_negative_with_only_url():
    reasons = _rule_weak_assertions("negative", [
        {"type": "status", "expected": 200},
    ])
    assert len(reasons) == 1
    assert "弱断言风险" in reasons[0]


def test_rule_weak_assertions_negative_with_json_path():
    reasons = _rule_weak_assertions("negative", [
        {"type": "status", "expected": 200},
        {"type": "json", "path": "code", "expected": 500},
    ])
    assert len(reasons) == 0


def test_rule_weak_assertions_positive_ignored():
    """Positive scenarios don't trigger weak assertion check."""
    reasons = _rule_weak_assertions("positive", [{"type": "status", "expected": 200}])
    assert len(reasons) == 0


def test_rule_ai_hallucination_depends_on_business():
    reasons = _rule_ai_hallucination([
        {"type": "json", "path": "code", "expected": "登录成功或提示用户不存在（取决于业务）"},
    ])
    assert len(reasons) == 1
    assert "AI幻觉风险" in reasons[0]
    assert "取决于业务" in reasons[0]


def test_rule_ai_hallucination_guessed_message():
    reasons = _rule_ai_hallucination([
        {"type": "json", "path": "message", "expected": "请输入账号"},
    ])
    assert len(reasons) == 1
    assert "AI幻觉风险" in reasons[0]
    assert "推测文案" in reasons[0]


def test_rule_ai_hallucination_clean():
    reasons = _rule_ai_hallucination([
        {"type": "json", "path": "code", "expected": 500},
    ])
    assert len(reasons) == 0


def test_rule_false_positive_negative_no_json():
    reasons = _rule_false_positive_risk("negative", [
        {"type": "status", "expected": 200},
    ])
    assert len(reasons) == 1
    assert "假通过风险" in reasons[0]


def test_rule_false_positive_negative_with_json():
    reasons = _rule_false_positive_risk("negative", [
        {"type": "json", "path": "code", "expected": 500},
    ])
    assert len(reasons) == 0


def test_rule_false_positive_positive_ignored():
    reasons = _rule_false_positive_risk("positive", [{"type": "status", "expected": 200}])
    assert len(reasons) == 0


# ---------------------------------------------------------------------------
# Integration: check_reliability with TestIntent model
# ---------------------------------------------------------------------------

def test_gate_pass_trusted_intent():
    intent = TestIntent(
        name="login_success",
        scenario="positive",
        api_request=ApiRequest(path="/login", body={}),
        assertions=[
            Assertion(type="status", expected=200),
            Assertion(type="json", path="data.token", operator="not_empty"),
        ],
    )
    result = check_reliability(intent)
    assert result.verdict == "PASS"
    assert result.blocked is False


def test_gate_reject_missing_assertions():
    intent = TestIntent(
        name="login_no_assert",
        scenario="positive",
        api_request=ApiRequest(path="/login", body={}),
        assertions=[],
    )
    result = check_reliability(intent)
    assert result.verdict == "REJECT"
    assert result.blocked is True
    assert any("断言缺失" in r for r in result.reasons)


def test_gate_reject_ai_hallucination():
    intent = TestIntent(
        name="login_boundary",
        scenario="boundary",
        api_request=ApiRequest(path="/login", body={}),
        assertions=[
            Assertion(type="assert_text", expected="用户名长度至少6位"),
        ],
    )
    result = check_reliability(intent)
    assert result.verdict == "REJECT"
    assert any("AI幻觉" in r for r in result.reasons)


def test_gate_review_weak_negative():
    intent = TestIntent(
        name="login_failed",
        scenario="negative",
        api_request=ApiRequest(path="/login", body={}),
        assertions=[
            Assertion(type="status", expected=200),
        ],
    )
    result = check_reliability(intent)
    assert result.verdict == "REVIEW"
    assert any("弱断言" in r or "假通过" in r for r in result.reasons)


def test_gate_with_dict_input():
    """Gate accepts dict input too (backward compat)."""
    result = check_reliability({
        "name": "test",
        "scenario": "negative",
        "assertions": [{"type": "status", "expected": 200}],
    })
    assert result.verdict == "REVIEW"


# ---------------------------------------------------------------------------
# Historical data validation: the 24-case audit baseline
# ---------------------------------------------------------------------------

def test_historical_24_cases_baseline():
    """Verify the gate catches the same patterns found in the audit.

    The real audit found:
      - 16 REJECT (false pass risk)
      - 7 PASS (trusted)
      - 1 REVIEW (needs human)

    We validate representative cases here.
    """
    # Case from audit: zero assertions → REJECT
    zero_assert = TestIntent(
        name="首次登录成功",
        scenario="positive",
        api_request=ApiRequest(path="/admin/login", body={"username": "admin", "password": "macro123"}),
        assertions=[],
    )
    r = check_reliability(zero_assert)
    assert r.verdict == "REJECT"

    # Case from audit: negative + AI hallucination → REJECT
    hallucinated = TestIntent(
        name="用户名长度小于6位",
        scenario="negative",
        api_request=ApiRequest(path="/admin/login", body={}),
        assertions=[
            Assertion(type="assert_text", expected="用户名长度至少6位"),
        ],
    )
    r = check_reliability(hallucinated)
    assert r.verdict == "REJECT"

    # Case from audit: negative + json path → PASS
    trusted_negative = TestIntent(
        name="错误密码登录",
        scenario="negative",
        api_request=ApiRequest(path="/admin/login", body={"username": "admin", "password": "wrong"}),
        assertions=[
            Assertion(type="status", expected=200),
            Assertion(type="json", path="code", expected=500),
            Assertion(type="json", path="message", operator="contains", expected="用户名或密码错误"),
        ],
    )
    r = check_reliability(trusted_negative)
    assert r.verdict == "PASS"

    # Case from audit: positive with full assertions → PASS
    trusted_positive = TestIntent(
        name="正确密码登录成功",
        scenario="positive",
        api_request=ApiRequest(path="/admin/login", body={"username": "admin", "password": "macro123"}),
        assertions=[
            Assertion(type="status", expected=200),
            Assertion(type="json", path="code", expected=200),
            Assertion(type="json", path="data.token", operator="not_empty"),
        ],
    )
    r = check_reliability(trusted_positive)
    assert r.verdict == "PASS"


def test_gate_result_dataclass():
    """GateResult dataclass properties."""
    r = GateResult(verdict="PASS")
    assert r.blocked is False
    assert r.needs_review is False

    r = GateResult(verdict="REVIEW", reasons=["something"])
    assert r.blocked is False
    assert r.needs_review is True

    r = GateResult(verdict="REJECT", reasons=["fatal"])
    assert r.blocked is True
    assert r.needs_review is True
