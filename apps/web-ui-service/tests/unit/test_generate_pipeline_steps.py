"""generate_pipeline 步骤函数的特征测试。保护刚拆分的 6 个步骤函数。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Import step functions
import sys
from pathlib import Path
src_root = Path(__file__).resolve().parents[3] / "app" / "services" / "workbench_generation_compiler" / "runtime"
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.workbench_generation_compiler.runtime.generate_pipeline import (
    _allocate_and_format_case_id,
)


# ---------------------------------------------------------------------------
# _allocate_and_format_case_id —— 最可测的纯数据变换步骤
# ---------------------------------------------------------------------------

class TestAllocateAndFormatCaseId:
    def test_returns_expected_keys(self) -> None:
        payload = SimpleNamespace(
            case_id="", project="atp", title="登录测试", priority="P1",
            tags=["smoke", "login"],
        )
        result = _allocate_and_format_case_id(
            payload=payload,
            case_yaml={"id": "", "execution": {"page": "login"}},
            resolved_page="login",
            normalized_page="login",
            allocate_case_id=lambda **kw: "atp-web-login-fn-ai-0001",
            ai_cases_root=Path("/tmp/cases"),
            existing_case_ids=[],
            page_object={"page_url": "https://example.com/login"},
            execution_payload={"page": "login"},
        )
        assert result["case_id"] == "atp-web-login-fn-ai-0001"
        assert result["case_yaml"]["title"] == "登录测试"
        assert result["case_yaml"]["priority"] == "P1"
        assert result["case_yaml"]["tags"] == ["smoke", "login"]
        assert result["final_page_url"] == "https://example.com/login"

    def test_uses_existing_tags_when_payload_tags_empty(self) -> None:
        payload = SimpleNamespace(
            case_id="", project="atp", title="", priority="", tags=[],
        )
        result = _allocate_and_format_case_id(
            payload=payload,
            case_yaml={"id": "", "tags": ["ai-generated"], "module": "login",
                        "execution": {"page": "login"}},
            resolved_page="login",
            normalized_page="login",
            allocate_case_id=lambda **kw: "case-001",
            ai_cases_root=Path("/tmp/cases"),
            existing_case_ids=[],
            page_object={},
            execution_payload={"page": "login"},
        )
        assert "ai-generated" in result["case_yaml"]["tags"]

    def test_falls_back_to_product_page(self) -> None:
        payload = SimpleNamespace(
            case_id="", project="atp", title="", priority="", tags=[],
        )
        result = _allocate_and_format_case_id(
            payload=payload,
            case_yaml={"id": "", "execution": {}},
            resolved_page="",
            normalized_page="",
            allocate_case_id=lambda **kw: "case-002",
            ai_cases_root=Path("/tmp/cases"),
            existing_case_ids=[],
            page_object={},
            execution_payload={},
        )
        assert result["case_yaml"]["execution"]["page"] == "product"


# ---------------------------------------------------------------------------
# _normalize_and_scope_test_points —— 测试点规范化
# ---------------------------------------------------------------------------

class TestNormalizeAndScopeTestPoints:
    def test_returns_expected_keys(self, monkeypatch) -> None:
        from app.services.workbench_generation_compiler.runtime.generate_pipeline import (
            _normalize_and_scope_test_points,
        )

        payload = SimpleNamespace(project="atp", case_id="test-001")
        result = _normalize_and_scope_test_points(
            payload=payload,
            resolved_page="login",
            test_points=[{"intent_id": "I001", "title": "登录成功", "steps": ["输入账号"]}],
            test_points_payload={"points": []},
            orchestrator_result={},
            selected_intent_ids=set(),
            candidate_snapshots=[],
            requirement_spec=None,
            http_exception_cls=RuntimeError,
            unprocessable_entity_status=422,
        )
        assert isinstance(result, dict)
        assert "test_points" in result
        assert "test_points_payload" in result

    def test_scopes_to_selected_intents(self, monkeypatch) -> None:
        from app.services.workbench_generation_compiler.runtime.generate_pipeline import (
            _normalize_and_scope_test_points,
        )

        payload = SimpleNamespace(project="atp", case_id="test-001")
        result = _normalize_and_scope_test_points(
            payload=payload,
            resolved_page="login",
            test_points=[
                {"intent_id": "I001", "title": "登录成功", "steps": ["输入账号"]},
                {"intent_id": "I002", "title": "登录失败", "steps": ["输入错误密码"]},
            ],
            test_points_payload={"points": []},
            orchestrator_result={},
            selected_intent_ids={"I001"},
            candidate_snapshots=[],
            requirement_spec={"test_intents": [{"intent_id": "I001"}, {"intent_id": "I002"}]},
            http_exception_cls=RuntimeError,
            unprocessable_entity_status=422,
        )
        # After scoping, only I001 should remain
        points = result["test_points"]
        intent_ids = {p.get("intent_id") for p in points if isinstance(p, dict)}
        assert "I001" in intent_ids


# ---------------------------------------------------------------------------
# _handle_generation_exception —— 异常处理（总是 re-raise）
# ---------------------------------------------------------------------------

class TestHandleGenerationException:
    def test_reraises_execution_compiler_error(self) -> None:
        from app.services.workbench_generation_compiler.runtime.generate_pipeline import (
            _handle_generation_exception,
        )
        from shared_backend.execution_compiler import ExecutionCompilerError

        exc = ExecutionCompilerError(code="test_code", message="test error")
        payload = SimpleNamespace(case_id="test-001", source="manual")
        with pytest.raises(Exception):
            _handle_generation_exception(
                exc=exc, trace_id="trace-1", selected_intent_ids_list=[],
                mode="generate", http_exception_cls=RuntimeError,
                unprocessable_entity_status=422,
                is_quality_gate_blocked=lambda detail: (False, {}),
                payload=payload, normalized_page="login",
                multisource_enabled=False,
                append_history=lambda entry: None,
                now_iso=lambda: "2026-01-01T00:00:00Z",
            )

    def test_reraises_unexpected_exception(self) -> None:
        from app.services.workbench_generation_compiler.runtime.generate_pipeline import (
            _handle_generation_exception,
        )

        exc = ValueError("unexpected error")
        payload = SimpleNamespace(case_id="test-001", source="manual")
        with pytest.raises(Exception):
            _handle_generation_exception(
                exc=exc, trace_id="trace-1", selected_intent_ids_list=[],
                mode="generate", http_exception_cls=RuntimeError,
                unprocessable_entity_status=422,
                is_quality_gate_blocked=lambda detail: (False, {}),
                payload=payload, normalized_page="login",
                multisource_enabled=False,
                append_history=lambda entry: None,
                now_iso=lambda: "2026-01-01T00:00:00Z",
            )
