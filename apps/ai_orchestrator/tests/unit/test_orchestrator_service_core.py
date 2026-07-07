"""OrchestratorService 核心纯函数测试。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

src_root = Path(__file__).resolve().parents[2] / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from http import HTTPStatus
from orchestrator_service import (
    OrchestratorError,
    OrchestratorValidationError,
    RunnerExecutionError,
    OrchestrationResult,
    OrchestratorService,
)


class TestOrchestratorError:
    def test_to_response_includes_code_and_message(self) -> None:
        err = OrchestratorError(code="test_code", message="test message")
        resp = err.to_response()
        assert resp["error"]["code"] == "test_code"
        assert resp["error"]["message"] == "test message"
        assert "details" not in resp["error"]

    def test_to_response_includes_details_when_present(self) -> None:
        err = OrchestratorError(
            code="test_code", message="test message",
            details={"extra": "info"},
        )
        resp = err.to_response()
        assert resp["error"]["details"] == {"extra": "info"}

    def test_default_status_code_is_500(self) -> None:
        err = OrchestratorError(code="x", message="y")
        assert err.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class TestOrchestratorValidationError:
    def test_has_422_status_and_validation_code(self) -> None:
        err = OrchestratorValidationError("bad input", details={"field": "page"})
        assert err.code == "validation_error"
        assert err.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "details" in err.to_response()["error"]


class TestRunnerExecutionError:
    def test_has_502_status_and_runner_code(self) -> None:
        err = RunnerExecutionError("runner crashed")
        assert err.code == "runner_failed"
        assert err.status_code == HTTPStatus.BAD_GATEWAY


class TestAgentPipelineOrder:
    def test_returns_8_agents_in_order(self) -> None:
        order = OrchestratorService.agent_pipeline_order()
        assert len(order) == 8
        assert order[0] == "requirement-parser-agent"
        assert order[-1] == "self-healing-advisor-agent"

    def test_requirement_parser_is_first(self) -> None:
        order = OrchestratorService.agent_pipeline_order()
        assert "requirement" in order[0]


class TestSerializeResult:
    def test_round_trips_dict(self) -> None:
        result = OrchestrationResult(
            requirement_spec={}, case={}, generated_script={},
            execution_plan={}, design_generation={}, risk_report={},
            failure_triage={}, agent_pipeline=[], test_points={},
            execution_record={}, case_path="", execution_requested=False,
        )
        serialized = OrchestratorService.serialize_result(result)
        assert serialized["case_path"] == ""
        assert serialized["execution_requested"] is False


class TestRenderRequirementSpec:
    def test_delegates_to_support(self) -> None:
        markdown = OrchestratorService.render_requirement_spec_markdown({})
        assert isinstance(markdown, str)
