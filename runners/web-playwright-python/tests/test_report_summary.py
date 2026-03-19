import importlib.util
from pathlib import Path

import pytest


pytestmark = [pytest.mark.contract]


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "tools" / "report_summary.py"
SPEC = importlib.util.spec_from_file_location("web_playwright_python_report_summary", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_report_summary_handles_empty_artifacts_dir(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    output_path = tmp_path / "report_summary.txt"

    result = MODULE.build_report_summary(artifacts_dir, output_path)

    assert result == output_path
    assert output_path.exists()
    text = output_path.read_text(encoding="utf-8")
    assert "Total Analysis Files: 0" in text
    assert "No analysis.txt files were found." in text


def test_build_report_summary_aggregates_analysis_files(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    case_a = artifacts_dir / "tests_test_a"
    case_b = artifacts_dir / "tests_test_b"
    case_a.mkdir(parents=True)
    case_b.mkdir(parents=True)
    (case_a / "analysis.txt").write_text(
        "\n".join(
            [
                "Summary: Product assertion failed.",
                "Failure Category: assertion",
                "Likely Cause: product_list_title was not visible.",
                "Risk Level: high",
                "Recommended Action: Review the assertion target manually.",
                "Confidence: 0.81",
                "Evidence Used: error, page_html, current_url",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (case_b / "analysis.txt").write_text(
        "\n".join(
            [
                "Summary: Timeout waiting for order table.",
                "Failure Category: timeout",
                "Likely Cause: order_table was not ready in time.",
                "Risk Level: medium",
                "Recommended Action: Review wait strategy manually.",
                "Confidence: 0.73",
                "Evidence Used: error, current_url",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (case_a / "suggestion.json").write_text(
        '{"advice_type":"locator_update","target":"product_table","confidence":0.81}',
        encoding="utf-8",
    )
    (case_b / "suggestion.json").write_text(
        '{"advice_type":"no_change","target":"","confidence":0.40}',
        encoding="utf-8",
    )
    output_path = tmp_path / "report_summary.txt"

    MODULE.build_report_summary(artifacts_dir, output_path)

    text = output_path.read_text(encoding="utf-8")
    assert "Total Analysis Files: 2" in text
    assert "Management Summary:" in text
    assert "- Total Failed Cases: 2" in text
    assert "- Environment Failures: 0" in text
    assert "- Business Failures: 2" in text
    assert "- High Risk Failures: 1" in text
    assert "- Cases With Actionable Self-Healing Advice: 1" in text
    assert "- assertion: 1" in text
    assert "- timeout: 1" in text
    assert "- high: 1" in text
    assert "- medium: 1" in text
    assert "1. Case: tests_test_a" in text
    assert "2. Case: tests_test_b" in text
    assert "Actionable Suggestion: yes" in text
    assert "Suggestion Target: product_table" in text
    assert "Review the assertion target manually." in text
    assert "Review wait strategy manually." in text


def test_build_report_summary_finds_nested_analysis_files(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    nested_case = artifacts_dir / "nested" / "tests_test_c"
    nested_case.mkdir(parents=True)
    (nested_case / "analysis.txt").write_text(
        "\n".join(
            [
                "Summary: Nested analysis file.",
                "Failure Category: locator",
                "Likely Cause: stale target.",
                "Risk Level: low",
                "Recommended Action: Review locator target manually.",
                "Confidence: 0.66",
                "Evidence Used: error, page_html",
                "",
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "report_summary.txt"

    MODULE.build_report_summary(artifacts_dir, output_path)

    text = output_path.read_text(encoding="utf-8")
    assert "Total Analysis Files: 1" in text
    assert "Case: tests_test_c" in text
    assert "- locator: 1" in text


def test_build_report_summary_manifest_first_supports_non_default_names(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    case_dir = artifacts_dir / "case_manifest_first"
    case_dir.mkdir(parents=True)
    (case_dir / "failure-analysis-alt.txt").write_text(
        "\n".join(
            [
                "Summary: Manifest first analysis.",
                "Failure Category: assertion",
                "Likely Cause: non-default analysis file path.",
                "Risk Level: high",
                "Recommended Action: Review locator manually.",
                "Confidence: 0.91",
                "Evidence Used: error, page_html",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (case_dir / "healing-suggestion-alt.json").write_text(
        '{"advice_type":"locator_update","target":"product_table","confidence":0.91}',
        encoding="utf-8",
    )
    (case_dir / "evidence_manifest.json").write_text(
        """
{
  "schema_version": "evidence-manifest.v1",
  "generated_at": "2026-03-18T00:00:00+00:00",
  "artifact_root": ".",
  "screenshots": [],
  "html_pages": [],
  "meta_files": [],
  "analysis_files": ["failure-analysis-alt.txt"],
  "suggestion_files": ["healing-suggestion-alt.json"],
  "execution_record_files": [],
  "self_healing_result_files": [],
  "videos": [],
  "other_files": [],
  "total_files": 2
}
""".strip(),
        encoding="utf-8",
    )
    output_path = tmp_path / "report_summary.txt"

    MODULE.build_report_summary(artifacts_dir, output_path)

    text = output_path.read_text(encoding="utf-8")
    assert "Total Analysis Files: 1" in text
    assert "Manifest first analysis." in text
    assert "Suggestion Target: product_table" in text
    assert "Source File: " in text
    assert "failure-analysis-alt.txt" in text


def test_build_report_summary_ignores_invalid_manifest_and_uses_legacy_scan(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    case_dir = artifacts_dir / "case_invalid_manifest"
    case_dir.mkdir(parents=True)
    (case_dir / "analysis.txt").write_text(
        "\n".join(
            [
                "Summary: Legacy analysis fallback.",
                "Failure Category: timeout",
                "Likely Cause: invalid manifest should be ignored.",
                "Risk Level: medium",
                "Recommended Action: Review wait manually.",
                "Confidence: 0.72",
                "Evidence Used: error, current_url",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (case_dir / "evidence_manifest.json").write_text(
        '{"schema_version":"evidence-manifest.v0","analysis_files":"invalid"}',
        encoding="utf-8",
    )
    output_path = tmp_path / "report_summary.txt"

    MODULE.build_report_summary(artifacts_dir, output_path)

    text = output_path.read_text(encoding="utf-8")
    assert "Total Analysis Files: 1" in text
    assert "Legacy analysis fallback." in text
    assert "case_invalid_manifest" in text
