from __future__ import annotations

from app.services.test_case_data_service import normalize_report_url


def test_normalize_report_url_uses_new_execution_results_path() -> None:
    assert normalize_report_url("", 101) == "/execution/results/101"
    assert normalize_report_url("  /legacy/report  ", 202) == "/execution/results/202"
    assert normalize_report_url("https://report.local/latest", 303) == "https://report.local/latest"
