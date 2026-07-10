"""API Step Runner — Sprint 1 Day 1-3.

Executes a TestIntent with four-layer fault attribution:

  Layer A: Platform  — selftest (httpbin.org) verifies HTTP client health
  Layer B: Network   — DNS / TCP / TLS connectivity diagnostics
  Layer C: Contract  — HTTP response received, JSON parse check
  Layer D: Business  — assertion evaluation + DB verification

All layers contribute to ExecutionResult.failure_layer and
platform_error flag. No FastAPI dependency.
"""
from __future__ import annotations

import json
import os
import socket
import time
from typing import Any

import requests
from sqlalchemy import create_engine, text

from app.models.api_test_models import (
    AssertionResult,
    ExecutionResult,
    TestIntent,
)
from app.services.test_reliability_gate import check_reliability
from shared_backend.type_utils import dict_value, str_value


# ---------------------------------------------------------------------------
# Layer A: Platform Selftest
# ---------------------------------------------------------------------------

_SELFTEST_URL = os.getenv("ATP_SELFTEST_URL", "https://httpbin.org/get").strip()
_SELFTEST_CACHE: tuple[bool, str] | None = None


def selftest(timeout: int = 10) -> tuple[bool, str]:
    """Verify the HTTP client is healthy by pinging a known-good endpoint.

    Returns (ok, details). Result is cached per process lifetime;
    pass use_cache=False to force re-check.
    """
    global _SELFTEST_CACHE
    if _SELFTEST_CACHE is not None:
        return _SELFTEST_CACHE

    try:
        resp = requests.get(_SELFTEST_URL, timeout=timeout)
        if resp.status_code == 200:
            _SELFTEST_CACHE = (True, f"selftest OK: {_SELFTEST_URL} responded 200")
        else:
            _SELFTEST_CACHE = (False, f"selftest FAIL: {_SELFTEST_URL} returned {resp.status_code}")
    except requests.ConnectionError as exc:
        _SELFTEST_CACHE = (False, f"selftest FAIL: cannot reach {_SELFTEST_URL} — {exc}")
    except requests.Timeout:
        _SELFTEST_CACHE = (False, f"selftest FAIL: {_SELFTEST_URL} timed out after {timeout}s")
    except requests.RequestException as exc:
        _SELFTEST_CACHE = (False, f"selftest FAIL: {exc}")

    return _SELFTEST_CACHE


def reset_selftest_cache() -> None:
    """Clear the cached selftest result (for testing)."""
    global _SELFTEST_CACHE
    _SELFTEST_CACHE = None


# ---------------------------------------------------------------------------
# Layer B: Connectivity diagnostics
# ---------------------------------------------------------------------------

def _diagnose_connectivity(base_url: str) -> dict[str, Any]:
    """Probe DNS resolution and TCP reachability for the SUT base URL.

    Returns a dict suitable for ExecutionResult.connectivity_report.
    """
    report: dict[str, Any] = {"dns_ok": False, "tcp_connected": False, "tls_ok": None}
    try:
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        host = parsed.hostname or base_url
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        # DNS
        start = time.monotonic()
        addrs = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        dns_ms = (time.monotonic() - start) * 1000
        report["dns_ok"] = True
        report["dns_ms"] = round(dns_ms, 1)

        # TCP
        for _, _, _, _, sockaddr in addrs:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            start = time.monotonic()
            try:
                sock.connect(sockaddr)
                tcp_ms = (time.monotonic() - start) * 1000
                report["tcp_connected"] = True
                report["tcp_ms"] = round(tcp_ms, 1)
            except (socket.timeout, OSError):
                pass
            finally:
                sock.close()
            if report["tcp_connected"]:
                break
    except Exception as exc:
        report["error"] = str(exc)

    return report


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# HTTP request execution
# ---------------------------------------------------------------------------

def _build_url(base_url: str, path: str) -> str:
    """Build full URL from base_url and path, avoiding double slashes."""
    base = base_url.rstrip("/")
    p = path if path.startswith("/") else f"/{path}"
    return f"{base}{p}"


def _execute_api_request(
    intent: TestIntent,
    base_url: str,
    timeout: int = 30,
) -> tuple[int, Any, dict[str, Any], float]:
    """Send HTTP request and return (status_code, response_body, evidence, duration_ms).

    Returns response_body as parsed JSON dict if Content-Type is json,
    otherwise returns the raw text as a dict keyed by "_raw_body".

    Raises requests.RequestException on connectivity/protocol errors;
    caller is responsible for catching and converting to ExecutionResult.
    """
    url = _build_url(base_url, intent.api_request.path)
    headers = {**intent.api_request.headers}
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"

    evidence: dict[str, Any] = {
        "request": {
            "method": intent.api_request.method,
            "url": url,
            "headers": headers,
            "body": intent.api_request.body,
        },
    }

    start = time.monotonic()
    response = requests.request(
        method=intent.api_request.method.upper(),
        url=url,
        headers=headers,
        json=intent.api_request.body,
        timeout=timeout,
    )
    duration_ms = (time.monotonic() - start) * 1000

    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        body = {"_raw_body": response.text}

    evidence["response"] = {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": body,
        "duration_ms": round(duration_ms, 1),
    }

    return response.status_code, body, evidence, duration_ms


# ---------------------------------------------------------------------------
# Assertion evaluation
# ---------------------------------------------------------------------------

def _resolve_json_path(data: dict[str, Any], path: str) -> tuple[bool, Any]:
    """Resolve a dot-separated JSON path against a dict.

    Returns (found, value). Supports nested keys like "data.token".
    """
    if not path:
        return False, None
    current: Any = data
    for key in path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return False, None
    return True, current


def _field(obj: Any, name: str, default: Any = None) -> Any:
    """Extract a field value from either a dict or a Pydantic model."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _evaluate_assertions(
    response_status: int,
    response_body: dict[str, Any],
    assertions: list[Any],
) -> list[AssertionResult]:
    """Evaluate all assertions against the response. Returns per-assertion results."""
    results: list[AssertionResult] = []
    for a in assertions:
        atype = str_value(_field(a, "type", ""))
        apath = str_value(_field(a, "path", "")) or None
        expected = _field(a, "expected")
        operator = str_value(_field(a, "operator", "eq"))

        actual: Any = None
        passed = False

        if atype == "status":
            actual = response_status
            passed = (actual == expected)

        elif atype == "json":
            found, value = _resolve_json_path(response_body, apath or "")
            actual = value if found else "<not found>"
            if not found:
                passed = False
            elif operator == "exists":
                passed = True
            elif operator == "not_empty":
                passed = bool(value)
            elif operator == "contains":
                passed = str(expected or "") in str(value) if expected is not None else False
            else:  # "eq"
                passed = (value == expected)

        results.append(AssertionResult(
            type=atype,
            path=apath,
            expected=expected,
            actual=actual,
            passed=passed,
        ))

    return results


# ---------------------------------------------------------------------------
# DB assertion execution
# ---------------------------------------------------------------------------

def _get_sut_db_url() -> str:
    """Return the SUT (System Under Test) database URL.

    Reads ATP_SUT_DB_URL from environment. Raises RuntimeError if not set.
    """
    url = os.getenv("ATP_SUT_DB_URL", "").strip()
    if not url:
        raise RuntimeError(
            "ATP_SUT_DB_URL environment variable is not set. "
            "DB assertions require a connection to the system under test database."
        )
    return url


def _execute_db_assertions(
    db_assertions: list[Any],
    sut_db_url: str,
) -> tuple[list[AssertionResult], dict[str, Any]]:
    """Execute SQL-based assertions against the SUT database.

    Returns (assertion_results, db_evidence).
    Each assertion is a dict or DbAssertion with sql + expected.
    """
    engine = create_engine(sut_db_url, future=True)
    results: list[AssertionResult] = []
    db_evidence: dict[str, Any] = {"queries": []}

    try:
        with engine.connect() as conn:
            for da in db_assertions:
                sql = str_value(_field(da, "sql", ""))
                expected_type = str_value(_field(da, "expected", ""))
                expected_value = _field(da, "expected_value")

                query_evidence: dict[str, Any] = {"sql": sql}
                passed = False
                actual: Any = None

                try:
                    result = conn.execute(text(sql))
                    rows = result.fetchall()
                    query_evidence["row_count"] = len(rows)

                    if expected_type == "exists":
                        passed = len(rows) > 0
                        actual = f"{len(rows)} rows"
                    elif expected_type == "not_exists":
                        passed = len(rows) == 0
                        actual = f"{len(rows)} rows"
                    elif expected_value is not None:
                        # count(*) or scalar query
                        actual = rows[0][0] if rows and rows[0] else None
                        passed = actual == expected_value
                    else:
                        passed = len(rows) > 0
                        actual = f"{len(rows)} rows"
                except Exception as exc:
                    passed = False
                    actual = str(exc)
                    query_evidence["error"] = str(exc)

                query_evidence["passed"] = passed
                query_evidence["actual"] = str(actual)
                db_evidence["queries"].append(query_evidence)

                results.append(AssertionResult(
                    type="db",
                    expected=str(expected_type or expected_value),
                    actual=actual,
                    passed=passed,
                ))

        return results, db_evidence
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def execute_api_test(
    intent: TestIntent,
    *,
    base_url: str,
    timeout: int = 30,
    sut_db_url: str | None = None,
    skip_selftest: bool = False,
) -> ExecutionResult:
    """Execute a single TestIntent with four-layer fault attribution.

    Args:
        intent: The TestIntent to execute.
        base_url: Base URL of the system under test.
        timeout: HTTP request timeout in seconds.
        sut_db_url: Optional SUT DB URL (falls back to ATP_SUT_DB_URL env var).
        skip_selftest: If True, skip Layer A platform selftest (for testing).

    Returns:
        ExecutionResult with status, assertions, failure_layer, platform_error,
        connectivity_report, and evidence.
    """
    result = ExecutionResult(intent_name=intent.name)

    # =================================================================
    # Test Reliability Gate — pre-execution quality check
    # =================================================================
    gate_result = check_reliability(intent)
    if gate_result.blocked:
        result.status = "failed"
        result.failure_layer = "business_rule"
        result.platform_error = False
        result.evidence = {
            "gate_verdict": gate_result.verdict,
            "gate_reasons": gate_result.reasons,
        }
        result.assertions = [AssertionResult(
            type="reliability_gate",
            expected="trusted test intent",
            actual=f"REJECT: {'; '.join(gate_result.reasons)}",
            passed=False,
        )]
        return result

    # =================================================================
    # Layer A: Platform — verify HTTP client is healthy
    # =================================================================
    if not skip_selftest:
        platform_ok, platform_msg = selftest(timeout=min(10, timeout))
        if not platform_ok:
            result.status = "failed"
            result.failure_layer = "platform"
            result.platform_error = True
            result.platform_error_details = platform_msg
            result.evidence = {"selftest": platform_msg}
            return result

    # =================================================================
    # Layer B: Network — connectivity diagnostics
    # =================================================================
    connectivity_report = _diagnose_connectivity(base_url)
    result.connectivity_report = connectivity_report

    # =================================================================
    # Layer C: API Contract — HTTP request / response
    # =================================================================
    try:
        response_status, response_body, evidence, duration_ms = _execute_api_request(
            intent, base_url=base_url, timeout=timeout,
        )
    except requests.ConnectionError:
        result.status = "failed"
        result.failure_layer = "network"
        result.platform_error = False
        result.evidence = {"error": "connection_refused", "base_url": base_url}
        return result
    except requests.Timeout:
        result.status = "failed"
        result.failure_layer = "network"
        result.platform_error = False
        result.evidence = {"error": "timeout", "base_url": base_url}
        return result
    except requests.RequestException as exc:
        result.status = "failed"
        result.failure_layer = "network"
        result.platform_error = False
        result.evidence = {"error": str(exc), "base_url": base_url}
        return result

    # Validate protocol-level response quality
    if evidence.get("response", {}).get("status_code", 0) in {502, 503, 504}:
        result.status = "failed"
        result.failure_layer = "api_contract"
        result.platform_error = False
        result.evidence = evidence
        result.assertions = [AssertionResult(
            type="protocol",
            expected="valid HTTP response",
            actual=f"gateway error {response_status}",
            passed=False,
        )]
        return result

    if isinstance(response_body, dict) and "_raw_body" in response_body:
        # Response body was not JSON — protocol layer issue
        result.status = "failed"
        result.failure_layer = "api_contract"
        result.platform_error = False
        result.evidence = evidence
        result.assertions = [AssertionResult(
            type="protocol",
            expected="valid JSON response",
            actual=f"non-JSON: {str(response_body.get('_raw_body', ''))[:200]}",
            passed=False,
        )]
        return result

    evidence["connectivity"] = connectivity_report

    # =================================================================
    # Layer D: Business Rule — assertion evaluation
    # =================================================================
    api_results = _evaluate_assertions(
        response_status,
        response_body,
        intent.assertions,
    )
    result.assertions = api_results
    result.evidence = evidence

    # --- DB assertions ---
    db_url = sut_db_url or os.getenv("ATP_SUT_DB_URL", "").strip() or None
    if intent.db_assertions and db_url:
        db_results, db_evidence = _execute_db_assertions(
            intent.db_assertions, sut_db_url=db_url,
        )
        result.assertions.extend(db_results)
        evidence["db"] = db_evidence
    elif intent.db_assertions and not db_url:
        result.assertions.append(AssertionResult(
            type="db",
            expected="DB assertions defined",
            actual="ATP_SUT_DB_URL not set",
            passed=False,
        ))
        result.evidence = evidence

    all_passed = all(a.passed for a in result.assertions)
    if all_passed:
        result.status = "passed"
        result.failure_layer = None
    else:
        result.status = "failed"
        result.failure_layer = "business_rule"

    return result


def execute_intents(
    intents: list[TestIntent],
    *,
    base_url: str,
    timeout: int = 30,
    sut_db_url: str | None = None,
    skip_selftest: bool = False,
) -> list[ExecutionResult]:
    """Execute multiple TestIntents and return a list of ExecutionResults.

    Convenience wrapper for batch execution.
    """
    return [
        execute_api_test(i, base_url=base_url, timeout=timeout,
                         sut_db_url=sut_db_url, skip_selftest=skip_selftest)
        for i in intents
    ]
