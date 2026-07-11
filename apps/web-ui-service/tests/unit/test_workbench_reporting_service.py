"""workbench_reporting_service 纯函数特征测试。"""
from __future__ import annotations

from app.services.workbench_reporting_service import (
    normalize_failure_source_value,
    normalize_failure_evidence_meta,
    _safe_report_slug,
    _parse_last_json_object,
)
from app.services.workbench_reporting_views import build_report_allure_pending


class TestNormalizeFailureSourceValue:
    def test_returns_known_source(self) -> None:
        assert normalize_failure_source_value("page_object") == "page_object"
        assert normalize_failure_source_value("PAGE_OBJECT") == "page_object"
        assert normalize_failure_source_value("app_bug") == "app_bug"
        assert normalize_failure_source_value("environment") == "environment"

    def test_returns_unknown_for_unrecognized(self) -> None:
        assert normalize_failure_source_value("random_value") == "unknown"
        assert normalize_failure_source_value("") == "unknown"
        assert normalize_failure_source_value(None) == "unknown"


class TestSafeReportSlug:
    def test_replaces_special_chars(self) -> None:
        assert "/" not in _safe_report_slug("a/b/c")
        assert " " not in _safe_report_slug("a b c")


class TestBuildReportAllurePending:
    def test_returns_pending_structure(self) -> None:
        result = build_report_allure_pending(
            reason="no_data", message="暂无数据", legacy_available=False
        )
        assert result["available"] is False
        assert result["report_source"] == "none"
        assert result["reason"] == "no_data"
        assert "summary" in result
        assert result["summary"]["statistic"]["total"] == 0


class TestNormalizeFailureEvidenceMeta:
    def test_returns_healthy_defaults_for_empty(self) -> None:
        result = normalize_failure_evidence_meta({})
        assert result["manifest_entry_count"] == 0
        assert result["compat_scan_entry_count"] == 0
        assert result["policy_mode"] == "compat"
        assert result["health"] == "healthy"

    def test_returns_healthy_defaults_for_none(self) -> None:
        result = normalize_failure_evidence_meta(None)
        assert result["health"] == "healthy"

    def test_detects_degraded_when_compat_scan_present(self) -> None:
        result = normalize_failure_evidence_meta({
            "compat_scan_entry_count": 5,
            "manifest_entry_count": 3,
        })
        assert result["health"] == "degraded"
        assert result["total_visible_entries"] == 8

    def test_respects_explicit_health(self) -> None:
        result = normalize_failure_evidence_meta({"health": "warning"})
        assert result["health"] == "warning"

    def test_computes_manifest_first_ratio(self) -> None:
        result = normalize_failure_evidence_meta({
            "manifest_entry_count": 7,
            "compat_scan_entry_count": 3,
        })
        assert result["manifest_first_ratio"] == 0.7
        assert result["compat_scan_ratio"] == 0.3


class TestParseLastJsonObject:
    def test_parses_multiline_json_object(self) -> None:
        # 函数从文本末尾找单独成行的 { 然后向后解析
        text = "some log line\nanother line\n{\n  \"key\": \"value\"\n}"
        result = _parse_last_json_object(text)
        assert result == {"key": "value"}

    def test_returns_empty_dict_for_empty(self) -> None:
        assert _parse_last_json_object("") == {}

    def test_returns_empty_dict_for_no_json(self) -> None:
        assert _parse_last_json_object("just some text\nno json here") == {}

    def test_parses_last_json_when_multiple_present(self) -> None:
        text = '{\n  "first": 1\n}\nsome text\n{\n  "second": 2\n}'
        result = _parse_last_json_object(text)
        assert result == {"second": 2}
