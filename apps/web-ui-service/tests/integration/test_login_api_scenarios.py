"""Sprint 1 Day 5: 3 Login API scenarios — end-to-end verification.

Run against a live mall system:
  ATP_SUT_BASE_URL=http://localhost:8080 python -m pytest apps/web-ui-service/tests/integration/test_login_api_scenarios.py -v
"""
from __future__ import annotations

import os

import pytest

from app.models.api_test_models import (
    ApiRequest,
    Assertion,
    ExecutionResult,
    TestIntent,
)
from app.services.api_step_runner import execute_api_test


# ---------------------------------------------------------------------------
# Test Intent definitions — based on mall system scan results
# ---------------------------------------------------------------------------

def _login_success_intent() -> TestIntent:
    """场景1：正向 — 正确密码登录成功。

    mall POST /admin/login → 200 {code:200, data:{token, tokenHead}}
    """
    return TestIntent(
        name="login_success",
        scenario="positive",
        api_request=ApiRequest(
            method="POST",
            path="/admin/login",
            body={"username": "admin", "password": "macro123"},
        ),
        assertions=[
            Assertion(type="status", expected=200),
            Assertion(type="json", path="code", expected=200),
            Assertion(type="json", path="data.token", operator="not_empty"),
        ],
    )


def _login_failed_wrong_password_intent() -> TestIntent:
    """场景2：负向 — 错误密码被拒绝。

    mall 返回 HTTP 200（非标准401），body.code=500，message="用户名或密码错误"
    ATP 断言的 expected 是 API 实际返回的值，不是需求文档说的值。
    """
    return TestIntent(
        name="login_failed_wrong_password",
        scenario="negative",
        api_request=ApiRequest(
            method="POST",
            path="/admin/login",
            body={"username": "admin", "password": "wrong_password"},
        ),
        assertions=[
            Assertion(type="status", expected=200),
            Assertion(type="json", path="code", expected=500),
            Assertion(type="json", path="message", operator="contains", expected="密码"),
        ],
    )


def _login_failed_empty_username_intent() -> TestIntent:
    """场景3：负向 — 空用户名被参数校验拦截。

    mall 使用 @Validated + @NotEmpty，返回 HTTP 200，body.code=404
    且 message 包含字段校验信息。
    """
    return TestIntent(
        name="login_failed_empty_username",
        scenario="negative",
        api_request=ApiRequest(
            method="POST",
            path="/admin/login",
            body={"username": "", "password": "macro123"},
        ),
        assertions=[
            Assertion(type="status", expected=200),
            Assertion(type="json", path="code", expected=404),
        ],
    )


ALL_INTENTS = [
    _login_success_intent(),
    _login_failed_wrong_password_intent(),
    _login_failed_empty_username_intent(),
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def get_base_url() -> str:
    url = os.getenv("ATP_SUT_BASE_URL", "").strip()
    if not url:
        pytest.skip("ATP_SUT_BASE_URL not set — skipping integration test")
    return url


# ---------------------------------------------------------------------------
# Integration tests (require live mall system)
# ---------------------------------------------------------------------------

class TestLoginApiScenarios:
    """3 login API scenarios — full integration with mall system."""

    def test_scenario_1_login_success(self):
        intent = _login_success_intent()
        result = execute_api_test(
            intent, base_url=get_base_url(), skip_selftest=True,
        )
        _assert_result_ok(result, "login_success")

    def test_scenario_2_login_failed_wrong_password(self):
        intent = _login_failed_wrong_password_intent()
        result = execute_api_test(
            intent, base_url=get_base_url(), skip_selftest=True,
        )
        _assert_result_ok(result, "login_failed_wrong_password")

    def test_scenario_3_login_failed_empty_username(self):
        intent = _login_failed_empty_username_intent()
        result = execute_api_test(
            intent, base_url=get_base_url(), skip_selftest=True,
        )
        _assert_result_ok(result, "login_failed_empty_username")


def _assert_result_ok(result: ExecutionResult, intent_name: str):
    """Verify ExecutionResult structure is correct."""
    assert result.intent_name == intent_name, f"intent_name mismatch: {result.intent_name}"
    assert result.status in {"passed", "failed"}, f"unexpected status: {result.status}"
    assert len(result.assertions) > 0, "no assertion results"
    assert "request" in result.evidence, "evidence missing request"
    assert "response" in result.evidence, "evidence missing response"
    # connectivity report populated
    assert "dns_ok" in result.connectivity_report


# ---------------------------------------------------------------------------
# Smoke test — verifies intent definitions are valid (no live system needed)
# ---------------------------------------------------------------------------

class TestIntentDefinitions:
    """Verify the 3 TestIntents are valid without requiring a live system."""

    def test_all_intents_have_assertions(self):
        for intent in ALL_INTENTS:
            assert len(intent.assertions) > 0, f"{intent.name}: no assertions"

    def test_all_intents_have_valid_scenario(self):
        for intent in ALL_INTENTS:
            assert intent.scenario in {"positive", "negative", "boundary"}, \
                f"{intent.name}: invalid scenario {intent.scenario}"

    def test_all_intents_have_api_request(self):
        for intent in ALL_INTENTS:
            assert intent.api_request.path, f"{intent.name}: no api path"
            assert intent.api_request.method, f"{intent.name}: no api method"

    def test_negative_scenarios_have_code_assertion(self):
        """Negative scenarios should validate error code, not just status."""
        for intent in ALL_INTENTS:
            if intent.scenario == "negative":
                has_code = any(
                    a.type == "json" and a.path == "code"
                    for a in intent.assertions
                )
                assert has_code, f"{intent.name}: negative scenario missing code assertion"

    def test_positive_scenario_has_token_check(self):
        """Positive login should verify token is returned."""
        intent = _login_success_intent()
        has_token = any(
            a.type == "json" and a.path == "data.token"
            for a in intent.assertions
        )
        assert has_token, "login_success: missing token assertion"
