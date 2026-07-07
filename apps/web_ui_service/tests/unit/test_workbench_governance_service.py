"""workbench_governance_service + _helpers 单元测试。"""
from __future__ import annotations

from datetime import datetime
from shared_backend.datetime_compat import UTC
from unittest.mock import MagicMock

import pytest

from app.services.workbench_governance_service import build_flaky_top5
from app.api.workbench._helpers import (
    build_empty_trend,
    default_overview,
    text,
    to_utc,
    utc_now,
    normalize_optional_project_code,
    parse_iso_datetime,
    read_json_file,
    write_json_file,
    is_within,
    python_literal,
    safe_python_identifier,
    validate_test_point_review_status,
)


class TestBuildFlakyTop5:
    def test_returns_empty_list_when_no_cases(self) -> None:
        result = build_flaky_top5([], [])
        assert result == []

    def test_returns_seed_estimate_when_no_executions(self) -> None:
        """cases 有记录但 executions 为空 → 仍返回 seed 估算值，不返回空列表。"""
        case = MagicMock()
        case.id = 1
        case.name = "test"
        case.module = "core"
        case.last_execution_result = "unknown"
        result = build_flaky_top5([case], [])
        assert len(result) == 1
        assert result[0]["total_runs"] == 0
        assert result[0]["flaky_rate"] > 0

    def test_returns_max_5_items(self) -> None:
        cases = []
        executions = []
        for i in range(10):
            c = MagicMock()
            c.id = i
            c.name = f"case-{i}"
            c.module = "core"
            c.last_execution_result = "unknown"
            cases.append(c)
            # Add 2 executions per case with alternating pass/fail
            for j in range(2):
                e = MagicMock()
                e.case_id = i
                e.status = "passed" if j == 0 else "failed"
                e.executed_at = datetime(2026, 1, i + 1, tzinfo=UTC)
                e.id = i * 10 + j
                executions.append(e)

        result = build_flaky_top5(cases, executions)
        assert len(result) <= 5
        for item in result:
            assert "case_id" in item
            assert "name" in item
            assert "flaky_rate" in item
            assert "total_runs" in item
            assert "unstable_runs" in item
            assert "last_result" in item

    def test_single_execution_uses_seed_estimate(self) -> None:
        case = MagicMock()
        case.id = 100
        case.name = "single-run"
        case.module = "core"
        case.last_execution_result = "passed"

        execution = MagicMock()
        execution.case_id = 100
        execution.status = "passed"
        execution.executed_at = datetime(2026, 1, 1, tzinfo=UTC)
        execution.id = 1

        result = build_flaky_top5([case], [execution])
        assert len(result) == 1
        # Single execution → seed-based estimate, should be > 0
        assert result[0]["flaky_rate"] > 0
        assert result[0]["total_runs"] == 1
        assert result[0]["unstable_runs"] == 0


class TestBuildEmptyTrend:
    def test_returns_24_hours(self) -> None:
        now = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
        result = build_empty_trend(now)
        assert len(result) == 24
        for item in result:
            assert "hour" in item
            assert item["pass_rate"] == 0.0
            assert item["execution_count"] == 0


class TestDefaultOverview:
    def test_returns_degraded_response(self) -> None:
        now = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
        result = default_overview(now, "test_degraded")
        assert result["risk"]["level"] == "数据不可用"
        assert result["risk"]["score"] == 0
        assert len(result["trend_24h"]) == 24
        assert result["top_flaky"] == []
        assert result["gate_last10"] == []
        assert result["pending_issues"] == []


# ---------------------------------------------------------------------------
# _helpers.py 纯函数测试
# ---------------------------------------------------------------------------

class TestText:
    def test_returns_stripped_string(self) -> None:
        assert text(" hello ") == "hello"
        assert text(42) == "42"
        assert text(None) == ""
        assert text("") == ""


class TestToUtc:
    def test_adds_utc_to_naive(self) -> None:
        result = to_utc(datetime(2026, 1, 1, 12, 0, 0))
        assert result.tzinfo == UTC

    def test_returns_current_utc_for_none(self) -> None:
        result = to_utc(None)
        assert result.tzinfo == UTC


class TestUtcNow:
    def test_returns_utc(self) -> None:
        assert utc_now().tzinfo == UTC


class TestNormalizeOptionalProjectCode:
    def test_handles_all_inputs(self) -> None:
        assert normalize_optional_project_code(None) == ""
        assert normalize_optional_project_code("ATP") == "atp"
        assert normalize_optional_project_code("  Mall ") == "mall"


class TestParseIsoDatetime:
    def test_returns_none_for_empty(self) -> None:
        assert parse_iso_datetime("") is None

    def test_parses_z_suffix(self) -> None:
        result = parse_iso_datetime("2026-01-01T12:00:00Z")
        assert result is not None
        assert result.tzinfo == UTC


class TestReadWriteJsonFile:
    def test_read_returns_empty_dict_for_nonexistent(self, tmp_path) -> None:
        assert read_json_file(tmp_path / "nonexistent.json") == {}

    def test_write_then_read(self, tmp_path) -> None:
        path = tmp_path / "test.json"
        write_json_file(path, {"key": "value"})
        assert read_json_file(path) == {"key": "value"}


class TestIsWithin:
    def test_path_inside_root(self, tmp_path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        child = root / "child.txt"
        child.write_text("x")
        assert is_within(child, root) is True

    def test_path_outside_root(self, tmp_path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("x")
        assert is_within(outside, root) is False


class TestPythonLiteral:
    def test_returns_quoted_string(self) -> None:
        assert python_literal("hello") == '"hello"'

    def test_returns_number_as_string(self) -> None:
        assert python_literal(42) == "42"


class TestSafePythonIdentifier:
    def test_lowercases_and_filters(self) -> None:
        assert safe_python_identifier("Hello World") == "hello_world"

    def test_falls_back_when_empty(self) -> None:
        assert safe_python_identifier("") == "intent"

    def test_uses_custom_fallback(self) -> None:
        assert safe_python_identifier("", fallback="login") == "login"


class TestValidateTestPointReviewStatus:
    def test_returns_pending_for_unknown(self) -> None:
        assert validate_test_point_review_status("unknown-status") == "pending"

    def test_returns_approved_for_approve(self) -> None:
        assert validate_test_point_review_status("approve") == "approved"

    def test_accepts_valid_status(self) -> None:
        assert validate_test_point_review_status("approved") == "approved"
