"""Unit tests for api_step_runner — Sprint 1 Day 1."""
from __future__ import annotations

import os
from unittest import mock

import pytest
import requests

from app.models.api_test_models import (
    ApiRequest,
    Assertion,
    ExecutionResult,
    TestIntent,
)
from app.services.api_step_runner import (
    _build_url,
    _evaluate_assertions,
    _execute_api_request,
    _resolve_json_path,
    execute_api_test,
    execute_intents,
)


# ---------------------------------------------------------------------------
# _build_url
# ---------------------------------------------------------------------------

def test_build_url_simple():
    assert _build_url("http://localhost:8080", "/admin/login") == "http://localhost:8080/admin/login"


def test_build_url_trailing_slash():
    assert _build_url("http://localhost:8080/", "/admin/login") == "http://localhost:8080/admin/login"


def test_build_url_no_leading_slash():
    assert _build_url("http://localhost:8080", "admin/login") == "http://localhost:8080/admin/login"


# ---------------------------------------------------------------------------
# _resolve_json_path
# ---------------------------------------------------------------------------

def test_resolve_json_path_simple():
    data = {"code": 200, "message": "ok"}
    found, value = _resolve_json_path(data, "code")
    assert found is True
    assert value == 200


def test_resolve_json_path_nested():
    data = {"data": {"token": "abc123", "user": {"id": 1}}}
    found, value = _resolve_json_path(data, "data.token")
    assert found is True
    assert value == "abc123"


def test_resolve_json_path_not_found():
    data = {"code": 200}
    found, value = _resolve_json_path(data, "data.token")
    assert found is False
    assert value is None


def test_resolve_json_path_empty():
    found, value = _resolve_json_path({}, "")
    assert found is False


# ---------------------------------------------------------------------------
# _evaluate_assertions — status
# ---------------------------------------------------------------------------

def test_assert_status_pass():
    results = _evaluate_assertions(200, {}, [
        {"type": "status", "expected": 200},
    ])
    assert len(results) == 1
    assert results[0].passed is True


def test_assert_status_fail():
    results = _evaluate_assertions(500, {}, [
        {"type": "status", "expected": 200},
    ])
    assert len(results) == 1
    assert results[0].passed is False
    assert results[0].actual == 500


# ---------------------------------------------------------------------------
# _evaluate_assertions — json path
# ---------------------------------------------------------------------------

def test_assert_json_eq_pass():
    results = _evaluate_assertions(200, {"code": 200, "data": {"token": "abc"}}, [
        {"type": "json", "path": "code", "expected": 200},
    ])
    assert results[0].passed is True


def test_assert_json_eq_fail():
    results = _evaluate_assertions(200, {"code": 500}, [
        {"type": "json", "path": "code", "expected": 200},
    ])
    assert results[0].passed is False
    assert results[0].actual == 500


def test_assert_json_exists():
    results = _evaluate_assertions(200, {"data": {"token": "abc"}}, [
        {"type": "json", "path": "data.token", "operator": "exists"},
    ])
    assert results[0].passed is True


def test_assert_json_not_empty():
    results = _evaluate_assertions(200, {"data": {"token": "abc"}}, [
        {"type": "json", "path": "data.token", "operator": "not_empty"},
    ])
    assert results[0].passed is True


def test_assert_json_not_empty_fail():
    results = _evaluate_assertions(200, {"data": {"token": ""}}, [
        {"type": "json", "path": "data.token", "operator": "not_empty"},
    ])
    assert results[0].passed is False


def test_assert_json_contains():
    results = _evaluate_assertions(200, {"message": "用户名或密码错误"}, [
        {"type": "json", "path": "message", "operator": "contains", "expected": "密码错误"},
    ])
    assert results[0].passed is True


# ---------------------------------------------------------------------------
# execute_api_test — integration with mock
# ---------------------------------------------------------------------------

MOCK_RESPONSE_SUCCESS = mock.Mock(
    status_code=200,
    headers={"Content-Type": "application/json"},
)
MOCK_RESPONSE_SUCCESS.json.return_value = {
    "code": 200,
    "message": "操作成功",
    "data": {"token": "eyJtest123", "tokenHead": "Bearer "},
}


def test_execute_api_test_login_success():
    intent = TestIntent(
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

    with mock.patch("requests.request", return_value=MOCK_RESPONSE_SUCCESS) as mock_req:
        result = execute_api_test(intent, base_url="http://localhost:8080", skip_selftest=True)

    assert result.status == "passed"
    assert result.intent_name == "login_success"
    assert result.failure_layer is None
    assert len(result.assertions) == 3
    assert all(a.passed for a in result.assertions)
    mock_req.assert_called_once()


def test_execute_api_test_connection_refused():
    intent = TestIntent(
        name="login_failed",
        scenario="negative",
        api_request=ApiRequest(path="/admin/login", body={}),
        assertions=[Assertion(type="status", expected=200)],
    )

    with mock.patch("requests.request", side_effect=requests.ConnectionError("refused")):
        result = execute_api_test(intent, base_url="http://localhost:9999", skip_selftest=True)

    assert result.status == "failed"
    assert result.failure_layer == "network"


def test_execute_api_test_status_fail():
    fail_response = mock.Mock(
        status_code=500,
        headers={"Content-Type": "application/json"},
    )
    fail_response.json.return_value = {"code": 500, "message": "用户名或密码错误"}

    intent = TestIntent(
        name="login_failed_wrong_password",
        scenario="negative",
        api_request=ApiRequest(
            path="/admin/login",
            body={"username": "admin", "password": "wrong"},
        ),
        assertions=[Assertion(type="status", expected=200)],
    )

    with mock.patch("requests.request", return_value=fail_response):
        result = execute_api_test(intent, base_url="http://localhost:8080", skip_selftest=True)

    assert result.status == "failed"
    assert result.failure_layer == "business_rule"
    assert result.assertions[0].passed is False
    assert result.assertions[0].actual == 500


# ---------------------------------------------------------------------------
# execute_intents — batch
# ---------------------------------------------------------------------------

def test_execute_intents_batch():
    intent1 = TestIntent(
        name="test1",
        scenario="positive",
        api_request=ApiRequest(path="/api/test1", body={}),
        assertions=[Assertion(type="status", expected=200)],
    )
    intent2 = TestIntent(
        name="test2",
        scenario="positive",
        api_request=ApiRequest(path="/api/test2", body={}),
        assertions=[Assertion(type="status", expected=200)],
    )

    with mock.patch("requests.request", return_value=MOCK_RESPONSE_SUCCESS):
        results = execute_intents([intent1, intent2], base_url="http://localhost:8080", skip_selftest=True)

    assert len(results) == 2
    assert results[0].intent_name == "test1"
    assert results[1].intent_name == "test2"
    assert all(r.status == "passed" for r in results)


# ---------------------------------------------------------------------------
# DB Assertion tests
# ---------------------------------------------------------------------------

from app.models.api_test_models import DbAssertion
from app.services.api_step_runner import _execute_db_assertions, _get_sut_db_url


def test_get_sut_db_url_from_env():
    with mock.patch.dict(os.environ, {"ATP_SUT_DB_URL": "postgresql://localhost:5432/test"}):
        url = _get_sut_db_url()
        assert url == "postgresql://localhost:5432/test"


def test_get_sut_db_url_missing():
    with mock.patch.dict(os.environ, clear=True):
        with pytest.raises(RuntimeError, match="ATP_SUT_DB_URL"):
            _get_sut_db_url()


def test_db_assertion_exists():
    """Mock DB query returning rows → exists passes."""
    with mock.patch("app.services.api_step_runner.create_engine") as mock_engine:
        mock_conn = mock.MagicMock()
        mock_result = mock.MagicMock()
        mock_result.fetchall.return_value = [(1,)]
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = mock.Mock(return_value=mock_conn)
        mock_conn.__exit__ = mock.Mock(return_value=False)
        mock_engine.return_value.connect.return_value = mock_conn

        results, evidence = _execute_db_assertions(
            [{"sql": "SELECT 1 FROM sessions WHERE user_id=1", "expected": "exists"}],
            sut_db_url="sqlite://",
        )

        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].type == "db"
        assert len(evidence["queries"]) == 1
        assert evidence["queries"][0]["passed"] is True


def test_db_assertion_not_exists():
    """Mock DB query returning no rows → not_exists passes."""
    with mock.patch("app.services.api_step_runner.create_engine") as mock_engine:
        mock_conn = mock.MagicMock()
        mock_result = mock.MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = mock.Mock(return_value=mock_conn)
        mock_conn.__exit__ = mock.Mock(return_value=False)
        mock_engine.return_value.connect.return_value = mock_conn

        results, evidence = _execute_db_assertions(
            [{"sql": "SELECT 1 FROM sessions WHERE user_id=999", "expected": "not_exists"}],
            sut_db_url="sqlite://",
        )

        assert results[0].passed is True


def test_db_assertion_count_match():
    """Mock DB query returning count → expected_value matches."""
    with mock.patch("app.services.api_step_runner.create_engine") as mock_engine:
        mock_conn = mock.MagicMock()
        mock_result = mock.MagicMock()
        mock_result.fetchall.return_value = [(3,)]
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = mock.Mock(return_value=mock_conn)
        mock_conn.__exit__ = mock.Mock(return_value=False)
        mock_engine.return_value.connect.return_value = mock_conn

        results, evidence = _execute_db_assertions(
            [{"sql": "SELECT count(*) FROM users", "expected_value": 3}],
            sut_db_url="sqlite://",
        )

        assert results[0].passed is True
        assert results[0].actual == 3


def test_db_assertion_count_mismatch():
    """Mock DB query returning wrong count → fails."""
    with mock.patch("app.services.api_step_runner.create_engine") as mock_engine:
        mock_conn = mock.MagicMock()
        mock_result = mock.MagicMock()
        mock_result.fetchall.return_value = [(1,)]
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = mock.Mock(return_value=mock_conn)
        mock_conn.__exit__ = mock.Mock(return_value=False)
        mock_engine.return_value.connect.return_value = mock_conn

        results, evidence = _execute_db_assertions(
            [{"sql": "SELECT count(*) FROM users", "expected_value": 10}],
            sut_db_url="sqlite://",
        )

        assert results[0].passed is False
        assert results[0].actual == 1


def test_execute_api_test_with_db_set_but_no_url():
    """DB assertions defined but ATP_SUT_DB_URL not set → graceful fail."""
    intent = TestIntent(
        name="login_with_db",
        scenario="positive",
        api_request=ApiRequest(path="/admin/login", body={"username": "admin"}),
        assertions=[Assertion(type="status", expected=200)],
        db_assertions=[DbAssertion(sql="SELECT 1", expected="exists")],
    )

    with mock.patch("requests.request", return_value=MOCK_RESPONSE_SUCCESS):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = execute_api_test(intent, base_url="http://localhost:8080", skip_selftest=True)

    assert result.status == "failed"
    db_assertion = [a for a in result.assertions if a.type == "db"][0]
    assert db_assertion.passed is False
    assert "ATP_SUT_DB_URL" in str(db_assertion.actual)


# ---------------------------------------------------------------------------
# Fault Attribution tests — Sprint 1 Day 3
# ---------------------------------------------------------------------------

from app.services.api_step_runner import (
    _diagnose_connectivity,
    reset_selftest_cache,
    selftest,
)


def test_selftest_ok():
    reset_selftest_cache()
    with mock.patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        ok, msg = selftest()
        assert ok is True
        assert "OK" in msg


def test_selftest_fail_connection():
    reset_selftest_cache()
    with mock.patch("requests.get", side_effect=requests.ConnectionError("refused")):
        ok, msg = selftest()
        assert ok is False
        assert "FAIL" in msg


def test_selftest_cached():
    reset_selftest_cache()
    with mock.patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        selftest()   # first call → populates cache
        selftest()   # second call → uses cache
        assert mock_get.call_count == 1


def test_execute_api_test_platform_error():
    """Selftest fails → platform_error=true, SUT not tested."""
    reset_selftest_cache()
    intent = TestIntent(
        name="should_not_run",
        scenario="positive",
        api_request=ApiRequest(path="/test", body={}),
        assertions=[Assertion(type="status", expected=200)],
    )

    with mock.patch("app.services.api_step_runner.selftest", return_value=(False, "selftest FAIL")):
        result = execute_api_test(intent, base_url="http://localhost:8080", skip_selftest=False)

    assert result.status == "failed"
    assert result.failure_layer == "platform"
    assert result.platform_error is True


def test_execute_api_test_skips_selftest():
    """skip_selftest=True → no platform check (used by existing tests)."""
    intent = TestIntent(
        name="test",
        scenario="positive",
        api_request=ApiRequest(path="/test", body={}),
        assertions=[Assertion(type="status", expected=200)],
    )

    with mock.patch("requests.request", return_value=MOCK_RESPONSE_SUCCESS):
        result = execute_api_test(intent, base_url="http://localhost:8080", skip_selftest=True)

    assert result.status == "passed"
    assert result.platform_error is False


def test_diagnose_connectivity_localhost():
    report = _diagnose_connectivity("http://localhost:8080")
    assert "dns_ok" in report
    assert "tcp_connected" in report


def test_diagnose_connectivity_unreachable():
    report = _diagnose_connectivity("http://192.0.2.1:9999")
    assert report["dns_ok"] is True  # DNS resolves
    # TCP may or may not connect to TEST-NET-1, so don't assert tcp_connected


def test_execute_failure_layer_network():
    """Connection refused → failure_layer=network, platform_error=false."""
    intent = TestIntent(
        name="conn_refused",
        scenario="positive",
        api_request=ApiRequest(path="/test", body={}),
        assertions=[Assertion(type="status", expected=200)],
    )

    with mock.patch("requests.request", side_effect=requests.ConnectionError("refused")):
        result = execute_api_test(intent, base_url="http://localhost:9999", skip_selftest=True)

    assert result.status == "failed"
    assert result.failure_layer == "network"
    assert result.platform_error is False


def test_execute_failure_layer_business_rule():
    """Assertion fails → failure_layer=business_rule."""
    fail_response = mock.Mock(status_code=500, headers={"Content-Type": "application/json"})
    fail_response.json.return_value = {"code": 500}

    intent = TestIntent(
        name="wrong_pw",
        scenario="negative",
        api_request=ApiRequest(path="/login", body={}),
        assertions=[Assertion(type="status", expected=200)],
    )

    with mock.patch("requests.request", return_value=fail_response):
        result = execute_api_test(intent, base_url="http://localhost:8080", skip_selftest=True)

    assert result.status == "failed"
    assert result.failure_layer == "business_rule"
    assert result.platform_error is False


def test_execute_failure_layer_api_contract_gateway():
    """502 Bad Gateway → failure_layer=api_contract."""
    gw_response = mock.Mock(status_code=502, headers={"Content-Type": "text/html"})
    gw_response.json.return_value = {"_raw_body": "<html>502 Bad Gateway</html>"}

    intent = TestIntent(
        name="gw_error",
        scenario="positive",
        api_request=ApiRequest(path="/test", body={}),
        assertions=[Assertion(type="status", expected=200)],
    )

    with mock.patch("requests.request", return_value=gw_response):
        result = execute_api_test(intent, base_url="http://localhost:8080", skip_selftest=True)

    assert result.status == "failed"
    assert result.failure_layer == "api_contract"


def test_execute_connectivity_report_present():
    """connectivity_report is populated on successful runs too."""
    intent = TestIntent(
        name="test",
        scenario="positive",
        api_request=ApiRequest(path="/test", body={}),
        assertions=[Assertion(type="status", expected=200)],
    )

    with mock.patch("requests.request", return_value=MOCK_RESPONSE_SUCCESS):
        result = execute_api_test(intent, base_url="http://localhost:8080", skip_selftest=True)

    assert "dns_ok" in result.connectivity_report
