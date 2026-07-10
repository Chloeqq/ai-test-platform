"""ATP API Test Models — Sprint 1 Day 1.

Pydantic models for TestIntent, ExecutionResult, and TestReport.
No database dependency. Used by api_step_runner.py.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# TestIntent — 用户定义"测什么、怎么测、期望什么"
# ---------------------------------------------------------------------------

class ApiRequest(BaseModel):
    """API 请求定义。Phase 1 仅支持 POST + JSON body。"""
    method: str = "POST"
    path: str = ""
    body: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)


class Assertion(BaseModel):
    """单条断言：检查 response 的 status 或 JSON path。"""
    type: str = "status"  # "status" | "json" | "assert_text" | "assert_visible" | "assert_url" | "protocol" | "db"
    path: str | None = None       # JSON path（type="json" 时必填），如 "code"、"data.token"
    expected: Any = None          # 期望值
    operator: str = "eq"          # "eq" | "contains" | "exists" | "not_empty"


class DbAssertion(BaseModel):
    """DB 断言：直接写 SQL + 期望结果。"""
    sql: str = ""
    expected: Literal["exists", "not_exists"] | None = None
    expected_value: int | None = None  # count(*) 时使用


class TestIntent(BaseModel):
    """一个测试意图：包含 API 请求 + 断言 + 可选的 DB 断言。"""
    name: str = ""
    scenario: Literal["positive", "negative", "boundary"] = "positive"
    api_request: ApiRequest = Field(default_factory=ApiRequest)
    assertions: list[Assertion] = Field(default_factory=list)
    db_assertions: list[DbAssertion] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# ExecutionResult — 执行结果 + 故障归因
# ---------------------------------------------------------------------------

class AssertionResult(BaseModel):
    """单条断言的执行结果。"""
    type: str = ""  # "status" | "json" | "db" | "protocol" | "reliability_gate" | "assert_text" | ...
    path: str | None = None
    expected: Any = None
    actual: Any = None
    passed: bool = False


class ExecutionResult(BaseModel):
    """单个 TestIntent 的执行结果。"""
    intent_name: str = ""
    status: Literal["passed", "failed"] = "failed"
    assertions: list[AssertionResult] = Field(default_factory=list)
    failure_layer: str | None = None
    # "platform" | "network" | "api_contract" | "business_rule"
    platform_error: bool = False
    # true = ATP自身问题，被测系统未被有效测试
    platform_error_details: str = ""
    connectivity_report: dict[str, Any] = Field(default_factory=dict)
    # {dns_ok, tcp_connected, tls_ok, latency_ms, ...}
    evidence: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# UIEvidence — 外部 UI 测试结果接入（输入 DTO，非核心 Model）
# ---------------------------------------------------------------------------

class UIAssertion(BaseModel):
    """单条 UI 断言的原始信息。"""
    type: str = ""
    target: str = ""
    expected: str = ""
    actual: str = ""


class UIEvidence(BaseModel):
    """外部 UI 测试结果接入合约。Phase 1 支持 Playwright JSON 输出。

    ATP 不负责执行 UI 测试。
    ATP 负责接入已有 UI 自动化结果，判断其可信度。
    """
    case_id: str = ""
    intent_name: str = ""
    status: str = ""         # "passed" | "failed"
    assertions: list[UIAssertion] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# TestReport — 汇总报告
# ---------------------------------------------------------------------------

class TestReport(BaseModel):
    """一次完整测试的汇总报告。"""
    summary: str = ""
    results: list[ExecutionResult] = Field(default_factory=list)
    calibrations: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    confidence_level: str = ""
    # "Level_A" | "Level_B" | "Level_C"
