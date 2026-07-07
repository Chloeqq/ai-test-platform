from __future__ import annotations

import json
from pathlib import Path

from app.services import workbench_reporting_service


def test_parse_analysis_file_preserves_failed_step_and_element_impact(tmp_path: Path) -> None:
    analysis_path = tmp_path / "analysis.txt"
    analysis_path.write_text(
        "\n".join(
            [
                "Summary: locator timeout",
                'Failed Step: {"page_code": "product", "element_code": "product_name_input"}',
                'Element Impact: {"governance_href": "/assets/page-objects/product/elements/product_name_input?project=mall"}',
                "",
            ]
        ),
        encoding="utf-8",
    )

    parsed = workbench_reporting_service.parse_analysis_file(analysis_path)

    assert parsed["failed_step"]["element_code"] == "product_name_input"
    assert parsed["element_impact"]["governance_href"].endswith("product_name_input?project=mall")


def test_parse_analysis_file_reads_final_json_when_inline_json_exists(tmp_path: Path) -> None:
    analysis_path = tmp_path / "analysis.txt"
    analysis_path.write_text(
        "\n".join(
            [
                "Summary: locator timeout",
                'Failed Step: {"page_code": "product", "element_code": "product_name_input"}',
                'Element Impact: {"governance_href": "/assets/page-objects/product/elements/product_name_input?project=mall"}',
                "",
                json.dumps(
                    {
                        "evidence_used": ["error", "page_html"],
                        "source_evidence": [{"kind": "dom"}],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )

    parsed = workbench_reporting_service.parse_analysis_file(analysis_path)

    assert parsed["evidence_used"] == ["error", "page_html"]
    assert parsed["source_evidence"] == [{"kind": "dom"}]


def test_build_report_failures_exposes_governance_link_from_execution_record(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    analysis_path = case_dir / "analysis.txt"
    analysis_path.write_text("Summary: locator timeout\n", encoding="utf-8")
    record_path = case_dir / "execution_record.json"
    record_payload = {
        "case_id": "tc-product-GEN-001",
        "finished_at": "2026-05-01T00:00:00+00:00",
        "metadata": {
            "failed_step": {"page_code": "product", "element_code": "product_name_input"},
            "element_impact": {
                "project_code": "mall",
                "page_code": "product",
                "element_code": "product_name_input",
                "governance_href": "/assets/page-objects/product/elements/product_name_input?project=mall",
            },
        },
    }
    record_path.write_text(json.dumps(record_payload), encoding="utf-8")
    manifest_path = case_dir / "evidence_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "analysis_files": ["analysis.txt"],
                "execution_record_files": ["execution_record.json"],
            }
        ),
        encoding="utf-8",
    )

    def _collect() -> tuple[list[dict], dict]:
        return workbench_reporting_service.collect_failure_entries_with_meta(
            compat_scan_enabled=False,
            artifact_roots=[tmp_path],
            logger=None,
            normalize_evidence_manifest_payload=lambda payload: payload,
            resolve_manifest_entries=lambda value, root: [root / item for item in (value or [])],
            load_execution_record_payload=lambda path: json.loads(Path(path).read_text(encoding="utf-8")),
            parse_analysis_file=workbench_reporting_service.parse_analysis_file,
        )

    payload = workbench_reporting_service.build_report_failures(
        case_id="",
        keyword="",
        defect_status="all",
        collect_failure_entries_with_meta=_collect,
        normalize_failure_evidence_meta=workbench_reporting_service.normalize_failure_evidence_meta,
        read_defect_items=lambda: [],
    )

    row = payload["items"][0]
    assert row["element_impact"]["element_code"] == "product_name_input"
    assert row["governance_href"].endswith("product_name_input?project=mall")


def test_build_report_allure_uses_readable_version_and_keeps_cache_version(tmp_path: Path) -> None:
    payload = workbench_reporting_service.build_report_allure(
        available=True,
        read_allure_summary=lambda: {
            "reportName": "Allure Report",
            "statistic": {"total": 3},
            "time": {"stop": 1778566103555},
        },
        read_allure_environment=lambda: [{"name": "Project", "values": ["mall"]}],
        read_allure_executors=lambda: [{"name": "AI 自动化测试平台", "type": "pytest-playwright"}],
        ensure_allure_snapshot=lambda *, version, snapshot_slug: f"/allure-snapshots/{snapshot_slug}/index.html",
        get_allure_index_version=lambda: 1778566103555927300,
        current_results_dir=tmp_path / "run-artifacts" / "allure-results",
    )

    assert payload["version"] == "Allure-2026-05-12-Run03"
    assert payload["display_version"] == "Allure-2026-05-12-Run03"
    assert payload["cache_version"] == 1778566103555927300
    assert payload["allure_index"] == "/allure-snapshots/Allure-2026-05-12-Run03/index.html"
    assert payload["report_name"] == "AI 自动化测试执行报告 (Allure-2026-05-12-Run03)"
    assert payload["environment"] == [{"name": "Project", "values": ["mall"]}]
    assert payload["executors"] == [{"name": "AI 自动化测试平台", "type": "pytest-playwright"}]


def test_build_report_allure_uses_version_from_business_report_name(tmp_path: Path) -> None:
    payload = workbench_reporting_service.build_report_allure(
        available=True,
        read_allure_summary=lambda: {
            "reportName": "首次登录成功 - 回归执行报告 (mall-web-login-auth-fn-ai-0001-v1.run-abc12345)",
            "statistic": {"total": 1},
            "time": {"stop": 1778566103555},
        },
        read_allure_environment=lambda: [],
        read_allure_executors=lambda: [],
        ensure_allure_snapshot=lambda *, version, snapshot_slug: f"/allure-snapshots/{snapshot_slug}/index.html",
        get_allure_index_version=lambda: 1778566103555927300,
        current_results_dir=tmp_path / "run-artifacts" / "allure-results",
    )

    assert payload["version"] == "mall-web-login-auth-fn-ai-0001-v1.run-abc12345"
    assert payload["snapshot_slug"] == "mall-web-login-auth-fn-ai-0001-v1.run-abc12345"


def test_build_report_allure_without_run_scoped_results_returns_pending() -> None:
    payload = workbench_reporting_service.build_report_allure(
        available=True,
        read_allure_summary=lambda: {"statistic": {"total": 3}},
        read_allure_environment=lambda: [],
        read_allure_executors=lambda: [],
        ensure_allure_snapshot=lambda **_kwargs: "/allure-snapshots/legacy/index.html",
        get_allure_index_version=lambda: 123,
    )

    assert payload["available"] is False
    assert payload["report_source"] == "none"
    assert payload["reason"] == "no_run_scoped_allure_results"
    assert payload["legacy_available"] is True
    assert payload["summary"]["statistic"]["total"] == 0


def test_find_latest_run_allure_results_prefers_newest_result(tmp_path: Path) -> None:
    older = tmp_path / "web-ui" / "state" / "runs" / "older-artifacts" / "allure-results"
    newer = tmp_path / "web-ui" / "state" / "runs" / "newer-artifacts" / "allure-results"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    older_result = older / "old-result.json"
    newer_result = newer / "new-result.json"
    older_result.write_text("{}", encoding="utf-8")
    newer_result.write_text("{}", encoding="utf-8")
    older_mtime = 1_000_000
    newer_mtime = 2_000_000
    older_result.touch()
    newer_result.touch()
    import os

    os.utime(older_result, (older_mtime, older_mtime))
    os.utime(newer_result, (newer_mtime, newer_mtime))

    assert workbench_reporting_service.find_latest_run_allure_results(repo_root=tmp_path) == newer


def test_inject_allure_branding_inserts_style_before_head_end() -> None:
    html = "<html><head><title>Allure</title></head><body></body></html>"

    branded = workbench_reporting_service.inject_allure_branding(html)

    assert "data-atp-allure-branding" in branded
    assert branded.index("data-atp-allure-branding") < branded.index("</head>")
    assert "--atp-success-bg: #ecfdf3" in branded


def test_inject_allure_branding_is_idempotent() -> None:
    html = "<html><head></head><body></body></html>"

    branded = workbench_reporting_service.inject_allure_branding(html)
    branded_again = workbench_reporting_service.inject_allure_branding(branded)

    assert branded_again == branded
    assert branded_again.count("data-atp-allure-branding") == 1


def test_inject_allure_branding_appends_when_head_is_missing() -> None:
    html = "<html><body>Allure</body></html>"

    branded = workbench_reporting_service.inject_allure_branding(html)

    assert branded.startswith(html)
    assert "data-atp-allure-branding" in branded
