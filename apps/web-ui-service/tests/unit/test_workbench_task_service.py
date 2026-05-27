"""workbench_task_service 纯函数特征测试。"""
from __future__ import annotations

from app.services.workbench_task_service import (
    parse_optional_bool_query,
    execution_record_time_value,
    build_task_governance_risk,
)


class TestParseOptionalBoolQuery:
    def test_returns_true_for_truthy(self) -> None:
        for val in ("1", "true", "yes", "y", "on", "TRUE", "YES"):
            assert parse_optional_bool_query(val) is True, f"failed for {val}"

    def test_returns_false_for_falsy(self) -> None:
        for val in ("0", "false", "no", "n", "off", "FALSE"):
            assert parse_optional_bool_query(val) is False, f"failed for {val}"

    def test_returns_none_for_empty_or_unknown(self) -> None:
        assert parse_optional_bool_query("") is None
        assert parse_optional_bool_query(None) is None
        assert parse_optional_bool_query("maybe") is None


class TestExecutionRecordTimeValue:
    def test_prefers_finished_at(self) -> None:
        record = {"finished_at": "2026-01-01T12:00:00Z", "started_at": "earlier", "created_at": "even_earlier"}
        assert execution_record_time_value(record) == "2026-01-01T12:00:00Z"

    def test_falls_back_to_started_at(self) -> None:
        record = {"started_at": "start_time", "created_at": "created_time"}
        assert execution_record_time_value(record) == "start_time"

    def test_falls_back_to_created_at(self) -> None:
        record = {"created_at": "created_time"}
        assert execution_record_time_value(record) == "created_time"

    def test_returns_empty_for_missing_all(self) -> None:
        assert execution_record_time_value({}) == ""


class TestBuildTaskGovernanceRisk:
    def test_returns_structured_risk(self) -> None:
        result = build_task_governance_risk({
            "evidence_health": {"status": "healthy"},
            "evidence_freshness": {"status": "fresh"},
            "manifest_action": "ok",
        })
        assert "level" in result
        assert "score" in result
        assert isinstance(result["score"], int)

    def test_handles_empty_input(self) -> None:
        result = build_task_governance_risk({})
        assert "level" in result
        assert "score" in result

    def test_high_risk_for_degraded_stale_inspect(self) -> None:
        result = build_task_governance_risk({
            "evidence_health": {"status": "degraded"},
            "evidence_freshness": {"status": "stale"},
            "manifest_action": "inspect_source",
        })
        assert result["level"] == "critical"
        assert result["score"] >= 10
