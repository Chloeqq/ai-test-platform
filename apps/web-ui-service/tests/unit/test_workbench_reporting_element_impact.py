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
